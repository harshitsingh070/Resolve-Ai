"""
test_intent.py — no live Groq needed, tests parsing/validation + fallback + prompt grounding.
"""
import json
import pytest
from app.agent.intent import IntentResult, IntentEntities, _parse_and_validate, fallback_intent
from app.agent.prompts import INTENT_PROMPT, RESPONSE_PROMPT


class TestParseValidate:
    def test_valid_json(self):
        raw = json.dumps({"primary_intent": "hotel_request", "secondary_intents": ["fare_waiver_request"], "sentiment": "frustrated", "requested_exception": True, "entities": {"amount": 2000, "hotel_type": "full_night"}})
        r = _parse_and_validate(raw)
        assert r.primary_intent == "hotel_request" and r.entities.amount == 2000

    def test_fence_stripped(self):
        raw = "```json\n" + json.dumps({"primary_intent": "refund_request", "sentiment": "angry", "entities": {}}) + "\n```"
        r = _parse_and_validate(raw)
        assert r.primary_intent == "refund_request"

    def test_amount_string_rupee(self):
        raw = json.dumps({"primary_intent": "fare_waiver_request", "sentiment": "neutral", "entities": {"amount": "₹2,000"}})
        r = _parse_and_validate(raw)
        assert r.entities.amount == 2000

    def test_invalid_intent_fallback(self):
        raw = json.dumps({"primary_intent": "invalid_intent", "sentiment": "neutral", "entities": {}})
        r = _parse_and_validate(raw)
        assert r.primary_intent == "unknown"

    def test_legal_threat_preserved(self):
        raw = json.dumps({"primary_intent": "complaint", "sentiment": "legal_threat", "requested_exception": True, "entities": {}})
        r = _parse_and_validate(raw)
        assert r.sentiment == "legal_threat"


class TestFallback:
    def test_hotel_paraphrases(self):
        # both should map to hotel_request via fallback (proves deterministic without LLM)
        for msg in ["I need somewhere to stay.", "Can you arrange accommodation?", "I want a hotel for tonight"]:
            r = fallback_intent(msg)
            assert r.primary_intent == "hotel_request", msg

    def test_fare_waiver_amount(self):
        r = fallback_intent("waive my 2000 fare difference")
        assert r.primary_intent == "fare_waiver_request" and r.entities.amount == 2000

    def test_legal_threat(self):
        r = fallback_intent("I will sue you and file a formal complaint")
        assert r.sentiment == "legal_threat"


class TestPromptsGrounded:
    def test_intent_prompt_has_no_policy(self):
        # ensure we never ask LLM to decide policy
        low = INTENT_PROMPT.lower()
        assert "should we give" not in low
        assert "is it allowed" not in low
        assert "policy_result" not in low  # intent is before policy

    def test_response_prompt_grounding(self):
        low = RESPONSE_PROMPT.lower()
        assert "ground your answer only in the verified" in low
        assert "do not invent" in low
        assert "policy result" in low
        assert "verified booking facts" in low

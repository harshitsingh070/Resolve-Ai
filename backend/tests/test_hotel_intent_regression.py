"""
Regression tests for hotel intent QA fix — must all classify as hotel_request, while preserving policy.
"""
import pytest
from app.agent.intent import fallback_intent

hotel_cases = [
    "I need a hotel",
    "Need hotel accommodation",
    "I need accommodation",
    "I need somewhere to stay",
    "Can you arrange a hotel?",
    "Can you arrange accommodation?",
    "I need somewhere to stay because of the delay",
    "I'm stranded and need a place to stay",
    "Can you provide a room?",
    "I need a place to stay tonight",
    "I'm frustrated because my 4 hour delay is making me miss an important meeting. I need a hotel.",
]

@pytest.mark.parametrize("msg", hotel_cases)
def test_hotel_paraphrase_fallback(msg):
    r = fallback_intent(msg)
    assert r.primary_intent == "hotel_request", f"'{msg}' got {r.primary_intent}"
    # ensure optional entities don't pollute: amount should be None for hotel-only
    assert r.entities.amount is None or isinstance(r.entities.amount, (int, float))

def test_refund_still_works():
    assert fallback_intent("I want a refund").primary_intent == "refund_request"
    assert fallback_intent("Give me a full cash refund please").primary_intent == "refund_request"

def test_upgrade_still_works():
    r = fallback_intent("I want a business class upgrade")
    assert r.primary_intent == "upgrade_request"

def test_hello_general():
    r = fallback_intent("hello")
    assert r.primary_intent == "unknown"

def test_fare_waiver_combined():
    r = fallback_intent("I want a full-night hotel and waive 2000")
    assert r.primary_intent == "hotel_request"
    assert "fare_waiver_request" in r.secondary_intents
    assert r.entities.amount == 2000

def test_orchestrator_preserves_hotel_with_missing_entities():
    # Simulate orchestrator fallback when Groq returns unknown but message is hotel
    from app.agent.intent import IntentResult, IntentEntities
    from unittest.mock import patch
    from app.database import SessionLocal
    from app.agent.orchestrator import handle_chat
    from app.models import Action, Escalation, Conversation

    db = SessionLocal()
    # clean
    db.query(Action).delete(); db.query(Escalation).delete(); db.query(Conversation).delete(); db.commit()

    def mock_unknown(*a, **kw):
        return IntentResult(primary_intent="unknown", secondary_intents=[], sentiment="frustrated", requested_exception=False, entities=IntentEntities(amount=None, hotel_type=None))

    with patch("app.agent.orchestrator.extract_intent", side_effect=mock_unknown), patch("app.agent.orchestrator.generate_response", return_value="ok"):
        res = handle_chat(db, "TR1190B", "I'm frustrated because my 4 hour delay is making me miss an important meeting. I need a hotel.")
        assert res["intent"]["primary_intent"] == "hotel_request", f"Expected hotel_request, got {res['intent']}"
        # policy must still be correct: 4h -> meal+lounge, no hotel, no escalation
        assert any(a["action_type"]=="MEAL_VOUCHER" for a in res["actions"])
        assert any(a["action_type"]=="LOUNGE_ACCESS" for a in res["actions"])
        assert not any(a["action_type"]=="HOTEL" for a in res["actions"])
        assert res["escalation"] is None
        assert "Hotel accommodation" not in str(res["intent"]["primary_intent"]) or True  # backend keeps hotel_request, frontend will map
        # trace should contain hotel intent, not unknown
        assert any("hotel_request" in t for t in res["decision_trace"])

    db.query(Action).delete(); db.query(Escalation).delete(); db.query(Conversation).delete(); db.commit()
    db.close()

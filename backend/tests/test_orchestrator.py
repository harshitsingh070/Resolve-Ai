"""
test_orchestrator.py — end-to-end (policy+tools+audit, Groq mocked).
Uses real DB, mocks Groq via fallback_intent when Groq fails, so tests are deterministic.
"""
import pytest
from app.database import SessionLocal, Base, engine
from app.models import Action, Conversation, Escalation
from app.agent.orchestrator import handle_chat
from unittest.mock import patch

@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()

@pytest.fixture(autouse=True)
def clean(db):
    db.query(Action).delete()
    db.query(Escalation).delete()
    db.query(Conversation).delete()
    db.commit()
    yield
    db.query(Action).delete()
    db.query(Escalation).delete()
    db.query(Conversation).delete()
    db.commit()

def mock_intent_refund(*args, **kwargs):
    from app.agent.intent import IntentResult, IntentEntities
    return IntentResult(primary_intent="refund_request", secondary_intents=[], sentiment="frustrated", requested_exception=False, entities=IntentEntities())

def mock_intent_hotel_4h(*args, **kwargs):
    from app.agent.intent import IntentResult, IntentEntities
    return IntentResult(primary_intent="hotel_request", secondary_intents=[], sentiment="neutral", requested_exception=False, entities=IntentEntities(hotel_type=None))

def mock_intent_hotel_fullnight_fare2000(*args, **kwargs):
    from app.agent.intent import IntentResult, IntentEntities
    return IntentResult(primary_intent="hotel_request", secondary_intents=["fare_waiver_request"], sentiment="neutral", requested_exception=True, entities=IntentEntities(amount=2000, hotel_type="full_night"))

def mock_intent_priya(*args, **kwargs):
    from app.agent.intent import IntentResult, IntentEntities
    return IntentResult(primary_intent="refund_request", secondary_intents=["upgrade_request"], sentiment="angry", requested_exception=True, entities=IntentEntities(upgrade_class="business"))

class TestOrchestrator:
    def test_priya_refund_and_upgrade_escalate(self, db):
        with patch("app.agent.orchestrator.extract_intent", side_effect=mock_intent_priya), \
             patch("app.agent.orchestrator.generate_response", return_value="Refund initiated, upgrade escalated"):
            res = handle_chat(db, "SK4821X", "I want refund and business upgrade")
        assert any(a["action_type"]=="REFUND_INITIATED" for a in res["actions"])
        assert res["escalation"] is not None and res["escalation"]["reason"]=="upgrade_exception"
        assert "refund" in res["decision_trace"][3].lower() or "REFUND" in str(res["decision_trace"])
        # audit
        assert db.query(Conversation).count() == 2  # user + assistant

    def test_arvind_4h_hotel_blocked_meal_lounge_given(self, db):
        with patch("app.agent.orchestrator.extract_intent", side_effect=mock_intent_hotel_4h), \
             patch("app.agent.orchestrator.generate_response", return_value="Hotel blocked, meal lounge given"):
            res = handle_chat(db, "TR1190B", "Need hotel accommodation")
        assert any(a["action_type"]=="MEAL_VOUCHER" for a in res["actions"])
        assert any(a["action_type"]=="LOUNGE_ACCESS" for a in res["actions"])
        assert not any(a["action_type"]=="HOTEL" for a in res["actions"])
        assert res["escalation"] is None
        # trace mentions over 5h
        assert any("over 5h" in t for t in res["decision_trace"])

    def test_meher_6h_fullnight_blocked_fare2000_escalate(self, db):
        with patch("app.agent.orchestrator.extract_intent", side_effect=mock_intent_hotel_fullnight_fare2000), \
             patch("app.agent.orchestrator.generate_response", return_value="Hotel delayed only, fare escalated"):
            res = handle_chat(db, "WL7742", "Give me full night hotel and waive 2000")
        # meal + lounge + hotel delayed_hours_only
        assert any(a["action_type"]=="MEAL_VOUCHER" for a in res["actions"])
        assert any(a["action_type"]=="HOTEL" for a in res["actions"])
        assert res["escalation"] is not None and res["escalation"]["reason"]=="fare_difference_exceeds_limit"
        # full-night should be blocked in trace
        assert any("full-night" in t or "delayed-hours only" in t for t in res["decision_trace"])

    def test_unknown_pnr(self, db):
        res = handle_chat(db, "XX9999", "hello")
        assert res["booking"] is None
        assert "couldn't find" in res["response"].lower()

    def test_ask_for_pnr(self, db):
        res = handle_chat(db, "", "my flight cancelled")
        assert res["ask_for_pnr"] is True

    def test_refund_alternate_escalate(self, db):
        def mock_alternate(*a, **kw):
            from app.agent.intent import IntentResult, IntentEntities
            return IntentResult(primary_intent="refund_request", sentiment="neutral", requested_exception=True, entities=IntentEntities(refund_method="alternate"))
        with patch("app.agent.orchestrator.extract_intent", side_effect=mock_alternate), \
             patch("app.agent.orchestrator.generate_response", return_value="escalated"):
            res = handle_chat(db, "SK4821X", "refund to another bank")
        assert res["escalation"] is not None and "refund" in res["escalation"]["reason"]

    def test_legal_threat_immediate_escalate(self, db):
        def mock_legal(*a, **kw):
            from app.agent.intent import IntentResult, IntentEntities
            return IntentResult(primary_intent="complaint", sentiment="legal_threat", requested_exception=True, entities=IntentEntities())
        with patch("app.agent.orchestrator.extract_intent", side_effect=mock_legal), \
             patch("app.agent.orchestrator.generate_response", return_value="escalated"):
            res = handle_chat(db, "WL7742", "I will sue you")
        assert res["escalation"] is not None and res["escalation"]["reason"]=="legal_threat"
        assert res["actions"] == []

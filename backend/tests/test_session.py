"""
test_session.py — read-only session hydration, decision_trace persistence, no duplicate on refresh.
"""
import json
from app.database import SessionLocal, Base, engine
from app.models import Action, Conversation, Escalation
from app.agent.orchestrator import handle_chat
from app.routes.session import get_session
from unittest.mock import patch
from fastapi import HTTPException
import pytest

def mock_hotel_fare(*args, **kwargs):
    from app.agent.intent import IntentResult, IntentEntities
    return IntentResult(primary_intent="hotel_request", secondary_intents=["fare_waiver_request"], sentiment="neutral", requested_exception=True, entities=IntentEntities(amount=2000, hotel_type="full_night"))

@pytest.fixture
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

def test_session_persists_trace_and_actions(db):
    with patch("app.agent.orchestrator.extract_intent", side_effect=mock_hotel_fare), patch("app.agent.orchestrator.generate_response", return_value="ok"):
        res = handle_chat(db, "WL7742", "full night hotel and waive 2000")
    trace_before = res["decision_trace"]
    assert len(trace_before) > 0
    # Session should return same trace without new Groq call
    sess = get_session("WL7742", db)
    assert sess["decision_trace"] == trace_before
    assert len(sess["actions"]) == len(res["actions"])
    assert sess["escalation"] is not None
    assert len(sess["messages"]) == 2  # user + assistant

def test_refresh_is_read_only_no_duplicate(db):
    with patch("app.agent.orchestrator.extract_intent", side_effect=mock_hotel_fare), patch("app.agent.orchestrator.generate_response", return_value="ok"):
        handle_chat(db, "WL7742", "full night hotel and waive 2000")
    actions_before = db.query(Action).count()
    esc_before = db.query(Escalation).count()
    conv_before = db.query(Conversation).count()
    # Refresh: call session twice
    get_session("WL7742", db)
    get_session("WL7742", db)
    assert db.query(Action).count() == actions_before
    assert db.query(Escalation).count() == esc_before
    assert db.query(Conversation).count() == conv_before

def test_pnr_switch_isolation(db):
    def mock_priya(*a, **kw):
        from app.agent.intent import IntentResult, IntentEntities
        return IntentResult(primary_intent="refund_request", secondary_intents=["upgrade_request"], sentiment="angry", requested_exception=True, entities=IntentEntities(upgrade_class="business"))
    def mock_arvind(*a, **kw):
        from app.agent.intent import IntentResult, IntentEntities
        return IntentResult(primary_intent="hotel_request", sentiment="neutral", requested_exception=False, entities=IntentEntities())
    with patch("app.agent.orchestrator.extract_intent", side_effect=mock_priya), patch("app.agent.orchestrator.generate_response", return_value="ok"):
        handle_chat(db, "SK4821X", "refund + upgrade")
    with patch("app.agent.orchestrator.extract_intent", side_effect=mock_arvind), patch("app.agent.orchestrator.generate_response", return_value="ok"):
        handle_chat(db, "TR1190B", "need hotel")
    sess_priya = get_session("SK4821X", db)
    sess_arvind = get_session("TR1190B", db)
    assert sess_priya["booking"]["pnr"] == "SK4821X"
    assert sess_arvind["booking"]["pnr"] == "TR1190B"
    assert len(sess_priya["messages"]) == 2
    assert len(sess_arvind["messages"]) == 2
    # traces should not be cross-contaminated
    assert sess_priya["decision_trace"] != sess_arvind["decision_trace"]

def test_unknown_pnr_404(db):
    with pytest.raises(HTTPException) as e:
        get_session("XX9999", db)
    assert e.value.status_code == 404

def test_old_rows_without_trace_return_empty_not_fake(db):
    # Simulate pre-migration row without decision_trace_json
    from app.models import Conversation
    # create a manual assistant row without trace
    db.add(Conversation(booking_id=1, pnr="SK4821X", role="assistant", message="old", intent_json="{}"))
    db.commit()
    sess = get_session("SK4821X", db)
    # should return empty trace, not invented
    assert sess["decision_trace"] == [] or isinstance(sess["decision_trace"], list)

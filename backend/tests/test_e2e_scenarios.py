"""
E2E — 3 mandatory scenarios via TestClient (real orchestrator + policy + tools + session).
"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Action, Escalation, Conversation

client = TestClient(app)

def clean():
    db = SessionLocal()
    db.query(Action).delete(); db.query(Escalation).delete(); db.query(Conversation).delete(); db.commit(); db.close()

def test_priya_cancellation_refund_and_upgrade_escalate():
    clean()
    r = client.post("/api/chat", json={"pnr":"SK4821X","message":"I am furious! I want full cash refund and free business upgrade for the trouble."})
    assert r.status_code==200
    j=r.json()
    # refund allowed
    assert any(a["action_type"]=="REFUND_INITIATED" for a in j["actions"])
    # upgrade escalated
    assert j["escalation"] is not None and "upgrade" in j["escalation"]["reason"]
    assert any("refund" in t.lower() for t in j["decision_trace"])
    # DB
    db=SessionLocal(); assert db.query(Action).filter(Action.action_type=="REFUND_INITIATED").count()==1; assert db.query(Escalation).filter(Escalation.reason=="upgrade_exception").count()==1; db.close()
    # session reflects same
    s=client.get("/api/session/SK4821X").json()
    assert len(s["messages"])==2 and len(s["decision_trace"])>0

def test_arvind_4h_meal_lounge_no_hotel():
    clean()
    r = client.post("/api/chat", json={"pnr":"TR1190B","message":"I'm frustrated because my 4 hour delay is making me miss an important meeting. I need a hotel."})
    assert r.status_code==200
    j=r.json()
    assert any(a["action_type"]=="MEAL_VOUCHER" for a in j["actions"])
    assert any(a["action_type"]=="LOUNGE_ACCESS" for a in j["actions"])
    assert not any(a["action_type"]=="HOTEL" for a in j["actions"])
    assert j["escalation"] is None
    assert any("hotel" in t.lower() and "not eligible" in t.lower() for t in j["decision_trace"])
    s=client.get("/api/session/TR1190B").json()
    assert len(s["actions"])>=2

def test_meher_6h_hotel_delayed_and_fare2000_escalate():
    clean()
    r = client.post("/api/chat", json={"pnr":"WL7742","message":"I want a full-night hotel and waive my 2000 fare difference"})
    assert r.status_code==200
    j=r.json()
    assert any(a["action_type"]=="MEAL_VOUCHER" for a in j["actions"])
    assert any(a["action_type"]=="LOUNGE_ACCESS" for a in j["actions"])
    assert any(a["action_type"]=="HOTEL" for a in j["actions"])
    # hotel is delayed-hours only
    hotel = [a for a in j["actions"] if a["action_type"]=="HOTEL"][0]
    assert hotel["metadata"]["coverage"]=="delayed_hours_only"
    assert j["escalation"] is not None and "fare_difference" in j["escalation"]["reason"]
    assert any("full-night" in t.lower() for t in j["decision_trace"])
    s=client.get("/api/session/WL7742").json()
    assert s["escalation"] is not None

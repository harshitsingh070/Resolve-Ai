"""
session.py — read-only aggregated hydration endpoint.
No tool execution, no Groq, no policy evaluation. Only reads persisted SQLite.
"""
import json
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.tools.customer_tools import get_customer
from app.tools.booking_tools import get_booking
from app.models import Conversation, Action, Escalation

router = APIRouter()

@router.get("/session/{pnr}")
def get_session(pnr: str, db: Session = Depends(get_db)):
    pnr_norm = (pnr or "").strip().upper()
    if not pnr_norm:
        raise HTTPException(status_code=400, detail="PNR required")

    # Try customer via pnr, else via booking owner (SK4821X-R case)
    customer = get_customer(db, pnr_norm)
    booking = get_booking(db, pnr_norm)
    if booking and not customer:
        from app.models import Customer
        customer = db.query(Customer).filter(Customer.id == booking.customer_id).first()
    if not booking or not customer:
        raise HTTPException(status_code=404, detail=f"Session not found for PNR '{pnr_norm}'")

    # Messages: all conversations ordered chronologically
    conv_rows = db.query(Conversation).filter(Conversation.booking_id == booking.id).order_by(Conversation.created_at).all()
    messages = []
    decision_trace = []
    for r in conv_rows:
        messages.append({
            "role": r.role,
            "message": r.message,
            "intent": json.loads(r.intent_json) if r.intent_json else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
        # trace is stored on assistant rows only; take latest non-empty
        if r.role == "assistant" and getattr(r, "decision_trace_json", None):
            try:
                parsed = json.loads(r.decision_trace_json)
                if isinstance(parsed, list) and len(parsed) > 0:
                    decision_trace = parsed  # keep latest
            except Exception:
                pass

    # Actions: all for this booking
    action_rows = db.query(Action).filter(Action.booking_id == booking.id).order_by(Action.created_at).all()
    actions = []
    for a in action_rows:
        actions.append({
            "id": a.id, "booking_id": a.booking_id, "pnr": a.pnr, "action_type": a.action_type,
            "status": a.status, "reason": a.reason,
            "metadata": json.loads(a.metadata_json) if a.metadata_json else {},
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    # Escalation: latest pending (or latest overall if none pending)
    esc = db.query(Escalation).filter(Escalation.booking_id == booking.id).order_by(Escalation.created_at.desc()).first()
    escalation = None
    if esc:
        escalation = {"id": esc.id, "booking_id": esc.booking_id, "pnr": esc.pnr, "reason": esc.reason, "requested_action": esc.requested_action, "status": esc.status, "created_at": esc.created_at.isoformat() if esc.created_at else None}

    # Also check if decision_trace was not yet persisted for older rows (pre-migration) — leave empty, do NOT regenerate via Groq/policy
    return {
        "customer": {"id": customer.id, "name": customer.name, "loyalty_tier": customer.loyalty_tier, "pnr": customer.pnr, "email": customer.email, "phone": customer.phone},
        "booking": {"id": booking.id, "customer_id": booking.customer_id, "pnr": booking.pnr, "flight_number": booking.flight_number, "route": booking.route, "travel_date": booking.travel_date, "scheduled_departure": booking.scheduled_departure, "status": booking.status, "delay_hours": booking.delay_hours, "new_departure": booking.new_departure, "reason": booking.reason},
        "messages": [{"role": m["role"], "message": m["message"]} for m in messages],
        "decision_trace": decision_trace,
        "actions": actions,
        "escalation": escalation,
    }

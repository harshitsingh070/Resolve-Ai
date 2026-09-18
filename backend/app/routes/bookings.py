from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.tools.booking_tools import get_booking, get_bookings_by_customer, get_action_history
from app.models import Conversation

router = APIRouter()

@router.get("/bookings/{pnr}")
def get_booking_api(pnr: str, include_return: bool = Query(False), db: Session = Depends(get_db)):
    b = get_booking(db, pnr)
    if not b:
        raise HTTPException(status_code=404, detail=f"Booking not found for PNR '{pnr}'.")
    if include_return:
        # return all bookings for this customer (Priya 2 bookings)
        bookings = get_bookings_by_customer(db, b.customer_id)
        return [{"id": x.id, "customer_id": x.customer_id, "pnr": x.pnr, "flight_number": x.flight_number, "route": x.route, "travel_date": x.travel_date, "scheduled_departure": x.scheduled_departure, "status": x.status, "delay_hours": x.delay_hours, "new_departure": x.new_departure, "reason": x.reason} for x in bookings]
    return {"id": b.id, "customer_id": b.customer_id, "pnr": b.pnr, "flight_number": b.flight_number, "route": b.route, "travel_date": b.travel_date, "scheduled_departure": b.scheduled_departure, "status": b.status, "delay_hours": b.delay_hours, "new_departure": b.new_departure, "reason": b.reason}

@router.get("/actions/{pnr}")
def get_actions_api(pnr: str, db: Session = Depends(get_db)):
    # if booking not found, 404 (per api-contract choice)
    b = get_booking(db, pnr)
    if not b:
        raise HTTPException(status_code=404, detail=f"Booking not found for PNR '{pnr}'.")
    hist = get_action_history(db, pnr)
    out = []
    for h in hist:
        import json
        out.append({"id": h.id, "booking_id": h.booking_id, "pnr": h.pnr, "action_type": h.action_type, "status": h.status, "reason": h.reason, "metadata": json.loads(h.metadata_json) if h.metadata_json else {}, "created_at": h.created_at.isoformat() if h.created_at else None})
    return out

@router.get("/conversations/{pnr}")
def get_conversations_api(pnr: str, db: Session = Depends(get_db)):
    b = get_booking(db, pnr)
    if not b:
        raise HTTPException(status_code=404, detail=f"Booking not found for PNR '{pnr}'.")
    rows = db.query(Conversation).filter(Conversation.booking_id == b.id).order_by(Conversation.created_at).all()
    import json
    out = []
    for r in rows:
        out.append({"id": r.id, "booking_id": r.booking_id, "pnr": r.pnr, "role": r.role, "message": r.message, "intent": json.loads(r.intent_json) if r.intent_json else None, "created_at": r.created_at.isoformat() if r.created_at else None})
    return out

"""
booking_tools.py — booking lookup + history helpers.
"""
from sqlalchemy.orm import Session
from app.models import Booking, Action


def _norm_pnr(pnr: str) -> str:
    return (pnr or "").strip().upper()


def get_booking(db: Session, pnr: str):
    """Fetch booking by PNR (case-insensitive). None if not found."""
    norm = _norm_pnr(pnr)
    if not norm:
        return None
    return db.query(Booking).filter(Booking.pnr == norm).first()


def get_bookings_by_customer(db: Session, customer_id: int):
    """All bookings for a customer (demonstrates 1—N, e.g., Priya has 2)."""
    return db.query(Booking).filter(Booking.customer_id == customer_id).order_by(Booking.travel_date).all()


def get_action_history(db: Session, pnr: str):
    """Action log for a PNR, oldest first. Returns [] if none or unknown PNR."""
    norm = _norm_pnr(pnr)
    if not norm:
        return []
    # Prefer booking_id lookup for correctness, fallback to pnr index
    booking = get_booking(db, norm)
    if booking:
        return db.query(Action).filter(Action.booking_id == booking.id).order_by(Action.created_at).all()
    return db.query(Action).filter(Action.pnr == norm).order_by(Action.created_at).all()

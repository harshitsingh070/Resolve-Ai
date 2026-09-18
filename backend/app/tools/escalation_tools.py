"""
escalation_tools.py — human/supervisor escalation.
Always allowed when needed. Creates pending escalation row.
"""
from sqlalchemy.orm import Session
from app.models import Escalation
from app.tools.booking_tools import get_booking


def escalate_to_human(db: Session, pnr: str, reason: str, requested_action: str) -> Escalation:
    """
    Create escalation. pnr is normalized; booking_id resolved from booking table.
    reason: machine key e.g., fare_difference_exceeds_limit, upgrade_exception, refund_payment_method, legal_threat
    requested_action: what customer wanted e.g., waive_2000, full_night_hotel, business_upgrade
    """
    booking = get_booking(db, pnr)
    if not booking:
        # Use pnr as provided for audit, with booking_id = 0 placeholder? Instead fail clearly.
        raise ValueError(f"Cannot escalate without booking for PNR '{pnr}'")
    esc = Escalation(
        booking_id=booking.id,
        pnr=booking.pnr,
        reason=reason,
        requested_action=requested_action,
        status="pending",
    )
    db.add(esc)
    db.commit()
    db.refresh(esc)
    return esc

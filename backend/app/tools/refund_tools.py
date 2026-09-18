"""
refund_tools.py — refund and rebooking with self-checks.
Refund: only for airline-caused cancellation (Cancelled + Operational reasons) to original method.
Rebook: only for airline-caused cancellation within 24h window (simulated, no inventory).
Both idempotent.
"""
import json
from sqlalchemy.orm import Session
from app.models import Action
from app.policies.policy_engine import evaluate_cancellation
from app.tools.booking_tools import get_booking


class AuthorizationError(Exception):
    pass


def _existing_action(db: Session, booking_id: int, action_type: str):
    return db.query(Action).filter(
        Action.booking_id == booking_id,
        Action.action_type == action_type,
        Action.status == "completed",
    ).first()


def initiate_refund(db: Session, pnr: str) -> Action:
    """
    Initiate full refund — checks cancellation policy.
    Refund is record-only (no payment gateway) with SLA 7 business days, original method.
    """
    booking = get_booking(db, pnr)
    if not booking:
        raise AuthorizationError(f"Booking not found for PNR '{pnr}'")
    policy = evaluate_cancellation(booking)
    if not policy.eligible_for_full_refund:
        raise AuthorizationError(
            f"Refund only for airline-caused cancellation (SR-01/SR-05). PNR {pnr} status={booking.status} reason={booking.reason}"
        )
    existing = _existing_action(db, booking.id, "REFUND_INITIATED")
    if existing:
        return existing
    action = Action(
        booking_id=booking.id,
        pnr=booking.pnr,
        action_type="REFUND_INITIATED",
        status="completed",
        reason="airline_cancellation",
        metadata_json=json.dumps({"sla": policy.refund_sla, "method": policy.refund_method}),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def rebook_next_available(db: Session, pnr: str) -> Action:
    """
    Rebook on next available flight within 24h — simulated (no inventory API).
    Only for airline-caused cancellation.
    """
    booking = get_booking(db, pnr)
    if not booking:
        raise AuthorizationError(f"Booking not found for PNR '{pnr}'")
    policy = evaluate_cancellation(booking)
    if not policy.eligible_for_free_rebooking:
        raise AuthorizationError(
            f"Free rebooking only for airline-caused cancellation (SR-01). PNR {pnr} status={booking.status}"
        )
    existing = _existing_action(db, booking.id, "REBOOKED")
    if existing:
        return existing
    action = Action(
        booking_id=booking.id,
        pnr=booking.pnr,
        action_type="REBOOKED",
        status="completed",
        reason="airline_cancellation",
        metadata_json=json.dumps({"window_hours": policy.rebooking_window_hours, "note": "simulated — no inventory API"}),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action

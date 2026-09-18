"""
compensation_tools.py — meal voucher, lounge, hotel with self-checks.
Each write tool verifies policy via policy_engine BEFORE inserting.
Idempotent: second call returns existing completed action, no duplicate.
"""
import json
from sqlalchemy.orm import Session
from app.models import Booking, Action
from app.policies.policy_engine import evaluate_delay
from app.tools.booking_tools import get_booking


class AuthorizationError(Exception):
    """Raised when tool is called outside its policy authority."""
    pass


def _existing_action(db: Session, booking_id: int, action_type: str):
    return db.query(Action).filter(
        Action.booking_id == booking_id,
        Action.action_type == action_type,
        Action.status == "completed",
    ).first()


def issue_meal_voucher(db: Session, pnr: str) -> Action:
    """Issue Rs 500 meal voucher — only if delay >3h. Idempotent."""
    booking = get_booking(db, pnr)
    if not booking:
        raise AuthorizationError(f"Booking not found for PNR '{pnr}'")
    policy = evaluate_delay(booking.delay_hours)
    if not policy.meal_voucher:
        raise AuthorizationError(
            f"Meal voucher requires delay over 3h (SR-03). PNR {pnr} has delay={booking.delay_hours}, not eligible."
        )
    existing = _existing_action(db, booking.id, "MEAL_VOUCHER")
    if existing:
        return existing
    action = Action(
        booking_id=booking.id,
        pnr=booking.pnr,
        action_type="MEAL_VOUCHER",
        status="completed",
        reason="delay_over_3h",
        metadata_json=json.dumps({"amount": policy.meal_voucher_amount}),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def grant_lounge_access(db: Session, pnr: str) -> Action:
    """Grant lounge access — only if delay >3h. Idempotent."""
    booking = get_booking(db, pnr)
    if not booking:
        raise AuthorizationError(f"Booking not found for PNR '{pnr}'")
    policy = evaluate_delay(booking.delay_hours)
    if not policy.lounge_access:
        raise AuthorizationError(
            f"Lounge requires delay over 3h (SR-03). PNR {pnr} has delay={booking.delay_hours}."
        )
    existing = _existing_action(db, booking.id, "LOUNGE_ACCESS")
    if existing:
        return existing
    action = Action(
        booking_id=booking.id,
        pnr=booking.pnr,
        action_type="LOUNGE_ACCESS",
        status="completed",
        reason="delay_over_3h",
        metadata_json=json.dumps({}),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def create_hotel_request(db: Session, pnr: str) -> Action:
    """
    Create hotel request for delayed-hours only — only if delay >5h.
    Coverage is always delayed_hours_only per SR-04 (full-night never created).
    Idempotent.
    """
    booking = get_booking(db, pnr)
    if not booking:
        raise AuthorizationError(f"Booking not found for PNR '{pnr}'")
    policy = evaluate_delay(booking.delay_hours)
    if not policy.hotel:
        raise AuthorizationError(
            f"Hotel requires delay over 5h (SR-04). PNR {pnr} has delay={booking.delay_hours}, not eligible."
        )
    existing = _existing_action(db, booking.id, "HOTEL")
    if existing:
        return existing
    action = Action(
        booking_id=booking.id,
        pnr=booking.pnr,
        action_type="HOTEL",
        status="completed",
        reason="delay_over_5h",
        metadata_json=json.dumps({"coverage": policy.hotel_coverage}),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


# Read-only helpers for orchestrator (no DB write)

def evaluate_delay_compensation(db: Session, pnr: str):
    """Read-only wrapper — returns DelayResult without writing."""
    booking = get_booking(db, pnr)
    if not booking:
        return None
    return evaluate_delay(booking.delay_hours)

"""
policy_engine.py — this is where all airline rules live.

I kept it plain Python on purpose. No Groq, no database, no magic.
That way we can test every rule with pytest alone, and an interviewer
can open this one file and see exactly how decisions are made.

Think of it as the rulebook the agent must follow — the LLM never
gets to bend these. If a customer asks for something outside these
rules, the engine will say no, and later code decides whether to
escalate or just explain.
"""
from typing import Literal, Optional
from pydantic import BaseModel


# These models are what the API shows in the decision trace.
# They are simple, typed, and easy to read in the UI.

class DelayResult(BaseModel):
    meal_voucher: bool
    meal_voucher_amount: Optional[int] = None  # 500 if meal_voucher
    lounge_access: bool
    hotel: bool
    hotel_coverage: Optional[Literal["delayed_hours_only"]] = None
    # True only when delay_hours == 3.0 — source has no rule for exactly 3h (explicitly unspecified)
    unspecified: bool = False
    unspecified_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump()


class CancellationResult(BaseModel):
    eligible_for_free_rebooking: bool
    rebooking_window_hours: Optional[int] = None  # 24 if eligible
    eligible_for_full_refund: bool
    refund_sla: Optional[str] = None  # "7 business days" if eligible
    refund_method: Optional[str] = None  # "original_payment_method_only" if eligible

    def to_dict(self) -> dict:
        return self.model_dump()


class FareResult(BaseModel):
    fare_difference: float
    agent_limit: int = 1500
    agent_can_waive: bool
    requires_supervisor: bool

    def to_dict(self) -> dict:
        return self.model_dump()


# Authorization is different from policy. Policy says what is possible;
# authorization says whether this agent is allowed to do what the customer asked.

class AuthorizationResult(BaseModel):
    allowed: bool
    reason: str  # machine key e.g., "hotel_coverage_mismatch"
    detail: str  # human sentence for decision_trace
    escalation: bool = False
    escalation_reason: Optional[str] = None


# --- The actual rules ---

def evaluate_delay(delay_hours: Optional[float]) -> DelayResult:
    """
    Authoritative Data Pack (corrected):
      delay < 3h  → meal voucher Rs 500 only (no lounge, no hotel)
      delay == 3h → UNSPECIFIED — source provides no rule, do not invent
      delay > 3h and <=5h → meal voucher Rs 500 + lounge access
      delay > 5h → meal voucher Rs 500 + lounge + hotel (delayed-hours only)

    Boundaries are strict per pack examples:
      2h, 2.99h → meal only
      3h → unspecified (no entitlement invented)
      3.01h, 4h → meal + lounge
      5h → meal + lounge (no hotel)
      5.01h, 6h → meal + lounge + hotel delayed-hours-only
    None covers Cancelled/Unaffected (no delay).
    """
    if delay_hours is None:
        return DelayResult(meal_voucher=False, meal_voucher_amount=None, lounge_access=False, hotel=False, hotel_coverage=None, unspecified=False)
    try:
        h = float(delay_hours)
    except Exception:
        return DelayResult(meal_voucher=False, meal_voucher_amount=None, lounge_access=False, hotel=False, hotel_coverage=None, unspecified=False)
    if h < 0:
        h = 0

    # Exactly 3.0 is explicitly unspecified — do not invent entitlement
    if abs(h - 3.0) < 1e-9:
        return DelayResult(
            meal_voucher=False, meal_voucher_amount=None, lounge_access=False, hotel=False, hotel_coverage=None,
            unspecified=True, unspecified_reason="Source Data Pack provides no rule for exactly 3h",
        )

    if h > 5:
        return DelayResult(meal_voucher=True, meal_voucher_amount=500, lounge_access=True, hotel=True, hotel_coverage="delayed_hours_only", unspecified=False)
    if h > 3:
        return DelayResult(meal_voucher=True, meal_voucher_amount=500, lounge_access=True, hotel=False, hotel_coverage=None, unspecified=False)
    if h < 3:
        # covers 2h, 2.99h etc. — meal only per corrected pack
        return DelayResult(meal_voucher=True, meal_voucher_amount=500, lounge_access=False, hotel=False, hotel_coverage=None, unspecified=False)
    # fallback (should not reach due to 3.0 case above)
    return DelayResult(meal_voucher=False, meal_voucher_amount=None, lounge_access=False, hotel=False, hotel_coverage=None, unspecified=False)


def evaluate_cancellation(booking) -> CancellationResult:
    """
    Cancellations are only special when the airline caused them.
    In our data that is shown as status Cancelled with reason
    Operational reasons - like Priya's flight. Then the customer
    can pick either a free rebooking within a day or a full refund
    that goes back to how they paid, within 7 business days.

    Anything else is not considered airline-caused here, so no
    special rebooking or refund.
    This helper accepts both real DB objects and plain dicts,
    so tests don't need a database at all.
    """
    # Extract status/reason defensively
    if isinstance(booking, dict):
        status = booking.get("status")
        reason = booking.get("reason")
    else:
        status = getattr(booking, "status", None)
        reason = getattr(booking, "reason", None)

    is_airline_cancelled = (status == "Cancelled" and reason == "Operational reasons")
    if is_airline_cancelled:
        return CancellationResult(
            eligible_for_free_rebooking=True,
            rebooking_window_hours=24,
            eligible_for_full_refund=True,
            refund_sla="7 business days",
            refund_method="original_payment_method_only",
        )
    return CancellationResult(
        eligible_for_free_rebooking=False,
        rebooking_window_hours=None,
        eligible_for_full_refund=False,
        refund_sla=None,
        refund_method=None,
    )


def evaluate_fare_difference(amount) -> FareResult:
    """
    This one is about who can waive money. Our agent can only waive
    up to Rs 1,500 on its own. Anything higher, like Meher's Rs 2,000,
    has to go to a supervisor. That limit is fixed and we don't try
    to interpret it further - see assumptions for why.

    Boundary is inclusive: 1500 is allowed, 1500.01 is not.
    Accepts int or float (e.g., 1500.01 test case).
    """
    try:
        amt = float(amount)
    except Exception:
        raise ValueError(f"fare_difference amount must be numeric, got {amount!r}")
    if amt < 0:
        amt = 0
    # Preserve int when possible for cleaner JSON, but keep float precision for 1500.01
    fare_val = int(amt) if amt.is_integer() else amt
    return FareResult(
        fare_difference=fare_val,
        agent_limit=1500,
        agent_can_waive=amt <= 1500,
        requires_supervisor=amt > 1500,
    )


# These small helpers turn a policy result into a yes/no for the agent.
# They keep the decision explainable and give a nice sentence for the UI.

def authorize_hotel(requested_coverage: Optional[str], delay_hours: Optional[float]) -> AuthorizationResult:
    """
    Hotel check is where people expect the most. We only give hotel
    when the delay is truly over 5 hours, and even then only for
    the delayed time - not a free night. So if someone asks for a
    full night, we have to say no and explain why in plain words.
    """
    policy = evaluate_delay(delay_hours)
    if not policy.hotel:
        # Not even eligible for delayed-hours hotel
        needed = "over 5 hours"
        actual = f"{delay_hours}h" if delay_hours is not None else "Cancelled/Unaffected"
        return AuthorizationResult(
            allowed=False,
            reason="hotel_not_eligible",
            detail=f"Hotel requires delay over 5h (SR-04). Your delay is {actual}, so hotel not eligible.",
            escalation=False,
        )
    # Policy allows delayed_hours_only
    if requested_coverage == "full_night":
        return AuthorizationResult(
            allowed=False,
            reason="hotel_coverage_mismatch",
            detail="Policy covers hotel for delayed-hours only (SR-04), not a full night's stay.",
            escalation=False,  # blocked with explanation; escalation only if insisting on exception (handled by orchestrator)
        )
    return AuthorizationResult(
        allowed=True,
        reason="hotel_delayed_hours_eligible",
        detail="Hotel covering delayed-hours portion is eligible (SR-04).",
        escalation=False,
    )


def authorize_fare_waiver(amount: int) -> AuthorizationResult:
    policy = evaluate_fare_difference(amount)
    if policy.requires_supervisor:
        return AuthorizationResult(
            allowed=False,
            reason="exceeds_agent_limit",
            detail=f"Fare difference ₹{policy.fare_difference} exceeds agent authority of ₹{policy.agent_limit} (SR-06) → requires supervisor.",
            escalation=True,
            escalation_reason="fare_difference_exceeds_limit",
        )
    return AuthorizationResult(
        allowed=True,
        reason="within_agent_limit",
        detail=f"Fare difference ₹{policy.fare_difference} is within agent limit of ₹{policy.agent_limit} (SR-06).",
        escalation=False,
    )


def authorize_refund(booking, requested_method: Optional[str] = None) -> AuthorizationResult:
    """
    Refund authorization.
    requested_method: "original" | "alternate" | None
    """
    policy = evaluate_cancellation(booking)
    if not policy.eligible_for_full_refund:
        return AuthorizationResult(
            allowed=False,
            reason="not_airline_cancelled",
            detail="Refund only for airline-caused cancellation (SR-01/SR-05).",
            escalation=False,
        )
    if requested_method == "alternate":
        return AuthorizationResult(
            allowed=False,
            reason="refund_payment_method",
            detail="Refunds are issued to original payment method only (SR-05) → escalation required.",
            escalation=True,
            escalation_reason="refund_payment_method",
        )
    return AuthorizationResult(
        allowed=True,
        reason="refund_eligible",
        detail="Full refund eligible: 7 business days to original payment method (SR-05).",
        escalation=False,
    )


def authorize_upgrade() -> AuthorizationResult:
    """There is simply no rule that gives a free business upgrade for
    a cancellation. Gold or Platinum only means priority rebooking.
    So we always say no here and let the orchestrator decide if this
    needs to be escalated when the customer keeps asking."""
    return AuthorizationResult(
        allowed=False,
        reason="no_upgrade_policy",
        detail="No policy provides complimentary business-class upgrade. Gold/Platinum gives priority rebooking only (SR-07).",
        escalation=False,  # if insists, orchestrator escalates as upgrade_exception
    )

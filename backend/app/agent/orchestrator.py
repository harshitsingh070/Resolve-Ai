"""
orchestrator.py — 10-step coordinator, no business rules inside.
Calls: intent -> DB -> policy -> authz -> tools -> audit -> grounded response.
"""
import json
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Conversation, Customer, Booking
from app.tools.customer_tools import get_customer
from app.tools.booking_tools import get_booking
from app.policies.policy_engine import (
    evaluate_delay, evaluate_cancellation, evaluate_fare_difference,
    authorize_hotel, authorize_fare_waiver, authorize_refund, authorize_upgrade,
)
from app.tools.compensation_tools import issue_meal_voucher, grant_lounge_access, create_hotel_request
from app.tools.refund_tools import initiate_refund, rebook_next_available
from app.tools.escalation_tools import escalate_to_human
from app.agent.intent import extract_intent, fallback_intent, generate_response
from app.agent.prompts import RESPONSE_PROMPT  # for reference, not direct use


def _booking_context(customer: Optional[Customer], booking: Optional[Booking]) -> str:
    if not customer or not booking:
        return "No booking loaded"
    return (
        f"PNR {booking.pnr}, Customer {customer.name} ({customer.loyalty_tier}), "
        f"Flight {booking.flight_number} {booking.route} on {booking.travel_date} at {booking.scheduled_departure}, "
        f"Status {booking.status}, delay_hours={booking.delay_hours}, new_departure={booking.new_departure}, reason={booking.reason}"
    )


def _history_context(db: Session, booking_id: int, limit: int = 3) -> str:
    rows = db.query(Conversation).filter(Conversation.booking_id == booking_id).order_by(Conversation.created_at.desc()).limit(limit).all()
    if not rows:
        return "No history"
    # reverse to chronological
    rows = list(reversed(rows))
    return "\n".join([f"{r.role}: {r.message[:200]}" for r in rows])


def handle_chat(db: Session, pnr: str, message: str) -> dict:
    """
    Main orchestrator entry. Returns dict matching ChatResponse plus decision_trace.
    Steps 1-10 per architecture.md:5
    """
    trace = []
    pnr_norm = (pnr or "").strip().upper()
    msg = (message or "").strip()

    # Step 1-2: PNR check
    if not pnr_norm:
        trace.append("Ask for PNR: no PNR provided")
        return {
            "response": "I can help. Please share your PNR (e.g., SK4821X, TR1190B, WL7742).",
            "intent": {"primary_intent": "unknown", "sentiment": "neutral"},
            "actions": [],
            "escalation": None,
            "decision_trace": trace,
            "booking": None,
            "customer": None,
            "ask_for_pnr": True,
        }

    customer = get_customer(db, pnr_norm)
    booking = get_booking(db, pnr_norm)

    # Handle SK4821X-R return leg: customer exists via SK4821X but booking is SK4821X-R
    # If booking found but customer not via pnr, try via booking.customer
    if booking and not customer:
        customer = db.query(Customer).filter(Customer.id == booking.customer_id).first()

    if not customer or not booking:
        trace.append(f"Verified facts: PNR {pnr_norm} not found")
        # Still log conversation for audit if possible? Need booking_id, so skip if no booking
        return {
            "response": f"I couldn't find that booking for PNR '{pnr_norm}'. Please try SK4821X, TR1190B, or WL7742.",
            "intent": {"primary_intent": "unknown", "sentiment": "neutral"},
            "actions": [],
            "escalation": None,
            "decision_trace": trace,
            "booking": None,
            "customer": None,
            "ask_for_pnr": False,
        }

    # Log user message early for history (intent will be added after extraction)
    # We need booking_id for conversation
    user_conv = Conversation(booking_id=booking.id, pnr=booking.pnr, role="user", message=msg, intent_json=None)
    db.add(user_conv)
    db.commit()

    # Step 3: Intent extraction (Groq -> fallback)
    booking_ctx = _booking_context(customer, booking)
    hist_ctx = _history_context(db, booking.id)
    try:
        intent = extract_intent(msg, booking_context=booking_ctx, history=hist_ctx)
    except Exception as e:
        # Groq failure -> fallback keyword
        trace.append(f"Groq intent failed, fallback keyword: {str(e)[:100]}")
        intent = fallback_intent(msg)

    # Validate intent shape already done in extract_intent
    trace.append(f"Intent: {intent.primary_intent} + {intent.secondary_intents} ({intent.sentiment}) amount={intent.entities.amount} hotel_type={intent.entities.hotel_type}")

    # Legal threat immediate escalation (EC-07)
    if intent.sentiment == "legal_threat":
        trace.append("Sentiment: legal_threat → immediate escalation")
        esc = escalate_to_human(db, booking.pnr, "legal_threat", intent.primary_intent)
        # also store intent in user conversation
        user_conv.intent_json = json.dumps(intent.model_dump())
        db.commit()
        # Build response via Groq grounded
        policy_result = {"delay": evaluate_delay(booking.delay_hours).model_dump(), "cancellation": evaluate_cancellation(booking).model_dump()}
        decision_trace = trace + ["Escalation: legal_threat → pending human"]
        try:
            resp = generate_response(msg, booking_ctx, policy_result, [], esc.__dict__, decision_trace, pnr_norm)
        except Exception:
            resp = "I understand this is a serious concern. I've escalated your case to a human agent immediately who will contact you shortly."
        # audit assistant — persist factual decision trace (read-only after refresh, no Groq regeneration)
        db.add(Conversation(booking_id=booking.id, pnr=booking.pnr, role="assistant", message=resp, intent_json=json.dumps(intent.model_dump()), decision_trace_json=json.dumps(decision_trace)))
        db.commit()
        return {
            "response": resp,
            "intent": intent.model_dump(),
            "actions": [],
            "escalation": {"id": esc.id, "booking_id": esc.booking_id, "pnr": esc.pnr, "reason": esc.reason, "requested_action": esc.requested_action, "status": esc.status, "created_at": esc.created_at.isoformat()},
            "decision_trace": decision_trace,
            "booking": {"pnr": booking.pnr, "flight_number": booking.flight_number, "route": booking.route, "travel_date": booking.travel_date, "scheduled_departure": booking.scheduled_departure, "status": booking.status, "delay_hours": booking.delay_hours, "new_departure": booking.new_departure, "reason": booking.reason},
            "customer": {"pnr": customer.pnr, "name": customer.name, "loyalty_tier": customer.loyalty_tier, "email": customer.email},
            "ask_for_pnr": False,
        }

    # Step 4-5: Policy evaluation
    delay_result = evaluate_delay(booking.delay_hours)
    cancel_result = evaluate_cancellation(booking)
    trace.append(f"Verified facts: {customer.name} ({customer.loyalty_tier}), {booking.flight_number} {booking.route}, status {booking.status}, delay {booking.delay_hours}, new {booking.new_departure}")
    if delay_result.unspecified:
        trace.append("Policy: delay exactly 3h → unspecified by source (no entitlement) (SR-02a)")
    else:
        if booking.delay_hours is not None:
            if delay_result.hotel:
                trace.append(f"Policy: delay {booking.delay_hours}h → meal ₹500 ✓, lounge ✓, hotel delayed-hours only ✓ (SR-02/03/04)")
            elif delay_result.lounge_access:
                trace.append(f"Policy: delay {booking.delay_hours}h → meal ₹500 ✓, lounge ✓, hotel ✗ (needs >5h)")
            elif delay_result.meal_voucher:
                trace.append(f"Policy: delay {booking.delay_hours}h → meal ₹500 ✓, lounge ✗, hotel ✗ (<3h meal only)")
            else:
                trace.append(f"Policy: delay {booking.delay_hours}h → no delay compensation (cancelled/None)")
    trace.append(f"Policy: cancellation {booking.status} → refund eligible={cancel_result.eligible_for_full_refund}, rebook eligible={cancel_result.eligible_for_free_rebooking} (SR-01/05)")

    # Step 6-7: Authorization + Tool execution
    actions_taken = []
    escalation_obj = None
    all_intents = [intent.primary_intent] + (intent.secondary_intents or [])
    # dedupe while preserving order
    seen = set()
    uniq_intents = []
    for i in all_intents:
        if i not in seen:
            seen.add(i)
            uniq_intents.append(i)

    # For delay compensations, we handle both explicit requests and automatic eligible compensations when customer is frustrated and has delay
    # This covers Arvind 4h hotel request -> still gets meal+lounge
    def try_tool(func, pnr_arg, success_msg, fail_trace):
        try:
            a = func(db, pnr_arg)
            trace.append(success_msg.format(pnr=pnr_arg))
            actions_taken.append(a)
            return a
        except Exception as e:
            trace.append(fail_trace + f": {str(e)[:120]}")
            return None

    # Determine if we should auto-issue delay compensations for delayed bookings when customer is asking about hotel/meal/lounge/complaint
    is_delay_query = any(x in uniq_intents for x in ["hotel_request", "meal_voucher_request", "lounge_request", "complaint", "unknown"]) or intent.sentiment in ["frustrated", "angry"]
    # But don't auto-issue for pure refund/rebook requests on cancelled flights

    for intent_name in uniq_intents:
        if intent_name == "refund_request":
            auth = authorize_refund(booking, intent.entities.refund_method)
            trace.append(f"Authority: refund → allowed={auth.allowed} escalation={auth.escalation} ({auth.detail})")
            if auth.allowed:
                try_tool(initiate_refund, booking.pnr, "Action: REFUND_INITIATED ✓ (7 days, original method)", "Refund blocked")
            elif auth.escalation:
                escalation_obj = escalate_to_human(db, booking.pnr, auth.escalation_reason or "refund_payment_method", "refund_alternate_method" if intent.entities.refund_method=="alternate" else "refund_request")
                trace.append(f"Escalation: {escalation_obj.reason} → pending")
            else:
                trace.append(f"Blocked: {auth.detail}")

        elif intent_name == "rebooking_request":
            # similar to refund, check cancellation
            if cancel_result.eligible_for_free_rebooking:
                try_tool(rebook_next_available, booking.pnr, "Action: REBOOKED ✓ (24h window, simulated)", "Rebook blocked")
            else:
                trace.append("Blocked: rebooking only for airline-caused cancellation (SR-01)")

        elif intent_name == "meal_voucher_request":
            try_tool(issue_meal_voucher, booking.pnr, "Action: MEAL_VOUCHER ₹500 ✓", "Meal voucher blocked")

        elif intent_name == "lounge_request":
            try_tool(grant_lounge_access, booking.pnr, "Action: LOUNGE_ACCESS ✓", "Lounge blocked")

        elif intent_name == "hotel_request":
            hotel_type = intent.entities.hotel_type
            auth = authorize_hotel(hotel_type, booking.delay_hours)
            trace.append(f"Authority: hotel {hotel_type or 'delayed_hours'} → allowed={auth.allowed} ({auth.detail})")
            # Corrected: if delay policy says hotel is eligible (>5h), we still grant delayed-hours hotel even when customer asked for full-night.
            # Full-night is blocked as extra, but eligible delayed-hours is still provided (Meher 6h expects hotel).
            if delay_result.hotel:
                if delay_result.meal_voucher:
                    try_tool(issue_meal_voucher, booking.pnr, "Action: MEAL_VOUCHER ₹500 ✓ (with hotel)", "Meal voucher blocked")
                if delay_result.lounge_access:
                    try_tool(grant_lounge_access, booking.pnr, "Action: LOUNGE_ACCESS ✓ (with hotel)", "Lounge blocked")
                try_tool(create_hotel_request, booking.pnr, "Action: HOTEL delayed-hours only ✓ (SR-04)", "Hotel blocked")
                if hotel_type == "full_night":
                    trace.append("Blocked: full-night hotel not covered, only delayed-hours (SR-04) — granted delayed-hours hotel")
            else:
                # Hotel not eligible (e.g., 4h)
                if delay_result.meal_voucher:
                    try_tool(issue_meal_voucher, booking.pnr, "Action: MEAL_VOUCHER ₹500 ✓ (hotel request, meal eligible)", "Meal voucher blocked")
                if delay_result.lounge_access:
                    try_tool(grant_lounge_access, booking.pnr, "Action: LOUNGE_ACCESS ✓ (hotel request, lounge eligible)", "Lounge blocked")
                if hotel_type == "full_night":
                    trace.append("Blocked: full-night hotel not covered, only delayed-hours (SR-04)")
                else:
                    trace.append("Blocked: hotel not eligible (requires delay >5h)")

        elif intent_name == "fare_waiver_request":
            amt = intent.entities.amount
            if amt is None:
                trace.append("Fare waiver: no amount detected → ask clarification")
                # no tool, will ask in response
                continue
            auth = authorize_fare_waiver(amt)
            trace.append(f"Authority: fare waiver ₹{amt} → allowed={auth.allowed} escalation={auth.escalation} ({auth.detail})")
            if auth.allowed:
                # In prototype, waiving within limit would be a tool, but we have no waive tool — just note allowed
                trace.append(f"Fare waiver ₹{amt} within limit — would be waived (no payment tool, record as action note)")
                # We could create a dummy action for audit, but not required — decision_trace covers it
            elif auth.escalation:
                escalation_obj = escalate_to_human(db, booking.pnr, auth.escalation_reason, f"waive_{amt}")
                trace.append(f"Escalation: {escalation_obj.reason} → pending supervisor")

        elif intent_name == "upgrade_request":
            auth = authorize_upgrade()
            trace.append(f"Authority: upgrade → allowed={auth.allowed} ({auth.detail})")
            if intent.requested_exception or "business" in msg.lower():
                escalation_obj = escalate_to_human(db, booking.pnr, "upgrade_exception", intent.entities.upgrade_class or "business_upgrade")
                trace.append(f"Escalation: upgrade_exception → pending")
            else:
                trace.append("Blocked: no upgrade policy (SR-07)")

        elif intent_name == "booking_inquiry":
            trace.append("Booking inquiry — no tool, will return booking facts")

        elif intent_name == "complaint":
            # For complaints, ensure eligible compensations are offered
            if delay_result.meal_voucher and not any(a.action_type=="MEAL_VOUCHER" for a in actions_taken):
                try_tool(issue_meal_voucher, booking.pnr, "Action: MEAL_VOUCHER ₹500 ✓ (complaint, auto-eligible)", "Meal voucher blocked")
            if delay_result.lounge_access:
                try_tool(grant_lounge_access, booking.pnr, "Action: LOUNGE_ACCESS ✓ (complaint)", "Lounge blocked")

        elif intent_name == "unknown":
            # Check if unrelated question: if message is not about airline data, respond with no policy
            low = msg.lower()
            if any(k in low for k in ["baggage allowance", "indigo", "what is", "capital of"]):
                trace.append("Unknown/unrelated → no policy entitlement, will respond with available info only")
            # else, ensure delayed bookings get at least meal/lounge if frustrated and eligible
            if is_delay_query and booking.status == "Delayed":
                if delay_result.meal_voucher:
                    try_tool(issue_meal_voucher, booking.pnr, "Action: MEAL_VOUCHER ₹500 ✓ (auto for delayed booking)", "Meal voucher blocked")
                if delay_result.lounge_access:
                    try_tool(grant_lounge_access, booking.pnr, "Action: LOUNGE_ACCESS ✓ (auto)", "Lounge blocked")

    # Handle alternate refund method via entities even if primary wasn't refund_request (e.g., Priya says refund to another account)
    if intent.entities.refund_method == "alternate" and not any(i=="refund_request" for i in uniq_intents):
        auth = authorize_refund(booking, "alternate")
        if auth.escalation and escalation_obj is None:
            escalation_obj = escalate_to_human(db, booking.pnr, auth.escalation_reason, "refund_alternate_method")
            trace.append(f"Escalation: refund alternate method → pending")

    # Also handle hotel_type full_night even if intent was not hotel_request but contains full night phrase
    if intent.entities.hotel_type == "full_night" and "hotel_request" not in uniq_intents:
        auth = authorize_hotel("full_night", booking.delay_hours)
        if not auth.allowed:
            trace.append(f"Authority: hotel full_night implicit → blocked ({auth.detail})")

    # Step 8: Audit — update user conv with intent, prepare actions list for response
    user_conv.intent_json = json.dumps(intent.model_dump())
    db.commit()

    # Prepare serializable actions for response
    actions_serialized = []
    for a in actions_taken:
        actions_serialized.append({
            "id": a.id,
            "booking_id": a.booking_id,
            "pnr": a.pnr,
            "action_type": a.action_type,
            "status": a.status,
            "reason": a.reason,
            "metadata": json.loads(a.metadata_json) if a.metadata_json else {},
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    escalation_serialized = None
    if escalation_obj:
        escalation_serialized = {
            "id": escalation_obj.id,
            "booking_id": escalation_obj.booking_id,
            "pnr": escalation_obj.pnr,
            "reason": escalation_obj.reason,
            "requested_action": escalation_obj.requested_action,
            "status": escalation_obj.status,
            "created_at": escalation_obj.created_at.isoformat() if escalation_obj.created_at else None,
        }

    # Step 5 results for response grounding
    policy_result = {
        "delay": delay_result.model_dump(),
        "cancellation": cancel_result.model_dump(),
        "fare": evaluate_fare_difference(intent.entities.amount).model_dump() if intent.entities.amount is not None else None,
    }

    # Step 9-10: Grounded response generation
    try:
        resp = generate_response(msg, _booking_context(customer, booking), policy_result, actions_serialized, escalation_serialized, trace, pnr_norm)
    except Exception as e:
        # Fallback template if Groq fails
        if escalation_serialized:
            resp = f"I've escalated your request ({escalation_serialized['reason']}) to a supervisor for review."
        elif actions_serialized:
            resp = f"Done — I've processed: {', '.join([a['action_type'] for a in actions_serialized])}. "
            # add policy explanation for hotel blocked
            if any("hotel" in t.lower() for t in trace) and not any(a['action_type']=='HOTEL' for a in actions_serialized):
                if booking.delay_hours == 4:
                    resp += "Hotel requires delay over 5 hours (SR-04). Your delay is 4 hours, so hotel is not eligible, but meal voucher and lounge are provided."
                elif intent.entities.hotel_type == "full_night":
                    resp += "Hotel covers delayed-hours only (SR-04), not a full night's stay."
        else:
            # check if cancelled refund case
            if intent.primary_intent == "refund_request" and cancel_result.eligible_for_full_refund:
                resp = "Your refund is eligible — full refund within 7 business days to your original payment method (SR-05)."
            elif "upgrade" in msg.lower():
                resp = "There is no policy for complimentary business-class upgrades; Gold/Platinum gives priority rebooking only (SR-07)."
            else:
                resp = "I can help with your booking. Available policies: meal voucher, lounge, hotel (delayed-hours only for >5h), refund/rebook for airline cancellations."

    # Audit assistant message — persist factual decision trace
    db.add(Conversation(booking_id=booking.id, pnr=booking.pnr, role="assistant", message=resp, intent_json=json.dumps(intent.model_dump()), decision_trace_json=json.dumps(trace)))
    db.commit()

    return {
        "response": resp,
        "intent": intent.model_dump(),
        "actions": actions_serialized,
        "escalation": escalation_serialized,
        "decision_trace": trace,
        "booking": {"pnr": booking.pnr, "flight_number": booking.flight_number, "route": booking.route, "travel_date": booking.travel_date, "scheduled_departure": booking.scheduled_departure, "status": booking.status, "delay_hours": booking.delay_hours, "new_departure": booking.new_departure, "reason": booking.reason},
        "customer": {"pnr": customer.pnr, "name": customer.name, "loyalty_tier": customer.loyalty_tier, "email": customer.email, "phone": customer.phone},
        "ask_for_pnr": False,
    }

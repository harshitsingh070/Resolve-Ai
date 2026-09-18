"""
These are plain rule checks. No database, no AI needed.
We just call the engine with different inputs and see if it
does what the assignment says. Run with pytest -v in backend.
"""
import pytest
from app.policies.policy_engine import (
    evaluate_delay,
    evaluate_cancellation,
    evaluate_fare_difference,
    authorize_hotel,
    authorize_fare_waiver,
    authorize_refund,
    authorize_upgrade,
)


# Delay cases - we are strict, 3 hours is not enough, 5 is not enough for hotel

class TestDelay:
    def test_cancelled_or_none_no_comp(self):
        r = evaluate_delay(None)
        assert r.meal_voucher is False and r.lounge_access is False and r.hotel is False
        assert r.meal_voucher_amount is None and r.hotel_coverage is None

    def test_delay_2h_no_comp(self):
        r = evaluate_delay(2)
        assert r.meal_voucher is False and r.lounge_access is False and r.hotel is False

    def test_delay_3h_exact_no_comp(self):
        # boundary: needs OVER 3h
        r = evaluate_delay(3)
        assert r.meal_voucher is False
        r2 = evaluate_delay(3.0)
        assert r2.meal_voucher is False

    def test_delay_3_1h_meal_lounge_no_hotel(self):
        r = evaluate_delay(3.01)
        assert r.meal_voucher is True and r.meal_voucher_amount == 500
        assert r.lounge_access is True and r.hotel is False
        assert r.hotel_coverage is None

    def test_delay_4h_meal_lounge_no_hotel(self):
        # S-02 Arvind TR1190B
        r = evaluate_delay(4)
        assert r.meal_voucher is True and r.meal_voucher_amount == 500
        assert r.lounge_access is True
        assert r.hotel is False and r.hotel_coverage is None

    def test_delay_5h_exact_no_hotel(self):
        # boundary: needs OVER 5h
        r = evaluate_delay(5)
        assert r.meal_voucher is True and r.hotel is False
        assert r.hotel_coverage is None

    def test_delay_5_1h_hotel_delayed_only(self):
        r = evaluate_delay(5.01)
        assert r.hotel is True and r.hotel_coverage == "delayed_hours_only"

    def test_delay_6h_meal_lounge_hotel_delayed(self):
        # S-03 Meher WL7742
        r = evaluate_delay(6)
        assert r.meal_voucher is True and r.meal_voucher_amount == 500
        assert r.lounge_access is True
        assert r.hotel is True and r.hotel_coverage == "delayed_hours_only"

    def test_delay_float_and_negative(self):
        assert evaluate_delay(4.0).meal_voucher is True
        assert evaluate_delay(-1).meal_voucher is False  # treated as 0
        assert evaluate_delay(0).hotel is False


# Cancellation - only airline-caused cancellations get refund or rebooking

class FakeBooking:
    def __init__(self, status, reason):
        self.status = status
        self.reason = reason

class TestCancellation:
    def test_airline_cancelled_eligible(self):
        b = FakeBooking("Cancelled", "Operational reasons")
        r = evaluate_cancellation(b)
        assert r.eligible_for_full_refund is True
        assert r.eligible_for_free_rebooking is True
        assert r.rebooking_window_hours == 24
        assert r.refund_sla == "7 business days"
        assert r.refund_method == "original_payment_method_only"

    def test_cancelled_wrong_reason_not_eligible(self):
        b = FakeBooking("Cancelled", "Weather")
        r = evaluate_cancellation(b)
        assert r.eligible_for_full_refund is False
        assert r.eligible_for_free_rebooking is False

    def test_delayed_not_cancellation(self):
        b = FakeBooking("Delayed", None)
        r = evaluate_cancellation(b)
        assert r.eligible_for_full_refund is False

    def test_dict_input(self):
        r = evaluate_cancellation({"status": "Cancelled", "reason": "Operational reasons"})
        assert r.eligible_for_full_refund is True
        r2 = evaluate_cancellation({"status": "Unaffected", "reason": None})
        assert r2.eligible_for_full_refund is False


# Fare waiver - agent can only waive up to 1500

class TestFare:
    def test_1000_within_limit(self):
        r = evaluate_fare_difference(1000)
        assert r.agent_can_waive is True and r.requires_supervisor is False
        assert r.agent_limit == 1500

    def test_1500_at_limit(self):
        r = evaluate_fare_difference(1500)
        assert r.agent_can_waive is True and r.requires_supervisor is False

    def test_1501_over_limit(self):
        r = evaluate_fare_difference(1501)
        assert r.agent_can_waive is False and r.requires_supervisor is True

    def test_2000_supervisor_required(self):
        # S-03 Meher
        r = evaluate_fare_difference(2000)
        assert r.agent_can_waive is False and r.requires_supervisor is True
        assert r.fare_difference == 2000

    def test_zero_and_negative(self):
        assert evaluate_fare_difference(0).agent_can_waive is True
        assert evaluate_fare_difference(-500).fare_difference == 0


# These check the second layer - not just what policy allows,
# but whether the agent is allowed to do what the customer wants

class TestAuthorizeHotel:
    def test_not_eligible_4h(self):
        auth = authorize_hotel("delayed_hours", 4)
        assert auth.allowed is False and "over 5h" in auth.detail

    def test_eligible_6h_delayed_hours(self):
        auth = authorize_hotel("delayed_hours", 6)
        assert auth.allowed is True

    def test_eligible_6h_but_full_night_blocked(self):
        auth = authorize_hotel("full_night", 6)
        assert auth.allowed is False and auth.reason == "hotel_coverage_mismatch"
        assert "delayed-hours only" in auth.detail

class TestAuthorizeFare:
    def test_within_limit(self):
        auth = authorize_fare_waiver(1000)
        assert auth.allowed is True and auth.escalation is False

    def test_exceeds_2000_escalate(self):
        auth = authorize_fare_waiver(2000)
        assert auth.allowed is False and auth.escalation is True
        assert auth.escalation_reason == "fare_difference_exceeds_limit"

class TestAuthorizeRefund:
    def test_airline_cancelled_ok(self):
        b = FakeBooking("Cancelled", "Operational reasons")
        auth = authorize_refund(b)
        assert auth.allowed is True

    def test_alternate_method_escalate(self):
        b = FakeBooking("Cancelled", "Operational reasons")
        auth = authorize_refund(b, requested_method="alternate")
        assert auth.allowed is False and auth.escalation is True
        assert auth.escalation_reason == "refund_payment_method"

    def test_not_airline_cancelled_blocked(self):
        b = FakeBooking("Delayed", None)
        auth = authorize_refund(b)
        assert auth.allowed is False and "airline-caused" in auth.detail

class TestAuthorizeUpgrade:
    def test_no_upgrade_policy(self):
        auth = authorize_upgrade()
        assert auth.allowed is False and "No policy" in auth.detail

"""
test_tools.py — tool authorization + idempotency, uses real SQLite (backend/resolveai.db).
Requires seed data (run python seed.py first). Each test resets via seed logic.
"""
import pytest
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal, Base, engine
from app.models import Action, Escalation
from app.tools.customer_tools import get_customer
from app.tools.booking_tools import get_booking, get_action_history
from app.tools.compensation_tools import issue_meal_voucher, grant_lounge_access, create_hotel_request, AuthorizationError as CompAuthError
from app.tools.refund_tools import initiate_refund, rebook_next_available, AuthorizationError as RefundAuthError
from app.tools.escalation_tools import escalate_to_human


@pytest.fixture(scope="module", autouse=True)
def ensure_seed():
    # Recreate tables + ensure seed rows exist (idempotent)
    Base.metadata.create_all(bind=engine)
    # Don't wipe here — seed.py already did; just verify customers exist
    db = SessionLocal()
    cnt = db.query(Action).count()  # just to touch DB
    db.close()
    yield


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def clean_audit(db: Session):
    # Clean audit tables before each test for isolation
    db.query(Action).delete()
    db.query(Escalation).delete()
    db.commit()
    yield
    db.query(Action).delete()
    db.query(Escalation).delete()
    db.commit()


class TestLookup:
    def test_get_customer_found(self, db):
        c = get_customer(db, "SK4821X")
        assert c and c.name == "Priya Nair" and c.loyalty_tier == "Gold"

    def test_get_customer_case_insensitive(self, db):
        assert get_customer(db, "sk4821x") is not None
        assert get_customer(db, "  SK4821X ") is not None

    def test_get_customer_unknown_none(self, db):
        assert get_customer(db, "XX9999") is None

    def test_get_booking_found(self, db):
        b = get_booking(db, "TR1190B")
        assert b and b.flight_number == "SK-118" and b.delay_hours == 4

    def test_get_booking_cancelled(self, db):
        b = get_booking(db, "SK4821X")
        assert b.status == "Cancelled" and b.reason == "Operational reasons"


class TestCompensation:
    def test_meal_voucher_4h_ok(self, db):
        a = issue_meal_voucher(db, "TR1190B")
        assert a.action_type == "MEAL_VOUCHER" and a.status == "completed"
        assert json.loads(a.metadata_json)["amount"] == 500

    def test_meal_voucher_idempotent(self, db):
        a1 = issue_meal_voucher(db, "TR1190B")
        a2 = issue_meal_voucher(db, "TR1190B")
        assert a1.id == a2.id
        assert db.query(Action).filter(Action.action_type == "MEAL_VOUCHER").count() == 1

    def test_meal_voucher_cancelled_blocked(self, db):
        # Cancelled has delay_hours None -> no meal
        with pytest.raises(CompAuthError):
            issue_meal_voucher(db, "SK4821X")

    def test_lounge_6h_ok(self, db):
        a = grant_lounge_access(db, "WL7742")
        assert a.action_type == "LOUNGE_ACCESS"

    def test_hotel_4h_blocked(self, db):
        with pytest.raises(CompAuthError) as e:
            create_hotel_request(db, "TR1190B")
        assert "over 5h" in str(e.value)

    def test_hotel_6h_delayed_hours_only(self, db):
        a = create_hotel_request(db, "WL7742")
        assert a.action_type == "HOTEL"
        assert json.loads(a.metadata_json)["coverage"] == "delayed_hours_only"

    def test_hotel_idempotent(self, db):
        a1 = create_hotel_request(db, "WL7742")
        a2 = create_hotel_request(db, "WL7742")
        assert a1.id == a2.id


class TestRefundRebook:
    def test_refund_cancelled_ok(self, db):
        a = initiate_refund(db, "SK4821X")
        assert a.action_type == "REFUND_INITIATED"
        meta = json.loads(a.metadata_json)
        assert "7 business days" in meta["sla"]

    def test_refund_idempotent(self, db):
        a1 = initiate_refund(db, "SK4821X")
        a2 = initiate_refund(db, "SK4821X")
        assert a1.id == a2.id

    def test_refund_delayed_blocked(self, db):
        with pytest.raises(RefundAuthError):
            initiate_refund(db, "TR1190B")

    def test_rebook_cancelled_ok(self, db):
        a = rebook_next_available(db, "SK4821X")
        assert a.action_type == "REBOOKED"
        assert json.loads(a.metadata_json)["window_hours"] == 24

    def test_rebook_delayed_blocked(self, db):
        with pytest.raises(RefundAuthError):
            rebook_next_available(db, "WL7742")


class TestEscalationAndHistory:
    def test_escalate_creates_pending(self, db):
        e = escalate_to_human(db, "WL7742", "fare_difference_exceeds_limit", "waive_2000")
        assert e.status == "pending" and e.reason == "fare_difference_exceeds_limit"

    def test_action_history(self, db):
        issue_meal_voucher(db, "WL7742")
        grant_lounge_access(db, "WL7742")
        hist = get_action_history(db, "WL7742")
        assert len(hist) == 2
        assert [h.action_type for h in hist] == ["MEAL_VOUCHER", "LOUNGE_ACCESS"]


class TestBoundaryAndSecurity:
    """Audit-required boundaries: 2h,2.99,3,3.01,5,5.01 + 1500/1500.01 + unknown PNR + isolation"""

    def _make_tmp_booking(self, db, pnr_suffix, delay, status="Delayed"):
        from app.models import Booking, Customer
        # create temp customer + booking for isolated boundary test
        tmp_pnr = f"TMP{pnr_suffix}"
        cust = Customer(name="Tmp", loyalty_tier="Silver", pnr=tmp_pnr+"_C", email="tmp@example.com", phone="000")
        db.add(cust); db.flush()
        bk = Booking(customer_id=cust.id, pnr=tmp_pnr, flight_number="TMP", route="A → B", travel_date="2026-09-23", scheduled_departure="10:00", status=status, delay_hours=delay, new_departure=None, reason=None)
        db.add(bk); db.commit(); db.refresh(bk)
        return bk.pnr

    def test_meal_under_3h_via_tmp_booking(self, db):
        pnr = self._make_tmp_booking(db, "2H", 2)
        a = issue_meal_voucher(db, pnr)
        assert a.action_type == "MEAL_VOUCHER"
        # lounge should be blocked for <3
        with pytest.raises(CompAuthError):
            grant_lounge_access(db, pnr)
        # cleanup
        from app.models import Booking, Customer
        db.query(Booking).filter(Booking.pnr == pnr).delete()
        db.query(Customer).filter(Customer.pnr == pnr+"_C").delete()
        db.commit()

    def test_meal_2_99h_allowed_lounge_blocked(self, db):
        pnr = self._make_tmp_booking(db, "299", 2.99)
        a = issue_meal_voucher(db, pnr)
        assert a.action_type == "MEAL_VOUCHER"
        with pytest.raises(CompAuthError):
            grant_lounge_access(db, pnr)
        from app.models import Booking, Customer
        db.query(Booking).filter(Booking.pnr == pnr).delete()
        db.query(Customer).filter(Customer.pnr == pnr+"_C").delete()
        db.commit()

    def test_3h_unspecified_both_blocked(self, db):
        pnr = self._make_tmp_booking(db, "3H", 3)
        with pytest.raises(CompAuthError) as e1:
            issue_meal_voucher(db, pnr)
        assert "3h" in str(e1.value) and "unspecified" in str(e1.value).lower()
        with pytest.raises(CompAuthError) as e2:
            grant_lounge_access(db, pnr)
        assert "3h" in str(e2.value)
        with pytest.raises(CompAuthError):
            create_hotel_request(db, pnr)
        from app.models import Booking, Customer
        db.query(Booking).filter(Booking.pnr == pnr).delete()
        db.query(Customer).filter(Customer.pnr == pnr+"_C").delete()
        db.commit()

    def test_3_01h_meal_lounge_allowed_hotel_blocked(self, db):
        pnr = self._make_tmp_booking(db, "301", 3.01)
        assert issue_meal_voucher(db, pnr).action_type == "MEAL_VOUCHER"
        assert grant_lounge_access(db, pnr).action_type == "LOUNGE_ACCESS"
        with pytest.raises(CompAuthError):
            create_hotel_request(db, pnr)
        from app.models import Booking, Customer
        db.query(Booking).filter(Booking.pnr == pnr).delete()
        db.query(Customer).filter(Customer.pnr == pnr+"_C").delete()
        db.commit()

    def test_5h_lounge_no_hotel(self, db):
        pnr = self._make_tmp_booking(db, "5H", 5)
        assert grant_lounge_access(db, pnr).action_type == "LOUNGE_ACCESS"
        with pytest.raises(CompAuthError):
            create_hotel_request(db, pnr)
        from app.models import Booking, Customer
        db.query(Booking).filter(Booking.pnr == pnr).delete()
        db.query(Customer).filter(Customer.pnr == pnr+"_C").delete()
        db.commit()

    def test_5_01h_hotel_allowed(self, db):
        pnr = self._make_tmp_booking(db, "501", 5.01)
        a = create_hotel_request(db, pnr)
        assert json.loads(a.metadata_json)["coverage"] == "delayed_hours_only"
        from app.models import Booking, Customer
        db.query(Booking).filter(Booking.pnr == pnr).delete()
        db.query(Customer).filter(Customer.pnr == pnr+"_C").delete()
        db.commit()

    def test_unknown_pnr_tool_blocked(self, db):
        with pytest.raises(CompAuthError):
            issue_meal_voucher(db, "XX9999")
        with pytest.raises(RefundAuthError):
            initiate_refund(db, "XX9999")
        # escalation with unknown PNR should raise ValueError per implementation
        with pytest.raises(Exception):
            escalate_to_human(db, "XX9999", "test", "action")

    def test_pnr_isolation(self, db):
        # requesting one PNR must not return another's booking
        b1 = get_booking(db, "SK4821X")
        b2 = get_booking(db, "TR1190B")
        assert b1.pnr != b2.pnr
        assert b1.flight_number != b2.flight_number
        c1 = get_customer(db, "SK4821X")
        c2 = get_customer(db, "TR1190B")
        assert c1.pnr != c2.pnr

    def test_fare_1500_01_requires_supervisor_via_authorize(self, db):
        from app.policies.policy_engine import authorize_fare_waiver
        auth = authorize_fare_waiver(1500.01)
        assert auth.allowed is False and auth.escalation is True
        auth2 = authorize_fare_waiver(1500)
        assert auth2.allowed is True

    def test_refund_original_vs_alternate(self, db):
        from app.policies.policy_engine import authorize_refund
        from app.tools.booking_tools import get_booking
        b = get_booking(db, "SK4821X")
        assert authorize_refund(b, "original").allowed is True
        assert authorize_refund(b, "alternate").escalation is True
        b2 = get_booking(db, "TR1190B")
        assert authorize_refund(b2).allowed is False  # delayed not airline cancelled

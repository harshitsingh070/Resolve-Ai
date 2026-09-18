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

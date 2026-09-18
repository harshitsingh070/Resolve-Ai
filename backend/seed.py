"""
seed.py — Intentional demo reset (NOT auto on startup).
Per architecture.md:269-276 + database.md:8.

Usage:
  python seed.py              # reset + seed (warns, then recreates)
  python seed.py --reset      # same, explicit flag
  python seed.py --check      # only verify, don't write

What it does:
  - Creates tables if missing (Base.metadata.create_all)
  - Deletes existing seed customers/bookings (CASCADE clears child audit rows for those bookings)
  - Inserts exactly 3 customers + 4 bookings (Priya has 2: SK4821X + SK4821X-R)
  - Leaves other DB state untouched except seed rows.

Normal app startup (uvicorn) only does create_all() — keeps audit history.
"""
import argparse
import sys
from pathlib import Path

# Windows cp1252 fix — allow Unicode arrow → in output
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Ensure backend/ is on path when run as `python seed.py` from project root or backend/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import engine, SessionLocal, Base
from app.models import Customer, Booking

# ── Seed truth (locked, from requirements.md + database.md:6) ──
CUSTOMERS = [
    {"name": "Priya Nair", "loyalty_tier": "Gold", "pnr": "SK4821X", "email": "priya.nair@example.com", "phone": "+91-98xxxxxx1"},
    {"name": "Arvind Kulkarni", "loyalty_tier": "Silver", "pnr": "TR1190B", "email": "arvind.kulkarni@example.com", "phone": "+91-98xxxxxx2"},
    {"name": "Meher Kaur", "loyalty_tier": "Platinum", "pnr": "WL7742", "email": "meher.kaur@example.com", "phone": "+91-98xxxxxx3"},
]

BOOKINGS = [
    # Priya forward — Cancelled (Operational reasons) — airline-caused
    {"pnr": "SK4821X", "customer_pnr": "SK4821X", "flight_number": "SK-204", "route": "Delhi → Goa", "travel_date": "2026-09-23", "scheduled_departure": "18:40", "status": "Cancelled", "delay_hours": None, "new_departure": None, "reason": "Operational reasons"},
    # Priya return — Unaffected (second booking for same customer, demonstrates 1—N)
    {"pnr": "SK4821X-R", "customer_pnr": "SK4821X", "flight_number": "SK-204R", "route": "Goa → Delhi", "travel_date": "2026-09-25", "scheduled_departure": "16:20", "status": "Unaffected", "delay_hours": None, "new_departure": None, "reason": None},
    # Arvind — Delayed 4h
    {"pnr": "TR1190B", "customer_pnr": "TR1190B", "flight_number": "SK-118", "route": "Mumbai → Bengaluru", "travel_date": "2026-09-23", "scheduled_departure": "07:10", "status": "Delayed", "delay_hours": 4, "new_departure": "11:10", "reason": None},
    # Meher — Delayed 6h
    {"pnr": "WL7742", "customer_pnr": "WL7742", "flight_number": "SK-305", "route": "Delhi → Hyderabad", "travel_date": "2026-09-23", "scheduled_departure": "14:00", "status": "Delayed", "delay_hours": 6, "new_departure": "20:00", "reason": None},
]


def seed(check_only: bool = False):
    # Always ensure tables exist
    Base.metadata.create_all(bind=engine)
    print(f"Tables ensured on {engine.url}")

    db = SessionLocal()
    try:
        # Check current counts
        c_count = db.query(Customer).count()
        b_count = db.query(Booking).count()
        print(f"Before: customers={c_count}, bookings={b_count}")

        if check_only:
            print("Check only — not writing.")
            _verify(db)
            return

        # Idempotent reset: delete seed rows (CASCADE deletes child actions/conversations/escalations for those bookings)
        # We delete bookings first, then customers.
        for b in BOOKINGS:
            db.query(Booking).filter(Booking.pnr == b["pnr"]).delete(synchronize_session=False)
        for cust in CUSTOMERS:
            db.query(Customer).filter(Customer.pnr == cust["pnr"]).delete(synchronize_session=False)
        db.commit()
        print("Old seed rows cleared (if any).")

        # Insert customers, keep map pnr -> id
        pnr_to_customer = {}
        for cust in CUSTOMERS:
            obj = Customer(**cust)
            db.add(obj)
            db.flush()  # to get id
            pnr_to_customer[cust["pnr"]] = obj
        db.commit()
        print(f"Inserted {len(CUSTOMERS)} customers.")

        # Insert bookings
        for b in BOOKINGS:
            customer = pnr_to_customer[b["customer_pnr"]]
            booking = Booking(
                customer_id=customer.id,
                pnr=b["pnr"],
                flight_number=b["flight_number"],
                route=b["route"],
                travel_date=b["travel_date"],
                scheduled_departure=b["scheduled_departure"],
                status=b["status"],
                delay_hours=b["delay_hours"],
                new_departure=b["new_departure"],
                reason=b["reason"],
            )
            db.add(booking)
        db.commit()
        print(f"Inserted {len(BOOKINGS)} bookings.")

        _verify(db)
        print("Seed complete. Run with --check to verify again.")
    finally:
        db.close()


def _verify(db):
    customers = db.query(Customer).order_by(Customer.pnr).all()
    bookings = db.query(Booking).order_by(Booking.pnr).all()
    print("\nVerify:")
    print(f"  customers: {len(customers)} (expected 3)")
    for cust in customers:
        print(f"    - {cust.pnr} | {cust.name} | {cust.loyalty_tier} | {cust.email}")
    print(f"  bookings: {len(bookings)} (expected 4)")
    for bk in bookings:
        print(f"    - {bk.pnr} | cust_id={bk.customer_id} | {bk.flight_number} {bk.route} {bk.travel_date} {bk.scheduled_departure} | {bk.status} delay={bk.delay_hours} new={bk.new_departure} reason={bk.reason}")

    # Relations check
    for cust in customers:
        count = db.query(Booking).filter(Booking.customer_id == cust.id).count()
        print(f"    relation: {cust.pnr} -> {count} booking(s)")

    # Counts for audit tables
    from app.models import Action, Conversation, Escalation
    print(f"  actions: {db.query(Action).count()} (expected 0 on fresh seed)")
    print(f"  conversations: {db.query(Conversation).count()} (expected 0)")
    print(f"  escalations: {db.query(Escalation).count()} (expected 0)")

    assert len(customers) == 3, f"Expected 3 customers, got {len(customers)}"
    assert len(bookings) == 4, f"Expected 4 bookings, got {len(bookings)}"
    print("Verification PASSED.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ResolveAI seed — intentional reset")
    parser.add_argument("--check", action="store_true", help="only verify, don't seed")
    parser.add_argument("--reset", action="store_true", help="explicit flag, same as default")
    args = parser.parse_args()
    seed(check_only=args.check)

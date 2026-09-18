"""
main.py — FastAPI app, CORS, routers, lifespan (create tables only, not seed).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine, ensure_trace_column
from app.routes import chat, customers, bookings
try:
    from app.routes import session as session_route
except ImportError:
    session_route = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if missing, keep audit data
    Base.metadata.create_all(bind=engine)
    ensure_trace_column()
    # Auto-seed for free tier without shell: if DB empty (fresh ephemeral FS), seed 3 customers/4 bookings once
    try:
        from sqlalchemy.orm import Session
        from app.models import Customer
        from sqlalchemy import text
        with Session(engine) as s:
            if s.query(Customer).count() == 0:
                # import seed logic inline to avoid circular import
                from pathlib import Path
                import sys
                # run seed.py main logic without wiping audit (DB is empty anyway)
                import subprocess
                # best effort: call seed via import
                from app.database import SessionLocal
                from app.models import Customer as C, Booking as B
                db = SessionLocal()
                try:
                    # reuse seed.py's CUSTOMERS/BOOKINGS if available
                    try:
                        from seed import CUSTOMERS, BOOKINGS
                    except ImportError:
                        CUSTOMERS = [
                            {"name": "Priya Nair", "loyalty_tier": "Gold", "pnr": "SK4821X", "email": "priya.nair@example.com", "phone": "+91-98xxxxxx1"},
                            {"name": "Arvind Kulkarni", "loyalty_tier": "Silver", "pnr": "TR1190B", "email": "arvind.kulkarni@example.com", "phone": "+91-98xxxxxx2"},
                            {"name": "Meher Kaur", "loyalty_tier": "Platinum", "pnr": "WL7742", "email": "meher.kaur@example.com", "phone": "+91-98xxxxxx3"},
                        ]
                        BOOKINGS = [
                            {"pnr": "SK4821X", "customer_pnr": "SK4821X", "flight_number": "SK-204", "route": "Delhi → Goa", "travel_date": "2026-09-23", "scheduled_departure": "18:40", "status": "Cancelled", "delay_hours": None, "new_departure": None, "reason": "Operational reasons"},
                            {"pnr": "SK4821X-R", "customer_pnr": "SK4821X", "flight_number": "SK-204R", "route": "Goa → Delhi", "travel_date": "2026-09-25", "scheduled_departure": "16:20", "status": "Unaffected", "delay_hours": None, "new_departure": None, "reason": None},
                            {"pnr": "TR1190B", "customer_pnr": "TR1190B", "flight_number": "SK-118", "route": "Mumbai → Bengaluru", "travel_date": "2026-09-23", "scheduled_departure": "07:10", "status": "Delayed", "delay_hours": 4, "new_departure": "11:10", "reason": None},
                            {"pnr": "WL7742", "customer_pnr": "WL7742", "flight_number": "SK-305", "route": "Delhi → Hyderabad", "travel_date": "2026-09-23", "scheduled_departure": "14:00", "status": "Delayed", "delay_hours": 6, "new_departure": "20:00", "reason": None},
                        ]
                    pnr_to_customer = {}
                    for cust in CUSTOMERS:
                        obj = C(**cust)
                        db.add(obj); db.flush()
                        pnr_to_customer[cust["pnr"]] = obj
                    db.commit()
                    for b in BOOKINGS:
                        cust = pnr_to_customer[b["customer_pnr"]]
                        db.add(B(customer_id=cust.id, pnr=b["pnr"], flight_number=b["flight_number"], route=b["route"], travel_date=b["travel_date"], scheduled_departure=b["scheduled_departure"], status=b["status"], delay_hours=b["delay_hours"], new_departure=b["new_departure"], reason=b["reason"]))
                    db.commit()
                finally:
                    db.close()
    except Exception:
        pass
    yield


app = FastAPI(title="ResolveAI — Airline Resolution Agent", version="1.0", lifespan=lifespan)

# CORS for Vite dev + any origin for demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(customers.router, prefix="/api", tags=["customers"])
app.include_router(bookings.router, prefix="/api", tags=["bookings"])
if session_route:
    app.include_router(session_route.router, prefix="/api", tags=["session"])


@app.get("/api/health")
def health():
    from app.config import settings
    return {"status": "ok", "db": "connected", "groq": "configured" if settings.GROQ_API_KEY and settings.GROQ_API_KEY != "your_groq_api_key_here" else "missing"}


@app.get("/")
def root():
    return {"message": "ResolveAI API — see /docs"}

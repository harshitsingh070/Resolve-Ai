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
    # Create tables if missing, keep audit data (seed is intentional python seed.py)
    Base.metadata.create_all(bind=engine)
    ensure_trace_column()
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

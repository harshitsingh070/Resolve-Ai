"""
database.py — SQLite engine + SessionLocal + Base + get_db dependency.
Locked per architecture.md:210-276, database.md:4.

Engine points at resolveai.db next to backend/ (via DATABASE_URL).
Normal startup only does Base.metadata.create_all() — never wipes.
Seed script (seed.py) is the intentional reset.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings
from pathlib import Path

def _resolve_db_url(url: str) -> str:
    """Make relative sqlite URL absolute to backend/ so cwd doesn't matter (review fix for cwd bug)."""
    if url.startswith("sqlite:///./"):
        # url is sqlite:///./resolveai.db -> resolve to backend/resolveai.db absolute
        rel = url.replace("sqlite:///./", "")
        # backend/ is parent of app/ (this file is in backend/app/)
        abs_path = (Path(__file__).resolve().parent.parent / rel).resolve()
        return f"sqlite:///{abs_path.as_posix()}"
    if url == "sqlite:///./resolveai.db":  # legacy exact
        abs_path = (Path(__file__).resolve().parent.parent / "resolveai.db").resolve()
        return f"sqlite:///{abs_path.as_posix()}"
    return url

def ensure_trace_column():
    """Auto-migrate: add decision_trace column if DB was created before Phase 8. Idempotent."""
    try:
        with engine.connect() as conn:
            result = conn.exec_driver_sql("PRAGMA table_info(conversations)")
            cols = [r[1] for r in result.fetchall()]
            if "decision_trace" not in cols:
                conn.exec_driver_sql("ALTER TABLE conversations ADD COLUMN decision_trace TEXT")
                conn.commit()
    except Exception:
        pass  # fresh DB will be created correctly by create_all

RESOLVED_DB_URL = _resolve_db_url(settings.DATABASE_URL)

# SQLite needs check_same_thread=False for FastAPI threaded use
connect_args = {"check_same_thread": False} if RESOLVED_DB_URL.startswith("sqlite") else {}

engine = create_engine(
    RESOLVED_DB_URL,
    connect_args=connect_args,
    echo=False,  # set True to see SQL
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

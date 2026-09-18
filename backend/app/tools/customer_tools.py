"""
customer_tools.py — PNR-aware customer lookup.
No policy check needed — always allowed. Returns None for unknown PNR.
"""
from sqlalchemy.orm import Session
from app.models import Customer


def _norm_pnr(pnr: str) -> str:
    return (pnr or "").strip().upper()


def get_customer(db: Session, pnr: str):
    """Fetch customer by PNR (case-insensitive). None if not found."""
    norm = _norm_pnr(pnr)
    if not norm:
        return None
    return db.query(Customer).filter(Customer.pnr == norm).first()


def get_customer_by_pnr(db: Session, pnr: str):
    """Alias for get_customer — kept for api-contract.md compatibility."""
    return get_customer(db, pnr)

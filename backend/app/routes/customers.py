from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.tools.customer_tools import get_customer
from app.tools.booking_tools import get_booking

router = APIRouter()

@router.get("/customers/{pnr}")
def get_customer_api(pnr: str, db: Session = Depends(get_db)):
    c = get_customer(db, pnr)
    if c:
        return {"id": c.id, "name": c.name, "loyalty_tier": c.loyalty_tier, "pnr": c.pnr, "email": c.email, "phone": c.phone}
    # Fallback: PNR like SK4821X-R is a booking PNR for Priya's return leg — return its owner customer (1:N)
    b = get_booking(db, pnr)
    if b:
        from app.models import Customer
        owner = db.query(Customer).filter(Customer.id == b.customer_id).first()
        if owner:
            return {"id": owner.id, "name": owner.name, "loyalty_tier": owner.loyalty_tier, "pnr": owner.pnr, "email": owner.email, "phone": owner.phone}
    raise HTTPException(status_code=404, detail=f"Customer not found for PNR '{pnr}'.")

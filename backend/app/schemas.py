"""
schemas.py — Pydantic I/O for API (mirrors models + api-contract.md).
Used by routes; also generates TS types for frontend.
"""
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class CustomerOut(BaseModel):
    id: int
    name: str
    loyalty_tier: str
    pnr: str
    email: str
    phone: str

    class Config:
        from_attributes = True


class BookingOut(BaseModel):
    id: int
    customer_id: int
    pnr: str
    flight_number: str
    route: str
    travel_date: str
    scheduled_departure: str
    status: str
    delay_hours: Optional[float] = None
    new_departure: Optional[str] = None
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class ActionOut(BaseModel):
    id: int
    booking_id: int
    pnr: str
    action_type: str
    status: str
    reason: Optional[str] = None
    metadata: Optional[Any] = None  # will map from metadata_json (parsed JSON)
    created_at: datetime

    class Config:
        from_attributes = True


class EscalationOut(BaseModel):
    id: int
    booking_id: int
    pnr: str
    reason: str
    requested_action: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: int
    booking_id: int
    pnr: str
    role: str
    message: str
    intent: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    pnr: str
    message: str


class IntentOut(BaseModel):
    primary_intent: str
    secondary_intents: list[str] = []
    sentiment: str = "neutral"
    requested_exception: bool = False
    entities: dict = {}


class ChatResponse(BaseModel):
    response: str
    intent: Optional[IntentOut] = None
    actions: list[ActionOut] = []
    escalation: Optional[EscalationOut] = None
    decision_trace: list[str] = []
    booking: Optional[BookingOut] = None
    customer: Optional[CustomerOut] = None
    ask_for_pnr: bool = False

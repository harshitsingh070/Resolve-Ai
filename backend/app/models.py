"""
models.py — 5 tables, locked per database.md + architecture.md:210-276.
Customer 1—N Bookings 1—N (Actions, Conversations, Escalations)
booking_id is true FK; pnr TEXT IDX is API convenience (requirements.md:98-104).
"""
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    loyalty_tier = Column(String, nullable=False)  # Gold | Silver | Platinum
    pnr = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)

    bookings = relationship("Booking", back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("loyalty_tier IN ('Gold','Silver','Platinum')", name="ck_customers_tier"),
    )

    def __repr__(self):
        return f"<Customer {self.pnr} {self.name} {self.loyalty_tier}>"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    pnr = Column(String, nullable=False, unique=True, index=True)
    flight_number = Column(String, nullable=False)
    route = Column(String, nullable=False)
    travel_date = Column(String, nullable=False)  # ISO YYYY-MM-DD
    scheduled_departure = Column(String, nullable=False)  # HH:MM
    status = Column(String, nullable=False)  # Cancelled | Delayed | Unaffected
    delay_hours = Column(Float, nullable=True)
    new_departure = Column(String, nullable=True)
    reason = Column(Text, nullable=True)  # "Operational reasons" or NULL

    customer = relationship("Customer", back_populates="bookings")
    actions = relationship("Action", back_populates="booking", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="booking", cascade="all, delete-orphan")
    escalations = relationship("Escalation", back_populates="booking", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('Cancelled','Delayed','Unaffected')", name="ck_bookings_status"),
    )

    def __repr__(self):
        return f"<Booking {self.pnr} {self.flight_number} {self.status} delay={self.delay_hours}>"


class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    pnr = Column(String, nullable=False, index=True)
    action_type = Column(String, nullable=False)  # MEAL_VOUCHER | LOUNGE_ACCESS | HOTEL | REFUND_INITIATED | REBOOKED
    status = Column(String, nullable=False)  # completed | blocked | failed
    reason = Column(Text, nullable=True)
    metadata_json = Column("metadata", Text, nullable=True)  # JSON string
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    booking = relationship("Booking", back_populates="actions")

    __table_args__ = (
        CheckConstraint(
            "action_type IN ('MEAL_VOUCHER','LOUNGE_ACCESS','HOTEL','REFUND_INITIATED','REBOOKED')",
            name="ck_actions_type",
        ),
        CheckConstraint("status IN ('completed','blocked','failed')", name="ck_actions_status"),
        Index("idx_actions_pnr", "pnr"),
        Index("idx_actions_booking_id", "booking_id"),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    pnr = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # user | assistant
    message = Column(Text, nullable=False)
    intent_json = Column("intent", Text, nullable=True)  # JSON string
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    booking = relationship("Booking", back_populates="conversations")

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_conversations_role"),
        Index("idx_conversations_pnr", "pnr"),
        Index("idx_conversations_booking_id", "booking_id"),
    )


class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    pnr = Column(String, nullable=False, index=True)
    reason = Column(Text, nullable=False)
    requested_action = Column(Text, nullable=False)
    status = Column(String, nullable=False)  # pending | resolved
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    booking = relationship("Booking", back_populates="escalations")

    __table_args__ = (
        CheckConstraint("status IN ('pending','resolved')", name="ck_escalations_status"),
        Index("idx_escalations_pnr", "pnr"),
        Index("idx_escalations_booking_id", "booking_id"),
    )

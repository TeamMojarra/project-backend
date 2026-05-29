from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="user")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=True)

    events = relationship("Event", foreign_keys="Event.created_by", back_populates="creator")
    reservations = relationship("Reservation", back_populates="user")
    tickets = relationship("Ticket", back_populates="user")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(50), nullable=False, default="event")
    modality = Column(String(30), nullable=False, default="presencial")
    location = Column(String(180), nullable=True)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=True)
    total_capacity = Column(Integer, nullable=False)
    available_capacity = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, index=True, default="available")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    creator = relationship("User", foreign_keys=[created_by], back_populates="events")
    updater = relationship("User", foreign_keys=[updated_by])
    reservations = relationship("Reservation", back_populates="event")


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), index=True, nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, index=True, default="pending_payment")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="reservations")
    event = relationship("Event", back_populates="reservations")
    payment = relationship("SimulatedPayment", back_populates="reservation", uselist=False)
    tickets = relationship("Ticket", back_populates="reservation")


class SimulatedPayment(Base):
    __tablename__ = "simulated_payments"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), unique=True, nullable=False)
    holder_name = Column(String(100), nullable=False)
    masked_card_number = Column(String(25), nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    result = Column(String(30), nullable=False, default="approved")
    processed_at = Column(DateTime, nullable=False, default=utc_now)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    reservation = relationship("Reservation", back_populates="payment")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    ticket_code = Column(String(120), unique=True, index=True, nullable=False)
    qr_code_url = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="active")
    generated_at = Column(DateTime, nullable=False, default=utc_now)
    used_at = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    reservation = relationship("Reservation", back_populates="tickets")
    user = relationship("User", back_populates="tickets")


class TicketValidation(Base):
    __tablename__ = "ticket_validations"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    validated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    validation_result = Column(String(30), nullable=False)
    validation_datetime = Column(DateTime, nullable=False, default=utc_now)
    notes = Column(Text, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    type = Column(String(50), nullable=False, default="system")
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="unread")
    created_at = Column(DateTime, nullable=False, default=utc_now)

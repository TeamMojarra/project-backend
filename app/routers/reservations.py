from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_database
from app.models import Event, Reservation, SimulatedPayment, Ticket, User
from app.schemas import (
    CheckoutResponse,
    MessageResponse,
    PaymentCreate,
    ReservationCreate,
    ReservationResponse,
)
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["Reservations"])


@router.post(
    "/reservations",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation(
    payload: ReservationCreate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = (
        database.query(Event)
        .filter(Event.id == payload.event_id)
        .with_for_update()
        .first()
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evento no encontrado"
        )
    if event.created_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes reservar tu propio evento",
        )
    if event.status != "available" or event.available_capacity < payload.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No hay cupos suficientes"
        )
    if payload.quantity > event.max_tickets_per_purchase:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Este evento permite comprar hasta "
                f"{event.max_tickets_per_purchase} tickets por reserva"
            ),
        )

    reservation = Reservation(
        user_id=current_user.id, event_id=event.id, quantity=payload.quantity
    )
    event.available_capacity -= payload.quantity
    event.status = "sold_out" if event.available_capacity == 0 else event.status
    database.add(reservation)
    database.commit()
    database.refresh(reservation)
    reservation.event = event
    return reservation


@router.get("/reservations/my", response_model=List[ReservationResponse])
def list_my_reservations(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    return (
        database.query(Reservation)
        .options(joinedload(Reservation.event))
        .filter(Reservation.user_id == current_user.id)
        .filter(Reservation.status.in_(("pending_payment", "confirmed")))
        .order_by(Reservation.created_at.desc())
        .all()
    )


@router.delete("/reservations/{reservation_id}", response_model=MessageResponse)
def cancel_pending_reservation(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    reservation = (
        database.query(Reservation)
        .filter(
            Reservation.id == reservation_id, Reservation.user_id == current_user.id
        )
        .first()
    )
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada"
        )
    if reservation.status != "pending_payment":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo puedes cancelar reservas pendientes de pago",
        )

    event = (
        database.query(Event)
        .filter(Event.id == reservation.event_id)
        .with_for_update()
        .first()
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evento no encontrado"
        )

    event.available_capacity += reservation.quantity
    if event.status == "sold_out" and event.available_capacity > 0:
        event.status = "available"
    reservation.status = "cancelled"
    reservation.updated_at = datetime.now(timezone.utc)
    database.commit()
    return MessageResponse(message="Reserva cancelada correctamente")


@router.post("/reservations/{reservation_id}/pay", response_model=CheckoutResponse)
def pay_reservation(
    reservation_id: int,
    payload: PaymentCreate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    reservation = (
        database.query(Reservation)
        .filter(
            Reservation.id == reservation_id, Reservation.user_id == current_user.id
        )
        .first()
    )
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada"
        )
    if reservation.status != "pending_payment":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="La reserva ya fue procesada"
        )

    event = (
        database.query(Event)
        .filter(Event.id == reservation.event_id)
        .with_for_update()
        .first()
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evento no encontrado"
        )

    payment = SimulatedPayment(
        reservation_id=reservation.id,
        holder_name=payload.holder_name,
        masked_card_number=mask_card(payload.card_number),
        amount=0.0,
        result=payload.result,
    )

    if payload.result == "rejected":
        event.available_capacity += reservation.quantity
        if event.status == "sold_out" and event.available_capacity > 0:
            event.status = "available"
        reservation.status = "rejected"
        reservation.updated_at = datetime.now(timezone.utc)
        database.add(payment)
        database.commit()
        database.refresh(payment)
        database.refresh(reservation)
        reservation.event = event
        return CheckoutResponse(
            payment=payment,
            reservation=reservation,
            ticket=None,
            message="Pago simulado rechazado",
        )

    reservation.status = "confirmed"
    reservation.updated_at = datetime.now(timezone.utc)

    tickets = [
        Ticket(
            reservation_id=reservation.id,
            user_id=current_user.id,
            ticket_code=f"RSV-{uuid4().hex[:10].upper()}",
            qr_code_url=None,
        )
        for _ in range(reservation.quantity)
    ]
    database.add_all([payment, *tickets])
    database.commit()
    database.refresh(payment)
    for ticket in tickets:
        database.refresh(ticket)
        ticket.event = event
        ticket.user = current_user
    database.refresh(reservation)
    reservation.event = event
    return CheckoutResponse(
        payment=payment,
        reservation=reservation,
        ticket=tickets[0] if tickets else None,
        tickets=tickets,
        message="Pago aprobado y ticket generado",
    )


def mask_card(card_number: str | None) -> str:
    digits = "".join(char for char in (card_number or "") if char.isdigit())
    return f"**** **** **** {digits[-4:]}" if len(digits) >= 4 else "simulated"

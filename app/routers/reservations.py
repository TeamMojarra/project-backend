from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_database
from app.dependencies import require_event_owner
from app.models import Event, Reservation, ServiceSlot, SimulatedPayment, Ticket, User
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
    service_slot = None
    if event.event_type == "service":
        if payload.quantity != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los servicios se reservan de a un turno",
            )
        if not payload.service_slot_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selecciona un horario disponible para este servicio",
            )
        service_slot = (
            database.query(ServiceSlot)
            .filter(
                ServiceSlot.id == payload.service_slot_id,
                ServiceSlot.event_id == event.id,
            )
            .with_for_update()
            .first()
        )
        if not service_slot or service_slot.status != "available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ese horario ya no esta disponible",
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
        user_id=current_user.id,
        event_id=event.id,
        quantity=payload.quantity,
        service_slot_id=payload.service_slot_id,
    )
    event.available_capacity -= payload.quantity
    event.status = "sold_out" if event.available_capacity == 0 else event.status
    if service_slot:
        service_slot.status = "held"
        service_slot.updated_at = datetime.now(timezone.utc)
    database.add(reservation)
    database.commit()
    database.refresh(reservation)
    reservation.event = event
    reservation.service_slot = service_slot
    return reservation


@router.get("/reservations/my", response_model=List[ReservationResponse])
def list_my_reservations(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    return (
        database.query(Reservation)
        .options(joinedload(Reservation.event), joinedload(Reservation.service_slot))
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

    release_reservation_capacity(event, reservation)
    reservation.status = "cancelled"
    reservation.updated_at = datetime.now(timezone.utc)
    database.commit()
    return MessageResponse(message="Reserva cancelada correctamente")


@router.post("/reservations/{reservation_id}/owner-cancel", response_model=MessageResponse)
def cancel_reservation_as_owner(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    reservation = (
        database.query(Reservation)
        .options(joinedload(Reservation.event), joinedload(Reservation.service_slot))
        .filter(Reservation.id == reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada"
        )
    require_event_owner(reservation.event, current_user)
    if reservation.status not in {"pending_payment", "confirmed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La reserva ya fue cancelada o procesada",
        )

    release_reservation_capacity(reservation.event, reservation)
    reservation.status = "cancelled"
    reservation.updated_at = datetime.now(timezone.utc)
    database.query(Ticket).filter(Ticket.reservation_id == reservation.id).update(
        {"status": "cancelled"}, synchronize_session=False
    )
    database.commit()
    return MessageResponse(
        message="Reserva cancelada. Procesa el reembolso fuera del simulador."
    )


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
        amount=float(event.price or 0) * reservation.quantity,
        result=payload.result,
    )

    if payload.result == "rejected":
        release_reservation_capacity(event, reservation)
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
    if reservation.service_slot:
        reservation.service_slot.status = "booked"
        reservation.service_slot.updated_at = datetime.now(timezone.utc)

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


def release_reservation_capacity(event: Event, reservation: Reservation):
    event.available_capacity += reservation.quantity
    if event.status == "sold_out" and event.available_capacity > 0:
        event.status = "available"
    if reservation.service_slot:
        reservation.service_slot.status = "available"
        reservation.service_slot.updated_at = datetime.now(timezone.utc)

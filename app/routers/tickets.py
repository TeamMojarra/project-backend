from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_database
from app.dependencies import require_ticket_validator
from app.models import Reservation, Ticket, TicketValidation, User
from app.schemas import TicketResponse, TicketValidationResponse
from app.security import get_current_user

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


@router.get("/my", response_model=List[TicketResponse])
def list_my_tickets(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    tickets = (
        database.query(Ticket)
        .options(joinedload(Ticket.reservation).joinedload(Reservation.event), joinedload(Ticket.user))
        .filter(Ticket.user_id == current_user.id)
        .order_by(Ticket.generated_at.desc())
        .all()
    )
    for ticket in tickets:
        ticket.event = ticket.reservation.event
    return tickets


@router.post("/{ticket_code}/validate", response_model=TicketValidationResponse)
def validate_ticket(
    ticket_code: str,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    ticket = (
        database.query(Ticket)
        .options(joinedload(Ticket.reservation).joinedload(Reservation.event), joinedload(Ticket.user))
        .filter(Ticket.ticket_code == ticket_code)
        .first()
    )
    if not ticket:
        return TicketValidationResponse(
            valid=False, status="invalid", message="Ticket no encontrado"
        )

    require_ticket_validator(ticket.reservation.event, current_user)

    if ticket.status != "active":
        ticket.event = ticket.reservation.event
        return TicketValidationResponse(
            valid=False,
            status="already_used" if ticket.status == "used" else ticket.status,
            message="El ticket ya fue usado" if ticket.status == "used" else "El ticket no está activo",
            ticket=ticket,
        )

    ticket.status = "used"
    ticket.used_at = datetime.now(timezone.utc)
    database.add(
        TicketValidation(
            ticket_id=ticket.id, validated_by=current_user.id, validation_result="valid"
        )
    )
    database.commit()
    database.refresh(ticket)
    ticket.event = ticket.reservation.event
    return TicketValidationResponse(
        valid=True,
        status="valid",
        message="Ticket validado correctamente",
        ticket=ticket,
    )

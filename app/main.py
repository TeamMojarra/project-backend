from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_database
from app.models import Event, Notification, Reservation, SimulatedPayment, Ticket, TicketValidation, User
from app.schemas import (
    CheckoutResponse,
    EventCreate,
    EventResponse,
    EventUpdate,
    MessageResponse,
    NotificationResponse,
    PasswordChange,
    PaymentCreate,
    ReservationCreate,
    ReservationResponse,
    TicketResponse,
    TicketValidationResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.security import create_access_token, get_current_user, hash_password, verify_password

app = FastAPI(
    title="Reservent API",
    description="API de reservas, eventos y tickets digitales.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
def root():
    return {"message": "API Reservent funcionando correctamente", "docs": "/docs"}


@app.post("/api/auth/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, database: Session = Depends(get_database)):
    existing_user = database.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo ya está registrado")

    user = User(
        name=payload.name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role="user",
    )
    database.add(user)
    database.commit()

    return MessageResponse(message="Registro exitoso. Ya puede iniciar sesión.")


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: UserLogin, database: Session = Depends(get_database)):
    user = database.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_access_token(user), user=UserResponse.model_validate(user))


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.put("/api/auth/me", response_model=UserResponse)
@app.patch("/api/auth/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    duplicate = (
        database.query(User)
        .filter(func.lower(User.email) == payload.email.lower(), User.id != current_user.id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este correo ya está registrado")

    current_user.name = payload.name
    current_user.email = payload.email.lower()
    current_user.updated_at = datetime.now(timezone.utc)
    database.commit()
    database.refresh(current_user)
    return current_user


@app.put("/api/auth/password", response_model=MessageResponse)
@app.post("/api/auth/password", response_model=MessageResponse)
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual es incorrecta")
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La nueva contraseña debe ser diferente")

    current_user.password_hash = hash_password(payload.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    database.commit()
    return MessageResponse(message="Contraseña actualizada correctamente")


@app.get("/api/events", response_model=List[EventResponse])
def list_events(
    event_type: Optional[str] = None,
    modality: Optional[str] = None,
    search: Optional[str] = None,
    include_expired: bool = False,
    created_by: Optional[int] = None,
    exclude_creator: Optional[int] = None,
    database: Session = Depends(get_database),
):
    query = database.query(Event)
    if not include_expired:
        query = query.filter(Event.status != "cancelled")
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if modality:
        query = query.filter(Event.modality == modality)
    if created_by:
        query = query.filter(Event.created_by == created_by)
    if exclude_creator:
        query = query.filter(Event.created_by != exclude_creator)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Event.name.ilike(pattern), Event.description.ilike(pattern)))

    return query.order_by(Event.start_datetime.asc()).all()


@app.post("/api/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = Event(
        created_by=current_user.id,
        name=payload.name,
        description=payload.description,
        event_type=payload.event_type,
        modality=payload.modality,
        location=payload.location,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        total_capacity=payload.total_capacity,
        available_capacity=payload.total_capacity,
        status="available",
    )
    database.add(event)
    database.commit()
    database.refresh(event)
    return event


@app.get("/api/events/{event_id}", response_model=EventResponse)
def get_event(event_id: int, database: Session = Depends(get_database)):
    return find_event(database, event_id)


@app.put("/api/events/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    payload: EventUpdate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = find_event(database, event_id)
    require_event_owner(event, current_user)

    reserved = event.total_capacity - event.available_capacity
    if payload.total_capacity < reserved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El cupo no puede ser menor a las reservas existentes")

    event.name = payload.name
    event.description = payload.description
    event.event_type = payload.event_type
    event.modality = payload.modality
    event.location = payload.location
    event.start_datetime = payload.start_datetime
    event.end_datetime = payload.end_datetime
    event.total_capacity = payload.total_capacity
    event.available_capacity = payload.total_capacity - reserved
    event.status = "sold_out" if event.available_capacity == 0 else payload.status
    event.updated_by = current_user.id
    event.updated_at = datetime.now(timezone.utc)
    database.commit()
    database.refresh(event)
    return event


@app.delete("/api/events/{event_id}", response_model=MessageResponse)
def cancel_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = find_event(database, event_id)
    require_event_owner(event, current_user)

    confirmed = database.query(Reservation).filter_by(event_id=event.id, status="confirmed").count()
    if confirmed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se puede cancelar un evento con reservas confirmadas")

    event.status = "cancelled"
    event.updated_by = current_user.id
    event.updated_at = datetime.now(timezone.utc)
    database.commit()
    return MessageResponse(message="Evento cancelado correctamente")


@app.post("/api/reservations", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
def create_reservation(
    payload: ReservationCreate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = find_event(database, payload.event_id)
    if event.status not in {"available", "sold_out"} or event.available_capacity < payload.quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay cupos suficientes")

    reservation = Reservation(user_id=current_user.id, event_id=event.id, quantity=payload.quantity)
    database.add(reservation)
    database.commit()
    database.refresh(reservation)
    reservation.event = event
    return reservation


@app.get("/api/reservations/my", response_model=List[ReservationResponse])
def list_my_reservations(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    return (
        database.query(Reservation)
        .options(joinedload(Reservation.event))
        .filter(Reservation.user_id == current_user.id)
        .order_by(Reservation.created_at.desc())
        .all()
    )


@app.post("/api/reservations/{reservation_id}/pay", response_model=CheckoutResponse)
def pay_reservation(
    reservation_id: int,
    payload: PaymentCreate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    reservation = (
        database.query(Reservation)
        .options(joinedload(Reservation.event))
        .filter(Reservation.id == reservation_id, Reservation.user_id == current_user.id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    if reservation.status == "confirmed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La reserva ya fue pagada")
    if reservation.event.available_capacity < reservation.quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay cupos suficientes")

    reservation.event.available_capacity -= reservation.quantity
    reservation.event.status = "sold_out" if reservation.event.available_capacity == 0 else reservation.event.status
    reservation.status = "confirmed"
    reservation.updated_at = datetime.now(timezone.utc)

    payment = SimulatedPayment(
        reservation_id=reservation.id,
        holder_name=payload.holder_name,
        masked_card_number=mask_card(payload.card_number),
        amount=0.0,
        result="approved",
    )
    ticket = Ticket(
        reservation_id=reservation.id,
        user_id=current_user.id,
        ticket_code=f"RSV-{uuid4().hex[:10].upper()}",
        qr_code_url=None,
    )
    database.add_all([payment, ticket])
    database.commit()
    database.refresh(payment)
    database.refresh(ticket)
    database.refresh(reservation)
    return CheckoutResponse(payment=payment, reservation=reservation, ticket=ticket, message="Pago aprobado y ticket generado")


@app.get("/api/tickets/my", response_model=List[TicketResponse])
def list_my_tickets(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    tickets = (
        database.query(Ticket)
        .options(joinedload(Ticket.reservation).joinedload(Reservation.event))
        .filter(Ticket.user_id == current_user.id)
        .order_by(Ticket.generated_at.desc())
        .all()
    )
    for ticket in tickets:
        ticket.event = ticket.reservation.event
    return tickets


@app.post("/api/tickets/{ticket_code}/validate", response_model=TicketValidationResponse)
def validate_ticket(
    ticket_code: str,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    ticket = database.query(Ticket).filter(Ticket.ticket_code == ticket_code).first()
    if not ticket:
        return TicketValidationResponse(valid=False, status="invalid", message="Ticket no encontrado")
    if ticket.status == "used":
        return TicketValidationResponse(valid=False, status="already_used", message="El ticket ya fue usado", ticket=ticket)

    ticket.status = "used"
    ticket.used_at = datetime.now(timezone.utc)
    database.add(TicketValidation(ticket_id=ticket.id, validated_by=current_user.id, validation_result="valid"))
    database.commit()
    database.refresh(ticket)
    return TicketValidationResponse(valid=True, status="valid", message="Ticket validado correctamente", ticket=ticket)


@app.get("/api/notifications", response_model=List[NotificationResponse])
def list_notifications(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    return (
        database.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@app.put("/api/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    notification = (
        database.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificación no encontrada")
    notification.status = "read"
    database.commit()
    database.refresh(notification)
    return notification


@app.put("/api/notifications/read-all", response_model=MessageResponse)
@app.post("/api/notifications/mark_all_read", response_model=MessageResponse)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    database.query(Notification).filter(Notification.user_id == current_user.id).update({"status": "read"})
    database.commit()
    return MessageResponse(message="Notificaciones marcadas como leídas")


@app.delete("/api/notifications", response_model=MessageResponse)
def clear_notifications(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    database.query(Notification).filter(Notification.user_id == current_user.id).delete()
    database.commit()
    return MessageResponse(message="Notificaciones eliminadas")


def find_event(database: Session, event_id: int) -> Event:
    event = database.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento no encontrado")
    return event


def require_event_owner(event: Event, user: User):
    if event.created_by != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos sobre este evento")


def mask_card(card_number: Optional[str]) -> str:
    digits = "".join(char for char in (card_number or "") if char.isdigit())
    return f"**** **** **** {digits[-4:]}" if len(digits) >= 4 else "simulated"

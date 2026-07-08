from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import nullslast, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_database
from app.dependencies import find_event, require_event_owner
from app.models import Event, Reservation, ServiceSlot, User
from app.schemas import (
    EventCreate,
    EventResponse,
    EventUpdate,
    MessageResponse,
    ReservationResponse,
    ServiceSlotGenerate,
    ServiceSlotResponse,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/events", tags=["Events"])


@router.get("", response_model=List[EventResponse])
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
        query = query.filter(
            or_(Event.name.ilike(pattern), Event.description.ilike(pattern))
        )

    return query.order_by(
        nullslast(Event.start_datetime.asc()), Event.created_at.desc()
    ).all()


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = Event(
        created_by=current_user.id,
        name=payload.name,
        description=payload.description,
        image_url=payload.image_url,
        event_type=payload.event_type,
        modality=payload.modality,
        location=payload.location,
        price=payload.price,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        total_capacity=payload.total_capacity,
        available_capacity=payload.total_capacity,
        max_tickets_per_purchase=payload.max_tickets_per_purchase,
        status="available",
    )
    database.add(event)
    database.commit()
    database.refresh(event)
    return event


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: int, database: Session = Depends(get_database)):
    return find_event(database, event_id)


@router.get("/{event_id}/slots", response_model=List[ServiceSlotResponse])
def list_service_slots(
    event_id: int,
    include_booked: bool = False,
    database: Session = Depends(get_database),
):
    event = find_event(database, event_id)
    if event.event_type != "service":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este recurso solo aplica para servicios",
        )
    if event.status != "available" and not include_booked:
        return []

    query = database.query(ServiceSlot).filter(ServiceSlot.event_id == event.id)
    if not include_booked:
        query = query.filter(ServiceSlot.status == "available")
    return query.order_by(ServiceSlot.starts_at.asc()).all()


@router.get("/{event_id}/reservations", response_model=List[ReservationResponse])
def list_event_reservations(
    event_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = find_event(database, event_id)
    require_event_owner(event, current_user)
    return (
        database.query(Reservation)
        .options(joinedload(Reservation.user), joinedload(Reservation.service_slot))
        .filter(Reservation.event_id == event.id)
        .order_by(Reservation.created_at.desc())
        .all()
    )


@router.post("/{event_id}/slots/generate", response_model=List[ServiceSlotResponse])
def generate_service_slots(
    event_id: int,
    payload: ServiceSlotGenerate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = find_event(database, event_id)
    require_event_owner(event, current_user)
    if event.event_type != "service":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo los servicios pueden generar horarios",
        )

    database.query(ServiceSlot).filter(
        ServiceSlot.event_id == event.id, ServiceSlot.status == "available"
    ).delete(synchronize_session=False)

    slots = []
    current_date = payload.start_date
    selected_weekdays = set(payload.weekdays)
    while current_date <= payload.end_date:
        if current_date.weekday() in selected_weekdays:
            slot_start = datetime.combine(current_date, payload.start_time)
            day_end = datetime.combine(current_date, payload.end_time)
            while slot_start + timedelta(minutes=payload.slot_minutes) <= day_end:
                slot_end = slot_start + timedelta(minutes=payload.slot_minutes)
                slots.append(
                    ServiceSlot(
                        event_id=event.id,
                        starts_at=slot_start,
                        ends_at=slot_end,
                        status="available",
                    )
                )
                slot_start = slot_end
        current_date += timedelta(days=1)

    if not slots:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La agenda no genera horarios disponibles",
        )

    database.add_all(slots)
    database.flush()
    sync_service_capacity(database, event)
    database.commit()
    for slot in slots:
        database.refresh(slot)
    return slots


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    payload: EventUpdate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = find_event(database, event_id)
    require_event_owner(event, current_user)
    ensure_event_not_started(event)

    reserved = event.total_capacity - event.available_capacity
    if payload.total_capacity < reserved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cupo no puede ser menor a las reservas existentes",
        )

    event.name = payload.name
    event.description = payload.description
    event.image_url = payload.image_url
    event.event_type = payload.event_type
    event.modality = payload.modality
    event.location = payload.location
    event.price = payload.price
    event.start_datetime = payload.start_datetime
    event.end_datetime = payload.end_datetime
    event.total_capacity = payload.total_capacity
    event.available_capacity = payload.total_capacity - reserved
    event.max_tickets_per_purchase = payload.max_tickets_per_purchase
    event.status = (
        "sold_out"
        if payload.status == "available" and event.available_capacity == 0
        else payload.status
    )
    event.updated_by = current_user.id
    event.updated_at = datetime.now(timezone.utc)
    database.commit()
    database.refresh(event)
    return event


@router.delete("/{event_id}", response_model=MessageResponse)
def cancel_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = find_event(database, event_id)
    require_event_owner(event, current_user)
    ensure_event_not_started(event)

    confirmed = (
        database.query(Reservation)
        .filter_by(event_id=event.id, status="confirmed")
        .count()
    )
    if confirmed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede cancelar un evento con reservas confirmadas",
        )

    event.status = "cancelled"
    event.updated_by = current_user.id
    event.updated_at = datetime.now(timezone.utc)
    database.commit()
    return MessageResponse(message="Evento cancelado correctamente")


def ensure_event_not_started(event: Event):
    event_start = event.start_datetime
    if not event_start:
        return
    if event_start.tzinfo is None:
        event_start = event_start.replace(tzinfo=timezone.utc)
    if event_start <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede modificar un evento que ya inició",
        )


def sync_service_capacity(database: Session, event: Event):
    available = (
        database.query(ServiceSlot)
        .filter_by(event_id=event.id, status="available")
        .count()
    )
    active = (
        database.query(ServiceSlot)
        .filter(ServiceSlot.event_id == event.id, ServiceSlot.status != "cancelled")
        .count()
    )
    event.total_capacity = active
    event.available_capacity = available
    if event.status in {"cancelled", "finished"}:
        return
    event.status = "sold_out" if available == 0 else "available"

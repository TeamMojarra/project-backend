from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_database
from app.dependencies import find_event, require_event_owner
from app.models import Event, Reservation, User
from app.schemas import EventCreate, EventResponse, EventUpdate, MessageResponse
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
        query = query.filter(or_(Event.name.ilike(pattern), Event.description.ilike(pattern)))

    return query.order_by(Event.start_datetime.asc()).all()


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


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: int, database: Session = Depends(get_database)):
    return find_event(database, event_id)


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


@router.delete("/{event_id}", response_model=MessageResponse)
def cancel_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    event = find_event(database, event_id)
    require_event_owner(event, current_user)
    ensure_event_not_started(event)

    confirmed = database.query(Reservation).filter_by(event_id=event.id, status="confirmed").count()
    if confirmed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se puede cancelar un evento con reservas confirmadas")

    event.status = "cancelled"
    event.updated_by = current_user.id
    event.updated_at = datetime.now(timezone.utc)
    database.commit()
    return MessageResponse(message="Evento cancelado correctamente")


def ensure_event_not_started(event: Event):
    event_start = event.start_datetime
    if event_start.tzinfo is None:
        event_start = event_start.replace(tzinfo=timezone.utc)
    if event_start <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede modificar un evento que ya inició")

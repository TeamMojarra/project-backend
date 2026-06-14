from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Event, User


def find_event(database: Session, event_id: int) -> Event:
    event = database.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evento no encontrado"
        )
    return event


def require_event_owner(event: Event, user: User):
    if event.created_by != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos sobre este evento",
        )


def require_ticket_validator(event: Event, user: User):
    if event.created_by != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para validar tickets de este evento",
        )

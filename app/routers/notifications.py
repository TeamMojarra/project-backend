from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_database
from app.models import Notification, User
from app.schemas import MessageResponse, NotificationResponse
from app.security import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationResponse])
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


@router.put("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    notification = (
        database.query(Notification)
        .filter(
            Notification.id == notification_id, Notification.user_id == current_user.id
        )
        .first()
    )
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notificación no encontrada"
        )
    notification.status = "read"
    database.commit()
    database.refresh(notification)
    return notification


@router.put("/read-all", response_model=MessageResponse)
@router.post("/mark_all_read", response_model=MessageResponse)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    database.query(Notification).filter(Notification.user_id == current_user.id).update(
        {"status": "read"}
    )
    database.commit()
    return MessageResponse(message="Notificaciones marcadas como leídas")


@router.delete("", response_model=MessageResponse)
def clear_notifications(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    database.query(Notification).filter(
        Notification.user_id == current_user.id
    ).delete()
    database.commit()
    return MessageResponse(message="Notificaciones eliminadas")

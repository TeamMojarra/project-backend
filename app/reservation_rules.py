from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import Event, Reservation, ServiceSlot

CHECKOUT_EXPIRATION_MINUTES = 5


def release_reservation_capacity(event: Event, reservation: Reservation):
    event.available_capacity += reservation.quantity
    if event.status == "sold_out" and event.available_capacity > 0:
        event.status = "available"
    if reservation.service_slot:
        reservation.service_slot.status = "available"
        reservation.service_slot.updated_at = datetime.now(timezone.utc)


def expire_pending_reservations(database: Session):
    expires_before = datetime.now(timezone.utc) - timedelta(
        minutes=CHECKOUT_EXPIRATION_MINUTES
    )
    pending_reservations = (
        database.query(Reservation)
        .options(joinedload(Reservation.event), joinedload(Reservation.service_slot))
        .filter(Reservation.status == "pending_payment")
        .filter(Reservation.created_at <= expires_before)
        .all()
    )
    if not pending_reservations:
        return 0

    for reservation in pending_reservations:
        release_reservation_capacity(reservation.event, reservation)
        reservation.status = "cancelled"
        reservation.updated_at = datetime.now(timezone.utc)

    database.commit()
    return len(pending_reservations)

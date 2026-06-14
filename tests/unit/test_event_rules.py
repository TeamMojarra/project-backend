from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas import EventCreate, EventUpdate, ensure_aware_datetime


def future_datetime(hours=2):
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def valid_event_payload(**overrides):
    payload = {
        "name": "Charla de Python",
        "description": "Evento de prueba",
        "event_type": "event",
        "modality": "presencial",
        "location": "Auditorio",
        "start_datetime": future_datetime(),
        "end_datetime": future_datetime(hours=4),
        "total_capacity": 30,
    }
    payload.update(overrides)
    return payload


def test_event_requires_start_datetime():
    with pytest.raises(ValidationError, match="fecha de inicio es obligatoria"):
        EventCreate(**valid_event_payload(start_datetime=None, end_datetime=None))


def test_event_normalizes_name_whitespace():
    event = EventCreate(**valid_event_payload(name="  Taller de testing  "))

    assert event.name == "Taller de testing"


def test_event_rejects_blank_name():
    with pytest.raises(ValidationError, match="nombre del evento es obligatorio"):
        EventCreate(**valid_event_payload(name="   "))


def test_service_accepts_undefined_dates():
    service = EventCreate(
        **valid_event_payload(
            event_type="service",
            start_datetime=None,
            end_datetime=None,
        )
    )

    assert service.start_datetime is None
    assert service.end_datetime is None


@pytest.mark.parametrize("modality", ["presencial", "virtual", "hibrido"])
def test_event_accepts_supported_modalities(modality):
    event = EventCreate(**valid_event_payload(modality=modality))

    assert event.modality == modality


@pytest.mark.parametrize("event_type", ["event", "service"])
def test_event_accepts_supported_event_types(event_type):
    event = EventCreate(**valid_event_payload(event_type=event_type))

    assert event.event_type == event_type


def test_service_rejects_end_datetime_without_start_datetime():
    with pytest.raises(ValidationError, match="fecha de inicio es obligatoria"):
        EventCreate(
            **valid_event_payload(
                event_type="service",
                start_datetime=None,
                end_datetime=future_datetime(),
            )
        )


def test_event_rejects_past_start_datetime():
    with pytest.raises(ValidationError, match="fecha de inicio debe ser futura"):
        EventCreate(
            **valid_event_payload(
                start_datetime=datetime.now(timezone.utc) - timedelta(hours=1)
            )
        )


def test_event_rejects_end_datetime_before_start_datetime():
    start = future_datetime(hours=4)
    end = future_datetime(hours=2)

    with pytest.raises(ValidationError, match="fecha de fin debe ser posterior"):
        EventCreate(**valid_event_payload(start_datetime=start, end_datetime=end))


def test_event_rejects_end_datetime_equal_to_start_datetime():
    start = future_datetime(hours=2)

    with pytest.raises(ValidationError, match="fecha de fin debe ser posterior"):
        EventCreate(**valid_event_payload(start_datetime=start, end_datetime=start))


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("event_type", "conference", "tipo debe ser"),
        ("modality", "mixta", "modalidad debe ser"),
        ("image_url", "ftp://image.test/banner.png", "imagen debe ser una URL"),
    ],
)
def test_event_rejects_unsupported_catalog_values(field, value, expected_message):
    with pytest.raises(ValidationError, match=expected_message):
        EventCreate(**valid_event_payload(**{field: value}))


def test_event_accepts_https_image_url_and_ignores_blank_image_url():
    event_with_image = EventCreate(
        **valid_event_payload(image_url=" https://example.com/banner.png ")
    )
    event_without_image = EventCreate(**valid_event_payload(image_url="   "))

    assert event_with_image.image_url == "https://example.com/banner.png"
    assert event_without_image.image_url is None


def test_event_rejects_zero_capacity_boundary():
    with pytest.raises(ValidationError):
        EventCreate(**valid_event_payload(total_capacity=0))


def test_event_accepts_one_as_minimum_capacity_boundary():
    event = EventCreate(**valid_event_payload(total_capacity=1))

    assert event.total_capacity == 1


def test_event_update_rejects_invalid_status():
    with pytest.raises(ValidationError, match="Estado de evento inválido"):
        EventUpdate(**valid_event_payload(status="archived"))


@pytest.mark.parametrize("status", ["available", "sold_out", "finished", "cancelled"])
def test_event_update_accepts_supported_statuses(status):
    event = EventUpdate(**valid_event_payload(status=status))

    assert event.status == status


def test_ensure_aware_datetime_adds_timezone_to_naive_values():
    naive_datetime = datetime(2026, 6, 13, 10, 30)

    aware_datetime = ensure_aware_datetime(naive_datetime)

    assert aware_datetime.tzinfo is not None
    assert aware_datetime.replace(tzinfo=None) == naive_datetime


def test_ensure_aware_datetime_preserves_timezone_aware_values():
    aware_datetime = datetime(2026, 6, 13, 10, 30, tzinfo=timezone.utc)

    result = ensure_aware_datetime(aware_datetime)

    assert result is aware_datetime

import pytest
from pydantic import ValidationError

from app.routers.reservations import mask_card
from app.schemas import PaymentCreate, ReservationCreate


def test_payment_requires_holder_name():
    with pytest.raises(ValidationError, match="nombre del titular es obligatorio"):
        PaymentCreate(holder_name="   ")


def test_payment_normalizes_holder_name_whitespace():
    payment = PaymentCreate(holder_name="  Buyer Name  ")

    assert payment.holder_name == "Buyer Name"


def test_payment_uses_approved_as_default_result():
    payment = PaymentCreate(holder_name="Buyer")

    assert payment.result == "approved"


@pytest.mark.parametrize("result", ["approved", "rejected"])
def test_payment_accepts_supported_simulation_results(result):
    payment = PaymentCreate(holder_name="Buyer", result=result)

    assert payment.result == result


@pytest.mark.parametrize("result", ["pending", "APPROVED", "", "failed"])
def test_payment_rejects_unknown_simulation_result(result):
    with pytest.raises(ValidationError, match="approved o rejected"):
        PaymentCreate(holder_name="Buyer", result=result)


@pytest.mark.parametrize("quantity", [0, -1, -100])
def test_reservation_rejects_non_positive_quantity(quantity):
    with pytest.raises(ValidationError):
        ReservationCreate(event_id=1, quantity=quantity)


def test_reservation_accepts_positive_quantity():
    reservation = ReservationCreate(event_id=1, quantity=2)

    assert reservation.quantity == 2


def test_reservation_accepts_one_as_minimum_valid_quantity():
    reservation = ReservationCreate(event_id=1, quantity=1)

    assert reservation.quantity == 1


@pytest.mark.parametrize("event_id", [0, -1])
def test_reservation_rejects_non_positive_event_id(event_id):
    with pytest.raises(ValidationError):
        ReservationCreate(event_id=event_id, quantity=1)


@pytest.mark.parametrize(
    ("card_number", "expected_mask"),
    [
        (None, "simulated"),
        ("", "simulated"),
        ("123", "simulated"),
        ("abcd4242", "**** **** **** 4242"),
        ("4242", "**** **** **** 4242"),
        ("4242 4242 4242 4242", "**** **** **** 4242"),
        ("4000-0000-0000-0002", "**** **** **** 0002"),
    ],
)
def test_mask_card_returns_safe_card_representation(card_number, expected_mask):
    assert mask_card(card_number) == expected_mask

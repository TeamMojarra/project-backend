from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from jose import jwt
from pydantic import ValidationError

from app.schemas import (
    PasswordChange,
    UserLogin,
    UserRegister,
    UserUpdate,
    validate_password_strength,
)
from app.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)


@pytest.mark.parametrize(
    "password",
    [
        "Aa123456",
        "StrongPass1",
        "Reservent2026",
        "A1bcdefg",
        "LongPassword123456789",
    ],
)
def test_password_strength_accepts_valid_boundary_passwords(password):
    validate_password_strength(password)


@pytest.mark.parametrize(
    ("password", "expected_message"),
    [
        ("Short1", "al menos 8 caracteres"),
        ("Password 1", "no debe incluir espacios"),
        ("Password\t1", "no debe incluir espacios"),
        ("Password\n1", "no debe incluir espacios"),
        ("lowercase1", "mayúscula"),
        ("UPPERCASE1", "minúscula"),
        ("NoNumbers", "número"),
    ],
)
def test_password_strength_rejects_weak_passwords(password, expected_message):
    with pytest.raises(ValueError, match=expected_message):
        validate_password_strength(password)


def test_user_registration_normalizes_name_whitespace():
    payload = UserRegister(
        name="  Francisco Miranda  ",
        email="francisco@example.com",
        password="Password1",
        confirm_password="Password1",
    )

    assert payload.name == "Francisco Miranda"


def test_user_registration_rejects_short_name_boundary():
    with pytest.raises(
        ValidationError, match="nombre debe tener al menos 2 caracteres"
    ):
        UserRegister(
            name="F",
            email="francisco@example.com",
            password="Password1",
            confirm_password="Password1",
        )


def test_user_registration_rejects_invalid_email_format():
    with pytest.raises(ValidationError):
        UserRegister(
            name="Francisco Miranda",
            email="not-an-email",
            password="Password1",
            confirm_password="Password1",
        )


@pytest.mark.parametrize(
    "email", ["francisco@example.com", "f.miranda+test@unal.edu.co"]
)
def test_user_registration_accepts_valid_email_formats(email):
    payload = UserRegister(
        name="Francisco Miranda",
        email=email,
        password="Password1",
        confirm_password="Password1",
    )

    assert str(payload.email) == email


def test_user_registration_rejects_mismatched_password_confirmation():
    with pytest.raises(ValidationError, match="Las contraseñas no coinciden"):
        UserRegister(
            name="Francisco Miranda",
            email="francisco@example.com",
            password="Password1",
            confirm_password="Password2",
        )


def test_user_login_rejects_blank_password():
    with pytest.raises(ValidationError, match="contraseña es obligatoria"):
        UserLogin(email="francisco@example.com", password="   ")


def test_user_update_rejects_name_over_maximum_boundary():
    with pytest.raises(ValidationError, match="entre 2 y 100 caracteres"):
        UserUpdate(name="A" * 101, email="francisco@example.com")


def test_password_change_rejects_confirmation_mismatch():
    with pytest.raises(ValidationError, match="Las contraseñas no coinciden"):
        PasswordChange(
            current_password="OldPass1",
            new_password="NewPass1",
            confirm_password="OtherPass1",
        )


def test_access_token_contains_identity_claims_and_expiration():
    user = SimpleNamespace(id=42, email="owner@example.com", role="user")

    token = create_access_token(user)
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == "42"
    assert payload["email"] == "owner@example.com"
    assert payload["role"] == "user"
    assert datetime.fromtimestamp(payload["exp"], tz=timezone.utc) > datetime.now(
        timezone.utc
    )


def test_password_hash_verification_accepts_only_original_password():
    password_hash = hash_password("StrongPass1")

    assert password_hash != "StrongPass1"
    assert verify_password("StrongPass1", password_hash) is True
    assert verify_password("WrongPass1", password_hash) is False

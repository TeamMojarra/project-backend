import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        validate_password_strength(value)
        return value

    @field_validator("confirm_password")
    @classmethod
    def validate_password_confirmation(cls, value, info):
        if value != info.data.get("password"):
            raise ValueError("Las contraseñas no coinciden")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_required_password(cls, value):
        if not value.strip():
            raise ValueError("La contraseña es obligatoria")
        return value


class UserUpdate(BaseModel):
    name: str
    email: EmailStr

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()
        if len(value) < 2 or len(value) > 100:
            raise ValueError("El nombre debe tener entre 2 y 100 caracteres")
        return value


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value):
        validate_password_strength(value)
        return value

    @field_validator("confirm_password")
    @classmethod
    def validate_password_confirmation(cls, value, info):
        if value != info.data.get("new_password"):
            raise ValueError("Las contraseñas no coinciden")
        return value


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class EventCreate(BaseModel):
    name: str
    description: Optional[str] = None
    event_type: str = "event"
    modality: str = "presencial"
    location: Optional[str] = None
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    total_capacity: int = Field(..., gt=0)

    @field_validator("name")
    @classmethod
    def validate_event_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("El nombre del evento es obligatorio")
        return value

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value):
        if value not in {"event", "service"}:
            raise ValueError("El tipo debe ser 'event' o 'service'")
        return value

    @field_validator("modality")
    @classmethod
    def validate_modality(cls, value):
        if value not in {"presencial", "virtual", "hibrido"}:
            raise ValueError("La modalidad debe ser presencial, virtual o hibrido")
        return value


class EventUpdate(EventCreate):
    status: str = "available"

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value not in {"available", "sold_out", "finished", "cancelled"}:
            raise ValueError("Estado de evento inválido")
        return value


class EventResponse(BaseModel):
    id: int
    created_by: int
    name: str
    description: Optional[str]
    event_type: str
    modality: str
    location: Optional[str]
    start_datetime: datetime
    end_datetime: Optional[datetime]
    total_capacity: int
    available_capacity: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    updated_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class ReservationCreate(BaseModel):
    event_id: int
    quantity: int = Field(..., gt=0)


class ReservationResponse(BaseModel):
    id: int
    user_id: int
    event_id: int
    quantity: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    event: Optional[EventResponse] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    holder_name: str
    card_number: Optional[str] = None

    @field_validator("holder_name")
    @classmethod
    def validate_holder_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("El nombre del titular es obligatorio")
        return value


class PaymentResponse(BaseModel):
    id: int
    reservation_id: int
    holder_name: str
    masked_card_number: str
    amount: float
    result: str
    processed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketResponse(BaseModel):
    id: int
    reservation_id: int
    ticket_code: str
    qr_code_url: Optional[str]
    status: str
    generated_at: datetime
    used_at: Optional[datetime]
    user_id: int
    event: Optional[EventResponse] = None

    model_config = ConfigDict(from_attributes=True)


class CheckoutResponse(BaseModel):
    payment: PaymentResponse
    reservation: ReservationResponse
    ticket: TicketResponse
    message: str


class TicketValidationResponse(BaseModel):
    valid: bool
    status: str
    message: str
    ticket: Optional[TicketResponse] = None


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    message: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def validate_password_strength(value: str):
    if len(value) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    if not re.search(r"[A-Z]", value):
        raise ValueError("La contraseña debe incluir una mayúscula")
    if not re.search(r"[a-z]", value):
        raise ValueError("La contraseña debe incluir una minúscula")
    if not re.search(r"[0-9]", value):
        raise ValueError("La contraseña debe incluir un número")

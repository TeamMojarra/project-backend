import re
from datetime import date, datetime, time
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


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
    image_url: Optional[str] = None
    event_type: str = "event"
    modality: str = "presencial"
    location: Optional[str] = None
    price: float = Field(0.0, ge=0)
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    total_capacity: int = Field(..., gt=0)
    max_tickets_per_purchase: int = Field(1, gt=0)

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

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            return None
        if not value.startswith(("http://", "https://")):
            raise ValueError("La imagen debe ser una URL http o https")
        return value

    @field_validator("modality")
    @classmethod
    def validate_modality(cls, value):
        if value not in {"presencial", "virtual", "hibrido"}:
            raise ValueError("La modalidad debe ser presencial, virtual o hibrido")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if self.max_tickets_per_purchase > self.total_capacity:
            raise ValueError("El limite por compra no puede superar la capacidad")
        if self.event_type == "event" and not self.start_datetime:
            raise ValueError("La fecha de inicio es obligatoria para eventos")
        if self.end_datetime and not self.start_datetime:
            raise ValueError(
                "La fecha de inicio es obligatoria si se define una fecha de fin"
            )
        if not self.start_datetime:
            return self

        start_datetime = ensure_aware_datetime(self.start_datetime)
        if start_datetime <= datetime.now(start_datetime.tzinfo):
            raise ValueError("La fecha de inicio debe ser futura")
        if self.end_datetime:
            end_datetime = ensure_aware_datetime(self.end_datetime)
            if end_datetime <= start_datetime:
                raise ValueError("La fecha de fin debe ser posterior al inicio")
        return self


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
    image_url: Optional[str]
    event_type: str
    modality: str
    location: Optional[str]
    price: float
    start_datetime: Optional[datetime]
    end_datetime: Optional[datetime]
    total_capacity: int
    available_capacity: int
    max_tickets_per_purchase: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    updated_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class ReservationCreate(BaseModel):
    event_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    service_slot_id: Optional[int] = Field(None, gt=0)


class ServiceSlotResponse(BaseModel):
    id: int
    event_id: int
    starts_at: datetime
    ends_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class ServiceSlotGenerate(BaseModel):
    start_date: date
    end_date: date
    weekdays: list[int]
    start_time: time
    end_time: time
    slot_minutes: int = Field(30, ge=15, le=480)

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.end_date < self.start_date:
            raise ValueError("La fecha final debe ser igual o posterior a la inicial")
        if self.end_time <= self.start_time:
            raise ValueError("La hora final debe ser posterior a la inicial")
        if not self.weekdays:
            raise ValueError("Selecciona al menos un dia de atencion")
        invalid_days = [day for day in self.weekdays if day < 0 or day > 6]
        if invalid_days:
            raise ValueError("Los dias deben estar entre 0 y 6")
        return self


class ReservationResponse(BaseModel):
    id: int
    user_id: int
    event_id: int
    quantity: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    event: Optional[EventResponse] = None
    service_slot: Optional[ServiceSlotResponse] = None
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    holder_name: str
    card_number: Optional[str] = None
    expiry_date: Optional[str] = None
    cvc: Optional[str] = None
    result: str = "approved"

    @field_validator("holder_name")
    @classmethod
    def validate_holder_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("El nombre del titular es obligatorio")
        return value

    @field_validator("result")
    @classmethod
    def validate_result(cls, value):
        if value not in {"approved", "rejected"}:
            raise ValueError("El resultado del pago debe ser approved o rejected")
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
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


class CheckoutResponse(BaseModel):
    payment: PaymentResponse
    reservation: ReservationResponse
    ticket: Optional[TicketResponse]
    tickets: list[TicketResponse] = Field(default_factory=list)
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
    if re.search(r"\s", value):
        raise ValueError("La contraseña no debe incluir espacios")
    if not re.search(r"[A-Z]", value):
        raise ValueError("La contraseña debe incluir una mayúscula")
    if not re.search(r"[a-z]", value):
        raise ValueError("La contraseña debe incluir una minúscula")
    if not re.search(r"[0-9]", value):
        raise ValueError("La contraseña debe incluir un número")


def ensure_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value

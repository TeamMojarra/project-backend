import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


# ============================================================
# Schemas de entrada (Request)
# ============================================================

class UserRegister(BaseModel):
    """
    Schema de registro de usuario (RF_01).
    Valida correo, fuerza de contraseña y coincidencia de contraseñas
    según el flujo del caso de uso CU_01.
    """
    email: EmailStr
    password: str
    confirm_password: str
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("El nombre completo es obligatorio")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        """
        Valida requisitos de seguridad de la contraseña (CU_01, paso 10):
        - Mínimo 8 caracteres
        - Al menos una mayúscula
        - Al menos una minúscula
        - Al menos un número
        """
        if len(v) < 8:
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres"
            )
        if not re.search(r"[A-Z]", v):
            raise ValueError(
                "La contraseña debe incluir al menos una letra mayúscula"
            )
        if not re.search(r"[a-z]", v):
            raise ValueError(
                "La contraseña debe incluir al menos una letra minúscula"
            )
        if not re.search(r"[0-9]", v):
            raise ValueError(
                "La contraseña debe incluir al menos un número"
            )
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        """
        Verifica que las contraseñas coincidan (CU_01, paso 12).
        """
        password = info.data.get("password")
        if password and v != password:
            raise ValueError("Las contraseñas no coinciden")
        return v


class UserLogin(BaseModel):
    """
    Schema de inicio de sesión (RF_02).
    Valida que los campos no estén vacíos y que el correo tenga formato válido.
    """
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("La contraseña es obligatoria")
        return v


# ============================================================
# Schemas de salida (Response)
# ============================================================

class UserResponse(BaseModel):
    """
    Schema de respuesta del usuario (sin datos sensibles).
    Campos alineados con la tabla 'users' de reservent-db.sql.
    """
    id: int
    email: str
    name: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """
    Schema de respuesta del token JWT (RF_02).
    """
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    """
    Schema genérico para mensajes del sistema.
    """
    message: str
    detail: Optional[str] = None

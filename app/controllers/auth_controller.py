from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_database
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    MessageResponse,
)
from app.services.auth_service import register_user, login_user
from app.utils.security import get_current_user
from app.models.user import User


router = APIRouter(
    prefix="/api/auth",
    tags=["Autenticación - Módulo 1"]
)


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario (RF_01)",
    description="Permite que un usuario visitante cree una nueva cuenta en Reservent. "
                "Valida correo único, formato de email, fuerza de contraseña y "
                "coincidencia de contraseñas según CU_01."
)
def register(user_data: UserRegister, database: Session = Depends(get_database)):
    """
    Endpoint de registro de usuario (RF_01 / CU_01).

    Validaciones realizadas:
    - Campos vacíos (Pydantic)
    - Formato de correo electrónico (EmailStr)
    - Fuerza de contraseña: mínimo 8 caracteres, mayúsculas, minúsculas, números
    - Coincidencia de contraseñas
    - Correo electrónico no duplicado (servicio)

    Retorna mensaje de confirmación y redirige al login (CU_01, paso 16-17).
    """
    new_user = register_user(
        database=database,
        email=user_data.email,
        password=user_data.password,
        name=user_data.name
    )

    return MessageResponse(
        message="Registro exitoso. Ya puede iniciar sesión.",
        detail=f"Usuario registrado con correo: {new_user.email}"
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión (RF_02)",
    description="Permite que un usuario registrado inicie sesión con correo y contraseña. "
                "Retorna un token JWT para acceso autenticado según CU_02."
)
def login(user_data: UserLogin, database: Session = Depends(get_database)):
    """
    Endpoint de inicio de sesión (RF_02 / CU_02).

    Validaciones realizadas:
    - Campos vacíos (Pydantic)
    - Formato de correo electrónico (EmailStr)
    - Credenciales contra la base de datos (servicio)
    - Mensaje genérico si las credenciales son incorrectas

    Retorna token JWT y datos del usuario autenticado.
    """
    access_token, user = login_user(
        database=database,
        email=user_data.email,
        password=user_data.password
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener usuario actual",
    description="Retorna la información del usuario autenticado. "
                "Requiere un token JWT válido en el header Authorization."
)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Endpoint protegido que retorna los datos del usuario autenticado.
    Verifica que el token JWT sea válido y que el usuario exista.
    """
    return UserResponse.model_validate(current_user)

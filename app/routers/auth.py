import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_database
from app.email import send_registration_confirmation
from app.models import User
from app.schemas import MessageResponse, PasswordChange, TokenResponse, UserLogin, UserRegister, UserResponse, UserUpdate
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, database: Session = Depends(get_database)):
    existing_user = database.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo ya está registrado")

    user = User(
        name=payload.name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role="user",
    )
    database.add(user)
    database.commit()

    try:
        send_registration_confirmation(user.email, user.name)
    except Exception as exc:
        logger.warning("No se pudo enviar confirmación de registro: %s", exc)

    return MessageResponse(message="Registro exitoso. Ya puede iniciar sesión.")


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, database: Session = Depends(get_database)):
    user = database.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_access_token(user), user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    duplicate = (
        database.query(User)
        .filter(func.lower(User.email) == payload.email.lower(), User.id != current_user.id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este correo ya está registrado")

    current_user.name = payload.name
    current_user.email = payload.email.lower()
    current_user.updated_at = datetime.now(timezone.utc)
    database.commit()
    database.refresh(current_user)
    return current_user


@router.put("/password", response_model=MessageResponse)
@router.post("/password", response_model=MessageResponse)
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_database),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual es incorrecta")
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La nueva contraseña debe ser diferente")

    current_user.password_hash = hash_password(payload.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    database.commit()
    return MessageResponse(message="Contraseña actualizada correctamente")

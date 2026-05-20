import os
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_database
from app.repositories.user_repository import get_user_by_id

# Cargar variables de entorno
load_dotenv()

# ============================================================
# Configuración
# ============================================================

SECRET_KEY = os.getenv("SECRET_KEY", "reservent_secret_key_dev_2024_change_in_production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ============================================================
# OAuth2 Bearer Token
# ============================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ============================================================
# Funciones de hashing de contraseñas (RNF_01)
# ============================================================

def hash_password(password: str) -> str:
    """
    Genera un hash bcrypt de la contraseña (RNF_01).
    El sistema no almacena contraseñas en texto plano.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una contraseña contra su hash bcrypt (CU_02, paso 12).
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ============================================================
# Funciones de JWT
# ============================================================

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """
    Genera un token JWT con los datos del usuario y tiempo de expiración.
    La sesión tiene un tiempo de expiración por seguridad (CU_02, notas).
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def verify_access_token(token: str) -> dict:
    """
    Decodifica y valida un token JWT.
    Retorna el payload si es válido, o lanza excepción si ha expirado o es inválido.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================
# Dependencia: obtener usuario actual desde JWT
# ============================================================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    database: Session = Depends(get_database)
):
    """
    Dependencia de FastAPI que extrae el usuario actual del token JWT.
    Se usa para proteger endpoints que requieren autenticación.
    """
    payload = verify_access_token(token)
    user_id = payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: no contiene identificador de usuario",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(database, int(user_id))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

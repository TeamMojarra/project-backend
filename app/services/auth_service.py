from datetime import datetime, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.repositories.user_repository import get_user_by_email, create_user
from app.utils.security import hash_password, verify_password, create_access_token


def register_user(database: Session, email: str, password: str, name: str):
    """
    Servicio de registro de usuario (RF_01 / CU_01).

    Flujo:
    1. Verifica que el correo no exista previamente (CU_01, paso 6-7).
    2. Hashea la contraseña con bcrypt (CU_01, paso 15 / RNF_01).
    3. Crea el usuario con rol 'user' (CU_01, paso 14).
    4. Retorna el usuario creado.

    Las validaciones de formato de correo, fuerza de contraseña y coincidencia
    de contraseñas se realizan en la capa de schemas (Pydantic).
    """
    # Verificar correo único (CU_01, paso 6)
    existing_user = get_user_by_email(database, email)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo electrónico ya está registrado. "
                   "Puede usar la opción de recuperar contraseña."
        )

    # Hashear contraseña (CU_01, paso 15 / RNF_01)
    hashed = hash_password(password)

    # Crear usuario (CU_01, paso 14)
    new_user = create_user(
        database=database,
        email=email,
        password_hash=hashed,
        name=name
    )

    # Log de registro (CU_01, postcondiciones)
    print(f"[LOG] Usuario registrado: {email} | ID: {new_user.id} | "
          f"Fecha: {datetime.now(timezone.utc).isoformat()}")

    return new_user


def login_user(database: Session, email: str, password: str):
    """
    Servicio de inicio de sesión autenticado (RF_02 / CU_02).

    Flujo:
    1. Busca usuario por correo electrónico (CU_02, paso 11).
    2. Compara la contraseña ingresada con el hash almacenado (CU_02, paso 12).
    3. Si las credenciales son correctas, genera un token JWT (CU_02, paso 13).
    4. Si son incorrectas, muestra mensaje genérico (CU_02, paso 16).

    El mensaje de error es genérico para no revelar si el correo existe o no
    en el sistema (CU_02, notas de seguridad).
    """
    # Mensaje genérico de error (CU_02, paso 16)
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Correo electrónico o contraseña incorrectos",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Buscar usuario por correo (CU_02, paso 11)
    user = get_user_by_email(database, email)

    if not user:
        # No revelamos que el correo no existe (CU_02, notas)
        raise credentials_error

    # Verificar contraseña contra hash (CU_02, paso 12)
    if not verify_password(password, user.password_hash):
        # Log de intento fallido (CU_02, postcondiciones)
        print(f"[LOG] Intento de login fallido: {email} | "
              f"Fecha: {datetime.now(timezone.utc).isoformat()}")
        raise credentials_error

    # Crear token JWT (CU_02, paso 13)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role}
    )

    # Log de inicio de sesión exitoso (CU_02, paso 14)
    print(f"[LOG] Inicio de sesión exitoso: {email} | ID: {user.id} | "
          f"Fecha: {datetime.now(timezone.utc).isoformat()}")

    return access_token, user

"""
Tests automatizados para RF_01 (Registro de usuarios) y RF_02 (Inicio de sesión).

Estos tests validan los flujos completos descritos en los casos de uso
CU_01 y CU_02, incluyendo validaciones de datos, manejo de errores
y autenticación con JWT.

Se usa una base de datos SQLite en memoria para aislar los tests
del entorno de producción (PostgreSQL).
"""

import sys
from pathlib import Path

# Asegurar que el paquete app sea accesible
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_database
from app.models.user import User  # Importar para registrar el modelo
from app.main import app

# ============================================================
# Configuración de base de datos de prueba (SQLite en memoria)
# ============================================================

SQLALCHEMY_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)

# Crear tablas en la base de datos de prueba usando los modelos de SQLAlchemy
Base.metadata.create_all(bind=test_engine)


def override_get_database():
    database = TestingSessionLocal()
    try:
        yield database
    finally:
        database.close()


# Inyectar la base de datos de prueba
app.dependency_overrides[get_database] = override_get_database

client = TestClient(app)

# ============================================================
# Datos de prueba (campos alineados con reservent-db.sql)
# ============================================================

VALID_USER = {
    "email": "layo.moreno@unal.edu.co",
    "password": "Reservent2024",
    "confirm_password": "Reservent2024",
    "name": "Layo Andrés Moreno Cortés"
}

SECOND_USER = {
    "email": "juan.rodriguez@unal.edu.co",
    "password": "Password123",
    "confirm_password": "Password123",
    "name": "Juan Pablo Rodríguez Cruz"
}


# ============================================================
# Tests del endpoint raíz
# ============================================================

class TestRootEndpoint:

    def test_root_returns_200(self):
        """Verifica que el endpoint raíz responda correctamente."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["message"] == "API Reservent funcionando correctamente"


# ============================================================
# Tests de RF_01 - Registro de usuarios (CU_01)
# ============================================================

class TestRegister:

    def test_register_successful(self):
        """
        CU_01 - Flujo normal completo:
        Registro exitoso con datos válidos.
        """
        response = client.post("/api/auth/register", json=VALID_USER)
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Registro exitoso. Ya puede iniciar sesión."
        assert VALID_USER["email"] in data["detail"]

    def test_register_duplicate_email(self):
        """
        CU_01 - Paso 7:
        El correo electrónico ya está registrado → error 409.
        """
        response = client.post("/api/auth/register", json=VALID_USER)
        assert response.status_code == 409
        assert "ya está registrado" in response.json()["detail"]

    def test_register_weak_password_no_uppercase(self):
        """
        CU_01 - Paso 10-11:
        Contraseña sin mayúsculas → error de validación.
        """
        user = {**VALID_USER, "email": "test1@test.com",
                "password": "password123", "confirm_password": "password123"}
        response = client.post("/api/auth/register", json=user)
        assert response.status_code == 422

    def test_register_weak_password_no_lowercase(self):
        """
        CU_01 - Paso 10-11:
        Contraseña sin minúsculas → error de validación.
        """
        user = {**VALID_USER, "email": "test2@test.com",
                "password": "PASSWORD123", "confirm_password": "PASSWORD123"}
        response = client.post("/api/auth/register", json=user)
        assert response.status_code == 422

    def test_register_weak_password_no_numbers(self):
        """
        CU_01 - Paso 10-11:
        Contraseña sin números → error de validación.
        """
        user = {**VALID_USER, "email": "test3@test.com",
                "password": "PasswordABC", "confirm_password": "PasswordABC"}
        response = client.post("/api/auth/register", json=user)
        assert response.status_code == 422

    def test_register_weak_password_too_short(self):
        """
        CU_01 - Paso 10-11:
        Contraseña menor a 8 caracteres → error de validación.
        """
        user = {**VALID_USER, "email": "test4@test.com",
                "password": "Pass1", "confirm_password": "Pass1"}
        response = client.post("/api/auth/register", json=user)
        assert response.status_code == 422

    def test_register_passwords_mismatch(self):
        """
        CU_01 - Paso 12-13:
        Las contraseñas no coinciden → error de validación.
        """
        user = {**VALID_USER, "email": "test5@test.com",
                "confirm_password": "OtraPassword1"}
        response = client.post("/api/auth/register", json=user)
        assert response.status_code == 422

    def test_register_invalid_email_format(self):
        """
        CU_01 - Paso 8-9:
        Formato de correo inválido → error de validación.
        """
        user = {**VALID_USER, "email": "correo-sin-arroba"}
        response = client.post("/api/auth/register", json=user)
        assert response.status_code == 422

    def test_register_empty_name(self):
        """
        CU_01 - Paso 4-5:
        Nombre completo vacío → error de validación.
        """
        user = {**VALID_USER, "email": "test6@test.com", "name": "   "}
        response = client.post("/api/auth/register", json=user)
        assert response.status_code == 422

    def test_register_missing_fields(self):
        """
        CU_01 - Paso 4-5:
        Campos obligatorios faltantes → error de validación.
        """
        response = client.post("/api/auth/register", json={"email": "test@test.com"})
        assert response.status_code == 422


# ============================================================
# Tests de RF_02 - Inicio de sesión (CU_02)
# ============================================================

class TestLogin:

    def test_login_successful(self):
        """
        CU_02 - Flujo normal completo:
        Login exitoso con credenciales válidas → token JWT.
        """
        response = client.post("/api/auth/login", json={
            "email": VALID_USER["email"],
            "password": VALID_USER["password"]
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == VALID_USER["email"]
        assert data["user"]["name"] == VALID_USER["name"]
        assert data["user"]["role"] == "user"

    def test_login_wrong_password(self):
        """
        CU_02 - Paso 16:
        Contraseña incorrecta → mensaje genérico sin revelar si el correo existe.
        """
        response = client.post("/api/auth/login", json={
            "email": VALID_USER["email"],
            "password": "ContraseñaIncorrecta1"
        })
        assert response.status_code == 401
        assert response.json()["detail"] == "Correo electrónico o contraseña incorrectos"

    def test_login_nonexistent_email(self):
        """
        CU_02 - Paso 16 (notas de seguridad):
        Correo no registrado → mismo mensaje genérico (no revelar existencia).
        """
        response = client.post("/api/auth/login", json={
            "email": "noexiste@test.com",
            "password": "Password123"
        })
        assert response.status_code == 401
        assert response.json()["detail"] == "Correo electrónico o contraseña incorrectos"

    def test_login_invalid_email_format(self):
        """
        CU_02 - Paso 9-10:
        Formato de correo inválido → error de validación.
        """
        response = client.post("/api/auth/login", json={
            "email": "correo-invalido",
            "password": "Password123"
        })
        assert response.status_code == 422

    def test_login_empty_password(self):
        """
        CU_02 - Paso 7-8:
        Contraseña vacía → error de validación.
        """
        response = client.post("/api/auth/login", json={
            "email": VALID_USER["email"],
            "password": ""
        })
        assert response.status_code == 422

    def test_login_returns_valid_jwt(self):
        """
        CU_02 - Paso 13:
        El token JWT retornado permite acceder a endpoints protegidos.
        """
        # Login
        login_response = client.post("/api/auth/login", json={
            "email": VALID_USER["email"],
            "password": VALID_USER["password"]
        })
        token = login_response.json()["access_token"]

        # Acceder a endpoint protegido
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == VALID_USER["email"]


# ============================================================
# Tests del endpoint protegido /me
# ============================================================

class TestProtectedEndpoint:

    def test_me_without_token(self):
        """
        Acceder a /me sin token → error 401.
        """
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token(self):
        """
        Acceder a /me con token inválido → error 401.
        """
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer token_invalido_123"}
        )
        assert response.status_code == 401

    def test_me_returns_user_data(self):
        """
        Acceder a /me con token válido → datos del usuario.
        """
        # Registrar segundo usuario
        client.post("/api/auth/register", json=SECOND_USER)

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": SECOND_USER["email"],
            "password": SECOND_USER["password"]
        })
        token = login_response.json()["access_token"]

        # Obtener datos del usuario
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        data = me_response.json()
        assert data["email"] == SECOND_USER["email"]
        assert data["name"] == SECOND_USER["name"]
        assert data["role"] == "user"
        assert "id" in data
        assert "created_at" in data

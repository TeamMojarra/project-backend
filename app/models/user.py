from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime

from app.database import Base


class User(Base):
    """
    Entidad User - Módulo 1: Gestión de usuarios.

    Almacena la información de cada usuario registrado en el sistema Reservent.
    El correo electrónico es el identificador único del usuario (RF_01).
    La contraseña se almacena con hash bcrypt (RNF_01).

    Esquema definido en reservent-db.sql por el equipo.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="user")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"

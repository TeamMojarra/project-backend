import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Cargar variables de entorno desde .env
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://reservent:pass1234@localhost:5432/reservent_db"
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_database():
    """
    Generador de sesiones de base de datos.
    Se usa como dependencia en los controladores de FastAPI.
    """
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()

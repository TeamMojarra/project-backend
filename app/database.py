import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://reservent:pass1234@127.0.0.1:5433/reservent_db",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

_database_ready = False


def ensure_database():
    global _database_ready

    if _database_ready:
        return

    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _database_ready = True


def get_database():
    ensure_database()
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()


get_db = get_database

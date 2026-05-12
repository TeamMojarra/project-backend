from sqlalchemy.orm import Session
from app.models import Greeting


def get_first_greeting(database: Session):
    return database.query(Greeting).first()


def create_greeting(database: Session, content: str):
    greeting = Greeting(content=content)

    database.add(greeting)
    database.commit()
    database.refresh(greeting)

    return greeting
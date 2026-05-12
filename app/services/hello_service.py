from sqlalchemy.orm import Session
from app.repositories.hello_repository import get_first_greeting, create_greeting


def get_hello_message(database: Session):
    greeting = get_first_greeting(database)

    if greeting is None:
        greeting = create_greeting(
            database,
            "Primer saludo guardado en la base de datos"
        )

    return {
        "message": "Hola Mundo desde FastAPI",
        "database_status": "connected",
        "entity": {
            "id": greeting.id,
            "content": greeting.content
        }
    }
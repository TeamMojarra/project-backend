from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_database
from app.services.hello_service import get_hello_message

router = APIRouter(
    prefix="/api",
    tags=["Hola Mundo"]
)


@router.get("/hello")
def hello_world(database: Session = Depends(get_database)):
    return get_hello_message(database)
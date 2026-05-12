from fastapi import FastAPI
from app.database import Base, engine
from app.controllers.hello_controller import router as hello_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Reservent API",
    description="Backend inicial del proyecto Reservent con FastAPI y PostgreSQL",
    version="1.0.0"
)

app.include_router(hello_router)


@app.get("/")
def root():
    return {
        "message": "API Reservent funcionando correctamente"
    }
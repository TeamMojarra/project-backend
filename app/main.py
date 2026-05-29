from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, events, notifications, reservations, tickets

app = FastAPI(
    title="Reservent API",
    description="API de reservas, eventos y tickets digitales.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(reservations.router)
app.include_router(tickets.router)
app.include_router(notifications.router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "API Reservent funcionando correctamente", "docs": "/docs"}

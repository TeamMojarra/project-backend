import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine
from app.controllers.auth_controller import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Evento de inicio de la aplicación.
    Ejecuta el script SQL del equipo (reservent-db.sql) para crear las tablas
    si no existen. Esto garantiza compatibilidad con el esquema definido
    por el equipo en el repositorio.
    """
    sql_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reservent-db.sql")

    with engine.connect() as conn:
        # Verificar si las tablas ya existen
        result = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')"
        ))
        tables_exist = result.scalar()

        if not tables_exist:
            # Ejecutar el SQL del equipo para crear todas las tablas
            with open(sql_path, "r") as f:
                sql_script = f.read()

            # Ejecutar cada statement por separado
            for statement in sql_script.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))

            conn.commit()
            print("[DB] Tablas creadas desde reservent-db.sql")
        else:
            print("[DB] Tablas ya existen, omitiendo creación")

    yield


app = FastAPI(
    title="Reservent API",
    description="Backend del proyecto Reservent - Sistema de reservas de eventos "
                "con tickets digitales. Universidad Nacional de Colombia.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar controladores (routers)
app.include_router(auth_router)


@app.get("/", tags=["Root"])
def root():
    """Endpoint raíz que confirma que la API está funcionando."""
    return {
        "message": "API Reservent funcionando correctamente",
        "version": "1.0.0",
        "docs": "/docs"
    }

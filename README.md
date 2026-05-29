# Reservent - Backend

Backend del proyecto Reservent. Este repositorio contiene la API construida con FastAPI, SQLAlchemy ORM y PostgreSQL.

Incluye autenticacion con JWT, gestion de eventos, reservas, pagos simulados, tickets digitales y notificaciones basicas.

## Requisitos

- Python 3.11 o superior
- Docker y Docker Compose

## Inicializacion rapida

Clona el repositorio y ejecuta el script de configuracion segun tu sistema operativo:

### Linux / macOS

```bash
bash setup.sh
```

### Windows

```bat
setup.bat
```

El script crea el entorno virtual, instala las dependencias, levanta PostgreSQL con Docker, ejecuta las pruebas e inicia el servidor en modo desarrollo.

## Ejecucion manual

Si prefieres iniciar el proyecto manualmente:

```bash
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d
venv\Scripts\python.exe -m pytest
venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

En Linux/macOS usa `venv/bin/python` en lugar de `venv\Scripts\python.exe`.

El servidor tambien puede ejecutarse directamente con:

```bash
uvicorn app.main:app --reload
```

La documentacion interactiva de FastAPI queda disponible en `http://127.0.0.1:8000/docs`.

## Endpoints principales

- `GET /`: confirma que la API esta funcionando.
- `POST /api/auth/register`: registra usuarios.
- `POST /api/auth/login`: inicia sesion y devuelve un JWT.
- `GET /api/auth/me`: devuelve el usuario autenticado.
- `GET /api/events`: lista eventos.
- `POST /api/events`: crea eventos autenticados.
- `POST /api/reservations`: crea reservas.
- `POST /api/reservations/{id}/pay`: confirma una reserva con pago simulado.
- `GET /api/tickets/my`: lista tickets del usuario.
- `POST /api/tickets/{code}/validate`: valida un ticket.
- `GET /api/notifications`: lista notificaciones basicas.

## Estructura del proyecto

- `app/main.py`: configuracion de FastAPI y registro de routers.
- `app/database.py`: conexion y sesiones de base de datos.
- `app/models.py`: modelos ORM.
- `app/schemas.py`: contratos de entrada y salida.
- `app/security.py`: hashing de contrasenas y JWT.
- `app/dependencies.py`: dependencias compartidas y validaciones de permisos.
- `app/routers/`: rutas de autenticacion, eventos, reservas, tickets y notificaciones.
- `tests/`: pruebas de flujos principales con base SQLite en memoria.
- `reservent-db.sql`: esquema base de la base de datos del sistema.

## Notas

El archivo `reservent-db.sql` define la estructura principal del dominio, incluyendo usuarios, eventos, reservas, pagos simulados, tickets y validaciones.

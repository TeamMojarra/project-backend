# Reservent - Backend

Backend del proyecto Reservent. Este repositorio contiene la base de la API construida con FastAPI, SQLAlchemy y PostgreSQL.

Actualmente incluye la configuracion inicial del servidor, la conexion a la base de datos, un endpoint de prueba y un esquema SQL con las tablas principales del sistema de reservas y eventos.

## Requisitos

- Python 3.11 o superior
- Docker y Docker Compose

## Inicializacion

Clona el repositorio y ejecuta el script de configuracion segun tu sistema operativo:

### Linux / macOS

```bash
bash setup.sh
```

### Windows

```bat
setup.bat
```

El script crea el entorno virtual, instala las dependencias, levanta PostgreSQL con Docker, ejecuta las pruebas basicas e inicia el servidor en modo desarrollo.

## Ejecucion manual

Si prefieres iniciar el proyecto manualmente, el servidor puede ejecutarse con:

```bash
uvicorn app.main:app --reload
```

La documentacion interactiva de FastAPI queda disponible en `http://127.0.0.1:8000/docs`.

## Endpoints iniciales

- `GET /`: confirma que la API esta funcionando.
- `GET /api/hello`: devuelve un mensaje de prueba y registra el primer saludo en la base de datos si no existe.

## Estructura del proyecto

- `app/main.py`: configuracion principal de FastAPI.
- `app/controllers/`: definicion de rutas y endpoints.
- `app/services/`: logica de negocio.
- `app/repositories/`: acceso a datos.
- `app/database.py`: conexion y sesiones de base de datos.
- `app/models.py`: modelos ORM.
- `app/schemas.py`: esquemas de respuesta.
- `tests/`: pruebas basicas del proyecto.
- `reservent-db.sql`: esquema base de la base de datos del sistema.

## Notas

El archivo `reservent-db.sql` define la estructura principal del dominio, incluyendo usuarios, eventos, reservas, pagos simulados, tickets y validaciones.

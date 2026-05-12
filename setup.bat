@echo off

REM ==========================================
REM Setup inicial del proyecto Reservent
REM Sistema: Windows
REM ==========================================

REM Crear entorno virtual de Python
python -m venv venv

REM Activar entorno virtual
call venv\Scripts\activate

REM Actualizar pip
python -m pip install --upgrade pip

REM Instalar dependencias del proyecto
pip install -r requirements.txt

REM Levantar base de datos PostgreSQL con Docker Compose
docker compose up -d

REM Ejecutar pruebas basicas del proyecto
python -m pytest

REM Iniciar servidor FastAPI
uvicorn app.main:app --reload
#!/bin/bash

# ==========================================
# Setup inicial del proyecto Reservent
# Sistema: Linux / Mac / Git Bash
# ==========================================

# Detener ejecucion si ocurre un error
set -e

# Crear entorno virtual de Python
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate

# Actualizar pip
python -m pip install --upgrade pip

# Instalar dependencias del proyecto
python -m pip install -r requirements.txt

# Levantar base de datos PostgreSQL con Docker Compose
docker compose up -d

# Configurar la raiz del proyecto para que Python encuentre el paquete app
export PYTHONPATH="${PWD}"

# Ejecutar pruebas basicas del proyecto
python -m pytest

# Iniciar servidor FastAPI
python -m uvicorn app.main:app --reload
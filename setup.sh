#!/bin/bash

# ==========================================
# Setup inicial del proyecto Reservent
# Sistema: Linux / Mac / Git Bash
# ==========================================

# Detener ejecucion si ocurre un error
set -e

echo "=========================================="
echo "  Configuración del proyecto Reservent"
echo "=========================================="

# Crear entorno virtual de Python
echo "[1/5] Creando entorno virtual..."
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate

# Actualizar pip
echo "[2/5] Actualizando pip..."
python -m pip install --upgrade pip

# Instalar dependencias del proyecto
echo "[3/5] Instalando dependencias..."
python -m pip install -r requirements.txt

# Levantar base de datos PostgreSQL con Docker Compose
echo "[4/5] Levantando base de datos PostgreSQL..."
docker compose up -d

# Esperar a que PostgreSQL esté listo
echo "Esperando a que PostgreSQL esté listo..."
sleep 3

# Configurar la raiz del proyecto para que Python encuentre el paquete app
export PYTHONPATH="${PWD}"

# Ejecutar pruebas basicas del proyecto
echo "[5/5] Ejecutando pruebas..."
python -m pytest tests/ -v

echo ""
echo "=========================================="
echo "  Setup completado exitosamente"
echo "  Ejecuta: uvicorn app.main:app --reload"
echo "  Docs:    http://localhost:8000/docs"
echo "=========================================="

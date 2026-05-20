@echo off

REM ==========================================
REM Setup inicial del proyecto Reservent
REM Sistema: Windows
REM ==========================================

echo ==========================================
echo   Configuracion del proyecto Reservent
echo ==========================================

REM Crear entorno virtual de Python
echo [1/5] Creando entorno virtual...
python -m venv venv

REM Activar entorno virtual
call venv\Scripts\activate

REM Actualizar pip
echo [2/5] Actualizando pip...
python -m pip install --upgrade pip

REM Instalar dependencias del proyecto
echo [3/5] Instalando dependencias...
pip install -r requirements.txt

REM Levantar base de datos PostgreSQL con Docker Compose
echo [4/5] Levantando base de datos PostgreSQL...
docker compose up -d

REM Esperar a que PostgreSQL este listo
echo Esperando a que PostgreSQL este listo...
timeout /t 3

REM Configurar PYTHONPATH
set PYTHONPATH=%CD%

REM Ejecutar pruebas basicas del proyecto
echo [5/5] Ejecutando pruebas...
pytest tests/ -v

echo.
echo ==========================================
echo   Setup completado exitosamente
echo   Ejecuta: uvicorn app.main:app --reload
echo   Docs:    http://localhost:8000/docs
echo ==========================================

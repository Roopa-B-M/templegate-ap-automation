@echo off
REM ============================================================
REM  TempleGate AP Automation - one-time setup (Windows)
REM  Run from the project root:  scripts\setup_windows.bat
REM  Prerequisites: Python 3.11+, Node 18+, PostgreSQL 14+,
REM                 Tesseract OCR (optional, for image invoices)
REM ============================================================
setlocal

echo.
echo [1/6] Creating the PostgreSQL database (psql must be on PATH)...
echo       If this step fails, create the DB manually in pgAdmin:
echo         CREATE DATABASE templegate_ap;
if "%DB_PASSWORD%"=="" set DB_PASSWORD=postgres
set PGPASSWORD=%DB_PASSWORD%
psql -h localhost -U postgres -c "CREATE DATABASE templegate_ap;" 2>nul
if errorlevel 1 echo       (skipped - database may already exist, or psql is not on PATH)

echo.
echo [2/6] Creating backend virtual environment...
cd /d "%~dp0..\backend"
python -m venv venv
call venv\Scripts\activate.bat

echo.
echo [3/6] Installing backend dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [4/6] Creating backend\.env from .env.example (edit it to set your DB password)...
if not exist .env copy .env.example .env

echo.
echo [5/6] Applying migrations...
python manage.py migrate

echo.
echo [6/6] Frontend dependencies...
cd /d "%~dp0..\frontend"
call npm install

echo.
echo ============================================================
echo  Setup complete!
echo  1. Edit backend\.env (DB_PASSWORD, TESSERACT_CMD)
echo  2. Optional demo data:  cd backend ^&^& python manage.py seed_demo
echo  3. Start everything with:  scripts\start_windows.bat
echo ============================================================
endlocal

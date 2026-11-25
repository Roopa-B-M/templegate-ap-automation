@echo off
REM ============================================================
REM  TempleGate AP Automation - start backend + frontend (Windows)
REM  Opens two terminal windows:
REM    - Django API on http://127.0.0.1:8000
REM    - React dev server on http://localhost:5173
REM ============================================================

start "TempleGate - Django API" cmd /k "cd /d %~dp0..\backend && venv\Scripts\activate.bat && python manage.py runserver"

start "TempleGate - React Frontend" cmd /k "cd /d %~dp0..\frontend && npm run dev"

echo Two windows launched:
echo   Backend:  http://127.0.0.1:8000
echo   Frontend: http://localhost:5173
echo (If the frontend window closes instantly, run "npm install" first.)

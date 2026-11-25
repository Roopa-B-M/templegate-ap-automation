#!/usr/bin/env bash
# ============================================================
#  TempleGate AP Automation - start backend + frontend (macOS / Linux)
#  Runs the Django API on http://127.0.0.1:8000 and the Vite dev
#  server on http://localhost:5173 (Ctrl+C stops both).
# ============================================================
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() {
  echo
  echo "Stopping services..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "Starting Django backend..."
cd "$ROOT/backend"
if [ -f venv/bin/activate ]; then . venv/bin/activate; fi
python manage.py runserver 127.0.0.1:8000 &
BACKEND_PID=$!

echo "Starting React frontend..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo
echo "Backend : http://127.0.0.1:8000"
echo "Frontend: http://localhost:5173"
wait

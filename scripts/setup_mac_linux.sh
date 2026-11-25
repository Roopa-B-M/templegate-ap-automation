#!/usr/bin/env bash
# ============================================================
#  TempleGate AP Automation - one-time setup (macOS / Linux)
#  Run from the project root:  bash scripts/setup_mac_linux.sh
#  Prerequisites: Python 3.11+, Node 18+, PostgreSQL 14+,
#                 Tesseract OCR (optional, for image invoices)
# ============================================================
set -e

echo
echo "[1/6] Creating the PostgreSQL database (psql must be on PATH)..."
echo "      If this step fails, create the DB manually:"
echo "        CREATE DATABASE templegate_ap;"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
if command -v psql >/dev/null 2>&1; then
  PGPASSWORD="$DB_PASSWORD" psql -h localhost -U postgres -c "CREATE DATABASE templegate_ap;" 2>/dev/null \
    || echo "      (skipped - database may already exist)"
else
  echo "      psql not found - create the database manually."
fi

echo
echo "[2/6] Creating the backend virtual environment..."
cd "$(dirname "$0")/../backend"
python3 -m venv venv
. venv/bin/activate

echo
echo "[3/6] Installing backend dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

echo
echo "[4/6] Creating backend/.env from .env.example (edit it to set your DB password)..."
[ -f .env ] || cp .env.example .env

echo
echo "[5/6] Applying migrations..."
python manage.py migrate

echo
echo "[6/6] Frontend dependencies..."
cd ../frontend
npm install --no-audit --no-fund

echo
echo "============================================================"
echo " Setup complete!"
echo " 1. Edit backend/.env (DB_PASSWORD, TESSERACT_CMD)"
echo " 2. Optional demo data:  cd backend && python manage.py seed_demo"
echo " 3. Start everything with:  bash scripts/start_mac_linux.sh"
echo "============================================================"

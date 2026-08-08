#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "BehTech Sales Hub başlatılıyor..."

# PostgreSQL (Docker)
if command -v docker &>/dev/null; then
  echo "PostgreSQL başlatılıyor..."
  cd "$ROOT"
  if docker compose version &>/dev/null; then
    docker compose up -d
    echo "PostgreSQL hazır olana kadar bekleniyor..."
    until docker compose exec -T postgres pg_isready -U crm_user -d crm_db &>/dev/null; do
      sleep 1
    done
  elif command -v docker-compose &>/dev/null; then
    docker-compose up -d
    until docker-compose exec -T postgres pg_isready -U crm_user -d crm_db &>/dev/null; do
      sleep 1
    done
  fi
else
  echo "Uyarı: Docker bulunamadı. PostgreSQL'in çalıştığından emin olun."
fi

# Backend
if [ ! -d "$ROOT/backend/venv" ]; then
  echo "Backend sanal ortamı oluşturuluyor..."
  python3 -m venv "$ROOT/backend/venv"
  source "$ROOT/backend/venv/bin/activate"
  pip install -r "$ROOT/backend/requirements.txt"
else
  source "$ROOT/backend/venv/bin/activate"
fi

pip install -q psycopg2-binary 2>/dev/null || pip install -r "$ROOT/backend/requirements.txt"

# SQLite verisi varsa PostgreSQL'e aktar
cd "$ROOT/backend"
python migrate_sqlite.py 2>/dev/null || true

# Frontend
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "Frontend bağımlılıkları yükleniyor..."
  cd "$ROOT/frontend" && npm install
fi

# Eski backend süreçlerini temizle (port çakışmasını önler)
if lsof -ti :8000 &>/dev/null; then
  echo "Port 8000'deki eski süreçler kapatılıyor..."
  lsof -ti :8000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# Backend başlat
cd "$ROOT/backend"
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Frontend başlat
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================="
echo "  CRM Sistemi çalışıyor!"
echo "  Arayüz:     http://localhost:5173"
echo "  API:        http://localhost:8000"
echo "  PostgreSQL: localhost:5433 (crm_db)"
echo "  Şifre:      behlul / (backend/.env'deki SEED_ADMIN_PASSWORD)"
echo "========================================="
echo ""
echo "Durdurmak için Ctrl+C"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait

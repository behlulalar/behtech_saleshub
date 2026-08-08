#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/deploy/.env.production"

if [ ! -f "$ENV_FILE" ]; then
  echo "Hata: $ENV_FILE bulunamadı."
  echo "Önce: cp deploy/.env.production.example deploy/.env.production"
  echo "Sonra değerleri düzenleyin."
  exit 1
fi

cd "$ROOT"

COMPOSE="docker compose"
if ! docker compose version &>/dev/null; then
  COMPOSE="docker-compose"
fi

echo "BehTech Sales Hub production deploy başlıyor..."
$COMPOSE -f docker-compose.prod.yml --env-file "$ENV_FILE" up -d --build

echo ""
echo "Deploy tamamlandı."
echo "Kontrol: curl -I http://127.0.0.1:$(grep -E '^APP_HOST_PORT=' "$ENV_FILE" | cut -d= -f2 || echo 18080)"
echo "Host nginx proxy ayarını deploy/host-nginx.example.conf dosyasından ekleyin."

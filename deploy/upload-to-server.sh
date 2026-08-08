#!/bin/bash
# Lokal Mac'ten sunucuya yükleme
# Kullanım: chmod +x deploy/upload-to-server.sh && ./deploy/upload-to-server.sh

set -euo pipefail

SERVER="root@45.141.150.48"
REMOTE_DIR="/opt/behtech-sales-hub"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Frontend production build"
cd "$LOCAL_DIR/frontend"
npm run build

echo "==> Sunucuda dizin oluştur"
ssh "$SERVER" "mkdir -p $REMOTE_DIR"

echo "==> Proje dosyalarını rsync ile gönder"
rsync -avz --delete \
  --exclude '.git' \
  --exclude 'backend/venv' \
  --exclude 'backend/.env' \
  --exclude 'backend/__pycache__' \
  --exclude 'frontend/node_modules' \
  --exclude 'node_modules' \
  --exclude '.cursor' \
  --exclude '*.db' \
  "$LOCAL_DIR/" "$SERVER:$REMOTE_DIR/"

echo "==> Deploy script izinleri"
ssh "$SERVER" "chmod +x $REMOTE_DIR/deploy/*.sh 2>/dev/null || true"

echo "==> Backend uploads + servis kullanıcısı (behtech)"
ssh "$SERVER" "mkdir -p $REMOTE_DIR/backend/uploads && chown -R behtech:behtech $REMOTE_DIR/backend && chmod 700 $REMOTE_DIR/backend/uploads"

echo "==> Sunucu saati (NTP)"
ssh "$SERVER" "command -v chronyc >/dev/null && chronyc tracking | head -3 || timedatectl status | head -5"

echo ""
echo "Yükleme tamamlandı: $SERVER:$REMOTE_DIR"
echo ""
echo "Not: Sunucudaki backend/.env korunur (rsync exclude). Güncelleme gerekiyorsa sunucuda elle düzenleyin."
echo ""
echo "Servisi yeniden başlat:"
echo "  ssh $SERVER 'systemctl restart behtech-crm && systemctl reload nginx'"

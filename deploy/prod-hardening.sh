#!/bin/bash
# Faz 0 — Sunucu güvenlik kontrolleri (root olarak çalıştırın)
#   chmod +x deploy/prod-hardening.sh && ./deploy/prod-hardening.sh

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/behtech-sales-hub}"
ENV_FILE="$APP_DIR/backend/.env"

echo "==> BehTech Sales Hub — Prod hardening (Faz 0)"
echo ""

if [ "$(id -u)" -ne 0 ]; then
  echo "Bu script root olarak çalıştırılmalı (sudo)."
  exit 1
fi

echo "==> 1/4 UFW firewall"
if command -v ufw &>/dev/null; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
  ufw status verbose
else
  echo "Uyarı: ufw yüklü değil. apt install ufw"
fi

echo ""
echo "==> 2/4 .env production kontrolü"
if [ ! -f "$ENV_FILE" ]; then
  echo "HATA: $ENV_FILE bulunamadı"
  exit 1
fi

check_env() {
  local key="$1"
  local val
  val=$(grep "^${key}=" "$ENV_FILE" | cut -d= -f2- || true)
  if [ -z "$val" ]; then
    echo "  ✗ $key eksik"
    return 1
  fi
  echo "  ✓ $key ayarlı"
}

FAIL=0
grep -q '^APP_ENV=production' "$ENV_FILE" || { echo "  ✗ APP_ENV=production gerekli"; FAIL=1; }
check_env SECRET_KEY || FAIL=1
check_env DATABASE_URL || FAIL=1
check_env APP_URL || FAIL=1
check_env CORS_ORIGINS || FAIL=1

if grep -q 'localhost\|127.0.0.1' "$ENV_FILE" 2>/dev/null; then
  if grep '^APP_URL=\|^CORS_ORIGINS=' "$ENV_FILE" | grep -q 'localhost\|127.0.0.1'; then
    echo "  ✗ APP_URL / CORS_ORIGINS localhost içermemeli"
    FAIL=1
  fi
fi

if [ "$FAIL" -ne 0 ]; then
  echo ""
  echo "HATA: .env düzeltin ve tekrar deneyin."
  exit 1
fi

echo ""
echo "==> 3/4 Yedekleme dizini + cron"
mkdir -p /var/backups/behtech-crm
chmod +x "$APP_DIR/deploy/backup-db.sh"
CRON_LINE="0 3 * * * $APP_DIR/deploy/backup-db.sh >> /var/log/behtech-crm-backup.log 2>&1"
(crontab -l 2>/dev/null | grep -Fv "backup-db.sh"; echo "$CRON_LINE") | crontab -
echo "  ✓ Günlük yedek cron: 03:00"

chmod +x "$APP_DIR/deploy/cleanup-old-activities.sh" 2>/dev/null || true
if [ -f "$APP_DIR/deploy/cleanup-old-activities.sh" ]; then
  CLEANUP_CRON="0 4 * * 0 $APP_DIR/deploy/cleanup-old-activities.sh >> /var/log/behtech-crm-cleanup.log 2>&1"
  (crontab -l 2>/dev/null | grep -Fv "cleanup-old-activities.sh"; echo "$CLEANUP_CRON") | crontab -
  echo "  ✓ Haftalık aktivite temizliği cron: Pazar 04:00"
fi

chmod +x "$APP_DIR/deploy/run-ai-batch.sh" 2>/dev/null || true
if [ -f "$APP_DIR/deploy/run-ai-batch.sh" ]; then
  AI_CRON="0 2 * * * $APP_DIR/deploy/run-ai-batch.sh >> /var/log/behtech-ai-batch.log 2>&1"
  (crontab -l 2>/dev/null | grep -Fv "run-ai-batch.sh"; echo "$AI_CRON") | crontab -
  echo "  ✓ Gece AI batch skor cron: 02:00 (Europe/Istanbul)"
fi

echo ""
echo "==> 4/5 NTP (chrony) — cron / otomasyon saatleri için zorunlu"
timedatectl set-timezone Europe/Istanbul
if ! command -v chronyc &>/dev/null; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y chrony
fi
# Large step always allowed — otherwise clock can stay hours ahead and digests fire early.
if [ -f /etc/chrony/chrony.conf ]; then
  if grep -qE '^makestep' /etc/chrony/chrony.conf; then
    sed -i 's/^makestep.*/makestep 1.0 -1/' /etc/chrony/chrony.conf
  else
    echo 'makestep 1.0 -1' >> /etc/chrony/chrony.conf
  fi
fi
systemctl enable --now chrony
systemctl restart chrony
# Hard sync if slew-only left the clock hours off
if chronyc tracking 2>/dev/null | awk '/System time/{exit !(sqrt($4*$4)>60)}'; then
  echo "  ⚠ large NTP offset — hard stepping clock"
  systemctl stop chrony
  chronyd -q 'server time.ume.tubitak.gov.tr iburst' 2>/dev/null \
    || chronyd -q 'server time.cloudflare.com iburst' 2>/dev/null \
    || true
  systemctl start chrony
fi
chronyc makestep 2>/dev/null || true
hwclock --systohc --utc 2>/dev/null || true
if chronyc tracking | grep -q "System time"; then
  OFF=$(chronyc tracking | awk '/System time/{print $4}')
  REF=$(chronyc tracking | awk '/Reference ID/{print $3}' | tr -d '()')
  echo "  ✓ chrony aktif (ref=$REF offset=${OFF}s)"
else
  echo "  ⚠ chrony durumunu kontrol edin: chronyc tracking"
fi

echo ""
echo "==> 5/5 API health"
if curl -sf http://127.0.0.1:18080/api/health | grep -q '"status"'; then
  echo "  ✓ /api/health OK"
else
  echo "  ✗ API yanıt vermiyor — systemctl status behtech-crm"
  exit 1
fi

echo ""
echo "========================================="
echo " Faz 0 tamamlandı"
echo " Yedekler: /var/backups/behtech-crm"
echo " Log     : /var/log/behtech-crm-backup.log"
echo ""
echo " Sonraki: deploy/MONITORING-CLOUDFLARE.md"
echo "   - Cloudflare DNS + SSL"
echo "   - UptimeRobot /api/health monitor"
echo "========================================="

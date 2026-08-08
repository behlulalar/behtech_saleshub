#!/bin/bash
# Sunucuda bir kez (ve güncelleme sonrası) çalıştırın:
#   chmod +x /opt/behtech-sales-hub/deploy/setup-server.sh
#   /opt/behtech-sales-hub/deploy/setup-server.sh

set -euo pipefail

APP_DIR="/opt/behtech-sales-hub"
DB_USER="behtech_crm_user"
DB_NAME="behtech_crm_db"
SERVICE_NAME="behtech-crm"
NGINX_SITE="behtech-saleshub"
DOMAIN="saleshub.behtechlabs.com"

if [ -z "${BEHTECH_DB_PASSWORD:-}" ]; then
  echo "Hata: BEHTECH_DB_PASSWORD ortam değişkeni gerekli."
  echo "  export BEHTECH_DB_PASSWORD='guclu-sifreniz'"
  exit 1
fi
DB_PASS="$BEHTECH_DB_PASSWORD"

echo "==> BehTech Sales Hub sunucu kurulumu"
echo "    Dizin : $APP_DIR"
echo "    Domain: $DOMAIN"

if [ ! -d "$APP_DIR/backend" ]; then
  echo "Hata: $APP_DIR/backend bulunamadı. Önce dosyaları yükleyin."
  exit 1
fi

echo "==> PostgreSQL kullanıcı/veritabanı"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';
SQL
  echo "Kullanıcı oluşturuldu: $DB_USER"
else
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';"
  echo "Kullanıcı şifresi güncellendi: $DB_USER"
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
CREATE DATABASE $DB_NAME OWNER $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
SQL
  echo "Veritabanı oluşturuldu: $DB_NAME"
else
  echo "Veritabanı zaten var: $DB_NAME"
fi

echo "==> backend/.env"
if [ ! -f "$APP_DIR/backend/.env" ]; then
  cp "$APP_DIR/backend/.env.server.example" "$APP_DIR/backend/.env"
fi
# DATABASE_URL her zaman senkronize et
if grep -q '^DATABASE_URL=' "$APP_DIR/backend/.env"; then
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg2://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}|" "$APP_DIR/backend/.env"
else
  echo "DATABASE_URL=postgresql+psycopg2://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}" >> "$APP_DIR/backend/.env"
fi
grep -q '^APP_URL=' "$APP_DIR/backend/.env" && sed -i 's|^APP_URL=.*|APP_URL=https://saleshub.behtechlabs.com|' "$APP_DIR/backend/.env" || echo 'APP_URL=https://saleshub.behtechlabs.com' >> "$APP_DIR/backend/.env"
grep -q '^CORS_ORIGINS=' "$APP_DIR/backend/.env" && sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://saleshub.behtechlabs.com|' "$APP_DIR/backend/.env" || echo 'CORS_ORIGINS=https://saleshub.behtechlabs.com' >> "$APP_DIR/backend/.env"
grep -q '^APP_ENV=' "$APP_DIR/backend/.env" && sed -i 's|^APP_ENV=.*|APP_ENV=production|' "$APP_DIR/backend/.env" || echo 'APP_ENV=production' >> "$APP_DIR/backend/.env"

echo "==> Python venv"
cd "$APP_DIR/backend"
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt

echo "==> Frontend build kontrolü"
if [ ! -f "$APP_DIR/frontend/dist/index.html" ]; then
  if command -v npm &>/dev/null; then
    cd "$APP_DIR/frontend"
    npm ci
    npm run build
  else
    echo "Uyarı: frontend/dist yok ve npm bulunamadı. Local'den dist yükleyin."
  fi
fi

echo "==> Sistem kullanıcısı (behtech)"
if ! id behtech &>/dev/null; then
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin behtech
fi
chown -R behtech:behtech "$APP_DIR/backend"
chmod -R a+rX "$APP_DIR/frontend/dist" 2>/dev/null || true

echo "==> Nginx rate limit (auth)"
cp "$APP_DIR/deploy/nginx-rate-limit.conf" /etc/nginx/conf.d/behtech-rate-limit.conf

echo "==> Nginx Cloudflare gerçek IP"
cp "$APP_DIR/deploy/nginx-cloudflare-realip.conf" /etc/nginx/conf.d/nginx-cloudflare-realip.conf

echo "==> systemd servisi"
cp "$APP_DIR/deploy/behtech-crm.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 3
systemctl --no-pager status "$SERVICE_NAME" || true

echo "==> API test"
curl -sf http://127.0.0.1:18080/api/health || echo "API henüz hazır değil — journalctl -u $SERVICE_NAME -f"

echo "==> Nginx site (önce HTTP bootstrap)"
cp "$APP_DIR/deploy/saleshub.nginx.bootstrap.conf" "/etc/nginx/sites-available/${NGINX_SITE}.conf"
ln -sf "/etc/nginx/sites-available/${NGINX_SITE}.conf" "/etc/nginx/sites-enabled/${NGINX_SITE}.conf"
nginx -t
systemctl reload nginx

if [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
  echo "SSL sertifikası yok. Certbot çalıştırılıyor..."
  if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m behlulalar32@gmail.com; then
    cp "$APP_DIR/deploy/saleshub.nginx.conf" "/etc/nginx/sites-available/${NGINX_SITE}.conf"
    nginx -t
    systemctl reload nginx
    echo "SSL kuruldu ve tam nginx config aktif"
  else
    echo "Certbot başarısız. DNS A kaydı: $DOMAIN -> sunucu IP (45.141.150.48) olmalı"
    echo "Şimdilik HTTP ile test: http://$DOMAIN"
  fi
else
  cp "$APP_DIR/deploy/saleshub.nginx.conf" "/etc/nginx/sites-available/${NGINX_SITE}.conf"
  nginx -t
  systemctl reload nginx
fi

echo ""
echo "Sonraki adım (Faz 0 hardening):"
echo "  $APP_DIR/deploy/prod-hardening.sh"
echo ""
echo "========================================="
echo " Kurulum tamamlandı!"
echo " Site : https://$DOMAIN (DNS + SSL hazırsa)"
echo " API  : http://127.0.0.1:18080"
echo " DB   : $DB_NAME @ 127.0.0.1:5432"
echo "========================================="
echo "Log: journalctl -u $SERVICE_NAME -f"

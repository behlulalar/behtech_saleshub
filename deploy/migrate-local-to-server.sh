#!/bin/bash
# Lokal Docker PostgreSQL verisini prod sunucuya taşır.
# Kullanım (Mac, proje kökünden):
#   chmod +x deploy/migrate-local-to-server.sh
#   ./deploy/migrate-local-to-server.sh
#
# UYARI: Sunucudaki mevcut CRM veritabanı verilerinin üzerine yazar.
# Önce otomatik yedek alınır.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER="${SERVER:-root@45.141.150.48}"
REMOTE_DIR="${REMOTE_DIR:-/opt/behtech-sales-hub}"
STAMP=$(date +%Y%m%d_%H%M%S)
LOCAL_DUMP="$ROOT/deploy/backups/local_to_prod_${STAMP}.sql.gz"
REMOTE_DUMP="/tmp/local_to_prod_${STAMP}.sql.gz"

mkdir -p "$ROOT/deploy/backups"

echo "========================================="
echo " BehTech CRM — Lokal → Prod DB Taşıma"
echo "========================================="
echo ""

cd "$ROOT"

if ! docker compose ps --status running 2>/dev/null | grep -q postgres; then
  echo "Hata: Lokal PostgreSQL çalışmıyor. Önce ./start.sh veya docker compose up -d"
  exit 1
fi

echo "[1/4] Lokal veritabanı dışa aktarılıyor..."
docker compose exec -T postgres pg_dump -U crm_user -d crm_db \
  --no-owner --no-acl | gzip > "$LOCAL_DUMP"
ls -lh "$LOCAL_DUMP"
docker compose exec -T postgres psql -U crm_user -d crm_db -c \
  "SELECT 'users' t, count(*) FROM users UNION ALL SELECT 'leads', count(*) FROM leads UNION ALL SELECT 'categories', count(*) FROM categories;"

echo ""
echo "[2/4] Dump sunucuya kopyalanıyor..."
scp "$LOCAL_DUMP" "$SERVER:$REMOTE_DUMP"

echo ""
echo "[3/4] Sunucuda yedek alınıp restore ediliyor..."
ssh "$SERVER" bash -s "$REMOTE_DUMP" "$REMOTE_DIR" <<'REMOTE'
set -euo pipefail
REMOTE_DUMP="$1"
REMOTE_DIR="$2"
ENV_FILE="$REMOTE_DIR/backend/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Hata: $ENV_FILE bulunamadı"
  exit 1
fi

DATABASE_URL=$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
PARSED=$(python3 - <<'PY' "$DATABASE_URL"
import sys
from urllib.parse import urlparse
u = urlparse(sys.argv[1].replace("postgresql+psycopg2", "postgresql", 1))
print(u.username or "")
print(u.password or "")
print(u.hostname or "127.0.0.1")
print(u.port or 5432)
print((u.path or "/").lstrip("/"))
PY
)
DB_USER=$(echo "$PARSED" | sed -n '1p')
DB_PASS=$(echo "$PARSED" | sed -n '2p')
DB_HOST=$(echo "$PARSED" | sed -n '3p')
DB_PORT=$(echo "$PARSED" | sed -n '4p')
DB_NAME=$(echo "$PARSED" | sed -n '5p')

BACKUP_DIR="/var/backups/behtech-crm"
mkdir -p "$BACKUP_DIR"
PROD_BACKUP="$BACKUP_DIR/${DB_NAME}_before_local_import_$(date +%Y%m%d_%H%M%S).sql.gz"

echo "Prod yedek: $PROD_BACKUP"
sudo -u postgres pg_dump -d "$DB_NAME" --no-owner --no-acl | gzip > "$PROD_BACKUP"

echo "API durduruluyor..."
systemctl stop behtech-crm

echo "Mevcut şema temizleniyor (CASCADE)..."
sudo -u postgres psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -q <<SQL
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
ALTER SCHEMA public OWNER TO $DB_USER;
GRANT ALL ON SCHEMA public TO $DB_USER;
GRANT ALL ON SCHEMA public TO public;
SQL

echo "Lokal dump restore ediliyor..."
gunzip -c "$REMOTE_DUMP" | sudo -u postgres psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -q

sudo -u postgres psql -d "$DB_NAME" -q <<SQL
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
DO \$\$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO $DB_USER', r.tablename);
  END LOOP;
  FOR r IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public' LOOP
    EXECUTE format('ALTER SEQUENCE public.%I OWNER TO $DB_USER', r.sequence_name);
  END LOOP;
END \$\$;
ALTER DATABASE $DB_NAME OWNER TO $DB_USER;
SQL

echo "Sequence'ler senkronize ediliyor..."
sudo -u postgres psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -q <<'SQL'
SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 1));
SELECT setval(pg_get_serial_sequence('leads', 'id'), COALESCE((SELECT MAX(id) FROM leads), 1));
SELECT setval(pg_get_serial_sequence('lead_activities', 'id'), COALESCE((SELECT MAX(id) FROM lead_activities), 1));
SELECT setval(pg_get_serial_sequence('lead_requests', 'id'), COALESCE((SELECT MAX(id) FROM lead_requests), 1));
SELECT setval(pg_get_serial_sequence('email_verification_tokens', 'id'), COALESCE((SELECT MAX(id) FROM email_verification_tokens), 1));
SELECT setval(pg_get_serial_sequence('password_reset_tokens', 'id'), COALESCE((SELECT MAX(id) FROM password_reset_tokens), 1));
SQL

rm -f "$REMOTE_DUMP"

echo "Restore sonrası kayıt sayıları:"
sudo -u postgres psql -d "$DB_NAME" -c \
  "SELECT 'users' t, count(*) FROM users UNION ALL SELECT 'leads', count(*) FROM leads UNION ALL SELECT 'categories', count(*) FROM categories UNION ALL SELECT 'activities', count(*) FROM lead_activities;"

chown -R behtech:behtech "$REMOTE_DIR/backend"
systemctl start behtech-crm
sleep 2
systemctl is-active behtech-crm
curl -s http://127.0.0.1:18080/api/health || true
REMOTE

echo ""
echo "[4/4] Tamamlandı"
echo "Lokal yedek : $LOCAL_DUMP"
echo "Sunucu      : $SERVER"
echo ""
echo "Prod'da giriş: behlul + lokal şifreniz (backend/.env SEED_ADMIN_PASSWORD)"
echo "Dashboard   : https://saleshub.behtechlabs.com"

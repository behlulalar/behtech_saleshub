#!/bin/bash
# PostgreSQL günlük yedekleme
# Tam yedek + Drive: deploy/backup-all.sh — ayrıntılar: deploy/BACKUP.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BACKUP_ENV:-$SCRIPT_DIR/backup.env}"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

APP_DIR="${APP_DIR:-/opt/behtech-sales-hub}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/behtech-crm}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
ENV_FILE="$APP_DIR/backend/.env"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[$(date -Iseconds)] ERROR: $ENV_FILE not found"
  exit 1
fi

DATABASE_URL=$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
if [ -z "$DATABASE_URL" ]; then
  echo "[$(date -Iseconds)] ERROR: DATABASE_URL missing in $ENV_FILE"
  exit 1
fi

# postgresql+psycopg2://user:pass@host:port/dbname -> user, pass, host, port, dbname
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

STAMP=$(date +%Y%m%d_%H%M%S)
OUTFILE="$BACKUP_DIR/${DB_NAME}_${STAMP}.sql.gz"

export PGPASSWORD="$DB_PASS"
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl | gzip > "$OUTFILE"
unset PGPASSWORD

find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete

SIZE=$(du -h "$OUTFILE" | cut -f1)
echo "[$(date -Iseconds)] OK: $OUTFILE ($SIZE)"

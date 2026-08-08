#!/bin/bash
# Müşteri dosyaları (sözleşmeler vb.) günlük yedekleme

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BACKUP_ENV:-$SCRIPT_DIR/backup.env}"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

APP_DIR="${APP_DIR:-/opt/behtech-sales-hub}"
UPLOADS_SRC="$APP_DIR/backend/uploads"
BACKUP_DIR="${UPLOADS_BACKUP_DIR:-/var/backups/behtech-crm/uploads}"
RETENTION_DAYS="${UPLOADS_RETENTION_DAYS:-7}"

if [ ! -d "$UPLOADS_SRC" ]; then
  echo "[$(date -Iseconds)] SKIP: uploads directory not found ($UPLOADS_SRC)"
  exit 0
fi

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
OUTFILE="$BACKUP_DIR/uploads_${STAMP}.tar.gz"

tar -czf "$OUTFILE" -C "$APP_DIR/backend" uploads
chmod 600 "$OUTFILE"

find "$BACKUP_DIR" -name 'uploads_*.tar.gz' -mtime +"$RETENTION_DAYS" -delete

SIZE=$(du -h "$OUTFILE" | cut -f1)
echo "[$(date -Iseconds)] OK: $OUTFILE ($SIZE)"

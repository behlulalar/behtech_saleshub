#!/bin/bash
# Yerel yedekleri Google Drive klasörüne kopyalar (berber randevu_yedekleri mantığı)
# DB dump (.sql.gz) ve dosya arşivi (.tar.gz) aynı Drive klasörüne gider.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BACKUP_ENV:-$SCRIPT_DIR/backup.env}"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
RCLONE_DEST="${RCLONE_DEST:-saleshub_yedekleri}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/behtech-crm}"
UPLOADS_BACKUP_DIR="${UPLOADS_BACKUP_DIR:-$BACKUP_DIR/uploads}"
DRIVE_RETENTION_DAYS="${DRIVE_RETENTION_DAYS:-365}"

if ! command -v rclone >/dev/null 2>&1; then
  echo "[$(date -Iseconds)] ERROR: rclone kurulu değil. deploy/setup-rclone-drive.sh çalıştırın."
  exit 1
fi

if ! rclone listremotes 2>/dev/null | grep -qx "${RCLONE_REMOTE}:"; then
  echo "[$(date -Iseconds)] ERROR: rclone remote '${RCLONE_REMOTE}:' yapılandırılmamış."
  echo "  Sunucuda: rclone config  (remote adı: ${RCLONE_REMOTE}, hesap: behlulalar32@gmail.com)"
  exit 1
fi

REMOTE="${RCLONE_REMOTE}:${RCLONE_DEST}"

echo "[$(date -Iseconds)] Drive yedek → ${REMOTE}"

if [ -d "$BACKUP_DIR" ]; then
  rclone copy "$BACKUP_DIR" "$REMOTE" \
    --include "*.sql.gz" \
    --transfers 4 \
    --checkers 8 \
    --stats-one-line \
    --stats 30s
fi

if [ -d "$UPLOADS_BACKUP_DIR" ]; then
  rclone copy "$UPLOADS_BACKUP_DIR" "$REMOTE" \
    --include "*.tar.gz" \
    --transfers 4 \
    --checkers 8 \
    --stats-one-line \
    --stats 30s
fi

if [ "${DRIVE_RETENTION_DAYS:-0}" -gt 0 ]; then
  rclone delete "$REMOTE" --min-age "${DRIVE_RETENTION_DAYS}d" --include "*.sql.gz" || true
  rclone delete "$REMOTE" --min-age "${DRIVE_RETENTION_DAYS}d" --include "*.tar.gz" || true
fi

echo "[$(date -Iseconds)] OK: Drive yedek tamam (${RCLONE_DEST}/)"

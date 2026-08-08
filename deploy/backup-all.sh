#!/bin/bash
# Veritabanı + müşteri dosyaları yedekleme (+ Google Drive varsa otomatik yükleme)
# Cron: 0 3 * * * /opt/behtech-sales-hub/deploy/backup-all.sh >> /var/log/behtech-crm-backup.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BACKUP_ENV:-$SCRIPT_DIR/backup.env}"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  export BACKUP_DIR UPLOADS_BACKUP_DIR RETENTION_DAYS UPLOADS_RETENTION_DAYS
fi

echo "[$(date -Iseconds)] === BehTech Sales Hub backup started ==="
"$SCRIPT_DIR/backup-db.sh"
"$SCRIPT_DIR/backup-uploads.sh"

if [ -x "$SCRIPT_DIR/backup-to-drive.sh" ]; then
  if command -v rclone >/dev/null 2>&1; then
    REMOTE="${RCLONE_REMOTE:-gdrive}"
    if rclone listremotes 2>/dev/null | grep -qx "${REMOTE}:"; then
      "$SCRIPT_DIR/backup-to-drive.sh" || echo "[$(date -Iseconds)] WARN: Drive yedek başarısız"
    else
      echo "[$(date -Iseconds)] SKIP: Drive remote '${REMOTE}:' yapılandırılmamış (deploy/setup-rclone-drive.sh)"
    fi
  fi
fi

echo "[$(date -Iseconds)] === Backup completed ==="

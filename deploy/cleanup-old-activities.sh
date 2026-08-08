#!/bin/bash
# 2 yıldan eski aktivite loglarını temizler (opsiyonel, haftalık cron)
# Cron: 0 4 * * 0 /opt/behtech-sales-hub/deploy/cleanup-old-activities.sh >> /var/log/behtech-crm-cleanup.log 2>&1

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/behtech-sales-hub}"
ENV_FILE="$APP_DIR/backend/.env"
RETENTION_DAYS="${RETENTION_DAYS:-730}"

DATABASE_URL=$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")

python3 - <<PY "$DATABASE_URL" "$RETENTION_DAYS"
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

db_url = sys.argv[1].replace("postgresql+psycopg2", "postgresql", 1)
retention_days = int(sys.argv[2])
cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

engine = create_engine(db_url)
with engine.begin() as conn:
    result = conn.execute(
        text("DELETE FROM lead_activities WHERE created_at < :cutoff"),
        {"cutoff": cutoff.replace(tzinfo=None)},
    )
    print(f"[{datetime.now().isoformat()}] Deleted {result.rowcount} activities older than {retention_days} days")
PY

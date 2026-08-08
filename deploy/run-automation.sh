#!/bin/bash
# CRM otomasyon e-postaları
# Crontab (Europe/Istanbul):
# CRON_TZ=Europe/Istanbul
# 0 8 * * * /opt/behtech-sales-hub/deploy/run-automation.sh morning
# 0 18 * * * /opt/behtech-sales-hub/deploy/run-automation.sh eod

set -euo pipefail

export TZ=Europe/Istanbul

APP_DIR="${APP_DIR:-/opt/behtech-sales-hub}"
MODE="${1:-morning}"
VENV_PYTHON="$APP_DIR/backend/venv/bin/python"
JOB="$APP_DIR/backend/jobs/run_automation.py"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "[$(date -Iseconds)] ERROR: Python venv not found: $VENV_PYTHON"
  exit 1
fi

echo "[$(date -Iseconds)] automation $MODE started"
cd "$APP_DIR/backend"
"$VENV_PYTHON" "$JOB" "$MODE"
echo "[$(date -Iseconds)] automation $MODE finished"

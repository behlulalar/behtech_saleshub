#!/bin/bash
# Gece toplu lead skorlama + kuyruk işleme (Faz 3)
set -euo pipefail

APP_DIR="/opt/behtech-sales-hub"
VENV="$APP_DIR/backend/venv/bin/python"

cd "$APP_DIR/backend"
export PYTHONPATH="$APP_DIR/backend"

if [[ ! -x "$VENV" ]]; then
  echo "Python venv bulunamadı: $VENV" >&2
  exit 1
fi

"$VENV" jobs/run_ai_job.py score_all_orgs
"$VENV" jobs/run_ai_job.py process_queue --limit 20

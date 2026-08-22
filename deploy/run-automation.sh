#!/bin/bash
# CRM otomasyon e-postaları
# Crontab (Europe/Istanbul) — CRON_TZ en üste yazılmalı:
# CRON_TZ=Europe/Istanbul
# 0 8 * * * /opt/behtech-sales-hub/deploy/run-automation.sh morning >> /var/log/behtech-crm-automation.log 2>&1
# 0 18 * * * /opt/behtech-sales-hub/deploy/run-automation.sh eod >> /var/log/behtech-crm-automation.log 2>&1
#
# Beklenen gönderim: sabah 08:00 TR, gün sonu 18:00 TR.
# Saat kayması varsa (NTP offset) mail GÖNDERİLMEZ — erken/geç özet engellenir.

set -euo pipefail

export TZ=Europe/Istanbul

APP_DIR="${APP_DIR:-/opt/behtech-sales-hub}"
MODE="${1:-morning}"
VENV_PYTHON="$APP_DIR/backend/venv/bin/python"
JOB="$APP_DIR/backend/jobs/run_automation.py"
# Max allowed |NTP offset| in seconds before refusing to send
MAX_SKEW_SEC="${AUTOMATION_MAX_CLOCK_SKEW_SEC:-90}"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "[$(date -Iseconds)] ERROR: Python venv not found: $VENV_PYTHON"
  exit 1
fi

if [ "$MODE" != "morning" ] && [ "$MODE" != "eod" ]; then
  echo "[$(date -Iseconds)] ERROR: mode must be morning|eod (got: $MODE)"
  exit 1
fi

# Guard: system clock must be close to NTP (prevents 2–3h early digests).
if command -v chronyc >/dev/null 2>&1; then
  TRACKING="$(chronyc tracking 2>/dev/null || true)"
  OFFSET="$(printf '%s\n' "$TRACKING" | awk '/System time/ {print $4; exit}')"
  LEAP="$(printf '%s\n' "$TRACKING" | awk '/Leap status/ {print $4; exit}')"
  if [ -z "$OFFSET" ]; then
    echo "[$(date -Iseconds)] ERROR: chronyc tracking unavailable — refusing automation send"
    exit 1
  fi
  echo "[$(date -Iseconds)] clock check: ntp_offset_sec=$OFFSET leap=$LEAP limit=$MAX_SKEW_SEC"
  if ! python3 -c "import sys; sys.exit(0 if abs(float('$OFFSET')) <= float('$MAX_SKEW_SEC') else 1)"; then
    echo "[$(date -Iseconds)] ERROR: clock skew ${OFFSET}s exceeds ${MAX_SKEW_SEC}s — refusing $MODE send"
    echo "[$(date -Iseconds)] Fix: systemctl stop chrony; chronyd -q 'server time.ume.tubitak.gov.tr iburst'; systemctl start chrony"
    exit 1
  fi
  if printf '%s\n' "$TRACKING" | grep -q "Leap status[[:space:]]*:[[:space:]]*Not synchronised"; then
    echo "[$(date -Iseconds)] WARN: chrony not synchronised yet (offset=${OFFSET}s) — continuing if skew within limit"
  fi
else
  echo "[$(date -Iseconds)] WARN: chronyc missing — proceeding without NTP skew guard"
fi

# Expected local hour window (soft warn only; cron owns schedule)
HOUR="$(date +%H)"
if [ "$MODE" = "morning" ] && [ "$HOUR" != "08" ]; then
  echo "[$(date -Iseconds)] WARN: morning job running at hour=$HOUR (expected 08 TR)"
fi
if [ "$MODE" = "eod" ] && [ "$HOUR" != "18" ]; then
  echo "[$(date -Iseconds)] WARN: eod job running at hour=$HOUR (expected 18 TR)"
fi

echo "[$(date -Iseconds)] automation $MODE started"
cd "$APP_DIR/backend"
"$VENV_PYTHON" "$JOB" "$MODE"
echo "[$(date -Iseconds)] automation $MODE finished"

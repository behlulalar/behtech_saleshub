"""Uygulama takvimi — Türkiye (Europe/Istanbul). Otomasyon ve 'bugün' mantığı için."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo("Europe/Istanbul")


def local_now() -> datetime:
    return datetime.now(APP_TZ)


def local_today() -> date:
    return local_now().date()

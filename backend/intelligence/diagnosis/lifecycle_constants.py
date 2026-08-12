"""DE-5.0 diagnosis lifecycle constants."""

from __future__ import annotations

PERIOD_KEY_CURRENT = "current"
PERIOD_FUNNEL = frozenset({"daily", "weekly", "monthly"})

STATE_NEW = "new"
STATE_ACTIVE = "active"
STATE_IMPROVING = "improving"
STATE_WORSENING = "worsening"
STATE_RESOLVED = "resolved"

ALLOWED_STATES = frozenset(
    {STATE_NEW, STATE_ACTIVE, STATE_IMPROVING, STATE_WORSENING, STATE_RESOLVED}
)

SEVERITY_RANK: dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

TRIGGER_SYNC = "sync"
TRIGGER_RESOLVE = "resolve"

DIAGNOSIS_TYPE_FUNNEL = "funnel_drop"
DIAGNOSIS_TYPE_FOLLOW_UP = "follow_up"
DIAGNOSIS_TYPE_OFFER = "offer"

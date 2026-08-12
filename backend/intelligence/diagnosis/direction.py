"""Shared severity / metric comparison for sync lifecycle and trend (DE-5.1)."""

from __future__ import annotations

from typing import Any

from intelligence.diagnosis.lifecycle_constants import (
    DIAGNOSIS_TYPE_FUNNEL,
    SEVERITY_RANK,
)


def severity_delta(old: str, new: str) -> int:
    """Positive = worse, negative = better, 0 = same/unknown."""
    a = SEVERITY_RANK.get((old or "").strip().lower())
    b = SEVERITY_RANK.get((new or "").strip().lower())
    if a is None or b is None:
        return 0
    return b - a


def metric_direction(
    diagnosis_type: str,
    old_value: float | None,
    new_value: float | None,
) -> int:
    """
    Positive = worse, negative = better, 0 = same/unknown.

    funnel_drop: higher conversion is better.
    follow_up / offer: higher idle/age is worse.
    """
    if old_value is None or new_value is None:
        return 0
    if new_value == old_value:
        return 0
    if diagnosis_type == DIAGNOSIS_TYPE_FUNNEL:
        return -1 if new_value > old_value else 1
    return 1 if new_value > old_value else -1


def coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

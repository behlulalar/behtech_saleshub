"""Whitelist context for DE-5.1-C historical diagnosis interpretation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from intelligence.diagnosis.trend import filter_substantive_snapshots, is_resolve_snapshot


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _public_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    return {
        "observed_at": str(snap.get("observed_at") or ""),
        "state": str(snap.get("state") or ""),
        "severity": str(snap.get("severity") or ""),
        "current_value": _num(snap.get("current_value")),
        "affected_lead_count": int(snap.get("affected_lead_count") or 0),
        "change_percent": _num(snap.get("change_percent")),
    }


def _public_changes(changes: dict[str, Any] | None) -> dict[str, Any]:
    raw = changes if isinstance(changes, dict) else {}
    keys = (
        "severity_from",
        "severity_to",
        "severity_delta",
        "current_value_from",
        "current_value_to",
        "current_value_delta",
        "metric_direction",
        "affected_lead_count_from",
        "affected_lead_count_to",
        "affected_lead_count_delta",
        "high_priority_count_from",
        "high_priority_count_to",
        "high_priority_count_delta",
        "lead_set_size_from",
        "lead_set_size_to",
        "lead_set_added_count",
        "lead_set_removed_count",
    )
    return {k: raw.get(k) for k in keys if k in raw}


def _public_worst(worst: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(worst, dict):
        return None
    return {
        "observed_at": str(worst.get("observed_at") or ""),
        "severity": str(worst.get("severity") or ""),
        "metric": str(worst.get("metric") or ""),
        "current_value": _num(worst.get("current_value")),
        "affected_lead_count": int(worst.get("affected_lead_count") or 0),
    }


def build_diagnosis_history_interpret_context(
    *,
    locale: str,
    diagnosis_id: str,
    diagnosis_type: str,
    period_key: str,
    case_state: str,
    title: str,
    severity: str,
    metric: str,
    current_value: Any,
    affected_lead_count: int,
    trend: dict[str, Any],
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Safe LLM context. No org ids, DB ids, fingerprints, raw evidence, or lead names.
    Trend is precomputed — AI must not recalculate it.
    """
    metrics = trend.get("metrics") if isinstance(trend.get("metrics"), dict) else {}
    window = metrics.get("window") if isinstance(metrics.get("window"), dict) else {}
    substantive = filter_substantive_snapshots(snapshots, ascending=True)
    # Cap history length for prompt size (newest last; keep last 12 substantive).
    history_rows = [_public_snapshot(s) for s in substantive[-12:]]

    return {
        "locale": (locale or "tr")[:8],
        "period_key": period_key,
        "case_state": str(case_state or ""),
        "diagnosis": {
            "diagnosis_id": diagnosis_id,
            "diagnosis_type": diagnosis_type,
            "title": (title or "")[:255],
            "severity": severity,
            "metric": metric,
            "current_value": _num(current_value),
            "affected_lead_count": int(affected_lead_count or 0),
        },
        "trend": {
            "direction": str(trend.get("direction") or "stable"),
            "reason_codes": list(trend.get("reason_codes") or []),
            "changes": _public_changes(
                trend.get("changes") if isinstance(trend.get("changes"), dict) else {}
            ),
            "substantive_count": int(trend.get("substantive_count") or len(substantive)),
            "observation_count": int(window.get("observation_count") or len(substantive)),
            "reopen_count": int(metrics.get("reopen_count") or 0),
            "active_duration_seconds": metrics.get("active_duration_seconds"),
            "last_substantive_change_at": metrics.get("last_substantive_change_at"),
            "worst_point": _public_worst(
                metrics.get("worst_point") if isinstance(metrics.get("worst_point"), dict) else None
            ),
            "window": {
                "n": window.get("n"),
                "dominant_direction": window.get("dominant_direction"),
                "min_current_value": window.get("min_current_value"),
                "max_current_value": window.get("max_current_value"),
                "min_affected_lead_count": window.get("min_affected_lead_count"),
                "max_affected_lead_count": window.get("max_affected_lead_count"),
                "worst_severity": window.get("worst_severity"),
            },
        },
        "history": {
            "substantive_snapshots": history_rows,
            "resolve_snapshot_count": sum(1 for s in snapshots if is_resolve_snapshot(s)),
        },
    }


def _strip_volatile_context(context: dict[str, Any]) -> dict[str, Any]:
    """Wall-clock duration must not bust cache between identical histories."""
    raw = json.loads(json.dumps(context, ensure_ascii=False))
    trend = raw.get("trend")
    if isinstance(trend, dict):
        trend.pop("active_duration_seconds", None)
    return raw


def compute_history_context_fingerprint(context: dict[str, Any]) -> str:
    stable = _strip_volatile_context(context)
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def compute_trend_fingerprint(trend: dict[str, Any]) -> str:
    """Stable hash of deterministic trend used for cache invalidation."""
    metrics = trend.get("metrics") if isinstance(trend.get("metrics"), dict) else {}
    slim = {
        "direction": trend.get("direction"),
        "reason_codes": trend.get("reason_codes"),
        "changes": trend.get("changes"),
        "substantive_count": trend.get("substantive_count"),
        "metrics": {
            "reopen_count": metrics.get("reopen_count"),
            "last_substantive_change_at": metrics.get("last_substantive_change_at"),
            "worst_point": metrics.get("worst_point"),
            "window": metrics.get("window"),
            # intentionally omit active_duration_seconds (changes every request)
        },
    }
    payload = json.dumps(slim, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

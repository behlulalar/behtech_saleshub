"""DE-5.1-B — public read-only trend DTO for diagnosis history API."""

from __future__ import annotations

from typing import Any

from database import DiagnosisCase, DiagnosisSnapshot
from intelligence.diagnosis.history_api import _iso, _load_json
from intelligence.diagnosis.trend import (
    DEFAULT_N_SNAPSHOTS,
    SnapshotChanges,
    compute_episode_metrics,
    compute_n_snapshot_trend,
    compute_trend_summary,
)


def _snapshot_row_to_trend_input(row: DiagnosisSnapshot) -> dict[str, Any]:
    """Internal dict for trend.py (may include fields stripped from public DTO)."""
    return {
        "id": row.id,
        "observed_at": _iso(row.observed_at) or "",
        "created_at": _iso(row.created_at) or "",
        "state": row.state,
        "severity": row.severity,
        "metric": row.metric or "",
        "current_value": row.current_value,
        "engine_previous_value": row.engine_previous_value,
        "change_percent": row.change_percent,
        "affected_lead_count": int(row.affected_lead_count or 0),
        "impact": _load_json(row.impact_json, {}),
        "top_leads": _load_json(row.top_leads_json, []),
        "fingerprint": row.fingerprint or "",
        "trigger": row.trigger or "",
    }


def public_trend_snapshot(snap: dict[str, Any] | None) -> dict[str, Any] | None:
    """Whitelist observation fields for API — no fingerprint / evidence / DB ids."""
    if not isinstance(snap, dict):
        return None
    return {
        "observed_at": str(snap.get("observed_at") or ""),
        "state": str(snap.get("state") or ""),
        "severity": str(snap.get("severity") or ""),
        "metric": str(snap.get("metric") or ""),
        "current_value": snap.get("current_value"),
        "change_percent": snap.get("change_percent"),
        "affected_lead_count": int(snap.get("affected_lead_count") or 0),
        "trigger": str(snap.get("trigger") or ""),
    }


def public_trend_changes(changes: SnapshotChanges) -> dict[str, Any]:
    return {
        "severity_from": changes.severity_from,
        "severity_to": changes.severity_to,
        "severity_delta": changes.severity_delta,
        "current_value_from": changes.current_value_from,
        "current_value_to": changes.current_value_to,
        "current_value_delta": changes.current_value_delta,
        "metric_direction": changes.metric_direction,
        "affected_lead_count_from": changes.affected_lead_count_from,
        "affected_lead_count_to": changes.affected_lead_count_to,
        "affected_lead_count_delta": changes.affected_lead_count_delta,
        "high_priority_count_from": changes.high_priority_count_from,
        "high_priority_count_to": changes.high_priority_count_to,
        "high_priority_count_delta": changes.high_priority_count_delta,
        "medium_priority_count_from": changes.medium_priority_count_from,
        "medium_priority_count_to": changes.medium_priority_count_to,
        "medium_priority_count_delta": changes.medium_priority_count_delta,
        "low_priority_count_from": changes.low_priority_count_from,
        "low_priority_count_to": changes.low_priority_count_to,
        "low_priority_count_delta": changes.low_priority_count_delta,
        "lead_set_added_count": len(changes.lead_set_added),
        "lead_set_removed_count": len(changes.lead_set_removed),
        "lead_set_size_from": len(changes.lead_set_from),
        "lead_set_size_to": len(changes.lead_set_to),
    }


def public_worst_point(worst: Any) -> dict[str, Any] | None:
    if worst is None:
        return None
    snap = getattr(worst, "snapshot", None) or {}
    return {
        "observed_at": str(snap.get("observed_at") or "") if isinstance(snap, dict) else "",
        "severity": str(getattr(worst, "severity", "") or ""),
        "metric": str(snap.get("metric") or "") if isinstance(snap, dict) else "",
        "current_value": getattr(worst, "current_value", None),
        "affected_lead_count": int(getattr(worst, "affected_lead_count", 0) or 0),
    }


def build_history_trend(
    case: DiagnosisCase,
    snapshots: list[DiagnosisSnapshot],
    *,
    n: int = DEFAULT_N_SNAPSHOTS,
) -> dict[str, Any]:
    """
    Build public trend block from full case snapshot history (not a page slice).

    Pure computation — does not write to DB.
    """
    dtype = (case.diagnosis_type or "").strip()
    inputs = [_snapshot_row_to_trend_input(s) for s in snapshots]
    summary = compute_trend_summary(
        inputs,
        diagnosis_type=dtype,
        case_state=case.state,
    )
    episode = compute_episode_metrics(
        diagnosis_type=dtype,
        snapshots=inputs,
        first_seen_at=case.first_seen_at,
        resolved_at=case.resolved_at,
        case_state=case.state,
    )
    window = compute_n_snapshot_trend(inputs, diagnosis_type=dtype, n=n)

    return {
        "direction": summary.direction,
        "reason_codes": list(summary.reason_codes),
        "changes": public_trend_changes(summary.changes),
        "previous_snapshot": public_trend_snapshot(summary.previous_snapshot),
        "current_snapshot": public_trend_snapshot(summary.current_snapshot),
        "substantive_count": summary.substantive_count,
        "metrics": {
            "active_duration_seconds": episode.active_duration_seconds,
            "last_substantive_change_at": episode.last_substantive_change_at,
            "reopen_count": episode.reopen_count,
            "substantive_count": episode.substantive_count,
            "total_snapshot_count": episode.total_snapshot_count,
            "worst_point": public_worst_point(episode.worst_point),
            "window": {
                "n": window.n,
                "observation_count": window.observation_count,
                "dominant_direction": window.dominant_direction,
                "min_current_value": window.min_current_value,
                "max_current_value": window.max_current_value,
                "min_affected_lead_count": window.min_affected_lead_count,
                "max_affected_lead_count": window.max_affected_lead_count,
                "worst_severity": window.worst_severity,
            },
        },
    }

"""DE-5.0 observation fingerprint (deterministic, exclude noisy fields)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from intelligence.diagnosis.lifecycle_constants import DIAGNOSIS_TYPE_FUNNEL


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _impact_counts(impact: dict[str, Any] | None) -> dict[str, int]:
    raw = impact if isinstance(impact, dict) else {}
    return {
        "high_priority_count": int(raw.get("high_priority_count") or 0),
        "medium_priority_count": int(raw.get("medium_priority_count") or 0),
        "low_priority_count": int(raw.get("low_priority_count") or 0),
    }


def _lead_ids(top_priority_leads: list[Any] | None) -> list[int]:
    ids: list[int] = []
    for row in top_priority_leads or []:
        if not isinstance(row, dict):
            continue
        lid = row.get("lead_id")
        if lid is None:
            continue
        try:
            ids.append(int(lid))
        except (TypeError, ValueError):
            continue
    return sorted(set(ids))


def _funnel_samples(evidence: dict[str, Any] | None) -> dict[str, int]:
    raw = evidence if isinstance(evidence, dict) else {}
    return {
        "sample_current_from": int(raw.get("sample_current_from") or 0),
        "sample_current_to": int(raw.get("sample_current_to") or 0),
    }


def observation_fingerprint_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Canonical payload for hashing — only substantive observation fields."""
    dtype = str(item.get("type") or item.get("diagnosis_type") or "")
    payload: dict[str, Any] = {
        "diagnosis_id": str(item.get("diagnosis_id") or ""),
        "diagnosis_type": dtype,
        "severity": str(item.get("severity") or ""),
        "metric": str(item.get("metric") or ""),
        "current_value": _num(item.get("current_value")),
        "engine_previous_value": _num(
            item.get("engine_previous_value")
            if "engine_previous_value" in item
            else item.get("previous_value")
        ),
        "change_percent": _num(item.get("change_percent")),
        "affected_lead_count": int(item.get("affected_lead_count") or 0),
        "impact": _impact_counts(item.get("impact") if isinstance(item.get("impact"), dict) else None),
    }
    if dtype == DIAGNOSIS_TYPE_FUNNEL:
        payload["funnel_samples"] = _funnel_samples(
            item.get("evidence") if isinstance(item.get("evidence"), dict) else None
        )
        payload["lead_ids"] = []
    else:
        payload["funnel_samples"] = {"sample_current_from": 0, "sample_current_to": 0}
        payload["lead_ids"] = _lead_ids(item.get("top_priority_leads"))
    return payload


def compute_observation_fingerprint(item: dict[str, Any]) -> str:
    payload = observation_fingerprint_payload(item)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def resolution_fingerprint(*, diagnosis_id: str, period_key: str) -> str:
    payload = {
        "kind": "resolved",
        "diagnosis_id": diagnosis_id,
        "period_key": period_key,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

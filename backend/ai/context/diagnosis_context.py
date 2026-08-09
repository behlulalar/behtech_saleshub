"""Deterministic whitelist context for DE-3 diagnosis interpretation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

_TOP_LEAD_KEYS = frozenset(
    {
        "lead_id",
        "lead_name",
        "durum",
        "existing_lead_score",
        "diagnosis_modifier",
        "diagnosis_priority_score",
        "priority",
        "reason_codes",
        "idle_days",
        "offer_age_days",
    }
)

_IMPACT_KEYS = frozenset(
    {
        "affected_lead_count",
        "high_priority_count",
        "medium_priority_count",
        "low_priority_count",
    }
)

_FUNNEL_EVIDENCE_KEYS = frozenset(
    {
        "from_stage",
        "to_stage",
        "current",
        "previous",
        "delta",
        "delta_percent",
        "sample_current_from",
        "sample_current_to",
        "sample_previous_from",
        "sample_previous_to",
        "current_period",
        "previous_period",
    }
)

_FOLLOWUP_EVIDENCE_KEYS = frozenset(
    {
        "affected_lead_count",
        "idle_contact_count",
        "no_contact_count",
        "oldest_days_idle",
        "average_days_idle",
        "threshold_medium_days",
        "threshold_high_days",
        "worst_case",
    }
)

_OFFER_EVIDENCE_KEYS = frozenset(
    {
        "pending_offer_count",
        "pending_with_reliable_age",
        "count_age_gte_medium",
        "count_age_gte_high",
        "average_offer_age_days",
        "max_offer_age_days",
        "threshold_medium_days",
        "threshold_high_days",
    }
)

_FORBIDDEN_EVIDENCE_KEYS = frozenset(
    {
        "sample_lead_ids",
    }
)


def _pick_evidence(diagnosis_type: str, evidence: dict[str, Any]) -> dict[str, Any]:
    raw = evidence or {}
    if diagnosis_type == "funnel_drop":
        allowed = _FUNNEL_EVIDENCE_KEYS
    elif diagnosis_type == "follow_up":
        allowed = _FOLLOWUP_EVIDENCE_KEYS
    elif diagnosis_type == "offer":
        allowed = _OFFER_EVIDENCE_KEYS
    else:
        allowed = frozenset()

    out: dict[str, Any] = {}
    for key in allowed:
        if key not in raw:
            continue
        value = raw[key]
        if key == "worst_case" and isinstance(value, dict):
            out[key] = {
                k: value[k]
                for k in ("days_idle", "reason")
                if k in value
            }
        else:
            out[key] = value

    for forbidden in _FORBIDDEN_EVIDENCE_KEYS:
        if forbidden in raw:
            continue
    return out


def _pick_impact(impact: dict[str, Any] | None) -> dict[str, int]:
    raw = impact or {}
    return {key: int(raw.get(key) or 0) for key in _IMPACT_KEYS}


def _pick_top_leads(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        picked = {k: row[k] for k in _TOP_LEAD_KEYS if k in row}
        if picked:
            out.append(picked)
    return out


def build_diagnosis_interpret_context(
    diagnosis: dict[str, Any],
    *,
    locale: str = "tr",
    period_type: str = "monthly",
    anchor: str = "",
) -> dict[str, Any]:
    """
    Build JSON-serializable context for LLM interpretation only.
    Does not include detected_at, raw notes, contact fields, or full lead lists.
    """
    dtype = str(diagnosis.get("type") or "")
    return {
        "locale": (locale or "tr")[:8],
        "period_type": period_type,
        "anchor": anchor,
        "diagnosis": {
            "diagnosis_id": diagnosis.get("diagnosis_id"),
            "type": dtype,
            "severity": diagnosis.get("severity"),
            "title": diagnosis.get("title"),
            "description": diagnosis.get("description"),
            "metric": diagnosis.get("metric"),
            "current_value": diagnosis.get("current_value"),
            "previous_value": diagnosis.get("previous_value"),
            "change_percent": diagnosis.get("change_percent"),
            "affected_lead_count": int(diagnosis.get("affected_lead_count") or 0),
        },
        "evidence": _pick_evidence(dtype, diagnosis.get("evidence") or {}),
        "impact": _pick_impact(diagnosis.get("impact")),
        "top_priority_leads": _pick_top_leads(diagnosis.get("top_priority_leads")),
        "affected_leads_available": bool(diagnosis.get("affected_leads_available", True)),
    }


def compute_context_fingerprint(context: dict[str, Any]) -> str:
    """Stable hash of interpret context for ai_runs cache (detected_at excluded by design)."""
    payload = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

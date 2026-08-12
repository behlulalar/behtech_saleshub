"""DE-5.0-C — read-only diagnosis case/history queries for API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from database import DiagnosisCase, DiagnosisSnapshot
from intelligence.diagnosis.lifecycle_constants import (
    DIAGNOSIS_TYPE_FOLLOW_UP,
    DIAGNOSIS_TYPE_FUNNEL,
    DIAGNOSIS_TYPE_OFFER,
    PERIOD_FUNNEL,
    PERIOD_KEY_CURRENT,
)
from intelligence.diagnosis.sync import _whitelist_evidence

_KNOWN_CURRENT_IDS = frozenset({"follow_up_idle_leads", "offer_pending_stale"})
_KNOWN_FUNNEL_IDS = frozenset({"funnel_offer_to_won_drop", "funnel_demo_to_offer_drop"})

PeriodResolveStatus = Literal["ok", "invalid", "ambiguous"]


@dataclass(frozen=True)
class PeriodKeyResolve:
    status: PeriodResolveStatus
    period_key: str | None = None


def default_period_key_for_diagnosis(diagnosis_id: str) -> str | None:
    did = (diagnosis_id or "").strip()
    if did in _KNOWN_CURRENT_IDS:
        return PERIOD_KEY_CURRENT
    if did in _KNOWN_FUNNEL_IDS:
        return "monthly"
    return None


def resolve_history_period_key(
    db: Session,
    *,
    organization_id: int,
    diagnosis_id: str,
    period_key: str | None,
) -> PeriodKeyResolve:
    """
    Resolve period_key for history lookup.

    - Explicit invalid period_key → invalid (HTTP 422)
    - Ambiguous (multiple cases, no key, unknown id) → ambiguous (HTTP 422)
    - Otherwise → ok with resolved key (missing case still → HTTP 404 at lookup)
    """
    did = (diagnosis_id or "").strip()
    if period_key is not None and str(period_key).strip() != "":
        pk = str(period_key).strip()
        if pk == PERIOD_KEY_CURRENT or pk in PERIOD_FUNNEL:
            return PeriodKeyResolve("ok", pk)
        return PeriodKeyResolve("invalid")

    inferred = default_period_key_for_diagnosis(did)
    if inferred:
        return PeriodKeyResolve("ok", inferred)

    rows = (
        db.query(DiagnosisCase.period_key)
        .filter(
            DiagnosisCase.organization_id == organization_id,
            DiagnosisCase.diagnosis_id == did,
        )
        .distinct()
        .all()
    )
    keys = [r[0] for r in rows]
    if len(keys) == 1:
        return PeriodKeyResolve("ok", keys[0])
    if len(keys) > 1:
        return PeriodKeyResolve("ambiguous")
    # Zero cases: still return a sentinel so lookup yields 404 (not 422).
    return PeriodKeyResolve("ok", PERIOD_KEY_CURRENT)


def get_case_for_org(
    db: Session,
    *,
    organization_id: int,
    diagnosis_id: str,
    period_key: str,
) -> DiagnosisCase | None:
    return (
        db.query(DiagnosisCase)
        .filter(
            DiagnosisCase.organization_id == organization_id,
            DiagnosisCase.diagnosis_id == diagnosis_id,
            DiagnosisCase.period_key == period_key,
        )
        .first()
    )


def _iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.isoformat()


def _load_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _infer_type(diagnosis_id: str) -> str:
    did = diagnosis_id or ""
    if did.startswith("funnel_"):
        return DIAGNOSIS_TYPE_FUNNEL
    if did.startswith("offer_"):
        return DIAGNOSIS_TYPE_OFFER
    if did.startswith("follow_up"):
        return DIAGNOSIS_TYPE_FOLLOW_UP
    return ""


def snapshot_to_api_dict(row: DiagnosisSnapshot, *, diagnosis_type: str | None = None) -> dict[str, Any]:
    evidence_raw = _load_json(row.evidence_json, {})
    dtype = (diagnosis_type or _infer_type(row.diagnosis_id)).strip()
    evidence = _whitelist_evidence(dtype, evidence_raw if isinstance(evidence_raw, dict) else {})
    impact = _load_json(row.impact_json, {})
    top_leads = _load_json(row.top_leads_json, [])
    return {
        "id": row.id,
        "observed_at": _iso(row.observed_at) or "",
        "state": row.state,
        "severity": row.severity,
        "metric": row.metric,
        "current_value": row.current_value,
        "engine_previous_value": row.engine_previous_value,
        "change_percent": row.change_percent,
        "affected_lead_count": int(row.affected_lead_count or 0),
        "impact": impact if isinstance(impact, dict) else {},
        "top_leads": top_leads if isinstance(top_leads, list) else [],
        "evidence": evidence,
        "fingerprint": row.fingerprint or "",
        "trigger": row.trigger or "",
        "created_at": _iso(row.created_at) or "",
    }


def case_history_to_api_dict(
    case: DiagnosisCase,
    snapshots: list[DiagnosisSnapshot],
    *,
    page: int,
    limit: int,
    total: int,
    trend: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "diagnosis_id": case.diagnosis_id,
        "diagnosis_type": case.diagnosis_type,
        "period_key": case.period_key,
        "state": case.state,
        "first_seen_at": _iso(case.first_seen_at),
        "last_seen_at": _iso(case.last_seen_at),
        "last_synced_at": _iso(case.last_synced_at),
        "resolved_at": _iso(case.resolved_at),
        "latest_snapshot_id": case.latest_snapshot_id,
        "page": page,
        "limit": limit,
        "total": total,
        "snapshots": [
            snapshot_to_api_dict(s, diagnosis_type=case.diagnosis_type) for s in snapshots
        ],
    }
    if trend is not None:
        payload["trend"] = trend
    return payload


def list_case_snapshots(
    db: Session,
    *,
    case_id: int,
    organization_id: int,
    page: int,
    limit: int,
) -> tuple[list[DiagnosisSnapshot], int]:
    q = db.query(DiagnosisSnapshot).filter(
        DiagnosisSnapshot.case_id == case_id,
        DiagnosisSnapshot.organization_id == organization_id,
    )
    total = q.count()
    rows = (
        q.order_by(DiagnosisSnapshot.observed_at.desc(), DiagnosisSnapshot.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return rows, total


def list_all_case_snapshots(
    db: Session,
    *,
    case_id: int,
    organization_id: int,
) -> list[DiagnosisSnapshot]:
    """Full history for trend (ascending by observed_at)."""
    return (
        db.query(DiagnosisSnapshot)
        .filter(
            DiagnosisSnapshot.case_id == case_id,
            DiagnosisSnapshot.organization_id == organization_id,
        )
        .order_by(DiagnosisSnapshot.observed_at.asc(), DiagnosisSnapshot.id.asc())
        .all()
    )

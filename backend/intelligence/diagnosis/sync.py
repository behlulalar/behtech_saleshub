"""DE-5.0-B — persist compute_diagnoses() into DiagnosisCase / DiagnosisSnapshot."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app_timezone import local_today
from database import DiagnosisCase, DiagnosisSnapshot
from intelligence.diagnosis.engine import compute_diagnoses
from intelligence.diagnosis.fingerprint import (
    compute_observation_fingerprint,
    resolution_fingerprint,
)
from intelligence.diagnosis.direction import metric_direction, severity_delta
from intelligence.diagnosis.lifecycle_constants import (
    DIAGNOSIS_TYPE_FOLLOW_UP,
    DIAGNOSIS_TYPE_FUNNEL,
    DIAGNOSIS_TYPE_OFFER,
    PERIOD_FUNNEL,
    PERIOD_KEY_CURRENT,
    STATE_ACTIVE,
    STATE_IMPROVING,
    STATE_NEW,
    STATE_RESOLVED,
    STATE_WORSENING,
    TRIGGER_RESOLVE,
    TRIGGER_SYNC,
)


@dataclass
class DiagnosisSyncResult:
    created_cases: int = 0
    updated_cases: int = 0
    new_snapshots: int = 0
    resolved_cases: int = 0
    reopened_cases: int = 0
    unchanged_cases: int = 0
    period: str = "monthly"
    period_keys_in_scope: list[str] = field(default_factory=list)
    organization_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_period_key(diagnosis_type: str, period: str) -> str:
    dtype = (diagnosis_type or "").strip()
    p = (period or "monthly").strip()
    if p not in PERIOD_FUNNEL:
        p = "monthly"
    if dtype == DIAGNOSIS_TYPE_FUNNEL:
        return p
    return PERIOD_KEY_CURRENT


def period_keys_owned_by_sync(period: str) -> set[str]:
    """Cases this sync is authoritative for (resolve scope)."""
    p = (period or "monthly").strip()
    if p not in PERIOD_FUNNEL:
        p = "monthly"
    return {p, PERIOD_KEY_CURRENT}


def _dump(data: Any) -> str:
    return json.dumps(data if data is not None else {}, ensure_ascii=False)


def _whitelist_evidence(dtype: str, evidence: dict[str, Any] | None) -> dict[str, Any]:
    raw = evidence if isinstance(evidence, dict) else {}
    if dtype == DIAGNOSIS_TYPE_FUNNEL:
        keys = (
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
        )
    elif dtype == DIAGNOSIS_TYPE_FOLLOW_UP:
        keys = (
            "affected_lead_count",
            "idle_contact_count",
            "no_contact_count",
            "oldest_days_idle",
            "threshold_medium_days",
            "threshold_high_days",
            "worst_case",
        )
    elif dtype == DIAGNOSIS_TYPE_OFFER:
        keys = (
            "pending_offer_count",
            "pending_with_reliable_age",
            "count_age_gte_medium",
            "count_age_gte_high",
            "max_offer_age_days",
            "threshold_medium_days",
            "threshold_high_days",
        )
    else:
        return {}
    return {key: raw[key] for key in keys if key in raw}


def _compact_top_leads(rows: list[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        lid = row.get("lead_id")
        if lid is None:
            continue
        try:
            out.append(
                {
                    "lead_id": int(lid),
                    "priority": row.get("priority"),
                    "diagnosis_priority_score": row.get("diagnosis_priority_score"),
                }
            )
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda r: int(r["lead_id"]))
    return out


def compute_next_state(
    *,
    diagnosis_type: str,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    was_resolved: bool,
) -> str:
    if previous is None:
        return STATE_ACTIVE if was_resolved else STATE_NEW

    sev = severity_delta(str(previous.get("severity") or ""), str(current.get("severity") or ""))
    if sev > 0:
        return STATE_WORSENING
    if sev < 0:
        return STATE_IMPROVING

    try:
        old_f = float(previous["current_value"]) if previous.get("current_value") is not None else None
        new_f = float(current["current_value"]) if current.get("current_value") is not None else None
    except (TypeError, ValueError, KeyError):
        old_f, new_f = None, None
    md = metric_direction(diagnosis_type, old_f, new_f)
    if md > 0:
        return STATE_WORSENING
    if md < 0:
        return STATE_IMPROVING

    old_count = int(previous.get("affected_lead_count") or 0)
    new_count = int(current.get("affected_lead_count") or 0)
    if new_count > old_count:
        return STATE_WORSENING
    if new_count < old_count:
        return STATE_IMPROVING
    return STATE_ACTIVE


def _normalize_item(item: dict[str, Any], *, period: str, anchor: str) -> dict[str, Any]:
    dtype = str(item.get("type") or "")
    impact = item.get("impact") if isinstance(item.get("impact"), dict) else {}
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    return {
        "diagnosis_id": str(item.get("diagnosis_id") or ""),
        "diagnosis_type": dtype,
        "type": dtype,
        "period_key": canonical_period_key(dtype, period),
        "severity": str(item.get("severity") or "medium"),
        "title": str(item.get("title") or "")[:255],
        "metric": str(item.get("metric") or ""),
        "current_value": item.get("current_value"),
        "engine_previous_value": item.get("previous_value"),
        "previous_value": item.get("previous_value"),
        "change_percent": item.get("change_percent"),
        "affected_lead_count": int(item.get("affected_lead_count") or 0),
        "impact": {
            "high_priority_count": int(impact.get("high_priority_count") or 0),
            "medium_priority_count": int(impact.get("medium_priority_count") or 0),
            "low_priority_count": int(impact.get("low_priority_count") or 0),
            "affected_lead_count": int(impact.get("affected_lead_count") or 0),
        },
        "top_priority_leads": item.get("top_priority_leads") or [],
        "evidence": evidence,
        "anchor": anchor,
        "fingerprint": "",
    }


def _apply_present_fields(case: DiagnosisCase, obs: dict[str, Any], *, now: datetime, state: str) -> None:
    case.diagnosis_type = obs["diagnosis_type"]
    case.state = state
    case.severity = obs["severity"]
    case.title = obs["title"]
    case.metric = obs["metric"]
    case.current_value = obs["current_value"]
    case.engine_previous_value = obs["engine_previous_value"]
    case.change_percent = obs["change_percent"]
    case.affected_lead_count = obs["affected_lead_count"]
    case.fingerprint = obs["fingerprint"]
    case.last_seen_at = now
    case.last_synced_at = now
    case.resolved_at = None
    case.updated_at = now


def _create_snapshot(
    db: Session,
    *,
    case: DiagnosisCase,
    obs: dict[str, Any],
    state: str,
    now: datetime,
    trigger: str,
    fingerprint: str,
) -> DiagnosisSnapshot:
    snap = DiagnosisSnapshot(
        organization_id=case.organization_id,
        case_id=case.id,
        diagnosis_id=case.diagnosis_id,
        period_key=case.period_key,
        anchor=str(obs.get("anchor") or ""),
        observed_at=now,
        state=state,
        severity=str(obs.get("severity") or case.severity),
        metric=str(obs.get("metric") or case.metric),
        current_value=obs.get("current_value"),
        engine_previous_value=obs.get("engine_previous_value"),
        change_percent=obs.get("change_percent"),
        affected_lead_count=int(obs.get("affected_lead_count") or 0),
        impact_json=_dump(obs.get("impact") or {}),
        top_leads_json=_dump(_compact_top_leads(obs.get("top_priority_leads"))),
        evidence_json=_dump(
            _whitelist_evidence(str(obs.get("diagnosis_type") or ""), obs.get("evidence"))
        ),
        fingerprint=fingerprint,
        trigger=trigger,
        created_at=now,
    )
    db.add(snap)
    db.flush()
    case.latest_snapshot_id = snap.id
    return snap


def _get_case(
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


def _ensure_case(
    db: Session,
    *,
    organization_id: int,
    obs: dict[str, Any],
    now: datetime,
) -> tuple[DiagnosisCase, bool]:
    """Return (case, created). Uses savepoint on race."""
    existing = _get_case(
        db,
        organization_id=organization_id,
        diagnosis_id=obs["diagnosis_id"],
        period_key=obs["period_key"],
    )
    if existing is not None:
        return existing, False

    case = DiagnosisCase(
        organization_id=organization_id,
        diagnosis_id=obs["diagnosis_id"],
        diagnosis_type=obs["diagnosis_type"],
        period_key=obs["period_key"],
        state=STATE_NEW,
        severity=obs["severity"],
        title=obs["title"],
        metric=obs["metric"],
        current_value=obs["current_value"],
        engine_previous_value=obs["engine_previous_value"],
        change_percent=obs["change_percent"],
        affected_lead_count=obs["affected_lead_count"],
        fingerprint=obs["fingerprint"],
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
        resolved_at=None,
        created_at=now,
        updated_at=now,
    )
    try:
        with db.begin_nested():
            db.add(case)
            db.flush()
        return case, True
    except IntegrityError:
        raced = _get_case(
            db,
            organization_id=organization_id,
            diagnosis_id=obs["diagnosis_id"],
            period_key=obs["period_key"],
        )
        if raced is None:
            raise
        return raced, False


def sync_diagnoses(
    db: Session,
    organization_id: int,
    *,
    period: str = "monthly",
    anchor: date | None = None,
    trigger: str = TRIGGER_SYNC,
) -> DiagnosisSyncResult:
    """
    Unfiltered compute_diagnoses → upsert DiagnosisCase / DiagnosisSnapshot.

    Does not commit — caller owns the transaction boundary.
    """
    org_id = int(organization_id)
    period_norm = (period or "monthly").strip()
    if period_norm not in PERIOD_FUNNEL:
        period_norm = "monthly"
    owned_keys = period_keys_owned_by_sync(period_norm)
    result = DiagnosisSyncResult(
        organization_id=org_id,
        period=period_norm,
        period_keys_in_scope=sorted(owned_keys),
    )

    data = compute_diagnoses(
        db,
        org_id,
        period_type=period_norm,
        anchor=anchor,
        diagnosis_type=None,
        severity=None,
    )
    anchor_str = str(data.get("anchor") or (anchor or local_today()).isoformat())
    now = datetime.utcnow()

    present_keys: set[tuple[str, str]] = set()
    observations: list[dict[str, Any]] = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        obs = _normalize_item(raw, period=period_norm, anchor=anchor_str)
        if not obs["diagnosis_id"]:
            continue
        obs["fingerprint"] = compute_observation_fingerprint(obs)
        present_keys.add((obs["diagnosis_id"], obs["period_key"]))
        observations.append(obs)

    for obs in observations:
        case, created = _ensure_case(db, organization_id=org_id, obs=obs, now=now)
        was_resolved = case.state == STATE_RESOLVED

        if created:
            _apply_present_fields(case, obs, now=now, state=STATE_NEW)
            _create_snapshot(
                db,
                case=case,
                obs=obs,
                state=STATE_NEW,
                now=now,
                trigger=trigger,
                fingerprint=obs["fingerprint"],
            )
            result.created_cases += 1
            result.new_snapshots += 1
            continue

        if not was_resolved and case.fingerprint == obs["fingerprint"]:
            _apply_present_fields(case, obs, now=now, state=case.state)
            result.unchanged_cases += 1
            result.updated_cases += 1
            continue

        previous = {
            "severity": case.severity,
            "current_value": case.current_value,
            "affected_lead_count": case.affected_lead_count,
        }
        if was_resolved:
            state = STATE_ACTIVE
            result.reopened_cases += 1
        else:
            state = compute_next_state(
                diagnosis_type=obs["diagnosis_type"],
                previous=previous,
                current=obs,
                was_resolved=False,
            )

        _apply_present_fields(case, obs, now=now, state=state)
        _create_snapshot(
            db,
            case=case,
            obs=obs,
            state=state,
            now=now,
            trigger=trigger,
            fingerprint=obs["fingerprint"],
        )
        result.new_snapshots += 1
        result.updated_cases += 1

    open_cases = (
        db.query(DiagnosisCase)
        .filter(
            DiagnosisCase.organization_id == org_id,
            DiagnosisCase.period_key.in_(sorted(owned_keys)),
            DiagnosisCase.state != STATE_RESOLVED,
        )
        .all()
    )
    for case in open_cases:
        if (case.diagnosis_id, case.period_key) in present_keys:
            continue
        fp = resolution_fingerprint(diagnosis_id=case.diagnosis_id, period_key=case.period_key)
        case.state = STATE_RESOLVED
        case.resolved_at = now
        case.last_synced_at = now
        case.updated_at = now
        case.fingerprint = fp
        resolve_obs = {
            "diagnosis_type": case.diagnosis_type,
            "severity": case.severity,
            "metric": case.metric,
            "current_value": None,
            "engine_previous_value": None,
            "change_percent": None,
            "affected_lead_count": 0,
            "impact": {},
            "top_priority_leads": [],
            "evidence": {},
            "anchor": anchor_str,
        }
        _create_snapshot(
            db,
            case=case,
            obs=resolve_obs,
            state=STATE_RESOLVED,
            now=now,
            trigger=TRIGGER_RESOLVE,
            fingerprint=fp,
        )
        result.resolved_cases += 1
        result.new_snapshots += 1

    db.flush()
    return result

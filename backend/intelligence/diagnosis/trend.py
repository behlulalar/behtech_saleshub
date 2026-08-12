"""DE-5.1-A — deterministic diagnosis trend from snapshot history (pure, no I/O)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from intelligence.diagnosis.direction import coerce_float, metric_direction, severity_delta
from intelligence.diagnosis.lifecycle_constants import (
    DIAGNOSIS_TYPE_FUNNEL,
    SEVERITY_RANK,
    STATE_RESOLVED,
    TRIGGER_RESOLVE,
)

# Trend directions (product layer — not DiagnosisCase.state enum).
TREND_NEWLY_DETECTED = "newly_detected"
TREND_WORSENING = "worsening"
TREND_IMPROVING = "improving"
TREND_STABLE = "stable"
TREND_RESOLVED = "resolved"
TREND_REOPENED = "reopened"

ALLOWED_TREND_DIRECTIONS = frozenset(
    {
        TREND_NEWLY_DETECTED,
        TREND_WORSENING,
        TREND_IMPROVING,
        TREND_STABLE,
        TREND_RESOLVED,
        TREND_REOPENED,
    }
)

REASON_SEVERITY_INCREASED = "severity_increased"
REASON_SEVERITY_DECREASED = "severity_decreased"
REASON_METRIC_WORSENED = "metric_worsened"
REASON_METRIC_IMPROVED = "metric_improved"
REASON_AFFECTED_INCREASED = "affected_lead_count_increased"
REASON_AFFECTED_DECREASED = "affected_lead_count_decreased"
REASON_HIGH_PRIORITY_INCREASED = "high_priority_count_increased"
REASON_HIGH_PRIORITY_DECREASED = "high_priority_count_decreased"
REASON_LEAD_SET_INCREASED = "lead_set_increased"
REASON_LEAD_SET_DECREASED = "lead_set_decreased"

DEFAULT_N_SNAPSHOTS = 5


@dataclass
class SnapshotChanges:
    severity_delta: int = 0
    severity_from: str | None = None
    severity_to: str | None = None
    current_value_from: float | None = None
    current_value_to: float | None = None
    current_value_delta: float | None = None
    metric_direction: int = 0
    affected_lead_count_from: int = 0
    affected_lead_count_to: int = 0
    affected_lead_count_delta: int = 0
    high_priority_count_from: int = 0
    high_priority_count_to: int = 0
    high_priority_count_delta: int = 0
    medium_priority_count_from: int = 0
    medium_priority_count_to: int = 0
    medium_priority_count_delta: int = 0
    low_priority_count_from: int = 0
    low_priority_count_to: int = 0
    low_priority_count_delta: int = 0
    lead_set_from: list[int] = field(default_factory=list)
    lead_set_to: list[int] = field(default_factory=list)
    lead_set_added: list[int] = field(default_factory=list)
    lead_set_removed: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotDiffResult:
    previous: dict[str, Any] | None
    current: dict[str, Any] | None
    diagnosis_type: str
    changes: SnapshotChanges
    reason_codes: list[str] = field(default_factory=list)
    direction: str = TREND_STABLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous": self.previous,
            "current": self.current,
            "diagnosis_type": self.diagnosis_type,
            "changes": self.changes.to_dict(),
            "reason_codes": list(self.reason_codes),
            "direction": self.direction,
        }


@dataclass
class TrendSummary:
    direction: str
    previous_snapshot: dict[str, Any] | None
    current_snapshot: dict[str, Any] | None
    changes: SnapshotChanges
    reason_codes: list[str] = field(default_factory=list)
    diagnosis_type: str = ""
    substantive_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "previous_snapshot": self.previous_snapshot,
            "current_snapshot": self.current_snapshot,
            "changes": self.changes.to_dict(),
            "reason_codes": list(self.reason_codes),
            "diagnosis_type": self.diagnosis_type,
            "substantive_count": self.substantive_count,
        }


@dataclass
class NSnapshotTrend:
    n: int
    observation_count: int
    dominant_direction: str
    min_current_value: float | None
    max_current_value: float | None
    min_affected_lead_count: int | None
    max_affected_lead_count: int | None
    worst_severity: str | None
    pair_directions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorstPoint:
    snapshot: dict[str, Any]
    severity: str
    current_value: float | None
    affected_lead_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot": self.snapshot,
            "severity": self.severity,
            "current_value": self.current_value,
            "affected_lead_count": self.affected_lead_count,
        }


@dataclass
class EpisodeMetrics:
    active_duration_seconds: float | None
    last_substantive_change_at: str | None
    reopen_count: int
    worst_point: WorstPoint | None
    substantive_count: int
    total_snapshot_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_duration_seconds": self.active_duration_seconds,
            "last_substantive_change_at": self.last_substantive_change_at,
            "reopen_count": self.reopen_count,
            "worst_point": self.worst_point.to_dict() if self.worst_point else None,
            "substantive_count": self.substantive_count,
            "total_snapshot_count": self.total_snapshot_count,
        }


def is_resolve_snapshot(snap: dict[str, Any] | None) -> bool:
    if not isinstance(snap, dict):
        return False
    if str(snap.get("trigger") or "").strip() == TRIGGER_RESOLVE:
        return True
    if str(snap.get("state") or "").strip() == STATE_RESOLVED:
        return True
    return False


def is_substantive_snapshot(snap: dict[str, Any] | None) -> bool:
    return isinstance(snap, dict) and not is_resolve_snapshot(snap)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _snap_sort_key(snap: dict[str, Any]) -> tuple:
    dt = _parse_dt(snap.get("observed_at")) or _parse_dt(snap.get("created_at"))
    sid = snap.get("id")
    try:
        sid_n = int(sid) if sid is not None else 0
    except (TypeError, ValueError):
        sid_n = 0
    # Missing timestamps sort first (oldest unknown).
    epoch = dt.timestamp() if dt is not None else float("-inf")
    return (epoch, sid_n)


def order_snapshots_ascending(snapshots: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    rows = [s for s in (snapshots or []) if isinstance(s, dict)]
    return sorted(rows, key=_snap_sort_key)


def filter_substantive_snapshots(
    snapshots: list[dict[str, Any]] | None,
    *,
    ascending: bool = True,
) -> list[dict[str, Any]]:
    ordered = order_snapshots_ascending(snapshots)
    substantive = [s for s in ordered if is_substantive_snapshot(s)]
    if ascending:
        return substantive
    return list(reversed(substantive))


def _impact_counts(snap: dict[str, Any] | None) -> dict[str, int]:
    raw = {}
    if isinstance(snap, dict):
        impact = snap.get("impact")
        if isinstance(impact, dict):
            raw = impact
        else:
            # Allow flat fields or pre-parsed impact_json already as dict under "impact".
            raw = {
                "high_priority_count": snap.get("high_priority_count"),
                "medium_priority_count": snap.get("medium_priority_count"),
                "low_priority_count": snap.get("low_priority_count"),
            }
    return {
        "high_priority_count": int(raw.get("high_priority_count") or 0),
        "medium_priority_count": int(raw.get("medium_priority_count") or 0),
        "low_priority_count": int(raw.get("low_priority_count") or 0),
    }


def _lead_ids(snap: dict[str, Any] | None) -> list[int]:
    if not isinstance(snap, dict):
        return []
    rows = snap.get("top_leads")
    if rows is None:
        rows = snap.get("top_priority_leads")
    ids: list[int] = []
    for row in rows or []:
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


def _affected_count(snap: dict[str, Any] | None) -> int:
    if not isinstance(snap, dict):
        return 0
    try:
        return int(snap.get("affected_lead_count") or 0)
    except (TypeError, ValueError):
        return 0


def compute_snapshot_changes(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    diagnosis_type: str,
) -> SnapshotChanges:
    sev_from = str(previous.get("severity") or "")
    sev_to = str(current.get("severity") or "")
    val_from = coerce_float(previous.get("current_value"))
    val_to = coerce_float(current.get("current_value"))
    md = metric_direction(diagnosis_type, val_from, val_to)
    aff_from = _affected_count(previous)
    aff_to = _affected_count(current)
    imp_from = _impact_counts(previous)
    imp_to = _impact_counts(current)
    leads_from = _lead_ids(previous)
    leads_to = _lead_ids(current)
    added = sorted(set(leads_to) - set(leads_from))
    removed = sorted(set(leads_from) - set(leads_to))
    value_delta: float | None = None
    if val_from is not None and val_to is not None:
        value_delta = val_to - val_from
    return SnapshotChanges(
        severity_delta=severity_delta(sev_from, sev_to),
        severity_from=sev_from or None,
        severity_to=sev_to or None,
        current_value_from=val_from,
        current_value_to=val_to,
        current_value_delta=value_delta,
        metric_direction=md,
        affected_lead_count_from=aff_from,
        affected_lead_count_to=aff_to,
        affected_lead_count_delta=aff_to - aff_from,
        high_priority_count_from=imp_from["high_priority_count"],
        high_priority_count_to=imp_to["high_priority_count"],
        high_priority_count_delta=imp_to["high_priority_count"] - imp_from["high_priority_count"],
        medium_priority_count_from=imp_from["medium_priority_count"],
        medium_priority_count_to=imp_to["medium_priority_count"],
        medium_priority_count_delta=(
            imp_to["medium_priority_count"] - imp_from["medium_priority_count"]
        ),
        low_priority_count_from=imp_from["low_priority_count"],
        low_priority_count_to=imp_to["low_priority_count"],
        low_priority_count_delta=imp_to["low_priority_count"] - imp_from["low_priority_count"],
        lead_set_from=leads_from,
        lead_set_to=leads_to,
        lead_set_added=added,
        lead_set_removed=removed,
    )


def reason_codes_from_changes(changes: SnapshotChanges) -> list[str]:
    codes: list[str] = []
    if changes.severity_delta > 0:
        codes.append(REASON_SEVERITY_INCREASED)
    elif changes.severity_delta < 0:
        codes.append(REASON_SEVERITY_DECREASED)
    if changes.metric_direction > 0:
        codes.append(REASON_METRIC_WORSENED)
    elif changes.metric_direction < 0:
        codes.append(REASON_METRIC_IMPROVED)
    if changes.affected_lead_count_delta > 0:
        codes.append(REASON_AFFECTED_INCREASED)
    elif changes.affected_lead_count_delta < 0:
        codes.append(REASON_AFFECTED_DECREASED)
    if changes.high_priority_count_delta > 0:
        codes.append(REASON_HIGH_PRIORITY_INCREASED)
    elif changes.high_priority_count_delta < 0:
        codes.append(REASON_HIGH_PRIORITY_DECREASED)
    if changes.lead_set_added and not changes.lead_set_removed:
        codes.append(REASON_LEAD_SET_INCREASED)
    elif changes.lead_set_removed and not changes.lead_set_added:
        codes.append(REASON_LEAD_SET_DECREASED)
    elif changes.lead_set_added and changes.lead_set_removed:
        # Net size change only when unambiguous growth/shrink.
        if len(changes.lead_set_to) > len(changes.lead_set_from):
            codes.append(REASON_LEAD_SET_INCREASED)
        elif len(changes.lead_set_to) < len(changes.lead_set_from):
            codes.append(REASON_LEAD_SET_DECREASED)
    return codes


def direction_from_changes(changes: SnapshotChanges) -> str:
    """Align with sync.compute_next_state priority: severity → metric → affected count."""
    if changes.severity_delta > 0:
        return TREND_WORSENING
    if changes.severity_delta < 0:
        return TREND_IMPROVING
    if changes.metric_direction > 0:
        return TREND_WORSENING
    if changes.metric_direction < 0:
        return TREND_IMPROVING
    if changes.affected_lead_count_delta > 0:
        return TREND_WORSENING
    if changes.affected_lead_count_delta < 0:
        return TREND_IMPROVING
    return TREND_STABLE


def diff_snapshots(
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
    *,
    diagnosis_type: str,
) -> SnapshotDiffResult:
    """Diff two snapshots. Resolve snapshots should not be passed as normal baselines."""
    dtype = (diagnosis_type or "").strip()
    if previous is None or current is None:
        return SnapshotDiffResult(
            previous=previous,
            current=current,
            diagnosis_type=dtype,
            changes=SnapshotChanges(),
            reason_codes=[],
            direction=TREND_STABLE,
        )
    if is_resolve_snapshot(previous) or is_resolve_snapshot(current):
        return SnapshotDiffResult(
            previous=previous,
            current=current,
            diagnosis_type=dtype,
            changes=SnapshotChanges(),
            reason_codes=[],
            direction=TREND_STABLE,
        )
    changes = compute_snapshot_changes(previous, current, diagnosis_type=dtype)
    codes = reason_codes_from_changes(changes)
    return SnapshotDiffResult(
        previous=previous,
        current=current,
        diagnosis_type=dtype,
        changes=changes,
        reason_codes=codes,
        direction=direction_from_changes(changes),
    )


def _empty_trend_summary(diagnosis_type: str = "") -> TrendSummary:
    return TrendSummary(
        direction=TREND_STABLE,
        previous_snapshot=None,
        current_snapshot=None,
        changes=SnapshotChanges(),
        reason_codes=[],
        diagnosis_type=(diagnosis_type or "").strip(),
        substantive_count=0,
    )


def compute_trend_summary(
    snapshots: list[dict[str, Any]] | None,
    *,
    diagnosis_type: str,
    case_state: str | None = None,
) -> TrendSummary:
    """
    Deterministic trend for a case history.

    Lifecycle Case.state is not mutated; `reopened` / `newly_detected` / `stable`
    are trend-layer directions only.
    """
    dtype = (diagnosis_type or "").strip()
    ordered = order_snapshots_ascending(snapshots)
    if not ordered:
        summary = _empty_trend_summary(dtype)
        if (case_state or "").strip() == STATE_RESOLVED:
            summary.direction = TREND_RESOLVED
        return summary

    substantive = [s for s in ordered if is_substantive_snapshot(s)]
    latest = ordered[-1]
    case_resolved = (case_state or "").strip() == STATE_RESOLVED or is_resolve_snapshot(latest)

    if case_resolved and (not substantive or is_resolve_snapshot(latest)):
        prev = substantive[-1] if substantive else None
        return TrendSummary(
            direction=TREND_RESOLVED,
            previous_snapshot=prev,
            current_snapshot=latest if is_resolve_snapshot(latest) else prev,
            changes=SnapshotChanges(),
            reason_codes=[],
            diagnosis_type=dtype,
            substantive_count=len(substantive),
        )

    if not substantive:
        return _empty_trend_summary(dtype)

    current = substantive[-1]
    # Immediate predecessor in full timeline is resolve → reopen event.
    cur_idx = ordered.index(current) if current in ordered else -1
    if cur_idx > 0 and is_resolve_snapshot(ordered[cur_idx - 1]):
        prev_sub = substantive[-2] if len(substantive) >= 2 else None
        if prev_sub is not None:
            diff = diff_snapshots(prev_sub, current, diagnosis_type=dtype)
            return TrendSummary(
                direction=TREND_REOPENED,
                previous_snapshot=prev_sub,
                current_snapshot=current,
                changes=diff.changes,
                reason_codes=diff.reason_codes,
                diagnosis_type=dtype,
                substantive_count=len(substantive),
            )
        return TrendSummary(
            direction=TREND_REOPENED,
            previous_snapshot=None,
            current_snapshot=current,
            changes=SnapshotChanges(),
            reason_codes=[],
            diagnosis_type=dtype,
            substantive_count=len(substantive),
        )

    if len(substantive) == 1:
        return TrendSummary(
            direction=TREND_NEWLY_DETECTED,
            previous_snapshot=None,
            current_snapshot=current,
            changes=SnapshotChanges(),
            reason_codes=[],
            diagnosis_type=dtype,
            substantive_count=1,
        )

    previous = substantive[-2]
    diff = diff_snapshots(previous, current, diagnosis_type=dtype)
    return TrendSummary(
        direction=diff.direction,
        previous_snapshot=previous,
        current_snapshot=current,
        changes=diff.changes,
        reason_codes=diff.reason_codes,
        diagnosis_type=dtype,
        substantive_count=len(substantive),
    )


def compute_n_snapshot_trend(
    snapshots: list[dict[str, Any]] | None,
    *,
    diagnosis_type: str,
    n: int = DEFAULT_N_SNAPSHOTS,
) -> NSnapshotTrend:
    dtype = (diagnosis_type or "").strip()
    try:
        limit = int(n)
    except (TypeError, ValueError):
        limit = DEFAULT_N_SNAPSHOTS
    if limit < 1:
        limit = DEFAULT_N_SNAPSHOTS

    substantive = filter_substantive_snapshots(snapshots, ascending=True)
    window = substantive[-limit:] if substantive else []
    values = [coerce_float(s.get("current_value")) for s in window]
    values_present = [v for v in values if v is not None]
    counts = [_affected_count(s) for s in window]

    pair_dirs: list[str] = []
    for i in range(1, len(window)):
        diff = diff_snapshots(window[i - 1], window[i], diagnosis_type=dtype)
        pair_dirs.append(diff.direction)

    worsen = sum(1 for d in pair_dirs if d == TREND_WORSENING)
    improve = sum(1 for d in pair_dirs if d == TREND_IMPROVING)
    if not pair_dirs:
        dominant = TREND_NEWLY_DETECTED if len(window) == 1 else TREND_STABLE
    elif worsen > improve:
        dominant = TREND_WORSENING
    elif improve > worsen:
        dominant = TREND_IMPROVING
    else:
        dominant = TREND_STABLE

    worst_sev = None
    best_rank = -1
    for s in window:
        sev = str(s.get("severity") or "").strip().lower()
        rank = SEVERITY_RANK.get(sev, -1)
        if rank > best_rank:
            best_rank = rank
            worst_sev = sev or None

    return NSnapshotTrend(
        n=limit,
        observation_count=len(window),
        dominant_direction=dominant,
        min_current_value=min(values_present) if values_present else None,
        max_current_value=max(values_present) if values_present else None,
        min_affected_lead_count=min(counts) if counts else None,
        max_affected_lead_count=max(counts) if counts else None,
        worst_severity=worst_sev,
        pair_directions=pair_dirs,
    )


def _metric_worse_key(diagnosis_type: str, value: float | None) -> float:
    """Higher key = worse observation for sorting."""
    if value is None:
        return float("-inf")
    if diagnosis_type == DIAGNOSIS_TYPE_FUNNEL:
        # Lower conversion is worse → invert.
        return -value
    return value


def select_worst_point(
    snapshots: list[dict[str, Any]] | None,
    *,
    diagnosis_type: str,
) -> WorstPoint | None:
    dtype = (diagnosis_type or "").strip()
    substantive = filter_substantive_snapshots(snapshots, ascending=True)
    if not substantive:
        return None

    def sort_key(snap: dict[str, Any]) -> tuple:
        sev = str(snap.get("severity") or "").strip().lower()
        rank = SEVERITY_RANK.get(sev, 0)
        val = coerce_float(snap.get("current_value"))
        aff = _affected_count(snap)
        # Ascending sort then take last: worse ranks last.
        return (rank, _metric_worse_key(dtype, val), aff, _snap_sort_key(snap))

    worst = max(substantive, key=sort_key)
    return WorstPoint(
        snapshot=worst,
        severity=str(worst.get("severity") or ""),
        current_value=coerce_float(worst.get("current_value")),
        affected_lead_count=_affected_count(worst),
    )


def count_reopens(snapshots: list[dict[str, Any]] | None) -> int:
    ordered = order_snapshots_ascending(snapshots)
    count = 0
    for i in range(1, len(ordered)):
        if is_resolve_snapshot(ordered[i - 1]) and is_substantive_snapshot(ordered[i]):
            count += 1
    return count


def last_substantive_change_at(
    snapshots: list[dict[str, Any]] | None,
    *,
    diagnosis_type: str = "",
) -> str | None:
    """
    observed_at of the latest substantive snapshot that differs from the prior
    substantive snapshot (field-level). First substantive counts as a change.
    """
    substantive = filter_substantive_snapshots(snapshots, ascending=True)
    if not substantive:
        return None
    if len(substantive) == 1:
        return _iso_or_str(substantive[0].get("observed_at"))

    dtype = (diagnosis_type or "").strip()
    last_change = substantive[0]
    for i in range(1, len(substantive)):
        diff = diff_snapshots(substantive[i - 1], substantive[i], diagnosis_type=dtype)
        if diff.direction != TREND_STABLE or diff.reason_codes:
            last_change = substantive[i]
        elif _snap_identity_changed(substantive[i - 1], substantive[i]):
            last_change = substantive[i]
    return _iso_or_str(last_change.get("observed_at"))


def _snap_identity_changed(a: dict[str, Any], b: dict[str, Any]) -> bool:
    fp_a = str(a.get("fingerprint") or "")
    fp_b = str(b.get("fingerprint") or "")
    if fp_a and fp_b and fp_a != fp_b:
        return True
    return False


def _iso_or_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def active_duration_seconds(
    *,
    first_seen_at: Any,
    resolved_at: Any = None,
    case_state: str | None = None,
    now: datetime | None = None,
) -> float | None:
    start = _parse_dt(first_seen_at)
    if start is None:
        return None
    if (case_state or "").strip() == STATE_RESOLVED or resolved_at is not None:
        end = _parse_dt(resolved_at)
        if end is None:
            return None
    else:
        end = now or datetime.utcnow()
    delta = (end - start).total_seconds()
    return max(0.0, float(delta))


def compute_episode_metrics(
    *,
    diagnosis_type: str,
    snapshots: list[dict[str, Any]] | None,
    first_seen_at: Any = None,
    resolved_at: Any = None,
    case_state: str | None = None,
    now: datetime | None = None,
) -> EpisodeMetrics:
    ordered = order_snapshots_ascending(snapshots)
    substantive = [s for s in ordered if is_substantive_snapshot(s)]
    return EpisodeMetrics(
        active_duration_seconds=active_duration_seconds(
            first_seen_at=first_seen_at,
            resolved_at=resolved_at,
            case_state=case_state,
            now=now,
        ),
        last_substantive_change_at=last_substantive_change_at(
            ordered, diagnosis_type=diagnosis_type
        ),
        reopen_count=count_reopens(ordered),
        worst_point=select_worst_point(ordered, diagnosis_type=diagnosis_type),
        substantive_count=len(substantive),
        total_snapshot_count=len(ordered),
    )

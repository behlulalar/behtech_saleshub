"""DE-5.1-A — deterministic diagnosis trend (pure functions)."""

from __future__ import annotations

from datetime import datetime, timedelta

from intelligence.diagnosis.lifecycle_constants import (
    DIAGNOSIS_TYPE_FOLLOW_UP,
    DIAGNOSIS_TYPE_FUNNEL,
    DIAGNOSIS_TYPE_OFFER,
    STATE_ACTIVE,
    STATE_RESOLVED,
    STATE_WORSENING,
)
from intelligence.diagnosis.sync import compute_next_state
from intelligence.diagnosis.trend import (
    REASON_AFFECTED_DECREASED,
    REASON_AFFECTED_INCREASED,
    REASON_HIGH_PRIORITY_INCREASED,
    REASON_LEAD_SET_INCREASED,
    REASON_METRIC_IMPROVED,
    REASON_METRIC_WORSENED,
    REASON_SEVERITY_DECREASED,
    REASON_SEVERITY_INCREASED,
    TREND_IMPROVING,
    TREND_NEWLY_DETECTED,
    TREND_REOPENED,
    TREND_RESOLVED,
    TREND_STABLE,
    TREND_WORSENING,
    compute_episode_metrics,
    compute_n_snapshot_trend,
    compute_trend_summary,
    diff_snapshots,
    filter_substantive_snapshots,
    is_resolve_snapshot,
    select_worst_point,
)


def _snap(
    *,
    sid: int,
    observed_at: str,
    severity: str = "medium",
    current_value: float | None = 7.0,
    affected: int = 1,
    state: str = "active",
    trigger: str = "sync",
    high: int = 0,
    medium: int = 0,
    low: int = 0,
    lead_ids: list[int] | None = None,
    fingerprint: str = "",
) -> dict:
    leads = [{"lead_id": lid, "priority": "high"} for lid in (lead_ids or [])]
    return {
        "id": sid,
        "observed_at": observed_at,
        "created_at": observed_at,
        "state": state,
        "severity": severity,
        "metric": "days_since_last_contact",
        "current_value": current_value,
        "affected_lead_count": affected,
        "impact": {
            "high_priority_count": high,
            "medium_priority_count": medium,
            "low_priority_count": low,
            "affected_lead_count": affected,
        },
        "top_leads": leads,
        "fingerprint": fingerprint or f"fp-{sid}",
        "trigger": trigger,
    }


def test_a_medium_to_high_worsening():
    prev = _snap(sid=1, observed_at="2026-01-01T00:00:00", severity="medium", current_value=7)
    cur = _snap(sid=2, observed_at="2026-01-02T00:00:00", severity="high", current_value=7)
    diff = diff_snapshots(prev, cur, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert diff.direction == TREND_WORSENING
    assert REASON_SEVERITY_INCREASED in diff.reason_codes
    summary = compute_trend_summary([prev, cur], diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert summary.direction == TREND_WORSENING


def test_b_high_to_medium_improving():
    prev = _snap(sid=1, observed_at="2026-01-01T00:00:00", severity="high", current_value=10)
    cur = _snap(sid=2, observed_at="2026-01-02T00:00:00", severity="medium", current_value=10)
    diff = diff_snapshots(prev, cur, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert diff.direction == TREND_IMPROVING
    assert REASON_SEVERITY_DECREASED in diff.reason_codes


def test_c_value_worsening_follow_up():
    prev = _snap(sid=1, observed_at="2026-01-01T00:00:00", severity="medium", current_value=5)
    cur = _snap(sid=2, observed_at="2026-01-02T00:00:00", severity="medium", current_value=12)
    diff = diff_snapshots(prev, cur, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert diff.direction == TREND_WORSENING
    assert REASON_METRIC_WORSENED in diff.reason_codes


def test_d_value_improving_follow_up():
    prev = _snap(sid=1, observed_at="2026-01-01T00:00:00", severity="medium", current_value=12)
    cur = _snap(sid=2, observed_at="2026-01-02T00:00:00", severity="medium", current_value=6)
    diff = diff_snapshots(prev, cur, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert diff.direction == TREND_IMPROVING
    assert REASON_METRIC_IMPROVED in diff.reason_codes


def test_e_affected_lead_count_increase():
    prev = _snap(
        sid=1, observed_at="2026-01-01T00:00:00", severity="medium", current_value=7, affected=1
    )
    cur = _snap(
        sid=2, observed_at="2026-01-02T00:00:00", severity="medium", current_value=7, affected=4
    )
    diff = diff_snapshots(prev, cur, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert diff.direction == TREND_WORSENING
    assert REASON_AFFECTED_INCREASED in diff.reason_codes
    assert diff.changes.affected_lead_count_delta == 3


def test_f_affected_lead_count_decrease():
    prev = _snap(
        sid=1, observed_at="2026-01-01T00:00:00", severity="medium", current_value=7, affected=4
    )
    cur = _snap(
        sid=2, observed_at="2026-01-02T00:00:00", severity="medium", current_value=7, affected=1
    )
    diff = diff_snapshots(prev, cur, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert diff.direction == TREND_IMPROVING
    assert REASON_AFFECTED_DECREASED in diff.reason_codes


def test_g_same_values_stable():
    prev = _snap(
        sid=1,
        observed_at="2026-01-01T00:00:00",
        severity="medium",
        current_value=7,
        affected=2,
        high=1,
        lead_ids=[10],
    )
    cur = _snap(
        sid=2,
        observed_at="2026-01-02T00:00:00",
        severity="medium",
        current_value=7,
        affected=2,
        high=1,
        lead_ids=[10],
    )
    diff = diff_snapshots(prev, cur, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert diff.direction == TREND_STABLE
    assert diff.reason_codes == []
    summary = compute_trend_summary([prev, cur], diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert summary.direction == TREND_STABLE


def test_h_resolve_snapshot_excluded_from_substantive_and_diff_baseline():
    a = _snap(sid=1, observed_at="2026-01-01T00:00:00", severity="medium", current_value=7)
    resolve = _snap(
        sid=2,
        observed_at="2026-01-02T00:00:00",
        severity="medium",
        current_value=None,
        affected=0,
        state=STATE_RESOLVED,
        trigger="resolve",
    )
    b = _snap(sid=3, observed_at="2026-01-03T00:00:00", severity="high", current_value=9)
    assert is_resolve_snapshot(resolve)
    substantive = filter_substantive_snapshots([a, resolve, b])
    assert [s["id"] for s in substantive] == [1, 3]
    # Diff refuses resolve as baseline → empty stable (not a normal observation pair).
    blocked = diff_snapshots(a, resolve, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert blocked.direction == TREND_STABLE
    assert blocked.reason_codes == []
    assert blocked.changes.severity_delta == 0


def test_i_resolved_then_active_reopened():
    a = _snap(sid=1, observed_at="2026-01-01T00:00:00", severity="medium", current_value=7)
    resolve = _snap(
        sid=2,
        observed_at="2026-01-02T00:00:00",
        current_value=None,
        affected=0,
        state=STATE_RESOLVED,
        trigger="resolve",
    )
    again = _snap(
        sid=3,
        observed_at="2026-01-03T00:00:00",
        severity="medium",
        current_value=8,
        state=STATE_ACTIVE,
    )
    summary = compute_trend_summary(
        [a, resolve, again], diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP
    )
    assert summary.direction == TREND_REOPENED
    assert summary.current_snapshot["id"] == 3
    # Case lifecycle enum still uses active on reopen — trend is separate.
    assert summary.direction != STATE_ACTIVE


def test_j_worst_point_selection():
    snaps = [
        _snap(sid=1, observed_at="2026-01-01T00:00:00", severity="low", current_value=20, affected=5),
        _snap(sid=2, observed_at="2026-01-02T00:00:00", severity="high", current_value=8, affected=1),
        _snap(sid=3, observed_at="2026-01-03T00:00:00", severity="high", current_value=15, affected=2),
        _snap(sid=4, observed_at="2026-01-04T00:00:00", severity="high", current_value=15, affected=9),
        _snap(
            sid=5,
            observed_at="2026-01-05T00:00:00",
            current_value=None,
            state=STATE_RESOLVED,
            trigger="resolve",
        ),
    ]
    worst = select_worst_point(snaps, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert worst is not None
    # severity high wins over low; among high, higher idle days; then higher affected.
    assert worst.snapshot["id"] == 4
    assert worst.severity == "high"
    assert worst.current_value == 15
    assert worst.affected_lead_count == 9


def test_k_n_snapshot_dominant_trend():
    snaps = [
        _snap(sid=1, observed_at="2026-01-01T00:00:00", severity="medium", current_value=5),
        _snap(sid=2, observed_at="2026-01-02T00:00:00", severity="medium", current_value=8),
        _snap(sid=3, observed_at="2026-01-03T00:00:00", severity="medium", current_value=11),
        _snap(sid=4, observed_at="2026-01-04T00:00:00", severity="medium", current_value=14),
    ]
    ntrend = compute_n_snapshot_trend(
        snaps, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP, n=5
    )
    assert ntrend.observation_count == 4
    assert ntrend.dominant_direction == TREND_WORSENING
    assert ntrend.min_current_value == 5
    assert ntrend.max_current_value == 14
    assert ntrend.worst_severity == "medium"
    assert len(ntrend.pair_directions) == 3


def test_l_funnel_metric_direction():
    # Higher conversion = improving
    prev = _snap(sid=1, observed_at="2026-01-01T00:00:00", severity="medium", current_value=0.20)
    better = _snap(sid=2, observed_at="2026-01-02T00:00:00", severity="medium", current_value=0.35)
    worse = _snap(sid=3, observed_at="2026-01-03T00:00:00", severity="medium", current_value=0.10)
    assert diff_snapshots(prev, better, diagnosis_type=DIAGNOSIS_TYPE_FUNNEL).direction == TREND_IMPROVING
    assert (
        REASON_METRIC_IMPROVED
        in diff_snapshots(prev, better, diagnosis_type=DIAGNOSIS_TYPE_FUNNEL).reason_codes
    )
    assert diff_snapshots(prev, worse, diagnosis_type=DIAGNOSIS_TYPE_FUNNEL).direction == TREND_WORSENING
    # Must not use follow_up polarity for funnel.
    assert diff_snapshots(prev, better, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP).direction == TREND_WORSENING


def test_m_follow_up_metric_direction():
    prev = _snap(sid=1, observed_at="2026-01-01T00:00:00", current_value=5)
    higher = _snap(sid=2, observed_at="2026-01-02T00:00:00", current_value=9)
    assert diff_snapshots(prev, higher, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP).direction == TREND_WORSENING


def test_n_offer_metric_direction():
    prev = _snap(sid=1, observed_at="2026-01-01T00:00:00", current_value=10)
    higher = _snap(sid=2, observed_at="2026-01-02T00:00:00", current_value=18)
    lower = _snap(sid=3, observed_at="2026-01-03T00:00:00", current_value=6)
    assert diff_snapshots(prev, higher, diagnosis_type=DIAGNOSIS_TYPE_OFFER).direction == TREND_WORSENING
    assert diff_snapshots(prev, lower, diagnosis_type=DIAGNOSIS_TYPE_OFFER).direction == TREND_IMPROVING


def test_o_reason_codes():
    prev = _snap(
        sid=1,
        observed_at="2026-01-01T00:00:00",
        severity="medium",
        current_value=5,
        affected=1,
        high=0,
        lead_ids=[1],
    )
    cur = _snap(
        sid=2,
        observed_at="2026-01-02T00:00:00",
        severity="high",
        current_value=12,
        affected=3,
        high=2,
        lead_ids=[1, 2],
    )
    codes = diff_snapshots(prev, cur, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP).reason_codes
    assert REASON_SEVERITY_INCREASED in codes
    assert REASON_METRIC_WORSENED in codes
    assert REASON_AFFECTED_INCREASED in codes
    assert REASON_HIGH_PRIORITY_INCREASED in codes
    assert REASON_LEAD_SET_INCREASED in codes


def test_p_empty_history_safe():
    summary = compute_trend_summary([], diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert summary.direction == TREND_STABLE
    assert summary.previous_snapshot is None
    assert summary.current_snapshot is None
    assert summary.reason_codes == []
    assert summary.substantive_count == 0

    ntrend = compute_n_snapshot_trend([], diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP, n=5)
    assert ntrend.observation_count == 0
    assert ntrend.dominant_direction == TREND_STABLE
    assert ntrend.min_current_value is None

    assert select_worst_point([], diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP) is None
    assert diff_snapshots(None, None, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP).direction == TREND_STABLE

    metrics = compute_episode_metrics(
        diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP,
        snapshots=[],
        first_seen_at=None,
    )
    assert metrics.reopen_count == 0
    assert metrics.worst_point is None
    assert metrics.active_duration_seconds is None


def test_newly_detected_single_substantive():
    only = _snap(sid=1, observed_at="2026-01-01T00:00:00")
    summary = compute_trend_summary([only], diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP)
    assert summary.direction == TREND_NEWLY_DETECTED


def test_resolved_case_direction():
    a = _snap(sid=1, observed_at="2026-01-01T00:00:00")
    resolve = _snap(
        sid=2,
        observed_at="2026-01-02T00:00:00",
        current_value=None,
        state=STATE_RESOLVED,
        trigger="resolve",
    )
    summary = compute_trend_summary(
        [a, resolve],
        diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP,
        case_state=STATE_RESOLVED,
    )
    assert summary.direction == TREND_RESOLVED


def test_funnel_worst_point_prefers_lower_conversion():
    snaps = [
        _snap(sid=1, observed_at="2026-01-01T00:00:00", severity="high", current_value=0.40),
        _snap(sid=2, observed_at="2026-01-02T00:00:00", severity="high", current_value=0.10),
    ]
    worst = select_worst_point(snaps, diagnosis_type=DIAGNOSIS_TYPE_FUNNEL)
    assert worst is not None
    assert worst.snapshot["id"] == 2


def test_episode_metrics_reopen_and_duration():
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    snaps = [
        _snap(sid=1, observed_at=t0.isoformat(), current_value=5),
        _snap(
            sid=2,
            observed_at=(t0 + timedelta(days=2)).isoformat(),
            current_value=None,
            state=STATE_RESOLVED,
            trigger="resolve",
        ),
        _snap(sid=3, observed_at=(t0 + timedelta(days=3)).isoformat(), current_value=8),
        _snap(
            sid=4,
            observed_at=(t0 + timedelta(days=4)).isoformat(),
            current_value=None,
            state=STATE_RESOLVED,
            trigger="resolve",
        ),
        _snap(sid=5, observed_at=(t0 + timedelta(days=5)).isoformat(), current_value=9),
    ]
    metrics = compute_episode_metrics(
        diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP,
        snapshots=snaps,
        first_seen_at=t0.isoformat(),
        case_state=STATE_ACTIVE,
        now=t0 + timedelta(days=5),
    )
    assert metrics.reopen_count == 2
    assert metrics.substantive_count == 3
    assert metrics.active_duration_seconds == 5 * 24 * 3600
    assert metrics.worst_point is not None
    assert metrics.last_substantive_change_at is not None


def test_sync_and_trend_direction_align():
    """Same previous/current fields → sync state and trend direction agree on worsen/improve/stable."""
    cases = [
        ({"severity": "medium", "current_value": 5, "affected_lead_count": 1},
         {"severity": "high", "current_value": 5, "affected_lead_count": 1},
         STATE_WORSENING, TREND_WORSENING, DIAGNOSIS_TYPE_FOLLOW_UP),
        ({"severity": "high", "current_value": 5, "affected_lead_count": 1},
         {"severity": "medium", "current_value": 5, "affected_lead_count": 1},
         "improving", TREND_IMPROVING, DIAGNOSIS_TYPE_FOLLOW_UP),
        ({"severity": "medium", "current_value": 5, "affected_lead_count": 1},
         {"severity": "medium", "current_value": 9, "affected_lead_count": 1},
         STATE_WORSENING, TREND_WORSENING, DIAGNOSIS_TYPE_FOLLOW_UP),
        ({"severity": "medium", "current_value": 0.2, "affected_lead_count": 0},
         {"severity": "medium", "current_value": 0.4, "affected_lead_count": 0},
         "improving", TREND_IMPROVING, DIAGNOSIS_TYPE_FUNNEL),
        ({"severity": "medium", "current_value": 0.4, "affected_lead_count": 0},
         {"severity": "medium", "current_value": 0.2, "affected_lead_count": 0},
         STATE_WORSENING, TREND_WORSENING, DIAGNOSIS_TYPE_FUNNEL),
        ({"severity": "medium", "current_value": 5, "affected_lead_count": 1},
         {"severity": "medium", "current_value": 5, "affected_lead_count": 1},
         STATE_ACTIVE, TREND_STABLE, DIAGNOSIS_TYPE_OFFER),
    ]
    for previous, current, sync_state, trend_dir, dtype in cases:
        assert compute_next_state(
            diagnosis_type=dtype, previous=previous, current=current, was_resolved=False
        ) == sync_state
        prev_s = _snap(
            sid=1,
            observed_at="2026-01-01T00:00:00",
            severity=previous["severity"],
            current_value=previous["current_value"],
            affected=previous["affected_lead_count"],
        )
        cur_s = _snap(
            sid=2,
            observed_at="2026-01-02T00:00:00",
            severity=current["severity"],
            current_value=current["current_value"],
            affected=current["affected_lead_count"],
        )
        assert diff_snapshots(prev_s, cur_s, diagnosis_type=dtype).direction == trend_dir


def test_n_parameter_window():
    snaps = [
        _snap(sid=i, observed_at=f"2026-01-{i:02d}T00:00:00", current_value=float(i))
        for i in range(1, 8)
    ]
    # Last 2: 6→7 worsening once
    ntrend = compute_n_snapshot_trend(snaps, diagnosis_type=DIAGNOSIS_TYPE_FOLLOW_UP, n=2)
    assert ntrend.n == 2
    assert ntrend.observation_count == 2
    assert ntrend.min_current_value == 6
    assert ntrend.max_current_value == 7

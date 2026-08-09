"""Central thresholds for deterministic diagnosis rules (DE-1)."""

from __future__ import annotations

# --- Funnel drop ---

FUNNEL_MIN_STAGE_DENOMINATOR = 5
"""Minimum leads in the *source* stage (denominator) in each period to compare rates."""

FUNNEL_MIN_RELATIVE_DROP_PERCENT = 20.0
"""Relative drop vs previous rate (e.g. 28→22.4 = -20%) required to emit funnel_drop."""

FUNNEL_MIN_ABSOLUTE_DROP_POINTS = 5.0
"""Also require at least this many percentage-point drop (guards tiny-rate noise)."""

# (from_stage_key, to_stage_key, metric_name, diagnosis_id_suffix)
FUNNEL_TRANSITIONS: tuple[tuple[str, str, str, str], ...] = (
    ("teklif", "satis", "offer_to_won_conversion", "funnel_offer_to_won_drop"),
    ("demo", "teklif", "demo_to_offer_conversion", "funnel_demo_to_offer_drop"),
)

# --- Follow-up idle ---

FOLLOWUP_IDLE_DAYS_MEDIUM = 5
FOLLOWUP_IDLE_DAYS_HIGH = 10
FOLLOWUP_MIN_AFFECTED_LEADS = 1

# --- Pending offers ---

PENDING_OFFER_STATUS = frozenset({"Teklif Verildi"})
OFFER_OLD_DAYS_MEDIUM = 5
OFFER_OLD_DAYS_HIGH = 10
OFFER_MIN_PENDING_WITH_AGE = 2
"""Minimum pending offers with reliable age to emit offer diagnosis."""

# --- DE-2 priority (aligned with rank_leads_for_org score bands) ---

PRIORITY_BAND_HIGH = 70
PRIORITY_BAND_MEDIUM = 45

DE2_TOP_LEADS_LIMIT = 10

NO_CONTACT_MODIFIER = 8
OFFER_AGE_MODIFIER_MEDIUM = 6
OFFER_AGE_MODIFIER_HIGH = 12

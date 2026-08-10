"""Deterministic deduplication of DE-3 recommended_actions before proposal bridge."""

from __future__ import annotations

from ai.actions.mapper import MAPPER_NO_ACTION, MapperContext, MapperInput, map_recommended_action
from schemas import DiagnosisRecommendedAction


def dedupe_recommended_actions_by_operation(
    recommendations: list[DiagnosisRecommendedAction],
    ctx: MapperContext,
) -> tuple[list[DiagnosisRecommendedAction], int]:
    """
    Collapse multiple LLM recommendations that map to the same (action_type, lead_id).
    Unmapped / NO_ACTION items are kept (they do not create proposals).
    """
    if not recommendations:
        return [], 0

    seen: set[tuple[str, int]] = set()
    kept: list[DiagnosisRecommendedAction] = []
    skipped = 0

    for rec in recommendations:
        mapped = map_recommended_action(
            MapperInput(title=rec.title, reason=rec.reason, priority=rec.priority),
            ctx,
        )
        if mapped.outcome == MAPPER_NO_ACTION or not mapped.action_type or not mapped.parameters:
            kept.append(rec)
            continue

        lead_id = int(mapped.parameters.get("lead_id", ctx.lead_id or 0))
        if lead_id <= 0:
            kept.append(rec)
            continue

        op_key = (mapped.action_type, lead_id)
        if op_key in seen:
            skipped += 1
            continue
        seen.add(op_key)
        kept.append(rec)

    return kept, skipped

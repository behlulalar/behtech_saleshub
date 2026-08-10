"""DE-4 Stage 4.4 — DE-3 recommended_actions → ai_actions (proposed only)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from ai.actions.mapper import MAPPER_NO_ACTION, MapperContext, MapperInput, map_recommended_action
from ai.actions.propose_service import ProposeValidationError, propose_ai_action
from ai.actions.recommendation_dedup import dedupe_recommended_actions_by_operation
from ai.actions.schemas import TARGET_ENTITY_LEAD, validate_idempotency_key
from schemas import DiagnosisRecommendedAction


@dataclass
class ProposalBridgeItemResult:
    recommendation_index: int
    outcome: str
    action_type: str | None = None
    action_id: str | None = None
    created: bool = False
    skip_reason: str | None = None


@dataclass
class ProposalBridgeSummary:
    recommendation_count: int = 0
    mapped_count: int = 0
    no_action_count: int = 0
    proposed_count: int = 0
    skipped_count: int = 0
    created_count: int = 0
    action_ids: list[str] = field(default_factory=list)
    items: list[ProposalBridgeItemResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_count": self.recommendation_count,
            "mapped_count": self.mapped_count,
            "no_action_count": self.no_action_count,
            "proposed_count": self.proposed_count,
            "skipped_count": self.skipped_count,
            "created_count": self.created_count,
            "action_ids": list(self.action_ids),
            "items": [
                {
                    "recommendation_index": i.recommendation_index,
                    "outcome": i.outcome,
                    "action_type": i.action_type,
                    "action_id": i.action_id,
                    "created": i.created,
                    "skip_reason": i.skip_reason,
                }
                for i in self.items
            ],
        }


def primary_lead_id_from_diagnosis_item(item: dict[str, Any]) -> int | None:
    for lead in item.get("top_priority_leads") or []:
        if not isinstance(lead, dict):
            continue
        lid = lead.get("lead_id")
        if lid is not None and int(lid) > 0:
            return int(lid)
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    wc = evidence.get("worst_case") if isinstance(evidence.get("worst_case"), dict) else {}
    lid = wc.get("lead_id")
    if lid is not None and int(lid) > 0:
        return int(lid)
    sample = evidence.get("sample_lead_ids") or []
    if sample:
        try:
            first = int(sample[0])
            if first > 0:
                return first
        except (TypeError, ValueError):
            pass
    return None


def build_bridge_idempotency_key(
    *,
    organization_id: int,
    diagnosis_id: str,
    interpret_run_id: int,
    recommendation_index: int,
    action_type: str,
    target_entity: str,
    target_entity_id: int,
) -> str:
    """Deterministic idempotency key (unique per org via DB constraint)."""
    payload = (
        f"org={organization_id}|dx={diagnosis_id}|run={interpret_run_id}|idx={recommendation_index}|"
        f"type={action_type}|ent={target_entity}|tid={target_entity_id}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]
    key = f"de3bridge-{digest}"
    out = validate_idempotency_key(key, required=True)
    assert out is not None
    return out


def bridge_recommended_actions_to_proposals(
    db: Session,
    *,
    user_id: int,
    org_id: int,
    role: str,
    diagnosis_id: str,
    interpret_run_id: int,
    recommended_actions: list[DiagnosisRecommendedAction],
    primary_lead_id: int | None,
    locale: str = "tr",
) -> ProposalBridgeSummary:
    """
    Map DE-3 recommendations to ai_actions (status=proposed). Never approve/execute.
    Per-item failures do not abort the batch.
    """
    summary = ProposalBridgeSummary(recommendation_count=len(recommended_actions or []))
    if not recommended_actions:
        return summary

    ctx = MapperContext(lead_id=primary_lead_id, diagnosis_id=diagnosis_id, locale=locale)
    recommended_actions, dedup_skipped = dedupe_recommended_actions_by_operation(recommended_actions, ctx)
    summary.skipped_count += dedup_skipped

    seen_operational: set[tuple[str, int]] = set()

    for index, rec in enumerate(recommended_actions):
        mapped = map_recommended_action(
            MapperInput(title=rec.title, reason=rec.reason, priority=rec.priority),
            ctx,
        )
        if mapped.outcome == MAPPER_NO_ACTION or not mapped.action_type or not mapped.parameters:
            summary.no_action_count += 1
            summary.items.append(
                ProposalBridgeItemResult(
                    recommendation_index=index,
                    outcome=MAPPER_NO_ACTION,
                    skip_reason=mapped.mapper_reason or "no_action",
                )
            )
            continue

        summary.mapped_count += 1
        lead_id_param = int(mapped.parameters.get("lead_id", primary_lead_id or 0))
        if lead_id_param <= 0:
            summary.skipped_count += 1
            summary.items.append(
                ProposalBridgeItemResult(
                    recommendation_index=index,
                    outcome="skipped",
                    action_type=mapped.action_type,
                    skip_reason="missing_lead_id",
                )
            )
            continue

        op_key = (mapped.action_type, lead_id_param)
        if op_key in seen_operational:
            summary.skipped_count += 1
            summary.items.append(
                ProposalBridgeItemResult(
                    recommendation_index=index,
                    outcome="skipped",
                    action_type=mapped.action_type,
                    skip_reason="duplicate_operational_recommendation",
                )
            )
            continue
        seen_operational.add(op_key)

        try:
            idem = build_bridge_idempotency_key(
                organization_id=org_id,
                diagnosis_id=diagnosis_id,
                interpret_run_id=interpret_run_id,
                recommendation_index=index,
                action_type=mapped.action_type,
                target_entity=TARGET_ENTITY_LEAD,
                target_entity_id=lead_id_param,
            )
        except ValueError:
            summary.skipped_count += 1
            summary.items.append(
                ProposalBridgeItemResult(
                    recommendation_index=index,
                    outcome="skipped",
                    action_type=mapped.action_type,
                    skip_reason="idempotency_key_invalid",
                )
            )
            continue

        reason = (rec.reason or rec.title or "")[:600]
        try:
            row, created = propose_ai_action(
                db,
                user_id=user_id,
                org_id=org_id,
                role=role,
                action_type=mapped.action_type,
                target_entity=TARGET_ENTITY_LEAD,
                target_entity_id=lead_id_param,
                parameters=mapped.parameters,
                reason=reason,
                source_diagnosis_id=diagnosis_id,
                source_interpret_run_id=interpret_run_id,
                idempotency_key=idem,
            )
        except ProposeValidationError as exc:
            summary.skipped_count += 1
            summary.items.append(
                ProposalBridgeItemResult(
                    recommendation_index=index,
                    outcome="skipped",
                    action_type=mapped.action_type,
                    skip_reason=exc.code,
                )
            )
            continue

        summary.proposed_count += 1
        if created:
            summary.created_count += 1
        if row.action_id not in summary.action_ids:
            summary.action_ids.append(row.action_id)
        summary.items.append(
            ProposalBridgeItemResult(
                recommendation_index=index,
                outcome="proposed",
                action_type=mapped.action_type,
                action_id=row.action_id,
                created=created,
            )
        )

    return summary

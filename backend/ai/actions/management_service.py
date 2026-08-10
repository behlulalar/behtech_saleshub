"""DE-4 action update / cancel (proposed-only management; no CRM mutation)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ai.actions.constants import EXECUTE_V1_ACTION_TYPES
from ai.actions.execute_service import ExecuteValidationError, _lock_action, _touch
from ai.actions.lifecycle import InvalidActionTransitionError, assert_transition
from ai.actions.propose_service import (
    ACTIVE_OPERATIONAL_DUPLICATE_STATUSES,
    ProposeValidationError,
    _parse_parameters_json,
    _validate_target_entity,
)
from ai.actions.registry import ActionParamsValidationError, validate_params
from database import AiAction

# Parameter keys owners may change while status=proposed.
EDITABLE_PARAMETER_KEYS: dict[str, frozenset[str]] = {
    "propose_follow_up_task": frozenset({"note"}),
    "propose_priority_change": frozenset({"priority"}),
    "propose_status_change": frozenset({"target_status"}),
    "propose_note_append": frozenset({"note_text", "separator"}),
    "propose_log_activity": frozenset({"activity_type", "title", "description"}),
}

UPDATE_SUPPORTED_ACTION_TYPES: frozenset[str] = frozenset(EDITABLE_PARAMETER_KEYS)


def _find_other_active_operational(
    db: Session,
    org_id: int,
    *,
    action_type: str,
    target_entity: str,
    target_entity_id: int,
    exclude_action_id: str,
) -> AiAction | None:
    entity = (target_entity or "").strip().lower()
    return (
        db.query(AiAction)
        .filter(
            AiAction.organization_id == org_id,
            AiAction.action_type == action_type,
            AiAction.target_entity == entity,
            AiAction.target_entity_id == int(target_entity_id),
            AiAction.status.in_(ACTIVE_OPERATIONAL_DUPLICATE_STATUSES),
            AiAction.action_id != exclude_action_id,
        )
        .order_by(AiAction.created_at.desc())
        .first()
    )


def update_ai_action(
    db: Session,
    *,
    org_id: int,
    role: str,
    action_id: str,
    parameters: dict[str, Any] | None,
) -> AiAction:
    _ = role  # owner enforced at router; keep signature aligned with execute/approve
    row = _lock_action(db, org_id, action_id)
    if not row:
        raise ExecuteValidationError("not_found", "Aksiyon bulunamadı")

    if row.status != "proposed":
        raise ExecuteValidationError(
            "invalid_status_for_update",
            "Yalnızca önerilmiş aksiyon düzenlenebilir",
        )

    if row.action_type not in UPDATE_SUPPORTED_ACTION_TYPES:
        raise ExecuteValidationError(
            "update_not_supported",
            "Bu aksiyon türü düzenlenemez",
        )

    incoming = parameters if isinstance(parameters, dict) else None
    if incoming is None:
        raise ExecuteValidationError("invalid_parameters", "parameters gerekli")

    editable = EDITABLE_PARAMETER_KEYS[row.action_type]
    allowed_keys = editable | {"lead_id"}
    unknown = set(incoming.keys()) - allowed_keys
    if unknown:
        raise ExecuteValidationError(
            "immutable_parameter",
            "Değiştirilemeyen veya desteklenmeyen parametre alanı",
        )

    if "lead_id" in incoming:
        try:
            req_lead = int(incoming["lead_id"])
        except (TypeError, ValueError) as exc:
            raise ExecuteValidationError("target_lead_mismatch", "Parametre lead_id hedef ile uyuşmuyor") from exc
        if not row.target_entity_id or req_lead != int(row.target_entity_id):
            raise ExecuteValidationError(
                "target_lead_mismatch",
                "Parametre lead_id hedef ile uyuşmuyor",
            )

    current = _parse_parameters_json(row.parameters_json)
    merged: dict[str, Any] = dict(current)
    for key in editable:
        if key in incoming:
            merged[key] = incoming[key]
    if not row.target_entity_id:
        raise ExecuteValidationError("invalid_parameters", "Hedef lead gerekli")
    merged["lead_id"] = int(row.target_entity_id)

    try:
        validated = validate_params(row.action_type, merged)
    except ActionParamsValidationError as exc:
        raise ExecuteValidationError("invalid_parameters", exc.detail) from exc

    validated_params = validated.model_dump(mode="json")
    try:
        _validate_target_entity(
            db,
            org_id,
            action_type=row.action_type,
            target_entity=row.target_entity,
            target_entity_id=row.target_entity_id,
            validated_params=validated_params,
        )
    except ProposeValidationError as exc:
        raise ExecuteValidationError(exc.code, exc.detail) from exc

    other = _find_other_active_operational(
        db,
        org_id,
        action_type=row.action_type,
        target_entity=row.target_entity,
        target_entity_id=int(row.target_entity_id),
        exclude_action_id=row.action_id,
    )
    if other:
        raise ExecuteValidationError(
            "operational_duplicate_conflict",
            "Aynı hedef için başka aktif öneri varken düzenlenemez",
        )

    # Identity / provenance fields intentionally untouched.
    row.parameters_json = json.dumps(validated_params, ensure_ascii=False)
    _touch(row)
    db.flush()
    return row


def cancel_ai_action(
    db: Session,
    *,
    org_id: int,
    role: str,
    action_id: str,
) -> AiAction:
    _ = role
    row = _lock_action(db, org_id, action_id)
    if not row:
        raise ExecuteValidationError("not_found", "Aksiyon bulunamadı")

    # Idempotent: already cancelled → return as-is (no CRM side effects).
    if row.status == "cancelled":
        return row

    if row.status != "proposed":
        raise ExecuteValidationError(
            "invalid_status_for_cancel",
            "Yalnızca önerilmiş aksiyon iptal edilebilir",
        )

    try:
        assert_transition("proposed", "cancelled")
    except InvalidActionTransitionError as exc:
        raise ExecuteValidationError("invalid_transition", str(exc)) from exc

    row.status = "cancelled"
    _touch(row)
    db.flush()
    return row


def is_update_supported(action_type: str) -> bool:
    return (action_type or "").strip() in UPDATE_SUPPORTED_ACTION_TYPES


# Keep EXECUTE_V1 alignment visible for callers / tests.
assert UPDATE_SUPPORTED_ACTION_TYPES <= EXECUTE_V1_ACTION_TYPES

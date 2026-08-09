"""DE-4 Stage 4.1 — persist action proposals (no CRM mutation)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai.actions.mapper import MAPPER_NO_ACTION, MapperContext, MapperInput, map_recommended_action
from ai.actions.registry import (
    ActionDisabledError,
    ActionNotAllowedForAiError,
    ActionParamsValidationError,
    UnknownActionTypeError,
    assert_proposable,
    validate_params,
)
from ai.actions.schemas import TARGET_ENTITY_LEAD, ActionStatus, validate_idempotency_key
from ai.actions.constants import EXECUTE_V1_ACTION_TYPES
from ai.store import get_run_for_org
from database import AiAction, Lead


class ProposeValidationError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


INITIAL_PROPOSE_STATUS: ActionStatus = "proposed"


def _parse_parameters_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def ai_action_to_dict(row: AiAction, *, lead_name: str | None = None) -> dict[str, Any]:
    from ai.actions.registry import get_policy

    policy = get_policy(row.action_type)
    exec_result: dict[str, Any] = {}
    raw_exec = getattr(row, "execution_result_json", None)
    if raw_exec:
        try:
            parsed = json.loads(raw_exec)
            if isinstance(parsed, dict):
                exec_result = parsed
        except json.JSONDecodeError:
            pass
    return {
        "action_id": row.action_id,
        "action_type": row.action_type,
        "target_entity": row.target_entity,
        "target_entity_id": row.target_entity_id,
        "parameters": _parse_parameters_json(row.parameters_json),
        "reason": row.reason or "",
        "source_diagnosis_id": row.source_diagnosis_id,
        "source_interpret_run_id": row.source_interpret_run_id,
        "status": row.status,
        "requires_confirmation": policy.requires_confirmation,
        "lead_name": lead_name,
        "idempotency_key": row.idempotency_key,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "executed_at": row.executed_at.isoformat() if row.executed_at else None,
        "execution_result": exec_result,
        "execute_enabled_v1": row.action_type in EXECUTE_V1_ACTION_TYPES,
    }


def _lead_name(db: Session, org_id: int, lead_id: int | None) -> str | None:
    if not lead_id:
        return None
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == org_id).first()
    if not lead:
        return None
    return (lead.isletme_adi or "").strip() or None


def _validate_target_entity(
    db: Session,
    org_id: int,
    *,
    action_type: str,
    target_entity: str,
    target_entity_id: int | None,
    validated_params: dict[str, Any],
) -> None:
    entity = (target_entity or "").strip().lower()
    if entity != TARGET_ENTITY_LEAD:
        raise ProposeValidationError("invalid_target_entity", "Geçersiz hedef varlık")

    if not target_entity_id or target_entity_id <= 0:
        raise ProposeValidationError("target_entity_id_required", "Hedef lead gerekli")

    param_lead = validated_params.get("lead_id")
    if param_lead is not None and int(param_lead) != int(target_entity_id):
        raise ProposeValidationError("target_lead_mismatch", "Parametre lead_id hedef ile uyuşmuyor")

    lead = db.query(Lead).filter(Lead.id == target_entity_id, Lead.user_id == org_id).first()
    if not lead:
        raise ProposeValidationError("target_not_in_org", "Lead bulunamadı veya erişim yok")


def _validate_sources(
    db: Session,
    org_id: int,
    *,
    source_interpret_run_id: int | None,
) -> None:
    if source_interpret_run_id is None:
        return
    run = get_run_for_org(db, org_id, source_interpret_run_id)
    if not run:
        raise ProposeValidationError("invalid_source_run", "Kaynak interpret run bulunamadı")


def get_ai_action_for_org(db: Session, org_id: int, action_id: str) -> AiAction | None:
    key = (action_id or "").strip()
    if not key:
        return None
    return (
        db.query(AiAction)
        .filter(AiAction.organization_id == org_id, AiAction.action_id == key)
        .first()
    )


def list_ai_actions_for_org(
    db: Session,
    org_id: int,
    *,
    status: str | None = "proposed",
    limit: int = 50,
) -> list[AiAction]:
    q = db.query(AiAction).filter(AiAction.organization_id == org_id)
    if status and status != "all":
        q = q.filter(AiAction.status == status)
    return q.order_by(AiAction.created_at.desc()).limit(limit).all()


def _find_by_idempotency(db: Session, org_id: int, idempotency_key: str) -> AiAction | None:
    return (
        db.query(AiAction)
        .filter(
            AiAction.organization_id == org_id,
            AiAction.idempotency_key == idempotency_key,
        )
        .first()
    )


def propose_ai_action(
    db: Session,
    *,
    user_id: int,
    org_id: int,
    role: str,
    action_type: str,
    target_entity: str,
    target_entity_id: int | None,
    parameters: dict[str, Any] | None,
    reason: str,
    source_diagnosis_id: str | None = None,
    source_interpret_run_id: int | None = None,
    idempotency_key: str | None = None,
) -> tuple[AiAction, bool]:
    """
    Persist a proposed action. Returns (row, created).
    On idempotency duplicate, returns existing row with created=False.
    """
    try:
        assert_proposable(action_type, role=role)
    except UnknownActionTypeError as exc:
        raise ProposeValidationError("unknown_action_type", str(exc)) from exc
    except ActionDisabledError as exc:
        raise ProposeValidationError("action_disabled", str(exc)) from exc
    except ActionNotAllowedForAiError as exc:
        raise ProposeValidationError("action_not_allowed", str(exc)) from exc
    except PermissionError as exc:
        raise ProposeValidationError("role_not_allowed", str(exc)) from exc

    try:
        normalized_key = validate_idempotency_key(idempotency_key, required=False)
    except ValueError as exc:
        raise ProposeValidationError("idempotency_key_invalid", str(exc)) from exc

    if normalized_key:
        existing = _find_by_idempotency(db, org_id, normalized_key)
        if existing:
            return existing, False

    try:
        validated_model = validate_params(action_type, parameters)
    except ActionParamsValidationError as exc:
        raise ProposeValidationError("invalid_parameters", exc.detail) from exc

    validated_params = validated_model.model_dump(mode="json")
    _validate_target_entity(
        db,
        org_id,
        action_type=action_type,
        target_entity=target_entity,
        target_entity_id=target_entity_id,
        validated_params=validated_params,
    )
    _validate_sources(db, org_id, source_interpret_run_id=source_interpret_run_id)

    now = datetime.utcnow()
    row = AiAction(
        action_id=str(uuid.uuid4()),
        organization_id=org_id,
        action_type=action_type.strip(),
        target_entity=(target_entity or TARGET_ENTITY_LEAD).strip().lower(),
        target_entity_id=target_entity_id,
        parameters_json=json.dumps(validated_params, ensure_ascii=False),
        reason=(reason or "")[:600],
        source_diagnosis_id=(source_diagnosis_id or None),
        source_interpret_run_id=source_interpret_run_id,
        requested_by=user_id,
        status=INITIAL_PROPOSE_STATUS,
        idempotency_key=normalized_key,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if normalized_key:
            existing = _find_by_idempotency(db, org_id, normalized_key)
            if existing:
                return existing, False
        raise
    return row, True


def propose_from_recommended_action(
    db: Session,
    *,
    user_id: int,
    org_id: int,
    role: str,
    title: str,
    reason: str,
    lead_id: int,
    priority: str | None = None,
    source_diagnosis_id: str | None = None,
    source_interpret_run_id: int | None = None,
    idempotency_key: str | None = None,
) -> tuple[AiAction | None, bool, str]:
    """Map DE-3 recommended action text → proposal. Returns (row|None, created, mapper_outcome)."""
    mapped = map_recommended_action(
        MapperInput(title=title, reason=reason, priority=priority),
        MapperContext(lead_id=lead_id, diagnosis_id=source_diagnosis_id),
    )
    if mapped.outcome == MAPPER_NO_ACTION or not mapped.action_type or not mapped.parameters:
        return None, False, mapped.outcome

    lead_id_param = int(mapped.parameters.get("lead_id", lead_id))
    row, created = propose_ai_action(
        db,
        user_id=user_id,
        org_id=org_id,
        role=role,
        action_type=mapped.action_type,
        target_entity=TARGET_ENTITY_LEAD,
        target_entity_id=lead_id_param,
        parameters=mapped.parameters,
        reason=reason or title,
        source_diagnosis_id=source_diagnosis_id,
        source_interpret_run_id=source_interpret_run_id,
        idempotency_key=idempotency_key,
    )
    return row, created, "mapped"

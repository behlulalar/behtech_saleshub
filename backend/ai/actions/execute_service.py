"""DE-4 Stage 4.2 — approve and execute (controlled CRM mutation)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ai.actions.executors import ExecuteResult
from ai.actions.lifecycle import InvalidActionTransitionError, assert_transition
from ai.actions.propose_service import (
    ProposeValidationError,
    _parse_parameters_json,
    _validate_target_entity,
    get_ai_action_for_org,
)
from ai.actions.registry import (
    ActionDisabledError,
    ActionNotAllowedForAiError,
    ActionParamsValidationError,
    UnknownActionTypeError,
    assert_executable,
    assert_proposable,
    validate_params,
)
from ai.actions.schemas import ActionStatus, validate_idempotency_key
from database import AiAction

from ai.actions.constants import EXECUTE_V1_ACTION_TYPES


class ExecuteValidationError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


def _lock_action(db: Session, org_id: int, action_id: str) -> AiAction | None:
    key = (action_id or "").strip()
    if not key:
        return None
    return (
        db.query(AiAction)
        .filter(AiAction.organization_id == org_id, AiAction.action_id == key)
        .with_for_update()
        .first()
    )


def _touch(row: AiAction) -> None:
    row.updated_at = datetime.utcnow()


def _execution_result_dict(row: AiAction) -> dict[str, Any]:
    raw = getattr(row, "execution_result_json", None) or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def approve_ai_action(
    db: Session,
    *,
    org_id: int,
    role: str,
    action_id: str,
) -> AiAction:
    row = _lock_action(db, org_id, action_id)
    if not row:
        raise ExecuteValidationError("not_found", "Aksiyon bulunamadı")

    if row.status in ("cancelled", "expired"):
        raise ExecuteValidationError(
            "invalid_status_for_approve",
            "İptal edilmiş veya süresi dolmuş aksiyon onaylanamaz",
        )
    if row.status != "proposed":
        raise ExecuteValidationError("invalid_status_for_approve", "Yalnızca önerilmiş aksiyon onaylanabilir")

    try:
        assert_proposable(row.action_type, role=role)
    except UnknownActionTypeError as exc:
        raise ExecuteValidationError("unknown_action_type", str(exc)) from exc
    except ActionDisabledError as exc:
        raise ExecuteValidationError("action_disabled", str(exc)) from exc
    except PermissionError as exc:
        raise ExecuteValidationError("role_not_allowed", str(exc)) from exc

    try:
        assert_transition("proposed", "approved")
    except InvalidActionTransitionError as exc:
        raise ExecuteValidationError("invalid_transition", str(exc)) from exc

    now = datetime.utcnow()
    row.status = "approved"
    row.approved_at = now
    _touch(row)
    db.flush()
    return row


def execute_ai_action(
    db: Session,
    *,
    org_id: int,
    role: str,
    actor_user_id: int,
    action_id: str,
) -> tuple[AiAction, bool, ExecuteResult | None]:
    """
    Run approved action. Returns (row, did_run_executor, result).
    If already executed, returns stored outcome without CRM mutation (did_run=False).
    """
    row = _lock_action(db, org_id, action_id)
    if not row:
        raise ExecuteValidationError("not_found", "Aksiyon bulunamadı")

    if row.status == "executed":
        stored = _execution_result_dict(row)
        return (
            row,
            False,
            ExecuteResult(
                success=True,
                message=stored.get("message", "already_executed"),
                dry_run=False,
                activity_id=stored.get("activity_id"),
            ),
        )

    if row.status == "executing":
        raise ExecuteValidationError("action_in_progress", "Aksiyon zaten uygulanıyor")

    if row.status == "failed":
        raise ExecuteValidationError("action_failed", "Başarısız aksiyon tekrar uygulanamaz")

    if row.status in ("cancelled", "expired"):
        raise ExecuteValidationError(
            "invalid_status_for_execute",
            "İptal edilmiş veya süresi dolmuş aksiyon uygulanamaz",
        )

    if row.status != "approved":
        raise ExecuteValidationError("invalid_status_for_execute", "Execute için aksiyon onaylı olmalı")

    if row.action_type not in EXECUTE_V1_ACTION_TYPES:
        raise ExecuteValidationError(
            "execute_not_enabled",
            "Bu aksiyon türü henüz execute edilemiyor",
        )

    try:
        normalized_key = validate_idempotency_key(row.idempotency_key, required=True)
    except ValueError as exc:
        raise ExecuteValidationError("idempotency_key_required", str(exc)) from exc
    assert normalized_key is not None

    try:
        definition = assert_executable(row.action_type, role=role)
    except UnknownActionTypeError as exc:
        raise ExecuteValidationError("unknown_action_type", str(exc)) from exc
    except ActionDisabledError as exc:
        raise ExecuteValidationError("action_disabled", str(exc)) from exc
    except ActionNotAllowedForAiError as exc:
        raise ExecuteValidationError("action_not_allowed", str(exc)) from exc
    except PermissionError as exc:
        raise ExecuteValidationError("role_not_allowed", str(exc)) from exc

    params_raw = _parse_parameters_json(row.parameters_json)
    try:
        validated = validate_params(row.action_type, params_raw)
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

    try:
        assert_transition("approved", "executing")
    except InvalidActionTransitionError as exc:
        raise ExecuteValidationError("invalid_transition", str(exc)) from exc

    row.status = "executing"
    _touch(row)
    db.flush()

    try:
        result = definition.executor.execute(
            db=db,
            organization_id=org_id,
            actor_user_id=actor_user_id,
            params=validated,
        )
    except Exception as exc:
        row.status = "failed"
        _touch(row)
        db.flush()
        raise ExecuteValidationError("executor_failed", "Aksiyon uygulanamadı") from exc

    if not result.success:
        row.status = "failed"
        _touch(row)
        db.flush()
        raise ExecuteValidationError("executor_failed", result.message or "Aksiyon uygulanamadı")

    try:
        assert_transition("executing", "executed")
    except InvalidActionTransitionError as exc:
        row.status = "failed"
        _touch(row)
        db.flush()
        raise ExecuteValidationError("invalid_transition", str(exc)) from exc

    now = datetime.utcnow()
    row.status = "executed"
    row.executed_at = now
    payload = {
        "message": result.message,
        "activity_id": result.activity_id,
        "action_type": row.action_type,
    }
    if result.result_payload:
        payload.update(result.result_payload)
    row.execution_result_json = json.dumps(payload, ensure_ascii=False)
    _touch(row)
    db.flush()
    return row, True, result

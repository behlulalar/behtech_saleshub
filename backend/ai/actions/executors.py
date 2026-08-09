"""DE-4 executors — Stage 4.2: LogActivityExecutor; others stub/blocked."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from activities import ACTIVITY_TYPES, log_activity
from ai.actions.schemas import ProposeLogActivityParams, ProposeNoteAppendParams
from database import Lead


class ActionExecutionNotImplementedError(RuntimeError):
    """Execute path disabled for this action type."""


@dataclass(frozen=True, slots=True)
class ExecuteResult:
    success: bool
    message: str
    dry_run: bool = True
    activity_id: int | None = None
    result_payload: dict[str, Any] | None = None


class ActionExecutor:
    """Base executor; subclasses perform CRM side effects when allowed."""

    def __init__(self, action_type: str) -> None:
        self.action_type = action_type

    def execute(
        self,
        *,
        db: Session,
        organization_id: int,
        actor_user_id: int,
        params: BaseModel,
        **_: Any,
    ) -> ExecuteResult:
        raise ActionExecutionNotImplementedError(
            f"execute_not_implemented:{self.action_type}"
        )


class LogActivityExecutor(ActionExecutor):
    """Stage 4.2 v1 — creates LeadActivity via activities.log_activity."""

    def execute(
        self,
        *,
        db: Session,
        organization_id: int,
        actor_user_id: int,
        params: BaseModel,
        **_: Any,
    ) -> ExecuteResult:
        if not isinstance(params, ProposeLogActivityParams):
            raise TypeError("invalid_params_type")
        title = (params.title or "").strip() or ACTIVITY_TYPES.get(
            params.activity_type, params.activity_type
        )
        activity = log_activity(
            db,
            user_id=organization_id,
            lead_id=params.lead_id,
            activity_type=params.activity_type,
            title=title[:255],
            description=(params.description or "")[:2000],
        )
        db.flush()
        return ExecuteResult(
            success=True,
            message="activity_created",
            dry_run=False,
            activity_id=activity.id,
        )


class NoteAppendExecutor(ActionExecutor):
    """Stage 4.3 — append text to Lead.notlar (org-scoped lead row)."""

    def execute(
        self,
        *,
        db: Session,
        organization_id: int,
        actor_user_id: int,
        params: BaseModel,
        **_: Any,
    ) -> ExecuteResult:
        _ = actor_user_id
        if not isinstance(params, ProposeNoteAppendParams):
            raise TypeError("invalid_params_type")
        lead = (
            db.query(Lead)
            .filter(Lead.id == params.lead_id, Lead.user_id == organization_id)
            .first()
        )
        if not lead:
            raise ValueError("lead_not_found")
        existing = lead.notlar or ""
        sep = params.separator or "\n\n"
        addition = params.note_text.strip()
        if existing.strip():
            lead.notlar = existing.rstrip() + sep + addition
        else:
            lead.notlar = addition
        db.flush()
        return ExecuteResult(
            success=True,
            message="note_appended",
            dry_run=False,
            result_payload={
                "lead_id": lead.id,
                "notlar_length_after": len(lead.notlar or ""),
            },
        )


class StubExecutor(ActionExecutor):
    def execute(
        self,
        *,
        db: Session,
        organization_id: int,
        actor_user_id: int,
        params: BaseModel,
        **_: Any,
    ) -> ExecuteResult:
        _ = (db, organization_id, actor_user_id, params)
        return ExecuteResult(
            success=False,
            message="executor_stub: CRM mutation not enabled for this action in Stage 4.2",
            dry_run=True,
        )


class BlockedExecutor(ActionExecutor):
    def execute(
        self,
        *,
        db: Session,
        organization_id: int,
        actor_user_id: int,
        params: BaseModel,
        **_: Any,
    ) -> ExecuteResult:
        _ = (db, organization_id, actor_user_id, params)
        raise ActionExecutionNotImplementedError("action_not_allowed_for_ai")

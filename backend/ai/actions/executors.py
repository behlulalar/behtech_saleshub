"""DE-4 executors — Stage 4.2: LogActivityExecutor; others stub/blocked."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from activities import ACTIVITY_TYPES, log_activity
from ai.actions.schemas import ProposeFollowUpTaskParams, ProposeLogActivityParams, ProposeNoteAppendParams
from app_timezone import local_today
from database import Lead
from intelligence.proposal_effects import _first_free_takip_slot


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


class FollowUpTaskExecutor(ActionExecutor):
    """Stage 4.9 — schedule follow-up on Lead.takip_1 / takip_2 (same CRM model as Faz 6)."""

    def execute(
        self,
        *,
        db: Session,
        organization_id: int,
        actor_user_id: int,
        params: BaseModel,
        **_: Any,
    ) -> ExecuteResult:
        if not isinstance(params, ProposeFollowUpTaskParams):
            raise TypeError("invalid_params_type")
        lead = (
            db.query(Lead)
            .filter(Lead.id == params.lead_id, Lead.user_id == organization_id)
            .first()
        )
        if not lead:
            raise ValueError("lead_not_found")

        today_iso = local_today().isoformat()
        slot = _first_free_takip_slot(lead, today_iso)
        note = (params.note or "").strip()
        if slot:
            effect = "Bugün için takip görevi planlandı"
            description = f"{note}: {effect} ({slot})" if note else f"{effect} ({slot})"
            activity = log_activity(
                db,
                user_id=actor_user_id,
                lead_id=lead.id,
                activity_type="takip_yapildi",
                title="DE-4 takip görevi",
                description=description[:2000],
            )
            db.flush()
            return ExecuteResult(
                success=True,
                message="follow_up_task_scheduled",
                dry_run=False,
                activity_id=activity.id,
                result_payload={
                    "lead_id": lead.id,
                    "takip_field": slot,
                    "scheduled_date": today_iso,
                    "task_scheduled": True,
                    "action_type": self.action_type,
                },
            )

        effect = "Takip alanları dolu — manuel planlayın"
        description = f"{note}: {effect}" if note else effect
        activity = log_activity(
            db,
            user_id=actor_user_id,
            lead_id=lead.id,
            activity_type="diger",
            title="DE-4 takip görevi",
            description=description[:2000],
        )
        db.flush()
        return ExecuteResult(
            success=True,
            message="follow_up_slots_full",
            dry_run=False,
            activity_id=activity.id,
            result_payload={
                "lead_id": lead.id,
                "takip_field": None,
                "scheduled_date": None,
                "task_scheduled": False,
                "action_type": self.action_type,
            },
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

"""DE-4 typed action parameters and contracts."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ai.actions.constants import (
    ALLOWED_ACTIVITY_TYPES,
    ALLOWED_LEAD_DURUM,
    ALLOWED_PRIORITIES,
    TARGET_ENTITY_LEAD,
)

# --- Enabled action types (Stage 4.0) ---

ExecutableActionType = Literal[
    "propose_follow_up_task",
    "propose_meeting_date",
    "propose_log_activity",
    "propose_note_append",
    "propose_priority_change",
    "propose_status_change",
    "open_whatsapp_draft",
]

BlockedRegistryActionType = Literal[
    "send_whatsapp_message",
    "delete_lead",
    "delete_activity",
    "delete_attachment",
    "bulk_import_leads",
    "record_sale",
    "revenue_mutation",
    "create_lead",
    "approve_lead_request",
    "intelligence_rescore",
]

ActionType = ExecutableActionType | BlockedRegistryActionType

ActionStatus = Literal[
    "proposed",
    "approved",
    "executing",
    "executed",
    "failed",
    "cancelled",
    "expired",
]

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{7,127}$")


class LeadTargetParams(BaseModel):
    lead_id: int = Field(gt=0)


class ProposeFollowUpTaskParams(LeadTargetParams):
    """Schedule follow-up (maps to takip fields / activity in later stages)."""

    note: str = Field(default="", max_length=400)


class ProposeMeetingDateParams(LeadTargetParams):
    meeting_date: date
    meeting_time: str = Field(default="", max_length=16)


class ProposeLogActivityParams(LeadTargetParams):
    activity_type: str = Field(min_length=1, max_length=50)
    title: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=2000)

    @field_validator("activity_type")
    @classmethod
    def _activity_type_known(cls, v: str) -> str:
        if v not in ALLOWED_ACTIVITY_TYPES:
            raise ValueError("invalid_activity_type")
        return v


class ProposeNoteAppendParams(LeadTargetParams):
    note_text: str = Field(min_length=1, max_length=4000)
    separator: str = Field(default="\n\n", max_length=8)


class ProposePriorityChangeParams(LeadTargetParams):
    priority: str = Field(min_length=1, max_length=20)

    @field_validator("priority")
    @classmethod
    def _priority_known(cls, v: str) -> str:
        if v not in ALLOWED_PRIORITIES:
            raise ValueError("invalid_priority")
        return v


class ProposeStatusChangeParams(LeadTargetParams):
    target_status: str = Field(min_length=1, max_length=100)

    @field_validator("target_status")
    @classmethod
    def _status_known(cls, v: str) -> str:
        if v not in ALLOWED_LEAD_DURUM:
            raise ValueError("invalid_target_status")
        return v


class OpenWhatsAppDraftParams(LeadTargetParams):
    """Client-side wa.me only — no server send."""

    message_draft: str = Field(min_length=1, max_length=2000)


class EmptyBlockedParams(BaseModel):
    """Placeholder for NOT_ALLOWED actions — cannot validate execute params."""


PARAM_MODEL_BY_TYPE: dict[str, type[BaseModel]] = {
    "propose_follow_up_task": ProposeFollowUpTaskParams,
    "propose_meeting_date": ProposeMeetingDateParams,
    "propose_log_activity": ProposeLogActivityParams,
    "propose_note_append": ProposeNoteAppendParams,
    "propose_priority_change": ProposePriorityChangeParams,
    "propose_status_change": ProposeStatusChangeParams,
    "open_whatsapp_draft": OpenWhatsAppDraftParams,
    "send_whatsapp_message": EmptyBlockedParams,
    "delete_lead": EmptyBlockedParams,
    "delete_activity": EmptyBlockedParams,
    "delete_attachment": EmptyBlockedParams,
    "bulk_import_leads": EmptyBlockedParams,
    "record_sale": EmptyBlockedParams,
    "revenue_mutation": EmptyBlockedParams,
    "create_lead": EmptyBlockedParams,
    "approve_lead_request": EmptyBlockedParams,
    "intelligence_rescore": EmptyBlockedParams,
}


def validate_idempotency_key(key: str | None, *, required: bool = False) -> str | None:
    if key is None or key == "":
        if required:
            raise ValueError("idempotency_key_required")
        return None
    k = key.strip()
    if not IDEMPOTENCY_KEY_PATTERN.match(k):
        raise ValueError("idempotency_key_invalid_format")
    return k


class ActionProposalContract(BaseModel):
    """In-memory / API contract for a proposed action (not yet persisted in 4.0)."""

    action_type: str = Field(min_length=1, max_length=80)
    organization_id: int = Field(gt=0)
    target_entity: str = Field(default=TARGET_ENTITY_LEAD, max_length=40)
    target_entity_id: int | None = Field(default=None, gt=0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", max_length=600)
    source_diagnosis_id: str | None = Field(default=None, max_length=80)
    source_interpret_run_id: int | None = Field(default=None, gt=0)
    requested_by: int = Field(gt=0)
    status: ActionStatus = "proposed"
    idempotency_key: str | None = None

    @model_validator(mode="after")
    def _normalize_idempotency(self) -> ActionProposalContract:
        self.idempotency_key = validate_idempotency_key(self.idempotency_key, required=False)
        return self


class IdempotencyScope(BaseModel):
    """Unique key scope for future persistence (org + key)."""

    organization_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=128)

    @field_validator("idempotency_key")
    @classmethod
    def _key_format(cls, v: str) -> str:
        out = validate_idempotency_key(v, required=True)
        assert out is not None
        return out

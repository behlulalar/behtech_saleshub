"""Central DE-4 action registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from ai.actions.executors import (
    ActionExecutor,
    BlockedExecutor,
    FollowUpTaskExecutor,
    LogActivityExecutor,
    NoteAppendExecutor,
    StatusChangeExecutor,
    StubExecutor,
)
from ai.actions.policies import ActionPolicy, PermissionClass
from ai.actions.schemas import PARAM_MODEL_BY_TYPE


class UnknownActionTypeError(LookupError):
    pass


class ActionDisabledError(PermissionError):
    pass


class ActionNotAllowedForAiError(PermissionError):
    pass


class ActionParamsValidationError(ValueError):
    def __init__(self, action_type: str, detail: str):
        super().__init__(detail)
        self.action_type = action_type
        self.detail = detail


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    action_type: str
    params_model: type[BaseModel]
    policy: ActionPolicy
    executor: ActionExecutor


def _policy(
    action_type: str,
    *,
    risk_level: str,
    permission: PermissionClass,
    requires_confirmation: bool,
    allowed_roles: frozenset[str],
    enabled: bool,
    description: str,
) -> ActionPolicy:
    return ActionPolicy(
        action_type=action_type,
        risk_level=risk_level,  # type: ignore[arg-type]
        permission=permission,
        requires_confirmation=requires_confirmation,
        allowed_roles=frozenset(allowed_roles),  # type: ignore[arg-type]
        enabled=enabled,
        description=description,
    )


def _build_registry() -> dict[str, ActionDefinition]:
    owner_only: frozenset[str] = frozenset({"owner"})
    entries: list[ActionDefinition] = []

    executable_specs: list[tuple[str, str, str, bool, str]] = [
        (
            "propose_follow_up_task",
            "low",
            "Plan follow-up task on lead (takip fields / activity)",
            True,
            "Schedule follow-up for a lead",
        ),
        (
            "propose_meeting_date",
            "medium",
            "Set meeting date on lead",
            True,
            "Propose görüşme date for a lead",
        ),
        (
            "propose_log_activity",
            "low",
            "Append timeline activity on lead",
            True,
            "Log CRM activity on a lead",
        ),
        (
            "propose_note_append",
            "low",
            "Append text to lead notes",
            True,
            "Append note on a lead",
        ),
        (
            "propose_priority_change",
            "medium",
            "Change lead priority (oncelik)",
            True,
            "Change lead priority",
        ),
        (
            "propose_status_change",
            "medium",
            "Change lead pipeline status (durum)",
            True,
            "Change lead status",
        ),
        (
            "open_whatsapp_draft",
            "low",
            "Return wa.me draft for client — no server send",
            True,
            "Open WhatsApp with prefilled message (client only)",
        ),
    ]

    for action_type, risk, desc, confirm, short in executable_specs:
        model = PARAM_MODEL_BY_TYPE[action_type]
        if action_type == "propose_log_activity":
            executor: ActionExecutor = LogActivityExecutor(action_type=action_type)
        elif action_type == "propose_note_append":
            executor = NoteAppendExecutor(action_type=action_type)
        elif action_type == "propose_follow_up_task":
            executor = FollowUpTaskExecutor(action_type=action_type)
        elif action_type == "propose_status_change":
            executor = StatusChangeExecutor(action_type=action_type)
        else:
            executor = StubExecutor(action_type=action_type)
        entries.append(
            ActionDefinition(
                action_type=action_type,
                params_model=model,
                policy=_policy(
                    action_type,
                    risk_level=risk,
                    permission="USER_CONFIRMATION_REQUIRED",
                    requires_confirmation=confirm,
                    allowed_roles=owner_only,
                    enabled=True,
                    description=short,
                ),
                executor=executor,
            )
        )

    blocked_specs: list[tuple[str, str, PermissionClass, str]] = [
        ("send_whatsapp_message", "critical", "NOT_ALLOWED_FOR_AI", "Server-side WhatsApp send"),
        ("delete_lead", "critical", "NOT_ALLOWED_FOR_AI", "Delete lead"),
        ("delete_activity", "high", "NOT_ALLOWED_FOR_AI", "Delete activity"),
        ("delete_attachment", "high", "NOT_ALLOWED_FOR_AI", "Delete attachment"),
        ("bulk_import_leads", "critical", "NOT_ALLOWED_FOR_AI", "Bulk import"),
        ("record_sale", "critical", "NOT_ALLOWED_FOR_AI", "Record sale / financial"),
        ("revenue_mutation", "critical", "NOT_ALLOWED_FOR_AI", "Revenue field mutation"),
        ("create_lead", "high", "NOT_ALLOWED_FOR_AI", "Create lead via AI"),
        ("approve_lead_request", "high", "ADMIN_ONLY", "Approve employee lead request"),
        ("intelligence_rescore", "high", "ADMIN_ONLY", "Batch intelligence rescore"),
    ]

    for action_type, risk, perm, desc in blocked_specs:
        enabled = False if perm == "NOT_ALLOWED_FOR_AI" else False
        entries.append(
            ActionDefinition(
                action_type=action_type,
                params_model=PARAM_MODEL_BY_TYPE[action_type],
                policy=_policy(
                    action_type,
                    risk_level=risk,
                    permission=perm,
                    requires_confirmation=True,
                    allowed_roles=owner_only if perm == "ADMIN_ONLY" else owner_only,
                    enabled=enabled,
                    description=desc,
                ),
                executor=BlockedExecutor(action_type=action_type),
            )
        )

    return {e.action_type: e for e in entries}


_REGISTRY: dict[str, ActionDefinition] = _build_registry()


def get(action_type: str) -> ActionDefinition:
    key = (action_type or "").strip()
    if key not in _REGISTRY:
        raise UnknownActionTypeError(key)
    return _REGISTRY[key]


def exists(action_type: str) -> bool:
    return (action_type or "").strip() in _REGISTRY


def get_policy(action_type: str) -> ActionPolicy:
    return get(action_type).policy


def validate_params(action_type: str, params: dict[str, Any] | None) -> BaseModel:
    definition = get(action_type)
    raw = params or {}
    try:
        return definition.params_model.model_validate(raw)
    except ValidationError as exc:
        raise ActionParamsValidationError(action_type, exc.errors()[0]["type"]) from exc


def assert_proposable(action_type: str, *, role: str = "owner") -> ActionDefinition:
    definition = get(action_type)
    policy = definition.policy
    if not policy.enabled:
        raise ActionDisabledError(action_type)
    if not policy.role_may_propose(role):
        raise PermissionError("role_not_allowed")
    return definition


def assert_executable(action_type: str, *, role: str = "owner") -> ActionDefinition:
    definition = get(action_type)
    policy = definition.policy
    if not policy.enabled:
        raise ActionDisabledError(action_type)
    if policy.permission == "NOT_ALLOWED_FOR_AI":
        raise ActionNotAllowedForAiError(action_type)
    if policy.permission == "READ_ONLY":
        raise ActionDisabledError(action_type)
    if not policy.role_may_execute(role):
        raise PermissionError("role_not_allowed")
    return definition


def list_available_actions(*, include_disabled: bool = False) -> list[ActionPolicy]:
    out: list[ActionPolicy] = []
    for definition in _REGISTRY.values():
        if not include_disabled and not definition.policy.enabled:
            continue
        if definition.policy.permission == "NOT_ALLOWED_FOR_AI":
            continue
        out.append(definition.policy)
    return sorted(out, key=lambda p: p.action_type)


def list_all_registered_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def register_external_action(_: ActionDefinition) -> None:
    """Registry is closed in Stage 4.0 — no runtime registration."""
    raise RuntimeError("registry_is_closed")

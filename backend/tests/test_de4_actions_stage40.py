"""DE-4 Stage 4.0 — action registry and contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai.actions import (
    MAPPER_NO_ACTION,
    ActionDisabledError,
    ActionNotAllowedForAiError,
    ActionParamsValidationError,
    InvalidActionTransitionError,
    MapperContext,
    MapperInput,
    UnknownActionTypeError,
    assert_executable,
    assert_transition,
    can_transition,
    exists,
    get,
    get_policy,
    list_available_actions,
    map_recommended_action,
    register_external_action,
    validate_params,
)
from ai.actions.executors import ActionExecutionNotImplementedError, StubExecutor
from ai.actions.registry import ActionDefinition
from ai.actions.schemas import (
    IdempotencyScope,
    ProposeFollowUpTaskParams,
    ProposeLogActivityParams,
    ProposeMeetingDateParams,
    ProposePriorityChangeParams,
    validate_idempotency_key,
)


def test_registry_contains_enabled_actions():
    assert exists("propose_log_activity")
    policy = get_policy("propose_log_activity")
    assert policy.enabled is True
    assert policy.requires_confirmation is True
    assert policy.permission == "USER_CONFIRMATION_REQUIRED"


def test_unknown_action_rejected():
    with pytest.raises(UnknownActionTypeError):
        get("not_a_real_action")


def test_validate_params_success():
    model = validate_params(
        "propose_log_activity",
        {
            "lead_id": 1,
            "activity_type": "takip_yapildi",
            "title": "T",
            "description": "D",
        },
    )
    assert isinstance(model, ProposeLogActivityParams)


def test_validate_params_invalid_enum():
    with pytest.raises(ActionParamsValidationError):
        validate_params(
            "propose_log_activity",
            {"lead_id": 1, "activity_type": "invalid_type_xyz"},
        )


def test_validate_params_missing_required_field():
    with pytest.raises(ActionParamsValidationError):
        validate_params("propose_status_change", {"lead_id": 1})


def test_priority_invalid_enum():
    with pytest.raises(ActionParamsValidationError):
        validate_params("propose_priority_change", {"lead_id": 1, "priority": "urgent"})


def test_policy_allowed_roles_owner_only():
    policy = get_policy("propose_follow_up_task")
    assert policy.role_may_propose("owner") is True
    assert policy.role_may_execute("owner") is True
    assert policy.role_may_execute("employee") is False


def test_blocked_action_not_allowed_for_ai():
    policy = get_policy("send_whatsapp_message")
    assert policy.permission == "NOT_ALLOWED_FOR_AI"
    assert policy.enabled is False
    with pytest.raises(ActionDisabledError):
        assert_executable("send_whatsapp_message", role="owner")
    with pytest.raises(ActionDisabledError):
        assert_executable("send_whatsapp_message", role="owner")


def test_not_allowed_raises_on_assert_executable():
    with pytest.raises(ActionDisabledError):
        assert_executable("delete_lead", role="owner")


def test_admin_only_rescore_disabled():
    policy = get_policy("intelligence_rescore")
    assert policy.permission == "ADMIN_ONLY"
    assert policy.enabled is False
    with pytest.raises(ActionDisabledError):
        assert_executable("intelligence_rescore", role="owner")


def test_list_available_excludes_blocked_and_disabled():
    types = {p.action_type for p in list_available_actions()}
    assert "propose_log_activity" in types
    assert "send_whatsapp_message" not in types
    assert "delete_lead" not in types


def test_state_transitions_valid():
    assert can_transition("proposed", "approved") is True
    assert_transition("proposed", "approved")
    assert_transition("approved", "executing")
    assert_transition("executing", "executed")


def test_state_transition_invalid():
    assert can_transition("proposed", "executed") is False
    with pytest.raises(InvalidActionTransitionError):
        assert_transition("proposed", "executed")


def test_idempotency_key_optional():
    assert validate_idempotency_key(None) is None


def test_idempotency_key_required_when_missing():
    with pytest.raises(ValueError, match="required"):
        validate_idempotency_key(None, required=True)


def test_idempotency_key_format():
    with pytest.raises(ValueError, match="invalid_format"):
        validate_idempotency_key("short")
    assert validate_idempotency_key("abc12345") == "abc12345"


def test_idempotency_scope_unique_org_key():
    scope = IdempotencyScope(organization_id=10, idempotency_key="action-key-001")
    assert scope.organization_id == 10


def test_registry_closed():
    with pytest.raises(RuntimeError, match="registry_is_closed"):
        register_external_action(
            ActionDefinition(
                action_type="evil",
                params_model=ProposePriorityChangeParams,
                policy=get_policy("propose_log_activity"),
                executor=StubExecutor(action_type="evil"),
            )
        )


def test_status_change_executor_is_real():
    ex = get("propose_status_change").executor
    from ai.actions.executors import StatusChangeExecutor

    assert isinstance(ex, StatusChangeExecutor)


def test_follow_up_executor_is_real():
    ex = get("propose_follow_up_task").executor
    from ai.actions.executors import FollowUpTaskExecutor

    assert isinstance(ex, FollowUpTaskExecutor)


def test_priority_change_executor_is_real():
    ex = get("propose_priority_change").executor
    from ai.actions.executors import PriorityChangeExecutor

    assert isinstance(ex, PriorityChangeExecutor)


def test_executor_stub_does_not_mutate():
    ex = get("propose_meeting_date").executor
    from unittest.mock import MagicMock

    result = ex.execute(
        db=MagicMock(),
        organization_id=1,
        actor_user_id=1,
        params=ProposeMeetingDateParams(
            lead_id=1,
            meeting_date=__import__("datetime").date(2026, 8, 10),
        ),
    )
    assert result.dry_run is True
    assert result.success is False


def test_log_activity_executor_is_real():
    ex = get("propose_log_activity").executor
    from ai.actions.executors import LogActivityExecutor

    assert isinstance(ex, LogActivityExecutor)


def test_note_append_executor_is_real():
    ex = get("propose_note_append").executor
    from ai.actions.executors import NoteAppendExecutor

    assert isinstance(ex, NoteAppendExecutor)


def test_blocked_executor_raises():
    from unittest.mock import MagicMock

    ex = get("send_whatsapp_message").executor
    with pytest.raises(ActionExecutionNotImplementedError):
        ex.execute(
            db=MagicMock(),
            organization_id=1,
            actor_user_id=1,
            params=validate_params("send_whatsapp_message", {}),
        )


def test_mapper_no_action_without_lead():
    r = map_recommended_action(
        MapperInput(title="Takip yap", reason="x"),
        MapperContext(lead_id=None),
    )
    assert r.outcome == MAPPER_NO_ACTION


def test_mapper_ambiguous_offer_follow_up():
    r = map_recommended_action(
        MapperInput(title="Teklifleri takip et", reason="5 teklif beklemede"),
        MapperContext(lead_id=42, diagnosis_id="offer_stale"),
    )
    assert r.outcome == MAPPER_NO_ACTION
    assert r.mapper_reason == "ambiguous_offer_follow_up"


def test_mapper_maps_follow_up_when_clear():
    r = map_recommended_action(
        MapperInput(title="Idle lead takip", reason="7 gündür temas yok"),
        MapperContext(lead_id=5),
    )
    assert r.outcome == "mapped"
    assert r.action_type == "propose_follow_up_task"
    assert r.parameters["lead_id"] == 5


def test_mapper_unknown_action_type_not_invented():
    r = map_recommended_action(
        MapperInput(title="???", reason="???"),
        MapperContext(lead_id=1),
    )
    assert r.outcome == MAPPER_NO_ACTION

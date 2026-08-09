"""DE-4 — AI Action layer (Stage 4.0 registry; Stage 4.1 propose persist)."""

from ai.actions.lifecycle import (
    InvalidActionTransitionError,
    assert_transition,
    can_transition,
    is_terminal,
)
from ai.actions.mapper import MAPPER_NO_ACTION, MapperContext, MapperInput, MapperResult, map_recommended_action
from ai.actions.registry import (
    ActionDisabledError,
    ActionNotAllowedForAiError,
    ActionParamsValidationError,
    UnknownActionTypeError,
    assert_executable,
    exists,
    get,
    get_policy,
    list_all_registered_types,
    list_available_actions,
    register_external_action,
    validate_params,
)

__all__ = [
    "MAPPER_NO_ACTION",
    "ActionDisabledError",
    "ActionNotAllowedForAiError",
    "ActionParamsValidationError",
    "InvalidActionTransitionError",
    "MapperContext",
    "MapperInput",
    "MapperResult",
    "UnknownActionTypeError",
    "assert_executable",
    "assert_transition",
    "can_transition",
    "exists",
    "get",
    "get_policy",
    "is_terminal",
    "list_all_registered_types",
    "list_available_actions",
    "map_recommended_action",
    "register_external_action",
    "validate_params",
]

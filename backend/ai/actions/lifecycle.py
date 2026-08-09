"""DE-4 action status transitions."""

from __future__ import annotations

from ai.actions.schemas import ActionStatus

TERMINAL_STATUSES: frozenset[ActionStatus] = frozenset(
    {"executed", "failed", "cancelled", "expired"}
)

ALLOWED_TRANSITIONS: dict[ActionStatus, frozenset[ActionStatus]] = {
    "proposed": frozenset({"approved", "cancelled", "expired"}),
    "approved": frozenset({"executing", "cancelled", "expired"}),
    "executing": frozenset({"executed", "failed"}),
    "executed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "expired": frozenset(),
}


class InvalidActionTransitionError(ValueError):
    pass


def can_transition(from_status: ActionStatus, to_status: ActionStatus) -> bool:
    if from_status == to_status:
        return True
    return to_status in ALLOWED_TRANSITIONS.get(from_status, frozenset())


def assert_transition(from_status: ActionStatus, to_status: ActionStatus) -> None:
    if not can_transition(from_status, to_status):
        raise InvalidActionTransitionError(f"invalid_transition:{from_status}->{to_status}")


def is_terminal(status: ActionStatus) -> bool:
    return status in TERMINAL_STATUSES

"""DE-4 action policies — permission and risk metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RiskLevel = Literal["low", "medium", "high", "critical"]
PermissionClass = Literal[
    "READ_ONLY",
    "USER_CONFIRMATION_REQUIRED",
    "ADMIN_ONLY",
    "NOT_ALLOWED_FOR_AI",
]
AllowedRole = Literal["owner", "employee"]


@dataclass(frozen=True, slots=True)
class ActionPolicy:
    action_type: str
    risk_level: RiskLevel
    permission: PermissionClass
    requires_confirmation: bool
    allowed_roles: frozenset[AllowedRole]
    enabled: bool
    description: str
    target_entity: str = "lead"

    def role_may_propose(self, role: str) -> bool:
        if not self.enabled:
            return False
        if self.permission == "NOT_ALLOWED_FOR_AI":
            return False
        if self.permission == "READ_ONLY":
            return True
        return role in self.allowed_roles

    def role_may_execute(self, role: str) -> bool:
        """Execute always requires enabled, non-read-only, allowed role (Stage 4.1+)."""
        if not self.enabled or self.permission in ("READ_ONLY", "NOT_ALLOWED_FOR_AI"):
            return False
        return role in self.allowed_roles

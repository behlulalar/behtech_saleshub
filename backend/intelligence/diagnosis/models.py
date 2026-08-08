"""Structured diagnosis DTOs (JSON-serializable, no ORM)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DiagnosisResult:
    diagnosis_id: str
    type: str
    severity: str
    title: str
    description: str
    metric: str
    current_value: float | None = None
    previous_value: float | None = None
    change_percent: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    affected_lead_count: int = 0
    detected_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

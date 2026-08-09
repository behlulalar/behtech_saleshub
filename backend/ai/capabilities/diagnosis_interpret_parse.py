"""DE-3 parse + safe failure classification (no raw output persistence)."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import ValidationError

from ai.llm_client import strip_llm_json_content
from schemas import DiagnosisInterpretation

ParseFailureReason = Literal[
    "empty_output",
    "invalid_json",
    "schema_validation_error",
    "missing_required_field",
    "invalid_enum",
    "malformed_structure",
    "unknown",
]


def _validation_path(loc: tuple | list) -> str:
    parts = [str(x) for x in loc if str(x) != "__root__"]
    return ".".join(parts)


def _reason_from_validation_error(err: dict) -> ParseFailureReason:
    err_type = str(err.get("type") or "")
    if err_type == "missing":
        return "missing_required_field"
    if err_type in ("enum", "literal_error"):
        return "invalid_enum"
    if "too_long" in err_type or "too_short" in err_type or "string_type" in err_type:
        return "schema_validation_error"
    if err_type in ("list_type", "dict_type", "model_type", "list_too_long"):
        return "malformed_structure"
    return "schema_validation_error"


def classify_parse_failure(raw: str) -> dict:
    """
    Classify why interpretation JSON could not be parsed/validated.
    Never includes raw text, values, or PII.
    """
    stripped = (raw or "").strip()
    if not stripped:
        return {"reason": "empty_output", "validation_path": None}

    normalized = strip_llm_json_content(stripped)
    try:
        obj = json.loads(normalized)
    except json.JSONDecodeError:
        tail = normalized.rstrip()
        if tail.startswith("{") and tail and not tail.endswith("}"):
            return {"reason": "malformed_structure", "validation_path": None}
        if not tail.startswith("{") and not tail.startswith("["):
            return {"reason": "invalid_json", "validation_path": None}
        return {"reason": "invalid_json", "validation_path": None}

    if not isinstance(obj, dict):
        return {"reason": "malformed_structure", "validation_path": None}

    try:
        DiagnosisInterpretation.model_validate(obj)
        return {"reason": "unknown", "validation_path": None}
    except ValidationError as ve:
        errors = ve.errors()
        if not errors:
            return {"reason": "unknown", "validation_path": None}
        first = errors[0]
        path = _validation_path(first.get("loc") or ())
        reason = _reason_from_validation_error(first)
        return {"reason": reason, "validation_path": path or None}


def try_parse_interpretation(raw: str) -> tuple[DiagnosisInterpretation | None, dict | None]:
    """Return (model, failure_meta). failure_meta is None on success."""
    stripped = (raw or "").strip()
    if not stripped:
        return None, {"reason": "empty_output", "validation_path": None}

    normalized = strip_llm_json_content(stripped)
    try:
        parsed = DiagnosisInterpretation.model_validate_json(normalized)
        return parsed, None
    except ValidationError:
        meta = classify_parse_failure(raw)
        return None, {"reason": meta["reason"], "validation_path": meta.get("validation_path")}
    except (json.JSONDecodeError, ValueError):
        meta = classify_parse_failure(raw)
        return None, {"reason": meta["reason"], "validation_path": meta.get("validation_path")}

"""Redact PII from agent run step logs before persistence."""

from __future__ import annotations

import copy
from typing import Any

from ai.snapshots.sanitize import sanitize_text

_PII_FIELD_KEYS = frozenset(
    {
        "whatsapp",
        "eposta",
        "email",
        "phone",
        "instagram",
        "yetkili",
        "isletme_adi",
    }
)


def _redact_string(value: str, *, field_key: str = "") -> str:
    if field_key in _PII_FIELD_KEYS:
        return sanitize_text(value, include_pii=False)
    return sanitize_text(value, include_pii=False)


def _redact_obj(value: Any, *, key: str = "") -> Any:
    if isinstance(value, str):
        return _redact_string(value, field_key=key)
    if isinstance(value, dict):
        return {k: _redact_obj(v, key=str(k).lower()) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_obj(item, key=key) for item in value]
    return value


def redact_run_step(step: dict) -> dict:
    """Return a copy safe to store in AiRun.steps_json."""
    out = copy.deepcopy(step)
    for text_key in ("raw", "text", "detail"):
        if text_key in out and isinstance(out[text_key], str):
            out[text_key] = _redact_string(out[text_key])[:500]
    if "result" in out:
        out["result"] = _redact_obj(out["result"])
    if "args" in out and isinstance(out["args"], dict):
        out["args"] = _redact_obj(out["args"])
    return out

"""Load DE-5.1-C diagnosis history interpret system prompt."""

from __future__ import annotations

import hashlib
from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parent / "diagnosis_history_interpret.md"


def prompt_version() -> str:
    raw = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.is_file() else ""
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"diagnosis_history_interpret.md@{digest}"


def system_prompt() -> str:
    if PROMPT_PATH.is_file():
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    return (
        "Teşhis geçmişi JSON context'ini yorumla; yalnızca geçerli JSON döndür. "
        "Aksiyon önerme. Trend hesaplama."
    )

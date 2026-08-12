"""DE-6.3-A — Sales Assistant conversation memory (context builder).

Bounded, org-scoped history for chat/stream.
DE-6.5: optional Redis working memory is a best-effort accelerator;
PostgreSQL remains authoritative (see ai.assistant_memory).
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from ai.conversations_store import (
    ROLE_ASSISTANT,
    ROLE_USER,
    get_conversation_for_org,
    list_messages_for_conversation,
)
from database import AssistantConversation, AssistantMessage

# Soft bounds — newest messages win; never unbounded prompts.
MAX_CONTEXT_MESSAGES = 12
MAX_CONTEXT_CHARS = 14_000
MAX_MESSAGE_CHARS = 2_000

# Deterministic placeholder when older turns are dropped (no LLM summarization).
TRUNCATION_PLACEHOLDER = (
    "[Önceki mesajlar bağlam limiti nedeniyle kısaltıldı. "
    "Yalnızca son konuşma özeti korunuyor.]"
)

# Internal identifiers that must not be echoed into model context.
_INTERNAL_KEY_RE = re.compile(
    r"(?i)\b(organization_id|org_id|user_id|fingerprint|run_id|"
    r"conversation_id|message_id|db_id|primary_key|lead_id)\b\s*[:=]\s*\S+"
)
_INTERNAL_JSON_KEY_RE = re.compile(
    r'(?i)"(organization_id|org_id|user_id|fingerprint|run_id|'
    r'conversation_id|message_id|lead_id)"\s*:\s*[^,}\]]+'
)
# Raw tool-result dumps should not be re-injected via history content.
_TOOL_DUMP_HINT_RE = re.compile(
    r'(?is)^\s*\{.*"ok"\s*:\s*(true|false).*"result"\s*:'
)


def resolve_owned_conversation(
    db: Session,
    *,
    organization_id: int,
    user_id: int,
    conversation_id: int,
    include_archived: bool = False,
) -> AssistantConversation | None:
    """Org + owner/employee user scope. None ⇒ safe not-found (no leak)."""
    conv = get_conversation_for_org(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        include_archived=include_archived,
    )
    if conv is None or conv.user_id != user_id:
        return None
    return conv


def sanitize_content_for_model(content: str, *, max_chars: int = MAX_MESSAGE_CHARS) -> str:
    """Strip internal ids / tool JSON dumps; cap length."""
    text = (content or "").strip()
    if not text:
        return ""
    if _TOOL_DUMP_HINT_RE.match(text):
        return "[CRM tool sonucu — ayrıntı tekrarlanmadı]"
    # Heuristic: large JSON blobs that look like internal payloads.
    if text.startswith("{") and len(text) > 400:
        try:
            data = json.loads(text)
            if isinstance(data, dict) and (
                "ok" in data or "organization_id" in data or "fingerprint" in data
            ):
                return "[Yapılandırılmış iç veri — bağlamda tekrarlanmadı]"
        except json.JSONDecodeError:
            pass
    text = _INTERNAL_JSON_KEY_RE.sub("", text)
    text = _INTERNAL_KEY_RE.sub("", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def _message_to_turn(row: AssistantMessage) -> dict[str, str] | None:
    if row.role not in (ROLE_USER, ROLE_ASSISTANT):
        return None
    content = sanitize_content_for_model(row.content or "")
    if not content:
        return None
    # Never include DB ids / run_id in model-facing turns.
    return {"role": row.role, "content": content}


def _truncate_newest_first(
    turns: list[dict[str, str]],
    *,
    max_messages: int,
    max_chars: int,
) -> tuple[list[dict[str, str]], bool]:
    """Keep newest turns within message + char budgets. Returns (turns, truncated)."""
    if not turns:
        return [], False

    budget_msgs = max(1, min(max_messages, MAX_CONTEXT_MESSAGES))
    budget_chars = max(500, min(max_chars, MAX_CONTEXT_CHARS))

    selected: list[dict[str, str]] = []
    used_chars = 0
    truncated = False

    for turn in reversed(turns):
        content = turn["content"]
        # Reserve room for optional truncation placeholder (~120 chars).
        if selected and (len(selected) >= budget_msgs or used_chars + len(content) > budget_chars - 140):
            truncated = True
            break
        selected.append(turn)
        used_chars += len(content)

    selected.reverse()
    if len(turns) > len(selected):
        truncated = True

    if truncated:
        placeholder = {
            "role": ROLE_ASSISTANT,
            "content": TRUNCATION_PLACEHOLDER,
        }
        # Ensure placeholder + selected still fit message budget.
        if len(selected) >= budget_msgs:
            selected = selected[-(budget_msgs - 1) :]
        selected = [placeholder, *selected]

    return selected, truncated


def build_conversation_history_for_llm(
    db: Session,
    *,
    organization_id: int,
    conversation_id: int,
    exclude_message_id: int | None = None,
    max_messages: int = MAX_CONTEXT_MESSAGES,
    max_chars: int = MAX_CONTEXT_CHARS,
) -> list[dict[str, str]]:
    """
    Load org-scoped messages and return sanitized user/assistant turns for the model.

    Does not include tool-role messages (those are ephemeral in the tool loop only).
    Keeps newest messages; may prepend a deterministic truncation placeholder.
    """
    # Fetch a bit more than max so char truncation can still choose newest dense turns.
    fetch_limit = max(max_messages * 2, max_messages + 4, 24)
    rows = list_messages_for_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        limit=fetch_limit,
    )

    turns: list[dict[str, str]] = []
    for row in rows:
        if exclude_message_id is not None and row.id == exclude_message_id:
            continue
        turn = _message_to_turn(row)
        if turn is not None:
            turns.append(turn)

    history, _truncated = _truncate_newest_first(
        turns,
        max_messages=max_messages,
        max_chars=max_chars,
    )
    return history


def build_chat_memory_context(
    db: Session,
    *,
    organization_id: int,
    user_id: int,
    conversation_id: int,
    exclude_message_id: int | None = None,
    max_messages: int = MAX_CONTEXT_MESSAGES,
    max_chars: int = MAX_CONTEXT_CHARS,
) -> tuple[AssistantConversation | None, list[dict[str, str]]]:
    """
    Resolve owned conversation + LLM history.

    Returns (None, []) when conversation is missing or not owned (caller → 404).
    """
    conv = resolve_owned_conversation(
        db,
        organization_id=organization_id,
        user_id=user_id,
        conversation_id=conversation_id,
        include_archived=False,
    )
    if conv is None:
        return None, []
    history = build_conversation_history_for_llm(
        db,
        organization_id=organization_id,
        conversation_id=conv.id,
        exclude_message_id=exclude_message_id,
        max_messages=max_messages,
        max_chars=max_chars,
    )
    return conv, history


def redact_context_bundle_for_model(bundle: Any) -> Any:
    """Drop internal keys from high-level CRM summary JSON before system prompt."""
    if isinstance(bundle, dict):
        out = {}
        for key, val in bundle.items():
            lk = str(key).lower()
            if lk in {
                "organization_id",
                "org_id",
                "user_id",
                "fingerprint",
                "run_id",
                "conversation_id",
                "message_id",
            }:
                continue
            out[key] = redact_context_bundle_for_model(val)
        return out
    if isinstance(bundle, list):
        return [redact_context_bundle_for_model(x) for x in bundle]
    return bundle

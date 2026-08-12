"""Sales chat SSE event stream."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from ai.assistant_memory import save_memory
from ai.capabilities.chat import SYSTEM_BASE, _build_context_block, _history_for_request
from ai.llm_client import assert_llm_configured, stream_chat_completion_messages
from ai.llm_config import provider_and_model
from ai.store import create_run, finish_run_failed, finish_run_success
from ai.usage import ensure_quota, record_usage
from database import User


def _build_messages(
    db: Session,
    *,
    user: User,
    org_id: int,
    message: str,
    history: list[dict] | None,
    locale: str,
) -> list[dict]:
    include_revenue = (user.account_type or "company") == "company"
    request_history = _history_for_request(db, user, org_id, history)
    context = _build_context_block(
        db,
        org_id,
        include_revenue=include_revenue,
        message=message,
    )
    system = (
        f"{SYSTEM_BASE}\nDil tercihi: {locale}\n\n"
        f"Güncel CRM özeti (JSON):\n{context}"
    )
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(request_history)
    messages.append({"role": "user", "content": message[:4000]})
    return messages


def iter_sales_chat_events(
    db: Session,
    *,
    user: User,
    org_id: int,
    message: str,
    history: list[dict] | None = None,
    locale: str = "tr",
) -> Iterator[dict[str, Any]]:
    """Yields delta, done and error events for the streaming assistant."""
    assert_llm_configured()
    ensure_quota(db, org_id, estimated_tokens=800)

    text = message.strip()
    if not text:
        yield {"type": "error", "detail": "empty_message"}
        return

    request_history = _history_for_request(db, user, org_id, history)
    messages = _build_messages(
        db,
        user=user,
        org_id=org_id,
        message=text,
        history=request_history,
        locale=locale,
    )
    provider, model = provider_and_model()
    run = create_run(
        db,
        org_id=org_id,
        requested_by=user.id,
        run_type="chat",
        input_data={"locale": locale, "message_len": len(text), "stream": True},
        provider=provider,
        model=model,
        prompt_version="sales_chat_v2",
    )
    db.flush()
    started = time.perf_counter()
    parts: list[str] = []
    usage: dict = {}

    try:
        for delta in stream_chat_completion_messages(messages=messages, usage_out=usage):
            parts.append(delta)
            yield {"type": "delta", "content": delta}

        reply = "".join(parts).strip()
        if not reply:
            duration_ms = int((time.perf_counter() - started) * 1000)
            finish_run_failed(db, run, error_code="empty_reply", duration_ms=duration_ms)
            db.commit()
            yield {"type": "error", "detail": "empty_reply"}
            return

        tokens = int(usage.get("total_tokens") or 0)
        if tokens <= 0:
            tokens = max(1, (len(text) + len(reply)) // 4)
        record_usage(db, org_id, tokens)
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_success(
            db,
            run,
            output_data={"reply_len": len(reply), "stream": True},
            tokens_prompt=usage.get("prompt_tokens"),
            tokens_completion=usage.get("completion_tokens"),
            tokens_total=tokens,
            duration_ms=duration_ms,
        )
        db.commit()
        save_memory(
            org_id,
            user.id,
            [*request_history, {"role": "user", "content": text}, {"role": "assistant", "content": reply}],
        )
        yield {"type": "done", "run_id": run.id}
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_failed(db, run, error_code="chat_failed", duration_ms=duration_ms)
        db.commit()
        yield {"type": "error", "detail": "chat_failed"}
        return

"""Faz 7 / DE-6.2 — Sales chat SSE event stream with CRM tools."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from ai.capabilities.chat import _build_context_block
from ai.capabilities.chat_tools import build_chat_messages, iter_tool_aware_chat_events
from ai.conversations_store import (
    ROLE_ASSISTANT,
    append_message,
    get_conversation_for_org,
)
from ai.llm_client import assert_llm_configured
from ai.llm_config import provider_and_model
from ai.store import create_run, finish_run_failed, finish_run_success
from ai.usage import ensure_quota, record_usage
from database import AssistantConversation, User


def iter_sales_chat_events(
    db: Session,
    *,
    user: User,
    org_id: int,
    message: str,
    history: list[dict] | None = None,
    locale: str = "tr",
    conversation: AssistantConversation | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Yields: tool_start, tool_done, delta, done {run_id[, conversation_id]}, error.
    Assistant message persisted only after full successful reply.
    """
    assert_llm_configured()
    ensure_quota(db, org_id, estimated_tokens=1200)

    text = message.strip()
    if not text:
        yield {"type": "error", "detail": "empty_message"}
        return

    include_revenue = (user.account_type or "company") == "company"
    context = _build_context_block(db, org_id, include_revenue=include_revenue)

    from ai.entity_continuity import (
        active_entity_system_hint,
        resolve_conversational_entity,
        set_conversation_active_entity,
    )

    resolution = resolve_conversational_entity(
        db,
        org_id=org_id,
        conversation=conversation,
        user_message=text,
    )
    if conversation is not None and resolution.persist:
        set_conversation_active_entity(db, conversation, resolution.entity)
        db.flush()

    entity_ctx = {
        "entity": resolution.entity,
        "bind_for_tools": resolution.bind_for_tools,
        "user_message": text,
        "dirty": False,
    }
    messages = build_chat_messages(
        locale=locale,
        history=history,
        user_message=text,
        context_json=context,
        entity_hint=active_entity_system_hint(
            resolution.entity,
            bind_for_tools=resolution.bind_for_tools,
        ),
    )

    provider, model = provider_and_model()
    run = create_run(
        db,
        org_id=org_id,
        requested_by=user.id,
        run_type="chat",
        input_data={
            "locale": locale,
            "message_len": len(text),
            "stream": True,
            "tools": True,
            "conversation_id": conversation.id if conversation else None,
            "entity_reason": resolution.reason,
            "entity_bound": bool(resolution.bind_for_tools and resolution.entity),
        },
        provider=provider,
        model=model,
        prompt_version="sales_chat_intel_v1",
    )
    db.flush()
    started = time.perf_counter()
    reply = ""
    usage: dict = {}

    try:
        for event in iter_tool_aware_chat_events(
            db,
            org_id=org_id,
            messages=messages,
            run=run,
            entity_ctx=entity_ctx,
        ):
            if event.get("type") == "_internal_done":
                reply = (event.get("reply") or "").strip()
                usage = event.get("usage") or {}
                continue
            yield event

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
            output_data={"reply_len": len(reply), "stream": True, "tools": True},
            tokens_prompt=usage.get("prompt_tokens"),
            tokens_completion=usage.get("completion_tokens"),
            tokens_total=tokens,
            duration_ms=duration_ms,
        )

        conversation_id = conversation.id if conversation else None
        if conversation is not None:
            live = get_conversation_for_org(
                db,
                organization_id=org_id,
                conversation_id=conversation.id,
                include_archived=False,
            )
            if live is not None:
                if entity_ctx.get("dirty") and entity_ctx.get("entity") is not None:
                    set_conversation_active_entity(db, live, entity_ctx["entity"])
                append_message(
                    db,
                    conversation=live,
                    user_id=user.id,
                    role=ROLE_ASSISTANT,
                    content=reply,
                    run_id=run.id,
                    touch_conversation=True,
                )
                conversation_id = live.id

        db.commit()
        done: dict[str, Any] = {"type": "done", "run_id": run.id}
        if conversation_id is not None:
            done["conversation_id"] = conversation_id
        yield done
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_failed(db, run, error_code="chat_failed", duration_ms=duration_ms)
        db.commit()
        yield {"type": "error", "detail": "chat_failed"}
        return

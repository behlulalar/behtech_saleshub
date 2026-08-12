"""Faz 5 / DE-6.2 — Sales assistant chat (read-only CRM tools)."""

import json
import time

from sqlalchemy.orm import Session

from ai.capabilities.chat_tools import build_chat_messages, run_tool_loop
from ai.llm_client import assert_llm_configured
from ai.llm_config import provider_and_model
from ai.store import create_run, finish_run_failed, finish_run_success
from ai.tools import tool_get_insights, tool_get_kpis, tool_list_leads
from ai.usage import ensure_quota, record_usage
from database import User
from intelligence.company_profile import get_org_profile

MAX_HISTORY = 12

SYSTEM_BASE = """Sen BehTech Sales Hub satış asistanısın.
Yalnızca verilen CRM özet verisine dayan; uydurma lead veya rakam yazma.
Lead kaydı değiştiremez, mesaj gönderemezsin — sadece öneri ve yorum.
Kısa, net Türkçe (kullanıcı İngilizce yazarsa İngilizce yanıtla).
"""


def _build_context_block(db: Session, org_id: int, *, include_revenue: bool) -> str:
    from ai.conversation_context import redact_context_bundle_for_model

    profile = get_org_profile(db, org_id, refresh=False, include_revenue=include_revenue)
    kpis = tool_get_kpis(db, org_id, period_type="monthly")
    insights = tool_get_insights(db, org_id, limit=5)
    leads = tool_list_leads(db, org_id, limit=5, ranked=True)
    bundle = redact_context_bundle_for_model(
        {
            "company_profile": profile,
            "kpis_monthly": kpis.get("period"),
            "insights": insights.get("items"),
            "priority_leads": leads.get("items"),
        }
    )
    return json.dumps(bundle, ensure_ascii=False)[:12000]


def normalize_history(history: list[dict] | None) -> list[dict]:
    from ai.conversation_context import (
        MAX_CONTEXT_MESSAGES,
        MAX_MESSAGE_CHARS,
        sanitize_content_for_model,
    )

    if not history:
        return []
    out: list[dict] = []
    for item in history[-max(MAX_HISTORY, MAX_CONTEXT_MESSAGES) :]:
        role = item.get("role")
        content = sanitize_content_for_model(
            (item.get("content") or "").strip(),
            max_chars=MAX_MESSAGE_CHARS,
        )
        if role not in ("user", "assistant") or not content:
            continue
        out.append({"role": role, "content": content})
    return out[-MAX_HISTORY:]


def run_sales_chat(
    db: Session,
    *,
    user: User,
    org_id: int,
    message: str,
    history: list[dict] | None = None,
    locale: str = "tr",
    conversation=None,
) -> tuple[str, int]:
    from ai.conversations_store import ROLE_ASSISTANT, append_message, get_conversation_for_org

    assert_llm_configured()
    ensure_quota(db, org_id, estimated_tokens=1200)

    text = message.strip()
    if not text:
        raise ValueError("empty_message")

    include_revenue = (user.account_type or "company") == "company"
    context = _build_context_block(db, org_id, include_revenue=include_revenue)
    messages = build_chat_messages(
        locale=locale,
        history=history,
        user_message=text,
        context_json=context,
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
            "conversation_id": conversation.id if conversation is not None else None,
            "tools": True,
        },
        provider=provider,
        model=model,
        prompt_version="sales_chat_intel_v1",
    )
    db.flush()
    started = time.perf_counter()

    try:
        reply, usage, tool_trace = run_tool_loop(
            db,
            org_id=org_id,
            messages=messages,
            run=run,
        )
        reply = (reply or "").strip()
        if not reply:
            finish_run_failed(db, run, error_code="empty_reply")
            raise RuntimeError("empty_reply")

        tokens = int(usage.get("total_tokens") or 0)
        if tokens <= 0:
            tokens = max(1, (len(text) + len(reply)) // 4)
        record_usage(db, org_id, tokens)
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_success(
            db,
            run,
            output_data={
                "reply_len": len(reply),
                "tool_calls": len(tool_trace),
                "tools": [t.get("tool") for t in tool_trace],
            },
            tokens_prompt=usage.get("prompt_tokens"),
            tokens_completion=usage.get("completion_tokens"),
            tokens_total=tokens,
            duration_ms=duration_ms,
        )
        if conversation is not None:
            live = get_conversation_for_org(
                db,
                organization_id=org_id,
                conversation_id=conversation.id,
                include_archived=False,
            )
            if live is not None:
                append_message(
                    db,
                    conversation=live,
                    user_id=user.id,
                    role=ROLE_ASSISTANT,
                    content=reply,
                    run_id=run.id,
                    touch_conversation=True,
                )
        db.commit()
        return reply, run.id
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_failed(db, run, error_code="chat_failed", duration_ms=duration_ms)
        db.commit()
        raise

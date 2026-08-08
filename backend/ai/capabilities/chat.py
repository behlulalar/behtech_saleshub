"""Faz 5 — Sales assistant chat (read-only CRM context)."""

import json
import time

from sqlalchemy.orm import Session

from ai.llm_client import assert_llm_configured, chat_completion_messages
from ai.llm_config import provider_and_model
from ai.store import create_run, finish_run_failed, finish_run_success
from ai.tools import tool_get_insights, tool_get_kpis, tool_list_leads
from ai.usage import ensure_quota, record_usage
from database import User
from intelligence.company_profile import get_org_profile

MAX_HISTORY = 8

SYSTEM_BASE = """Sen BehTech Sales Hub satış asistanısın.
Yalnızca verilen CRM özet verisine dayan; uydurma lead veya rakam yazma.
Lead kaydı değiştiremez, mesaj gönderemezsin — sadece öneri ve yorum.
Kısa, net Türkçe (kullanıcı İngilizce yazarsa İngilizce yanıtla).
"""


def _build_context_block(db: Session, org_id: int, *, include_revenue: bool) -> str:
    profile = get_org_profile(db, org_id, refresh=False, include_revenue=include_revenue)
    kpis = tool_get_kpis(db, org_id, period_type="monthly")
    insights = tool_get_insights(db, org_id, limit=5)
    leads = tool_list_leads(db, org_id, limit=5, ranked=True)
    bundle = {
        "company_profile": profile,
        "kpis_monthly": kpis.get("period"),
        "insights": insights.get("items"),
        "priority_leads": leads.get("items"),
    }
    return json.dumps(bundle, ensure_ascii=False)[:12000]


def normalize_history(history: list[dict] | None) -> list[dict]:
    if not history:
        return []
    out: list[dict] = []
    for item in history[-MAX_HISTORY:]:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        out.append({"role": role, "content": content[:4000]})
    return out


def run_sales_chat(
    db: Session,
    *,
    user: User,
    org_id: int,
    message: str,
    history: list[dict] | None = None,
    locale: str = "tr",
) -> tuple[str, int]:
    assert_llm_configured()
    ensure_quota(db, org_id, estimated_tokens=800)

    text = message.strip()
    if not text:
        raise ValueError("empty_message")

    include_revenue = (user.account_type or "company") == "company"
    context = _build_context_block(db, org_id, include_revenue=include_revenue)
    system = (
        f"{SYSTEM_BASE}\nDil tercihi: {locale}\n\n"
        f"Güncel CRM özeti (JSON):\n{context}"
    )

    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(normalize_history(history))
    messages.append({"role": "user", "content": text[:4000]})

    provider, model = provider_and_model()
    run = create_run(
        db,
        org_id=org_id,
        requested_by=user.id,
        run_type="chat",
        input_data={"locale": locale, "message_len": len(text)},
        provider=provider,
        model=model,
        prompt_version="sales_chat_v1",
    )
    started = time.perf_counter()

    try:
        reply, usage = chat_completion_messages(messages=messages)
        reply = (reply or "").strip()
        if not reply:
            finish_run_failed(db, run, error_code="empty_reply")
            raise RuntimeError("empty_reply")

        tokens = int(usage.get("total_tokens") or 0)
        record_usage(db, org_id, tokens)
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_success(
            db,
            run,
            output_data={"reply_len": len(reply)},
            tokens_prompt=usage.get("prompt_tokens"),
            tokens_completion=usage.get("completion_tokens"),
            tokens_total=tokens,
            duration_ms=duration_ms,
        )
        db.commit()
        return reply, run.id
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_failed(db, run, error_code="chat_failed", duration_ms=duration_ms)
        db.commit()
        raise

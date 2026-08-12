"""Sales assistant chat with deterministic, read-only CRM context."""

import json
import re
import time

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ai.assistant_memory import load_memory, save_memory
from ai.llm_client import assert_llm_configured, chat_completion_messages
from ai.llm_config import provider_and_model
from ai.store import create_run, finish_run_failed, finish_run_success
from ai.tools import tool_get_insights, tool_get_kpis, tool_list_leads
from ai.usage import ensure_quota, record_usage
from database import Lead, LeadActivity, User
from intelligence.company_profile import get_org_profile

MAX_HISTORY = 8

SYSTEM_BASE = """Sen BehTech Sales Hub satış asistanısın.
Yalnızca verilen CRM verisine dayan; uydurma lead, teklif, tarih veya rakam yazma.
CRM verisi sorulduğunda önce verilen kayıtları kullan ve cevabını açıkça kayda bağla.
Lead kaydı değiştiremez, mesaj gönderemezsin — bu sürüm yalnızca read-only bilgi ve analiz sağlar.
Kısa, net Türkçe (kullanıcı İngilizce yazarsa İngilizce yanıtla).
Teklif/satış tutarı gibi alanlarda CRM'deki ham değeri aynen koru; alan boşsa tahmin etme.
"""

_STOPWORDS = {
    "ne", "nedir", "hangi", "hangi", "bize", "bizim", "için", "olan", "olanı", "teklif", "teklifi",
    "fiyat", "kaç", "kadar", "vermiş", "vermistik", "yapmış", "yapmistik", "hakkında", "hakkinda",
    "durum", "son", "en", "ve", "ile", "de", "da", "mi", "mı", "mu", "mü", "bu", "şu", "su",
}


def _relevant_leads(db: Session, org_id: int, message: str) -> list[dict]:
    """Find likely lead records from the user's question; never crosses org boundary."""
    tokens = [
        token
        for token in re.findall(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+", message.lower())
        if len(token) >= 4 and token not in _STOPWORDS and not token.isdigit()
    ]
    if not tokens:
        return []

    conditions = []
    for token in tokens[:8]:
        like = f"%{token}%"
        conditions.extend([Lead.isletme_adi.ilike(like), Lead.sehir.ilike(like)])

    rows = (
        db.query(Lead)
        .filter(Lead.user_id == org_id, or_(*conditions))
        .order_by(Lead.updated_at.desc(), Lead.id.desc())
        .limit(8)
        .all()
    )

    result: list[dict] = []
    for lead in rows:
        activities = (
            db.query(LeadActivity)
            .filter(LeadActivity.user_id == org_id, LeadActivity.lead_id == lead.id)
            .order_by(LeadActivity.activity_date.desc(), LeadActivity.id.desc())
            .limit(5)
            .all()
        )
        result.append(
            {
                "lead_id": lead.id,
                "isletme_adi": lead.isletme_adi,
                "sehir": lead.sehir or "",
                "durum": lead.durum,
                "oncelik": lead.oncelik,
                "teklif": lead.teklif or "",
                "sonuc": lead.sonuc or "",
                "satis_tutari": float(lead.satis_tutari or 0),
                "satis_tarihi": lead.satis_tarihi or "",
                "demo_tarihi": lead.demo_tarihi or "",
                "gorusme_tarihi": lead.gorusme_tarihi or "",
                "notlar": (lead.notlar or "")[:1000],
                "activities": [
                    {
                        "activity_type": a.activity_type,
                        "title": a.title,
                        "description": a.description or "",
                        "activity_date": a.activity_date.isoformat() if a.activity_date else None,
                    }
                    for a in activities
                ],
            }
        )
    return result


def _build_context_block(
    db: Session,
    org_id: int,
    *,
    include_revenue: bool,
    message: str = "",
) -> str:
    profile = get_org_profile(db, org_id, refresh=False, include_revenue=include_revenue)
    kpis = tool_get_kpis(db, org_id, period_type="monthly")
    insights = tool_get_insights(db, org_id, limit=5)
    leads = tool_list_leads(db, org_id, limit=5, ranked=True)
    relevant = _relevant_leads(db, org_id, message) if message else []
    bundle = {
        "company_profile": profile,
        "kpis_monthly": kpis.get("period"),
        "insights": insights.get("items"),
        "priority_leads": leads.get("items"),
        "question_relevant_leads": relevant,
    }
    return json.dumps(bundle, ensure_ascii=False)[:18000]


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


def _history_for_request(db: Session, user: User, org_id: int, history: list[dict] | None) -> list[dict]:
    normalized = normalize_history(history)
    if normalized:
        return normalized
    return load_memory(org_id, user.id)


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
    request_history = _history_for_request(db, user, org_id, history)
    context = _build_context_block(
        db,
        org_id,
        include_revenue=include_revenue,
        message=text,
    )
    system = (
        f"{SYSTEM_BASE}\nDil tercihi: {locale}\n\n"
        f"Güncel CRM özeti (JSON):\n{context}"
    )

    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(request_history)
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
        prompt_version="sales_chat_v2",
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
        save_memory(org_id, user.id, [*request_history, {"role": "user", "content": text}, {"role": "assistant", "content": reply}])
        return reply, run.id
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_failed(db, run, error_code="chat_failed", duration_ms=duration_ms)
        db.commit()
        raise

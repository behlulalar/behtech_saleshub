"""DE-6.4 — Sales Intelligence Assistant: multi-tool reasoning + factuality."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from ai.crm_tools import CRM_TOOL_DEFINITIONS, execute_crm_tool
from ai.llm_client import assert_llm_configured, chat_completion_messages_with_tools
from ai.run_log_redact import redact_run_step
from ai.store import append_run_step
from database import AiRun

# Multi-tool synthesis (search → lead → offer → activities) needs headroom; hard cap.
MAX_TOOL_ITERATIONS = 6

TOOL_STATUS_LABELS = {
    "search_leads": "CRM kayıtları aranıyor…",
    "get_lead": "Lead detayı getiriliyor…",
    "get_lead_offer": "Teklif bilgisi getiriliyor…",
    "get_lead_activities": "Aktiviteler inceleniyor…",
    "get_sales_metrics": "Satış metrikleri hesaplanıyor…",
    "get_followup_candidates": "Takip adayları getiriliyor…",
    "get_diagnoses": "Teşhisler inceleniyor…",
    "get_diagnosis": "Teşhis detayı getiriliyor…",
    "get_pending_offers": "Bekleyen teklifler listeleniyor…",
    "get_daily_sales_brief": "Günlük satış özeti hazırlanıyor…",
}

SYSTEM_TOOLS = """Sen BehTech Sales Hub Proaktif Satış Asistanısın.
Lead kaydı değiştiremez, mesaj gönderemezsin — yalnızca READ-ONLY CRM araçlarını kullan.
AiAction oluşturma / lead update / teklif değiştirme / mesaj gönderme YASAK.
Yalnızca öneri verebilirsin ("…ile iletişime geçmeni öneririm").

## Gerçeklik (FACTUALITY) — EN ÖNEMLİ KURAL
- Fact: yalnızca tool sonuçlarında açıkça görünen bilgi.
- Inference: tool verisinden çekingen çıkarım (örn. "satışa geçtiğine dair kayıt yok").
- Unknown: CRM'de yoksa açıkça söyle. Uydurma sebep / tutar / tarih / satın alma olasılığı YASAK.
- "%80 alır", "fiyatı yüksek buldu" gibi iddialar YASAK (CRM'de yoksa).
- Örnek YANLIŞ: "Fiyatı yüksek bulduğu için almadı" (CRM'de yoksa).
- Örnek DOĞRU: "CRM'de kapanmama nedenini doğrudan belirten bir kayıt yok. Son aktivite … görünüyor."

## Daily Sales Brief (proaktif)
Broad sorular ("Bugün ne yapmalıyım?", "Neye odaklanmalıyım?", "En önemli leadler?",
"Bu hafta kritik müşteriler?", "Satışa en yakın fırsatlar?"):
→ ÖNCE get_daily_sales_brief (tercih).
Gerekirse ek: get_followup_candidates, get_pending_offers, get_diagnoses, get_sales_metrics.

Öncelik (tool zaten sıralar; uydurma skor üretme):
1) high severity diagnosis leadleri
2) uzun idle follow-up
3) bekleyen / eski teklifler
4) diğer diagnosis adayları

Boş listeler:
- follow-up yoksa: "Şu anda CRM'de follow-up adayı görünmüyor."
- pending offer yoksa: "Bekleyen teklif görünmüyor."
- diagnosis yoksa: "Şu anda aktif diagnosis bulunmuyor."
Fake lead üretme.

Cevap biçimi (kısa):
## Bugünkü önceliklerin
1. İşletme adı — neden (reason_code/CRM fact) — teklif/idle varsa — kısa öneri
Sonra 2–3 satır genel durum (follow-up / teklif / diagnosis / satış metriği).
"Satışa en yakın" = teklif süreci devam eden / yakın aktivite; yüzde tahmin yok.

## Diğer multi-tool
- Teklif → search_leads → get_lead_offer
- "Neden kapanmadı?" → search_leads → get_lead → get_lead_activities (± offer)
- Risk → get_diagnoses (± get_diagnosis)
- Satışlar → get_sales_metrics
- Teklif verilip satılmayanlar / bekleyen teklifler → get_pending_offers (veya get_daily_sales_brief).
  Tool sonuçlarında offer varsa "bekleyen teklif yok" DEME.

## Memory
Conversation memory kimlik bağlamı sağlar; CRM gerçeği tool'dan gelir.
Memory eski teklifi tool'suz kesin doğru sayma.

## Eşleşme / güvenlik
search_leads.ambiguous=true veya count>1 → netleştir; yanlış lead seçme.
organization_id / org_id / user_id tool argümanı ASLA gönderme.
Kullanıcıya gereksiz lead_id söyleme; işletme adı kullan.
Kullanıcı İngilizce yazarsa İngilizce yanıtla.
"""


def _add_usage(total: dict, usage: dict) -> None:
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        val = usage.get(key)
        if val is None:
            continue
        total[key] = int(total.get(key) or 0) + int(val)


def _parse_tool_args(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _tool_result_payload(result: dict) -> str:
    # Cap size so the model never gets a full CRM dump.
    return json.dumps(result, ensure_ascii=False)[:3500]


def _sanitize_args(args: dict) -> dict:
    cleaned = dict(args or {})
    cleaned.pop("organization_id", None)
    cleaned.pop("org_id", None)
    cleaned.pop("user_id", None)
    return cleaned


def build_chat_messages(
    *,
    locale: str,
    history: list[dict] | None,
    user_message: str,
    context_json: str | None = None,
) -> list[dict]:
    from ai.capabilities.chat import normalize_history

    system = f"{SYSTEM_TOOLS}\nDil tercihi: {locale}"
    if context_json:
        system += (
            "\n\nYüksek seviye CRM özeti (referans; kesin rakam/tarih için tool kullan):\n"
            f"{context_json[:5000]}"
        )
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(normalize_history(history))
    messages.append({"role": "user", "content": user_message[:4000]})
    return messages


def run_tool_loop(
    db: Session,
    *,
    org_id: int,
    messages: list[dict],
    run: AiRun | None = None,
) -> tuple[str, dict, list[dict]]:
    """Returns (reply, usage_totals, tool_trace)."""
    assert_llm_configured()
    usage_total: dict[str, Any] = {}
    tool_trace: list[dict] = []
    working = list(messages)

    for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
        assistant_msg, usage = chat_completion_messages_with_tools(
            messages=working,
            tools=CRM_TOOL_DEFINITIONS,
            tool_choice="auto",
        )
        _add_usage(usage_total, usage)

        tool_calls = assistant_msg.get("tool_calls") or []
        if not tool_calls:
            reply = (assistant_msg.get("content") or "").strip()
            return reply, usage_total, tool_trace

        working.append(assistant_msg)
        for tc in tool_calls:
            fn = tc.get("function") or {}
            name = str(fn.get("name") or "")
            args = _sanitize_args(_parse_tool_args(str(fn.get("arguments") or "{}")))
            started = time.perf_counter()
            result = execute_crm_tool(db, org_id, name, args)
            duration_ms = int((time.perf_counter() - started) * 1000)
            step = {
                "type": "tool",
                "tool": name,
                "success": bool(result.get("ok")),
                "duration_ms": duration_ms,
                "iteration": iteration,
                "error": result.get("error"),
            }
            tool_trace.append(step)
            if run is not None:
                append_run_step(db, run, redact_run_step(step))
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id") or "",
                    "content": _tool_result_payload(result),
                }
            )

    assistant_msg, usage = chat_completion_messages_with_tools(
        messages=working
        + [
            {
                "role": "user",
                "content": (
                    "Araç limitine ulaşıldı. Elindeki tool sonuçlarıyla kısa final cevap ver; "
                    "eksik veri uydurma. Bilinmeyenleri açıkça belirt."
                ),
            }
        ],
        tools=CRM_TOOL_DEFINITIONS,
        tool_choice="none",
    )
    _add_usage(usage_total, usage)
    reply = (assistant_msg.get("content") or "").strip()
    if not reply:
        reply = "CRM araç limitine ulaşıldı; lütfen soruyu daraltın."
    return reply, usage_total, tool_trace


def iter_tool_aware_chat_events(
    db: Session,
    *,
    org_id: int,
    messages: list[dict],
    run: AiRun,
) -> Iterator[dict[str, Any]]:
    """Yield tool_start / tool_done / delta events; ends with _internal_done."""
    assert_llm_configured()
    usage_total: dict[str, Any] = {}
    working = list(messages)
    final_reply = ""

    for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
        assistant_msg, usage = chat_completion_messages_with_tools(
            messages=working,
            tools=CRM_TOOL_DEFINITIONS,
            tool_choice="auto",
        )
        _add_usage(usage_total, usage)
        tool_calls = assistant_msg.get("tool_calls") or []
        if not tool_calls:
            final_reply = (assistant_msg.get("content") or "").strip()
            break

        working.append(assistant_msg)
        for tc in tool_calls:
            fn = tc.get("function") or {}
            name = str(fn.get("name") or "")
            args = _sanitize_args(_parse_tool_args(str(fn.get("arguments") or "{}")))
            yield {
                "type": "tool_start",
                "tool": name,
                "status": TOOL_STATUS_LABELS.get(name, "CRM inceleniyor…"),
            }
            started = time.perf_counter()
            result = execute_crm_tool(db, org_id, name, args)
            duration_ms = int((time.perf_counter() - started) * 1000)
            append_run_step(
                db,
                run,
                redact_run_step(
                    {
                        "type": "tool",
                        "tool": name,
                        "success": bool(result.get("ok")),
                        "duration_ms": duration_ms,
                        "iteration": iteration,
                        "error": result.get("error"),
                    }
                ),
            )
            yield {
                "type": "tool_done",
                "tool": name,
                "status": TOOL_STATUS_LABELS.get(name, "CRM incelendi"),
            }
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id") or "",
                    "content": _tool_result_payload(result),
                }
            )
    else:
        assistant_msg, usage = chat_completion_messages_with_tools(
            messages=working
            + [
                {
                    "role": "user",
                    "content": (
                        "Araç limitine ulaşıldı. Elindeki tool sonuçlarıyla kısa final cevap ver; "
                        "eksik veri uydurma."
                    ),
                }
            ],
            tools=CRM_TOOL_DEFINITIONS,
            tool_choice="none",
        )
        _add_usage(usage_total, usage)
        final_reply = (assistant_msg.get("content") or "").strip()

    if not final_reply:
        final_reply = "CRM'de yeterli bilgi bulunamadı veya araç limiti doldu."

    chunk_size = 28
    for i in range(0, len(final_reply), chunk_size):
        yield {"type": "delta", "content": final_reply[i : i + chunk_size]}

    yield {"type": "_internal_done", "reply": final_reply, "usage": usage_total}

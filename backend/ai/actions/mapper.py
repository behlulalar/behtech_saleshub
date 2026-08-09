"""Deterministic DE-3 recommended_action → typed action mapping (no LLM)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from ai.actions.registry import exists, validate_params

MAPPER_NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class MapperInput:
    """Single DE-3 recommended action item (title + reason only)."""

    title: str
    reason: str
    priority: str | None = None


@dataclass(frozen=True, slots=True)
class MapperContext:
    """Trusted context from CRM/diagnosis — not from free-form LLM alone."""

    lead_id: int | None = None
    diagnosis_id: str | None = None
    locale: str = "tr"


@dataclass(frozen=True, slots=True)
class MapperResult:
    outcome: str
    action_type: str | None = None
    parameters: dict[str, Any] | None = None
    mapper_reason: str = ""


def _normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", (text or "").strip().lower())
    t = re.sub(r"\s+", " ", t)
    return t


def map_recommended_action(item: MapperInput, ctx: MapperContext) -> MapperResult:
    """
    Conservative mapper: returns NO_ACTION unless title/reason match strict rules
    and required context (e.g. lead_id) is present.
    """
    if not ctx.lead_id or ctx.lead_id <= 0:
        return MapperResult(outcome=MAPPER_NO_ACTION, mapper_reason="missing_lead_id")

    title = _normalize_text(item.title)
    reason = _normalize_text(item.reason)
    combined = f"{title} {reason}"

    if not title and not reason:
        return MapperResult(outcome=MAPPER_NO_ACTION, mapper_reason="empty_recommendation")

    # WhatsApp / message draft — client opens wa.me only
    if any(k in combined for k in ("whatsapp", "mesaj gönder", "mesaj at", "yaz")):
        if "sil" in combined or "delete" in combined:
            return MapperResult(outcome=MAPPER_NO_ACTION, mapper_reason="ambiguous_whatsapp")
        draft = item.title.strip() or item.reason.strip()
        if len(draft) < 3:
            return MapperResult(outcome=MAPPER_NO_ACTION, mapper_reason="draft_too_short")
        action_type = "open_whatsapp_draft"
        params = {"lead_id": ctx.lead_id, "message_draft": draft[:2000]}
        _validate_mapped(action_type, params)
        return MapperResult(
            outcome="mapped",
            action_type=action_type,
            parameters=params,
            mapper_reason="keyword_whatsapp_draft",
        )

    # Follow-up / takip (exclude vague offer-follow-up phrases)
    if re.search(r"teklif.*takip|takip.*teklif", combined):
        return MapperResult(outcome=MAPPER_NO_ACTION, mapper_reason="ambiguous_offer_follow_up")
    if any(k in combined for k in ("takip", "follow-up", "follow up", "hatırlat", "idle", "bekleyen")):
        action_type = "propose_follow_up_task"
        params = {"lead_id": ctx.lead_id, "note": (item.reason or item.title)[:400]}
        _validate_mapped(action_type, params)
        return MapperResult(
            outcome="mapped",
            action_type=action_type,
            parameters=params,
            mapper_reason="keyword_follow_up",
        )

    # Meeting / görüşme
    if any(k in combined for k in ("görüşme", "gorusme", "meeting", "randevu", "toplantı")):
        action_type = "propose_meeting_date"
        from app_timezone import local_today

        params = {
            "lead_id": ctx.lead_id,
            "meeting_date": local_today().isoformat(),
            "meeting_time": "",
        }
        _validate_mapped(action_type, params)
        return MapperResult(
            outcome="mapped",
            action_type=action_type,
            parameters=params,
            mapper_reason="keyword_meeting",
        )

    # Log activity — explicit activity verbs
    if any(k in combined for k in ("aktivite", "activity", "kaydet", "log")):
        action_type = "propose_log_activity"
        params = {
            "lead_id": ctx.lead_id,
            "activity_type": "takip_yapildi",
            "title": item.title[:255] if item.title else "AI önerisi",
            "description": item.reason[:2000],
        }
        _validate_mapped(action_type, params)
        return MapperResult(
            outcome="mapped",
            action_type=action_type,
            parameters=params,
            mapper_reason="keyword_log_activity",
        )

    # Status change — only if explicit durum keyword + known target in text
    for status in (
        "Takip Bekliyor",
        "Görüşme Planlandı",
        "İletişime Geçildi",
        "Demo Gönderildi",
    ):
        if _normalize_text(status) in combined or status.lower() in combined:
            action_type = "propose_status_change"
            params = {"lead_id": ctx.lead_id, "target_status": status}
            _validate_mapped(action_type, params)
            return MapperResult(
                outcome="mapped",
                action_type=action_type,
                parameters=params,
                mapper_reason="explicit_target_status",
            )

    # Priority — explicit oncelik keywords
    if "öncelik" in combined or "priority" in combined:
        pri = "orta"
        if "yüksek" in combined or "yuksek" in combined or "high" in combined:
            pri = "yuksek"
        elif "düşük" in combined or "dusuk" in combined or "low" in combined:
            pri = "dusuk"
        else:
            return MapperResult(outcome=MAPPER_NO_ACTION, mapper_reason="priority_not_explicit")
        action_type = "propose_priority_change"
        params = {"lead_id": ctx.lead_id, "priority": pri}
        _validate_mapped(action_type, params)
        return MapperResult(
            outcome="mapped",
            action_type=action_type,
            parameters=params,
            mapper_reason="keyword_priority",
        )

    # Note append — explicit not
    if any(k in combined for k in ("not ekle", "nota", "not yaz", "note")):
        text = (item.reason or item.title).strip()
        if len(text) < 3:
            return MapperResult(outcome=MAPPER_NO_ACTION, mapper_reason="note_too_short")
        action_type = "propose_note_append"
        params = {"lead_id": ctx.lead_id, "note_text": text[:4000]}
        _validate_mapped(action_type, params)
        return MapperResult(
            outcome="mapped",
            action_type=action_type,
            parameters=params,
            mapper_reason="keyword_note",
        )

    return MapperResult(outcome=MAPPER_NO_ACTION, mapper_reason="no_matching_rule")


def _validate_mapped(action_type: str, params: dict[str, Any]) -> None:
    if not exists(action_type):
        raise ValueError("unknown_mapped_action")
    validate_params(action_type, params)

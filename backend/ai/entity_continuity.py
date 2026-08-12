"""DE-6.7 — Conversational CRM entity continuity (active lead binding).

PostgreSQL stores a minimal active-entity pointer on the conversation.
Redis is not required; no full CRM records are cached.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ai.crm_tools import search_leads
from database import AssistantConversation, Lead

ENTITY_TYPE_LEAD = "lead"

# Portfolio / multi-lead intents — do not force the active lead onto tools.
_BROAD_RE = re.compile(
    r"(?i)(?:"
    r"\bbug[uü]n\s+ne\s+yap\w*|"
    r"\bneye\s+odaklan\w*|"
    r"\ben\s+kritik\w*|"
    r"\ben\s+[oö]nemli\s+lead\w*|"
    r"\bbekleyen\s+teklif\w*|"
    r"\bg[uü]nl[uü]k\s+(?:sat[ıi][sş]|brief|özet)\w*|"
    r"\bbu\s+hafta\s+kritik\w*|"
    r"\bsat[ıi][sş]a\s+en\s+yak[ıi]n\w*|"
    r"\bt[uü]m\s+lead\w*|"
    r"\bgenel\s+durum\w*|"
    r"\bdaily\s+brief\b|"
    r"\bwhat\s+should\s+i\s+do\s+today\b|"
    r"\bpending\s+offers\b|"
    r"\bcritical\s+leads\b"
    r")"
)

# Pronoun / continuation follow-ups that should keep the prior entity.
_IMPLICIT_RE = re.compile(
    r"(?i)\b("
    r"peki|"
    r"onun|"
    r"bunun|"
    r"bu\s+(lead|m[uü][sş]teri|teklif|kayıt)|"
    r"neden\s+kapan|"
    r"kapanmad[ıi]|"
    r"son\s+aktivit\w*|"
    r"teklif\s+tarih\w*|"
    r"pe[sş]inden|"
    r"hat[ıi]rl[ıi]yor\s+musun|"
    r"tekrar\s+s[oö]yler\s+misin|"
    r"ka[cç]\s+tl|"
    r"neydi\b|"
    r"nedir\b|"
    r"durumu\s+ne|"
    r"what\s+about\s+(it|that)|"
    r"why\s+didn.?t\s+it\s+close|"
    r"last\s+activit"
    r")\b"
)

# Explicit switch / naming — try CRM search on captured phrase.
# Name ends before Turkish case endings / teklif|durum suffixes (do not swallow "ne").
_EXPLICIT_NAME_RE = re.compile(
    r"(?i)(?:^|[\s,;])("
    r"[A-ZÇĞİÖŞÜa-zçğıöşü0-9][A-ZÇĞİÖŞÜa-zçğıöşü0-9&.-]{0,40}"
    r"(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü0-9][A-ZÇĞİÖŞÜa-zçğıöşü0-9&.-]{0,40}){0,5}"
    r")(?='(?:de|da|te|ta|ye|ya|den|dan|ten|tan)\b|"
    r"\s+(?:için|hakkında|ile|durumu|teklif)\b)"
)

_VAGUE_SEARCH_RE = re.compile(
    r"(?i)^(neden|peki|onun|bu|lead|müşteri|musteri|teklif|durum|aktivite|kapan).*$"
)

LEAD_SCOPED_TOOLS = frozenset({"get_lead", "get_lead_offer", "get_lead_activities"})


@dataclass(frozen=True)
class ActiveEntity:
    entity_type: str
    lead_id: int
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "lead_id": int(self.lead_id),
            "label": (self.label or "").strip()[:120],
        }

    @classmethod
    def from_dict(cls, data: Any) -> ActiveEntity | None:
        if not isinstance(data, dict):
            return None
        try:
            lead_id = int(data.get("lead_id") or 0)
        except (TypeError, ValueError):
            return None
        if lead_id <= 0:
            return None
        et = str(data.get("entity_type") or ENTITY_TYPE_LEAD).strip() or ENTITY_TYPE_LEAD
        label = str(data.get("label") or "").strip()[:120]
        if not label:
            label = f"Lead #{lead_id}"
        return cls(entity_type=et, lead_id=lead_id, label=label)


@dataclass(frozen=True)
class EntityResolution:
    entity: ActiveEntity | None
    bind_for_tools: bool
    persist: bool
    reason: str


def is_broad_portfolio_intent(message: str) -> bool:
    return bool(_BROAD_RE.search(message or ""))


def is_implicit_followup(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if is_broad_portfolio_intent(text):
        return False
    return bool(_IMPLICIT_RE.search(text))


def get_conversation_active_entity(conversation: AssistantConversation | None) -> ActiveEntity | None:
    if conversation is None:
        return None
    raw = getattr(conversation, "active_entity_json", None)
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return None
    return ActiveEntity.from_dict(data)


def set_conversation_active_entity(
    db: Session,
    conversation: AssistantConversation,
    entity: ActiveEntity | None,
) -> None:
    """Persist minimal pointer only (no CRM dump)."""
    if entity is None:
        conversation.active_entity_json = None
    else:
        conversation.active_entity_json = json.dumps(entity.to_dict(), ensure_ascii=False)
    db.flush()


def _lead_entity(db: Session, org_id: int, lead_id: int) -> ActiveEntity | None:
    lead = db.query(Lead).filter(Lead.id == int(lead_id), Lead.user_id == int(org_id)).first()
    if lead is None:
        return None
    label = (lead.isletme_adi or "").strip() or f"Lead #{lead.id}"
    return ActiveEntity(entity_type=ENTITY_TYPE_LEAD, lead_id=lead.id, label=label[:120])


def _unique_search_entity(db: Session, org_id: int, query: str) -> ActiveEntity | None:
    q = (query or "").strip()
    if len(q) < 2:
        return None
    result = search_leads(db, org_id, query=q, limit=5)
    leads = list(result.get("leads") or [])
    if len(leads) != 1:
        # Prefer exact/contains label match when multiple.
        q_low = q.casefold()
        exact = [
            L
            for L in leads
            if str(L.get("business_name") or "").strip().casefold() == q_low
            or q_low in str(L.get("business_name") or "").casefold()
        ]
        if len(exact) == 1:
            leads = exact
        else:
            return None
    row = leads[0]
    try:
        lid = int(row.get("lead_id") or 0)
    except (TypeError, ValueError):
        return None
    return _lead_entity(db, org_id, lid)


def extract_explicit_entity(db: Session, org_id: int, message: str) -> ActiveEntity | None:
    """Resolve an explicitly named business to an org-owned lead (server-side)."""
    text = (message or "").strip()
    if not text or is_broad_portfolio_intent(text):
        return None

    candidates: list[str] = []
    for match in _EXPLICIT_NAME_RE.finditer(text):
        phrase = (match.group(1) or "").strip(" .,!?:;'\"")
        phrase = re.sub(r"(?i)\s+(ne|nedir|neler)$", "", phrase).strip(" .,!?:;'\"")
        if len(phrase) >= 3 and phrase.casefold() not in {
            "peki",
            "neden",
            "bugün",
            "bugun",
            "teklif",
            "durum",
            "lead",
            "müşteri",
            "musteri",
            "ne",
            "nedir",
            "neler",
        }:
            candidates.append(phrase)

    # Whole-message search for offer-style questions naming a business.
    if not candidates and not is_implicit_followup(text):
        # Strip trailing question boilerplate
        cleaned = re.sub(
            r"(?i)\s*(ya\s+)?ne\s+teklif.*$|\s*teklif(ini|i)?\s*(ne|nedir|neydi).*$|"
            r"\s*durum(u)?\s*(ne|nedir).*$|\s*hatırlıyor\s+musun\??$",
            "",
            text,
        ).strip(" .,!?:;'\"")
        cleaned = re.sub(r"(?i)'(?:de|da|te|ta|ye|ya|den|dan|ten|tan)$", "", cleaned).strip()
        if len(cleaned) >= 3:
            candidates.append(cleaned)

    seen: set[str] = set()
    for phrase in candidates:
        key = phrase.casefold()
        if key in seen:
            continue
        seen.add(key)
        ent = _unique_search_entity(db, org_id, phrase)
        if ent is not None:
            return ent
    return None


def resolve_conversational_entity(
    db: Session,
    *,
    org_id: int,
    conversation: AssistantConversation | None,
    user_message: str,
) -> EntityResolution:
    """
    Decide which lead (if any) is active for this turn.

    Never trusts client org/user ids — caller must pass server-resolved org_id
    and an already ownership-checked conversation.
    """
    stored = get_conversation_active_entity(conversation)
    text = (user_message or "").strip()

    if is_broad_portfolio_intent(text):
        return EntityResolution(
            entity=stored,
            bind_for_tools=False,
            persist=False,
            reason="broad_portfolio",
        )

    explicit = extract_explicit_entity(db, org_id, text)
    if explicit is not None:
        return EntityResolution(
            entity=explicit,
            bind_for_tools=True,
            persist=True,
            reason="explicit_mention",
        )

    if stored is not None and is_implicit_followup(text):
        # Re-validate ownership / existence.
        live = _lead_entity(db, org_id, stored.lead_id)
        if live is None:
            return EntityResolution(None, False, True, "stale_entity_cleared")
        return EntityResolution(live, True, True, "implicit_followup")

    # Non-implicit, non-broad: if search uniquely finds a lead, bind it.
    if text and not is_implicit_followup(text):
        found = _unique_search_entity(db, org_id, text)
        if found is not None:
            return EntityResolution(found, True, True, "unique_search")

    if stored is not None:
        live = _lead_entity(db, org_id, stored.lead_id)
        if live is None:
            return EntityResolution(None, False, True, "stale_entity_cleared")
        # Keep stored for continuity hints but don't force tool rewrite unless implicit.
        return EntityResolution(live, False, False, "stored_idle")

    return EntityResolution(None, False, False, "none")


def active_entity_system_hint(entity: ActiveEntity | None, *, bind_for_tools: bool) -> str:
    if entity is None:
        return ""
    if bind_for_tools:
        return (
            "\n\n## ACTIVE_CONVERSATIONAL_LEAD (DE-6.7)\n"
            f'- label: "{entity.label}"\n'
            f"- lead_id: {entity.lead_id}\n"
            "- Implicit follow-ups (peki / onun / neden kapanmadı / son aktivite / teklif tarihi) "
            "MUST use this lead_id with get_lead / get_lead_offer / get_lead_activities.\n"
            "- Do NOT search_leads for a different business unless the user names one explicitly.\n"
            "- Do NOT invent a close-lost reason; if CRM has no reason, say so and summarize "
            "offer/status/activities.\n"
            "- Broad portfolio questions are exempt (daily brief / pending offers / critical leads).\n"
        )
    return (
        "\n\n## LAST_ACTIVE_LEAD (context only; this turn is broad)\n"
        f'- label: "{entity.label}"\n'
        "- This turn asks for portfolio-level info; do not force tools onto this single lead.\n"
    )


def rewrite_tool_call_for_entity(
    *,
    tool_name: str,
    args: dict[str, Any],
    entity: ActiveEntity | None,
    bind_for_tools: bool,
    user_message: str,
) -> tuple[str, dict[str, Any]]:
    """Rewrite ambiguous follow-up tool calls onto the active lead."""
    name = tool_name
    cleaned = dict(args or {})
    cleaned.pop("organization_id", None)
    cleaned.pop("org_id", None)
    cleaned.pop("user_id", None)

    if not bind_for_tools or entity is None:
        return name, cleaned

    if name in LEAD_SCOPED_TOOLS:
        cleaned["lead_id"] = entity.lead_id
        return name, cleaned

    if name == "search_leads" and is_implicit_followup(user_message):
        # Avoid wandering search during pronoun follow-ups.
        return "get_lead", {"lead_id": entity.lead_id}

    if name == "search_leads":
        q = str(cleaned.get("query") or "").strip()
        if not q or _VAGUE_SEARCH_RE.match(q):
            cleaned["query"] = entity.label
            return name, cleaned

    return name, cleaned


def entity_from_tool_result(
    db: Session,
    org_id: int,
    *,
    tool_name: str,
    result: dict[str, Any],
) -> ActiveEntity | None:
    """Update candidate from successful lead-scoped tool results."""
    if not result.get("ok"):
        return None
    payload = result.get("result") if isinstance(result.get("result"), dict) else result
    if not isinstance(payload, dict):
        return None

    if tool_name in LEAD_SCOPED_TOOLS:
        lid = payload.get("lead_id")
        if lid is None:
            return None
        try:
            return _lead_entity(db, org_id, int(lid))
        except (TypeError, ValueError):
            return None

    if tool_name == "search_leads":
        leads = list(payload.get("leads") or [])
        if len(leads) == 1 and not payload.get("ambiguous"):
            try:
                return _lead_entity(db, org_id, int(leads[0].get("lead_id") or 0))
            except (TypeError, ValueError):
                return None
    return None

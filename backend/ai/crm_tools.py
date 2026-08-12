"""DE-6.2 — org-scoped READ-ONLY CRM tools for Sales Assistant.

organization_id always comes from authenticated context (never from LLM args).
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ai.snapshots.sanitize import sanitize_text
from config import settings
from database import CategoryModel, Lead, LeadActivity
from intelligence.analytics_engine import compute_kpis
from intelligence.diagnosis.engine import compute_diagnoses
from intelligence.diagnosis.evidence import get_reliable_offer_given_dates


class CrmToolError(ValueError):
    """Safe tool-level error (mapped to not_found / invalid_args)."""


_WS = re.compile(r"\s+")


def _clamp_limit(value: Any, *, default: int, lo: int = 1, hi: int = 25) -> int:
    try:
        n = int(value if value is not None else default)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def _category_label(db: Session, org_id: int, category_id: str) -> str:
    cat = (
        db.query(CategoryModel)
        .filter(CategoryModel.user_id == org_id, CategoryModel.id == category_id)
        .first()
    )
    return cat.label if cat else (category_id or "")


def _lead_for_org(db: Session, org_id: int, lead_id: int) -> Lead | None:
    if lead_id <= 0:
        return None
    return db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == org_id).first()


def _tokens(query: str) -> list[str]:
    parts = [p for p in _WS.split((query or "").strip()) if p]
    # Keep longer tokens first; drop ultra-short noise except digits
    out: list[str] = []
    for p in parts:
        if len(p) >= 2 or p.isdigit():
            out.append(p)
    return out[:8]


def search_leads(
    db: Session,
    org_id: int,
    *,
    query: str,
    limit: int = 10,
    city: str | None = None,
    category: str | None = None,
    status: str | None = None,
) -> dict:
    limit = _clamp_limit(limit, default=10, hi=20)
    q = (query or "").strip()
    if not q:
        return {"leads": [], "count": 0, "query": q}

    tokens = _tokens(q)
    filters = [Lead.user_id == org_id]
    if city and str(city).strip():
        filters.append(Lead.sehir.ilike(f"%{str(city).strip()}%"))
    if category and str(category).strip():
        cat = str(category).strip()
        filters.append(or_(Lead.category.ilike(f"%{cat}%"), Lead.category == cat))
    if status and str(status).strip():
        filters.append(Lead.durum.ilike(f"%{str(status).strip()}%"))

    # Prefer full phrase match, then token AND on name/city
    phrase = f"%{q}%"
    base = db.query(Lead).filter(*filters)
    rows = (
        base.filter(
            or_(
                Lead.isletme_adi.ilike(phrase),
                Lead.sehir.ilike(phrase),
            )
        )
        .order_by(Lead.intelligence_score.desc().nullslast(), Lead.id.desc())
        .limit(limit)
        .all()
    )

    if not rows and tokens:
        token_q = base
        for tok in tokens:
            like = f"%{tok}%"
            token_q = token_q.filter(
                or_(
                    Lead.isletme_adi.ilike(like),
                    Lead.sehir.ilike(like),
                    Lead.category.ilike(like),
                    Lead.durum.ilike(like),
                )
            )
        rows = (
            token_q.order_by(Lead.intelligence_score.desc().nullslast(), Lead.id.desc())
            .limit(limit)
            .all()
        )

    leads = [
        {
            "lead_id": row.id,
            "business_name": row.isletme_adi,
            "city": row.sehir or "",
            "category": _category_label(db, org_id, row.category),
            "status": row.durum or "",
            "priority": row.oncelik or "",
            "score": row.intelligence_score,
        }
        for row in rows
    ]
    ambiguous = len(leads) > 1
    return {
        "leads": leads,
        "count": len(leads),
        "query": q,
        "ambiguous": ambiguous,
        "clarification_hint": (
            "Birden fazla eşleşme var. Kullanıcıya işletme adı + şehir ile netleştirme sorun; "
            "tek lead seçmeden kesin teklif/aktivite iddiasında bulunmayın."
            if ambiguous
            else None
        ),
    }


def get_lead(db: Session, org_id: int, *, lead_id: int) -> dict:
    lead = _lead_for_org(db, org_id, int(lead_id))
    if not lead:
        raise CrmToolError("not_found")

    include_pii = bool(settings.ai_include_pii)
    notes = (lead.notlar or "").strip()
    if notes and not settings.ai_include_notes:
        notes = ""
    elif notes:
        notes = sanitize_text(notes[:500], include_pii=include_pii)

    return {
        "lead_id": lead.id,
        "business_name": lead.isletme_adi,
        "city": lead.sehir or "",
        "category": _category_label(db, org_id, lead.category),
        "status": lead.durum or "",
        "priority": lead.oncelik or "",
        "score": lead.intelligence_score,
        "offer_text": (lead.teklif or "").strip() or None,
        "sales_amount": float(lead.satis_tutari or 0) or None,
        "sales_date": (lead.satis_tarihi or "").strip() or None,
        "demo_sent": bool(lead.demo_gonderildi),
        "demo_date": (lead.demo_tarihi or "").strip() or None,
        "meeting_date": (lead.gorusme_tarihi or "").strip() or None,
        "meeting_time": (lead.gorusme_saati or "").strip() or None,
        "result": (lead.sonuc or "").strip() or None,
        "notes": notes or None,
        "contact_name": (
            sanitize_text(lead.yetkili or "", include_pii=include_pii) if include_pii else None
        ),
    }


def get_lead_offer(db: Session, org_id: int, *, lead_id: int) -> dict:
    lead = _lead_for_org(db, org_id, int(lead_id))
    if not lead:
        raise CrmToolError("not_found")

    offer_dates = get_reliable_offer_given_dates(db, org_id, [lead.id])
    offer_date = offer_dates.get(lead.id)

    activities = (
        db.query(LeadActivity)
        .filter(
            LeadActivity.user_id == org_id,
            LeadActivity.lead_id == lead.id,
            LeadActivity.activity_type == "teklif_verildi",
        )
        .order_by(LeadActivity.activity_date.desc())
        .limit(5)
        .all()
    )
    latest = activities[0] if activities else None
    offer_text = (lead.teklif or "").strip() or None
    if not offer_text and latest and (latest.description or "").strip():
        offer_text = (latest.description or "").strip()[:255]

    sales_amount = float(lead.satis_tutari or 0)
    return {
        "lead_id": lead.id,
        "business_name": lead.isletme_adi,
        "status": lead.durum or "",
        "offer_text": offer_text,
        "offer_amount": None,  # no dedicated numeric offer field on Lead
        "offer_date": offer_date.isoformat() if offer_date else (
            latest.activity_date.date().isoformat() if latest and latest.activity_date else None
        ),
        "offer_activity_count": len(activities),
        "latest_offer_activity": (
            {
                "activity_type": latest.activity_type,
                "activity_date": latest.activity_date.isoformat() if latest.activity_date else None,
                "description": (latest.description or "").strip()[:300] or None,
                "title": (latest.title or "").strip() or None,
            }
            if latest
            else None
        ),
        "sales_amount": sales_amount if sales_amount > 0 else None,
        "sales_date": (lead.satis_tarihi or "").strip() or None,
    }


def get_lead_activities(
    db: Session,
    org_id: int,
    *,
    lead_id: int,
    limit: int = 10,
) -> dict:
    lead = _lead_for_org(db, org_id, int(lead_id))
    if not lead:
        raise CrmToolError("not_found")
    limit = _clamp_limit(limit, default=10, hi=30)
    include_pii = bool(settings.ai_include_pii)
    rows = (
        db.query(LeadActivity)
        .filter(LeadActivity.user_id == org_id, LeadActivity.lead_id == lead.id)
        .order_by(LeadActivity.activity_date.desc(), LeadActivity.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "lead_id": lead.id,
        "business_name": lead.isletme_adi,
        "activities": [
            {
                "activity_type": row.activity_type,
                "activity_date": row.activity_date.isoformat() if row.activity_date else None,
                "title": (row.title or "").strip() or None,
                "description": sanitize_text(
                    (row.description or "")[:300],
                    include_pii=include_pii,
                )
                or None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


def get_sales_metrics(
    db: Session,
    org_id: int,
    *,
    period: str = "month",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Aggregate KPIs via existing report engine (no invented sales semantics)."""
    _ = start_date, end_date  # reserved; period drives compute_kpis today
    period_norm = (period or "month").strip().lower()
    if period_norm in ("month", "monthly"):
        period_type = "monthly"
    elif period_norm in ("week", "weekly"):
        period_type = "weekly"
    elif period_norm in ("day", "daily"):
        period_type = "daily"
    elif period_norm in ("quarter", "year"):
        # Report engine has no quarter/year; approximate with monthly current window + note.
        period_type = "monthly"
    else:
        period_type = "monthly"

    bundle = compute_kpis(db, org_id, period_type=period_type, include_revenue=True)
    period_block = bundle.get("period") or {}
    return {
        "period": period_norm,
        "period_type": period_type,
        "label": period_block.get("label"),
        "start": period_block.get("start"),
        "end": period_block.get("end"),
        "total_new_leads": period_block.get("yeni_kayit"),
        "won_count": period_block.get("yeni_musteri"),
        "sales_count": period_block.get("satis_sayisi"),
        "total_sales_amount": period_block.get("toplam_gelir"),
        "conversion_rate": period_block.get("satis_donusum_orani")
        or period_block.get("donusum_orani"),
        "previous_period": period_block.get("previous"),
        "note": (
            "quarter/year requested; returning current monthly report window"
            if period_norm in ("quarter", "year")
            else None
        ),
    }


def get_followup_candidates(
    db: Session,
    org_id: int,
    *,
    limit: int = 10,
) -> dict:
    """Reuse DE diagnosis follow-up output (no new idle algorithm)."""
    limit = _clamp_limit(limit, default=10, hi=25)
    result = compute_diagnoses(db, org_id, period_type="monthly", diagnosis_type="follow_up")
    items = result.get("items") or []

    def _id(item: Any) -> str | None:
        if isinstance(item, dict):
            return item.get("diagnosis_id")
        return getattr(item, "diagnosis_id", None)

    def _get(item: Any, key: str, default=None):
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    follow = next((x for x in items if _id(x) == "follow_up_idle_leads"), None)
    if follow is None and items:
        follow = items[0]
    if follow is None:
        return {"candidates": [], "count": 0, "diagnosis_id": None}

    top = list(_get(follow, "top_priority_leads") or [])[:limit]
    candidates = []
    for row in top:
        candidates.append(
            {
                "lead_id": row.get("lead_id"),
                "business_name": row.get("lead_name") or row.get("isletme_adi") or "",
                "status": row.get("durum") or "",
                "priority": row.get("priority") or "",
                "score": row.get("diagnosis_priority_score") or row.get("existing_lead_score"),
                "idle_days": row.get("idle_days"),
                "reason": ",".join(row.get("reason_codes") or []) or row.get("reason"),
            }
        )
    return {
        "diagnosis_id": _id(follow),
        "severity": _get(follow, "severity"),
        "title": _get(follow, "title"),
        "candidates": candidates,
        "count": len(candidates),
    }


def get_diagnoses(
    db: Session,
    org_id: int,
    *,
    severity: str | None = None,
    diagnosis_type: str | None = None,
    limit: int = 10,
) -> dict:
    limit = _clamp_limit(limit, default=10, hi=20)
    dtype = (diagnosis_type or "").strip() or None
    if dtype and dtype not in ("follow_up", "offer", "funnel_drop"):
        dtype = None
    result = compute_diagnoses(
        db,
        org_id,
        period_type="monthly",
        severity=severity,
        diagnosis_type=dtype,
    )
    items = result.get("items") or []
    out = []
    for item in items[:limit]:
        if isinstance(item, dict):
            out.append(
                {
                    "diagnosis_id": item.get("diagnosis_id"),
                    "type": item.get("type"),
                    "severity": item.get("severity"),
                    "title": item.get("title"),
                    "metric": item.get("metric"),
                    "current_value": item.get("current_value"),
                    "affected_lead_count": item.get("affected_lead_count"),
                    "description": (item.get("description") or "")[:400],
                }
            )
        else:
            out.append(
                {
                    "diagnosis_id": item.diagnosis_id,
                    "type": item.type,
                    "severity": item.severity,
                    "title": item.title,
                    "metric": item.metric,
                    "current_value": item.current_value,
                    "affected_lead_count": item.affected_lead_count,
                    "description": (item.description or "")[:400],
                }
            )
    return {"diagnoses": out, "count": len(out), "diagnosis_type": dtype}


def get_diagnosis(db: Session, org_id: int, *, diagnosis_id: str) -> dict:
    did = (diagnosis_id or "").strip()
    if not did:
        raise CrmToolError("invalid_diagnosis_id")
    result = compute_diagnoses(db, org_id, period_type="monthly")
    items = result.get("items") or []

    def _id(item: Any) -> str | None:
        if isinstance(item, dict):
            return item.get("diagnosis_id")
        return getattr(item, "diagnosis_id", None)

    match = next((x for x in items if _id(x) == did), None)
    if match is None:
        raise CrmToolError("not_found")

    if isinstance(match, dict):
        top = list(match.get("top_priority_leads") or [])[:8]
        return {
            "diagnosis_id": match.get("diagnosis_id"),
            "type": match.get("type"),
            "severity": match.get("severity"),
            "title": match.get("title"),
            "description": match.get("description"),
            "metric": match.get("metric"),
            "current_value": match.get("current_value"),
            "affected_lead_count": match.get("affected_lead_count"),
            "top_leads": [
                {
                    "lead_id": r.get("lead_id"),
                    "business_name": r.get("lead_name") or "",
                    "status": r.get("durum") or "",
                    "priority": r.get("priority") or "",
                    "idle_days": r.get("idle_days"),
                    "score": r.get("diagnosis_priority_score"),
                }
                for r in top
            ],
        }

    top = list(getattr(match, "top_priority_leads", None) or [])[:8]
    return {
        "diagnosis_id": match.diagnosis_id,
        "type": match.type,
        "severity": match.severity,
        "title": match.title,
        "description": match.description,
        "metric": match.metric,
        "current_value": match.current_value,
        "affected_lead_count": match.affected_lead_count,
        "top_leads": [
            {
                "lead_id": r.get("lead_id"),
                "business_name": r.get("lead_name") or "",
                "status": r.get("durum") or "",
                "priority": r.get("priority") or "",
                "idle_days": r.get("idle_days"),
                "score": r.get("diagnosis_priority_score"),
            }
            for r in top
        ],
    }


def get_pending_offers(
    db: Session,
    org_id: int,
    *,
    limit: int = 10,
    min_age_days: int = 0,
) -> dict:
    """
    DE-6.4 — leads with an offer signal that have not converted to a sale.

    READ-ONLY. Uses CRM lead fields + reliable teklif_verildi dates (no mutation).
    """
    from datetime import date as date_cls

    from app_timezone import local_today
    from intelligence.diagnosis.constants import PENDING_OFFER_STATUS

    limit = _clamp_limit(limit, default=10, hi=25)
    try:
        min_age = max(0, int(min_age_days or 0))
    except (TypeError, ValueError):
        min_age = 0

    leads = db.query(Lead).filter(Lead.user_id == org_id).all()
    candidates: list[Lead] = []
    for lead in leads:
        sold = float(lead.satis_tutari or 0) > 0
        if sold:
            continue
        has_offer = bool((lead.teklif or "").strip()) or (lead.durum or "") in PENDING_OFFER_STATUS
        if not has_offer:
            continue
        candidates.append(lead)

    offer_dates = get_reliable_offer_given_dates(db, org_id, [l.id for l in candidates])
    today = local_today()
    rows: list[dict] = []
    for lead in candidates:
        ref = offer_dates.get(lead.id)
        age_days = (today - ref).days if isinstance(ref, date_cls) else None
        if age_days is not None and age_days < min_age:
            continue
        rows.append(
            {
                "lead_id": lead.id,
                "business_name": lead.isletme_adi,
                "city": lead.sehir or "",
                "status": lead.durum or "",
                "offer_text": (lead.teklif or "").strip() or None,
                "offer_date": ref.isoformat() if ref else None,
                "offer_age_days": age_days,
                "priority": lead.oncelik or "",
                "score": lead.intelligence_score,
            }
        )

    rows.sort(
        key=lambda r: (
            -(r["offer_age_days"] if r["offer_age_days"] is not None else -1),
            -(r["score"] or 0),
        )
    )
    items = rows[:limit]
    return {
        "offers": items,
        "count": len(items),
        "total_matching": len(rows),
        "min_age_days": min_age,
        "note": (
            "Teklif kaydı olan ve satış tutarı olmayan leadler. "
            "Kapanmama nedeni bu listede yoktur; yalnızca CRM teklif/satış alanları."
        ),
    }


_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def get_daily_sales_brief(
    db: Session,
    org_id: int,
    *,
    limit: int = 8,
) -> dict:
    """
    DE-6.6 — compact daily sales brief from existing READ-ONLY tools.

    Deterministic priority (no ML / no invented scores):
    1) high-severity diagnosis top leads
    2) follow-up candidates by idle_days / diagnosis score
    3) pending offers by offer_age_days
    """
    limit = _clamp_limit(limit, default=8, hi=15)

    follow = get_followup_candidates(db, org_id, limit=limit)
    pending = get_pending_offers(db, org_id, limit=limit)
    diagnoses = get_diagnoses(db, org_id, limit=8)
    metrics = get_sales_metrics(db, org_id, period="month")

    diag_items = list(diagnoses.get("diagnoses") or [])
    high_diags = [d for d in diag_items if (d.get("severity") or "").lower() == "high"]

    # Expand top leads from highest-severity diagnoses (compact).
    diagnosis_leads: list[dict] = []
    for d in sorted(diag_items, key=lambda x: _SEVERITY_RANK.get(str(x.get("severity") or "").lower(), 9)):
        did = d.get("diagnosis_id")
        if not did:
            continue
        try:
            detail = get_diagnosis(db, org_id, diagnosis_id=str(did))
        except CrmToolError:
            continue
        for row in list(detail.get("top_leads") or [])[:5]:
            diagnosis_leads.append(
                {
                    "lead_id": row.get("lead_id"),
                    "business_name": row.get("business_name") or "",
                    "status": row.get("status") or "",
                    "idle_days": row.get("idle_days"),
                    "score": row.get("score"),
                    "source": "diagnosis",
                    "reason_code": "high_severity_diagnosis"
                    if (d.get("severity") or "").lower() == "high"
                    else "diagnosis_priority",
                    "diagnosis_id": did,
                    "diagnosis_title": d.get("title"),
                    "severity": d.get("severity"),
                }
            )

    priorities: list[dict] = []
    seen: set[int] = set()

    def _add(item: dict) -> None:
        lid = item.get("lead_id")
        if lid is None:
            return
        try:
            lid_i = int(lid)
        except (TypeError, ValueError):
            return
        if lid_i in seen:
            return
        seen.add(lid_i)
        priorities.append(item)

    # 1) High severity diagnosis leads first
    for row in diagnosis_leads:
        if (row.get("severity") or "").lower() == "high":
            _add(row)

    # 2) Follow-up idle (existing diagnosis score / idle_days)
    follow_rows = sorted(
        list(follow.get("candidates") or []),
        key=lambda r: (
            -(r.get("idle_days") if r.get("idle_days") is not None else -1),
            -(r.get("score") or 0),
        ),
    )
    for row in follow_rows:
        _add(
            {
                "lead_id": row.get("lead_id"),
                "business_name": row.get("business_name") or "",
                "status": row.get("status") or "",
                "idle_days": row.get("idle_days"),
                "score": row.get("score"),
                "source": "follow_up",
                "reason_code": "follow_up_idle",
                "priority": row.get("priority"),
            }
        )

    # 3) Pending / stale offers
    offer_rows = sorted(
        list(pending.get("offers") or []),
        key=lambda r: (
            -(r.get("offer_age_days") if r.get("offer_age_days") is not None else -1),
            -(r.get("score") or 0),
        ),
    )
    for row in offer_rows:
        _add(
            {
                "lead_id": row.get("lead_id"),
                "business_name": row.get("business_name") or "",
                "status": row.get("status") or "",
                "offer_text": row.get("offer_text"),
                "offer_date": row.get("offer_date"),
                "offer_age_days": row.get("offer_age_days"),
                "score": row.get("score"),
                "source": "pending_offer",
                "reason_code": "pending_offer",
            }
        )

    # 4) Remaining diagnosis leads (medium/low)
    for row in diagnosis_leads:
        _add(row)

    top = priorities[:limit]
    return {
        "priorities": top,
        "priority_count": len(top),
        "summary": {
            "follow_up_count": follow.get("count") or 0,
            "pending_offer_count": pending.get("count") or 0,
            "diagnosis_count": diagnoses.get("count") or 0,
            "high_severity_diagnosis_count": len(high_diags),
            "empty_follow_up": (follow.get("count") or 0) == 0,
            "empty_pending_offers": (pending.get("count") or 0) == 0,
            "empty_diagnoses": (diagnoses.get("count") or 0) == 0,
        },
        "diagnoses": [
            {
                "diagnosis_id": d.get("diagnosis_id"),
                "title": d.get("title"),
                "severity": d.get("severity"),
                "affected_lead_count": d.get("affected_lead_count"),
                "current_value": d.get("current_value"),
                "metric": d.get("metric"),
            }
            for d in diag_items[:6]
        ],
        "sales_metrics": {
            "period": metrics.get("period"),
            "label": metrics.get("label"),
            "sales_count": metrics.get("sales_count"),
            "won_count": metrics.get("won_count"),
            "total_sales_amount": metrics.get("total_sales_amount"),
            "conversion_rate": metrics.get("conversion_rate"),
        },
        "notes": [
            "Öncelik sırası diagnosis severity + idle_days + offer_age_days (mevcut CRM/diagnosis alanları).",
            "Satın alma olasılığı / yüzde tahmini yok.",
            "Kapanmama nedeni bu brief'te üretilmez; CRM notu yoksa unknown.",
            "Öneri okunur; mesaj gönderme / lead update / AiAction yok.",
        ],
    }


# OpenAI function-calling schemas (no organization_id parameter).
CRM_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_leads",
            "description": "Search org CRM leads by business name / city / category text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                    "city": {"type": "string"},
                    "category": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_lead",
            "description": "Get safe CRM fields for one lead by lead_id.",
            "parameters": {
                "type": "object",
                "properties": {"lead_id": {"type": "integer"}},
                "required": ["lead_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_lead_offer",
            "description": "Get offer text/date and related teklif_verildi activity for a lead.",
            "parameters": {
                "type": "object",
                "properties": {"lead_id": {"type": "integer"}},
                "required": ["lead_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_lead_activities",
            "description": "List recent activities for a lead (newest first).",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": ["lead_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_metrics",
            "description": "Read-only sales/KPI aggregates for a period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["month", "quarter", "year", "week", "day"],
                    },
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_followup_candidates",
            "description": "Leads that need follow-up (uses diagnosis engine).",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_diagnoses",
            "description": (
                "List current sales diagnoses (follow-up idle, stale offers, funnel drops). "
                "Use for risk / pipeline health questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string"},
                    "diagnosis_type": {
                        "type": "string",
                        "enum": ["follow_up", "offer", "funnel_drop"],
                    },
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_diagnosis",
            "description": "Get one diagnosis by diagnosis_id with top leads.",
            "parameters": {
                "type": "object",
                "properties": {"diagnosis_id": {"type": "string"}},
                "required": ["diagnosis_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_offers",
            "description": (
                "List leads that have an offer recorded but have not converted to a sale "
                "(includes Demo Gönderildi / Teklif Verildi with offer text). "
                "Use for 'bekleyen teklifler' / 'teklif verip satılmayanlar'. "
                "If result.count>0 you MUST list those offers; do not say none exist."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "min_age_days": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_sales_brief",
            "description": (
                "Compact daily sales brief for 'Bugün ne yapmalıyım?' / priority questions. "
                "Merges follow-up candidates, pending offers, diagnoses, and monthly metrics "
                "with deterministic priority. Prefer this for broad daily planning questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        },
    },
]


def execute_crm_tool(db: Session, org_id: int, tool_name: str, args: dict | None) -> dict:
    """Dispatch CRM tool; org_id from auth context only."""
    args = args or {}
    # Hard-block model attempts to pass org identifiers.
    if "organization_id" in args or "org_id" in args or "user_id" in args:
        return {"ok": False, "tool": tool_name, "error": "forbidden_arg"}

    try:
        if tool_name == "search_leads":
            result = search_leads(
                db,
                org_id,
                query=str(args.get("query") or ""),
                limit=args.get("limit", 10),
                city=args.get("city"),
                category=args.get("category"),
                status=args.get("status"),
            )
        elif tool_name == "get_lead":
            result = get_lead(db, org_id, lead_id=int(args["lead_id"]))
        elif tool_name == "get_lead_offer":
            result = get_lead_offer(db, org_id, lead_id=int(args["lead_id"]))
        elif tool_name == "get_lead_activities":
            result = get_lead_activities(
                db,
                org_id,
                lead_id=int(args["lead_id"]),
                limit=args.get("limit", 10),
            )
        elif tool_name == "get_sales_metrics":
            result = get_sales_metrics(
                db,
                org_id,
                period=str(args.get("period") or "month"),
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
            )
        elif tool_name == "get_followup_candidates":
            result = get_followup_candidates(db, org_id, limit=args.get("limit", 10))
        elif tool_name == "get_diagnoses":
            result = get_diagnoses(
                db,
                org_id,
                severity=args.get("severity"),
                diagnosis_type=args.get("diagnosis_type"),
                limit=args.get("limit", 10),
            )
        elif tool_name == "get_diagnosis":
            result = get_diagnosis(db, org_id, diagnosis_id=str(args.get("diagnosis_id") or ""))
        elif tool_name == "get_pending_offers":
            result = get_pending_offers(
                db,
                org_id,
                limit=args.get("limit", 10),
                min_age_days=args.get("min_age_days", 0),
            )
        elif tool_name == "get_daily_sales_brief":
            result = get_daily_sales_brief(db, org_id, limit=args.get("limit", 8))
        else:
            return {"ok": False, "tool": tool_name, "error": "unknown_tool"}
        return {"ok": True, "tool": tool_name, "result": result}
    except CrmToolError as exc:
        return {"ok": False, "tool": tool_name, "error": str(exc)}
    except (TypeError, ValueError, KeyError) as exc:
        return {"ok": False, "tool": tool_name, "error": "invalid_args", "detail": str(exc)[:120]}
    except Exception:
        return {"ok": False, "tool": tool_name, "error": "tool_failed"}

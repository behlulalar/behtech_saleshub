from fastapi import HTTPException
from sqlalchemy.orm import Session

from config import settings
from database import Lead, LeadActivity
from ai.snapshots.sanitize import sanitize_text


def _get_lead_or_404(db: Session, org_id: int, lead_id: int) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == org_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    return lead


def build_lead_snapshot(db: Session, org_id: int, lead_id: int) -> dict:
    lead = _get_lead_or_404(db, org_id, lead_id)
    include_pii = settings.ai_include_pii
    notes = (lead.notlar or "").strip()
    if notes and not settings.ai_include_notes:
        notes = ""
    elif notes:
        notes = notes[:500]

    activities = (
        db.query(LeadActivity)
        .filter(LeadActivity.user_id == org_id, LeadActivity.lead_id == lead_id)
        .order_by(LeadActivity.activity_date.desc())
        .limit(8)
        .all()
    )

    return {
        "lead_id": lead.id,
        "isletme_adi": lead.isletme_adi,
        "yetkili": sanitize_text(lead.yetkili or "", include_pii=include_pii),
        "sehir": lead.sehir or "",
        "category": lead.category,
        "durum": lead.durum,
        "oncelik": lead.oncelik,
        "notlar": sanitize_text(notes, include_pii=include_pii),
        "whatsapp": sanitize_text(lead.whatsapp or "", include_pii=include_pii) if include_pii else "",
        "eposta": sanitize_text(lead.eposta or "", include_pii=include_pii) if include_pii else "",
        "activities": [
            {
                "type": row.activity_type,
                "title": row.title,
                "date": row.activity_date.isoformat() if row.activity_date else "",
                "description": sanitize_text((row.description or "")[:200], include_pii=include_pii),
            }
            for row in activities
        ],
    }

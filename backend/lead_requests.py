import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from activities import activities_for_new_lead, log_activity, record_activities
from database import CategoryModel, Lead, LeadRequest, User
from lead_automation import apply_lead_automation
from tags import sync_lead_tags, validate_tag_ids
from text_format import normalize_lead_text_fields


def _parse_tag_ids(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _dump_tag_ids(tag_ids: list[str]) -> str:
    return json.dumps(tag_ids or [])


def request_response(db: Session, request: LeadRequest) -> dict:
    requester = db.query(User).filter(User.id == request.requested_by).first()
    reviewer = (
        db.query(User).filter(User.id == request.reviewed_by).first()
        if request.reviewed_by
        else None
    )
    category = (
        db.query(CategoryModel)
        .filter(CategoryModel.user_id == request.owner_id, CategoryModel.id == request.category)
        .first()
    )

    return {
        "id": request.id,
        "category": request.category,
        "category_label": category.label if category else request.category,
        "status": request.status,
        "requested_by": request.requested_by,
        "requested_by_username": requester.username if requester else "",
        "isletme_adi": request.isletme_adi,
        "yetkili": request.yetkili,
        "sehir": request.sehir,
        "instagram": request.instagram,
        "whatsapp": request.whatsapp,
        "ilk_iletisim_kanali": request.ilk_iletisim_kanali,
        "ilk_mesaj_tarihi": request.ilk_mesaj_tarihi,
        "ilk_mesaj_saati": request.ilk_mesaj_saati,
        "durum": request.durum,
        "oncelik": request.oncelik or "orta",
        "takip_1": request.takip_1,
        "takip_2": request.takip_2,
        "demo_gonderildi": request.demo_gonderildi,
        "demo_tarihi": request.demo_tarihi,
        "gorusme_tarihi": request.gorusme_tarihi,
        "gorusme_saati": request.gorusme_saati,
        "teklif": request.teklif,
        "sonuc": request.sonuc,
        "notlar": request.notlar,
        "tag_ids": _parse_tag_ids(request.tag_ids_json),
        "rejection_note": request.rejection_note or "",
        "reviewed_by_username": reviewer.username if reviewer else "",
        "reviewed_at": request.reviewed_at,
        "approved_lead_id": request.approved_lead_id,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


def create_lead_request(
    db: Session,
    *,
    owner_id: int,
    requested_by: int,
    category: str,
    data: dict,
    tag_ids: list[str],
) -> LeadRequest:
    validate_tag_ids(db, owner_id, tag_ids)

    request = LeadRequest(
        owner_id=owner_id,
        requested_by=requested_by,
        category=category,
        status="pending",
        tag_ids_json=_dump_tag_ids(tag_ids),
        **normalize_lead_text_fields(data),
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def approve_lead_request(db: Session, owner: User, request_id: int) -> Lead:
    request = (
        db.query(LeadRequest)
        .filter(LeadRequest.id == request_id, LeadRequest.owner_id == owner.id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Talep bulunamadı")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Talep zaten işlenmiş")

    requester = db.query(User).filter(User.id == request.requested_by).first()
    tag_ids = _parse_tag_ids(request.tag_ids_json)

    lead_payload = apply_lead_automation(
        {
            "category": request.category,
            "isletme_adi": request.isletme_adi,
            "yetkili": request.yetkili,
            "sehir": request.sehir,
            "instagram": request.instagram,
            "whatsapp": request.whatsapp,
            "ilk_iletisim_kanali": request.ilk_iletisim_kanali,
            "ilk_mesaj_tarihi": request.ilk_mesaj_tarihi,
            "ilk_mesaj_saati": request.ilk_mesaj_saati,
            "durum": request.durum,
            "oncelik": request.oncelik or "orta",
            "takip_1": request.takip_1,
            "takip_2": request.takip_2,
            "demo_gonderildi": request.demo_gonderildi,
            "demo_tarihi": request.demo_tarihi,
            "gorusme_tarihi": request.gorusme_tarihi,
            "gorusme_saati": request.gorusme_saati,
            "teklif": request.teklif,
            "sonuc": request.sonuc,
            "notlar": request.notlar,
        }
    )

    lead = Lead(user_id=owner.id, **lead_payload)
    db.add(lead)
    db.flush()

    sync_lead_tags(db, owner.id, lead.id, tag_ids)

    lead_data = {
        "isletme_adi": lead.isletme_adi,
        "ilk_iletisim_kanali": lead.ilk_iletisim_kanali,
        "ilk_mesaj_tarihi": lead.ilk_mesaj_tarihi,
        "ilk_mesaj_saati": lead.ilk_mesaj_saati,
        "demo_gonderildi": lead.demo_gonderildi,
        "demo_tarihi": lead.demo_tarihi,
        "teklif": lead.teklif,
        "gorusme_tarihi": lead.gorusme_tarihi,
        "gorusme_saati": lead.gorusme_saati,
        "durum": lead.durum,
        "takip_1": lead.takip_1,
        "takip_2": lead.takip_2,
        "notlar": lead.notlar,
    }
    record_activities(db, owner.id, lead.id, activities_for_new_lead(lead_data))

    if requester:
        log_activity(
            db,
            user_id=owner.id,
            lead_id=lead.id,
            activity_type="diger",
            title="Personel talebi onaylandı",
            description=f"{requester.username} tarafından oluşturulan talep onaylandı",
        )

    request.status = "approved"
    request.reviewed_by = owner.id
    request.reviewed_at = datetime.utcnow()
    request.approved_lead_id = lead.id
    db.commit()
    db.refresh(lead)
    return lead


def reject_lead_request(
    db: Session, owner: User, request_id: int, rejection_note: str = ""
) -> LeadRequest:
    request = (
        db.query(LeadRequest)
        .filter(LeadRequest.id == request_id, LeadRequest.owner_id == owner.id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Talep bulunamadı")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Talep zaten işlenmiş")

    request.status = "rejected"
    request.rejection_note = rejection_note.strip()
    request.reviewed_by = owner.id
    request.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(request)
    return request


def pending_request_count(db: Session, owner_id: int) -> int:
    return (
        db.query(LeadRequest)
        .filter(LeadRequest.owner_id == owner_id, LeadRequest.status == "pending")
        .count()
    )

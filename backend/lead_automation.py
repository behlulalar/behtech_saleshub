from app_timezone import local_today
from database import Lead
from text_format import normalize_lead_text_fields

DEMO_EARLY_STATUSES = {"Yeni", "İletişime Geçildi", "Takip Bekliyor", "Cevap Yok"}


def apply_lead_automation(data: dict, existing: Lead | None = None) -> dict:
    """Otomasyon kurallarını kayıt öncesi uygular."""
    result = normalize_lead_text_fields(dict(data))

    demo_sent = result.get("demo_gonderildi")
    demo_date = (result.get("demo_tarihi") or "").strip()
    if existing is not None and demo_sent is None:
        demo_sent = existing.demo_gonderildi
    if existing is not None and "demo_tarihi" not in result:
        demo_date = (existing.demo_tarihi or "").strip()

    if demo_sent or demo_date:
        result["demo_gonderildi"] = True
        if not (result.get("demo_tarihi") or "").strip():
            result["demo_tarihi"] = demo_date or local_today().isoformat()

        durum = result.get("durum")
        if existing is not None and durum is None:
            durum = existing.durum
        if durum in DEMO_EARLY_STATUSES:
            result["durum"] = "Demo Gönderildi"

    amount = float(result.get("satis_tutari") or 0)
    if amount > 0 and not (result.get("satis_tarihi") or "").strip():
        existing_date = (existing.satis_tarihi or "").strip() if existing is not None else ""
        result["satis_tarihi"] = existing_date or local_today().isoformat()

    return result

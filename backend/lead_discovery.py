"""
Google Places API (New) ile lead keşfi.

Field mask minimal tutulur (Enterprise + Atmosphere SKU):
places.id, displayName, formattedAddress, nationalPhoneNumber, rating, userRatingCount, location
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from activities import activities_for_new_lead, record_activities
from config import settings
from text_format import normalize_business_name
from database import ApiUsageLog, Lead, LeadDiscoveryScan
from lead_automation import apply_lead_automation

logger = logging.getLogger("behtech.discovery")

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
SKU_TYPE = "text_search_enterprise_atmosphere"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.nationalPhoneNumber,places.rating,places.userRatingCount,places.location"
)

CITY_COORDS: dict[str, tuple[float, float]] = {
    "adana": (37.0, 35.3213),
    "ankara": (39.9334, 32.8597),
    "antalya": (36.8969, 30.7133),
    "aydin": (37.856, 27.8416),
    "balikesir": (39.6484, 27.8826),
    "bursa": (40.1885, 29.061),
    "denizli": (37.7765, 29.0864),
    "diyarbakir": (37.9144, 40.2306),
    "duzce": (40.8438, 31.1565),
    "eskisehir": (39.7767, 30.5206),
    "gaziantep": (37.0662, 37.3833),
    "istanbul": (41.0082, 28.9784),
    "izmir": (38.4192, 27.1287),
    "kocaeli": (40.8533, 29.8815),
    "konya": (37.8746, 32.4932),
    "malatya": (38.3552, 38.3095),
    "manisa": (38.6191, 27.4289),
    "mersin": (36.8121, 34.6415),
    "mugla": (37.2153, 28.3636),
    "sakarya": (40.7731, 30.3948),
    "samsun": (41.2867, 36.33),
    "tekirdag": (40.978, 27.511),
    "trabzon": (41.0027, 39.7168),
}

# İlçe / yaygın yazımlar → il merkezi (grid tarama için)
CITY_ALIASES: dict[str, str] = {
    "adapazari": "sakarya",
    "serdivan": "sakarya",
    "hendek": "sakarya",
    "gebze": "kocaeli",
    "izmit": "kocaeli",
    "korfez": "kocaeli",
    "bodrum": "mugla",
    "fethiye": "mugla",
    "bornova": "izmir",
    "karsiyaka": "izmir",
}

_GEOCODE_CACHE: dict[str, tuple[float, float]] = {}
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
class DiscoveryError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class QuotaExceededError(DiscoveryError):
    def __init__(self, message: str, usage: dict[str, Any]):
        super().__init__(message, status_code=402)
        self.usage = usage


def current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def normalize_key(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_only = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_only)


def normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("90") and len(digits) >= 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


def region_key(city: str, district: str, sector_keyword: str) -> str:
    raw = f"{normalize_key(city)}|{normalize_key(district)}|{normalize_key(sector_keyword)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def map_sector_to_category(sector_keyword: str, category: str | None = None) -> str:
    if category:
        return category.strip()
    normalized = normalize_key(sector_keyword)
    if any(token in normalized for token in ("dovme", "dövme", "tattoo", "piercing")):
        return "dovme"
    if any(token in normalized for token in ("berber", "kuaf", "barber", "hair")):
        return "berber"
    if any(token in normalized for token in ("guzellik", "güzellik", "beauty", "nail", "spa")):
        return "guzellik"
    return "berber"


def _static_city_coords(city: str) -> tuple[float, float] | None:
    key = normalize_key(city)
    alias = CITY_ALIASES.get(key)
    if alias and alias in CITY_COORDS:
        return CITY_COORDS[alias]
    if key in CITY_COORDS:
        return CITY_COORDS[key]
    for name, coords in CITY_COORDS.items():
        if name in key or key in name:
            return coords
    return None


def geocode_city_coords(city: str, district: str, api_key: str) -> tuple[float, float] | None:
    """Google Geocoding ile şehir/ilçe merkez koordinatı (Türkiye)."""
    parts = [part.strip() for part in (district, city, "Türkiye") if part and part.strip()]
    address = ", ".join(parts)

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                GEOCODE_URL,
                params={
                    "address": address,
                    "key": api_key,
                    "region": "tr",
                    "language": "tr",
                    "components": "country:TR",
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("Geocoding request failed for %s: %s", address, exc)
        return None

    if response.status_code != 200:
        logger.warning("Geocoding HTTP %s for %s", response.status_code, address)
        return None

    payload = response.json()
    status = payload.get("status")
    if status != "OK":
        logger.info("Geocoding status %s for %s", status, address)
        return None

    results = payload.get("results") or []
    if not results:
        return None

    location = (results[0].get("geometry") or {}).get("location") or {}
    lat, lng = location.get("lat"), location.get("lng")
    if lat is None or lng is None:
        return None

    return float(lat), float(lng)


def resolve_city_coords(
    city: str,
    district: str = "",
    *,
    api_key: str | None = None,
) -> tuple[float, float] | None:
    cache_key = normalize_key(f"{district}|{city}")
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    coords = _static_city_coords(city)
    if not coords and district.strip():
        coords = _static_city_coords(district)

    if not coords and api_key:
        coords = geocode_city_coords(city, district, api_key)

    if coords:
        _GEOCODE_CACHE[cache_key] = coords
    return coords


def supported_cities_hint() -> str:
    return ", ".join(sorted(CITY_COORDS.keys()))


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def generate_grid_centers(lat: float, lng: float, radius_m: int, cell_m: int, max_cells: int) -> list[tuple[float, float]]:
    lat_step = cell_m / 111_000
    lng_step = cell_m / (111_000 * max(math.cos(math.radians(lat)), 0.2))
    steps = max(1, math.ceil(radius_m / cell_m))
    centers: list[tuple[float, float]] = []
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            c_lat = lat + i * lat_step
            c_lng = lng + j * lng_step
            if haversine_m(lat, lng, c_lat, c_lng) <= radius_m:
                centers.append((c_lat, c_lng))
    centers.sort(key=lambda c: haversine_m(lat, lng, c[0], c[1]))
    return centers[:max_cells]


def get_usage_summary(db: Session, user_id: int) -> dict[str, Any]:
    month = current_month()
    row = (
        db.query(ApiUsageLog)
        .filter(
            ApiUsageLog.user_id == user_id,
            ApiUsageLog.month == month,
            ApiUsageLog.sku_type == SKU_TYPE,
        )
        .first()
    )
    used = row.query_count if row else 0
    free_quota = settings.places_free_quota_monthly
    remaining = max(0, free_quota - used)
    return {
        "month": month,
        "sku_type": SKU_TYPE,
        "used": used,
        "free_quota": free_quota,
        "remaining": remaining,
        "warning": used >= settings.places_quota_warning,
        "over_quota": used >= free_quota,
    }


def increment_usage(db: Session, user_id: int, count: int = 1) -> dict[str, Any]:
    month = current_month()
    row = (
        db.query(ApiUsageLog)
        .filter(
            ApiUsageLog.user_id == user_id,
            ApiUsageLog.month == month,
            ApiUsageLog.sku_type == SKU_TYPE,
        )
        .first()
    )
    if not row:
        row = ApiUsageLog(user_id=user_id, month=month, sku_type=SKU_TYPE, query_count=0)
        db.add(row)
    row.query_count += count
    row.updated_at = datetime.utcnow()
    db.commit()
    summary = get_usage_summary(db, user_id)
    if summary["warning"] and not summary["over_quota"]:
        logger.warning(
            "places_quota_warning user_id=%s used=%s free_quota=%s",
            user_id,
            summary["used"],
            summary["free_quota"],
        )
    return summary


def ensure_quota(db: Session, user_id: int, queries_needed: int, confirm_over_quota: bool) -> dict[str, Any]:
    summary = get_usage_summary(db, user_id)
    projected = summary["used"] + queries_needed
    if projected > summary["free_quota"] and not confirm_over_quota:
        raise QuotaExceededError(
            "Bu ay ücretsiz sorgu kotası aşılacak. Devam etmek için onaylayın.",
            summary,
        )
    return summary


def check_rescan_allowed(db: Session, user_id: int, city: str, district: str, sector_keyword: str) -> datetime | None:
    key = region_key(city, district, sector_keyword)
    scan = (
        db.query(LeadDiscoveryScan)
        .filter(LeadDiscoveryScan.user_id == user_id, LeadDiscoveryScan.region_key == key)
        .order_by(LeadDiscoveryScan.scanned_at.desc())
        .first()
    )
    if not scan:
        return None
    blocked_until = scan.scanned_at + timedelta(hours=settings.places_rescan_hours)
    if datetime.utcnow() < blocked_until:
        return blocked_until
    return None


def record_scan(db: Session, user_id: int, city: str, district: str, sector_keyword: str) -> None:
    db.add(
        LeadDiscoveryScan(
            user_id=user_id,
            region_key=region_key(city, district, sector_keyword),
            city=city.strip(),
            district=(district or "").strip(),
            sector_keyword=sector_keyword.strip(),
            scanned_at=datetime.utcnow(),
        )
    )
    db.commit()


def _place_id(raw: str) -> str:
    return raw.split("/")[-1] if raw else ""


def _parse_place(item: dict[str, Any]) -> dict[str, Any]:
    location = item.get("location") or {}
    rating_count = item.get("userRatingCount")
    rating = item.get("rating")
    return {
        "google_place_id": _place_id(item.get("id", "")),
        "business_name": normalize_business_name((item.get("displayName") or {}).get("text", "").strip()),
        "address": (item.get("formattedAddress") or "").strip(),
        "phone_number": (item.get("nationalPhoneNumber") or "").strip(),
        "rating": float(rating) if rating is not None else None,
        "rating_count": int(rating_count) if rating_count is not None else None,
        "latitude": float(location.get("latitude")) if location.get("latitude") is not None else None,
        "longitude": float(location.get("longitude")) if location.get("longitude") is not None else None,
    }


def search_text(
    api_key: str,
    *,
    text_query: str,
    center: tuple[float, float] | None = None,
    radius_m: int = 2500,
    page_token: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    payload: dict[str, Any] = {"textQuery": text_query, "pageSize": 20}
    if page_token:
        payload["pageToken"] = page_token
    if center:
        payload["locationBias"] = {
            "circle": {
                "center": {"latitude": center[0], "longitude": center[1]},
                "radius": float(radius_m),
            }
        }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(PLACES_SEARCH_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise DiscoveryError("Google Places API'ye bağlanılamadı") from exc

    if response.status_code == 403:
        raise DiscoveryError("Google Places API anahtarı geçersiz veya yetkisiz", status_code=403)
    if response.status_code == 429:
        raise DiscoveryError("Google Places API kotası aşıldı", status_code=429)
    if response.status_code >= 400:
        detail = response.text[:300]
        raise DiscoveryError(f"Google Places API hatası: {detail or response.status_code}")

    data = response.json()
    places = [_parse_place(item) for item in data.get("places") or []]
    return places, data.get("nextPageToken")


def build_text_query(sector_keyword: str, city: str, district: str) -> str:
    parts = [sector_keyword.strip()]
    if district.strip():
        parts.append(district.strip())
    parts.append(city.strip())
    return " ".join(parts)


def existing_lead_index(db: Session, user_id: int) -> tuple[dict[str, Lead], dict[str, Lead]]:
    by_place: dict[str, Lead] = {}
    by_phone: dict[str, Lead] = {}
    leads = db.query(Lead).filter(Lead.user_id == user_id).all()
    for lead in leads:
        if lead.google_place_id:
            by_place[lead.google_place_id] = lead
        phone = normalize_phone(lead.whatsapp)
        if phone:
            by_phone[phone] = lead
    return by_place, by_phone


def enrich_result(
    place: dict[str, Any],
    *,
    by_place: dict[str, Lead],
    by_phone: dict[str, Lead],
) -> dict[str, Any]:
    phone_norm = normalize_phone(place.get("phone_number"))
    existing = by_place.get(place["google_place_id"])
    if not existing and phone_norm:
        existing = by_phone.get(phone_norm)

    rating_count = place.get("rating_count")
    low_digital = rating_count is not None and rating_count < settings.places_low_rating_count_threshold

    return {
        **place,
        "phone_normalized": phone_norm,
        "already_in_crm": existing is not None,
        "existing_lead_id": existing.id if existing else None,
        "low_digital_presence": low_digital,
    }


def discover_leads(
    db: Session,
    user_id: int,
    *,
    city: str,
    district: str = "",
    sector_keyword: str,
    category: str | None = None,
    radius_meters: int = 5000,
    confirm_over_quota: bool = False,
    include_pagination: bool = False,
) -> dict[str, Any]:
    if not settings.google_places_api_key:
        raise DiscoveryError("GOOGLE_PLACES_API_KEY yapılandırılmamış", status_code=503)

    city = city.strip()
    sector_keyword = sector_keyword.strip()
    if not city or not sector_keyword:
        raise DiscoveryError("Şehir ve sektör anahtar kelimesi zorunludur")

    blocked_until = check_rescan_allowed(db, user_id, city, district, sector_keyword)
    if blocked_until:
        raise DiscoveryError(
            f"Bu bölge/sektör {blocked_until.strftime('%d.%m.%Y %H:%M')} UTC'ye kadar tekrar taranamaz",
            status_code=409,
        )

    coords = resolve_city_coords(city, district, api_key=settings.google_places_api_key)
    if not coords:
        raise DiscoveryError(
            "Şehir koordinatı bulunamadı. İl adını Türkçe yazın (ör. Sakarya, Denizli). "
            "İlçe alanına Adapazarı, Gebze gibi değer girebilirsiniz. "
            "Google Geocoding API kapalıysa yedek liste: "
            + supported_cities_hint()
        )

    cells = generate_grid_centers(
        coords[0],
        coords[1],
        radius_meters,
        settings.places_grid_cell_meters,
        settings.places_max_grid_cells,
    )
    queries_needed = len(cells)
    usage_before = ensure_quota(db, user_id, queries_needed, confirm_over_quota)

    text_query = build_text_query(sector_keyword, city, district)
    merged: dict[str, dict[str, Any]] = {}
    queries_used = 0

    for center in cells:
        places, _ = search_text(
            settings.google_places_api_key,
            text_query=text_query,
            center=center,
            radius_m=min(settings.places_grid_cell_meters, radius_meters),
        )
        queries_used += 1
        for place in places:
            if place["google_place_id"]:
                merged[place["google_place_id"]] = place

        if include_pagination:
            # Pagination her sayfa ek sorgu sayılır; varsayılan kapalı.
            pass

    usage = increment_usage(db, user_id, queries_used)
    record_scan(db, user_id, city, district, sector_keyword)

    by_place, by_phone = existing_lead_index(db, user_id)
    results = [
        enrich_result(place, by_place=by_place, by_phone=by_phone)
        for place in merged.values()
        if place.get("business_name")
    ]
    results.sort(key=lambda item: (item["already_in_crm"], -(item.get("rating_count") or 0), item["business_name"]))

    mapped_category = map_sector_to_category(sector_keyword, category)

    return {
        "results": results,
        "queries_used": queries_used,
        "total_found": len(results),
        "mapped_category": mapped_category,
        "usage": usage,
        "usage_before": usage_before,
        "text_query": text_query,
    }


def _discovery_notes(place: dict[str, Any], city: str) -> str:
    lines = [f"Kaynak: Google Places"]
    if place.get("address"):
        lines.append(f"Adres: {place['address']}")
    if place.get("rating") is not None:
        rc = place.get("rating_count")
        lines.append(f"Google puanı: {place['rating']} ({rc or 0} yorum)")
    if place.get("low_digital_presence"):
        lines.append("Not: Düşük dijital varlık (az yorum — sıcak lead adayı)")
    return "\n".join(lines)


def import_discovered_leads(
    db: Session,
    user_id: int,
    *,
    category: str,
    places: list[dict[str, Any]],
    city: str,
) -> dict[str, Any]:
    by_place, by_phone = existing_lead_index(db, user_id)
    created = 0
    updated = 0
    skipped = 0
    lead_ids: list[int] = []

    for place in places:
        place_id = place.get("google_place_id") or ""
        if not place_id:
            skipped += 1
            continue

        phone = (place.get("phone_number") or "").strip()
        phone_norm = normalize_phone(phone)
        existing = by_place.get(place_id)
        if not existing and phone_norm:
            existing = by_phone.get(phone_norm)

        if existing:
            existing.google_place_id = place_id
            existing.source = "google_places"
            if phone and not existing.whatsapp:
                existing.whatsapp = phone
            if place.get("latitude") is not None:
                existing.latitude = place["latitude"]
            if place.get("longitude") is not None:
                existing.longitude = place["longitude"]
            if place.get("rating") is not None:
                existing.google_rating = place["rating"]
            if place.get("rating_count") is not None:
                existing.google_rating_count = place["rating_count"]
            existing.updated_at = datetime.utcnow()
            updated += 1
            lead_ids.append(existing.id)
            continue

        payload = apply_lead_automation(
            {
                "isletme_adi": place.get("business_name") or "İsimsiz İşletme",
                "yetkili": "",
                "sehir": city.strip(),
                "whatsapp": phone,
                "ilk_iletisim_kanali": "Google Places",
                "durum": "Yeni",
                "oncelik": "yuksek" if place.get("low_digital_presence") else "orta",
                "notlar": _discovery_notes(place, city),
            }
        )

        lead = Lead(
            user_id=user_id,
            category=category,
            source="google_places",
            google_place_id=place_id,
            latitude=place.get("latitude"),
            longitude=place.get("longitude"),
            google_rating=place.get("rating"),
            google_rating_count=place.get("rating_count"),
            **payload,
        )
        db.add(lead)
        db.flush()
        record_activities(
            db,
            user_id,
            lead.id,
            activities_for_new_lead(
                {
                    "isletme_adi": lead.isletme_adi,
                    "durum": lead.durum,
                    "ilk_iletisim_kanali": lead.ilk_iletisim_kanali,
                }
            ),
        )
        by_place[place_id] = lead
        if phone_norm:
            by_phone[phone_norm] = lead
        created += 1
        lead_ids.append(lead.id)

    if created or updated:
        db.commit()

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "lead_ids": lead_ids,
    }

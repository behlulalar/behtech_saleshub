from database import Lead

CEVAP_STATUSES = {
    "İletişime Geçildi",
    "Takip Bekliyor",
    "Demo Gönderildi",
    "Görüşme Planlandı",
    "Teklif Verildi",
    "Müşteri",
}

DEMO_STATUSES = {
    "Demo Gönderildi",
    "Görüşme Planlandı",
    "Teklif Verildi",
    "Müşteri",
}

TEKLIF_STATUSES = {
    "Teklif Verildi",
    "Müşteri",
}

FUNNEL_DEFINITIONS = [
    ("iletisim", "Kişi"),
    ("cevap", "Cevap"),
    ("demo", "Demo"),
    ("teklif", "Teklif"),
    ("satis", "Satış"),
]


def _reached_cevap(lead: Lead) -> bool:
    return lead.durum in CEVAP_STATUSES


def _reached_demo(lead: Lead) -> bool:
    return lead.demo_gonderildi or lead.durum in DEMO_STATUSES


def _reached_teklif(lead: Lead) -> bool:
    return bool((lead.teklif or "").strip()) or lead.durum in TEKLIF_STATUSES


def _reached_satis(lead: Lead) -> bool:
    return lead.durum == "Müşteri"


def _stage_count(leads: list[Lead], stage_key: str) -> int:
    checks = {
        "iletisim": lambda lead: True,
        "cevap": _reached_cevap,
        "demo": _reached_demo,
        "teklif": _reached_teklif,
        "satis": _reached_satis,
    }
    checker = checks[stage_key]
    return sum(1 for lead in leads if checker(lead))


def _rate(part: int, whole: int) -> float | None:
    if whole <= 0:
        return None
    return round((part / whole) * 100, 1)


def build_sales_funnel(leads: list[Lead]) -> dict:
    counts = {key: _stage_count(leads, key) for key, _ in FUNNEL_DEFINITIONS}
    top = counts["iletisim"] or 0

    stages: list[dict] = []
    previous_count: int | None = None

    for key, label in FUNNEL_DEFINITIONS:
        count = counts[key]
        stages.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "conversion_rate": _rate(count, previous_count) if previous_count is not None else None,
                "overall_rate": _rate(count, top) if top > 0 else (100.0 if count > 0 else 0.0),
            }
        )
        previous_count = count

    return {
        "satis_hunisi": stages,
        "satis_donusum_orani": stages[-1]["overall_rate"] if stages else 0.0,
    }

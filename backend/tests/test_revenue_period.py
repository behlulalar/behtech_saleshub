from datetime import date, datetime

from revenue import in_period, parse_offer_amount, resolve_sale_date


def test_parse_offer_amount():
    assert parse_offer_amount("8500 TL") == 8500
    assert parse_offer_amount("8.500") == 8500
    assert parse_offer_amount("") == 0


def test_resolve_sale_date_prefers_explicit_then_fallback():
    assert resolve_sale_date(satis_tarihi="2026-09-02") == date(2026, 9, 2)
    assert resolve_sale_date(
        satis_tarihi="",
        updated_at=datetime(2026, 8, 15, 12, 0),
        created_at=datetime(2026, 1, 1),
    ) == date(2026, 8, 15)


def test_in_period_filters_year_and_month():
    day = date(2026, 9, 2)
    assert in_period(day, None, None) is True
    assert in_period(day, 2026, None) is True
    assert in_period(day, 2026, 9) is True
    assert in_period(day, 2026, 8) is False
    assert in_period(day, 2025, None) is False
    assert in_period(None, 2026, 9) is False
    assert in_period(None, None, None) is True

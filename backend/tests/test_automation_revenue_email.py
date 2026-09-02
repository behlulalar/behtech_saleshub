from automation import format_revenue_digest_lines


def test_revenue_email_lists_today_payments_separately_from_offer():
    lines = format_revenue_digest_lines(
        today_total=4500,
        today_count=1,
        month_total=4500,
        year_total=4500,
        today_items=[("Roof Tattoo Sakarya", 4500.0, "8500 TL")],
    )
    text = "\n".join(lines)
    assert "kayıt gününe göre" in text
    assert "Bugün: 4.500 ₺ · 1 ödeme" in text
    assert "Bu ay: 4.500 ₺" in text
    assert "Roof Tattoo Sakarya — 4.500 ₺ · teklif 8500 TL" in text


def test_revenue_email_without_today_items_still_shows_month_totals():
    lines = format_revenue_digest_lines(
        today_total=0,
        today_count=0,
        month_total=6500,
        year_total=6500,
        today_items=[],
    )
    text = "\n".join(lines)
    assert "Bugün: 0 ₺ · 0 ödeme" in text
    assert "Bu ay: 6.500 ₺" in text
    assert "Bugünkü tahsilatlar" not in text

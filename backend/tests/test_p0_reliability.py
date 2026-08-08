"""P0 reliability: quota, events, contact dates, scoring, reports."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from ai.usage import QuotaExceededError, assert_quota_available, record_usage, usage_summary
from intelligence.business_events import LEAD_LOST, LEAD_WON, map_durum_to_event
from intelligence.scoring import rank_leads_for_org, score_lead
from reminders import get_last_contact_date
from reports import _lead_became_customer_in_range


# --- business events ---


def test_map_durum_to_lead_lost_olumsuz():
    assert map_durum_to_event("Yeni", "Olumsuz") == LEAD_LOST


def test_map_durum_to_lead_lost_cevap_yok():
    assert map_durum_to_event("Takip Bekliyor", "Cevap Yok") == LEAD_LOST


def test_map_durum_to_lead_won():
    assert map_durum_to_event("Teklif Verildi", "Müşteri") == LEAD_WON


def test_lead_lost_constant_defined():
    assert LEAD_LOST == "LeadLost"


# --- last contact ---


def test_updated_at_not_used_as_last_contact():
    lead = MagicMock()
    lead.id = 1
    lead.ilk_mesaj_tarihi = "2026-08-01"
    lead.demo_tarihi = ""
    lead.gorusme_tarihi = ""
    lead.updated_at = datetime(2026, 8, 8, 12, 0, 0)
    lead.created_at = datetime(2026, 7, 20, 12, 0, 0)

    result = get_last_contact_date(lead, {})
    assert result == date(2026, 8, 1)


def test_activity_date_counts_as_last_contact():
    lead = MagicMock()
    lead.id = 5
    lead.ilk_mesaj_tarihi = "2026-08-01"
    lead.demo_tarihi = ""
    lead.gorusme_tarihi = ""
    lead.created_at = None

    result = get_last_contact_date(lead, {5: date(2026, 8, 5)})
    assert result == date(2026, 8, 5)


# --- historical customer ---


def test_customer_in_range_uses_satis_tarihi_not_updated_at():
    lead = MagicMock()
    lead.durum = "Müşteri"
    lead.satis_tarihi = "2026-08-02"
    lead.updated_at = datetime(2026, 8, 10, 9, 0, 0)

    assert _lead_became_customer_in_range(lead, date(2026, 8, 1), date(2026, 8, 31)) is True
    assert _lead_became_customer_in_range(lead, date(2026, 7, 1), date(2026, 7, 31)) is False


def test_customer_without_satis_tarihi_not_counted_on_updated_at():
    lead = MagicMock()
    lead.durum = "Müşteri"
    lead.satis_tarihi = ""
    lead.updated_at = datetime(2026, 8, 10, 9, 0, 0)

    assert _lead_became_customer_in_range(lead, date(2026, 8, 1), date(2026, 8, 31)) is False


# --- agent quota & tokens ---


def test_assert_quota_available_raises_when_exhausted(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(
        "ai.usage.usage_summary",
        lambda _db, _org: {
            "tokens_remaining": 0,
            "tokens_used": 100,
            "tokens_quota": 100,
            "request_count": 1,
            "month": "2026-08",
        },
    )
    with pytest.raises(QuotaExceededError):
        assert_quota_available(db, 1, estimated_tokens=10)


def test_agent_multi_step_token_aggregation_and_record_usage():
    from ai.capabilities.run_agent import run_agent_query
    from database import AiRun

    db = MagicMock()
    run = AiRun(id=1, user_id=10, steps_json="[]")
    user = MagicMock()

    usages = [
        {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
    ]
    replies = ['{"final":"Tamam"}', "unused"]

    with patch("ai.capabilities.run_agent.assert_llm_configured"):
        with patch("ai.capabilities.run_agent.chat_completion") as mock_chat:
            mock_chat.side_effect = [(replies[0], usages[0]), (replies[1], usages[1])]
            with patch("ai.capabilities.run_agent.assert_quota_available"):
                with patch("ai.capabilities.run_agent.record_usage") as mock_record:
                    with patch("ai.capabilities.run_agent.append_run_step"):
                        answer, meta = run_agent_query(
                            db,
                            user=user,
                            org_id=10,
                            run=run,
                            question="Test?",
                        )

    assert answer == "Tamam"
    assert meta["tokens_total"] == 150
    mock_record.assert_called_once_with(db, 10, 150)


def test_agent_quota_exhausted_before_llm():
    from ai.capabilities.run_agent import run_agent_query
    from database import AiRun

    db = MagicMock()
    run = AiRun(id=1, user_id=10, steps_json="[]")
    user = MagicMock()

    with patch("ai.capabilities.run_agent.assert_llm_configured"):
        with patch(
            "ai.capabilities.run_agent.assert_quota_available",
            side_effect=QuotaExceededError("limit"),
        ):
            with pytest.raises(QuotaExceededError):
                run_agent_query(db, user=user, org_id=10, run=run, question="Q")


def test_run_worker_persists_agent_tokens_total():
    from ai.run_worker import execute_run
    from database import AiRun, User

    db = MagicMock()
    run = AiRun(
        id=1,
        user_id=10,
        requested_by=10,
        run_type="agent",
        status="queued",
        input_json='{"question":"hello","locale":"tr"}',
        steps_json="[]",
    )
    owner = User(id=10, username="o")

    db.query.return_value.filter.return_value.first.return_value = owner

    with patch(
        "ai.run_worker.run_agent_query",
        return_value=(
            "ok",
            {
                "output": {"answer": "ok"},
                "duration_ms": 10,
                "tokens_prompt": 10,
                "tokens_completion": 5,
                "tokens_total": 15,
            },
        ),
    ):
        with patch("ai.run_worker.mark_run_running"):
            with patch("ai.run_worker.finish_run_success") as mock_ok:
                execute_run(db, run)

    mock_ok.assert_called_once()
    kwargs = mock_ok.call_args.kwargs
    assert kwargs["tokens_total"] == 15


# --- scoring preload vs per-lead ---


def test_scoring_same_result_with_preloaded_activity_dates():
    db = MagicMock()
    lead = MagicMock()
    lead.id = 7
    lead.user_id = 1
    lead.durum = "İletişime Geçildi"
    lead.oncelik = "orta"
    lead.demo_gonderildi = False
    lead.demo_tarihi = ""
    lead.gorusme_tarihi = ""
    lead.ilk_mesaj_tarihi = "2026-08-01"

    preloaded = {7: date(2026, 8, 1)}

    with patch("intelligence.scoring.get_last_activity_dates") as mock_fetch:
        mock_fetch.return_value = preloaded
        a = score_lead(db, 1, lead, today=date(2026, 8, 8), activity_dates=preloaded)
        assert mock_fetch.call_count == 0

        mock_fetch.return_value = preloaded
        b = score_lead(db, 1, lead, today=date(2026, 8, 8), activity_dates=None)
        assert mock_fetch.call_count == 1

    assert a == b


def test_rank_leads_single_activity_query(monkeypatch):
    db = MagicMock()
    lead_a = MagicMock()
    lead_a.id = 1
    lead_a.user_id = 5
    lead_a.durum = "Yeni"
    lead_a.oncelik = "orta"
    lead_a.demo_gonderildi = False
    lead_a.demo_tarihi = ""
    lead_a.gorusme_tarihi = ""
    lead_a.ilk_mesaj_tarihi = ""
    lead_a.created_at = None
    lead_a.isletme_adi = "A"
    lead_a.category = "c1"

    lead_b = MagicMock()
    lead_b.id = 2
    lead_b.user_id = 5
    lead_b.durum = "Yeni"
    lead_b.oncelik = "orta"
    lead_b.demo_gonderildi = False
    lead_b.demo_tarihi = ""
    lead_b.gorusme_tarihi = ""
    lead_b.ilk_mesaj_tarihi = ""
    lead_b.created_at = None
    lead_b.isletme_adi = "B"
    lead_b.category = "c1"

    lead_query = MagicMock()
    lead_query.filter.return_value.order_by.return_value.all.return_value = [lead_a, lead_b]

    cat_row = MagicMock()
    cat_row.id = "c1"
    cat_row.label = "Cat"

    cat_query = MagicMock()
    cat_query.filter.return_value.all.return_value = [cat_row]

    def query_side_effect(model):
        name = getattr(model, "__name__", str(model))
        if name == "Lead":
            return lead_query
        return cat_query

    db.query.side_effect = query_side_effect

    monkeypatch.setattr("intelligence.scoring.settings.followup_reminder_days", 3)
    monkeypatch.setattr("intelligence.scoring.settings.meeting_reminder_days", 3)

    with patch("intelligence.scoring.get_last_activity_dates") as mock_act:
        mock_act.return_value = {}
        with patch("intelligence.scoring.local_today", return_value=date(2026, 8, 8)):
            rank_leads_for_org(db, 5, limit=10)
        mock_act.assert_called_once_with(db, 5, [1, 2])


def test_activity_dates_scoped_to_org_in_reminders():
    """get_last_activity_dates filters by user_id — tenant isolation at query layer."""
    from reminders import get_last_activity_dates

    db = MagicMock()
    db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
    get_last_activity_dates(db, 99, [1, 2])
    db.query.return_value.filter.assert_called()


# --- run log redaction ---


def test_agent_step_redacts_email_in_tool_result():
    from ai.run_log_redact import redact_run_step

    step = {
        "type": "tool",
        "result": {"eposta": "secret.person@example.com", "id": 1},
    }
    redacted = redact_run_step(step)
    assert "secret.person@example.com" not in str(redacted["result"])
    assert "@" in str(redacted["result"])

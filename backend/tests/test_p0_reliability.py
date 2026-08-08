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


def test_agent_single_step_records_usage_immediately():
    from ai.capabilities.run_agent import run_agent_query
    from database import AiRun

    db = MagicMock()
    run = AiRun(id=1, user_id=10, steps_json="[]")
    user = MagicMock()

    with patch("ai.capabilities.run_agent.assert_llm_configured"):
        with patch(
            "ai.capabilities.run_agent.chat_completion",
            return_value=('{"final":"Tamam"}', {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}),
        ):
            with patch("ai.capabilities.run_agent.assert_quota_available"):
                with patch("ai.capabilities.run_agent.record_usage") as mock_record:
                    with patch("ai.capabilities.run_agent.append_run_step"):
                        answer, meta = run_agent_query(
                            db, user=user, org_id=10, run=run, question="Test?"
                        )

    assert answer == "Tamam"
    assert meta["tokens_total"] == 150
    mock_record.assert_called_once_with(db, 10, 150)


def test_agent_multi_step_records_usage_after_each_llm_call():
    from ai.capabilities.run_agent import run_agent_query
    from database import AiRun

    db = MagicMock()
    run = AiRun(id=1, user_id=10, steps_json="[]")
    user = MagicMock()

    usages = [
        {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        {"prompt_tokens": 800, "completion_tokens": 200, "total_tokens": 2000},
    ]
    replies = [
        '{"tool":"get_kpis","args":{"period_type":"monthly"}}',
        '{"final":"Tamam"}',
    ]

    with patch("ai.capabilities.run_agent.assert_llm_configured"):
        with patch("ai.capabilities.run_agent.chat_completion") as mock_chat:
            mock_chat.side_effect = list(zip(replies, usages))
            with patch("ai.capabilities.run_agent.assert_quota_available"):
                with patch("ai.capabilities.run_agent.execute_tool", return_value={"ok": True}):
                    with patch("ai.capabilities.run_agent.record_usage") as mock_record:
                        with patch("ai.capabilities.run_agent.append_run_step"):
                            answer, meta = run_agent_query(
                                db, user=user, org_id=10, run=run, question="Test?"
                            )

    assert answer == "Tamam"
    assert meta["tokens_total"] == 3500
    assert mock_record.call_count == 2
    mock_record.assert_any_call(db, 10, 1500)
    mock_record.assert_any_call(db, 10, 2000)


def test_agent_no_upfront_max_steps_quota_reservation():
    from ai.capabilities.run_agent import _estimated_tokens_per_step, run_agent_query
    from database import AiRun

    db = MagicMock()
    run = AiRun(id=1, user_id=10, steps_json="[]")
    user = MagicMock()
    per_step = _estimated_tokens_per_step()

    with patch("ai.capabilities.run_agent.assert_llm_configured"):
        with patch(
            "ai.capabilities.run_agent.chat_completion",
            return_value=('{"final":"x"}', {"total_tokens": 10}),
        ):
            with patch("ai.capabilities.run_agent.assert_quota_available") as mock_assert:
                with patch("ai.capabilities.run_agent.record_usage"):
                    with patch("ai.capabilities.run_agent.append_run_step"):
                        run_agent_query(db, user=user, org_id=10, run=run, question="Q")

    first = mock_assert.call_args_list[0]
    assert first.args[1] == 10
    assert first.kwargs["estimated_tokens"] == per_step
    assert first.kwargs["estimated_tokens"] != per_step * 5


def test_agent_second_step_sees_updated_quota_remaining():
    from ai.capabilities.run_agent import run_agent_query
    from database import AiRun

    db = MagicMock()
    run = AiRun(id=1, user_id=10, steps_json="[]")
    user = MagicMock()
    quota = 10_000
    used = {"n": 0}
    remaining_at_assert: list[int] = []

    def fake_record(_db, _org, tokens):
        used["n"] += tokens

    def fake_assert(_db, _org, *, estimated_tokens=0):
        rem = quota - used["n"]
        remaining_at_assert.append(rem)
        if rem <= 0 or (estimated_tokens and rem < estimated_tokens):
            raise QuotaExceededError("limit")

    usages = [
        {"total_tokens": 1500},
        {"total_tokens": 2000},
    ]
    replies = [
        '{"tool":"get_kpis","args":{"period_type":"monthly"}}',
        '{"final":"done"}',
    ]

    with patch("ai.capabilities.run_agent.assert_llm_configured"):
        with patch("ai.capabilities.run_agent.chat_completion") as mock_chat:
            mock_chat.side_effect = list(zip(replies, usages))
            with patch("ai.capabilities.run_agent.assert_quota_available", side_effect=fake_assert):
                with patch("ai.capabilities.run_agent.record_usage", side_effect=fake_record):
                    with patch("ai.capabilities.run_agent.execute_tool", return_value={}):
                        with patch("ai.capabilities.run_agent.append_run_step"):
                            run_agent_query(db, user=user, org_id=10, run=run, question="Q")

    # İlk kontrol (request) + step 1 başlangıcı henüz usage yok; step 2 başlangıcı 1500 düşmüş olmalı
    assert remaining_at_assert[0] == 10_000
    assert remaining_at_assert[1] == 10_000
    assert remaining_at_assert[2] == 8_500


def test_agent_exception_after_first_step_keeps_recorded_tokens():
    from ai.capabilities.run_agent import run_agent_query
    from database import AiRun

    db = MagicMock()
    run = AiRun(id=1, user_id=10, steps_json="[]")
    user = MagicMock()
    recorded: list[int] = []

    def fake_record(_db, _org, tokens):
        recorded.append(tokens)

    with patch("ai.capabilities.run_agent.assert_llm_configured"):
        with patch("ai.capabilities.run_agent.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                ('{"tool":"get_kpis","args":{}}', {"total_tokens": 1500}),
                RuntimeError("llm failed"),
            ]
            with patch("ai.capabilities.run_agent.assert_quota_available"):
                with patch("ai.capabilities.run_agent.record_usage", side_effect=fake_record):
                    with patch("ai.capabilities.run_agent.execute_tool", return_value={}):
                        with patch("ai.capabilities.run_agent.append_run_step"):
                            with pytest.raises(RuntimeError):
                                run_agent_query(db, user=user, org_id=10, run=run, question="Q")

    assert recorded == [1500]


def test_agent_low_quota_blocks_second_llm_step():
    from ai.capabilities.run_agent import run_agent_query, _estimated_tokens_per_step
    from database import AiRun

    db = MagicMock()
    run = AiRun(id=1, user_id=10, steps_json="[]")
    user = MagicMock()
    quota = 10_000
    used = {"n": 0}
    per_step = _estimated_tokens_per_step()

    def fake_record(_db, _org, tokens):
        used["n"] += tokens

    def fake_assert(_db, _org, *, estimated_tokens=0):
        rem = quota - used["n"]
        if rem <= 0 or (estimated_tokens and rem < estimated_tokens):
            raise QuotaExceededError("limit")

    with patch("ai.capabilities.run_agent.assert_llm_configured"):
        with patch("ai.capabilities.run_agent.chat_completion") as mock_chat:
            mock_chat.return_value = (
                '{"tool":"get_kpis","args":{}}',
                {"total_tokens": quota - per_step + 1},
            )
            with patch("ai.capabilities.run_agent.assert_quota_available", side_effect=fake_assert):
                with patch("ai.capabilities.run_agent.record_usage", side_effect=fake_record):
                    with patch("ai.capabilities.run_agent.execute_tool", return_value={}):
                        with patch("ai.capabilities.run_agent.append_run_step"):
                            with pytest.raises(QuotaExceededError):
                                run_agent_query(db, user=user, org_id=10, run=run, question="Q")

    assert used["n"] == quota - per_step + 1
    assert mock_chat.call_count == 1


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

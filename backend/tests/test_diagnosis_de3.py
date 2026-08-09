"""DE-3 — AI Diagnosis Interpreter (stage tests grow with implementation)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from config import settings
from schemas import (
    DiagnosisInterpretation,
    DiagnosisInterpretRequest,
    DiagnosisInterpretResponse,
    DiagnosisRecommendedAction,
)
from ai.context.diagnosis_context import (
    build_diagnosis_interpret_context,
    compute_context_fingerprint,
)


def _sample_follow_up_diagnosis() -> dict:
    return {
        "diagnosis_id": "follow_up_idle_leads",
        "type": "follow_up",
        "severity": "high",
        "title": "Takip",
        "description": "desc",
        "metric": "days_since_last_contact",
        "current_value": 19.0,
        "previous_value": None,
        "change_percent": None,
        "affected_lead_count": 85,
        "detected_at": "2026-08-09T12:00:00+03:00",
        "affected_leads_available": True,
        "evidence": {
            "affected_lead_count": 85,
            "no_contact_count": 10,
            "idle_contact_count": 75,
            "oldest_days_idle": 19,
            "average_days_idle": 12.0,
            "threshold_medium_days": 5,
            "threshold_high_days": 10,
            "sample_lead_ids": [1, 2, 3],
            "worst_case": {"lead_id": 128, "days_idle": 19, "reason": "idle_after_contact"},
        },
        "impact": {
            "affected_lead_count": 85,
            "high_priority_count": 8,
            "medium_priority_count": 77,
            "low_priority_count": 0,
            "estimated_pipeline_value": 999999,
        },
        "top_priority_leads": [
            {
                "lead_id": 128,
                "lead_name": "Test Kuaför",
                "durum": "Demo Gönderildi",
                "existing_lead_score": 87,
                "diagnosis_modifier": 0,
                "diagnosis_priority_score": 87,
                "priority": "high",
                "reason_codes": ["high_lead_score"],
                "idle_days": 19,
                "offer_age_days": None,
                "eposta": "secret@example.com",
                "whatsapp": "555",
            }
        ],
    }


def test_context_builder_whitelist_and_no_detected_at():
    ctx = build_diagnosis_interpret_context(
        _sample_follow_up_diagnosis(),
        locale="tr",
        period_type="monthly",
        anchor="2026-08-01",
    )
    assert set(ctx.keys()) == {
        "locale",
        "period_type",
        "anchor",
        "diagnosis",
        "evidence",
        "impact",
        "top_priority_leads",
        "affected_leads_available",
    }
    assert "detected_at" not in ctx["diagnosis"]
    assert "sample_lead_ids" not in ctx["evidence"]
    assert ctx["evidence"]["worst_case"] == {"days_idle": 19, "reason": "idle_after_contact"}
    assert "estimated_pipeline_value" not in ctx["impact"]
    lead = ctx["top_priority_leads"][0]
    assert "eposta" not in lead
    assert "whatsapp" not in lead
    assert lead["lead_name"] == "Test Kuaför"


def test_context_fingerprint_ignores_detected_at_in_source():
    d1 = _sample_follow_up_diagnosis()
    d2 = _sample_follow_up_diagnosis()
    d2["detected_at"] = "2099-01-01T00:00:00+03:00"
    c1 = build_diagnosis_interpret_context(d1, anchor="2026-08-01")
    c2 = build_diagnosis_interpret_context(d2, anchor="2026-08-01")
    assert compute_context_fingerprint(c1) == compute_context_fingerprint(c2)


def test_context_fingerprint_changes_when_impact_changes():
    d = _sample_follow_up_diagnosis()
    c1 = build_diagnosis_interpret_context(d, anchor="2026-08-01")
    d["impact"]["high_priority_count"] = 9
    c2 = build_diagnosis_interpret_context(d, anchor="2026-08-01")
    assert compute_context_fingerprint(c1) != compute_context_fingerprint(c2)


def test_funnel_evidence_subset():
    diagnosis = {
        "diagnosis_id": "funnel_offer_to_won_drop",
        "type": "funnel_drop",
        "severity": "high",
        "title": "t",
        "description": "d",
        "metric": "m",
        "affected_lead_count": 3,
        "evidence": {
            "from_stage": "teklif",
            "to_stage": "satis",
            "current": 10.0,
            "previous": 50.0,
            "sample_lead_ids": [9, 8],
        },
        "impact": {},
        "top_priority_leads": [],
        "affected_leads_available": False,
    }
    ctx = build_diagnosis_interpret_context(diagnosis, anchor="2026-08-01")
    assert ctx["evidence"]["from_stage"] == "teklif"
    assert "sample_lead_ids" not in ctx["evidence"]
    assert ctx["affected_leads_available"] is False


def test_diagnosis_interpret_prompt_loads():
    from ai.prompts.diagnosis_interpret import prompt_version, system_prompt

    text = system_prompt()
    assert "JSON" in text or "json" in text.lower()
    assert "context" in text.lower()
    assert "uydur" in text.lower() or "Grounding" in text
    assert prompt_version().startswith("diagnosis_interpret.md@")


def test_strip_llm_json_content_removes_fences():
    from ai.llm_client import strip_llm_json_content

    raw = '```json\n{"summary":"x"}\n```'
    assert strip_llm_json_content(raw) == '{"summary":"x"}'


def test_chat_completion_structured_uses_json_mode_and_diagnosis_temperature(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.llm_client import chat_completion_structured

    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("config.settings.ai_provider", "openai")

    fake_usage = MagicMock(prompt_tokens=11, completion_tokens=22, total_tokens=33)
    fake_message = MagicMock(content='{"summary":"ok","why_it_matters":"ok","key_findings":[],"recommended_actions":[],"confidence":"low"}')
    fake_choice = MagicMock(message=fake_message)
    fake_response = MagicMock(choices=[fake_choice], usage=fake_usage)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_response

    with patch("ai.llm_client._openai_direct_client", return_value=mock_client):
        with patch("ai.llm_client.AzureOpenAI") as mock_azure:
            text, usage = chat_completion_structured(system="sys", user='{"locale":"tr"}')
            mock_azure.assert_not_called()

    assert '"summary"' in text
    assert usage["total_tokens"] == 33
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["temperature"] == settings.ai_diagnosis_interpret_temperature
    assert kwargs["max_tokens"] == settings.ai_diagnosis_interpret_max_output_tokens


def test_diagnosis_provider_and_model_override(monkeypatch):
    from ai.llm_config import diagnosis_provider_and_model

    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("config.settings.openai_chat_model", "gpt-4o-mini")
    monkeypatch.setattr("config.settings.ai_diagnosis_model", "custom-model")
    provider, model = diagnosis_provider_and_model()
    assert provider == "openai"
    assert model == "custom-model"


def test_de3_diagnosis_provider_rejects_azure_only(monkeypatch):
    from ai.llm_config import diagnosis_openai_available, diagnosis_provider_and_model

    monkeypatch.setattr("config.settings.openai_api_key", "")
    monkeypatch.setattr("config.settings.azure_openai_api_key", "azure-key")
    monkeypatch.setattr("config.settings.azure_openai_endpoint", "https://example.openai.azure.com")
    monkeypatch.setattr("config.settings.azure_openai_deployment_chat", "gpt-deploy")
    assert diagnosis_openai_available() is False
    with pytest.raises(RuntimeError, match="OpenAI"):
        diagnosis_provider_and_model()


def test_chat_completion_structured_rejects_without_openai_key(monkeypatch):
    from ai.llm_client import DiagnosisOpenAiRequiredError, chat_completion_structured

    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "")
    with pytest.raises(DiagnosisOpenAiRequiredError):
        chat_completion_structured(system="s", user="u")


def test_de3_config_defaults_safe():
    assert settings.ai_diagnosis_interpret_enabled is False
    assert settings.ai_diagnosis_interpret_cache_ttl_hours == 48
    assert settings.ai_diagnosis_interpret_max_output_tokens == 450
    assert 0.0 <= settings.ai_diagnosis_interpret_temperature <= 1.0
    assert settings.ai_diagnosis_interpret_estimated_tokens > 0
    assert (settings.ai_provider or "openai").strip().lower() == "openai"


def test_de3_config_model_fallback_empty():
    assert settings.ai_diagnosis_model == "" or isinstance(settings.ai_diagnosis_model, str)


def test_diagnosis_interpretation_validates_json():
    payload = {
        "summary": "Takip gecikmeleri öne çıkıyor.",
        "why_it_matters": "Uzun süre temas olmayan lead'ler dönüşüm kaybedebilir.",
        "key_findings": ["85 lead etkilendi", "8 lead yüksek öncelik"],
        "recommended_actions": [
            {
                "title": "Yüksek öncelikli lead'lere odaklan",
                "reason": "Context'teki impact dağılımına göre",
                "priority": "high",
            }
        ],
        "confidence": "medium",
    }
    parsed = DiagnosisInterpretation.model_validate_json(json.dumps(payload, ensure_ascii=False))
    assert parsed.confidence == "medium"
    assert len(parsed.recommended_actions) == 1


def test_diagnosis_interpretation_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        DiagnosisInterpretation(
            summary="x",
            why_it_matters="y",
            key_findings=[],
            recommended_actions=[],
            confidence="invalid",  # type: ignore[arg-type]
        )


def test_diagnosis_interpretation_rejects_overlong_summary():
    with pytest.raises(ValidationError):
        DiagnosisInterpretation(
            summary="a" * 601,
            why_it_matters="ok",
            key_findings=[],
            recommended_actions=[],
            confidence="low",
        )


def test_diagnosis_interpret_request_period_pattern():
    req = DiagnosisInterpretRequest(diagnosis_id="follow_up_idle_leads", period="monthly")
    assert req.refresh is False
    with pytest.raises(ValidationError):
        DiagnosisInterpretRequest(diagnosis_id="x", period="yearly")


def test_diagnosis_interpret_response_allows_null_interpretation():
    body = DiagnosisInterpretResponse(
        diagnosis_id="follow_up_idle_leads",
        interpretation=None,
        error_code="invalid_llm_output",
        disclaimer="AI yorumu alınamadı.",
    )
    assert body.interpretation is None
    assert body.error_code == "invalid_llm_output"


def _valid_interpretation_json() -> str:
    return json.dumps(
        {
            "summary": "Özet",
            "why_it_matters": "Etki",
            "key_findings": ["Bulgu"],
            "recommended_actions": [
                {"title": "Ara", "reason": "Context", "priority": "high"},
            ],
            "confidence": "medium",
        },
        ensure_ascii=False,
    )


def _compute_payload() -> dict:
    return {
        "generated_at": "2026-08-09T12:00:00+03:00",
        "duration_ms": 1,
        "period_type": "monthly",
        "anchor": "2026-08-01",
        "items": [
            {
                "diagnosis_id": "follow_up_idle_leads",
                "type": "follow_up",
                "severity": "high",
                "title": "Takip",
                "description": "desc",
                "metric": "days_since_last_contact",
                "affected_lead_count": 2,
                "detected_at": "2026-08-09T12:00:00+03:00",
                "affected_leads_available": True,
                "evidence": {"no_contact_count": 1, "idle_contact_count": 1, "oldest_days_idle": 10},
                "impact": {
                    "affected_lead_count": 2,
                    "high_priority_count": 0,
                    "medium_priority_count": 2,
                    "low_priority_count": 0,
                },
                "top_priority_leads": [],
            }
        ],
    }


def test_run_diagnosis_interpret_success(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    db = MagicMock()
    user = MagicMock()
    user.id = 7
    fake_run = MagicMock()
    fake_run.id = 99

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
            with patch(
                "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                return_value=(_valid_interpretation_json(), {"total_tokens": 40, "prompt_tokens": 30, "completion_tokens": 10}),
            ):
                with patch("ai.capabilities.diagnosis_interpreter.create_run", return_value=fake_run):
                    with patch("ai.capabilities.diagnosis_interpreter.finish_run_success") as mock_ok:
                        with patch("ai.capabilities.diagnosis_interpreter.record_usage") as mock_usage:
                            result = run_diagnosis_interpret(
                                db,
                                user=user,
                                org_id=1,
                                diagnosis_id="follow_up_idle_leads",
                            )

    assert result["cached"] is False
    assert result["interpretation"] is not None
    assert result["interpretation"].summary == "Özet"
    assert result["run_id"] == 99
    mock_ok.assert_called_once()
    mock_usage.assert_called_once_with(db, 1, 40)


def test_run_diagnosis_interpret_cache_hit(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    cached_run = MagicMock()
    cached_run.id = 5
    cached_run.output_json = json.dumps(
        {"interpretation": json.loads(_valid_interpretation_json())},
        ensure_ascii=False,
    )

    db = MagicMock()
    user = MagicMock(id=1)

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        with patch(
            "ai.capabilities.diagnosis_interpreter._find_cached_run",
            return_value=cached_run,
        ):
            with patch("ai.capabilities.diagnosis_interpreter.chat_completion_structured") as mock_llm:
                result = run_diagnosis_interpret(
                    db,
                    user=user,
                    org_id=1,
                    diagnosis_id="follow_up_idle_leads",
                    refresh=False,
                )

    mock_llm.assert_not_called()
    assert result["cached"] is True
    assert result["run_id"] == 5


def test_run_diagnosis_interpret_refresh_bypasses_cache(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    db = MagicMock()
    user = MagicMock(id=1)
    fake_run = MagicMock(id=88)

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        with patch(
            "ai.capabilities.diagnosis_interpreter._find_cached_run",
        ) as mock_find:
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch(
                    "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                    return_value=(_valid_interpretation_json(), {"total_tokens": 10}),
                ):
                    with patch("ai.capabilities.diagnosis_interpreter.create_run", return_value=fake_run):
                        with patch("ai.capabilities.diagnosis_interpreter.finish_run_success"):
                            with patch("ai.capabilities.diagnosis_interpreter.record_usage"):
                                run_diagnosis_interpret(
                                    db,
                                    user=user,
                                    org_id=1,
                                    diagnosis_id="follow_up_idle_leads",
                                    refresh=True,
                                )
            mock_find.assert_not_called()


def test_run_diagnosis_interpret_invalid_json_fallback(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    db = MagicMock()
    user = MagicMock(id=1)
    fake_run = MagicMock(id=77)

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        with patch(
            "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
            side_effect=[("not-json", {"total_tokens": 5}), ("still bad", {"total_tokens": 5})],
        ):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch("ai.capabilities.diagnosis_interpreter.create_run", return_value=fake_run):
                    with patch("ai.capabilities.diagnosis_interpreter.finish_run_failed") as mock_fail:
                        with patch("ai.capabilities.diagnosis_interpreter.record_usage"):
                            result = run_diagnosis_interpret(
                                db,
                                user=user,
                                org_id=1,
                                diagnosis_id="follow_up_idle_leads",
                            )

    assert result["interpretation"] is None
    assert result["error_code"] == "invalid_llm_output"
    mock_fail.assert_called_once()


def test_cache_identity_match_all_fields():
    from unittest.mock import MagicMock

    from ai.capabilities.diagnosis_interpreter import _run_matches_cache_identity

    run = MagicMock()
    run.provider = "openai"
    run.model = "gpt-test"
    run.prompt_version = "diagnosis_interpret.md@aaa111"
    inp = {
        "diagnosis_id": "follow_up_idle_leads",
        "context_fingerprint": "abc123",
    }
    assert _run_matches_cache_identity(
        run,
        inp,
        diagnosis_id="follow_up_idle_leads",
        context_fingerprint="abc123",
        provider="openai",
        model="gpt-test",
        prompt_ver="diagnosis_interpret.md@aaa111",
    )


def test_cache_identity_miss_on_prompt_version():
    from unittest.mock import MagicMock

    from ai.capabilities.diagnosis_interpreter import _run_matches_cache_identity

    run = MagicMock()
    run.provider = "openai"
    run.model = "gpt-test"
    run.prompt_version = "diagnosis_interpret.md@old"
    inp = {"diagnosis_id": "x", "context_fingerprint": "fp"}
    assert not _run_matches_cache_identity(
        run,
        inp,
        diagnosis_id="x",
        context_fingerprint="fp",
        provider="openai",
        model="gpt-test",
        prompt_ver="diagnosis_interpret.md@new",
    )


def test_cache_identity_miss_on_model():
    from unittest.mock import MagicMock

    from ai.capabilities.diagnosis_interpreter import _run_matches_cache_identity

    run = MagicMock()
    run.provider = "openai"
    run.model = "model-a"
    run.prompt_version = "pv1"
    inp = {"diagnosis_id": "x", "context_fingerprint": "fp"}
    assert not _run_matches_cache_identity(
        run,
        inp,
        diagnosis_id="x",
        context_fingerprint="fp",
        provider="openai",
        model="model-b",
        prompt_ver="pv1",
    )


def test_cache_identity_miss_on_provider():
    from unittest.mock import MagicMock

    from ai.capabilities.diagnosis_interpreter import _run_matches_cache_identity

    run = MagicMock()
    run.provider = "openai"
    run.model = "m"
    run.prompt_version = "pv1"
    inp = {"diagnosis_id": "x", "context_fingerprint": "fp"}
    assert not _run_matches_cache_identity(
        run,
        inp,
        diagnosis_id="x",
        context_fingerprint="fp",
        provider="other",
        model="m",
        prompt_ver="pv1",
    )


def test_find_cached_run_respects_full_cache_identity(monkeypatch):
    from unittest.mock import MagicMock

    from ai.capabilities.diagnosis_interpreter import _find_cached_run

    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_cache_ttl_hours", 48)

    match = MagicMock()
    match.provider = "openai"
    match.model = "gpt-test"
    match.prompt_version = "pv1"
    match.input_json = json.dumps(
        {"diagnosis_id": "d1", "context_fingerprint": "fp1"},
        ensure_ascii=False,
    )

    wrong_prompt = MagicMock()
    wrong_prompt.provider = "openai"
    wrong_prompt.model = "gpt-test"
    wrong_prompt.prompt_version = "pv-old"
    wrong_prompt.input_json = match.input_json

    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        wrong_prompt,
        match,
    ]

    found = _find_cached_run(
        db,
        1,
        diagnosis_id="d1",
        context_fingerprint="fp1",
        provider="openai",
        model="gpt-test",
        prompt_ver="pv1",
    )
    assert found is match


def test_run_diagnosis_interpret_repair_token_aggregation(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    db = MagicMock()
    user = MagicMock(id=1)
    fake_run = MagicMock(id=42)

    usage1 = {"prompt_tokens": 800, "completion_tokens": 200, "total_tokens": 1000}
    usage2 = {"prompt_tokens": 700, "completion_tokens": 150, "total_tokens": 850}

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        with patch("ai.capabilities.diagnosis_interpreter._find_cached_run", return_value=None):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch(
                    "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                    side_effect=[
                        ("not-json", usage1),
                        (_valid_interpretation_json(), usage2),
                    ],
                ):
                    with patch(
                        "ai.capabilities.diagnosis_interpreter.create_run",
                        return_value=fake_run,
                    ):
                        with patch(
                            "ai.capabilities.diagnosis_interpreter.finish_run_success",
                        ) as mock_ok:
                            with patch(
                                "ai.capabilities.diagnosis_interpreter.record_usage",
                            ) as mock_usage:
                                result = run_diagnosis_interpret(
                                    db,
                                    user=user,
                                    org_id=1,
                                    diagnosis_id="follow_up_idle_leads",
                                )

    assert result["interpretation"] is not None
    mock_ok.assert_called_once()
    kwargs = mock_ok.call_args.kwargs
    assert kwargs["tokens_prompt"] == 1500
    assert kwargs["tokens_completion"] == 350
    assert kwargs["tokens_total"] == 1850
    mock_usage.assert_called_once_with(db, 1, 1850)


def test_run_diagnosis_interpret_invalid_cached_output_soft_miss(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    cached_run = MagicMock()
    cached_run.id = 12
    cached_run.output_json = json.dumps({"interpretation": {"bad": True}})

    db = MagicMock()
    user = MagicMock(id=1)
    fake_run = MagicMock(id=99)

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        with patch(
            "ai.capabilities.diagnosis_interpreter._find_cached_run",
            return_value=cached_run,
        ):
            with patch("ai.capabilities.diagnosis_interpreter.append_run_step") as mock_step:
                with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                    with patch(
                        "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                        return_value=(_valid_interpretation_json(), {"total_tokens": 20}),
                    ):
                        with patch(
                            "ai.capabilities.diagnosis_interpreter.create_run",
                            return_value=fake_run,
                        ):
                            with patch(
                                "ai.capabilities.diagnosis_interpreter.finish_run_success",
                            ):
                                with patch(
                                    "ai.capabilities.diagnosis_interpreter.record_usage",
                                ):
                                    run_diagnosis_interpret(
                                        db,
                                        user=user,
                                        org_id=1,
                                        diagnosis_id="follow_up_idle_leads",
                                    )

    mock_step.assert_called_once()
    step = mock_step.call_args[0][2]
    assert step["reason"] == "invalid_cached_output"
    db.commit.assert_called()


def test_run_diagnosis_interpret_llm_exception(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    db = MagicMock()
    user = MagicMock(id=1)
    fake_run = MagicMock(id=66)

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        with patch(
            "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
            side_effect=TimeoutError("timeout"),
        ):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch("ai.capabilities.diagnosis_interpreter.create_run", return_value=fake_run):
                    with patch("ai.capabilities.diagnosis_interpreter.finish_run_failed"):
                        with pytest.raises(TimeoutError):
                            run_diagnosis_interpret(
                                db,
                                user=user,
                                org_id=1,
                                diagnosis_id="follow_up_idle_leads",
                            )


def test_run_diagnosis_interpret_not_found(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import (
        DiagnosisNotFoundError,
        run_diagnosis_interpret,
    )

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    payload = _compute_payload()
    payload["items"] = []

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=payload,
    ):
        with pytest.raises(DiagnosisNotFoundError):
            run_diagnosis_interpret(
                MagicMock(),
                user=MagicMock(id=1),
                org_id=1,
                diagnosis_id="missing",
            )


def test_run_diagnosis_interpret_feature_disabled(monkeypatch):
    from unittest.mock import MagicMock

    from ai.capabilities.diagnosis_interpreter import (
        DiagnosisInterpretDisabledError,
        run_diagnosis_interpret,
    )

    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", False)
    with pytest.raises(DiagnosisInterpretDisabledError):
        run_diagnosis_interpret(
            MagicMock(),
            user=MagicMock(id=1),
            org_id=1,
            diagnosis_id="follow_up_idle_leads",
        )


def test_run_diagnosis_interpret_quota_exceeded(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret
    from ai.usage import QuotaExceededError

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        with patch(
            "ai.capabilities.diagnosis_interpreter.ensure_quota",
            side_effect=QuotaExceededError("limit"),
        ):
            with pytest.raises(QuotaExceededError):
                run_diagnosis_interpret(
                    MagicMock(),
                    user=MagicMock(id=1),
                    org_id=1,
                    diagnosis_id="follow_up_idle_leads",
                    refresh=True,
                )


# --- API (Stage 7) ---


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app)


def _api_user(role: str = "owner", org_owner_id: int = 10):
    from unittest.mock import MagicMock

    user = MagicMock()
    user.role = role
    user.account_type = "company"
    if role == "owner":
        user.id = org_owner_id
        user.owner_id = None
    else:
        user.id = org_owner_id + 1
        user.owner_id = org_owner_id
    return user


def test_diagnosis_interpret_api_requires_auth(api_client):
    res = api_client.post(
        "/api/ai/diagnosis/interpret",
        json={"diagnosis_id": "follow_up_idle_leads"},
    )
    assert res.status_code == 401


def test_diagnosis_interpret_api_disabled(api_client):
    from unittest.mock import MagicMock

    from auth import verify_token
    from database import get_db
    from main import app

    prev = settings.ai_diagnosis_interpret_enabled
    prev_ai = settings.ai_enabled
    settings.ai_diagnosis_interpret_enabled = False
    settings.ai_enabled = True
    db = MagicMock()

    def _db():
        yield db

    try:
        app.dependency_overrides[verify_token] = lambda: _api_user("owner")
        app.dependency_overrides[get_db] = _db
        res = api_client.post(
            "/api/ai/diagnosis/interpret",
            headers={"Authorization": "Bearer test"},
            json={"diagnosis_id": "follow_up_idle_leads", "period": "monthly"},
        )
        assert res.status_code == 503
    finally:
        settings.ai_diagnosis_interpret_enabled = prev
        settings.ai_enabled = prev_ai
        app.dependency_overrides.clear()


def test_diagnosis_interpret_api_success(api_client):
    from auth import verify_token
    from database import get_db
    from main import app
    from unittest.mock import MagicMock, patch

    prev_flag = settings.ai_diagnosis_interpret_enabled
    prev_ai = settings.ai_enabled
    settings.ai_diagnosis_interpret_enabled = True
    settings.ai_enabled = True
    db = MagicMock()
    interpretation = DiagnosisInterpretation.model_validate_json(_valid_interpretation_json())

    def _db():
        yield db

    payload = {
        "diagnosis_id": "follow_up_idle_leads",
        "interpretation": interpretation,
        "run_id": 99,
        "cached": False,
        "context_fingerprint": "fp1",
        "disclaimer": "AI yorumu — karar vermeden önce teşhis verilerini kontrol edin.",
        "error_code": None,
    }

    try:
        app.dependency_overrides[verify_token] = lambda: _api_user("owner")
        app.dependency_overrides[get_db] = _db
        with patch("ai.router.run_diagnosis_interpret", return_value=payload):
            res = api_client.post(
                "/api/ai/diagnosis/interpret",
                headers={"Authorization": "Bearer test"},
                json={"diagnosis_id": "follow_up_idle_leads", "period": "monthly"},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["diagnosis_id"] == "follow_up_idle_leads"
        assert body["interpretation"]["summary"] == "Özet"
        assert body["run_id"] == 99
    finally:
        settings.ai_diagnosis_interpret_enabled = prev_flag
        settings.ai_enabled = prev_ai
        app.dependency_overrides.clear()


def test_diagnosis_interpret_api_not_found(api_client):
    from auth import verify_token
    from database import get_db
    from main import app
    from ai.capabilities.diagnosis_interpreter import DiagnosisNotFoundError
    from unittest.mock import MagicMock, patch

    prev_flag = settings.ai_diagnosis_interpret_enabled
    prev_ai = settings.ai_enabled
    settings.ai_diagnosis_interpret_enabled = True
    settings.ai_enabled = True
    db = MagicMock()

    def _db():
        yield db

    try:
        app.dependency_overrides[verify_token] = lambda: _api_user("owner")
        app.dependency_overrides[get_db] = _db
        with patch(
            "ai.router.run_diagnosis_interpret",
            side_effect=DiagnosisNotFoundError("missing"),
        ):
            res = api_client.post(
                "/api/ai/diagnosis/interpret",
                headers={"Authorization": "Bearer test"},
                json={"diagnosis_id": "missing", "period": "monthly"},
            )
        assert res.status_code == 404
    finally:
        settings.ai_diagnosis_interpret_enabled = prev_flag
        settings.ai_enabled = prev_ai
        app.dependency_overrides.clear()


def test_ai_status_includes_diagnosis_interpret_available(api_client):
    from unittest.mock import MagicMock, patch

    from auth import verify_token
    from database import get_db
    from main import app

    db = MagicMock()

    def _db():
        yield db

    usage = {
        "month": "2026-08",
        "tokens_used": 0,
        "tokens_quota": 100000,
        "tokens_remaining": 100000,
        "request_count": 0,
    }

    try:
        app.dependency_overrides[verify_token] = lambda: _api_user("owner")
        app.dependency_overrides[get_db] = _db
        with patch("ai.router.usage_summary", return_value=usage):
            res = api_client.get(
                "/api/ai/status",
                headers={"Authorization": "Bearer test"},
            )
        assert res.status_code == 200
        assert "diagnosis_interpret_available" in res.json()
    finally:
        app.dependency_overrides.clear()


def test_diagnosis_interpret_api_quota(api_client):
    from auth import verify_token
    from database import get_db
    from fastapi import HTTPException
    from main import app
    from unittest.mock import MagicMock, patch

    prev_flag = settings.ai_diagnosis_interpret_enabled
    prev_ai = settings.ai_enabled
    settings.ai_diagnosis_interpret_enabled = True
    settings.ai_enabled = True
    db = MagicMock()

    def _db():
        yield db

    try:
        app.dependency_overrides[verify_token] = lambda: _api_user("owner")
        app.dependency_overrides[get_db] = _db
        with patch(
            "ai.router.run_diagnosis_interpret",
            side_effect=HTTPException(status_code=429, detail="Aylık AI token limiti doldu"),
        ):
            res = api_client.post(
                "/api/ai/diagnosis/interpret",
                headers={"Authorization": "Bearer test"},
                json={"diagnosis_id": "follow_up_idle_leads", "period": "monthly"},
            )
        assert res.status_code == 429
    finally:
        settings.ai_diagnosis_interpret_enabled = prev_flag
        settings.ai_enabled = prev_ai
        app.dependency_overrides.clear()


def test_diagnosis_interpret_api_provider_error_502(api_client):
    from auth import verify_token
    from database import get_db
    from main import app
    from unittest.mock import MagicMock, patch

    prev_flag = settings.ai_diagnosis_interpret_enabled
    prev_ai = settings.ai_enabled
    settings.ai_diagnosis_interpret_enabled = True
    settings.ai_enabled = True
    db = MagicMock()

    def _db():
        yield db

    try:
        app.dependency_overrides[verify_token] = lambda: _api_user("owner")
        app.dependency_overrides[get_db] = _db
        with patch(
            "ai.router.run_diagnosis_interpret",
            side_effect=TimeoutError("timeout"),
        ):
            res = api_client.post(
                "/api/ai/diagnosis/interpret",
                headers={"Authorization": "Bearer test"},
                json={"diagnosis_id": "follow_up_idle_leads", "period": "monthly"},
            )
        assert res.status_code == 502
    finally:
        settings.ai_diagnosis_interpret_enabled = prev_flag
        settings.ai_enabled = prev_ai
        app.dependency_overrides.clear()


def test_diagnosis_interpret_api_invalid_llm_output_200(api_client):
    from auth import verify_token
    from database import get_db
    from main import app
    from unittest.mock import MagicMock, patch

    prev_flag = settings.ai_diagnosis_interpret_enabled
    prev_ai = settings.ai_enabled
    settings.ai_diagnosis_interpret_enabled = True
    settings.ai_enabled = True
    db = MagicMock()

    def _db():
        yield db

    payload = {
        "diagnosis_id": "follow_up_idle_leads",
        "interpretation": None,
        "run_id": 55,
        "cached": False,
        "context_fingerprint": "fp",
        "disclaimer": "AI yorumu",
        "error_code": "invalid_llm_output",
    }

    try:
        app.dependency_overrides[verify_token] = lambda: _api_user("owner")
        app.dependency_overrides[get_db] = _db
        with patch("ai.router.run_diagnosis_interpret", return_value=payload):
            res = api_client.post(
                "/api/ai/diagnosis/interpret",
                headers={"Authorization": "Bearer test"},
                json={"diagnosis_id": "follow_up_idle_leads", "period": "monthly"},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["interpretation"] is None
        assert body["error_code"] == "invalid_llm_output"
    finally:
        settings.ai_diagnosis_interpret_enabled = prev_flag
        settings.ai_enabled = prev_ai
        app.dependency_overrides.clear()


def test_diagnosis_interpret_api_cached_response(api_client):
    from auth import verify_token
    from database import get_db
    from main import app
    from unittest.mock import MagicMock, patch

    prev_flag = settings.ai_diagnosis_interpret_enabled
    prev_ai = settings.ai_enabled
    settings.ai_diagnosis_interpret_enabled = True
    settings.ai_enabled = True
    db = MagicMock()
    interpretation = DiagnosisInterpretation.model_validate_json(_valid_interpretation_json())

    def _db():
        yield db

    payload = {
        "diagnosis_id": "follow_up_idle_leads",
        "interpretation": interpretation,
        "run_id": 3,
        "cached": True,
        "context_fingerprint": "fp-cache",
        "disclaimer": "AI yorumu",
        "error_code": None,
    }

    try:
        app.dependency_overrides[verify_token] = lambda: _api_user("owner")
        app.dependency_overrides[get_db] = _db
        with patch("ai.router.run_diagnosis_interpret", return_value=payload):
            res = api_client.post(
                "/api/ai/diagnosis/interpret",
                headers={"Authorization": "Bearer test"},
                json={"diagnosis_id": "follow_up_idle_leads", "period": "monthly"},
            )
        assert res.status_code == 200
        assert res.json()["cached"] is True
    finally:
        settings.ai_diagnosis_interpret_enabled = prev_flag
        settings.ai_enabled = prev_ai
        app.dependency_overrides.clear()


def test_run_diagnosis_interpret_forwards_org_id_to_compute_diagnoses(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    db = MagicMock()
    user = MagicMock(id=5)

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ) as mock_compute:
        with patch("ai.capabilities.diagnosis_interpreter._find_cached_run", return_value=None):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota"):
                with patch(
                    "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                    return_value=(_valid_interpretation_json(), {"total_tokens": 1}),
                ):
                    with patch("ai.capabilities.diagnosis_interpreter.create_run", return_value=MagicMock(id=1)):
                        with patch("ai.capabilities.diagnosis_interpreter.finish_run_success"):
                            with patch("ai.capabilities.diagnosis_interpreter.record_usage"):
                                run_diagnosis_interpret(
                                    db,
                                    user=user,
                                    org_id=77,
                                    diagnosis_id="follow_up_idle_leads",
                                )
    mock_compute.assert_called_once()
    assert mock_compute.call_args[0][1] == 77


def test_run_diagnosis_interpret_quota_blocks_before_llm_and_run(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret
    from ai.usage import QuotaExceededError

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        with patch("ai.capabilities.diagnosis_interpreter._find_cached_run", return_value=None):
            with patch(
                "ai.capabilities.diagnosis_interpreter.ensure_quota",
                side_effect=QuotaExceededError("limit"),
            ):
                with patch("ai.capabilities.diagnosis_interpreter.create_run") as mock_create:
                    with patch(
                        "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                    ) as mock_llm:
                        with pytest.raises(QuotaExceededError):
                            run_diagnosis_interpret(
                                MagicMock(),
                                user=MagicMock(id=1),
                                org_id=1,
                                diagnosis_id="follow_up_idle_leads",
                            )
                        mock_create.assert_not_called()
                        mock_llm.assert_not_called()


def test_run_diagnosis_interpret_feature_disabled_no_openai(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import (
        DiagnosisInterpretDisabledError,
        run_diagnosis_interpret,
    )

    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", False)
    with patch("ai.capabilities.diagnosis_interpreter.chat_completion_structured") as mock_llm:
        with pytest.raises(DiagnosisInterpretDisabledError):
            run_diagnosis_interpret(
                MagicMock(),
                user=MagicMock(id=1),
                org_id=1,
                diagnosis_id="follow_up_idle_leads",
            )
        mock_llm.assert_not_called()


def test_run_diagnosis_interpret_cache_hit_skips_llm_and_usage(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ai.capabilities.diagnosis_interpreter import run_diagnosis_interpret

    monkeypatch.setattr("config.settings.diagnosis_engine_enabled", True)
    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_enabled", True)
    monkeypatch.setattr("config.settings.ai_enabled", True)
    monkeypatch.setattr("config.settings.openai_api_key", "sk-test")

    cached_run = MagicMock()
    cached_run.id = 9
    cached_run.output_json = json.dumps(
        {"interpretation": json.loads(_valid_interpretation_json())},
        ensure_ascii=False,
    )

    with patch(
        "ai.capabilities.diagnosis_interpreter.compute_diagnoses",
        return_value=_compute_payload(),
    ):
        with patch(
            "ai.capabilities.diagnosis_interpreter._find_cached_run",
            return_value=cached_run,
        ):
            with patch("ai.capabilities.diagnosis_interpreter.ensure_quota") as mock_quota:
                with patch(
                    "ai.capabilities.diagnosis_interpreter.chat_completion_structured",
                ) as mock_llm:
                    with patch("ai.capabilities.diagnosis_interpreter.create_run") as mock_create:
                        with patch("ai.capabilities.diagnosis_interpreter.record_usage") as mock_usage:
                            result = run_diagnosis_interpret(
                                MagicMock(),
                                user=MagicMock(id=1),
                                org_id=1,
                                diagnosis_id="follow_up_idle_leads",
                            )
    assert result["cached"] is True
    mock_quota.assert_not_called()
    mock_llm.assert_not_called()
    mock_create.assert_not_called()
    mock_usage.assert_not_called()


def test_find_cached_run_applies_org_id_filter(monkeypatch):
    from unittest.mock import MagicMock

    from ai.capabilities.diagnosis_interpreter import _find_cached_run
    from database import AiRun

    monkeypatch.setattr("config.settings.ai_diagnosis_interpret_cache_ttl_hours", 48)

    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    _find_cached_run(
        db,
        55,
        diagnosis_id="d1",
        context_fingerprint="fp",
        provider="openai",
        model="m",
        prompt_ver="pv",
    )

    db.query.assert_called_once_with(AiRun)
    assert db.query.return_value.filter.called


def test_diagnosis_interpret_api_org_isolation(api_client):
    from auth import verify_token
    from database import get_db
    from main import app
    from unittest.mock import MagicMock, patch

    prev_flag = settings.ai_diagnosis_interpret_enabled
    prev_ai = settings.ai_enabled
    settings.ai_diagnosis_interpret_enabled = True
    settings.ai_enabled = True
    db = MagicMock()
    seen_orgs: list[int] = []

    def _db():
        yield db

    def _capture_run(db_arg, *, user, org_id, **kwargs):
        seen_orgs.append(org_id)
        from ai.capabilities.diagnosis_interpreter import DiagnosisNotFoundError

        raise DiagnosisNotFoundError("missing")

    try:
        with patch("ai.router.run_diagnosis_interpret", side_effect=_capture_run):
            app.dependency_overrides[get_db] = _db

            app.dependency_overrides[verify_token] = lambda: _api_user("owner", org_owner_id=10)
            api_client.post(
                "/api/ai/diagnosis/interpret",
                headers={"Authorization": "Bearer test"},
                json={"diagnosis_id": "follow_up_idle_leads", "period": "monthly"},
            )

            app.dependency_overrides[verify_token] = lambda: _api_user("owner", org_owner_id=20)
            api_client.post(
                "/api/ai/diagnosis/interpret",
                headers={"Authorization": "Bearer test"},
                json={"diagnosis_id": "follow_up_idle_leads", "period": "monthly"},
            )

        assert seen_orgs == [10, 20]
    finally:
        settings.ai_diagnosis_interpret_enabled = prev_flag
        settings.ai_enabled = prev_ai
        app.dependency_overrides.clear()


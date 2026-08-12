"""DE-5.1-C — historical diagnosis interpretation (read-only, no DE-4 bridge)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ai.capabilities.diagnosis_history_interpret_parse import try_parse_history_interpretation
from ai.context.diagnosis_history_context import (
    build_diagnosis_history_interpret_context,
    compute_history_context_fingerprint,
    compute_trend_fingerprint,
)
from ai.llm_client import (
    DiagnosisOpenAiRequiredError,
    assert_diagnosis_openai_configured,
    chat_completion_structured,
)
from ai.llm_config import diagnosis_openai_available, diagnosis_provider_and_model
from ai.prompts.diagnosis_history_interpret import prompt_version, system_prompt
from ai.store import append_run_step, create_run, finish_run_failed, finish_run_success
from ai.usage import ensure_quota, record_usage
from config import settings
from database import AiRun, User
from intelligence.diagnosis.history_api import (
    get_case_for_org,
    list_all_case_snapshots,
    resolve_history_period_key,
)
from intelligence.diagnosis.trend_api import (
    _snapshot_row_to_trend_input,
    build_history_trend,
)
from schemas import DiagnosisHistoryInterpretation

RUN_TYPE = "diagnosis_history_interpret"
DISCLAIMER = (
    "Bu yorum teşhisin geçmiş verilerine dayanır. "
    "Teşhis durumunu veya aksiyonları değiştirmez."
)


class DiagnosisHistoryNotFoundError(LookupError):
    pass


class DiagnosisHistoryPeriodError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class DiagnosisHistoryInterpretDisabledError(RuntimeError):
    pass


def _merge_usage_totals(accum: dict, usage: dict) -> dict:
    out = {
        "prompt_tokens": int(accum.get("prompt_tokens") or 0),
        "completion_tokens": int(accum.get("completion_tokens") or 0),
        "total_tokens": int(accum.get("total_tokens") or 0),
    }
    out["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
    out["completion_tokens"] += int(usage.get("completion_tokens") or 0)
    out["total_tokens"] += int(usage.get("total_tokens") or 0)
    if out["total_tokens"] == 0 and (out["prompt_tokens"] or out["completion_tokens"]):
        out["total_tokens"] = out["prompt_tokens"] + out["completion_tokens"]
    return out


def _run_matches_cache(
    run: AiRun,
    inp: dict,
    *,
    diagnosis_id: str,
    period_key: str,
    latest_snapshot_id: int | None,
    trend_fingerprint: str,
    context_fingerprint: str,
    provider: str,
    model: str,
    prompt_ver: str,
) -> bool:
    if inp.get("diagnosis_id") != diagnosis_id:
        return False
    if inp.get("period_key") != period_key:
        return False
    if inp.get("latest_snapshot_id") != latest_snapshot_id:
        return False
    if inp.get("trend_fingerprint") != trend_fingerprint:
        return False
    if inp.get("context_fingerprint") != context_fingerprint:
        return False
    if (run.provider or "") != provider:
        return False
    if (run.model or "") != model:
        return False
    if (run.prompt_version or "") != prompt_ver:
        return False
    return True


def _find_cached_run(
    db: Session,
    org_id: int,
    *,
    diagnosis_id: str,
    period_key: str,
    latest_snapshot_id: int | None,
    trend_fingerprint: str,
    context_fingerprint: str,
    provider: str,
    model: str,
    prompt_ver: str,
) -> AiRun | None:
    ttl_hours = max(1, settings.ai_diagnosis_history_interpret_cache_ttl_hours)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=ttl_hours)
    rows = (
        db.query(AiRun)
        .filter(
            AiRun.user_id == org_id,
            AiRun.run_type == RUN_TYPE,
            AiRun.status == "success",
            AiRun.created_at >= cutoff,
        )
        .order_by(AiRun.created_at.desc())
        .limit(40)
        .all()
    )
    for run in rows:
        try:
            inp = json.loads(run.input_json or "{}")
        except json.JSONDecodeError:
            continue
        if _run_matches_cache(
            run,
            inp,
            diagnosis_id=diagnosis_id,
            period_key=period_key,
            latest_snapshot_id=latest_snapshot_id,
            trend_fingerprint=trend_fingerprint,
            context_fingerprint=context_fingerprint,
            provider=provider,
            model=model,
            prompt_ver=prompt_ver,
        ):
            return run
    return None


def _interpretation_from_run(run: AiRun) -> DiagnosisHistoryInterpretation | None:
    try:
        out = json.loads(run.output_json or "{}")
    except json.JSONDecodeError:
        return None
    raw = out.get("interpretation")
    if not raw:
        return None
    try:
        if isinstance(raw, dict):
            return DiagnosisHistoryInterpretation.model_validate(raw)
        return DiagnosisHistoryInterpretation.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError, ValueError):
        return None


def _public_trend_for_response(trend: dict) -> dict:
    return {
        "direction": trend.get("direction"),
        "reason_codes": list(trend.get("reason_codes") or []),
        "substantive_count": trend.get("substantive_count"),
        "metrics": {
            "reopen_count": (trend.get("metrics") or {}).get("reopen_count"),
            "active_duration_seconds": (trend.get("metrics") or {}).get(
                "active_duration_seconds"
            ),
            "last_substantive_change_at": (trend.get("metrics") or {}).get(
                "last_substantive_change_at"
            ),
            "worst_point": (trend.get("metrics") or {}).get("worst_point"),
        },
    }


def run_diagnosis_history_interpret(
    db: Session,
    *,
    user: User,
    org_id: int,
    diagnosis_id: str,
    period_key: str | None = None,
    locale: str = "tr",
    refresh: bool = False,
) -> dict:
    if not settings.diagnosis_engine_enabled:
        raise DiagnosisHistoryInterpretDisabledError("Diagnosis Engine etkin değil")
    if not settings.ai_diagnosis_history_interpret_enabled:
        raise DiagnosisHistoryInterpretDisabledError("Teşhis geçmişi AI yorumu etkin değil")
    if not settings.ai_enabled:
        raise DiagnosisHistoryInterpretDisabledError("AI özelliği kapalı")
    if not diagnosis_openai_available():
        raise DiagnosisOpenAiRequiredError(
            "Teşhis geçmişi yorumu için OpenAI gerekli (OPENAI_API_KEY)."
        )
    assert_diagnosis_openai_configured()

    did = (diagnosis_id or "").strip()
    if not did:
        raise DiagnosisHistoryNotFoundError(diagnosis_id)

    resolved = resolve_history_period_key(
        db,
        organization_id=org_id,
        diagnosis_id=did,
        period_key=period_key,
    )
    if resolved.status == "invalid":
        raise DiagnosisHistoryPeriodError("invalid_period_key")
    if resolved.status == "ambiguous":
        raise DiagnosisHistoryPeriodError("ambiguous_period_key")
    assert resolved.period_key is not None
    pk = resolved.period_key

    case = get_case_for_org(
        db,
        organization_id=org_id,
        diagnosis_id=did,
        period_key=pk,
    )
    if not case:
        raise DiagnosisHistoryNotFoundError(did)

    all_rows = list_all_case_snapshots(
        db, case_id=case.id, organization_id=org_id
    )
    trend = build_history_trend(case, all_rows)
    snap_inputs = [_snapshot_row_to_trend_input(s) for s in all_rows]

    context = build_diagnosis_history_interpret_context(
        locale=locale,
        diagnosis_id=case.diagnosis_id,
        diagnosis_type=case.diagnosis_type,
        period_key=pk,
        case_state=case.state,
        title=case.title,
        severity=case.severity,
        metric=case.metric,
        current_value=case.current_value,
        affected_lead_count=case.affected_lead_count,
        trend=trend,
        snapshots=snap_inputs,
    )
    context_fp = compute_history_context_fingerprint(context)
    trend_fp = compute_trend_fingerprint(trend)
    latest_snapshot_id = case.latest_snapshot_id
    provider, model = diagnosis_provider_and_model()
    prompt_ver = prompt_version()

    def _success_payload(
        interpretation: DiagnosisHistoryInterpretation | None,
        *,
        run_id: int | None,
        cached: bool,
        error_code: str | None = None,
        generated_at: str | None = None,
    ) -> dict:
        return {
            "diagnosis_id": did,
            "period_key": pk,
            "interpretation": interpretation,
            "trend_direction": str(trend.get("direction") or "stable"),
            "trend": _public_trend_for_response(trend),
            "run_id": run_id,
            "cached": cached,
            "generated_at": generated_at,
            "context_fingerprint": context_fp,
            "disclaimer": DISCLAIMER,
            "error_code": error_code,
        }

    if not refresh:
        cached_run = _find_cached_run(
            db,
            org_id,
            diagnosis_id=did,
            period_key=pk,
            latest_snapshot_id=latest_snapshot_id,
            trend_fingerprint=trend_fp,
            context_fingerprint=context_fp,
            provider=provider,
            model=model,
            prompt_ver=prompt_ver,
        )
        if cached_run:
            parsed = _interpretation_from_run(cached_run)
            if parsed:
                # No proposal bridge — ever.
                return _success_payload(
                    parsed,
                    run_id=cached_run.id,
                    cached=True,
                    generated_at=cached_run.created_at.isoformat()
                    if cached_run.created_at
                    else None,
                )
            append_run_step(
                db,
                cached_run,
                {"event": "cache_skip", "reason": "invalid_cached_output"},
            )
            db.commit()

    ensure_quota(
        db, org_id, estimated_tokens=settings.ai_diagnosis_history_interpret_estimated_tokens
    )

    run = create_run(
        db,
        org_id=org_id,
        requested_by=user.id,
        run_type=RUN_TYPE,
        input_data={
            "diagnosis_id": did,
            "period_key": pk,
            "locale": locale,
            "latest_snapshot_id": latest_snapshot_id,
            "trend_fingerprint": trend_fp,
            "context_fingerprint": context_fp,
            "prompt_version": prompt_ver,
            "provider": provider,
            "model": model,
        },
        provider=provider,
        model=model,
        prompt_version=prompt_ver,
    )

    system = system_prompt()
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    user_msg = (
        f"Dil/locale: {locale}\n\n"
        "Teşhis geçmişi context (JSON). Trend backend tarafından hesaplandı; "
        "yeniden hesaplama.\n"
        f"{context_json}"
    )

    started = time.perf_counter()
    interpretation: DiagnosisHistoryInterpretation | None = None
    error_code: str | None = None
    usage_agg: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    try:
        raw, usage = chat_completion_structured(system=system, user=user_msg)
        usage_agg = _merge_usage_totals(usage_agg, usage)
        append_run_step(
            db,
            run,
            {
                "event": "llm_attempt",
                "attempt": 1,
                "provider": provider,
                "model": model,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        )
        interpretation, failure_meta = try_parse_history_interpretation(raw)
        if interpretation is not None:
            append_run_step(db, run, {"event": "parse_success", "attempt": 1})
        else:
            append_run_step(
                db,
                run,
                {
                    "event": "parse_failed",
                    "attempt": 1,
                    "reason": (failure_meta or {}).get("reason"),
                    "validation_path": (failure_meta or {}).get("validation_path"),
                },
            )
            append_run_step(db, run, {"event": "repair_attempt", "attempt": 2})
            repair_user = (
                "Önceki geçersiz JSON çıktı:\n"
                f"{raw[:2000]}\n\n"
                "Yalnızca geçerli JSON nesnesi döndür (recommended_actions yok). Context aynı:\n"
                f"{context_json}"
            )
            raw2, usage2 = chat_completion_structured(system=system, user=repair_user)
            usage_agg = _merge_usage_totals(usage_agg, usage2)
            append_run_step(
                db,
                run,
                {
                    "event": "llm_attempt",
                    "attempt": 2,
                    "provider": provider,
                    "model": model,
                    "prompt_tokens": usage2.get("prompt_tokens"),
                    "completion_tokens": usage2.get("completion_tokens"),
                    "total_tokens": usage2.get("total_tokens"),
                },
            )
            interpretation, failure_meta2 = try_parse_history_interpretation(raw2)
            if interpretation is not None:
                append_run_step(db, run, {"event": "parse_success", "attempt": 2})
            else:
                append_run_step(
                    db,
                    run,
                    {
                        "event": "parse_failed",
                        "attempt": 2,
                        "reason": (failure_meta2 or {}).get("reason"),
                        "validation_path": (failure_meta2 or {}).get("validation_path"),
                    },
                )
                error_code = "invalid_llm_output"
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_failed(
            db,
            run,
            error_code="provider",
            duration_ms=duration_ms,
            tokens_prompt=int(usage_agg.get("prompt_tokens") or 0) or None,
            tokens_completion=int(usage_agg.get("completion_tokens") or 0) or None,
            tokens_total=int(usage_agg.get("total_tokens") or 0) or None,
        )
        db.commit()
        raise

    duration_ms = int((time.perf_counter() - started) * 1000)
    tokens_total = int(usage_agg.get("total_tokens") or 0)

    if interpretation is None:
        finish_run_failed(
            db,
            run,
            error_code=error_code or "invalid_llm_output",
            duration_ms=duration_ms,
            output_data={"interpretation": None},
            tokens_prompt=int(usage_agg.get("prompt_tokens") or 0) or None,
            tokens_completion=int(usage_agg.get("completion_tokens") or 0) or None,
            tokens_total=tokens_total or None,
        )
        record_usage(db, org_id, tokens_total)
        db.commit()
        return _success_payload(
            None,
            run_id=run.id,
            cached=False,
            error_code=error_code,
            generated_at=run.created_at.isoformat() if run.created_at else None,
        )

    finish_run_success(
        db,
        run,
        output_data={"interpretation": interpretation.model_dump()},
        tokens_prompt=usage_agg.get("prompt_tokens"),
        tokens_completion=usage_agg.get("completion_tokens"),
        tokens_total=tokens_total,
        duration_ms=duration_ms,
    )
    record_usage(db, org_id, tokens_total)
    db.commit()
    db.refresh(run)

    # Explicit: never call proposal bridge / create AiAction.
    return _success_payload(
        interpretation,
        run_id=run.id,
        cached=False,
        generated_at=run.created_at.isoformat() if run.created_at else None,
    )

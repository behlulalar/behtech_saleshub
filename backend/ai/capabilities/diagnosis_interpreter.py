"""DE-3 — interpret deterministic diagnosis via OpenAI (read-only)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ai.context.diagnosis_context import (
    build_diagnosis_interpret_context,
    compute_context_fingerprint,
)
from ai.llm_client import (
    DiagnosisOpenAiRequiredError,
    assert_diagnosis_openai_configured,
    chat_completion_structured,
)
from ai.llm_config import diagnosis_openai_available, diagnosis_provider_and_model
from ai.prompts.diagnosis_interpret import prompt_version, system_prompt
from ai.store import append_run_step, create_run, finish_run_failed, finish_run_success
from ai.usage import QuotaExceededError, ensure_quota, record_usage
from app_timezone import local_today
from config import settings
from database import AiRun, User
from intelligence.diagnosis.engine import compute_diagnoses
from reports import parse_report_anchor
from schemas import DiagnosisInterpretation
from ai.capabilities.diagnosis_interpret_parse import try_parse_interpretation
from ai.actions.proposal_bridge import (
    bridge_recommended_actions_to_proposals,
    primary_lead_id_from_diagnosis_item,
)

RUN_TYPE = "diagnosis_interpret"
DISCLAIMER = "AI yorumu — karar vermeden önce teşhis verilerini kontrol edin."


class DiagnosisNotFoundError(LookupError):
    pass


class DiagnosisInterpretDisabledError(RuntimeError):
    pass


def _resolve_anchor(period_type: str, date_param: str | None):
    if period_type == "monthly" and date_param and len(date_param) >= 7:
        return parse_report_anchor("monthly", None, date_param[:7])
    if date_param:
        return parse_report_anchor(period_type, date_param, None)
    return None


def _merge_usage_totals(accum: dict, usage: dict) -> dict:
    """Sum prompt/completion/total tokens across multiple LLM calls."""
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


def _run_matches_cache_identity(
    run: AiRun,
    inp: dict,
    *,
    diagnosis_id: str,
    context_fingerprint: str,
    provider: str,
    model: str,
    prompt_ver: str,
) -> bool:
    if inp.get("diagnosis_id") != diagnosis_id:
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
    context_fingerprint: str,
    provider: str,
    model: str,
    prompt_ver: str,
) -> AiRun | None:
    ttl_hours = max(1, settings.ai_diagnosis_interpret_cache_ttl_hours)
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
        if not _run_matches_cache_identity(
            run,
            inp,
            diagnosis_id=diagnosis_id,
            context_fingerprint=context_fingerprint,
            provider=provider,
            model=model,
            prompt_ver=prompt_ver,
        ):
            continue
        return run
    return None


def _interpretation_from_run(run: AiRun) -> DiagnosisInterpretation | None:
    try:
        out = json.loads(run.output_json or "{}")
    except json.JSONDecodeError:
        return None
    raw = out.get("interpretation")
    if not raw:
        return None
    try:
        if isinstance(raw, dict):
            return DiagnosisInterpretation.model_validate(raw)
        return DiagnosisInterpretation.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError, ValueError):
        return None


def _append_llm_attempt_step(
    db: Session,
    run: AiRun,
    *,
    attempt: int,
    provider: str,
    model: str,
    usage: dict,
) -> None:
    append_run_step(
        db,
        run,
        {
            "event": "llm_attempt",
            "attempt": attempt,
            "provider": provider,
            "model": model,
            "finish_reason": usage.get("finish_reason"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
    )


def _append_parse_failed_step(
    db: Session,
    run: AiRun,
    *,
    attempt: int,
    failure_meta: dict | None,
) -> None:
    meta = failure_meta or {"reason": "unknown", "validation_path": None}
    append_run_step(
        db,
        run,
        {
            "event": "parse_failed",
            "attempt": attempt,
            "reason": meta.get("reason") or "unknown",
            "validation_path": meta.get("validation_path"),
        },
    )


def _call_llm(system: str, user: str) -> tuple[str, dict]:
    return chat_completion_structured(system=system, user=user)


def _run_proposal_bridge(
    db: Session,
    *,
    user: User,
    org_id: int,
    diagnosis_id: str,
    interpret_run_id: int,
    interpretation: DiagnosisInterpretation,
    diagnosis_item: dict,
) -> dict | None:
    if not settings.ai_de4_interpret_proposal_bridge_enabled:
        return None
    if not interpretation.recommended_actions:
        return None
    role = getattr(user, "role", None) or "owner"
    primary_lead = primary_lead_id_from_diagnosis_item(diagnosis_item)
    try:
        summary = bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=org_id,
            role=role,
            diagnosis_id=diagnosis_id,
            interpret_run_id=interpret_run_id,
            recommended_actions=interpretation.recommended_actions,
            primary_lead_id=primary_lead,
        )
        return summary.to_dict()
    except Exception:
        db.rollback()
        return {
            "recommendation_count": len(interpretation.recommended_actions),
            "mapped_count": 0,
            "no_action_count": 0,
            "proposed_count": 0,
            "skipped_count": len(interpretation.recommended_actions),
            "created_count": 0,
            "action_ids": [],
            "items": [],
            "bridge_error": True,
        }


def run_diagnosis_interpret(
    db: Session,
    *,
    user: User,
    org_id: int,
    diagnosis_id: str,
    period: str = "monthly",
    date_param: str | None = None,
    locale: str = "tr",
    refresh: bool = False,
) -> dict:
    if not settings.diagnosis_engine_enabled:
        raise DiagnosisInterpretDisabledError("Diagnosis Engine etkin değil")
    if not settings.ai_diagnosis_interpret_enabled:
        raise DiagnosisInterpretDisabledError("Teşhis AI yorumu etkin değil")
    if not settings.ai_enabled:
        raise DiagnosisInterpretDisabledError("AI özelliği kapalı")
    if not diagnosis_openai_available():
        raise DiagnosisOpenAiRequiredError(
            "Teşhis yorumu için OpenAI gerekli (OPENAI_API_KEY). Azure bu özellikte kullanılmaz."
        )
    assert_diagnosis_openai_configured()

    anchor = _resolve_anchor(period, date_param) or local_today()
    data = compute_diagnoses(db, org_id, period_type=period, anchor=anchor)
    item = next((row for row in data["items"] if row.get("diagnosis_id") == diagnosis_id), None)
    if not item:
        raise DiagnosisNotFoundError(diagnosis_id)

    context = build_diagnosis_interpret_context(
        item,
        locale=locale,
        period_type=data["period_type"],
        anchor=data["anchor"],
    )
    fingerprint = compute_context_fingerprint(context)
    provider, model = diagnosis_provider_and_model()
    prompt_ver = prompt_version()

    if not refresh:
        cached_run = _find_cached_run(
            db,
            org_id,
            diagnosis_id=diagnosis_id,
            context_fingerprint=fingerprint,
            provider=provider,
            model=model,
            prompt_ver=prompt_ver,
        )
        if cached_run:
            parsed = _interpretation_from_run(cached_run)
            if parsed:
                bridge = _run_proposal_bridge(
                    db,
                    user=user,
                    org_id=org_id,
                    diagnosis_id=diagnosis_id,
                    interpret_run_id=cached_run.id,
                    interpretation=parsed,
                    diagnosis_item=item,
                )
                if bridge is not None:
                    db.commit()
                return {
                    "diagnosis_id": diagnosis_id,
                    "interpretation": parsed,
                    "run_id": cached_run.id,
                    "cached": True,
                    "context_fingerprint": fingerprint,
                    "disclaimer": DISCLAIMER,
                    "error_code": None,
                    "proposal_bridge": bridge,
                }
            append_run_step(
                db,
                cached_run,
                {"event": "cache_skip", "reason": "invalid_cached_output"},
            )
            db.commit()

    ensure_quota(db, org_id, estimated_tokens=settings.ai_diagnosis_interpret_estimated_tokens)

    run = create_run(
        db,
        org_id=org_id,
        requested_by=user.id,
        run_type=RUN_TYPE,
        input_data={
            "diagnosis_id": diagnosis_id,
            "period": period,
            "date": date_param,
            "locale": locale,
            "context_fingerprint": fingerprint,
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
    user_msg = f"Dil/locale: {locale}\n\nTeşhis context (JSON):\n{context_json}"

    started = time.perf_counter()
    interpretation: DiagnosisInterpretation | None = None
    error_code: str | None = None
    usage_agg: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    try:
        raw, usage = _call_llm(system, user_msg)
        usage_agg = _merge_usage_totals(usage_agg, usage)
        _append_llm_attempt_step(
            db, run, attempt=1, provider=provider, model=model, usage=usage
        )
        interpretation, failure_meta = try_parse_interpretation(raw)
        if interpretation is not None:
            append_run_step(db, run, {"event": "parse_success", "attempt": 1})
        else:
            _append_parse_failed_step(db, run, attempt=1, failure_meta=failure_meta)
            append_run_step(db, run, {"event": "repair_attempt", "attempt": 2})
            repair_user = (
                "Önceki geçersiz JSON çıktı:\n"
                f"{raw[:2000]}\n\n"
                "Yalnızca geçerli JSON nesnesi döndür. Context aynı:\n"
                f"{context_json}"
            )
            raw2, usage2 = _call_llm(system, repair_user)
            usage_agg = _merge_usage_totals(usage_agg, usage2)
            _append_llm_attempt_step(
                db, run, attempt=2, provider=provider, model=model, usage=usage2
            )
            interpretation, failure_meta2 = try_parse_interpretation(raw2)
            if interpretation is not None:
                append_run_step(db, run, {"event": "parse_success", "attempt": 2})
            else:
                _append_parse_failed_step(db, run, attempt=2, failure_meta=failure_meta2)
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
        return {
            "diagnosis_id": diagnosis_id,
            "interpretation": None,
            "run_id": run.id,
            "cached": False,
            "context_fingerprint": fingerprint,
            "disclaimer": DISCLAIMER,
            "error_code": error_code,
        }

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

    bridge = None
    if interpretation is not None:
        bridge = _run_proposal_bridge(
            db,
            user=user,
            org_id=org_id,
            diagnosis_id=diagnosis_id,
            interpret_run_id=run.id,
            interpretation=interpretation,
            diagnosis_item=item,
        )
        if bridge is not None:
            db.commit()

    return {
        "diagnosis_id": diagnosis_id,
        "interpretation": interpretation,
        "run_id": run.id,
        "cached": False,
        "context_fingerprint": fingerprint,
        "disclaimer": DISCLAIMER,
        "error_code": None,
        "proposal_bridge": bridge,
    }

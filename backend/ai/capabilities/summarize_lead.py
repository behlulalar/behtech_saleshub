import hashlib
import json
import time
from pathlib import Path

from sqlalchemy.orm import Session

from database import User
from ai.llm_client import chat_completion, assert_llm_configured
from ai.llm_config import provider_and_model
from ai.snapshots.lead_snapshot import build_lead_snapshot
from ai.store import create_run, finish_run_failed, finish_run_success
from ai.usage import ensure_quota, record_usage
from intelligence.insights import insight_to_dict, lead_insights_deterministic, persist_insights

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "summarize_lead.md"


def _prompt_version() -> str:
    raw = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.is_file() else ""
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"summarize_lead.md@{digest}"


def _system_prompt() -> str:
    if PROMPT_PATH.is_file():
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "Lead özeti yaz."


def run_summarize_lead(
    db: Session,
    *,
    user: User,
    org_id: int,
    lead_id: int,
    locale: str = "tr",
) -> tuple[str, list[dict], int]:
    assert_llm_configured()
    ensure_quota(db, org_id)

    snapshot = build_lead_snapshot(db, org_id, lead_id)
    det_items = lead_insights_deterministic(db, org_id, lead_id)
    saved = persist_insights(
        db,
        org_id,
        entity_type="lead",
        entity_id=lead_id,
        items=det_items,
        source="deterministic",
    )
    insight_payload = [insight_to_dict(row) for row in saved]

    user_prompt = (
        f"Dil: {locale}\n"
        f"Lead snapshot:\n{json.dumps(snapshot, ensure_ascii=False, indent=2)}\n\n"
        f"Insights:\n{json.dumps(insight_payload, ensure_ascii=False, indent=2)}\n\n"
        "Bu lead için özet yaz."
    )

    llm_provider, llm_model = provider_and_model()
    run = create_run(
        db,
        org_id=org_id,
        requested_by=user.id,
        run_type="summarize_lead",
        input_data={"lead_id": lead_id, "locale": locale},
        provider=llm_provider,
        model=llm_model,
        prompt_version=_prompt_version(),
    )

    started = time.perf_counter()
    try:
        text, usage = chat_completion(system=_system_prompt(), user=user_prompt)
    except Exception:
        finish_run_failed(db, run, error_code="provider", duration_ms=int((time.perf_counter() - started) * 1000))
        db.commit()
        raise

    duration_ms = int((time.perf_counter() - started) * 1000)
    tokens_total = usage.get("total_tokens") or 0
    finish_run_success(
        db,
        run,
        output_data={"summary_length": len(text)},
        tokens_prompt=usage.get("prompt_tokens"),
        tokens_completion=usage.get("completion_tokens"),
        tokens_total=tokens_total,
        duration_ms=duration_ms,
    )
    record_usage(db, org_id, tokens_total)
    db.commit()
    db.refresh(run)
    return text.strip(), insight_payload, run.id

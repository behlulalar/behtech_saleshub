import hashlib
import json
import time
from pathlib import Path

from sqlalchemy.orm import Session

from config import settings
from database import User
from roles import ROLE_EMPLOYEE
from ai.llm_client import chat_completion, assert_llm_configured
from ai.llm_config import provider_and_model
from ai.snapshots.lead_snapshot import build_lead_snapshot
from ai.store import create_run, finish_run_failed, finish_run_success
from ai.usage import ensure_quota, record_usage

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "suggest_message.md"

TEMPLATE_LABELS = {
    "intro": "İlk tanışma / intro mesajı",
    "followUp": "Takip mesajı",
    "demo": "Demo teklifi",
    "meeting": "Görüşme planlama",
}


def _prompt_version() -> str:
    raw = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.is_file() else ""
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"suggest_message.md@{digest}"


def _system_prompt() -> str:
    if PROMPT_PATH.is_file():
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "Türkçe satış mesajı öner."


def _user_prompt(user: User, snapshot: dict, template_id: str, locale: str) -> str:
    role = "employee" if user.role == ROLE_EMPLOYEE else "owner"
    label = TEMPLATE_LABELS.get(template_id, template_id)
    return (
        f"Dil: {locale}\n"
        f"Gönderen rolü: {role}\n"
        f"Mesaj türü: {label}\n"
        f"Lead bağlamı (JSON):\n{json.dumps(snapshot, ensure_ascii=False, indent=2)}\n\n"
        "Yukarıdaki lead için tek bir mesaj metni yaz."
    )


def run_suggest_message(
    db: Session,
    *,
    user: User,
    org_id: int,
    lead_id: int,
    template_id: str,
    locale: str = "tr",
) -> tuple[str, int]:
    assert_llm_configured()
    ensure_quota(db, org_id)

    snapshot = build_lead_snapshot(db, org_id, lead_id)
    input_data = {"lead_id": lead_id, "template_id": template_id, "locale": locale}
    llm_provider, llm_model = provider_and_model()
    run = create_run(
        db,
        org_id=org_id,
        requested_by=user.id,
        run_type="suggest_message",
        input_data=input_data,
        provider=llm_provider,
        model=llm_model,
        prompt_version=_prompt_version(),
    )

    started = time.perf_counter()
    try:
        text, usage = chat_completion(
            system=_system_prompt(),
            user=_user_prompt(user, snapshot, template_id, locale),
        )
    except Exception:
        finish_run_failed(db, run, error_code="provider", duration_ms=int((time.perf_counter() - started) * 1000))
        db.commit()
        raise

    duration_ms = int((time.perf_counter() - started) * 1000)
    tokens_total = usage.get("total_tokens") or 0
    output_payload = {"text_length": len(text)}
    if settings.ai_store_output:
        output_payload["text"] = text

    finish_run_success(
        db,
        run,
        output_data=output_payload,
        tokens_prompt=usage.get("prompt_tokens"),
        tokens_completion=usage.get("completion_tokens"),
        tokens_total=tokens_total,
        duration_ms=duration_ms,
    )
    record_usage(db, org_id, tokens_total)
    db.commit()
    db.refresh(run)
    return text.strip(), run.id

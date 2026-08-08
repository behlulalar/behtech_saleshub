"""Execute queued async AI runs."""

import time

from sqlalchemy.orm import Session

from ai.capabilities.batch_score_leads import run_batch_score_leads
from ai.capabilities.run_agent import run_agent_query
from ai.store import finish_run_failed, finish_run_success, mark_run_running
from ai.usage import QuotaExceededError
from database import AiRun, User


def execute_run(db: Session, run: AiRun) -> None:
    if run.status not in ("queued", "running"):
        return

    mark_run_running(db, run)
    db.flush()

    started = time.perf_counter()
    org_id = run.user_id
    requested_by = run.requested_by
    user = None
    if requested_by:
        user = db.query(User).filter(User.id == requested_by).first()
    if not user:
        user = db.query(User).filter(User.id == org_id).first()

    try:
        if run.run_type == "batch_score":
            result = run_batch_score_leads(db, org_id)
            duration_ms = int((time.perf_counter() - started) * 1000)
            finish_run_success(db, run, output_data=result, duration_ms=duration_ms)
            return

        if run.run_type == "agent":
            if not user:
                finish_run_failed(db, run, error_code="no_user", duration_ms=0)
                return
            import json

            try:
                inp = json.loads(run.input_json or "{}")
            except json.JSONDecodeError:
                inp = {}
            question = str(inp.get("question") or "").strip()
            if not question:
                finish_run_failed(db, run, error_code="missing_question", duration_ms=0)
                return
            locale = str(inp.get("locale") or "tr")
            _answer, meta = run_agent_query(
                db,
                user=user,
                org_id=org_id,
                run=run,
                question=question,
                locale=locale,
            )
            finish_run_success(
                db,
                run,
                output_data=meta["output"],
                duration_ms=meta.get("duration_ms"),
                tokens_prompt=meta.get("tokens_prompt"),
                tokens_completion=meta.get("tokens_completion"),
                tokens_total=meta.get("tokens_total"),
            )
            return

        finish_run_failed(db, run, error_code="unknown_run_type", duration_ms=0)
    except QuotaExceededError:
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_failed(db, run, error_code="quota_exhausted", duration_ms=duration_ms)
        return
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        finish_run_failed(db, run, error_code="execution_error", duration_ms=duration_ms)
        raise


def process_pending_runs(db: Session, *, limit: int = 5) -> int:
    """Pick queued runs FIFO. Skip if another run of same type is already running for org."""
    running = (
        db.query(AiRun.run_type, AiRun.user_id)
        .filter(AiRun.status == "running")
        .all()
    )
    busy = {(r.user_id, r.run_type) for r in running}

    queued = (
        db.query(AiRun)
        .filter(AiRun.status == "queued")
        .order_by(AiRun.created_at.asc())
        .limit(limit * 3)
        .all()
    )
    processed = 0
    for run in queued:
        if processed >= limit:
            break
        if (run.user_id, run.run_type) in busy:
            continue
        execute_run(db, run)
        db.commit()
        busy.add((run.user_id, run.run_type))
        processed += 1
    return processed


def batch_score_all_orgs(db: Session) -> dict:
    from database import User
    from roles import ROLE_OWNER

    owners = db.query(User).filter(User.role == ROLE_OWNER, User.owner_id.is_(None)).all()
    totals = {"orgs": 0, "leads_scored": 0}
    for owner in owners:
        result = run_batch_score_leads(db, owner.id)
        totals["orgs"] += 1
        totals["leads_scored"] += int(result.get("leads_scored") or 0)
    db.commit()
    return totals

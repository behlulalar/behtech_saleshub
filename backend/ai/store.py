import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from database import AiRun


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _load_steps(run: AiRun) -> list[dict]:
    try:
        raw = json.loads(run.steps_json or "[]")
        return raw if isinstance(raw, list) else []
    except json.JSONDecodeError:
        return []


def create_run(
    db: Session,
    *,
    org_id: int,
    requested_by: int | None,
    run_type: str,
    input_data: dict,
    provider: str = "",
    model: str = "",
    prompt_version: str = "",
    status: str = "running",
) -> AiRun:
    run = AiRun(
        user_id=org_id,
        requested_by=requested_by,
        run_type=run_type,
        status=status,
        input_json=_dump(input_data),
        steps_json="[]",
        provider=provider or None,
        model=model or None,
        prompt_version=prompt_version or None,
    )
    db.add(run)
    db.flush()
    return run


def create_queued_run(
    db: Session,
    *,
    org_id: int,
    requested_by: int | None,
    run_type: str,
    input_data: dict,
) -> AiRun:
    return create_run(
        db,
        org_id=org_id,
        requested_by=requested_by,
        run_type=run_type,
        input_data=input_data,
        status="queued",
    )


def mark_run_running(db: Session, run: AiRun) -> None:
    run.status = "running"
    run.updated_at = datetime.utcnow()


def append_run_step(db: Session, run: AiRun, step: dict) -> None:
    steps = _load_steps(run)
    steps.append(step)
    run.steps_json = _dump(steps)
    run.updated_at = datetime.utcnow()


def finish_run_success(
    db: Session,
    run: AiRun,
    *,
    output_data: dict | None = None,
    tokens_prompt: int | None = None,
    tokens_completion: int | None = None,
    tokens_total: int | None = None,
    duration_ms: int | None = None,
) -> None:
    run.status = "success"
    run.output_json = _dump(output_data or {})
    run.tokens_prompt = tokens_prompt
    run.tokens_completion = tokens_completion
    run.tokens_total = tokens_total
    run.duration_ms = duration_ms
    run.error_code = None
    run.updated_at = datetime.utcnow()


def finish_run_failed(
    db: Session,
    run: AiRun,
    *,
    error_code: str,
    duration_ms: int | None = None,
    output_data: dict | None = None,
) -> None:
    run.status = "failed"
    run.error_code = error_code
    run.duration_ms = duration_ms
    run.output_json = _dump(output_data or {})
    run.updated_at = datetime.utcnow()


def get_run_for_org(db: Session, org_id: int, run_id: int) -> AiRun | None:
    return (
        db.query(AiRun)
        .filter(AiRun.id == run_id, AiRun.user_id == org_id)
        .first()
    )


def list_runs_for_org(db: Session, org_id: int, *, limit: int = 20) -> list[AiRun]:
    return (
        db.query(AiRun)
        .filter(AiRun.user_id == org_id)
        .order_by(AiRun.created_at.desc())
        .limit(limit)
        .all()
    )


def run_to_api_dict(run: AiRun) -> dict:
    try:
        output = json.loads(run.output_json or "{}")
    except json.JSONDecodeError:
        output = None
    try:
        input_data = json.loads(run.input_json or "{}")
    except json.JSONDecodeError:
        input_data = {}
    steps = _load_steps(run)
    status = run.status
    if status == "success":
        public_status = "done"
    else:
        public_status = status
    return {
        "id": run.id,
        "run_type": run.run_type,
        "status": public_status,
        "input": input_data,
        "output": output,
        "steps": steps,
        "error_code": run.error_code,
        "created_at": _iso_utc(run.created_at),
        "updated_at": _iso_utc(run.updated_at),
        "duration_ms": run.duration_ms,
    }


def _iso_utc(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + "Z"

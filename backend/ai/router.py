from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import json

from ai.capabilities.chat import run_sales_chat
from ai.capabilities.chat_stream import iter_sales_chat_events
from ai.capabilities.diagnosis_interpreter import (
    DiagnosisInterpretDisabledError,
    DiagnosisNotFoundError,
    run_diagnosis_interpret,
)
from ai.capabilities.diagnosis_history_interpreter import (
    DiagnosisHistoryInterpretDisabledError,
    DiagnosisHistoryNotFoundError,
    DiagnosisHistoryPeriodError,
    run_diagnosis_history_interpret,
)
from ai.capabilities.priorities import run_priorities
from ai.capabilities.suggest_message import run_suggest_message
from ai.capabilities.summarize_lead import run_summarize_lead
from ai.deps import (
    ai_is_configured,
    diagnosis_history_interpret_available,
    diagnosis_interpret_available,
    get_ai_context,
    require_ai_enabled,
    require_chat_enabled,
)
from database import User, get_db
from roles import get_org_id, require_owner
from ai.llm_client import AiNotConfiguredError, DiagnosisOpenAiRequiredError
from ai.actions.propose_service import (
    ProposeValidationError,
    ai_action_to_dict,
    get_ai_action_for_org,
    list_ai_actions_for_org,
    propose_ai_action,
    propose_from_recommended_action,
    _lead_name,
)
from ai.actions.execute_service import ExecuteValidationError, approve_ai_action, execute_ai_action
from ai.actions.management_service import cancel_ai_action, update_ai_action
from ai.actions.mapper import MAPPER_NO_ACTION
from ai.store import create_queued_run, get_run_for_org, list_runs_for_org, run_to_api_dict
from ai.run_worker import execute_run, process_pending_runs
from ai.usage import usage_summary
from config import settings
from schemas import (
    AiRunCreateRequest,
    AiRunCreateResponse,
    AiRunDetailResponse,
    AiRunListResponse,
    AiStatusResponse,
    AiChatRequest,
    AiChatResponse,
    PrioritiesRequest,
    PrioritiesResponse,
    PriorityRecommendationItem,
    SuggestMessageRequest,
    SuggestMessageResponse,
    SummarizeLeadRequest,
    SummarizeLeadResponse,
    DiagnosisInterpretRequest,
    DiagnosisInterpretResponse,
    DiagnosisHistoryInterpretRequest,
    DiagnosisHistoryInterpretResponse,
    IntelligenceInsightItem,
    AiActionProposeRequest,
    AiActionFromRecommendationRequest,
    AiActionUpdateRequest,
    AiActionItemResponse,
    AiActionExecuteResponse,
    AiActionListResponse,
)

router = APIRouter()


@router.get("/status", response_model=AiStatusResponse)
def get_ai_status(
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
):
    db, _user, org_id = ctx
    usage = usage_summary(db, org_id)
    configured = ai_is_configured()
    enabled = settings.ai_enabled
    token_ok = enabled and configured and usage["tokens_remaining"] > 0
    chat_ok = token_ok and settings.ai_chat_enabled
    de3_ok = diagnosis_interpret_available(db, org_id)
    de51_ok = diagnosis_history_interpret_available(db, org_id)
    return AiStatusResponse(
        enabled=enabled,
        configured=configured,
        month=usage["month"],
        tokens_used=usage["tokens_used"],
        tokens_quota=usage["tokens_quota"],
        tokens_remaining=usage["tokens_remaining"],
        request_count=usage["request_count"],
        suggest_message_available=token_ok,
        summarize_lead_available=token_ok,
        priorities_available=enabled,
        batch_runs_available=enabled,
        agent_runs_available=token_ok,
        daily_email_enabled=enabled and settings.ai_daily_email and configured,
        chat_available=chat_ok,
        diagnosis_interpret_available=de3_ok,
        diagnosis_history_interpret_available=de51_ok,
    )


@router.post("/suggest-message", response_model=SuggestMessageResponse)
def suggest_message(
    body: SuggestMessageRequest,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
):
    require_ai_enabled()
    if not ai_is_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI yapılandırılmıyor")

    db, user, org_id = ctx
    if body.template_id not in ("intro", "followUp", "demo", "meeting"):
        raise HTTPException(status_code=422, detail="Geçersiz template_id")

    try:
        text, run_id = run_suggest_message(
            db,
            user=user,
            org_id=org_id,
            lead_id=body.lead_id,
            template_id=body.template_id,
            locale=body.locale or "tr",
        )
    except AiNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Öneri oluşturulamadı") from exc

    return SuggestMessageResponse(
        text=text,
        run_id=run_id,
        disclaimer="AI önerisi — göndermeden önce kontrol edin.",
    )


@router.post("/summarize-lead", response_model=SummarizeLeadResponse)
def summarize_lead(
    body: SummarizeLeadRequest,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
):
    require_ai_enabled()
    if not ai_is_configured():
        raise HTTPException(status_code=503, detail="AI yapılandırılmıyor")

    db, user, org_id = ctx
    try:
        summary, insights, run_id = run_summarize_lead(
            db,
            user=user,
            org_id=org_id,
            lead_id=body.lead_id,
            locale=body.locale or "tr",
        )
    except AiNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Özet oluşturulamadı") from exc

    return SummarizeLeadResponse(
        summary=summary,
        insights=[IntelligenceInsightItem(**item) for item in insights],
        run_id=run_id,
        disclaimer="AI özeti — karar vermeden önce kayıtları kontrol edin.",
    )


@router.post("/priorities", response_model=PrioritiesResponse)
def priorities(
    body: PrioritiesRequest,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    require_ai_enabled()
    db, user, org_id = ctx
    _ = owner
    try:
        items, run_id, cached = run_priorities(
            db,
            user=user,
            org_id=org_id,
            limit=body.limit,
            refresh=body.refresh,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Öncelik listesi oluşturulamadı") from exc

    return PrioritiesResponse(
        recommendations=[PriorityRecommendationItem(**item) for item in items],
        run_id=run_id or 0,
        cached=cached,
    )


@router.post("/diagnosis/interpret", response_model=DiagnosisInterpretResponse)
def diagnosis_interpret(
    body: DiagnosisInterpretRequest,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
):
    require_ai_enabled()
    db, user, org_id = ctx
    try:
        result = run_diagnosis_interpret(
            db,
            user=user,
            org_id=org_id,
            diagnosis_id=body.diagnosis_id,
            period=body.period,
            date_param=body.date,
            locale=body.locale or "tr",
            refresh=body.refresh,
        )
    except DiagnosisInterpretDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except DiagnosisNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teşhis bulunamadı") from exc
    except DiagnosisOpenAiRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Teşhis yorumu oluşturulamadı") from exc

    return DiagnosisInterpretResponse(**result)


@router.post(
    "/diagnosis/history/interpret",
    response_model=DiagnosisHistoryInterpretResponse,
)
def diagnosis_history_interpret(
    body: DiagnosisHistoryInterpretRequest,
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    """
    DE-5.1-C — historical diagnosis interpretation.
    Owner-only. Read-only vs Case/Snapshot. No proposal bridge / AiAction.
    """
    require_ai_enabled()
    org_id = get_org_id(owner)
    try:
        result = run_diagnosis_history_interpret(
            db,
            user=owner,
            org_id=org_id,
            diagnosis_id=body.diagnosis_id,
            period_key=body.period_key,
            locale=body.locale or "tr",
            refresh=body.refresh,
        )
    except DiagnosisHistoryInterpretDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except DiagnosisHistoryPeriodError as exc:
        detail = (
            "Geçersiz period_key"
            if exc.code == "invalid_period_key"
            else "period_key gerekli"
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    except DiagnosisHistoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teşhis bulunamadı") from exc
    except DiagnosisOpenAiRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Teşhis geçmişi yorumu oluşturulamadı") from exc

    return DiagnosisHistoryInterpretResponse(**result)


def _propose_validation_to_http(exc: ProposeValidationError) -> HTTPException:
    code = exc.code
    if code in ("unknown_action_type", "invalid_parameters", "invalid_target_entity", "target_entity_id_required", "target_lead_mismatch", "idempotency_key_invalid"):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif code in ("action_disabled", "action_not_allowed", "role_not_allowed"):
        status_code = status.HTTP_403_FORBIDDEN
    elif code in ("target_not_in_org", "invalid_source_run"):
        status_code = status.HTTP_404_NOT_FOUND
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail=exc.detail)


def _action_item(db, org_id: int, row) -> AiActionItemResponse:
    lead_id = row.target_entity_id if row.target_entity == "lead" else None
    return AiActionItemResponse(
        **ai_action_to_dict(row, lead_name=_lead_name(db, org_id, lead_id))
    )


@router.post("/actions/propose", response_model=AiActionItemResponse)
def propose_ai_action_endpoint(
    body: AiActionProposeRequest,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    require_ai_enabled()
    db, user, org_id = ctx
    _ = owner
    role = getattr(user, "role", None) or "owner"
    try:
        row, created = propose_ai_action(
            db,
            user_id=user.id,
            org_id=org_id,
            role=role,
            action_type=body.action_type,
            target_entity=body.target_entity,
            target_entity_id=body.target_entity_id,
            parameters=body.parameters,
            reason=body.reason,
            source_diagnosis_id=body.source_diagnosis_id,
            source_interpret_run_id=body.source_interpret_run_id,
            idempotency_key=body.idempotency_key,
        )
    except ProposeValidationError as exc:
        raise _propose_validation_to_http(exc) from exc
    db.commit()
    db.refresh(row)
    response = _action_item(db, org_id, row)
    if created:
        return response
    return response


@router.post("/actions/propose-from-recommendation", response_model=AiActionItemResponse)
def propose_from_recommendation_endpoint(
    body: AiActionFromRecommendationRequest,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    """Deterministic mapper → proposal (does not call OpenAI)."""
    require_ai_enabled()
    db, user, org_id = ctx
    _ = owner
    role = getattr(user, "role", None) or "owner"
    try:
        row, _created, outcome = propose_from_recommended_action(
            db,
            user_id=user.id,
            org_id=org_id,
            role=role,
            title=body.title,
            reason=body.reason,
            lead_id=body.lead_id,
            priority=body.priority,
            source_diagnosis_id=body.source_diagnosis_id,
            source_interpret_run_id=body.source_interpret_run_id,
            idempotency_key=body.idempotency_key,
        )
    except ProposeValidationError as exc:
        raise _propose_validation_to_http(exc) from exc
    if row is None or outcome == MAPPER_NO_ACTION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Öneri eyleme dönüştürülemedi (NO_ACTION)",
        )
    db.commit()
    db.refresh(row)
    return _action_item(db, org_id, row)


def _execute_validation_to_http(exc: ExecuteValidationError) -> HTTPException:
    code = exc.code
    if code in (
        "unknown_action_type",
        "invalid_parameters",
        "idempotency_key_required",
        "invalid_transition",
        "invalid_status_for_approve",
        "invalid_status_for_execute",
        "invalid_status_for_update",
        "invalid_status_for_cancel",
        "immutable_parameter",
        "target_lead_mismatch",
        "update_not_supported",
        "target_not_in_org",
        "invalid_target_entity",
        "target_entity_id_required",
    ):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif code in ("action_disabled", "action_not_allowed", "role_not_allowed", "execute_not_enabled"):
        status_code = status.HTTP_403_FORBIDDEN
    elif code == "not_found":
        status_code = status.HTTP_404_NOT_FOUND
    elif code in ("action_in_progress", "operational_duplicate_conflict"):
        status_code = status.HTTP_409_CONFLICT
    elif code in ("action_failed", "executor_failed"):
        status_code = status.HTTP_502_BAD_GATEWAY
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail=exc.detail)


@router.post("/actions/{action_id}/approve", response_model=AiActionItemResponse)
def approve_ai_action_endpoint(
    action_id: str,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    require_ai_enabled()
    db, _user, org_id = ctx
    _ = owner
    role = getattr(_user, "role", None) or "owner"
    try:
        row = approve_ai_action(db, org_id=org_id, role=role, action_id=action_id)
    except ExecuteValidationError as exc:
        raise _execute_validation_to_http(exc) from exc
    db.commit()
    db.refresh(row)
    return _action_item(db, org_id, row)


@router.post("/actions/{action_id}/update", response_model=AiActionItemResponse)
def update_ai_action_endpoint(
    action_id: str,
    body: AiActionUpdateRequest,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    require_ai_enabled()
    db, _user, org_id = ctx
    _ = owner
    role = getattr(_user, "role", None) or "owner"
    try:
        row = update_ai_action(
            db,
            org_id=org_id,
            role=role,
            action_id=action_id,
            parameters=body.parameters,
        )
    except ExecuteValidationError as exc:
        raise _execute_validation_to_http(exc) from exc
    db.commit()
    db.refresh(row)
    return _action_item(db, org_id, row)


@router.post("/actions/{action_id}/cancel", response_model=AiActionItemResponse)
def cancel_ai_action_endpoint(
    action_id: str,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    require_ai_enabled()
    db, _user, org_id = ctx
    _ = owner
    role = getattr(_user, "role", None) or "owner"
    try:
        row = cancel_ai_action(db, org_id=org_id, role=role, action_id=action_id)
    except ExecuteValidationError as exc:
        raise _execute_validation_to_http(exc) from exc
    db.commit()
    db.refresh(row)
    return _action_item(db, org_id, row)


@router.post("/actions/{action_id}/execute", response_model=AiActionExecuteResponse)
def execute_ai_action_endpoint(
    action_id: str,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    require_ai_enabled()
    db, user, org_id = ctx
    _ = owner
    role = getattr(user, "role", None) or "owner"
    try:
        row, did_run, result = execute_ai_action(
            db,
            org_id=org_id,
            role=role,
            actor_user_id=user.id,
            action_id=action_id,
        )
    except ExecuteValidationError as exc:
        db.commit()
        raise _execute_validation_to_http(exc) from exc
    db.commit()
    db.refresh(row)
    item = _action_item(db, org_id, row)
    activity_id = result.activity_id if result else item.execution_result.get("activity_id")
    if isinstance(activity_id, float):
        activity_id = int(activity_id)
    return AiActionExecuteResponse(
        action=item,
        activity_id=activity_id if isinstance(activity_id, int) else None,
        already_executed=not did_run and row.status == "executed",
    )


@router.get("/actions", response_model=AiActionListResponse)
def list_ai_actions(
    status_filter: str = "proposed",
    limit: int = 50,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    require_ai_enabled()
    db, _user, org_id = ctx
    _ = owner
    limit = max(1, min(limit, 100))
    rows = list_ai_actions_for_org(db, org_id, status=status_filter, limit=limit)
    items = [_action_item(db, org_id, r) for r in rows]
    return AiActionListResponse(items=items)


@router.get("/actions/{action_id}", response_model=AiActionItemResponse)
def get_ai_action(
    action_id: str,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    require_ai_enabled()
    db, _user, org_id = ctx
    _ = owner
    row = get_ai_action_for_org(db, org_id, action_id)
    if not row:
        raise HTTPException(status_code=404, detail="Aksiyon bulunamadı")
    return _action_item(db, org_id, row)


@router.post("/runs", response_model=AiRunCreateResponse)
def create_ai_run(
    body: AiRunCreateRequest,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    require_ai_enabled()
    db, user, org_id = ctx
    _ = owner

    if body.run_type == "agent":
        if not ai_is_configured():
            raise HTTPException(status_code=503, detail="AI yapılandırılmıyor")
        question = (body.question or "").strip()
        if not question:
            raise HTTPException(status_code=422, detail="Soru gerekli")
        input_data = {"question": question, "locale": body.locale or "tr"}
    else:
        input_data = {"locale": body.locale or "tr"}

    run = create_queued_run(
        db,
        org_id=org_id,
        requested_by=user.id,
        run_type=body.run_type,
        input_data=input_data,
    )
    db.commit()
    db.refresh(run)

    try:
        execute_run(db, run)
    except Exception:
        pass
    db.commit()
    db.refresh(run)

    public = run_to_api_dict(run)
    return AiRunCreateResponse(
        run_id=run.id,
        status=public["status"],
        run_type=run.run_type,
    )


@router.get("/runs/{run_id}", response_model=AiRunDetailResponse)
def get_ai_run(
    run_id: int,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
):
    require_ai_enabled()
    db, _user, org_id = ctx
    run = get_run_for_org(db, org_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run bulunamadı")
    return AiRunDetailResponse(**run_to_api_dict(run))


@router.get("/runs", response_model=AiRunListResponse)
def list_ai_runs(
    limit: int = 20,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    require_ai_enabled()
    db, _user, org_id = ctx
    _ = owner
    limit = max(1, min(limit, 50))
    rows = list_runs_for_org(db, org_id, limit=limit)
    return AiRunListResponse(items=[AiRunDetailResponse(**run_to_api_dict(r)) for r in rows])


@router.post("/runs/process-queue")
def process_ai_run_queue(
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
    owner: object = Depends(require_owner),
):
    """Cron veya owner — kuyruktaki run'ları işle."""
    require_ai_enabled()
    db, _user, _org_id = ctx
    _ = owner
    count = process_pending_runs(db, limit=5)
    db.commit()
    return {"processed": count}


@router.post("/chat", response_model=AiChatResponse)
def ai_chat(
    body: AiChatRequest,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
):
    require_chat_enabled()
    if not ai_is_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI yapılandırılmıyor")

    db, user, org_id = ctx
    history = [{"role": h.role, "content": h.content} for h in body.history]
    try:
        reply, run_id = run_sales_chat(
            db,
            user=user,
            org_id=org_id,
            message=body.message,
            history=history,
            locale=body.locale or "tr",
        )
    except ValueError as exc:
        if str(exc) == "empty_message":
            raise HTTPException(status_code=422, detail="Mesaj boş olamaz") from exc
        raise HTTPException(status_code=400, detail="Geçersiz istek") from exc
    except AiNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Yanıt oluşturulamadı") from exc

    return AiChatResponse(
        reply=reply,
        run_id=run_id,
        disclaimer="AI yanıtı — kritik kararlar için CRM kayıtlarını doğrulayın.",
    )


def _sse_line(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
def ai_chat_stream(
    body: AiChatRequest,
    ctx: tuple[Session, object, int] = Depends(get_ai_context),
):
    require_chat_enabled()
    if not ai_is_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI yapılandırılmıyor")

    db, user, org_id = ctx
    history = [{"role": h.role, "content": h.content} for h in body.history]

    if not (body.message or "").strip():
        raise HTTPException(status_code=422, detail="Mesaj boş olamaz")

    def event_stream():
        try:
            for event in iter_sales_chat_events(
                db,
                user=user,
                org_id=org_id,
                message=body.message,
                history=history,
                locale=body.locale or "tr",
            ):
                if event.get("type") == "error" and event.get("detail") == "empty_message":
                    yield _sse_line({"type": "error", "detail": "Mesaj boş olamaz"})
                    return
                if event.get("type") == "done":
                    yield _sse_line(
                        {
                            **event,
                            "disclaimer": "AI yanıtı — kritik kararlar için CRM kayıtlarını doğrulayın.",
                        }
                    )
                else:
                    yield _sse_line(event)
        except AiNotConfiguredError as exc:
            yield _sse_line({"type": "error", "detail": str(exc)})
        except Exception:
            yield _sse_line({"type": "error", "detail": "Yanıt oluşturulamadı"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

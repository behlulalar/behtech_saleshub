from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import json

from ai.capabilities.chat import run_sales_chat
from ai.capabilities.chat_stream import iter_sales_chat_events
from ai.capabilities.priorities import run_priorities
from ai.capabilities.suggest_message import run_suggest_message
from ai.capabilities.summarize_lead import run_summarize_lead
from ai.deps import ai_is_configured, get_ai_context, require_ai_enabled, require_chat_enabled
from ai.llm_client import AiNotConfiguredError
from ai.run_worker import execute_run, process_pending_runs
from ai.store import create_queued_run, get_run_for_org, list_runs_for_org, run_to_api_dict
from ai.usage import usage_summary
from config import settings
from roles import require_owner
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
    IntelligenceInsightItem,
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

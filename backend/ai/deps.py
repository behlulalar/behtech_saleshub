from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import verify_token
from config import settings
from database import User, get_db
from roles import get_org_id


from ai.llm_config import ai_is_configured, diagnosis_openai_available
from ai.usage import usage_summary

__all__ = [
    "ai_is_configured",
    "diagnosis_interpret_available",
    "diagnosis_history_interpret_available",
    "require_ai_enabled",
    "get_org_user",
    "get_ai_context",
]


def diagnosis_interpret_available(db, org_id: int) -> bool:
    if not settings.ai_enabled:
        return False
    if not settings.diagnosis_engine_enabled or not settings.ai_diagnosis_interpret_enabled:
        return False
    if not diagnosis_openai_available():
        return False
    usage = usage_summary(db, org_id)
    return usage["tokens_remaining"] > 0


def diagnosis_history_interpret_available(db, org_id: int) -> bool:
    if not settings.ai_enabled:
        return False
    if not settings.diagnosis_engine_enabled or not settings.ai_diagnosis_history_interpret_enabled:
        return False
    if not diagnosis_openai_available():
        return False
    usage = usage_summary(db, org_id)
    return usage["tokens_remaining"] > 0


def require_ai_enabled() -> None:
    if not settings.ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI özelliği kapalı",
        )


def require_chat_enabled() -> None:
    require_ai_enabled()
    if not settings.ai_chat_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI sohbet kapalı",
        )


def get_org_user(
    user: User = Depends(verify_token),
) -> tuple[User, int]:
    org_id = get_org_id(user)
    return user, org_id


def get_ai_context(
    db: Session = Depends(get_db),
    user_org: tuple[User, int] = Depends(get_org_user),
) -> tuple[Session, User, int]:
    user, org_id = user_org
    return db, user, org_id

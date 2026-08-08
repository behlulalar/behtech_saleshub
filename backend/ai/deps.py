from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import verify_token
from config import settings
from database import User, get_db
from roles import get_org_id


from ai.llm_config import ai_is_configured

__all__ = ["ai_is_configured", "require_ai_enabled", "get_org_user", "get_ai_context"]


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

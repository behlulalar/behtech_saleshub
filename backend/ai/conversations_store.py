"""DE-6 — Sales Assistant conversation persistence helpers."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from database import AssistantConversation, AssistantMessage

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
_TITLE_WS = re.compile(r"\s+")


def title_from_message(content: str, *, max_len: int = 80) -> str:
    text = _TITLE_WS.sub(" ", (content or "").strip())
    if not text:
        return "Yeni sohbet"
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def conversation_to_dict(row: AssistantConversation) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "organization_id": row.organization_id,
        "title": row.title or "",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "archived_at": row.archived_at,
    }


def message_to_dict(row: AssistantMessage) -> dict:
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "role": row.role,
        "content": row.content or "",
        "created_at": row.created_at,
        "run_id": row.run_id,
    }


def get_conversation_for_org(
    db: Session,
    *,
    organization_id: int,
    conversation_id: int,
    include_archived: bool = False,
) -> AssistantConversation | None:
    q = db.query(AssistantConversation).filter(
        AssistantConversation.organization_id == organization_id,
        AssistantConversation.id == conversation_id,
    )
    if not include_archived:
        q = q.filter(AssistantConversation.archived_at.is_(None))
    return q.first()


def list_conversations_for_org(
    db: Session,
    *,
    organization_id: int,
    user_id: int | None = None,
    limit: int = 50,
) -> list[AssistantConversation]:
    q = db.query(AssistantConversation).filter(
        AssistantConversation.organization_id == organization_id,
        AssistantConversation.archived_at.is_(None),
    )
    if user_id is not None:
        q = q.filter(AssistantConversation.user_id == user_id)
    return (
        q.order_by(AssistantConversation.updated_at.desc(), AssistantConversation.id.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )


def create_conversation(
    db: Session,
    *,
    organization_id: int,
    user_id: int,
    title: str | None = None,
) -> AssistantConversation:
    now = datetime.utcnow()
    row = AssistantConversation(
        organization_id=organization_id,
        user_id=user_id,
        title=(title or "").strip()[:255],
        created_at=now,
        updated_at=now,
        archived_at=None,
    )
    db.add(row)
    db.flush()
    return row


def update_conversation_title(
    db: Session,
    conv: AssistantConversation,
    *,
    title: str,
) -> AssistantConversation:
    conv.title = (title or "").strip()[:255]
    conv.updated_at = datetime.utcnow()
    db.flush()
    return conv


def archive_conversation(db: Session, conv: AssistantConversation) -> AssistantConversation:
    now = datetime.utcnow()
    conv.archived_at = now
    conv.updated_at = now
    db.flush()
    return conv


def list_messages_for_conversation(
    db: Session,
    *,
    organization_id: int,
    conversation_id: int,
    limit: int | None = None,
) -> list[AssistantMessage]:
    q = (
        db.query(AssistantMessage)
        .filter(
            AssistantMessage.organization_id == organization_id,
            AssistantMessage.conversation_id == conversation_id,
        )
        .order_by(AssistantMessage.created_at.asc(), AssistantMessage.id.asc())
    )
    if limit is not None:
        # Fetch latest N then restore chronological order.
        latest = (
            db.query(AssistantMessage)
            .filter(
                AssistantMessage.organization_id == organization_id,
                AssistantMessage.conversation_id == conversation_id,
            )
            .order_by(AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
            .limit(max(1, limit))
            .all()
        )
        return list(reversed(latest))
    return q.all()


def append_message(
    db: Session,
    *,
    conversation: AssistantConversation,
    user_id: int,
    role: str,
    content: str,
    run_id: int | None = None,
    touch_conversation: bool = True,
    auto_title_if_empty: bool = False,
) -> AssistantMessage:
    if role not in (ROLE_USER, ROLE_ASSISTANT):
        raise ValueError("invalid_role")
    text = (content or "").strip()
    if not text:
        raise ValueError("empty_content")

    msg = AssistantMessage(
        conversation_id=conversation.id,
        organization_id=conversation.organization_id,
        user_id=user_id,
        role=role,
        content=text[:4000],
        run_id=run_id,
        created_at=datetime.utcnow(),
    )
    db.add(msg)
    if touch_conversation:
        conversation.updated_at = datetime.utcnow()
    if auto_title_if_empty and role == ROLE_USER and not (conversation.title or "").strip():
        conversation.title = title_from_message(text)
    db.flush()
    return msg


def history_dicts_for_chat(
    db: Session,
    *,
    organization_id: int,
    conversation_id: int,
    exclude_message_id: int | None = None,
    max_items: int = 8,
) -> list[dict]:
    """Backward-compatible wrapper → DE-6.3-A conversation memory builder."""
    from ai.conversation_context import build_conversation_history_for_llm

    return build_conversation_history_for_llm(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        exclude_message_id=exclude_message_id,
        max_messages=max_items,
    )

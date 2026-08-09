"""HttpOnly refresh cookie sessions for remember-me (no passwords in browser)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import Request, Response
from sqlalchemy.orm import Session

from config import settings
from database import RefreshSession, User
from email_service import hash_token

REFRESH_COOKIE_NAME = "crm_refresh"
REFRESH_COOKIE_PATH = "/api/auth"


def _cookie_max_age_seconds() -> int:
    return int(timedelta(days=settings.remember_me_expire_days).total_seconds())


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=_cookie_max_age_seconds(),
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )


def _read_cookie_token(request: Request) -> str | None:
    raw = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw or not raw.strip():
        return None
    return raw.strip()


def create_refresh_session(db: Session, user_id: int, response: Response) -> None:
    raw = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=settings.remember_me_expire_days)
    row = RefreshSession(
        user_id=user_id,
        token_hash=hash_token(raw),
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    _set_refresh_cookie(response, raw)


def _load_valid_session(db: Session, raw_token: str) -> RefreshSession | None:
    token_hash = hash_token(raw_token)
    row = (
        db.query(RefreshSession)
        .filter(
            RefreshSession.token_hash == token_hash,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > datetime.utcnow(),
        )
        .first()
    )
    return row


def rotate_refresh_session(
    db: Session,
    request: Request,
    response: Response,
) -> User | None:
    raw = _read_cookie_token(request)
    if not raw:
        return None

    row = _load_valid_session(db, raw)
    if not row:
        clear_refresh_cookie(response)
        return None

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        row.revoked_at = datetime.utcnow()
        db.commit()
        clear_refresh_cookie(response)
        return None

    row.revoked_at = datetime.utcnow()
    raw_new = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=settings.remember_me_expire_days)
    db.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hash_token(raw_new),
            expires_at=expires_at,
        )
    )
    db.commit()
    _set_refresh_cookie(response, raw_new)
    return user


def revoke_refresh_from_request(db: Session, request: Request) -> None:
    raw = _read_cookie_token(request)
    if not raw:
        return
    token_hash = hash_token(raw)
    row = db.query(RefreshSession).filter(RefreshSession.token_hash == token_hash).first()
    if row and row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        db.commit()


def revoke_all_refresh_sessions(db: Session, user_id: int) -> None:
    now = datetime.utcnow()
    rows = (
        db.query(RefreshSession)
        .filter(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
        .all()
    )
    for row in rows:
        row.revoked_at = now
    if rows:
        db.commit()

from sqlalchemy.orm import Session

from app_timezone import local_today
from config import settings
from database import AiUsageMonthly


def current_usage_month() -> str:
    return local_today().strftime("%Y-%m")


def get_monthly_usage(db: Session, org_id: int, month: str | None = None) -> AiUsageMonthly:
    month = month or current_usage_month()
    row = (
        db.query(AiUsageMonthly)
        .filter(AiUsageMonthly.user_id == org_id, AiUsageMonthly.month == month)
        .first()
    )
    if not row:
        row = AiUsageMonthly(user_id=org_id, month=month, tokens_total=0, request_count=0)
        db.add(row)
        db.flush()
    return row


def usage_summary(db: Session, org_id: int) -> dict:
    month = current_usage_month()
    row = get_monthly_usage(db, org_id, month)
    quota = settings.ai_monthly_token_quota
    used = row.tokens_total or 0
    remaining = max(0, quota - used)
    return {
        "month": month,
        "tokens_used": used,
        "tokens_quota": quota,
        "tokens_remaining": remaining,
        "request_count": row.request_count or 0,
    }


def ensure_quota(db: Session, org_id: int, estimated_tokens: int = 0) -> None:
    summary = usage_summary(db, org_id)
    if summary["tokens_remaining"] <= 0:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Aylık AI token limiti doldu",
        )
    if estimated_tokens and summary["tokens_remaining"] < estimated_tokens:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bu istek için yeterli AI kotası yok",
        )


def record_usage(db: Session, org_id: int, tokens: int) -> None:
    row = get_monthly_usage(db, org_id)
    row.tokens_total = (row.tokens_total or 0) + max(0, tokens)
    row.request_count = (row.request_count or 0) + 1

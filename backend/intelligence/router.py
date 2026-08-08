from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import verify_token
from database import User, get_db
from intelligence.action_proposals import (
    create_proposal_from_lead,
    list_proposals,
    proposal_to_dict,
    resolve_proposal,
)
from intelligence.analytics_engine import compute_kpis
from intelligence.company_profile import get_org_profile
from intelligence.insights import insight_to_dict, list_active_insights, org_insights_deterministic, persist_insights
from reports import parse_report_anchor
from roles import get_org_id, require_owner
from schemas import (
    ActionProposalCreateRequest,
    ActionProposalItem,
    ActionProposalListResponse,
    ActionProposalResolveRequest,
    CompanyProfileResponse,
    IntelligenceInsightItem,
    IntelligenceInsightsResponse,
    IntelligenceKpisResponse,
)

router = APIRouter()


@router.get("/kpis", response_model=IntelligenceKpisResponse)
def get_intelligence_kpis(
    period: str = Query(default="monthly", pattern="^(daily|weekly|monthly)$"),
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD veya monthly için YYYY-MM"),
    db: Session = Depends(get_db),
    user: User = Depends(verify_token),
):
    org_id = get_org_id(user)
    anchor: date | None = None
    if period == "monthly" and date and len(date) >= 7:
        anchor = parse_report_anchor("monthly", None, date[:7])
    elif date:
        anchor = parse_report_anchor(period, date, None)

    include_revenue = (user.account_type or "company") == "company"
    if user.role == "employee":
        owner = db.query(User).filter(User.id == org_id).first()
        include_revenue = bool(owner and (owner.account_type or "company") == "company")

    data = compute_kpis(db, org_id, period_type=period, anchor=anchor, include_revenue=include_revenue)
    return IntelligenceKpisResponse(**data)


@router.get("/insights", response_model=IntelligenceInsightsResponse)
def get_intelligence_insights(
    limit: int = Query(default=20, ge=1, le=50),
    refresh_org: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(verify_token),
):
    org_id = get_org_id(user)
    if refresh_org:
        org_items = org_insights_deterministic(db, org_id)
        if org_items:
            persist_insights(db, org_id, entity_type="org", entity_id=None, items=org_items)
            db.commit()

    rows = list_active_insights(db, org_id, limit=limit)
    return IntelligenceInsightsResponse(
        items=[IntelligenceInsightItem(**insight_to_dict(row)) for row in rows]
    )


@router.get("/action-proposals", response_model=ActionProposalListResponse)
def get_action_proposals(
    status: str = Query(default="pending", pattern="^(pending|approved|rejected|all)$"),
    limit: int = Query(default=30, ge=1, le=50),
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    org_id = get_org_id(owner)
    st = None if status == "all" else status
    items = list_proposals(db, org_id, status=st, limit=limit)
    return ActionProposalListResponse(items=[ActionProposalItem(**item) for item in items])


@router.post("/action-proposals/{proposal_id}/resolve", response_model=ActionProposalItem)
def resolve_action_proposal(
    proposal_id: int,
    body: ActionProposalResolveRequest,
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    org_id = get_org_id(owner)
    try:
        row = resolve_proposal(db, org_id, proposal_id, approve=body.approve, actor_user_id=owner.id)
        db.commit()
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            raise HTTPException(status_code=404, detail="Öneri bulunamadı") from exc
        raise HTTPException(status_code=409, detail="Öneri zaten işlendi") from exc
    return ActionProposalItem(
        **proposal_to_dict(row, lead_name=_lead_name_from_row(db, org_id, row))
    )


@router.post("/action-proposals", response_model=ActionProposalItem, status_code=201)
def create_action_proposal(
    body: ActionProposalCreateRequest,
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    org_id = get_org_id(owner)
    try:
        row = create_proposal_from_lead(db, org_id, lead_id=body.lead_id)
        db.commit()
    except ValueError as exc:
        if str(exc) == "lead_not_found":
            raise HTTPException(status_code=404, detail="Lead bulunamadı") from exc
        raise HTTPException(status_code=400, detail="Öneri oluşturulamadı") from exc
    return ActionProposalItem(**proposal_to_dict(row, lead_name=_lead_name_from_row(db, org_id, row)))


def _lead_name_from_row(db: Session, org_id: int, row) -> str | None:
    from intelligence.action_proposals import _lead_name

    return _lead_name(db, org_id, row.lead_id)


@router.get("/company-profile", response_model=CompanyProfileResponse)
def get_company_profile(
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    org_id = get_org_id(owner)
    include_revenue = (owner.account_type or "company") == "company"
    data = get_org_profile(db, org_id, refresh=refresh, include_revenue=include_revenue)
    db.commit()
    return CompanyProfileResponse(**data)

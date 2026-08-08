"""Action proposals — human approval before CRM side effects (Faz 3 v1)."""

import json

from sqlalchemy.orm import Session

from database import ActionProposal, IntelligenceRecommendation, Lead
from intelligence.business_events import RECOMMENDATION_ACCEPTED, emit_business_event
from intelligence.proposal_effects import apply_accept_recommendation_effects


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def proposal_to_dict(row: ActionProposal, *, lead_name: str | None = None) -> dict:
    try:
        payload = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "id": row.id,
        "lead_id": row.lead_id,
        "lead_name": lead_name,
        "proposed_action": row.proposed_action,
        "payload": payload,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def _lead_name(db: Session, org_id: int, lead_id: int | None) -> str | None:
    if not lead_id:
        return None
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == org_id).first()
    return lead.isletme_adi if lead else None


def list_proposals(db: Session, org_id: int, *, status: str | None = "pending", limit: int = 30) -> list[dict]:
    q = db.query(ActionProposal).filter(ActionProposal.user_id == org_id)
    if status:
        q = q.filter(ActionProposal.status == status)
    rows = q.order_by(ActionProposal.created_at.desc()).limit(limit).all()
    return [proposal_to_dict(r, lead_name=_lead_name(db, org_id, r.lead_id)) for r in rows]


def create_proposal_from_lead(
    db: Session,
    org_id: int,
    *,
    lead_id: int,
) -> ActionProposal:
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == org_id).first()
    if not lead:
        raise ValueError("lead_not_found")

    existing = (
        db.query(ActionProposal)
        .filter(
            ActionProposal.user_id == org_id,
            ActionProposal.lead_id == lead_id,
            ActionProposal.status == "pending",
            ActionProposal.proposed_action == "accept_recommendation",
        )
        .first()
    )
    if existing:
        return existing

    rec = (
        db.query(IntelligenceRecommendation)
        .filter(
            IntelligenceRecommendation.user_id == org_id,
            IntelligenceRecommendation.lead_id == lead_id,
            IntelligenceRecommendation.user_action == "pending",
        )
        .order_by(IntelligenceRecommendation.created_at.desc())
        .first()
    )
    payload: dict = {
        "recommendation_id": rec.id if rec else None,
        "action_type": rec.action_type if rec else "follow_up",
        "score": rec.score if rec else lead.intelligence_score,
        "isletme_adi": lead.isletme_adi,
    }
    return create_proposal(
        db,
        org_id,
        proposed_action="accept_recommendation",
        lead_id=lead_id,
        payload=payload,
    )


def create_proposal(
    db: Session,
    org_id: int,
    *,
    proposed_action: str,
    lead_id: int | None = None,
    payload: dict | None = None,
) -> ActionProposal:
    row = ActionProposal(
        user_id=org_id,
        lead_id=lead_id,
        proposed_action=proposed_action,
        payload_json=_dump(payload or {}),
        status="pending",
    )
    db.add(row)
    db.flush()
    return row


def resolve_proposal(
    db: Session,
    org_id: int,
    proposal_id: int,
    *,
    approve: bool,
    actor_user_id: int | None = None,
) -> ActionProposal:
    row = (
        db.query(ActionProposal)
        .filter(ActionProposal.id == proposal_id, ActionProposal.user_id == org_id)
        .first()
    )
    if not row:
        raise ValueError("not_found")
    if row.status != "pending":
        raise ValueError("already_resolved")

    if approve:
        effect = _apply_proposal(db, org_id, row, actor_user_id=actor_user_id)
        row.status = "approved"
        if effect:
            try:
                payload = json.loads(row.payload_json or "{}")
            except json.JSONDecodeError:
                payload = {}
            payload["applied_effect"] = effect
            row.payload_json = _dump(payload)
    else:
        row.status = "rejected"
    db.flush()
    return row


def _apply_proposal(
    db: Session,
    org_id: int,
    row: ActionProposal,
    *,
    actor_user_id: int | None = None,
) -> str | None:
    if row.proposed_action == "accept_recommendation":
        try:
            payload = json.loads(row.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        rec_id = payload.get("recommendation_id")
        action_type = str(payload.get("action_type") or "follow_up")
        effect: str | None = None
        if rec_id:
            rec = (
                db.query(IntelligenceRecommendation)
                .filter(
                    IntelligenceRecommendation.id == int(rec_id),
                    IntelligenceRecommendation.user_id == org_id,
                )
                .first()
            )
            if rec:
                rec.user_action = "accepted"
                action_type = rec.action_type or action_type
        if row.lead_id and actor_user_id:
            lead = db.query(Lead).filter(Lead.id == row.lead_id, Lead.user_id == org_id).first()
            if lead:
                effect = apply_accept_recommendation_effects(
                    db,
                    org_id,
                    lead,
                    action_type=action_type,
                    actor_user_id=actor_user_id,
                )
        emit_business_event(
            db,
            org_id,
            RECOMMENDATION_ACCEPTED,
            lead_id=row.lead_id,
            payload={"proposal_id": row.id, "recommendation_id": rec_id, "effect": effect},
        )
        return effect
    return None

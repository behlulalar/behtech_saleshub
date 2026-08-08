from sqlalchemy.orm import Session

from database import DEFAULT_TAGS, LeadTag, TagModel
from schemas import TagResponse


def seed_default_tags(db: Session, user_id: int) -> None:
    for tag in DEFAULT_TAGS:
        exists = (
            db.query(TagModel)
            .filter(TagModel.user_id == user_id, TagModel.id == tag["id"])
            .first()
        )
        if not exists:
            db.add(TagModel(user_id=user_id, is_system=True, **tag))
    db.commit()


def tag_response(db: Session, user_id: int, tag: TagModel) -> TagResponse:
    lead_count = (
        db.query(LeadTag)
        .filter(LeadTag.user_id == user_id, LeadTag.tag_id == tag.id)
        .count()
    )
    return TagResponse(
        id=tag.id,
        label=tag.label,
        color=tag.color,
        is_system=tag.is_system,
        created_at=tag.created_at,
        lead_count=lead_count,
    )


def get_lead_tag_ids(db: Session, user_id: int, lead_id: int) -> list[str]:
    rows = (
        db.query(LeadTag.tag_id)
        .filter(LeadTag.user_id == user_id, LeadTag.lead_id == lead_id)
        .all()
    )
    return [row.tag_id for row in rows]


def get_lead_tags(db: Session, user_id: int, lead_id: int) -> list[TagResponse]:
    tag_ids = get_lead_tag_ids(db, user_id, lead_id)
    if not tag_ids:
        return []

    tags = (
        db.query(TagModel)
        .filter(TagModel.user_id == user_id, TagModel.id.in_(tag_ids))
        .all()
    )
    tag_map = {tag.id: tag for tag in tags}
    return [
        tag_response(db, user_id, tag_map[tag_id])
        for tag_id in tag_ids
        if tag_id in tag_map
    ]


def validate_tag_ids(db: Session, user_id: int, tag_ids: list[str]) -> None:
    if not tag_ids:
        return
    unique_ids = list(dict.fromkeys(tag_ids))
    count = (
        db.query(TagModel)
        .filter(TagModel.user_id == user_id, TagModel.id.in_(unique_ids))
        .count()
    )
    if count != len(unique_ids):
        raise ValueError("invalid")


def sync_lead_tags(db: Session, user_id: int, lead_id: int, tag_ids: list[str]) -> None:
    validate_tag_ids(db, user_id, tag_ids)
    unique_ids = list(dict.fromkeys(tag_ids))

    db.query(LeadTag).filter(LeadTag.lead_id == lead_id, LeadTag.user_id == user_id).delete()

    for tag_id in unique_ids:
        db.add(LeadTag(user_id=user_id, lead_id=lead_id, tag_id=tag_id))

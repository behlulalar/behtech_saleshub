"""Read-only CRM tools for AI agent (org-scoped)."""

from sqlalchemy.orm import Session

from database import CategoryModel, Lead
from intelligence.analytics_engine import compute_kpis
from intelligence.insights import insight_to_dict, list_active_insights
from intelligence.scoring import rank_leads_for_org


class ToolError(ValueError):
    pass


def tool_get_lead(db: Session, org_id: int, *, lead_id: int) -> dict:
    if lead_id <= 0:
        raise ToolError("invalid_lead_id")
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == org_id).first()
    if not lead:
        raise ToolError("not_found")
    cat_label = lead.category
    cat = (
        db.query(CategoryModel)
        .filter(CategoryModel.user_id == org_id, CategoryModel.id == lead.category)
        .first()
    )
    if cat:
        cat_label = cat.label
    return {
        "id": lead.id,
        "isletme_adi": lead.isletme_adi,
        "category": cat_label,
        "durum": lead.durum,
        "oncelik": lead.oncelik,
        "intelligence_score": lead.intelligence_score,
        "sehir": lead.sehir or "",
    }


def tool_list_leads(
    db: Session,
    org_id: int,
    *,
    limit: int = 10,
    ranked: bool = True,
) -> dict:
    limit = max(1, min(limit, 25))
    if ranked:
        items = rank_leads_for_org(db, org_id, limit=limit)
        return {
            "mode": "ranked",
            "count": len(items),
            "items": [
                {
                    "lead_id": x["lead_id"],
                    "isletme_adi": x["isletme_adi"],
                    "score": x["score"],
                    "priority": x["priority"],
                    "action_type": x["action_type"],
                }
                for x in items
            ],
        }
    rows = (
        db.query(Lead)
        .filter(Lead.user_id == org_id)
        .order_by(Lead.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "mode": "recent",
        "count": len(rows),
        "items": [{"lead_id": r.id, "isletme_adi": r.isletme_adi, "durum": r.durum} for r in rows],
    }


def tool_get_kpis(db: Session, org_id: int, *, period_type: str = "monthly") -> dict:
    if period_type not in ("daily", "weekly", "monthly"):
        period_type = "monthly"
    return compute_kpis(db, org_id, period_type=period_type, include_revenue=True)


def tool_get_insights(db: Session, org_id: int, *, limit: int = 10) -> dict:
    limit = max(1, min(limit, 20))
    rows = list_active_insights(db, org_id, limit=limit)
    return {
        "count": len(rows),
        "items": [insight_to_dict(row) for row in rows],
    }


TOOL_REGISTRY = {
    "get_lead": {
        "args": {"lead_id": "int"},
        "fn": lambda db, org_id, args: tool_get_lead(db, org_id, lead_id=int(args["lead_id"])),
    },
    "list_leads": {
        "args": {"limit": "int?", "ranked": "bool?"},
        "fn": lambda db, org_id, args: tool_list_leads(
            db,
            org_id,
            limit=int(args.get("limit") or 10),
            ranked=bool(args.get("ranked", True)),
        ),
    },
    "get_kpis": {
        "args": {"period_type": "str?"},
        "fn": lambda db, org_id, args: tool_get_kpis(db, org_id, period_type=str(args.get("period_type") or "monthly")),
    },
    "get_insights": {
        "args": {"limit": "int?"},
        "fn": lambda db, org_id, args: tool_get_insights(db, org_id, limit=int(args.get("limit") or 10)),
    },
}


def execute_tool(db: Session, org_id: int, tool_name: str, args: dict) -> dict:
    entry = TOOL_REGISTRY.get(tool_name)
    if not entry:
        raise ToolError("unknown_tool")
    try:
        result = entry["fn"](db, org_id, args or {})
        return {"ok": True, "tool": tool_name, "result": result}
    except ToolError as exc:
        return {"ok": False, "tool": tool_name, "error": str(exc)}
    except (TypeError, ValueError, KeyError) as exc:
        return {"ok": False, "tool": tool_name, "error": "invalid_args", "detail": str(exc)}

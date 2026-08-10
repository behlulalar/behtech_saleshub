"""Read-only analysis of duplicate active ai_actions (run locally; no mutations)."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy.orm import Session

from database import AiAction, SessionLocal

ACTIVE = ("proposed", "approved", "executing")


def analyze_duplicate_active_proposals(db: Session) -> list[dict]:
    rows = (
        db.query(AiAction)
        .filter(AiAction.status.in_(ACTIVE))
        .order_by(AiAction.organization_id, AiAction.action_type, AiAction.target_entity_id)
        .all()
    )
    groups: dict[tuple, list[AiAction]] = defaultdict(list)
    for row in rows:
        key = (
            row.organization_id,
            row.action_type,
            row.target_entity,
            row.target_entity_id,
        )
        groups[key].append(row)

    out: list[dict] = []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        org_id, action_type, target_entity, target_entity_id = key
        out.append(
            {
                "organization_id": org_id,
                "action_type": action_type,
                "target_entity": target_entity,
                "target_entity_id": target_entity_id,
                "duplicate_count": len(items),
                "rows": [
                    {
                        "action_id": i.action_id,
                        "status": i.status,
                        "source_diagnosis_id": i.source_diagnosis_id,
                        "source_interpret_run_id": i.source_interpret_run_id,
                        "created_at": i.created_at.isoformat() if i.created_at else None,
                    }
                    for i in items
                ],
            }
        )
    return out


def main() -> None:
    db = SessionLocal()
    try:
        dupes = analyze_duplicate_active_proposals(db)
        print(f"Active duplicate groups: {len(dupes)}")
        for g in dupes:
            print(g)
    finally:
        db.close()


if __name__ == "__main__":
    main()

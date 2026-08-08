#!/usr/bin/env python3
"""Async AI jobs — batch scoring and run queue processing."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.run_worker import batch_score_all_orgs, process_pending_runs
from database import SessionLocal, init_db
from intelligence.company_profile import refresh_all_org_profiles


def main() -> int:
    parser = argparse.ArgumentParser(description="BehTech Sales Hub AI jobs")
    parser.add_argument(
        "mode",
        choices=["process_queue", "score_all_orgs", "refresh_profiles"],
        help="process_queue=queued ai_runs; score_all_orgs=nightly batch; refresh_profiles=company intel",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max runs for process_queue")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        if args.mode == "process_queue":
            count = process_pending_runs(db, limit=max(1, args.limit))
            db.commit()
            print(f"[ai-job] process_queue processed={count}")
        elif args.mode == "score_all_orgs":
            totals = batch_score_all_orgs(db)
            print(f"[ai-job] score_all_orgs orgs={totals['orgs']} leads={totals['leads_scored']}")
        else:
            n = refresh_all_org_profiles(db)
            db.commit()
            print(f"[ai-job] refresh_profiles orgs={n}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

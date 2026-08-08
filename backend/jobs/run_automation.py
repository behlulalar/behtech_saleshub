#!/usr/bin/env python3
"""CRM otomasyon job'ları — sabah özeti ve gün sonu raporu."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation import run_eod_summaries, run_morning_digests
from database import SessionLocal, init_db


def main() -> int:
    parser = argparse.ArgumentParser(description="BehTech Sales Hub otomasyon")
    parser.add_argument("mode", choices=["morning", "eod"], help="morning=sabah özeti, eod=gün sonu")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        if args.mode == "morning":
            sent = run_morning_digests(db)
            print(f"[automation] morning digests sent: {sent}")
        else:
            sent = run_eod_summaries(db)
            print(f"[automation] eod summaries sent: {sent}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

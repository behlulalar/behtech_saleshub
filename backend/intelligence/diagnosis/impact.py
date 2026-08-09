"""DE-2 business impact aggregates from priority rows."""

from __future__ import annotations


def compute_impact(priority_rows: list[dict]) -> dict:
    high = sum(1 for r in priority_rows if r.get("priority") == "high")
    medium = sum(1 for r in priority_rows if r.get("priority") == "medium")
    low = sum(1 for r in priority_rows if r.get("priority") == "low")
    return {
        "high_priority_count": high,
        "medium_priority_count": medium,
        "low_priority_count": low,
        "estimated_pipeline_value": None,
    }


def empty_impact() -> dict:
    return {
        "high_priority_count": 0,
        "medium_priority_count": 0,
        "low_priority_count": 0,
        "estimated_pipeline_value": None,
    }

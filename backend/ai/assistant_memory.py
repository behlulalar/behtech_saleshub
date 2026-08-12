"""DE-6 assistant memory.

Redis is a short-term memory/cache layer only. Conversation UI history remains
client-persisted for the first vertical slice; CRM truth is never stored as
memory and is always read from PostgreSQL.
"""

from __future__ import annotations

import json
from typing import Any

from config import settings

try:  # Redis is optional for local development until the service is provisioned.
    from redis import Redis
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    Redis = None  # type: ignore[misc,assignment]


MAX_MEMORY_MESSAGES = 8
MEMORY_TTL_SECONDS = 60 * 60 * 24 * 30


def _client():
    if Redis is None or not settings.assistant_redis_enabled or not settings.assistant_redis_url:
        return None
    try:
        return Redis.from_url(
            settings.assistant_redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception:
        return None


def _key(org_id: int, user_id: int) -> str:
    return f"behtech:assistant:memory:{org_id}:{user_id}"


def load_memory(org_id: int, user_id: int) -> list[dict[str, str]]:
    client = _client()
    if client is None:
        return []
    try:
        raw = client.get(_key(org_id, user_id))
        if not raw:
            return []
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return [
            {"role": item["role"], "content": str(item["content"])[:4000]}
            for item in data
            if isinstance(item, dict) and item.get("role") in ("user", "assistant") and item.get("content")
        ][-MAX_MEMORY_MESSAGES:]
    except Exception:
        return []


def save_memory(org_id: int, user_id: int, messages: list[dict[str, Any]]) -> None:
    client = _client()
    if client is None:
        return
    clean = [
        {"role": item.get("role"), "content": str(item.get("content") or "")[:4000]}
        for item in messages
        if item.get("role") in ("user", "assistant") and str(item.get("content") or "").strip()
    ][-MAX_MEMORY_MESSAGES:]
    try:
        client.setex(_key(org_id, user_id), MEMORY_TTL_SECONDS, json.dumps(clean, ensure_ascii=False))
    except Exception:
        # Redis must never make the CRM assistant unavailable.
        return

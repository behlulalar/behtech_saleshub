"""DE-6.5 — Optional Redis working memory for Sales Assistant.

PostgreSQL remains the authoritative conversation store.
Redis is a best-effort short-term cache; failures never fail chat.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from config import settings

logger = logging.getLogger("behtech.ai.assistant_memory")

MEMORY_VERSION = 1
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


def memory_key(*, organization_id: int, user_id: int, conversation_id: int) -> str:
    return f"assistant:memory:{int(organization_id)}:{int(user_id)}:{int(conversation_id)}"


def _ttl_seconds() -> int | None:
    ttl = int(getattr(settings, "assistant_memory_ttl_seconds", 86400) or 0)
    if ttl <= 0:
        return None
    return ttl


def _max_messages() -> int:
    return max(1, min(int(getattr(settings, "assistant_memory_max_messages", 12) or 12), 50))


def _max_chars() -> int:
    return max(500, int(getattr(settings, "assistant_memory_max_chars", 14000) or 14000))


def sanitize_memory_messages(messages: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Keep only user/assistant role+content; strip tool dumps / internal ids."""
    from ai.conversation_context import sanitize_content_for_model

    out: list[dict[str, str]] = []
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        if role not in (ROLE_USER, ROLE_ASSISTANT):
            continue
        content = sanitize_content_for_model(str(item.get("content") or ""))
        if not content:
            continue
        # Drop any accidental internal fields — only role/content survive.
        out.append({"role": role, "content": content})
    return _bound_messages(out)


def _bound_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    from ai.conversation_context import _truncate_newest_first

    bounded, _ = _truncate_newest_first(
        messages,
        max_messages=_max_messages(),
        max_chars=_max_chars(),
    )
    # Drop truncation placeholder from Redis storage (PG builder adds it when needed).
    from ai.conversation_context import TRUNCATION_PLACEHOLDER

    return [m for m in bounded if m.get("content") != TRUNCATION_PLACEHOLDER]


def _payload(messages: list[dict[str, str]]) -> str:
    return json.dumps({"version": MEMORY_VERSION, "messages": messages}, ensure_ascii=False)


def _parse_payload(raw: str | None) -> list[dict[str, str]] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if int(data.get("version") or 0) != MEMORY_VERSION:
        return None
    msgs = data.get("messages")
    if not isinstance(msgs, list):
        return None
    cleaned = sanitize_memory_messages(msgs)
    return cleaned


class AssistantMemoryStore(Protocol):
    def get(
        self,
        *,
        organization_id: int,
        user_id: int,
        conversation_id: int,
    ) -> list[dict[str, str]] | None: ...

    def set(
        self,
        *,
        organization_id: int,
        user_id: int,
        conversation_id: int,
        messages: list[dict[str, Any]],
    ) -> bool: ...

    def append(
        self,
        *,
        organization_id: int,
        user_id: int,
        conversation_id: int,
        message: dict[str, Any],
    ) -> bool: ...

    def clear(
        self,
        *,
        organization_id: int,
        user_id: int,
        conversation_id: int,
    ) -> bool: ...

    def ping(self) -> bool: ...


class NullAssistantMemoryStore:
    """Feature disabled / no-op."""

    def get(self, *, organization_id: int, user_id: int, conversation_id: int) -> list[dict[str, str]] | None:
        logger.info("assistant_memory_disabled")
        return None

    def set(self, *, organization_id: int, user_id: int, conversation_id: int, messages: list[dict[str, Any]]) -> bool:
        return False

    def append(self, *, organization_id: int, user_id: int, conversation_id: int, message: dict[str, Any]) -> bool:
        return False

    def clear(self, *, organization_id: int, user_id: int, conversation_id: int) -> bool:
        return False

    def ping(self) -> bool:
        return False


class InMemoryAssistantMemoryStore:
    """Process-local store for unit tests (not production)."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, *, organization_id: int, user_id: int, conversation_id: int) -> list[dict[str, str]] | None:
        key = memory_key(organization_id=organization_id, user_id=user_id, conversation_id=conversation_id)
        parsed = _parse_payload(self._data.get(key))
        if parsed is None:
            logger.info("assistant_memory_miss")
            return None
        logger.info("assistant_memory_hit")
        return parsed

    def set(self, *, organization_id: int, user_id: int, conversation_id: int, messages: list[dict[str, Any]]) -> bool:
        key = memory_key(organization_id=organization_id, user_id=user_id, conversation_id=conversation_id)
        cleaned = sanitize_memory_messages(messages)
        self._data[key] = _payload(cleaned)
        return True

    def append(self, *, organization_id: int, user_id: int, conversation_id: int, message: dict[str, Any]) -> bool:
        existing = self.get(
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
        ) or []
        existing = list(existing)
        existing.extend(sanitize_memory_messages([message]))
        return self.set(
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
            messages=existing,
        )

    def clear(self, *, organization_id: int, user_id: int, conversation_id: int) -> bool:
        key = memory_key(organization_id=organization_id, user_id=user_id, conversation_id=conversation_id)
        self._data.pop(key, None)
        return True

    def ping(self) -> bool:
        return True


class RedisAssistantMemoryStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, *, organization_id: int, user_id: int, conversation_id: int) -> list[dict[str, str]] | None:
        key = memory_key(organization_id=organization_id, user_id=user_id, conversation_id=conversation_id)
        try:
            raw = self._client.get(key)
        except Exception:
            logger.warning("assistant_memory_fallback", extra={"op": "get"})
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        parsed = _parse_payload(raw)
        if parsed is None:
            logger.info("assistant_memory_miss")
            return None
        logger.info("assistant_memory_hit")
        return parsed

    def set(self, *, organization_id: int, user_id: int, conversation_id: int, messages: list[dict[str, Any]]) -> bool:
        key = memory_key(organization_id=organization_id, user_id=user_id, conversation_id=conversation_id)
        cleaned = sanitize_memory_messages(messages)
        ttl = _ttl_seconds()
        try:
            payload = _payload(cleaned)
            if ttl is None:
                # Spec: do not use infinite TTL — skip write when TTL invalid.
                logger.warning("assistant_memory_write_failed", extra={"reason": "invalid_ttl"})
                return False
            self._client.set(key, payload, ex=ttl)
            return True
        except Exception:
            logger.warning("assistant_memory_write_failed", extra={"op": "set"})
            return False

    def append(self, *, organization_id: int, user_id: int, conversation_id: int, message: dict[str, Any]) -> bool:
        existing = self.get(
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
        ) or []
        existing = list(existing)
        existing.extend(sanitize_memory_messages([message]))
        return self.set(
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
            messages=existing,
        )

    def clear(self, *, organization_id: int, user_id: int, conversation_id: int) -> bool:
        key = memory_key(organization_id=organization_id, user_id=user_id, conversation_id=conversation_id)
        try:
            self._client.delete(key)
            return True
        except Exception:
            logger.warning("assistant_memory_write_failed", extra={"op": "clear"})
            return False

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:
            return False


_store_singleton: AssistantMemoryStore | None = None
_test_override: AssistantMemoryStore | None = None


def reset_assistant_memory_store_for_tests(store: AssistantMemoryStore | None = None) -> None:
    """Test helper to inject/clear store singleton."""
    global _store_singleton, _test_override
    _test_override = store
    _store_singleton = None


def get_assistant_memory_store() -> AssistantMemoryStore:
    global _store_singleton
    if _test_override is not None:
        return _test_override
    if _store_singleton is not None:
        return _store_singleton

    if not bool(getattr(settings, "assistant_memory_enabled", False)):
        _store_singleton = NullAssistantMemoryStore()
        return _store_singleton

    ttl = _ttl_seconds()
    if ttl is None:
        _store_singleton = NullAssistantMemoryStore()
        return _store_singleton

    try:
        import redis  # optional dependency; import must not fail app if missing at runtime without flag
    except Exception:
        logger.warning("assistant_memory_fallback", extra={"reason": "redis_import_failed"})
        _store_singleton = NullAssistantMemoryStore()
        return _store_singleton

    try:
        timeout = float(getattr(settings, "assistant_memory_socket_timeout_sec", 0.5) or 0.5)
        timeout = max(0.2, min(timeout, 1.0))
        client = redis.Redis.from_url(
            str(settings.assistant_memory_redis_url),
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
            decode_responses=True,
        )
        # Do not require ping success for singleton: per-op get/set already fail-open,
        # so Redis can recover mid-process without permanently locking to Null.
        _store_singleton = RedisAssistantMemoryStore(client)
        return _store_singleton
    except Exception:
        logger.warning("assistant_memory_fallback", extra={"reason": "redis_connect_failed"})
        # Transient client construction failure — do not cache Null forever.
        return NullAssistantMemoryStore()


def _fingerprints(messages: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [(m.get("role") or "", (m.get("content") or "")[:120]) for m in messages]


def merge_working_memory_with_postgres(
    *,
    organization_id: int,
    user_id: int,
    conversation_id: int,
    postgres_history: list[dict[str, str]],
) -> tuple[list[dict[str, str]], str]:
    """
    Build LLM history with optional Redis working memory.

    Returns (history, source) where source in:
    disabled | hit | miss | stale_refresh | fallback
    PostgreSQL history is always authoritative on conflict.
    """
    pg = sanitize_memory_messages(postgres_history)
    store = get_assistant_memory_store()
    if isinstance(store, NullAssistantMemoryStore) or not bool(
        getattr(settings, "assistant_memory_enabled", False)
    ):
        return pg, "disabled"

    try:
        cached = store.get(
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
    except Exception:
        logger.warning("assistant_memory_fallback", extra={"op": "merge_get"})
        return pg, "fallback"

    if cached is None:
        # Warm cache from PG (best-effort).
        try:
            store.set(
                organization_id=organization_id,
                user_id=user_id,
                conversation_id=conversation_id,
                messages=pg,
            )
        except Exception:
            logger.warning("assistant_memory_write_failed", extra={"op": "warm"})
        return pg, "miss"

    # If Redis diverges from PG tail, PG wins and Redis is refreshed.
    pg_fp = _fingerprints(pg[-6:])
    cached_fp = _fingerprints(cached[-6:])
    if pg and cached_fp != pg_fp and pg_fp:
        try:
            store.set(
                organization_id=organization_id,
                user_id=user_id,
                conversation_id=conversation_id,
                messages=pg,
            )
        except Exception:
            logger.warning("assistant_memory_write_failed", extra={"op": "stale_refresh"})
        return pg, "stale_refresh"

    # Compatible — still return PG (authoritative). Redis hit logged for observability.
    return pg, "hit"


def best_effort_memory_append(
    *,
    organization_id: int,
    user_id: int,
    conversation_id: int,
    role: str,
    content: str,
) -> None:
    if role not in (ROLE_USER, ROLE_ASSISTANT):
        return
    if not bool(getattr(settings, "assistant_memory_enabled", False)):
        return
    try:
        get_assistant_memory_store().append(
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message={"role": role, "content": content},
        )
    except Exception:
        logger.warning("assistant_memory_write_failed", extra={"op": "append"})


def best_effort_memory_sync_from_postgres(
    *,
    organization_id: int,
    user_id: int,
    conversation_id: int,
    messages: list[dict[str, Any]],
) -> None:
    if not bool(getattr(settings, "assistant_memory_enabled", False)):
        return
    try:
        get_assistant_memory_store().set(
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
            messages=messages,
        )
    except Exception:
        logger.warning("assistant_memory_write_failed", extra={"op": "sync"})


def best_effort_memory_clear(
    *,
    organization_id: int,
    user_id: int,
    conversation_id: int,
) -> None:
    if not bool(getattr(settings, "assistant_memory_enabled", False)):
        return
    try:
        get_assistant_memory_store().clear(
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
    except Exception:
        logger.warning("assistant_memory_write_failed", extra={"op": "clear"})

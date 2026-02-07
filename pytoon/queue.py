"""Redis-backed job / segment queue with automatic fakeredis fallback."""

from __future__ import annotations

import json
from typing import Any, Optional

import redis as _redis_lib

from pytoon.config import get_settings
from pytoon.log import get_logger

logger = get_logger(__name__)

_client: Optional[_redis_lib.Redis] = None

QUEUE_KEY = "pytoon:jobs"
SEGMENT_QUEUE_KEY = "pytoon:segments"


def _connect() -> _redis_lib.Redis:
    """Connect to real Redis; fall back to fakeredis if unavailable."""
    global _client
    if _client is not None:
        return _client

    settings = get_settings()

    # Try real Redis first
    try:
        pool = _redis_lib.ConnectionPool.from_url(
            settings.redis_url, decode_responses=True,
        )
        client = _redis_lib.Redis(connection_pool=pool)
        client.ping()
        logger.info("queue_backend", backend="redis", url=settings.redis_url)
        _client = client
        return _client
    except Exception:
        pass

    # Fall back to fakeredis (in-memory, same process)
    try:
        import fakeredis
        client = fakeredis.FakeRedis(decode_responses=True)
        logger.info("queue_backend", backend="fakeredis (in-memory)")
        _client = client
        return _client
    except ImportError:
        raise RuntimeError(
            "Redis is not reachable and fakeredis is not installed. "
            "Install fakeredis (`pip install fakeredis`) or start a Redis server."
        )


def get_redis() -> _redis_lib.Redis:
    return _connect()


# ---------------------------------------------------------------------------
# Job queue helpers
# ---------------------------------------------------------------------------

def enqueue_job(job_id: str, payload: dict[str, Any] | None = None):
    r = get_redis()
    msg = json.dumps({"job_id": job_id, **(payload or {})})
    r.lpush(QUEUE_KEY, msg)
    logger.info("enqueued_job", job_id=job_id)


def dequeue_job(timeout: int = 5) -> Optional[dict[str, Any]]:
    r = get_redis()
    # fakeredis brpop may behave differently; handle gracefully
    try:
        result = r.brpop(QUEUE_KEY, timeout=timeout)
    except Exception:
        # For fakeredis: fall back to non-blocking rpop
        raw = r.rpop(QUEUE_KEY)
        if raw is None:
            return None
        return json.loads(raw)
    if result is None:
        return None
    _, raw = result
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Segment queue helpers
# ---------------------------------------------------------------------------

def enqueue_segment(job_id: str, segment_index: int):
    r = get_redis()
    msg = json.dumps({"job_id": job_id, "segment_index": segment_index})
    r.lpush(SEGMENT_QUEUE_KEY, msg)


def dequeue_segment(timeout: int = 5) -> Optional[dict[str, Any]]:
    r = get_redis()
    try:
        result = r.brpop(SEGMENT_QUEUE_KEY, timeout=timeout)
    except Exception:
        raw = r.rpop(SEGMENT_QUEUE_KEY)
        if raw is None:
            return None
        return json.loads(raw)
    if result is None:
        return None
    _, raw = result
    return json.loads(raw)


def queue_depth() -> int:
    r = get_redis()
    return r.llen(QUEUE_KEY) + r.llen(SEGMENT_QUEUE_KEY)

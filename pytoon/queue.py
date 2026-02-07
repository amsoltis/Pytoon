"""Redis-backed job / segment queue."""

from __future__ import annotations

import json
from typing import Any, Optional

import redis

from pytoon.config import get_settings
from pytoon.log import get_logger

logger = get_logger(__name__)

_pool: Optional[redis.ConnectionPool] = None

QUEUE_KEY = "pytoon:jobs"
SEGMENT_QUEUE_KEY = "pytoon:segments"


def _get_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    return _pool


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_get_pool())


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
    result = r.brpop(QUEUE_KEY, timeout=timeout)
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
    result = r.brpop(SEGMENT_QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _, raw = result
    return json.loads(raw)


def queue_depth() -> int:
    r = get_redis()
    return r.llen(QUEUE_KEY) + r.llen(SEGMENT_QUEUE_KEY)

"""Performance profiling and optimization utilities.

Provides:
  - Pipeline step timer decorator.
  - Memory-bounded temp file cleanup.
  - Prompt-hash based clip caching.
  - Parallel dispatch optimization helpers.
  - Benchmarking harness.

Ticket: P5-11
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from pytoon.log import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pipeline step timer
# ---------------------------------------------------------------------------


def timed_step(step_name: str):
    """Decorator to time and log a pipeline step."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            t0 = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                elapsed = (time.monotonic() - t0) * 1000
                logger.info(
                    "pipeline_step_complete",
                    step=step_name,
                    duration_ms=round(elapsed, 1),
                    status="success",
                )
                return result
            except Exception as exc:
                elapsed = (time.monotonic() - t0) * 1000
                logger.error(
                    "pipeline_step_failed",
                    step=step_name,
                    duration_ms=round(elapsed, 1),
                    error=str(exc),
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            t0 = time.monotonic()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.monotonic() - t0) * 1000
                logger.info(
                    "pipeline_step_complete",
                    step=step_name,
                    duration_ms=round(elapsed, 1),
                    status="success",
                )
                return result
            except Exception as exc:
                elapsed = (time.monotonic() - t0) * 1000
                logger.error(
                    "pipeline_step_failed",
                    step=step_name,
                    duration_ms=round(elapsed, 1),
                    error=str(exc),
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Temp file cleanup
# ---------------------------------------------------------------------------


def cleanup_temp_files(job_dir: str | Path, keep_final: bool = True) -> int:
    """Remove intermediate assembly files, keeping only final outputs.

    Returns number of files removed.
    """
    job_path = Path(job_dir)
    if not job_path.exists():
        return 0

    # Intermediate patterns to remove
    intermediate_patterns = [
        "assembly/01_*",
        "assembly/02_*",
        "assembly/03_*",
        "assembly/04_*",
        "assembly/audio/*",
        "processed/*",
    ]

    removed = 0
    for pattern in intermediate_patterns:
        for f in job_path.glob(pattern):
            if f.is_file():
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass

    if removed > 0:
        logger.info("temp_cleanup", job_dir=str(job_dir), files_removed=removed)

    return removed


def get_dir_size_mb(path: str | Path) -> float:
    """Get total size of directory in megabytes."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = Path(dirpath) / f
            try:
                total += fp.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


# ---------------------------------------------------------------------------
# Prompt-hash clip caching
# ---------------------------------------------------------------------------

_CACHE_DIR_NAME = ".clip_cache"


def get_cache_key(prompt: str, engine: str, duration_s: float) -> str:
    """Generate a cache key from prompt + engine + duration."""
    content = f"{engine}:{duration_s:.1f}:{prompt}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_cached_clip(
    cache_dir: str | Path,
    cache_key: str,
) -> Path | None:
    """Look up a cached clip by key."""
    cache_path = Path(cache_dir) / _CACHE_DIR_NAME / f"{cache_key}.mp4"
    if cache_path.exists() and cache_path.stat().st_size > 0:
        logger.info("cache_hit", key=cache_key)
        return cache_path
    return None


def cache_clip(
    cache_dir: str | Path,
    cache_key: str,
    clip_path: str | Path,
) -> Path:
    """Store a clip in the cache."""
    dest_dir = Path(cache_dir) / _CACHE_DIR_NAME
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{cache_key}.mp4"
    shutil.copy2(str(clip_path), str(dest))
    logger.info("cache_store", key=cache_key)
    return dest


# ---------------------------------------------------------------------------
# Benchmarking
# ---------------------------------------------------------------------------


class PipelineBenchmark:
    """Simple pipeline benchmarking tracker."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.steps: dict[str, float] = {}
        self._start_times: dict[str, float] = {}
        self.start_time = time.monotonic()

    def start_step(self, name: str) -> None:
        self._start_times[name] = time.monotonic()

    def end_step(self, name: str) -> None:
        if name in self._start_times:
            elapsed = (time.monotonic() - self._start_times[name]) * 1000
            self.steps[name] = elapsed
            del self._start_times[name]

    @property
    def total_ms(self) -> float:
        return (time.monotonic() - self.start_time) * 1000

    def report(self) -> dict:
        return {
            "job_id": self.job_id,
            "total_ms": round(self.total_ms, 1),
            "steps": {k: round(v, 1) for k, v in self.steps.items()},
            "bottleneck": max(self.steps, key=self.steps.get) if self.steps else None,
        }

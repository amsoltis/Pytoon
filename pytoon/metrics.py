"""Prometheus-style metrics helpers."""

from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge, generate_latest

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

RENDER_JOBS_TOTAL = Counter(
    "pytoon_render_jobs_total",
    "Total render jobs submitted",
    ["archetype", "preset"],
)

RENDER_SUCCESS = Counter(
    "pytoon_render_success_total",
    "Successful renders",
    ["archetype"],
)

RENDER_FAILURE = Counter(
    "pytoon_render_failure_total",
    "Failed renders",
    ["archetype", "reason"],
)

FALLBACK_USED = Counter(
    "pytoon_fallback_total",
    "Fallback events",
    ["fallback_type"],  # engine_fallback | archetype_fallback | template_fallback
)

# ---------------------------------------------------------------------------
# Histograms
# ---------------------------------------------------------------------------

SEGMENT_RENDER_TIME = Histogram(
    "pytoon_segment_render_seconds",
    "Time to render one segment",
    ["engine"],
    buckets=[1, 5, 10, 20, 30, 60, 120, 300],
)

JOB_TOTAL_TIME = Histogram(
    "pytoon_job_total_seconds",
    "Total wall-clock time per job",
    ["archetype"],
    buckets=[10, 30, 60, 120, 300, 600],
)

# ---------------------------------------------------------------------------
# Gauges
# ---------------------------------------------------------------------------

QUEUE_DEPTH = Gauge(
    "pytoon_queue_depth",
    "Current number of jobs in the queue",
)


def metrics_text() -> bytes:
    """Return Prometheus exposition text."""
    return generate_latest()

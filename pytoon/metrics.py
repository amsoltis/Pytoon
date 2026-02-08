"""Prometheus-style metrics helpers.

V2 enhancements (P5-13):
  - Scene render duration (per engine).
  - Engine invocations and fallbacks.
  - Caption alignment accuracy.
  - TTS duration and success/failure.
  - V2 job duration.
  - Audio processing metrics.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge, generate_latest

# ---------------------------------------------------------------------------
# V1 Counters
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
# V1 Histograms
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
# V1 Gauges
# ---------------------------------------------------------------------------

QUEUE_DEPTH = Gauge(
    "pytoon_queue_depth",
    "Current number of jobs in the queue",
)

# ---------------------------------------------------------------------------
# V2 Scene / Engine Metrics (P5-13)
# ---------------------------------------------------------------------------

V2_SCENE_RENDER_TIME = Histogram(
    "pytoon_v2_scene_render_seconds",
    "Time to render one V2 scene",
    ["engine", "scene_type"],
    buckets=[1, 5, 10, 20, 30, 60, 120, 300],
)

V2_ENGINE_INVOCATIONS = Counter(
    "pytoon_v2_engine_invocations_total",
    "Total engine invocations in V2",
    ["engine", "result"],  # result: success | failure | moderation | timeout
)

V2_ENGINE_FALLBACKS = Counter(
    "pytoon_v2_engine_fallbacks_total",
    "V2 engine fallback events",
    ["from_engine", "to_engine"],
)

V2_JOB_DURATION = Histogram(
    "pytoon_v2_job_total_seconds",
    "Total V2 job duration end-to-end",
    ["preset", "scene_count"],
    buckets=[10, 30, 60, 120, 240, 600],
)

V2_JOB_SUCCESS = Counter(
    "pytoon_v2_job_success_total",
    "V2 jobs completed successfully",
    ["preset"],
)

V2_JOB_FAILURE = Counter(
    "pytoon_v2_job_failure_total",
    "V2 jobs that failed",
    ["preset", "reason"],
)

# ---------------------------------------------------------------------------
# V2 Caption / Alignment Metrics
# ---------------------------------------------------------------------------

V2_CAPTION_ALIGNMENT_ACCURACY = Histogram(
    "pytoon_v2_caption_alignment_ms",
    "Caption alignment accuracy (milliseconds deviation)",
    ["method"],  # whisperx | stable_ts | even_split
    buckets=[10, 25, 50, 100, 200, 500],
)

V2_CAPTIONS_TOTAL = Counter(
    "pytoon_v2_captions_total",
    "Total captions generated",
    ["alignment_method"],
)

# ---------------------------------------------------------------------------
# V2 TTS Metrics
# ---------------------------------------------------------------------------

V2_TTS_DURATION = Histogram(
    "pytoon_v2_tts_duration_seconds",
    "TTS generation duration",
    ["provider"],
    buckets=[1, 2, 5, 10, 20, 30],
)

V2_TTS_SUCCESS = Counter(
    "pytoon_v2_tts_success_total",
    "Successful TTS generations",
    ["provider"],
)

V2_TTS_FAILURE = Counter(
    "pytoon_v2_tts_failure_total",
    "Failed TTS generations",
    ["provider"],
)

# ---------------------------------------------------------------------------
# V2 Audio Processing Metrics
# ---------------------------------------------------------------------------

V2_AUDIO_DUCKING_REGIONS = Histogram(
    "pytoon_v2_audio_ducking_regions",
    "Number of duck regions per job",
    buckets=[0, 1, 2, 3, 5, 10],
)

V2_AUDIO_NORMALIZATION_LUFS = Histogram(
    "pytoon_v2_audio_normalization_lufs",
    "Post-normalization LUFS values",
    buckets=[-20, -18, -16, -14, -12, -10],
)

# ---------------------------------------------------------------------------
# V2 Moderation Metrics
# ---------------------------------------------------------------------------

V2_MODERATION_FLAGS = Counter(
    "pytoon_v2_moderation_flags_total",
    "Content moderation flag events",
    ["strictness", "trigger"],  # trigger: prompt | nsfw | competitor
)

V2_MODERATION_REPHRASES = Counter(
    "pytoon_v2_moderation_rephrases_total",
    "Auto-rephrase attempts on moderation rejection",
    ["engine"],
)


def metrics_text() -> bytes:
    """Return Prometheus exposition text."""
    return generate_latest()

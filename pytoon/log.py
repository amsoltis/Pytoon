"""Structured JSON logging via structlog.

V2 enhancements (P5-12):
  - All pipeline events include: job_id, scene_id, engine_name, step, duration_ms, status, error.
  - Context binding for per-job/per-scene correlation.
  - No sensitive data (API keys) in production logs.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(json_output: bool = True):
    """Configure structlog for the whole process."""
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _sanitize_sensitive_data,
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_job_context(job_id: str, **extra) -> None:
    """Bind job-level context variables for all subsequent log calls."""
    structlog.contextvars.bind_contextvars(job_id=job_id, **extra)


def bind_scene_context(scene_id: int, engine_name: str = "", **extra) -> None:
    """Bind scene-level context for V2 pipeline logging."""
    structlog.contextvars.bind_contextvars(
        scene_id=scene_id,
        engine_name=engine_name,
        **extra,
    )


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()


# ---------------------------------------------------------------------------
# Sensitive data sanitization
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = {
    "api_key", "secret", "password", "token", "authorization",
    "xi-api-key", "x-api-key", "bearer",
}


def _sanitize_sensitive_data(logger, method_name, event_dict):
    """Remove sensitive data from log output."""
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in _SENSITIVE_KEYS):
            event_dict[key] = "***REDACTED***"
    return event_dict

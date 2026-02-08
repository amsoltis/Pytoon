"""Enhanced engine selection rules — per-preset prefs, user override, smart rotation.

Extends engine_manager.select_engine_for_scene with:
  - Per-preset engine preferences from config/engine.yaml.
  - User engine override (explicit request).
  - Smart rotation on high failure rate.
  - Engine capability matrix matching.

Ticket: P5-01
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Optional

from pytoon.config import get_engine_config
from pytoon.log import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Failure tracking for smart rotation
# ---------------------------------------------------------------------------

_failure_tracker: dict[str, list[float]] = defaultdict(list)
_success_tracker: dict[str, list[float]] = defaultdict(list)


def record_engine_result(engine_name: str, success: bool) -> None:
    """Record an engine attempt result for rotation tracking."""
    now = time.monotonic()
    if success:
        _success_tracker[engine_name].append(now)
    else:
        _failure_tracker[engine_name].append(now)


def get_failure_rate(engine_name: str, window_seconds: float = 300) -> float:
    """Get recent failure rate for an engine within a time window."""
    now = time.monotonic()
    cutoff = now - window_seconds

    fails = [t for t in _failure_tracker.get(engine_name, []) if t > cutoff]
    succs = [t for t in _success_tracker.get(engine_name, []) if t > cutoff]
    total = len(fails) + len(succs)

    if total == 0:
        return 0.0
    return len(fails) / total


def _should_rotate_away(engine_name: str) -> bool:
    """Check if an engine should be rotated out due to high failure rate."""
    cfg = get_engine_config().get("v2", {}).get("engine_rotation", {})
    if not cfg.get("enabled", False):
        return False

    threshold = cfg.get("failure_threshold", 0.5)
    window = cfg.get("window_seconds", 300)
    min_attempts = cfg.get("min_attempts", 3)

    now = time.monotonic()
    cutoff = now - window
    fails = [t for t in _failure_tracker.get(engine_name, []) if t > cutoff]
    succs = [t for t in _success_tracker.get(engine_name, []) if t > cutoff]
    total = len(fails) + len(succs)

    if total < min_attempts:
        return False

    rate = len(fails) / total
    if rate >= threshold:
        logger.warning(
            "engine_rotation_triggered",
            engine=engine_name,
            failure_rate=round(rate, 2),
            window_s=window,
        )
        return True
    return False


# ---------------------------------------------------------------------------
# Enhanced selection
# ---------------------------------------------------------------------------

def resolve_engine(
    *,
    scene_style_engine: str | None = None,
    user_override: str | None = None,
    preset_id: str | None = None,
    style_based_engine: str = "runway",
    capabilities_needed: list[str] | None = None,
) -> str:
    """Resolve the final engine choice with full priority chain.

    Priority:
    1. User explicit override (from API request).
    2. Scene-level explicit engine (from Scene Graph).
    3. Per-preset preferred engine (from config).
    4. Capability matrix match.
    5. Style-based selection (from engine_manager).
    6. Smart rotation override (skip if failing).
    """
    cfg = get_engine_config().get("v2", {})

    # Priority 1: User override
    if user_override:
        engine = user_override
    # Priority 2: Scene-level explicit
    elif scene_style_engine:
        engine = scene_style_engine
    # Priority 3: Per-preset preference
    elif preset_id:
        prefs = cfg.get("preset_engine_prefs", {}).get(preset_id, {})
        engine = prefs.get("preferred_engine", style_based_engine)
    # Priority 4: Capability match
    elif capabilities_needed:
        engine = _match_by_capabilities(capabilities_needed, cfg) or style_based_engine
    # Priority 5: Style-based
    else:
        engine = style_based_engine

    # Priority 6: Smart rotation
    if engine != "local" and _should_rotate_away(engine):
        alt = _find_healthy_alternative(engine, cfg)
        if alt:
            logger.info("engine_rotated", from_engine=engine, to_engine=alt)
            engine = alt

    return engine


def get_preset_fallback_chain(preset_id: str | None) -> list[str] | None:
    """Get the per-preset fallback chain override, or None for default."""
    if not preset_id:
        return None
    cfg = get_engine_config().get("v2", {})
    prefs = cfg.get("preset_engine_prefs", {}).get(preset_id, {})
    return prefs.get("fallback_override")


# ---------------------------------------------------------------------------
# Capability matrix
# ---------------------------------------------------------------------------

def _match_by_capabilities(
    needed: list[str],
    cfg: dict,
) -> str | None:
    """Find the best engine matching needed capabilities."""
    engines = cfg.get("engines", {})
    best_engine = None
    best_score = 0

    for name, ecfg in engines.items():
        if not ecfg.get("enabled", True):
            continue
        caps = set(ecfg.get("capabilities", []))
        score = len(caps.intersection(needed))
        if score > best_score:
            best_score = score
            best_engine = name

    return best_engine


def _find_healthy_alternative(excluded: str, cfg: dict) -> str | None:
    """Find an alternative engine that isn't failing."""
    chain = cfg.get("fallback_chain", ["runway", "pika", "luma"])
    for eng in chain:
        if eng != excluded and not _should_rotate_away(eng):
            return eng
    return None

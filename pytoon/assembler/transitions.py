"""Advanced V2 transitions — fade_black, swipe_left, swipe_right, zoom.

Extends the basic fade/cut transitions from Phase 2 with additional
FFmpeg xfade effects, configurable durations, and brand-safe restrictions.

Ticket: P5-03
"""

from __future__ import annotations

from dataclasses import dataclass

from pytoon.log import get_logger

logger = get_logger(__name__)


# FFmpeg xfade transition name mapping
TRANSITION_MAP: dict[str, str] = {
    "fade": "fade",
    "fade_black": "fadeblack",
    "cut": "fade",           # cuts use duration=0.001
    "swipe_left": "slideleft",
    "swipe_right": "slideright",
    "wipe_left": "wipeleft",
    "wipe_right": "wiperight",
    "zoom_in": "smoothup",
    "dissolve": "dissolve",
    "pixelize": "pixelize",
}

# Brand-safe allowed transitions
BRAND_SAFE_ALLOWED = {"fade", "cut", "fade_black"}

# Duration constraints
MIN_DURATION_S = 0.3
MAX_DURATION_S = 1.5
DEFAULT_DURATION_S = 0.5


@dataclass
class TransitionSpec:
    """Resolved transition specification for FFmpeg."""

    xfade_name: str        # FFmpeg xfade transition name
    duration_seconds: float
    is_cut: bool = False   # True for hard cuts


def resolve_transition(
    transition_type: str,
    duration_ms: int | None = None,
    *,
    brand_safe: bool = True,
    preset_default: str | None = None,
) -> TransitionSpec:
    """Resolve a transition type and duration into an FFmpeg xfade spec.

    Args:
        transition_type: User-requested transition type.
        duration_ms: Duration in milliseconds.
        brand_safe: If True, restrict to allowed types.
        preset_default: Default transition from preset.

    Returns:
        TransitionSpec ready for FFmpeg filter construction.
    """
    t_type = (transition_type or preset_default or "fade").lower()

    # Brand-safe restriction
    if brand_safe and t_type not in BRAND_SAFE_ALLOWED:
        logger.warning(
            "transition_brand_safe_downgrade",
            original=t_type,
            downgraded_to="fade",
        )
        t_type = "fade"

    # Resolve FFmpeg xfade name
    xfade_name = TRANSITION_MAP.get(t_type, "fade")

    # Handle cut
    is_cut = t_type == "cut"

    # Resolve duration
    if is_cut:
        dur_s = 0.001
    elif duration_ms is not None:
        dur_s = max(MIN_DURATION_S, min(MAX_DURATION_S, duration_ms / 1000.0))
    else:
        dur_s = DEFAULT_DURATION_S

    return TransitionSpec(
        xfade_name=xfade_name,
        duration_seconds=dur_s,
        is_cut=is_cut,
    )


def list_available_transitions(brand_safe: bool = False) -> list[str]:
    """List all available transition types."""
    if brand_safe:
        return sorted(BRAND_SAFE_ALLOWED)
    return sorted(TRANSITION_MAP.keys())

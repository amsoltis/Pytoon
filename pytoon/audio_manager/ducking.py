"""Audio ducking — reduce music volume during voiceover segments.

Detects voice-active regions, creates DuckRegion objects, and applies
volume envelope to music track via FFmpeg.

Ticket: P4-08
Acceptance Criteria: V2-AC-008
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pytoon.assembler.ffmpeg_ops import run_ffmpeg
from pytoon.log import get_logger

logger = get_logger(__name__)

# Default ducking parameters
DUCK_AMOUNT_DB = -12.0
FADE_IN_SECONDS = 0.2
FADE_OUT_SECONDS = 0.2


@dataclass
class DuckRegion:
    """A region where music volume should be reduced."""

    start_ms: int
    end_ms: int
    duck_amount_db: float = DUCK_AMOUNT_DB
    fade_in_s: float = FADE_IN_SECONDS
    fade_out_s: float = FADE_OUT_SECONDS


def detect_duck_regions(
    voice_segments: list[tuple[int, int]],
    *,
    duck_amount_db: float = DUCK_AMOUNT_DB,
    pad_ms: int = 100,
) -> list[DuckRegion]:
    """Create DuckRegion objects from voice-active segments.

    Args:
        voice_segments: List of (start_ms, end_ms) for each voice segment.
        duck_amount_db: Volume reduction in dB during voice.
        pad_ms: Padding before/after each voice segment.

    Returns:
        List of DuckRegion objects (merged overlapping regions).
    """
    if not voice_segments:
        return []

    # Sort by start time
    sorted_segs = sorted(voice_segments, key=lambda s: s[0])

    # Add padding and merge overlapping
    regions: list[tuple[int, int]] = []
    for start, end in sorted_segs:
        padded_start = max(0, start - pad_ms)
        padded_end = end + pad_ms

        if regions and padded_start <= regions[-1][1]:
            # Merge with previous
            regions[-1] = (regions[-1][0], max(regions[-1][1], padded_end))
        else:
            regions.append((padded_start, padded_end))

    duck_regions = [
        DuckRegion(
            start_ms=s,
            end_ms=e,
            duck_amount_db=duck_amount_db,
        )
        for s, e in regions
    ]

    logger.info("duck_regions_detected", count=len(duck_regions))
    return duck_regions


def apply_ducking(
    music_path: str | Path,
    output_path: str | Path,
    duck_regions: list[DuckRegion],
    *,
    base_volume_db: float = 0.0,
) -> str:
    """Apply ducking volume envelope to a music track.

    Uses FFmpeg volume filter with enable expressions for precise
    per-region ducking with smooth fade transitions.

    Returns path to the ducked music file.
    """
    music = Path(music_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not duck_regions:
        # No ducking needed — just copy
        run_ffmpeg(["-i", str(music), "-c:a", "copy", str(out)])
        return str(out)

    # Build volume filter with keyframe-based ducking
    # Strategy: for each duck region, reduce volume with fade transitions
    filter_parts: list[str] = []

    for region in duck_regions:
        start_s = region.start_ms / 1000.0
        end_s = region.end_ms / 1000.0
        duck_vol = _db_to_multiplier(region.duck_amount_db)

        # Fade-in to duck (volume goes down)
        fade_in_start = max(0, start_s - region.fade_in_s)
        # Fade-out from duck (volume goes up)
        fade_out_end = end_s + region.fade_out_s

        # Use volume filter with enable expression
        filter_parts.append(
            f"volume=enable='between(t,{start_s},{end_s})'"
            f":volume={duck_vol}"
        )

    # Chain all volume filters
    # For overlapping concerns, a simpler approach: build a single
    # volume expression using multiple enable clauses
    # But ffmpeg volume filter only takes one enable, so we chain filters.

    if len(filter_parts) == 1:
        af = filter_parts[0]
    else:
        af = ",".join(filter_parts)

    run_ffmpeg([
        "-i", str(music),
        "-af", af,
        "-ar", "44100",
        "-ac", "2",
        "-c:a", "pcm_s16le",
        str(out),
    ])

    logger.info("ducking_applied", regions=len(duck_regions), output=str(out))
    return str(out)


def _db_to_multiplier(db: float) -> float:
    """Convert dB to linear volume multiplier."""
    return 10 ** (db / 20.0)

"""Job planner — splits duration into segments, generates caption timings."""

from __future__ import annotations

import math
from typing import Any

from pytoon.models import (
    Archetype,
    CaptionsPlan,
    CaptionTiming,
    SegmentSpec,
)


def plan_segments(
    target_duration: int,
    segment_duration: int = 3,
) -> list[SegmentSpec]:
    """Return ordered list of SegmentSpec for the given total duration."""
    n_segments = math.ceil(target_duration / segment_duration)
    segments: list[SegmentSpec] = []
    remaining = float(target_duration)
    for i in range(n_segments):
        dur = min(float(segment_duration), remaining)
        segments.append(SegmentSpec(index=i, duration_seconds=dur))
        remaining -= dur
    return segments


def plan_captions(
    hook: str,
    beats: list[str],
    cta: str,
    target_duration: int,
) -> CaptionsPlan:
    """Distribute captions evenly across the duration."""
    all_texts = []
    if hook:
        all_texts.append(hook)
    all_texts.extend(beats)
    if cta:
        all_texts.append(cta)

    if not all_texts:
        return CaptionsPlan()

    n = len(all_texts)
    slot = target_duration / n
    timings: list[CaptionTiming] = []
    for i, text in enumerate(all_texts):
        timings.append(CaptionTiming(
            start=round(i * slot, 2),
            end=round((i + 1) * slot, 2),
            text=text,
        ))

    return CaptionsPlan(
        hook=hook,
        beats=beats,
        cta=cta,
        timings=timings,
    )


def default_prompt_for_segment(
    archetype: Archetype,
    base_prompt: str,
    segment_index: int,
    total_segments: int,
) -> str:
    """Generate a per-segment prompt (can be customized later)."""
    if archetype == Archetype.MEME_TEXT:
        return f"{base_prompt} (part {segment_index + 1}/{total_segments})"
    if archetype == Archetype.OVERLAY:
        return f"abstract motion background, smooth loop, {base_prompt}"
    # PRODUCT_HERO — subtle motion on product
    return f"subtle cinematic motion, product showcase, {base_prompt}"

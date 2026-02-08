"""Voice-to-scene mapping — assign transcript sentences to scenes.

Splits the transcript, distributes sentences across scenes in order,
estimates per-sentence duration, and updates Timeline audio tracks.

Ticket: P4-03
Acceptance Criteria: V2-AC-002, V2-AC-005
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from pytoon.log import get_logger

logger = get_logger(__name__)

# Sentence-ending pattern
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Average speech rate: ~2.5 words per second
_WORDS_PER_SECOND = 2.5


@dataclass
class VoiceSegment:
    """A voice segment mapped to a scene."""

    scene_id: int
    text: str
    estimated_duration_ms: int
    start_ms: int = 0
    end_ms: int = 0


@dataclass
class VoiceMappingResult:
    """Result of voice-to-scene mapping."""

    segments: list[VoiceSegment] = field(default_factory=list)
    total_voice_duration_ms: int = 0
    scenes_without_voice: list[int] = field(default_factory=list)


def map_voice_to_scenes(
    transcript: str,
    scene_ids: list[int],
    scene_durations_ms: list[int],
    *,
    voice_duration_ms: int | None = None,
) -> VoiceMappingResult:
    """Map transcript sentences to scenes in order.

    Rules:
    - More sentences than scenes → combine multiple sentences per scene.
    - More scenes than sentences → some scenes get no voice.
    - Duration is estimated from word count or proportionally from voice file.
    """
    sentences = _split_sentences(transcript)
    if not sentences:
        return VoiceMappingResult(scenes_without_voice=list(scene_ids))

    n_scenes = len(scene_ids)
    n_sentences = len(sentences)

    # Assign sentences to scenes
    assignments: dict[int, list[str]] = {sid: [] for sid in scene_ids}

    if n_sentences <= n_scenes:
        # One sentence per scene (some scenes get nothing)
        for i, sentence in enumerate(sentences):
            assignments[scene_ids[i]].append(sentence)
    else:
        # Distribute sentences across scenes as evenly as possible
        per_scene = n_sentences / n_scenes
        idx = 0.0
        for i, sid in enumerate(scene_ids):
            next_idx = idx + per_scene
            start = int(idx)
            end = int(next_idx) if i < n_scenes - 1 else n_sentences
            for j in range(start, end):
                assignments[sid].append(sentences[j])
            idx = next_idx

    # Build segments with duration estimation
    segments: list[VoiceSegment] = []
    scenes_without_voice: list[int] = []

    # Estimate durations
    total_words = sum(len(s.split()) for s in sentences)
    cursor = 0

    for i, sid in enumerate(scene_ids):
        texts = assignments[sid]
        if not texts:
            scenes_without_voice.append(sid)
            continue

        combined = " ".join(texts)
        word_count = len(combined.split())

        if voice_duration_ms and total_words > 0:
            # Proportional from actual voice duration
            ratio = word_count / total_words
            est_duration = int(voice_duration_ms * ratio)
        else:
            # Estimate from word count
            est_duration = int((word_count / _WORDS_PER_SECOND) * 1000)

        # Clamp to scene duration
        scene_dur = scene_durations_ms[i] if i < len(scene_durations_ms) else 5000
        est_duration = min(est_duration, scene_dur)
        est_duration = max(est_duration, 500)  # minimum 500ms

        segment = VoiceSegment(
            scene_id=sid,
            text=combined,
            estimated_duration_ms=est_duration,
            start_ms=cursor,
            end_ms=cursor + est_duration,
        )
        segments.append(segment)
        cursor += est_duration

    total_voice = sum(s.estimated_duration_ms for s in segments)

    logger.info(
        "voice_mapped",
        sentences=len(sentences),
        scenes=len(scene_ids),
        segments=len(segments),
        total_voice_ms=total_voice,
    )

    return VoiceMappingResult(
        segments=segments,
        total_voice_duration_ms=total_voice,
        scenes_without_voice=scenes_without_voice,
    )


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    if not text:
        return []
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]

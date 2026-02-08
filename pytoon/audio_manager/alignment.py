"""Forced alignment — sync captions to voiceover within ±100ms.

Uses WhisperX / stable-ts for word-level timestamps when available,
falls back to even-time sentence splitting.

Ticket: P4-04
Acceptance Criteria: V2-AC-002, V2-AC-004
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pytoon.log import get_logger

logger = get_logger(__name__)

# Sentence splitter
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class AlignedCaption:
    """A caption with precise timing from forced alignment."""

    text: str
    start_ms: int
    end_ms: int
    scene_id: Optional[int] = None
    confidence: float = 1.0


@dataclass
class AlignmentResult:
    """Result of forced alignment."""

    captions: list[AlignedCaption] = field(default_factory=list)
    method: str = "unknown"  # "whisperx" | "stable_ts" | "even_split"
    accuracy_ms: Optional[float] = None


def align_captions(
    audio_path: str | Path,
    transcript: str,
    scene_boundaries: list[tuple[int, int, int]],
    *,
    target_accuracy_ms: float = 100.0,
) -> AlignmentResult:
    """Produce time-aligned captions from audio + transcript.

    Args:
        audio_path: Path to the voiceover audio file.
        transcript: Full transcript text.
        scene_boundaries: List of (scene_id, start_ms, end_ms) tuples.
        target_accuracy_ms: Target sync accuracy.

    Returns:
        AlignmentResult with list of AlignedCaption objects.

    Tries in order:
    1. WhisperX (word-level, best accuracy).
    2. stable-ts (sentence-level).
    3. Even-time splitting (fallback).
    """
    audio = Path(audio_path)
    if not audio.exists():
        logger.warning("alignment_no_audio", path=str(audio))
        return _even_time_split(transcript, scene_boundaries)

    # Try WhisperX
    result = _try_whisperx(audio, transcript, scene_boundaries)
    if result is not None:
        return result

    # Try stable-ts
    result = _try_stable_ts(audio, transcript, scene_boundaries)
    if result is not None:
        return result

    # Fallback: even-time split
    logger.warning("alignment_fallback_to_even_split")
    return _even_time_split(transcript, scene_boundaries)


# ---------------------------------------------------------------------------
# WhisperX alignment
# ---------------------------------------------------------------------------

def _try_whisperx(
    audio: Path,
    transcript: str,
    scene_boundaries: list[tuple[int, int, int]],
) -> AlignmentResult | None:
    """Attempt alignment using WhisperX."""
    try:
        import whisperx
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = whisperx.load_model("base", device=device, compute_type="int8")

        # Transcribe with word timestamps
        audio_data = whisperx.load_audio(str(audio))
        result = model.transcribe(audio_data)

        # Align
        model_a, metadata = whisperx.load_align_model(
            language_code="en", device=device,
        )
        aligned = whisperx.align(
            result["segments"], model_a, metadata, audio_data, device,
        )

        # Convert to AlignedCaption objects grouped by sentence
        captions = _whisperx_segments_to_captions(
            aligned.get("segments", []),
            scene_boundaries,
        )

        if captions:
            logger.info("alignment_whisperx_success", captions=len(captions))
            return AlignmentResult(
                captions=captions,
                method="whisperx",
                accuracy_ms=50.0,  # WhisperX typically ±50ms
            )

    except ImportError:
        pass
    except Exception as exc:
        logger.warning("whisperx_failed", error=str(exc))

    return None


def _whisperx_segments_to_captions(
    segments: list[dict],
    scene_boundaries: list[tuple[int, int, int]],
) -> list[AlignedCaption]:
    """Convert WhisperX segments to AlignedCaption objects."""
    captions: list[AlignedCaption] = []

    for seg in segments:
        start_ms = int(seg.get("start", 0) * 1000)
        end_ms = int(seg.get("end", 0) * 1000)
        text = seg.get("text", "").strip()

        if not text:
            continue

        # Find owning scene
        scene_id = _find_scene(start_ms, scene_boundaries)

        captions.append(AlignedCaption(
            text=text,
            start_ms=start_ms,
            end_ms=end_ms,
            scene_id=scene_id,
            confidence=0.9,
        ))

    return captions


# ---------------------------------------------------------------------------
# stable-ts alignment
# ---------------------------------------------------------------------------

def _try_stable_ts(
    audio: Path,
    transcript: str,
    scene_boundaries: list[tuple[int, int, int]],
) -> AlignmentResult | None:
    """Attempt alignment using stable-ts."""
    try:
        import stable_whisper

        model = stable_whisper.load_model("base")
        result = model.align(str(audio), transcript)

        captions: list[AlignedCaption] = []
        for segment in result.segments:
            start_ms = int(segment.start * 1000)
            end_ms = int(segment.end * 1000)
            text = segment.text.strip()
            if text:
                scene_id = _find_scene(start_ms, scene_boundaries)
                captions.append(AlignedCaption(
                    text=text,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    scene_id=scene_id,
                    confidence=0.85,
                ))

        if captions:
            logger.info("alignment_stable_ts_success", captions=len(captions))
            return AlignmentResult(
                captions=captions,
                method="stable_ts",
                accuracy_ms=80.0,
            )

    except ImportError:
        pass
    except Exception as exc:
        logger.warning("stable_ts_failed", error=str(exc))

    return None


# ---------------------------------------------------------------------------
# Even-time fallback
# ---------------------------------------------------------------------------

def _even_time_split(
    transcript: str,
    scene_boundaries: list[tuple[int, int, int]],
) -> AlignmentResult:
    """Fallback: split transcript evenly across scene durations."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(transcript) if s.strip()]
    if not sentences:
        sentences = [transcript.strip()] if transcript.strip() else []

    if not sentences or not scene_boundaries:
        return AlignmentResult(captions=[], method="even_split")

    captions: list[AlignedCaption] = []

    # Distribute sentences across scenes
    n_scenes = len(scene_boundaries)
    n_sentences = len(sentences)

    if n_sentences <= n_scenes:
        # One sentence per scene
        for i, sentence in enumerate(sentences):
            if i < n_scenes:
                scene_id, s_start, s_end = scene_boundaries[i]
                # Pad slightly within scene bounds
                cap_start = s_start + 200
                cap_end = s_end - 200
                if cap_end <= cap_start:
                    cap_start = s_start
                    cap_end = s_end
                captions.append(AlignedCaption(
                    text=sentence,
                    start_ms=cap_start,
                    end_ms=cap_end,
                    scene_id=scene_id,
                    confidence=0.5,
                ))
    else:
        # Multiple sentences per scene — split evenly within each scene
        per_scene = n_sentences / n_scenes
        idx = 0.0
        for scene_id, s_start, s_end in scene_boundaries:
            next_idx = idx + per_scene
            start_i = int(idx)
            end_i = min(int(next_idx), n_sentences)

            scene_sentences = sentences[start_i:end_i]
            if not scene_sentences:
                idx = next_idx
                continue

            scene_duration = s_end - s_start
            per_sentence = scene_duration / len(scene_sentences)

            for j, sentence in enumerate(scene_sentences):
                cap_start = int(s_start + j * per_sentence) + 100
                cap_end = int(s_start + (j + 1) * per_sentence) - 100
                if cap_end <= cap_start:
                    cap_end = cap_start + 500
                captions.append(AlignedCaption(
                    text=sentence,
                    start_ms=cap_start,
                    end_ms=cap_end,
                    scene_id=scene_id,
                    confidence=0.5,
                ))

            idx = next_idx

    logger.info("alignment_even_split", captions=len(captions))
    return AlignmentResult(captions=captions, method="even_split", accuracy_ms=None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_scene(
    time_ms: int,
    scene_boundaries: list[tuple[int, int, int]],
) -> int | None:
    """Find which scene a timestamp falls into."""
    for scene_id, start, end in scene_boundaries:
        if start <= time_ms <= end:
            return scene_id
    # If not found, return the closest scene
    if scene_boundaries:
        return scene_boundaries[-1][0]
    return None

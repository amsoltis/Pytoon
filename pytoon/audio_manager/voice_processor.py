"""Voiceover ingestion and processing.

Validates, resamples, trims silence, measures duration, and optionally
transcribes user-provided audio files.

Ticket: P4-02
Acceptance Criteria: V2-AC-002, V2-AC-003
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pytoon.assembler.ffmpeg_ops import run_ffmpeg, run_ffprobe
from pytoon.log import get_logger

logger = get_logger(__name__)

# Accepted audio formats
ACCEPTED_FORMATS = {"wav", "mp3", "aac", "m4a", "ogg", "flac"}

# Silence threshold for trimming (dBFS)
SILENCE_THRESHOLD_DB = -40

# Target sample rate
TARGET_SAMPLE_RATE = 44100


@dataclass
class VoiceProcessResult:
    """Result of voice processing."""

    success: bool
    audio_path: Optional[str] = None
    duration_ms: Optional[int] = None
    transcript: Optional[str] = None
    error: Optional[str] = None


def process_voice(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    script: str | None = None,
    max_duration_ms: int | None = None,
    trim_silence: bool = True,
) -> VoiceProcessResult:
    """Process a voiceover file for use in the video pipeline.

    Steps:
    1. Validate format.
    2. Resample to 44.1kHz stereo.
    3. Trim leading/trailing silence.
    4. Measure duration.
    5. Handle overlong audio.
    6. Transcribe if no script provided (ASR).
    """
    inp = Path(input_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Validate
    if not inp.exists():
        return VoiceProcessResult(success=False, error=f"File not found: {inp}")

    ext = inp.suffix.lstrip(".").lower()
    if ext not in ACCEPTED_FORMATS:
        return VoiceProcessResult(
            success=False,
            error=f"Unsupported format: {ext}. Accepted: {', '.join(ACCEPTED_FORMATS)}",
        )

    # 2 & 3. Resample + trim silence
    processed_path = out_dir / "voiceover_processed.wav"

    filters = [f"aresample={TARGET_SAMPLE_RATE}"]
    if trim_silence:
        # silenceremove: strip leading silence, then reverse + strip trailing
        filters.append(
            f"silenceremove=start_periods=1:start_silence=0.1"
            f":start_threshold={SILENCE_THRESHOLD_DB}dB,"
            f"areverse,"
            f"silenceremove=start_periods=1:start_silence=0.1"
            f":start_threshold={SILENCE_THRESHOLD_DB}dB,"
            f"areverse"
        )

    af = ",".join(filters)

    try:
        run_ffmpeg([
            "-i", str(inp),
            "-af", af,
            "-ac", "2",  # stereo
            "-ar", str(TARGET_SAMPLE_RATE),
            "-c:a", "pcm_s16le",
            str(processed_path),
        ])
    except Exception as exc:
        return VoiceProcessResult(success=False, error=f"FFmpeg processing failed: {exc}")

    if not processed_path.exists() or processed_path.stat().st_size == 0:
        return VoiceProcessResult(success=False, error="Processing produced empty output")

    # 4. Measure duration
    duration_ms = _measure_duration_ms(processed_path)

    # 5. Handle overlong audio
    if max_duration_ms and duration_ms and duration_ms > max_duration_ms:
        trimmed_path = out_dir / "voiceover_trimmed.wav"
        trim_s = max_duration_ms / 1000.0
        # Trim with 0.5s fade-out
        fade_start = max(0, trim_s - 0.5)
        run_ffmpeg([
            "-i", str(processed_path),
            "-t", str(trim_s),
            "-af", f"afade=t=out:st={fade_start}:d=0.5",
            "-c:a", "pcm_s16le",
            str(trimmed_path),
        ])
        if trimmed_path.exists():
            processed_path = trimmed_path
            duration_ms = max_duration_ms
            logger.warning(
                "voiceover_trimmed",
                original_ms=duration_ms,
                trimmed_to_ms=max_duration_ms,
            )

    # 6. Transcribe if no script
    transcript = script
    if not transcript:
        transcript = _transcribe_audio(processed_path)

    logger.info(
        "voice_processed",
        duration_ms=duration_ms,
        has_transcript=bool(transcript),
    )

    return VoiceProcessResult(
        success=True,
        audio_path=str(processed_path),
        duration_ms=duration_ms,
        transcript=transcript,
    )


def _measure_duration_ms(path: Path) -> int | None:
    """Get audio duration in milliseconds."""
    try:
        out = run_ffprobe([
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ])
        return int(float(out.strip()) * 1000)
    except Exception:
        return None


def _transcribe_audio(path: Path) -> str | None:
    """Attempt ASR transcription using Whisper or similar.

    Falls back to None if transcription tools aren't available.
    """
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(str(path))
        return result.get("text", "")
    except ImportError:
        pass

    # Fallback: try faster-whisper
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", compute_type="int8")
        segments, _ = model.transcribe(str(path))
        return " ".join(s.text for s in segments)
    except ImportError:
        pass

    logger.warning("asr_unavailable", note="No Whisper installation found")
    return None

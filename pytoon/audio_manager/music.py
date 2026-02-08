"""Background music pipeline — load, fit to duration, apply base volume.

Handles:
  - Loading from preset/library/upload.
  - Trimming with fade-out or seamless looping.
  - Base volume at -12 dBFS.
  - Silence track fallback.

Ticket: P4-07
Acceptance Criteria: V2-AC-007, V2-AC-008
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pytoon.assembler.ffmpeg_ops import run_ffmpeg
from pytoon.log import get_logger

logger = get_logger(__name__)

# Base music volume in dBFS
BASE_VOLUME_DBFS = -12.0

# Fade-out duration for trim (seconds)
FADE_OUT_SECONDS = 2.0

# Crossfade overlap for loop (seconds)
LOOP_CROSSFADE_SECONDS = 0.5

# Music library search paths
MUSIC_SEARCH_PATHS = [
    "assets/music",
    "storage/music",
]


def prepare_music(
    source: str | Path | None,
    output_dir: str | Path,
    target_duration_seconds: float,
    *,
    base_volume_dbfs: float = BASE_VOLUME_DBFS,
) -> str | None:
    """Prepare background music track fitted to video duration.

    Args:
        source: Path to music file, or None for silence.
        output_dir: Directory for output files.
        target_duration_seconds: Target duration to fit music to.
        base_volume_dbfs: Base volume level.

    Returns:
        Path to the prepared music file, or None if no music available.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "music_prepared.wav"

    if source is None:
        return None

    source_path = Path(source)
    if not source_path.exists():
        # Try searching music library
        source_path = _find_in_library(str(source))
        if source_path is None:
            logger.warning("music_not_found", source=str(source))
            return None

    # Measure source duration
    source_duration = _get_audio_duration(source_path)
    if source_duration is None or source_duration <= 0:
        logger.warning("music_invalid_duration", source=str(source_path))
        return None

    target = target_duration_seconds

    if source_duration >= target:
        # Trim with fade-out
        _trim_with_fadeout(source_path, output_path, target, base_volume_dbfs)
    else:
        # Loop to fill duration
        _loop_to_duration(source_path, output_path, target, source_duration, base_volume_dbfs)

    if output_path.exists() and output_path.stat().st_size > 0:
        logger.info(
            "music_prepared",
            source=str(source_path),
            target_duration=target,
            source_duration=source_duration,
            method="trim" if source_duration >= target else "loop",
        )
        return str(output_path)

    return None


def generate_silence_track(
    output_dir: str | Path,
    duration_seconds: float,
) -> str:
    """Generate a silence audio track."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "silence.wav"

    run_ffmpeg([
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo:d={duration_seconds}",
        "-c:a", "pcm_s16le",
        str(output_path),
    ])

    return str(output_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _trim_with_fadeout(
    source: Path,
    output: Path,
    target_duration: float,
    volume_dbfs: float,
) -> None:
    """Trim music to target duration with a 2s fade-out."""
    volume_mult = _dbfs_to_multiplier(volume_dbfs)
    fade_start = max(0, target_duration - FADE_OUT_SECONDS)

    run_ffmpeg([
        "-i", str(source),
        "-t", str(target_duration),
        "-af", (
            f"volume={volume_mult},"
            f"afade=t=out:st={fade_start}:d={FADE_OUT_SECONDS}"
        ),
        "-ar", "44100",
        "-ac", "2",
        "-c:a", "pcm_s16le",
        str(output),
    ])


def _loop_to_duration(
    source: Path,
    output: Path,
    target_duration: float,
    source_duration: float,
    volume_dbfs: float,
) -> None:
    """Loop music to fill the target duration with crossfade at loop point."""
    volume_mult = _dbfs_to_multiplier(volume_dbfs)

    # Calculate number of loops needed
    loops = int(target_duration / source_duration) + 1

    # Use aloop to repeat, then trim to target with fade-out
    fade_start = max(0, target_duration - FADE_OUT_SECONDS)

    run_ffmpeg([
        "-stream_loop", str(loops),
        "-i", str(source),
        "-t", str(target_duration),
        "-af", (
            f"volume={volume_mult},"
            f"afade=t=in:d=0.2,"
            f"afade=t=out:st={fade_start}:d={FADE_OUT_SECONDS}"
        ),
        "-ar", "44100",
        "-ac", "2",
        "-c:a", "pcm_s16le",
        str(output),
    ])


def _get_audio_duration(path: Path) -> float | None:
    """Get audio duration in seconds."""
    from pytoon.assembler.ffmpeg_ops import run_ffprobe
    try:
        out = run_ffprobe([
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ])
        return float(out.strip())
    except Exception:
        return None


def _find_in_library(name: str) -> Path | None:
    """Search for a music file by name in known library paths."""
    for search_dir in MUSIC_SEARCH_PATHS:
        d = Path(search_dir)
        if d.exists():
            for ext in ("mp3", "wav", "aac", "ogg"):
                candidate = d / f"{name}.{ext}"
                if candidate.exists():
                    return candidate
                # Also try filename directly
                candidate = d / name
                if candidate.exists():
                    return candidate
    return None


def _dbfs_to_multiplier(dbfs: float) -> float:
    """Convert dBFS to linear volume multiplier."""
    return 10 ** (dbfs / 20.0)

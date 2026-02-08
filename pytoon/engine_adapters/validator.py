"""Engine response validation — verifies AI-generated clips meet quality requirements.

Validates:
  - File exists and is non-empty
  - Valid MP4 container via ffprobe
  - Duration within ±20% of expected
  - Resolution ≥ 720p
  - Not corrupt (has video stream)

Ticket: P3-08
Acceptance Criteria: V2-AC-011, V2-AC-013
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pytoon.log import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of validating an engine-generated clip."""

    valid: bool
    errors: list[str]
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    codec: Optional[str] = None
    file_size_bytes: Optional[int] = None


def validate_clip(
    clip_path: str | Path,
    expected_duration_seconds: float,
    *,
    min_width: int = 720,
    min_height: int = 1280,
    duration_tolerance: float = 0.2,
    max_file_size_mb: float = 200,
) -> ValidationResult:
    """Validate an AI-generated video clip.

    Args:
        clip_path: Path to the clip file.
        expected_duration_seconds: Expected duration in seconds.
        min_width: Minimum acceptable width (default 720).
        min_height: Minimum acceptable height (default 1280).
        duration_tolerance: Acceptable deviation as fraction (0.2 = ±20%).
        max_file_size_mb: Maximum file size in MB.

    Returns:
        ValidationResult with valid=True if all checks pass.
    """
    clip = Path(clip_path)
    errors: list[str] = []

    # --- Check 1: File exists and is non-empty --------------------------------
    if not clip.exists():
        return ValidationResult(valid=False, errors=["File does not exist"])

    file_size = clip.stat().st_size
    if file_size == 0:
        return ValidationResult(valid=False, errors=["File is empty (0 bytes)"])

    if file_size > max_file_size_mb * 1024 * 1024:
        errors.append(f"File too large: {file_size / 1024 / 1024:.1f}MB > {max_file_size_mb}MB")

    # --- Check 2: Valid video via ffprobe -------------------------------------
    probe = _probe_video(clip)
    if probe is None:
        return ValidationResult(
            valid=False,
            errors=["ffprobe failed — file may be corrupt or not a valid video"],
            file_size_bytes=file_size,
        )

    # --- Check 3: Has a video stream -----------------------------------------
    video_stream = _find_video_stream(probe)
    if video_stream is None:
        return ValidationResult(
            valid=False,
            errors=["No video stream found in file"],
            file_size_bytes=file_size,
        )

    # Extract metadata
    width = video_stream.get("width")
    height = video_stream.get("height")
    codec = video_stream.get("codec_name")

    # Duration from format (more reliable than stream)
    format_info = probe.get("format", {})
    duration_str = format_info.get("duration")
    duration = float(duration_str) if duration_str else None

    result = ValidationResult(
        valid=True,
        errors=[],
        duration_seconds=duration,
        width=width,
        height=height,
        codec=codec,
        file_size_bytes=file_size,
    )

    # --- Check 4: Duration within tolerance -----------------------------------
    if duration is not None and expected_duration_seconds > 0:
        min_dur = expected_duration_seconds * (1 - duration_tolerance)
        max_dur = expected_duration_seconds * (1 + duration_tolerance)
        if duration < min_dur or duration > max_dur:
            errors.append(
                f"Duration {duration:.1f}s outside ±{int(duration_tolerance * 100)}% "
                f"of expected {expected_duration_seconds:.1f}s "
                f"(acceptable: {min_dur:.1f}–{max_dur:.1f}s)"
            )

    # --- Check 5: Resolution check --------------------------------------------
    if width is not None and height is not None:
        if width < min_width or height < min_height:
            errors.append(
                f"Resolution {width}x{height} below minimum {min_width}x{min_height}"
            )

    if errors:
        result.valid = False
        result.errors = errors

    logger.info(
        "clip_validation",
        path=str(clip),
        valid=result.valid,
        duration=result.duration_seconds,
        resolution=f"{result.width}x{result.height}" if result.width else "unknown",
        errors=result.errors if result.errors else None,
    )

    return result


# ---------------------------------------------------------------------------
# ffprobe helpers
# ---------------------------------------------------------------------------

def _probe_video(path: Path) -> dict | None:
    """Run ffprobe and return parsed JSON output."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            logger.warning("ffprobe_failed", path=str(path), stderr=result.stderr[:200])
            return None
        return json.loads(result.stdout)
    except Exception as exc:
        logger.warning("ffprobe_error", path=str(path), error=str(exc))
        return None


def _find_video_stream(probe: dict) -> dict | None:
    """Find the first video stream in ffprobe output."""
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    return None

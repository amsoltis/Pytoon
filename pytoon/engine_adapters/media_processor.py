"""Scene media integration — process AI-generated clips for timeline composition.

Post-processes engine output clips:
  - Scale/crop to 1080x1920 (no aspect ratio distortion).
  - Trim or extend to exact scene duration.
  - Store processed clips.
  - Update Timeline video tracks with actual paths.

Ticket: P3-10
Acceptance Criteria: V2-AC-006, V2-AC-013
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pytoon.assembler.ffmpeg_ops import run_ffmpeg, run_ffprobe
from pytoon.log import get_logger

logger = get_logger(__name__)


def process_clip(
    input_path: str | Path,
    output_path: str | Path,
    *,
    target_duration_seconds: float,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> Path:
    """Process an engine-generated clip to match timeline requirements.

    Steps:
    1. Detect input resolution and duration.
    2. Scale to fill target resolution (no black bars, center-crop if needed).
    3. Trim or extend (freeze-frame) to exact target duration.
    4. Normalize framerate and pixel format.

    Returns the path to the processed clip.
    """
    inp = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Detect input properties
    input_dur = _get_duration(inp)
    input_w, input_h = _get_resolution(inp)

    logger.info(
        "processing_clip",
        input=str(inp),
        input_dur=input_dur,
        input_res=f"{input_w}x{input_h}",
        target_dur=target_duration_seconds,
        target_res=f"{width}x{height}",
    )

    # Build filter chain
    filters: list[str] = []

    # Step 1: Scale to fill (no black bars) — scale so the smallest dimension
    # matches, then center-crop to exact target size
    filters.append(
        f"scale={width}:{height}:force_original_aspect_ratio=increase"
    )
    filters.append(f"crop={width}:{height}")

    # Step 2: Normalize framerate and pixel format
    filters.append(f"fps={fps}")
    filters.append("format=yuv420p")

    vf = ",".join(filters)

    # Step 3: Handle duration mismatch
    if input_dur is not None and input_dur > 0:
        if input_dur >= target_duration_seconds:
            # Trim to target duration
            run_ffmpeg([
                "-i", str(inp),
                "-t", str(target_duration_seconds),
                "-vf", vf,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-an",  # Strip audio (audio handled separately in V2)
                str(out),
            ])
        else:
            # Extend with freeze-frame of last frame
            _extend_with_freeze(inp, out, input_dur, target_duration_seconds,
                                vf, width, height, fps)
    else:
        # Unknown duration — just process and trim
        run_ffmpeg([
            "-i", str(inp),
            "-t", str(target_duration_seconds),
            "-vf", vf,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-an",
            str(out),
        ])

    logger.info("clip_processed", output=str(out))
    return out


def process_all_clips(
    scene_clips: dict[int, str],
    output_dir: str | Path,
    scene_durations: dict[int, float],
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> dict[int, Path]:
    """Process all scene clips, returning {scene_id: processed_clip_path}.

    Args:
        scene_clips: {scene_id: raw_clip_path}
        output_dir: Directory for processed output.
        scene_durations: {scene_id: duration_seconds}
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    processed: dict[int, Path] = {}
    for scene_id, raw_path in scene_clips.items():
        duration = scene_durations.get(scene_id, 5.0)
        out_path = out_dir / f"scene_{scene_id}_processed.mp4"

        try:
            processed[scene_id] = process_clip(
                raw_path,
                out_path,
                target_duration_seconds=duration,
                width=width,
                height=height,
                fps=fps,
            )
        except Exception as exc:
            logger.error(
                "clip_processing_failed",
                scene_id=scene_id,
                error=str(exc),
            )
            # Use raw clip as fallback
            processed[scene_id] = Path(raw_path)

    return processed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_duration(path: Path) -> Optional[float]:
    """Get video duration in seconds."""
    try:
        out = run_ffprobe([
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ])
        return float(out.strip())
    except (ValueError, AttributeError):
        return None


def _get_resolution(path: Path) -> tuple[int, int]:
    """Get video resolution (width, height)."""
    try:
        out = run_ffprobe([
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            str(path),
        ])
        parts = out.strip().split("x")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except (ValueError, AttributeError):
        pass
    return 0, 0


def _extend_with_freeze(
    input_path: Path,
    output_path: Path,
    input_dur: float,
    target_dur: float,
    vf: str,
    width: int,
    height: int,
    fps: int,
) -> None:
    """Extend a clip by freeze-framing the last frame."""
    # Strategy: use tpad to pad the end with the last frame
    tpad_dur = target_dur - input_dur
    freeze_vf = f"{vf},tpad=stop_mode=clone:stop_duration={tpad_dur}"

    run_ffmpeg([
        "-i", str(input_path),
        "-vf", freeze_vf,
        "-t", str(target_dur),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ])

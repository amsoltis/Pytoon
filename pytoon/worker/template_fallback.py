"""Template fallback — generate a static-template video when all engines fail."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from pytoon.config import get_defaults
from pytoon.log import get_logger
from pytoon.storage import get_storage

logger = get_logger(__name__)


def generate_template_video(
    job_id: str,
    duration_seconds: int,
    text: str = "Video rendering in progress...",
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> str:
    """Create a simple colour-background video with text as a last-resort fallback.

    Returns the storage URI of the generated mp4.
    """
    storage = get_storage()
    out_key = f"jobs/{job_id}/fallback_template.mp4"
    out_path = storage.local_path(out_key)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build ffmpeg command for a static-colour video with burned text
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x1a1a2e:s={width}x{height}:d={duration_seconds}:r={fps}",
        "-vf", (
            f"drawtext=text='{_escape(text)}':"
            f"fontsize=48:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"font=Arial"
        ),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        "-t", str(duration_seconds),
        str(out_path),
    ]

    logger.info("template_fallback_start", job_id=job_id, duration=duration_seconds)

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.error("template_fallback_ffmpeg_error", error=str(exc))
        # Create a zero-byte file so the job isn't stuck
        out_path.write_bytes(b"")

    uri = storage.uri(out_key)
    logger.info("template_fallback_done", job_id=job_id, uri=uri)
    return uri


def _escape(text: str) -> str:
    """Escape special characters for ffmpeg drawtext filter."""
    return text.replace("'", "'\\''").replace(":", "\\:").replace("\\", "\\\\")

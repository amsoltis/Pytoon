"""Stub scene renderer — produces placeholder clips for Phase-2 testing.

For image-type scenes: generates a video from the static image with Ken Burns
pan/zoom via FFmpeg.
For video-type scenes: generates a solid-color clip at 1080x1920 with the
scene description overlaid as text.

Ticket: P2-05
Acceptance Criteria: V2-AC-013
"""

from __future__ import annotations

from pathlib import Path

from pytoon.assembler.ffmpeg_ops import run_ffmpeg
from pytoon.log import get_logger
from pytoon.scene_graph.models import MediaType, Scene

logger = get_logger(__name__)

# Output resolution
WIDTH = 1080
HEIGHT = 1920
FPS = 30


def render_scene_stub(
    scene: Scene,
    output_dir: Path,
    *,
    width: int = WIDTH,
    height: int = HEIGHT,
    fps: int = FPS,
) -> Path:
    """Render a single placeholder scene clip.

    Returns the path to the generated MP4 clip.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"scene_{scene.id}.mp4"
    duration_sec = scene.duration / 1000.0

    if scene.media.type == MediaType.IMAGE and scene.media.asset:
        _render_image_scene(scene, output_path, duration_sec, width, height, fps)
    else:
        _render_placeholder_scene(scene, output_path, duration_sec, width, height, fps)

    logger.info(
        "stub_scene_rendered",
        scene_id=scene.id,
        media_type=scene.media.type.value,
        duration_sec=duration_sec,
        output=str(output_path),
    )
    return output_path


def _render_image_scene(
    scene: Scene,
    output_path: Path,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
) -> None:
    """Render an image-based scene with Ken Burns zoom effect."""
    image_path = scene.media.asset
    # Ken Burns: slow zoom from 100% to 120% over duration
    # scale image up, then crop to output size with panning
    vf = (
        f"scale=-2:{int(height * 1.3)},"
        f"zoompan=z='min(zoom+0.0005,1.2)':d={int(duration_sec * fps)}"
        f":s={width}x{height}:fps={fps},"
        f"format=yuv420p"
    )
    run_ffmpeg([
        "-loop", "1",
        "-i", str(image_path),
        "-vf", vf,
        "-t", str(duration_sec),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        str(output_path),
    ])


def _render_placeholder_scene(
    scene: Scene,
    output_path: Path,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
) -> None:
    """Render a solid-color placeholder with scene description text."""
    # Use a dark teal background
    color = "0x1a3a4a"
    # Escape text for FFmpeg drawtext
    text = scene.description[:80].replace("'", "'\\''").replace(":", "\\:")
    scene_label = f"Scene {scene.id}"

    vf = (
        f"drawtext=text='{scene_label}':"
        f"fontsize=64:fontcolor=white:"
        f"x=(w-text_w)/2:y=(h/2)-80:"
        f"font=Arial,"
        f"drawtext=text='{text}':"
        f"fontsize=36:fontcolor=white@0.8:"
        f"x=(w-text_w)/2:y=(h/2)+20:"
        f"font=Arial"
    )

    run_ffmpeg([
        "-f", "lavfi",
        "-i", f"color=c={color}:s={width}x{height}:d={duration_sec}:r={fps}",
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-t", str(duration_sec),
        str(output_path),
    ])

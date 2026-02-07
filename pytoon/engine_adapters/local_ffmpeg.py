"""Local FFmpeg composition engine — creates video segments from images + text.

This engine does NOT require any AI model or external service. It uses pure
ffmpeg to compose video segments from static images with motion effects:

  PRODUCT_HERO  → Ken Burns zoom/pan on the product image (full frame)
  OVERLAY       → Blurred/dark background + centered product overlay
  MEME_TEXT     → Full-frame image (letterboxed if needed for text bars)
"""

from __future__ import annotations

import random
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from pytoon.config import get_defaults
from pytoon.engine_adapters.base import EngineAdapter, SegmentResult
from pytoon.log import get_logger

logger = get_logger(__name__)

# Temp directory for intermediate files
_WORK_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "_engine_tmp"


def _ffmpeg(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _ensure_work_dir() -> Path:
    _WORK_DIR.mkdir(parents=True, exist_ok=True)
    return _WORK_DIR


class LocalFFmpegAdapter(EngineAdapter):
    """Composes video segments from images using pure ffmpeg filters."""

    name = "local_ffmpeg"

    async def health_check(self) -> bool:
        """Always healthy if ffmpeg is installed."""
        try:
            r = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True, timeout=5,
            )
            return r.returncode == 0
        except Exception:
            return False

    async def render_segment(
        self,
        *,
        job_id: str,
        segment_index: int,
        prompt: str,
        duration_seconds: float,
        archetype: str,
        brand_safe: bool,
        image_path: Optional[str] = None,
        mask_path: Optional[str] = None,
        width: int = 1080,
        height: int = 1920,
        seed: Optional[int] = None,
        extra: dict[str, Any] | None = None,
    ) -> SegmentResult:
        t0 = time.monotonic()
        work = _ensure_work_dir()
        tag = f"{job_id}_{segment_index}_{uuid.uuid4().hex[:8]}"
        out_path = work / f"{tag}.mp4"

        try:
            if archetype == "PRODUCT_HERO":
                self._render_hero(image_path, out_path, duration_seconds, width, height, seed)
            elif archetype == "OVERLAY":
                self._render_overlay(image_path, out_path, duration_seconds, width, height, seed)
            elif archetype == "MEME_TEXT":
                if image_path:
                    self._render_meme_with_image(image_path, out_path, duration_seconds, width, height)
                else:
                    self._render_meme_text_only(prompt, out_path, duration_seconds, width, height)
            else:
                # Fallback: simple image-to-video
                if image_path:
                    self._render_hero(image_path, out_path, duration_seconds, width, height, seed)
                else:
                    self._render_meme_text_only(prompt, out_path, duration_seconds, width, height)

            elapsed = (time.monotonic() - t0) * 1000

            if out_path.exists() and out_path.stat().st_size > 0:
                logger.info(
                    "segment_rendered",
                    job_id=job_id, segment_index=segment_index,
                    engine=self.name, archetype=archetype, elapsed_ms=round(elapsed),
                )
                return SegmentResult(
                    success=True,
                    artifact_path=str(out_path),
                    engine_name=self.name,
                    seed=seed,
                    elapsed_ms=elapsed,
                )
            else:
                raise RuntimeError("ffmpeg produced empty or missing output")

        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.error(
                "segment_render_failed",
                job_id=job_id, segment_index=segment_index,
                engine=self.name, error=str(exc),
            )
            return SegmentResult(
                success=False,
                engine_name=self.name,
                elapsed_ms=elapsed,
                error=str(exc),
            )

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": "local",
            "archetypes": ["PRODUCT_HERO", "OVERLAY", "MEME_TEXT"],
            "max_segment_duration": 10,
        }

    # ------------------------------------------------------------------
    # PRODUCT_HERO: Ken Burns zoom + pan on full-frame image
    # ------------------------------------------------------------------

    def _render_hero(
        self, image_path: str | None, out: Path,
        dur: float, w: int, h: int, seed: int | None,
    ):
        if not image_path or not Path(image_path).exists():
            self._render_color_segment(out, dur, w, h, "0x1a1a2e")
            return

        # Pick a Ken Burns direction based on seed for variety
        rng = random.Random(seed)
        effect = rng.choice(["zoom_in", "zoom_out", "pan_up", "pan_down"])
        fps = 30
        frames = int(dur * fps)

        # zoompan filter: each frame we compute zoom and position
        if effect == "zoom_in":
            zp = (
                f"zoompan=z='1+0.0015*in':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:s={w}x{h}:fps={fps}"
            )
        elif effect == "zoom_out":
            zp = (
                f"zoompan=z='1.3-0.001*in':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:s={w}x{h}:fps={fps}"
            )
        elif effect == "pan_up":
            zp = (
                f"zoompan=z='1.15':x='iw/2-(iw/zoom/2)'"
                f":y='ih*0.3-ih*0.2*in/{frames}-(ih/zoom/2)+ih/2'"
                f":d={frames}:s={w}x{h}:fps={fps}"
            )
        else:  # pan_down
            zp = (
                f"zoompan=z='1.15':x='iw/2-(iw/zoom/2)'"
                f":y='ih*0.1+ih*0.2*in/{frames}-(ih/zoom/2)+ih/2'"
                f":d={frames}:s={w}x{h}:fps={fps}"
            )

        vf = f"{zp},format=yuv420p"

        r = _ffmpeg([
            "-loop", "1", "-framerate", str(fps), "-i", image_path,
            "-vf", vf,
            "-t", str(dur),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast",
            str(out),
        ])
        if r.returncode != 0:
            logger.error("hero_ffmpeg_fail", stderr=r.stderr[:300])
            raise RuntimeError(f"Hero render failed: {r.stderr[:200]}")

    # ------------------------------------------------------------------
    # OVERLAY: blurred/darkened background + centered product
    # ------------------------------------------------------------------

    def _render_overlay(
        self, image_path: str | None, out: Path,
        dur: float, w: int, h: int, seed: int | None,
    ):
        if not image_path or not Path(image_path).exists():
            self._render_color_segment(out, dur, w, h, "0x0d1117")
            return

        fps = 30
        frames = int(dur * fps)

        # Filter: create blurred dark background from the image,
        # then overlay the original image scaled + centered on top
        # Background: scale to fill, blur heavily, darken
        # Foreground: scale to fit with padding, centered
        product_w = int(w * 0.6)  # product takes 60% of width

        # Use a slow zoom on the background for subtle motion
        vf = (
            # Background: scale to fill frame, heavy blur, darken, slow zoom
            f"split[bg][fg];"
            f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},boxblur=20:20,"
            f"colorbalance=bs=-0.3:gs=-0.3:rs=-0.3,"
            f"zoompan=z='1.05+0.001*in':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={w}x{h}:fps={fps}[bgout];"
            # Foreground: scale product to fit, keep aspect
            f"[fg]scale={product_w}:-1:force_original_aspect_ratio=decrease,"
            f"pad={product_w}:ih:(ow-iw)/2:0:color=0x00000000@0[fgout];"
            # Overlay foreground centered on background
            f"[bgout][fgout]overlay=(W-w)/2:(H-h)*0.38:format=auto,"
            f"format=yuv420p"
        )

        r = _ffmpeg([
            "-loop", "1", "-framerate", str(fps), "-i", image_path,
            "-vf", vf,
            "-t", str(dur),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast",
            str(out),
        ])
        if r.returncode != 0:
            logger.error("overlay_ffmpeg_fail", stderr=r.stderr[:300])
            # Fallback to simpler approach without split
            self._render_overlay_simple(image_path, out, dur, w, h)

    def _render_overlay_simple(
        self, image_path: str, out: Path,
        dur: float, w: int, h: int,
    ):
        """Simpler overlay: solid dark background + centered product."""
        fps = 30
        product_w = int(w * 0.6)

        # Two-input approach: color background + image overlay
        r = _ffmpeg([
            "-f", "lavfi",
            "-i", f"color=c=0x0d1117:s={w}x{h}:d={dur}:r={fps}",
            "-loop", "1", "-framerate", str(fps), "-i", image_path,
            "-filter_complex",
            f"[1:v]scale={product_w}:-1:force_original_aspect_ratio=decrease[prod];"
            f"[0:v][prod]overlay=(W-w)/2:(H-h)*0.38:shortest=1,"
            f"format=yuv420p",
            "-t", str(dur),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast",
            str(out),
        ])
        if r.returncode != 0:
            raise RuntimeError(f"Overlay simple render failed: {r.stderr[:200]}")

    # ------------------------------------------------------------------
    # MEME_TEXT: full-frame image (with room for text bars in assembly)
    # ------------------------------------------------------------------

    def _render_meme_with_image(
        self, image_path: str, out: Path,
        dur: float, w: int, h: int,
    ):
        """Full-frame image with slight zoom, leaving space for text bars."""
        fps = 30
        frames = int(dur * fps)

        # Scale image to fill frame, slight slow zoom for life
        vf = (
            f"zoompan=z='1.02+0.001*in':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={w}x{h}:fps={fps},"
            f"format=yuv420p"
        )

        r = _ffmpeg([
            "-loop", "1", "-framerate", str(fps), "-i", image_path,
            "-vf", vf,
            "-t", str(dur),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast",
            str(out),
        ])
        if r.returncode != 0:
            raise RuntimeError(f"Meme image render failed: {r.stderr[:200]}")

    def _render_meme_text_only(
        self, prompt: str, out: Path,
        dur: float, w: int, h: int,
    ):
        """Text-only segment: gradient/colored background with text."""
        fps = 30
        safe_text = prompt.replace("'", "").replace(":", " ").replace("\\", "")[:80]

        # Animated gradient-like background using color + geq
        vf = (
            f"drawtext=text='{safe_text}':"
            f"fontsize=60:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"font=Arial"
        )

        r = _ffmpeg([
            "-f", "lavfi",
            "-i", f"color=c=0x1a1a2e:s={w}x{h}:d={dur}:r={fps}",
            "-vf", vf,
            "-t", str(dur),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast",
            str(out),
        ])
        if r.returncode != 0:
            raise RuntimeError(f"Meme text render failed: {r.stderr[:200]}")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _render_color_segment(
        self, out: Path, dur: float, w: int, h: int, color: str,
    ):
        """Solid colour video as minimal fallback."""
        _ffmpeg([
            "-f", "lavfi",
            "-i", f"color=c={color}:s={w}x{h}:d={dur}:r=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-t", str(dur),
            str(out),
        ])

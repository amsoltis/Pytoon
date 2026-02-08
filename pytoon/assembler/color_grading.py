"""Quality consistency — color grading and style normalization.

Applies global LUT/color filters, preset-driven color correction,
and brightness/contrast normalization as a post-rendering pipeline stage.

Ticket: P5-05
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pytoon.assembler.ffmpeg_ops import run_ffmpeg
from pytoon.log import get_logger

logger = get_logger(__name__)


@dataclass
class ColorProfile:
    """Color grading profile for video output."""

    name: str = "neutral"
    brightness: float = 0.0       # -1.0 to 1.0
    contrast: float = 1.0         # 0.5 to 2.0
    saturation: float = 1.0       # 0.0 to 3.0
    gamma: float = 1.0            # 0.1 to 10.0
    temperature: str = "neutral"  # warm | cool | neutral | vintage
    lut_path: Optional[str] = None


# Preset color profiles
COLOR_PROFILES: dict[str, ColorProfile] = {
    "neutral": ColorProfile(name="neutral"),
    "warm": ColorProfile(
        name="warm",
        brightness=0.02,
        contrast=1.05,
        saturation=1.1,
        temperature="warm",
    ),
    "cool": ColorProfile(
        name="cool",
        brightness=0.0,
        contrast=1.03,
        saturation=0.95,
        temperature="cool",
    ),
    "vintage": ColorProfile(
        name="vintage",
        brightness=-0.02,
        contrast=1.1,
        saturation=0.8,
        gamma=0.95,
        temperature="vintage",
    ),
    "cinematic": ColorProfile(
        name="cinematic",
        brightness=-0.01,
        contrast=1.15,
        saturation=0.9,
        temperature="cool",
    ),
    "vibrant": ColorProfile(
        name="vibrant",
        brightness=0.03,
        contrast=1.1,
        saturation=1.3,
        temperature="warm",
    ),
}


def get_color_profile(
    preset: dict | None = None,
    profile_name: str | None = None,
) -> ColorProfile:
    """Get color profile from preset or by name."""
    if profile_name and profile_name in COLOR_PROFILES:
        return COLOR_PROFILES[profile_name]

    if preset:
        color_cfg = preset.get("color_grade", {})
        name = color_cfg.get("profile", "neutral")
        if name in COLOR_PROFILES:
            profile = COLOR_PROFILES[name]
            # Apply overrides from preset
            if "brightness" in color_cfg:
                profile.brightness = color_cfg["brightness"]
            if "contrast" in color_cfg:
                profile.contrast = color_cfg["contrast"]
            if "saturation" in color_cfg:
                profile.saturation = color_cfg["saturation"]
            if "lut_path" in color_cfg:
                profile.lut_path = color_cfg["lut_path"]
            return profile

    return COLOR_PROFILES["neutral"]


def apply_color_grade(
    video_path: str | Path,
    output_path: str | Path,
    profile: ColorProfile | None = None,
) -> Path:
    """Apply color grading to a video clip.

    Pipeline stage: runs between scene rendering and composition.
    """
    vid = Path(video_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if profile is None:
        profile = ColorProfile()

    # Skip if neutral profile with no changes
    if (
        profile.name == "neutral"
        and profile.lut_path is None
        and profile.brightness == 0.0
        and profile.contrast == 1.0
        and profile.saturation == 1.0
        and profile.gamma == 1.0
    ):
        run_ffmpeg(["-i", str(vid), "-c", "copy", str(out)])
        return out

    filters: list[str] = []

    # Apply LUT if specified
    if profile.lut_path and Path(profile.lut_path).exists():
        filters.append(f"lut3d='{profile.lut_path}'")

    # Color correction using eq filter
    eq_parts: list[str] = []
    if profile.brightness != 0.0:
        eq_parts.append(f"brightness={profile.brightness}")
    if profile.contrast != 1.0:
        eq_parts.append(f"contrast={profile.contrast}")
    if profile.saturation != 1.0:
        eq_parts.append(f"saturation={profile.saturation}")
    if profile.gamma != 1.0:
        eq_parts.append(f"gamma={profile.gamma}")

    if eq_parts:
        filters.append("eq=" + ":".join(eq_parts))

    # Temperature adjustment
    if profile.temperature == "warm":
        filters.append("colortemperature=temperature=6500")
    elif profile.temperature == "cool":
        filters.append("colortemperature=temperature=4500")
    elif profile.temperature == "vintage":
        # Vintage: slight sepia with reduced saturation (already handled by eq)
        filters.append("colorchannelmixer=rr=1.1:gg=1.0:bb=0.9")

    if not filters:
        run_ffmpeg(["-i", str(vid), "-c", "copy", str(out)])
        return out

    vf = ",".join(filters)
    run_ffmpeg([
        "-i", str(vid),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(out),
    ])

    logger.info("color_grade_applied", profile=profile.name)
    return out


def normalize_brightness(
    video_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Auto-normalize brightness/contrast using FFmpeg normalize filter."""
    vid = Path(video_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    run_ffmpeg([
        "-i", str(vid),
        "-vf", "normalize=strength=0.3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(out),
    ])
    return out

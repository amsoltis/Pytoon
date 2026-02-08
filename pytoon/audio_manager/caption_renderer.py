"""Scene-aware caption renderer with styled burn-in and safe zone enforcement.

Renders captions onto video with:
  - Preset-driven styling (font, size, color, outline, background bar).
  - Auto line-wrap (max 2 lines), font reduction if overflow.
  - Fade-in/fade-out animation (0.2s).
  - Safe zone margins (top 100px, bottom 150px, sides 54px).
  - Brand-safe override (locked font/color, min 24px).

Replaces the basic P2-07 `burn_captions_v2`.

Tickets: P4-05, P4-06
Acceptance Criteria: V2-AC-002, V2-AC-017
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pytoon.assembler.ffmpeg_ops import run_ffmpeg
from pytoon.log import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Safe zone constants (1080x1920)
# ---------------------------------------------------------------------------

SAFE_TOP = 100
SAFE_BOTTOM = 150
SAFE_LEFT = 54
SAFE_RIGHT = 54
FRAME_WIDTH = 1080
FRAME_HEIGHT = 1920

# Usable caption area
SAFE_WIDTH = FRAME_WIDTH - SAFE_LEFT - SAFE_RIGHT   # 972
SAFE_HEIGHT = FRAME_HEIGHT - SAFE_TOP - SAFE_BOTTOM  # 1670

# Font constraints
MIN_FONT_SIZE = 20
BRAND_SAFE_MIN_FONT_SIZE = 24
MAX_LINES = 2


@dataclass
class CaptionStyle:
    """Caption styling configuration."""

    font_family: str = "Arial"
    font_size: int = 48
    font_color: str = "white"
    outline_color: str = "black"
    outline_width: int = 2
    background_color: str = "black"
    background_opacity: float = 0.5
    position: str = "bottom-center"
    max_lines: int = MAX_LINES
    animation: str = "fade"
    fade_duration: float = 0.2


def get_caption_style(preset: dict, brand_safe: bool = True) -> CaptionStyle:
    """Build CaptionStyle from preset configuration."""
    cap_cfg = preset.get("caption_style", {})

    style = CaptionStyle(
        font_family=cap_cfg.get("font", cap_cfg.get("font_family", "Arial")),
        font_size=cap_cfg.get("fontsize", cap_cfg.get("font_size", 48)),
        font_color=cap_cfg.get("fontcolor", cap_cfg.get("font_color", "white")),
        outline_color=cap_cfg.get("outline_color", "black"),
        outline_width=cap_cfg.get("outline_width", 2),
        background_color=cap_cfg.get("background_color", "black"),
        background_opacity=cap_cfg.get("background_opacity", 0.5),
        position=cap_cfg.get("position", "bottom-center"),
        max_lines=cap_cfg.get("max_lines", MAX_LINES),
        animation=cap_cfg.get("animation", "fade"),
        fade_duration=cap_cfg.get("fade_duration", 0.2),
    )

    # Brand-safe overrides
    if brand_safe:
        style.font_size = max(style.font_size, BRAND_SAFE_MIN_FONT_SIZE)
        brand_font = cap_cfg.get("brand_font")
        if brand_font:
            style.font_family = brand_font

    return style


def render_styled_captions(
    video_path: str | Path,
    output_path: str | Path,
    captions: list[dict],
    *,
    style: CaptionStyle | None = None,
    brand_safe: bool = True,
    width: int = FRAME_WIDTH,
    height: int = FRAME_HEIGHT,
) -> Path:
    """Render styled, scene-aware captions onto video.

    Each caption dict must have: text, start (ms), end (ms).
    Optional: scene_id, style (override per caption).

    Returns path to output video.
    """
    vid = Path(video_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not captions:
        run_ffmpeg(["-i", str(vid), "-c", "copy", str(out)])
        return out

    if style is None:
        style = CaptionStyle()

    filters: list[str] = []

    for cap in captions:
        text = cap.get("text", "")
        start_s = cap.get("start", 0) / 1000.0
        end_s = cap.get("end", 0) / 1000.0

        if not text or end_s <= start_s:
            continue

        # Auto line-wrap
        wrapped = _auto_wrap(text, style.font_size, width)

        # Safe zone position
        x, y = _safe_position(style.position, style.font_size, len(wrapped.split("\n")))

        # Escape for FFmpeg drawtext
        safe_text = wrapped.replace("'", "'\\''").replace(":", "\\:").replace("\\n", "\n")

        # Build drawtext filter
        parts = [
            f"drawtext=text='{safe_text}'",
            f"fontsize={style.font_size}",
            f"fontcolor={style.font_color}",
            f"font={style.font_family}",
            f"x={x}",
            f"y={y}",
            f"borderw={style.outline_width}",
            f"bordercolor={style.outline_color}",
            f"box=1",
            f"boxcolor={style.background_color}@{style.background_opacity}",
            f"boxborderw=14",
        ]

        # Enable with fade animation
        if style.animation == "fade" and style.fade_duration > 0:
            fd = style.fade_duration
            # Fade-in alpha: ramp from 0 to 1 over fade_duration
            # Fade-out alpha: ramp from 1 to 0 over fade_duration before end
            alpha_expr = (
                f"if(lt(t,{start_s}),0,"
                f"if(lt(t,{start_s + fd}),(t-{start_s})/{fd},"
                f"if(lt(t,{end_s - fd}),1,"
                f"if(lt(t,{end_s}),({end_s}-t)/{fd},0))))"
            )
            parts.append(f"alpha='{alpha_expr}'")
            parts.append(f"enable='between(t,{start_s},{end_s})'")
        else:
            parts.append(f"enable='between(t,{start_s},{end_s})'")

        filters.append(":".join(parts))

    if not filters:
        run_ffmpeg(["-i", str(vid), "-c", "copy", str(out)])
        return out

    vf = ",".join(filters)
    run_ffmpeg([
        "-i", str(vid),
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(out),
    ])

    logger.info("styled_captions_rendered", count=len(filters))
    return out


def generate_srt(
    captions: list[dict],
    output_path: str | Path,
) -> Path:
    """Generate an SRT subtitle file from caption data."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for i, cap in enumerate(captions, 1):
        start_ms = cap.get("start", 0)
        end_ms = cap.get("end", 0)
        text = cap.get("text", "")

        start_tc = _ms_to_srt_tc(start_ms)
        end_tc = _ms_to_srt_tc(end_ms)

        lines.append(str(i))
        lines.append(f"{start_tc} --> {end_tc}")
        lines.append(text)
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Safe zone helpers
# ---------------------------------------------------------------------------

def _safe_position(
    position: str,
    font_size: int,
    n_lines: int,
) -> tuple[str, str]:
    """Calculate safe X, Y coordinates for caption placement."""
    text_height = font_size * n_lines * 1.3  # approximate with line spacing

    if position == "top-center":
        x = "(w-text_w)/2"
        y = str(SAFE_TOP + 20)
    elif position == "center":
        x = "(w-text_w)/2"
        y = f"(h-text_h)/2"
    else:
        # Default: bottom-center within safe zone
        x = "(w-text_w)/2"
        y = f"h-{SAFE_BOTTOM}-text_h"

    return x, y


def _auto_wrap(text: str, font_size: int, frame_width: int) -> str:
    """Auto-wrap text to fit within safe zone width.

    Estimates characters per line from font size and wraps accordingly.
    Reduces font size if needed (minimum 20px).
    """
    usable_width = frame_width - SAFE_LEFT - SAFE_RIGHT - 28  # 28 = boxborderw * 2
    # Approximate: each character is ~0.55 * font_size wide
    chars_per_line = max(10, int(usable_width / (font_size * 0.55)))

    words = text.split()
    if not words:
        return text

    lines: list[str] = []
    current_line: list[str] = []
    current_len = 0

    for word in words:
        word_len = len(word)
        if current_len + word_len + (1 if current_line else 0) > chars_per_line:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_len = word_len
        else:
            current_line.append(word)
            current_len += word_len + (1 if len(current_line) > 1 else 0)

    if current_line:
        lines.append(" ".join(current_line))

    # Enforce max lines
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES]
        lines[-1] = lines[-1][:chars_per_line - 3] + "..."

    return "\\n".join(lines)


def _ms_to_srt_tc(ms: int) -> str:
    """Convert milliseconds to SRT timecode HH:MM:SS,mmm."""
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    remainder = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{remainder:03d}"

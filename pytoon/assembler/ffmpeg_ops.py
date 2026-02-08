"""Low-level ffmpeg operations."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from pytoon.log import get_logger

logger = get_logger(__name__)


def run_ffmpeg(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Run an ffmpeg command and return the result."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"] + args
    logger.debug("ffmpeg_cmd", cmd=" ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        logger.error("ffmpeg_error", stderr=result.stderr[:500])
        result.check_returncode()
    return result


def run_ffprobe(args: list[str], timeout: int = 30) -> str:
    """Run ffprobe and return stdout."""
    cmd = ["ffprobe", "-hide_banner"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout


# ---------------------------------------------------------------------------
# Concat with crossfade
# ---------------------------------------------------------------------------

def concat_segments(
    segment_paths: list[Path],
    output_path: Path,
    crossfade_ms: int = 150,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """Concatenate segment clips, optionally with crossfade transitions.

    For V1, we use ffmpeg concat demuxer for simplicity when crossfade=0,
    and the xfade filter when crossfade > 0.
    """
    if not segment_paths:
        raise ValueError("No segments to concatenate")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(segment_paths) == 1:
        # Single segment — just re-encode
        run_ffmpeg([
            "-i", str(segment_paths[0]),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-s", f"{width}x{height}",
            str(output_path),
        ])
        return output_path

    if crossfade_ms <= 0:
        return _concat_demuxer(segment_paths, output_path, fps, width, height)
    else:
        return _concat_xfade(segment_paths, output_path, crossfade_ms, fps, width, height)


def _concat_demuxer(
    paths: list[Path], out: Path, fps: int, w: int, h: int,
) -> Path:
    """Simple concat via demuxer (no transitions)."""
    list_file = out.with_suffix(".txt")
    with open(list_file, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-s", f"{w}x{h}",
        str(out),
    ])
    list_file.unlink(missing_ok=True)
    return out


def _concat_xfade(
    paths: list[Path], out: Path, xfade_ms: int, fps: int, w: int, h: int,
) -> Path:
    """Concat with xfade transitions between each pair."""
    xfade_sec = xfade_ms / 1000.0

    # Get durations
    durations = [_get_duration(p) for p in paths]

    # Build filter chain
    inputs = []
    for p in paths:
        inputs.extend(["-i", str(p)])

    if len(paths) == 2:
        offset = max(0, durations[0] - xfade_sec)
        filter_complex = (
            f"[0:v][1:v]xfade=transition=fade:duration={xfade_sec}:offset={offset},"
            f"format=yuv420p,scale={w}:{h},fps={fps}[outv]"
        )
        run_ffmpeg(inputs + [
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(out),
        ])
        return out

    # For 3+ segments, chain xfade filters
    filter_parts = []
    current_label = "0:v"
    cumulative_offset = 0.0

    for i in range(1, len(paths)):
        offset = cumulative_offset + durations[i - 1] - xfade_sec * i
        offset = max(0, offset)
        if i == 1:
            prev = "[0:v]"
            nxt = "[1:v]"
        else:
            prev = f"[v{i-1}]"
            nxt = f"[{i}:v]"

        if i < len(paths) - 1:
            out_label = f"[v{i}]"
        else:
            out_label = "[outv]"

        cumulative_offset += durations[i - 1] - xfade_sec
        xf_offset = max(0, cumulative_offset)

        filter_parts.append(
            f"{prev}{nxt}xfade=transition=fade:duration={xfade_sec}:offset={xf_offset}"
            f"{out_label}"
        )

    filter_str = ";".join(filter_parts)
    # Append format + scale
    # We modify the last filter to include format
    filter_str = filter_str.replace(
        "[outv]",
        f",format=yuv420p,scale={w}:{h},fps={fps}[outv]"
    )

    run_ffmpeg(inputs + [
        "-filter_complex", filter_str,
        "-map", "[outv]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out),
    ])
    return out


# ---------------------------------------------------------------------------
# Overlay
# ---------------------------------------------------------------------------

def overlay_image(
    video_path: Path,
    image_path: Path,
    output_path: Path,
    x: str = "(W-w)/2",
    y: str = "(H-h)*0.35",
    scale_w: int = 600,
    shadow: bool = False,
    glow: bool = False,
) -> Path:
    """Overlay a product/person image on the video."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build overlay filter
    filters = f"[1:v]scale={scale_w}:-1[ovr];"
    if shadow:
        filters += "[ovr]drawbox=x=2:y=2:w=iw:h=ih:color=black@0.3:t=fill[ovrs];"
        filters += f"[0:v][ovrs]overlay={x}:{y}[out]"
    else:
        filters += f"[0:v][ovr]overlay={x}:{y}[out]"

    run_ffmpeg([
        "-i", str(video_path),
        "-i", str(image_path),
        "-filter_complex", filters,
        "-map", "[out]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(output_path),
    ])
    return output_path


# ---------------------------------------------------------------------------
# Captions
# ---------------------------------------------------------------------------

def burn_captions(
    video_path: Path,
    output_path: Path,
    captions: list[dict],
    font: str = "Arial",
    fontsize: int = 56,
    fontcolor: str = "white",
    safe_margin: int = 120,
    width: int = 1080,
    archetype: str = "OVERLAY",
    position: str = "lower_third",
) -> Path:
    """Burn caption text onto the video using drawtext filters.

    Archetype-aware styling:
      MEME_TEXT   → bold text with black background bar, top or center
      PRODUCT_HERO → centered text with shadow, lower third
      OVERLAY     → lower third with semi-transparent box behind text
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not captions:
        run_ffmpeg(["-i", str(video_path), "-c", "copy", str(output_path)])
        return output_path

    filters = []
    for cap in captions:
        text = cap["text"].replace("'", "'\\''").replace(":", "\\:")
        start = cap["start"]
        end = cap["end"]

        if archetype == "MEME_TEXT":
            # Meme style: bold text with dark box, upper area
            filters.append(
                f"drawbox=x=0:y=0:w=iw:h=130:color=black@0.75:t=fill:"
                f"enable='between(t,{start},{end})'"
            )
            filters.append(
                f"drawtext=text='{text}':"
                f"fontsize=52:fontcolor=white:"
                f"font=Impact:"
                f"x=(w-text_w)/2:y=40:"
                f"borderw=2:bordercolor=black:"
                f"enable='between(t,{start},{end})'"
            )
        elif archetype == "PRODUCT_HERO":
            # Hero style: elegant centered text with shadow, lower portion
            filters.append(
                f"drawtext=text='{text}':"
                f"fontsize={fontsize}:fontcolor=white:"
                f"font={font}:"
                f"x=(w-text_w)/2:y=h-{safe_margin}-text_h:"
                f"shadowcolor=black@0.6:shadowx=2:shadowy=2:"
                f"enable='between(t,{start},{end})'"
            )
        else:
            # Overlay / default: lower third with background box behind text
            # Use drawtext with box=1 for a background box (avoids drawbox text_h issue)
            filters.append(
                f"drawtext=text='{text}':"
                f"fontsize={fontsize}:fontcolor=white:"
                f"font={font}:"
                f"x=(w-text_w)/2:y=h-{safe_margin}-text_h:"
                f"box=1:boxcolor=black@0.5:boxborderw=15:"
                f"enable='between(t,{start},{end})'"
            )

    vf = ",".join(filters)
    run_ffmpeg([
        "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(output_path),
    ])
    return output_path


# ---------------------------------------------------------------------------
# Brand watermark
# ---------------------------------------------------------------------------

def burn_watermark(
    video_path: Path,
    output_path: Path,
    watermark_path: Path,
    position: str = "top-right",
    scale_w: int = 120,
    opacity: float = 0.6,
    margin: int = 30,
) -> Path:
    """Overlay a semi-transparent brand logo/watermark on the video."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pos_map = {
        "top-left": f"x={margin}:y={margin}",
        "top-right": f"x=W-w-{margin}:y={margin}",
        "bottom-left": f"x={margin}:y=H-h-{margin}",
        "bottom-right": f"x=W-w-{margin}:y=H-h-{margin}",
    }
    pos_str = pos_map.get(position, pos_map["top-right"])

    # Scale watermark, apply opacity, overlay
    fc = (
        f"[1:v]scale={scale_w}:-1,format=rgba,"
        f"colorchannelmixer=aa={opacity}[wm];"
        f"[0:v][wm]overlay={pos_str}:format=auto[out]"
    )

    run_ffmpeg([
        "-i", str(video_path),
        "-i", str(watermark_path),
        "-filter_complex", fc,
        "-map", "[out]", "-map", "0:a?",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(output_path),
    ])
    return output_path


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

def mix_audio(
    video_path: Path,
    output_path: Path,
    music_path: Optional[Path] = None,
    voice_path: Optional[Path] = None,
    music_level_db: float = -18,
    voice_level_db: float = -6,
    duck_music: bool = True,
    duration_seconds: Optional[float] = None,
) -> Path:
    """Mix music and/or voice onto the video."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not music_path and not voice_path:
        run_ffmpeg(["-i", str(video_path), "-c", "copy", str(output_path)])
        return output_path

    inputs = ["-i", str(video_path)]
    filter_parts = []
    stream_idx = 1  # 0 is video

    if music_path and music_path.exists():
        inputs.extend(["-i", str(music_path)])
        # Loop music to duration
        loop = f"-stream_loop -1" if duration_seconds else ""
        filter_parts.append(
            f"[{stream_idx}:a]aloop=loop=-1:size=2e+09,atrim=0:{duration_seconds or 60},"
            f"volume={_db_to_vol(music_level_db)}[music]"
        )
        stream_idx += 1

    if voice_path and voice_path.exists():
        inputs.extend(["-i", str(voice_path)])
        filter_parts.append(
            f"[{stream_idx}:a]volume={_db_to_vol(voice_level_db)}[voice]"
        )
        stream_idx += 1

    # Mix
    if music_path and voice_path:
        if duck_music:
            filter_parts.append("[music][voice]sidechaincompress=threshold=0.02:ratio=6[ducked]")
            filter_parts.append("[ducked][voice]amix=inputs=2:duration=shortest[outa]")
        else:
            filter_parts.append("[music][voice]amix=inputs=2:duration=shortest[outa]")
    elif music_path:
        filter_parts.append("[music]anull[outa]")
    else:
        filter_parts.append("[voice]anull[outa]")

    filter_str = ";".join(filter_parts)

    run_ffmpeg(inputs + [
        "-filter_complex", filter_str,
        "-map", "0:v", "-map", "[outa]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output_path),
    ])
    return output_path


def loudness_normalize(
    input_path: Path,
    output_path: Path,
    target_lufs: float = -14.0,
) -> Path:
    """EBU R128 loudness normalization."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-i", str(input_path),
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path),
    ])
    return output_path


# ---------------------------------------------------------------------------
# Thumbnail
# ---------------------------------------------------------------------------

def extract_thumbnail(
    video_path: Path,
    output_path: Path,
    timestamp: float = 1.0,
) -> Path:
    """Extract a single frame as thumbnail."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-i", str(video_path),
        "-ss", str(timestamp),
        "-frames:v", "1",
        "-q:v", "2",
        str(output_path),
    ])
    return output_path


# ---------------------------------------------------------------------------
# V2: Scene composition with timeline-driven transitions  (P2-06)
# ---------------------------------------------------------------------------

def compose_scenes(
    scene_clips: list[Path],
    output_path: Path,
    transitions: list[dict | None],
    *,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """Compose scene clips with per-scene transition types from the Timeline.

    Args:
        scene_clips: Ordered list of scene clip paths.
        transitions: List of transition dicts (one per scene).
                     Each dict has 'type' (cut|fade) and 'duration' (ms).
                     Last entry should be None (no transition after last scene).
    """
    if not scene_clips:
        raise ValueError("No scene clips to compose")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(scene_clips) == 1:
        run_ffmpeg([
            "-i", str(scene_clips[0]),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-r", str(fps), "-s", f"{width}x{height}",
            str(output_path),
        ])
        return output_path

    # Get durations
    durations = [_get_duration(p) for p in scene_clips]

    inputs: list[str] = []
    for p in scene_clips:
        inputs.extend(["-i", str(p)])

    # Build xfade filter chain
    filter_parts: list[str] = []
    cumulative_duration = durations[0]

    for i in range(1, len(scene_clips)):
        trans = transitions[i - 1] if i - 1 < len(transitions) else None
        t_type = "fade"
        t_dur_sec = 0.5

        if trans:
            t_type = trans.get("type", "fade")
            t_dur_sec = trans.get("duration", 500) / 1000.0

        if t_type == "cut":
            t_dur_sec = 0.0

        # xfade offset: point where transition starts
        offset = max(0, cumulative_duration - t_dur_sec)

        xfade_type = "fade" if t_type in ("fade", "fade_black") else "fade"

        if i == 1:
            prev = "[0:v]"
        else:
            prev = f"[v{i-1}]"
        nxt = f"[{i}:v]"

        if i < len(scene_clips) - 1:
            out_label = f"[v{i}]"
        else:
            out_label = f",format=yuv420p,scale={width}:{height},fps={fps}[outv]"

        if t_dur_sec > 0:
            filter_parts.append(
                f"{prev}{nxt}xfade=transition={xfade_type}"
                f":duration={t_dur_sec}:offset={offset}{out_label}"
            )
        else:
            # Cut: just concat without transition
            filter_parts.append(
                f"{prev}{nxt}xfade=transition=fade"
                f":duration=0.001:offset={offset}{out_label}"
            )

        cumulative_duration = offset + durations[i]

    filter_str = ";".join(filter_parts)

    run_ffmpeg(inputs + [
        "-filter_complex", filter_str,
        "-map", "[outv]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(output_path),
    ])
    return output_path


# ---------------------------------------------------------------------------
# V2: Timeline-based caption burn-in  (P2-07)
# ---------------------------------------------------------------------------

def burn_captions_v2(
    video_path: Path,
    output_path: Path,
    captions: list[dict],
    *,
    font: str = "Arial",
    fontsize: int = 48,
    fontcolor: str = "white",
    borderw: int = 2,
    bordercolor: str = "black",
    safe_margin_bottom: int = 150,
    safe_margin_sides: int = 54,
    width: int = 1080,
) -> Path:
    """Burn captions onto video using timeline caption track entries.

    Each caption dict must have: text, start (ms), end (ms).
    Default styling: white text, black outline, centered at bottom with
    safe zone margin.

    Ticket: P2-07
    Acceptance Criteria: V2-AC-002, V2-AC-017
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not captions:
        run_ffmpeg(["-i", str(video_path), "-c", "copy", str(output_path)])
        return output_path

    filters: list[str] = []
    for cap in captions:
        text = cap["text"].replace("'", "'\\''").replace(":", "\\:")
        start_s = cap["start"] / 1000.0
        end_s = cap["end"] / 1000.0

        # Calculate Y position: bottom of safe area
        y_pos = f"h-{safe_margin_bottom}-text_h"

        filters.append(
            f"drawtext=text='{text}':"
            f"fontsize={fontsize}:fontcolor={fontcolor}:"
            f"font={font}:"
            f"x=(w-text_w)/2:y={y_pos}:"
            f"borderw={borderw}:bordercolor={bordercolor}:"
            f"box=1:boxcolor=black@0.4:boxborderw=12:"
            f"enable='between(t,{start_s},{end_s})'"
        )

    vf = ",".join(filters)
    run_ffmpeg([
        "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(output_path),
    ])
    return output_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_duration(path: Path) -> float:
    """Get duration of a video file in seconds."""
    out = run_ffprobe([
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    try:
        return float(out.strip())
    except (ValueError, AttributeError):
        return 3.0  # default assumption


def _db_to_vol(db: float) -> float:
    """Convert dB to ffmpeg volume multiplier."""
    return 10 ** (db / 20)

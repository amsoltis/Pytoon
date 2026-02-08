"""Multi-track audio mixing — combine voiceover + ducked music.

Mixes voice at ~-6 dBFS + ducked music, applies limiter at -1 dBFS peak,
and handles voice-only/music-only/both combinations.

Ticket: P4-09
Acceptance Criteria: V2-AC-007, V2-AC-008
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pytoon.assembler.ffmpeg_ops import run_ffmpeg
from pytoon.log import get_logger

logger = get_logger(__name__)

# Default levels
VOICE_LEVEL_DB = -6.0
LIMITER_THRESHOLD_DB = -1.0


def mix_audio_tracks(
    output_path: str | Path,
    *,
    voice_path: str | Path | None = None,
    music_path: str | Path | None = None,
    voice_level_db: float = VOICE_LEVEL_DB,
    target_duration_seconds: float | None = None,
) -> str | None:
    """Mix voiceover and music into a single stereo output.

    Handles:
    - Both voice + music: mix with voice volume and limiter.
    - Voice only: apply voice level.
    - Music only: pass through.
    - Neither: return None.

    Returns path to mixed audio, or None if no audio.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    has_voice = voice_path and Path(voice_path).exists()
    has_music = music_path and Path(music_path).exists()

    if not has_voice and not has_music:
        return None

    if has_voice and has_music:
        return _mix_voice_and_music(
            str(voice_path), str(music_path), out,
            voice_level_db, target_duration_seconds,
        )
    elif has_voice:
        return _process_voice_only(str(voice_path), out, voice_level_db)
    else:
        # Music only — just copy
        run_ffmpeg(["-i", str(music_path), "-c:a", "pcm_s16le", str(out)])
        return str(out)


def _mix_voice_and_music(
    voice_path: str,
    music_path: str,
    output: Path,
    voice_level_db: float,
    target_duration: float | None,
) -> str:
    """Mix voice + music with proper levels and limiter."""
    voice_vol = _db_to_mult(voice_level_db)

    # Build filter complex
    # [0] = voice, [1] = music (already ducked and at base volume)
    filter_parts = [
        f"[0:a]volume={voice_vol},apad[voice]",
        f"[1:a]anull[music]",
        f"[voice][music]amix=inputs=2:duration=longest:dropout_transition=0.05,"
        f"alimiter=limit={_db_to_mult(LIMITER_THRESHOLD_DB)}[out]",
    ]
    fc = ";".join(filter_parts)

    args = [
        "-i", voice_path,
        "-i", music_path,
        "-filter_complex", fc,
        "-map", "[out]",
        "-ar", "44100",
        "-ac", "2",
        "-c:a", "pcm_s16le",
    ]

    if target_duration:
        args.extend(["-t", str(target_duration)])

    args.append(str(output))
    run_ffmpeg(args)

    logger.info("audio_mixed", voice=voice_path, music=music_path, output=str(output))
    return str(output)


def _process_voice_only(
    voice_path: str,
    output: Path,
    voice_level_db: float,
) -> str:
    """Process voice-only audio with level adjustment."""
    voice_vol = _db_to_mult(voice_level_db)

    run_ffmpeg([
        "-i", voice_path,
        "-af", f"volume={voice_vol},alimiter=limit={_db_to_mult(LIMITER_THRESHOLD_DB)}",
        "-ar", "44100",
        "-ac", "2",
        "-c:a", "pcm_s16le",
        str(output),
    ])

    return str(output)


def mux_audio_to_video(
    video_path: str | Path,
    audio_path: str | Path,
    output_path: str | Path,
    *,
    replace_audio: bool = True,
) -> Path:
    """Mux a mixed audio track onto a video file.

    Args:
        video_path: Input video (may or may not have audio).
        audio_path: Mixed audio track.
        output_path: Output path for video with audio.
        replace_audio: If True, replace existing audio. If False, add as additional stream.

    Returns:
        Path to the output file.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    run_ffmpeg([
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(out),
    ])

    logger.info("audio_muxed", video=str(video_path), audio=str(audio_path))
    return out


def _db_to_mult(db: float) -> float:
    return 10 ** (db / 20.0)

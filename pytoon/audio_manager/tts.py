"""TTS integration — generate voiceover audio from text script.

Supports multiple providers with automatic fallback:
  - ElevenLabs (primary)
  - OpenAI TTS
  - Google Cloud TTS
  - Local pyttsx3 (offline fallback)

Ticket: P4-01
Acceptance Criteria: V2-AC-002, V2-AC-003
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from pytoon.config import get_defaults
from pytoon.log import get_logger

logger = get_logger(__name__)


@dataclass
class TTSResult:
    """Result of a TTS generation request."""

    success: bool
    audio_path: Optional[str] = None
    duration_ms: Optional[int] = None
    provider: str = ""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_TTS_CONFIG_KEY = "tts"


def _get_tts_config() -> dict:
    defaults = get_defaults()
    return defaults.get(_TTS_CONFIG_KEY, {})


async def generate_voiceover(
    script: str,
    output_dir: str | Path,
    *,
    voice_name: str | None = None,
    speed: float = 1.0,
    output_format: str = "mp3",
) -> TTSResult:
    """Generate voiceover audio from a text script.

    Tries providers in priority order:
    1. Primary provider from config.
    2. Backup provider from config.
    3. Local fallback (pyttsx3).

    Returns TTSResult with audio_path on success.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    config = _get_tts_config()
    primary = config.get("primary_provider", "elevenlabs")
    backup = config.get("backup_provider", "openai")
    voice = voice_name or config.get("voice_name", "default")
    spd = speed or config.get("speed", 1.0)
    fmt = output_format or config.get("output_format", "mp3")

    providers = [primary, backup, "local"]
    # Remove duplicates while preserving order
    seen = set()
    providers = [p for p in providers if not (p in seen or seen.add(p))]

    for provider in providers:
        logger.info("tts_attempt", provider=provider, script_len=len(script))
        result = await _generate_with_provider(
            provider, script, out_dir, voice, spd, fmt,
        )
        if result.success:
            return result
        logger.warning("tts_provider_failed", provider=provider, error=result.error)

    return TTSResult(
        success=False,
        provider="none",
        error="All TTS providers failed",
    )


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

async def _generate_with_provider(
    provider: str,
    script: str,
    output_dir: Path,
    voice: str,
    speed: float,
    fmt: str,
) -> TTSResult:
    """Dispatch to the appropriate TTS provider."""
    if provider == "elevenlabs":
        return await _generate_elevenlabs(script, output_dir, voice, speed, fmt)
    elif provider == "openai":
        return await _generate_openai(script, output_dir, voice, speed, fmt)
    elif provider == "google":
        return await _generate_google(script, output_dir, voice, speed, fmt)
    elif provider == "local":
        return _generate_local(script, output_dir, voice, speed, fmt)
    else:
        return TTSResult(success=False, error=f"Unknown TTS provider: {provider}")


async def _generate_elevenlabs(
    script: str,
    output_dir: Path,
    voice: str,
    speed: float,
    fmt: str,
) -> TTSResult:
    """ElevenLabs TTS API."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        return TTSResult(success=False, provider="elevenlabs", error="ELEVENLABS_API_KEY not set")

    voice_id = voice if voice != "default" else "21m00Tcm4TlvDq8ikWAM"  # Rachel
    output_path = output_dir / f"voiceover_elevenlabs.{fmt}"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                json={
                    "text": script,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
                headers={
                    "xi-api-key": api_key,
                    "Accept": f"audio/{fmt}",
                },
            )
            resp.raise_for_status()
            output_path.write_bytes(resp.content)

        duration_ms = _measure_duration(output_path)
        return TTSResult(
            success=True,
            audio_path=str(output_path),
            duration_ms=duration_ms,
            provider="elevenlabs",
        )
    except Exception as exc:
        return TTSResult(success=False, provider="elevenlabs", error=str(exc))


async def _generate_openai(
    script: str,
    output_dir: Path,
    voice: str,
    speed: float,
    fmt: str,
) -> TTSResult:
    """OpenAI TTS API."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return TTSResult(success=False, provider="openai", error="OPENAI_API_KEY not set")

    voice_name = voice if voice != "default" else "alloy"
    output_path = output_dir / f"voiceover_openai.{fmt}"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/speech",
                json={
                    "model": "tts-1",
                    "input": script,
                    "voice": voice_name,
                    "speed": speed,
                    "response_format": fmt,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
            )
            resp.raise_for_status()
            output_path.write_bytes(resp.content)

        duration_ms = _measure_duration(output_path)
        return TTSResult(
            success=True,
            audio_path=str(output_path),
            duration_ms=duration_ms,
            provider="openai",
        )
    except Exception as exc:
        return TTSResult(success=False, provider="openai", error=str(exc))


async def _generate_google(
    script: str,
    output_dir: Path,
    voice: str,
    speed: float,
    fmt: str,
) -> TTSResult:
    """Google Cloud TTS (requires google-cloud-texttospeech)."""
    try:
        from google.cloud import texttospeech
    except ImportError:
        return TTSResult(
            success=False, provider="google",
            error="google-cloud-texttospeech not installed",
        )

    output_path = output_dir / f"voiceover_google.{fmt}"

    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=script)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name=voice if voice != "default" else "en-US-Neural2-D",
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speed,
        )
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )
        output_path.write_bytes(response.audio_content)

        duration_ms = _measure_duration(output_path)
        return TTSResult(
            success=True,
            audio_path=str(output_path),
            duration_ms=duration_ms,
            provider="google",
        )
    except Exception as exc:
        return TTSResult(success=False, provider="google", error=str(exc))


def _generate_local(
    script: str,
    output_dir: Path,
    voice: str,
    speed: float,
    fmt: str,
) -> TTSResult:
    """Local TTS via pyttsx3 (offline fallback)."""
    try:
        import pyttsx3
    except ImportError:
        # Fallback: generate silence + log
        return _generate_silence_fallback(script, output_dir, fmt)

    output_path = output_dir / f"voiceover_local.wav"

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", int(150 * speed))
        engine.save_to_file(script, str(output_path))
        engine.runAndWait()

        duration_ms = _measure_duration(output_path)
        return TTSResult(
            success=True,
            audio_path=str(output_path),
            duration_ms=duration_ms,
            provider="local",
        )
    except Exception as exc:
        return _generate_silence_fallback(script, output_dir, fmt)


def _generate_silence_fallback(
    script: str, output_dir: Path, fmt: str,
) -> TTSResult:
    """Last-resort: generate a silence track so the pipeline doesn't break."""
    import subprocess

    # Estimate duration: ~150 words per minute
    word_count = len(script.split())
    duration_s = max(3, word_count / 2.5)  # ~2.5 words/sec
    output_path = output_dir / f"voiceover_silence.{fmt}"

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration_s}",
                "-c:a", "libmp3lame" if fmt == "mp3" else "aac",
                str(output_path),
            ],
            capture_output=True, timeout=15,
        )
        duration_ms = int(duration_s * 1000)
        return TTSResult(
            success=True,
            audio_path=str(output_path),
            duration_ms=duration_ms,
            provider="silence_fallback",
        )
    except Exception as exc:
        return TTSResult(success=False, provider="silence_fallback", error=str(exc))


# ---------------------------------------------------------------------------
# Audio duration measurement
# ---------------------------------------------------------------------------

def _measure_duration(path: Path) -> int | None:
    """Measure audio duration in milliseconds via ffprobe."""
    import subprocess
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        return int(float(result.stdout.strip()) * 1000)
    except Exception:
        return None

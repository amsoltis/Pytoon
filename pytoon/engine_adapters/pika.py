"""Pika Labs engine adapter — stylized AI video generation.

Implements async submit → poll → download workflow against Pika's API.
Best for: stylized scenes, creative effects, energetic visuals.

Ticket: P3-03
Acceptance Criteria: V2-AC-010, V2-AC-011
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from pytoon.config import get_engine_config
from pytoon.engine_adapters.external_base import EngineResult, ExternalEngineAdapter
from pytoon.log import get_logger

logger = get_logger(__name__)

_API_BASE = "https://api.pika.art/v1"


class PikaAdapter(ExternalEngineAdapter):
    """Pika Labs AI video generation adapter."""

    @property
    def name(self) -> str:
        return "pika"

    def __init__(self):
        self._api_key = os.environ.get("PIKA_API_KEY", "")
        cfg = get_engine_config().get("v2", {}).get("engines", {}).get("pika", {})
        self._timeout = cfg.get("timeout_seconds", 60)
        self._max_clip_duration = cfg.get("max_clip_duration_seconds", 8)
        self._poll_interval = 4
        self._enabled = cfg.get("enabled", True)

    # ---- Interface implementation ------------------------------------------

    async def generate(
        self,
        *,
        prompt: str,
        duration_seconds: float,
        width: int = 1080,
        height: int = 1920,
        image_path: Optional[str] = None,
        seed: Optional[int] = None,
        style_hints: dict[str, Any] | None = None,
        output_dir: str = "",
    ) -> EngineResult:
        t0 = time.monotonic()

        if not self._api_key:
            return EngineResult(
                success=False,
                engine_name=self.name,
                error="PIKA_API_KEY not set",
                error_code="missing_api_key",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )

        clip_duration = min(duration_seconds, self._max_clip_duration)

        payload: dict[str, Any] = {
            "prompt": prompt,
            "duration": int(clip_duration),
            "aspectRatio": "9:16",
            "resolution": f"{width}x{height}",
        }
        if seed is not None:
            payload["seed"] = seed

        # Pika supports style presets
        if style_hints:
            if style_hints.get("mood") in ("stylized", "creative", "artistic"):
                payload["style"] = "anime"  # Example: select style variant
            elif style_hints.get("mood") == "cinematic":
                payload["style"] = "cinematic"

        try:
            # Upload image if provided
            image_id = None
            if image_path and Path(image_path).exists():
                image_id = await self._upload_image(image_path)
                if image_id:
                    payload["imageId"] = image_id

            # Submit generation
            gen_id = await self._submit(payload)
            logger.info("pika_submitted", generation_id=gen_id, prompt=prompt[:60])

            # Poll for completion
            result_url = await self._poll(gen_id)

            # Download clip
            out_dir = Path(output_dir) if output_dir else Path("storage/_engine_tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            clip_path = out_dir / f"pika_{gen_id}_{uuid.uuid4().hex[:6]}.mp4"

            await self._download(result_url, clip_path)

            elapsed = (time.monotonic() - t0) * 1000
            logger.info("pika_complete", generation_id=gen_id, elapsed_ms=round(elapsed))

            return EngineResult(
                success=True,
                clip_path=str(clip_path),
                clip_url=result_url,
                engine_name=self.name,
                generation_id=gen_id,
                seed=seed,
                elapsed_ms=elapsed,
            )

        except _ModerationError as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.warning("pika_moderation", error=str(exc))
            return EngineResult(
                success=False,
                engine_name=self.name,
                error=str(exc),
                error_code="moderation_rejection",
                moderation_flagged=True,
                elapsed_ms=elapsed,
            )

        except _RateLimitError as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.warning("pika_rate_limited", error=str(exc))
            return EngineResult(
                success=False,
                engine_name=self.name,
                error=str(exc),
                error_code="rate_limited",
                rate_limited=True,
                elapsed_ms=elapsed,
            )

        except TimeoutError as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.error("pika_timeout", error=str(exc))
            return EngineResult(
                success=False,
                engine_name=self.name,
                error=str(exc),
                error_code="timeout",
                elapsed_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.error("pika_error", error=str(exc))
            return EngineResult(
                success=False,
                engine_name=self.name,
                error=str(exc),
                error_code="api_error",
                elapsed_ms=elapsed,
            )

    async def health_check(self) -> bool:
        if not self._api_key or not self._enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_API_BASE}/health",
                    headers=self._headers(),
                )
                return resp.status_code in (200, 401)
        except Exception:
            return False

    def max_duration(self) -> float:
        return self._max_clip_duration

    def supports_image_input(self) -> bool:
        return True

    # ---- Internal helpers --------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _upload_image(self, image_path: str) -> str | None:
        """Upload an image for image-to-video generation."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                with open(image_path, "rb") as f:
                    resp = await client.post(
                        f"{_API_BASE}/images/upload",
                        files={"file": f},
                        headers={"Authorization": f"Bearer {self._api_key}"},
                    )
                    if resp.status_code == 200:
                        return resp.json().get("id")
        except Exception as exc:
            logger.warning("pika_image_upload_failed", error=str(exc))
        return None

    async def _submit(self, payload: dict) -> str:
        """Submit a generation request and return the generation ID."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_API_BASE}/generations",
                json=payload,
                headers=self._headers(),
            )
            if resp.status_code == 429:
                raise _RateLimitError("Pika rate limit exceeded")
            if resp.status_code in (400, 422):
                data = resp.json()
                msg = str(data)
                if "moderation" in msg.lower() or "safety" in msg.lower():
                    raise _ModerationError(f"Content moderation: {data}")
            resp.raise_for_status()
            data = resp.json()
            return data.get("id", data.get("generationId", ""))

    async def _poll(self, gen_id: str) -> str:
        """Poll until generation completes and return the output URL."""
        deadline = time.monotonic() + self._timeout

        async with httpx.AsyncClient(timeout=15) as client:
            while time.monotonic() < deadline:
                await asyncio.sleep(self._poll_interval)
                resp = await client.get(
                    f"{_API_BASE}/generations/{gen_id}",
                    headers=self._headers(),
                )
                if resp.status_code == 429:
                    await asyncio.sleep(8)
                    continue
                if resp.status_code != 200:
                    continue

                data = resp.json()
                status = data.get("status", "")

                if status in ("completed", "succeeded"):
                    video_url = data.get("videoUrl") or data.get("output", {}).get("url", "")
                    if video_url:
                        return video_url
                    raise RuntimeError("Pika generation succeeded but no video URL")

                if status == "failed":
                    reason = data.get("error", "Unknown failure")
                    if "moderation" in str(reason).lower():
                        raise _ModerationError(f"Moderation rejection: {reason}")
                    raise RuntimeError(f"Pika generation failed: {reason}")

        raise TimeoutError(f"Pika generation {gen_id} timed out after {self._timeout}s")

    async def _download(self, url: str, output_path: Path) -> None:
        """Download a clip from URL to local path."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            output_path.write_bytes(resp.content)


class _ModerationError(Exception):
    pass

class _RateLimitError(Exception):
    pass

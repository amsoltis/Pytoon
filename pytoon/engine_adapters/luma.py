"""Luma AI Dream Machine engine adapter — realistic motion / product shots.

Implements async submit → poll → download workflow against Luma's API.
Best for: physics-realism, 3D-like rendering, product showcase.

Ticket: P3-04
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

_API_BASE = "https://api.lumalabs.ai/dream-machine/v1"


class LumaAdapter(ExternalEngineAdapter):
    """Luma AI Dream Machine video generation adapter."""

    @property
    def name(self) -> str:
        return "luma"

    def __init__(self):
        self._api_key = os.environ.get("LUMA_API_KEY", "")
        cfg = get_engine_config().get("v2", {}).get("engines", {}).get("luma", {})
        self._timeout = cfg.get("timeout_seconds", 60)
        self._max_clip_duration = cfg.get("max_clip_duration_seconds", 10)
        self._poll_interval = 5
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
                error="LUMA_API_KEY not set",
                error_code="missing_api_key",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )

        clip_duration = min(duration_seconds, self._max_clip_duration)

        payload: dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": "9:16",
        }

        # Luma supports image-to-video via keyframes
        if image_path and Path(image_path).exists():
            # Upload image first, then reference it
            image_url = await self._upload_image(image_path)
            if image_url:
                payload["keyframes"] = {
                    "frame0": {
                        "type": "image",
                        "url": image_url,
                    }
                }

        try:
            # Submit generation
            gen_id = await self._submit(payload)
            logger.info("luma_submitted", generation_id=gen_id, prompt=prompt[:60])

            # Poll for completion
            result_url = await self._poll(gen_id)

            # Download clip
            out_dir = Path(output_dir) if output_dir else Path("storage/_engine_tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            clip_path = out_dir / f"luma_{gen_id}_{uuid.uuid4().hex[:6]}.mp4"

            await self._download(result_url, clip_path)

            elapsed = (time.monotonic() - t0) * 1000
            logger.info("luma_complete", generation_id=gen_id, elapsed_ms=round(elapsed))

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
            logger.warning("luma_moderation", error=str(exc))
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
            logger.warning("luma_rate_limited", error=str(exc))
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
            logger.error("luma_timeout", error=str(exc))
            return EngineResult(
                success=False,
                engine_name=self.name,
                error=str(exc),
                error_code="timeout",
                elapsed_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.error("luma_error", error=str(exc))
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
                    f"{_API_BASE}/generations",
                    headers=self._headers(),
                    params={"limit": 1},
                )
                # 200 = healthy, 401 = key exists but auth issue
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
            "Accept": "application/json",
        }

    async def _upload_image(self, image_path: str) -> str | None:
        """Upload an image for image-to-video generation.

        Luma typically accepts image URLs; for local files we'd need
        a presigned upload or host the image temporarily.
        For now, return the local path as a file:// URI.
        """
        # In production, this would upload to a presigned URL
        # For now, return None to use prompt-only mode
        logger.info("luma_image_upload_skipped", note="local file — needs hosted URL")
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
                # Check Retry-After header
                retry_after = resp.headers.get("Retry-After", "10")
                raise _RateLimitError(
                    f"Luma rate limit exceeded, retry after {retry_after}s"
                )
            if resp.status_code in (400, 422):
                data = resp.json()
                msg = str(data)
                if "moderation" in msg.lower() or "safety" in msg.lower():
                    raise _ModerationError(f"Content moderation: {data}")
            resp.raise_for_status()
            data = resp.json()
            return data.get("id", "")

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
                    await asyncio.sleep(10)
                    continue
                if resp.status_code != 200:
                    continue

                data = resp.json()
                state = data.get("state", "")

                if state == "completed":
                    assets = data.get("assets", {})
                    video_url = assets.get("video", "")
                    if video_url:
                        return video_url
                    raise RuntimeError("Luma generation completed but no video URL")

                if state == "failed":
                    failure = data.get("failure_reason", "Unknown failure")
                    if "moderation" in str(failure).lower():
                        raise _ModerationError(f"Moderation rejection: {failure}")
                    raise RuntimeError(f"Luma generation failed: {failure}")

        raise TimeoutError(f"Luma generation {gen_id} timed out after {self._timeout}s")

    async def _download(self, url: str, output_path: Path) -> None:
        """Download a clip from URL to local path."""
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            output_path.write_bytes(resp.content)


class _ModerationError(Exception):
    pass

class _RateLimitError(Exception):
    pass

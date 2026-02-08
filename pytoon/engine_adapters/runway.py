"""Runway AI engine adapter — Gen-2 / Gen-4 video generation.

Implements async submit → poll → download workflow against Runway's API.
Handles HTTP errors, content moderation rejections, timeouts, and rate limits.

Ticket: P3-02
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

_API_BASE = "https://api.dev.runwayml.com/v1"


class RunwayAdapter(ExternalEngineAdapter):
    """Runway Gen-2/Gen-4 video generation adapter."""

    @property
    def name(self) -> str:
        return "runway"

    def __init__(self):
        self._api_key = os.environ.get("RUNWAY_API_KEY", "")
        cfg = get_engine_config().get("v2", {}).get("engines", {}).get("runway", {})
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
                error="RUNWAY_API_KEY not set",
                error_code="missing_api_key",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )

        # Clamp duration to engine max
        clip_duration = min(duration_seconds, self._max_clip_duration)

        # Build request payload
        payload: dict[str, Any] = {
            "promptText": prompt,
            "model": "gen3a_turbo",
            "duration": int(clip_duration),
            "ratio": "9:16",
        }
        if seed is not None:
            payload["seed"] = seed
        if image_path and Path(image_path).exists():
            # Runway supports init_image for image-to-video
            payload["promptImage"] = f"file://{image_path}"

        try:
            # Submit generation
            gen_id = await self._submit(payload)
            logger.info("runway_submitted", generation_id=gen_id, prompt=prompt[:60])

            # Poll for completion
            result_url = await self._poll(gen_id)

            # Download clip
            out_dir = Path(output_dir) if output_dir else Path("storage/_engine_tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            clip_path = out_dir / f"runway_{gen_id}_{uuid.uuid4().hex[:6]}.mp4"

            await self._download(result_url, clip_path)

            elapsed = (time.monotonic() - t0) * 1000
            logger.info("runway_complete", generation_id=gen_id, elapsed_ms=round(elapsed))

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
            logger.warning("runway_moderation", error=str(exc))
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
            logger.warning("runway_rate_limited", error=str(exc))
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
            logger.error("runway_timeout", error=str(exc))
            return EngineResult(
                success=False,
                engine_name=self.name,
                error=str(exc),
                error_code="timeout",
                elapsed_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.error("runway_error", error=str(exc))
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
                    f"{_API_BASE}/tasks",
                    headers=self._headers(),
                )
                return resp.status_code in (200, 401)  # 401 = key exists but may be rate limited
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
            "X-Runway-Version": "2024-11-06",
        }

    async def _submit(self, payload: dict) -> str:
        """Submit a generation request and return the task ID."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_API_BASE}/image_to_video",
                json=payload,
                headers=self._headers(),
            )
            if resp.status_code == 429:
                raise _RateLimitError("Runway rate limit exceeded")
            if resp.status_code == 422:
                data = resp.json()
                if "moderation" in str(data).lower() or "content policy" in str(data).lower():
                    raise _ModerationError(f"Content moderation: {data}")
                resp.raise_for_status()
            resp.raise_for_status()
            data = resp.json()
            return data.get("id", "")

    async def _poll(self, task_id: str) -> str:
        """Poll until the task completes and return the output URL."""
        deadline = time.monotonic() + self._timeout

        async with httpx.AsyncClient(timeout=15) as client:
            while time.monotonic() < deadline:
                await asyncio.sleep(self._poll_interval)
                resp = await client.get(
                    f"{_API_BASE}/tasks/{task_id}",
                    headers=self._headers(),
                )
                if resp.status_code == 429:
                    await asyncio.sleep(10)  # Back off on rate limit during poll
                    continue
                if resp.status_code != 200:
                    continue

                data = resp.json()
                status = data.get("status", "")

                if status == "SUCCEEDED":
                    output = data.get("output", [])
                    if output:
                        return output[0]
                    raise RuntimeError("Runway task succeeded but no output URL")

                if status == "FAILED":
                    failure = data.get("failure", "Unknown failure")
                    if "moderation" in str(failure).lower():
                        raise _ModerationError(f"Moderation rejection: {failure}")
                    raise RuntimeError(f"Runway task failed: {failure}")

        raise TimeoutError(f"Runway task {task_id} timed out after {self._timeout}s")

    async def _download(self, url: str, output_path: Path) -> None:
        """Download a clip from URL to local path."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            output_path.write_bytes(resp.content)


# ---- Custom exceptions -----------------------------------------------------

class _ModerationError(Exception):
    pass

class _RateLimitError(Exception):
    pass

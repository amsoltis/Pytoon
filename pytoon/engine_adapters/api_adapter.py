"""Hosted API engine adapter (generic interface-compatible provider)."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Optional

import httpx

from pytoon.config import get_settings
from pytoon.log import get_logger
from pytoon.engine_adapters.base import EngineAdapter, SegmentResult

logger = get_logger(__name__)


class APIEngineAdapter(EngineAdapter):
    name = "api_luma"

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.api_engine_base_url.rstrip("/")
        self.api_key = self.settings.api_engine_key

    # ---- health -----------------------------------------------------------

    async def health_check(self) -> bool:
        if not self.base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.base_url}/health",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False

    # ---- render -----------------------------------------------------------

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

        payload: dict[str, Any] = {
            "prompt": prompt,
            "duration_seconds": duration_seconds,
            "width": width,
            "height": height,
            "archetype": archetype,
        }
        if image_path:
            payload["image_url"] = image_path
        if seed is not None:
            payload["seed"] = seed

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/generations",
                    json=payload,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                gen = resp.json()
                generation_id = gen.get("id", "")

            # Poll for result
            output_url = await self._poll_generation(generation_id)
            elapsed = (time.monotonic() - t0) * 1000

            logger.info(
                "segment_rendered",
                job_id=job_id,
                segment_index=segment_index,
                engine=self.name,
                elapsed_ms=elapsed,
            )
            return SegmentResult(
                success=True,
                artifact_path=output_url,
                engine_name=self.name,
                seed=seed,
                elapsed_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.error(
                "segment_render_failed",
                job_id=job_id,
                segment_index=segment_index,
                engine=self.name,
                error=str(exc),
            )
            return SegmentResult(
                success=False,
                engine_name=self.name,
                elapsed_ms=elapsed,
                error=str(exc),
            )

    # ---- capabilities -----------------------------------------------------

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": "api",
            "archetypes": ["PRODUCT_HERO", "OVERLAY", "MEME_TEXT"],
            "max_segment_duration": 4,
        }

    # ---- internal ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def _poll_generation(
        self, generation_id: str, max_wait: int = 300, interval: int = 5,
    ) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            for _ in range(max_wait // interval):
                await asyncio.sleep(interval)
                resp = await client.get(
                    f"{self.base_url}/v1/generations/{generation_id}",
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                state = data.get("state", "")
                if state == "completed":
                    return data.get("video", {}).get("url", "")
                if state == "failed":
                    raise RuntimeError(
                        f"API generation {generation_id} failed: {data.get('failure_reason')}"
                    )
        raise TimeoutError(f"API generation {generation_id} timed out after {max_wait}s")

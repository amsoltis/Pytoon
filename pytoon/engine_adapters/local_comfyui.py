"""Local ComfyUI engine adapter."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from pytoon.config import get_engine_config, get_settings
from pytoon.log import get_logger
from pytoon.engine_adapters.base import EngineAdapter, SegmentResult

logger = get_logger(__name__)


class LocalComfyUIAdapter(EngineAdapter):
    name = "local_comfyui"

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.comfyui_base_url.rstrip("/")
        self.engine_cfg = get_engine_config().get("adapters", {}).get("local_comfyui", {})
        self.workflow_map = self.engine_cfg.get("workflows", {})

    # ---- health -----------------------------------------------------------

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/system_stats")
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
        workflow_name = self.workflow_map.get(archetype, "overlay_product")
        actual_seed = seed if seed is not None else int(uuid.uuid4().int % (2**31))

        # Build ComfyUI workflow payload
        workflow = self._build_workflow(
            workflow_name=workflow_name,
            prompt=prompt,
            duration_seconds=duration_seconds,
            image_path=image_path,
            mask_path=mask_path,
            width=width,
            height=height,
            seed=actual_seed,
        )

        try:
            prompt_id = await self._queue_prompt(workflow)
            output_path = await self._poll_result(prompt_id, job_id, segment_index)
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
                artifact_path=output_path,
                engine_name=self.name,
                seed=actual_seed,
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
            "type": "local",
            "archetypes": list(self.workflow_map.keys()),
            "max_segment_duration": 4,
        }

    # ---- internal ---------------------------------------------------------

    def _build_workflow(
        self,
        workflow_name: str,
        prompt: str,
        duration_seconds: float,
        image_path: str | None,
        mask_path: str | None,
        width: int,
        height: int,
        seed: int,
    ) -> dict[str, Any]:
        """Build a ComfyUI API-format workflow dict.

        In production this would load a real workflow JSON template
        and fill in the nodes. For V1 we build a minimal placeholder
        structure that ComfyUI can execute.
        """
        # Placeholder workflow — replace with actual workflow templates
        workflow: dict[str, Any] = {
            "client_id": uuid.uuid4().hex,
            "prompt": {
                "1": {
                    "class_type": "KSampler",
                    "inputs": {
                        "seed": seed,
                        "steps": 20,
                        "cfg": 7.0,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "denoise": 1.0,
                    },
                },
                "2": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": prompt},
                },
            },
            "_meta": {
                "workflow_name": workflow_name,
                "width": width,
                "height": height,
                "duration_seconds": duration_seconds,
            },
        }
        if image_path:
            workflow["prompt"]["3"] = {
                "class_type": "LoadImage",
                "inputs": {"image": image_path},
            }
        if mask_path:
            workflow["prompt"]["4"] = {
                "class_type": "LoadImage",
                "inputs": {"image": mask_path},
            }
        return workflow

    async def _queue_prompt(self, workflow: dict[str, Any]) -> str:
        """Submit workflow to ComfyUI /prompt endpoint."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/prompt",
                json=workflow,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["prompt_id"]

    async def _poll_result(
        self, prompt_id: str, job_id: str, segment_index: int,
        max_wait: int = 300, interval: int = 2,
    ) -> str:
        """Poll ComfyUI /history until the prompt completes."""
        async with httpx.AsyncClient(timeout=10) as client:
            for _ in range(max_wait // interval):
                await asyncio.sleep(interval)
                resp = await client.get(f"{self.base_url}/history/{prompt_id}")
                if resp.status_code != 200:
                    continue
                history = resp.json()
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    # Find first video/image output
                    for node_id, node_out in outputs.items():
                        if "videos" in node_out:
                            vid = node_out["videos"][0]
                            return f"{self.base_url}/view?filename={vid['filename']}&subfolder={vid.get('subfolder', '')}"
                        if "images" in node_out:
                            img = node_out["images"][0]
                            return f"{self.base_url}/view?filename={img['filename']}&subfolder={img.get('subfolder', '')}"
        raise TimeoutError(f"ComfyUI prompt {prompt_id} did not complete within {max_wait}s")

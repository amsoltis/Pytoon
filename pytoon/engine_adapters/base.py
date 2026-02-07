"""Abstract base for all engine adapters."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SegmentResult:
    """Result of rendering a single segment."""
    success: bool
    artifact_path: Optional[str] = None   # local path to rendered clip
    artifact_uri: Optional[str] = None     # storage URI once persisted
    engine_name: str = ""
    seed: Optional[int] = None
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EngineAdapter(abc.ABC):
    """Every engine adapter must implement these methods."""

    name: str = "base"

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Return True if the engine is reachable and healthy."""
        ...

    @abc.abstractmethod
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
        """Render a single video segment and return the result."""
        ...

    @abc.abstractmethod
    def get_capabilities(self) -> dict[str, Any]:
        """Return what this adapter supports (archetypes, max duration, etc.)."""
        ...

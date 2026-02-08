"""Abstract base class for external AI video generation engines (V2).

All external engines (Runway, Pika, Luma) extend ExternalEngineAdapter.
This sits alongside the V1 EngineAdapter base (base.py) — V1 adapters
continue to work; V2 adapters implement this richer interface.

Ticket: P3-01
Acceptance Criteria: V2-AC-010, V2-AC-011
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EngineResult:
    """Result of an external AI engine generation request."""

    success: bool
    clip_path: Optional[str] = None       # local path to downloaded clip
    clip_url: Optional[str] = None        # remote URL before download
    engine_name: str = ""
    generation_id: Optional[str] = None   # engine-side ID for tracking
    seed: Optional[int] = None
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    error_code: Optional[str] = None      # e.g. "moderation_rejection", "timeout"
    moderation_flagged: bool = False       # True if content moderation triggered
    rate_limited: bool = False             # True if rate limit hit
    metadata: dict[str, Any] = field(default_factory=dict)


class ExternalEngineAdapter(abc.ABC):
    """Base class for V2 external AI video generation engines.

    Every external engine adapter must implement:
      - generate()       — submit a generation and return the result
      - health_check()   — verify the engine is reachable
      - name             — unique adapter identifier
      - max_duration()   — maximum supported clip duration in seconds
      - supports_image_input() — whether the engine supports image conditioning
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique engine identifier (e.g. 'runway', 'pika', 'luma')."""
        ...

    @abc.abstractmethod
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
        """Submit a generation request and return the result.

        Implementations must:
        1. Build the API request from prompt + parameters.
        2. Submit asynchronously.
        3. Poll for completion (or await callback).
        4. Download the resulting clip to `output_dir`.
        5. Return EngineResult with clip_path on success.

        On failure (HTTP error, timeout, moderation), return
        EngineResult with success=False and appropriate error fields.
        """
        ...

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Return True if the engine API is reachable and keys are valid."""
        ...

    @abc.abstractmethod
    def max_duration(self) -> float:
        """Maximum clip duration in seconds this engine can produce."""
        ...

    @abc.abstractmethod
    def supports_image_input(self) -> bool:
        """Whether this engine supports image-to-video / image conditioning."""
        ...

    def get_capabilities(self) -> dict[str, Any]:
        """Return capability dict for the Engine Manager."""
        return {
            "name": self.name,
            "type": "external",
            "max_duration_seconds": self.max_duration(),
            "supports_image_input": self.supports_image_input(),
        }

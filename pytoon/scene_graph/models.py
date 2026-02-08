"""Pydantic models for the V2 Scene Graph (schema version 2.0).

Translates the frozen Scene Graph JSON schema (schemas/scene_graph_v2.json)
into validated Python models.  Used by the Scene Planner, Timeline Orchestrator,
Engine Manager, and Audio/Caption Manager.

Ticket: P2-01
Acceptance Criteria: V2-AC-001, V2-AC-020
"""

from __future__ import annotations

import enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MediaType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"


class EngineId(str, enum.Enum):
    RUNWAY = "runway"
    PIKA = "pika"
    LUMA = "luma"
    LOCAL = "local"


class VisualEffect(str, enum.Enum):
    KEN_BURNS_ZOOM = "ken_burns_zoom"
    KEN_BURNS_PAN = "ken_burns_pan"
    SLOW_ZOOM_IN = "slow_zoom_in"
    SLOW_ZOOM_OUT = "slow_zoom_out"
    STATIC = "static"


class TransitionType(str, enum.Enum):
    CUT = "cut"
    FADE = "fade"
    FADE_BLACK = "fade_black"
    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"


class OverlayType(str, enum.Enum):
    PRODUCT_IMAGE = "product_image"
    LOGO = "logo"
    TEXT = "text"
    GRAPHIC = "graphic"


class OverlayPosition(str, enum.Enum):
    CENTER = "center"
    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class SceneMedia(BaseModel):
    """Primary media content for a scene."""

    type: MediaType
    asset: Optional[str] = None
    engine: Optional[EngineId] = None
    prompt: Optional[str] = None
    effect: Optional[VisualEffect] = None

    @model_validator(mode="after")
    def _validate_engine_prompt(self) -> "SceneMedia":
        if self.engine is not None and self.prompt is None:
            raise ValueError("media.prompt is required when media.engine is set")
        if (
            self.type == MediaType.VIDEO
            and self.engine is None
            and self.asset is None
            and self.prompt is None
        ):
            raise ValueError(
                "video-type media requires at least one of: engine, asset, or prompt"
            )
        return self


class SceneStyle(BaseModel):
    """Visual style metadata for a scene."""

    mood: Optional[str] = None
    camera_motion: Optional[str] = None
    lighting: Optional[str] = None


class SceneOverlay(BaseModel):
    """Overlay element rendered on top of the primary media."""

    type: OverlayType
    asset: str
    position: OverlayPosition = OverlayPosition.CENTER
    scale: float = Field(default=1.0, ge=0.01, le=2.0)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class GlobalAudio(BaseModel):
    """Global audio configuration: voice script, voice file, background music."""

    voiceScript: Optional[str] = None
    voiceFile: Optional[str] = None
    backgroundMusic: Optional[str] = None


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

class Scene(BaseModel):
    """A single scene node in the Scene Graph."""

    id: int = Field(ge=1, description="Unique scene identifier")
    description: str = Field(min_length=1)
    duration: int = Field(
        ge=1000, le=60000,
        description="Scene duration in milliseconds (1s–60s)",
    )
    media: SceneMedia
    caption: str = ""
    audio: Optional[str] = None
    style: SceneStyle = Field(default_factory=SceneStyle)
    overlays: list[SceneOverlay] = Field(default_factory=list)
    transition: TransitionType = TransitionType.FADE


# ---------------------------------------------------------------------------
# SceneGraph  — top-level model
# ---------------------------------------------------------------------------

class SceneGraph(BaseModel):
    """Top-level V2 Scene Graph.

    Validation rules:
    - At least one scene is required.
    - Total duration across all scenes must not exceed 60 000 ms.
    - Scene IDs must be unique.
    """

    version: str = "2.0"
    scenes: list[Scene] = Field(min_length=1)
    globalAudio: GlobalAudio = Field(default_factory=GlobalAudio)

    @model_validator(mode="after")
    def _validate_scene_graph(self) -> "SceneGraph":
        # Unique scene IDs
        ids = [s.id for s in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("Scene IDs must be unique within the scene graph")

        # Total duration ≤ 60 000 ms
        total = sum(s.duration for s in self.scenes)
        if total > 60_000:
            raise ValueError(
                f"Total scene duration ({total}ms) exceeds maximum of 60000ms (60s)"
            )

        return self

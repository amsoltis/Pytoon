"""Pydantic models — the canonical RenderSpec and supporting types."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Archetype(str, enum.Enum):
    PRODUCT_HERO = "PRODUCT_HERO"
    OVERLAY = "OVERLAY"
    MEME_TEXT = "MEME_TEXT"


class EnginePolicy(str, enum.Enum):
    LOCAL_ONLY = "local_only"
    LOCAL_PREFERRED = "local_preferred"
    API_ONLY = "api_only"


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    RENDERING_SEGMENTS = "RENDERING_SEGMENTS"
    ASSEMBLING = "ASSEMBLING"
    DONE = "DONE"
    FAILED = "FAILED"


class SegmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class CaptionTiming(BaseModel):
    start: float
    end: float
    text: str


class CaptionsPlan(BaseModel):
    hook: str = ""
    beats: list[str] = Field(default_factory=list)
    cta: str = ""
    timings: list[CaptionTiming] = Field(default_factory=list)


class AudioPlan(BaseModel):
    music_level_db: float = -18.0
    voice_level_db: float = -6.0
    duck_music: bool = True


class Assets(BaseModel):
    images: list[str] = Field(default_factory=list)
    mask: Optional[str] = None
    music: Optional[str] = None
    voice: Optional[str] = None


class Constraints(BaseModel):
    safe_zones: str = "default"
    keep_subject_static: bool = True


class SegmentSpec(BaseModel):
    index: int
    duration_seconds: float
    prompt: str = ""
    engine: Optional[str] = None


# ---------------------------------------------------------------------------
# RenderSpec  — the canonical contract
# ---------------------------------------------------------------------------

class RenderSpec(BaseModel):
    render_spec_version: int = 1
    job_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    archetype: Archetype
    brand_safe: bool = True
    aspect_ratio: str = "9:16"
    target_duration_seconds: int = Field(ge=1, le=60)
    segment_duration_seconds: int = Field(ge=2, le=4, default=3)
    preset_id: str
    engine_policy: EnginePolicy = EnginePolicy.LOCAL_PREFERRED
    assets: Assets = Field(default_factory=Assets)
    segment_prompts: list[str] = Field(default_factory=list)
    captions_plan: CaptionsPlan = Field(default_factory=CaptionsPlan)
    audio_plan: AudioPlan = Field(default_factory=AudioPlan)
    constraints: Constraints = Field(default_factory=Constraints)
    segments: list[SegmentSpec] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------

class CreateJobRequest(BaseModel):
    preset_id: str
    prompt: str = ""
    target_duration_seconds: int = Field(ge=1, le=60, default=15)
    brand_safe: Optional[bool] = None
    engine_policy: Optional[EnginePolicy] = None
    archetype: Optional[Archetype] = None
    # Client uploads asset files separately; these are storage URIs assigned
    # after upload.
    image_uris: list[str] = Field(default_factory=list)
    mask_uri: Optional[str] = None
    music_uri: Optional[str] = None
    voice_uri: Optional[str] = None
    captions: Optional[CaptionsPlan] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    archetype: Archetype
    preset_id: str
    target_duration_seconds: int
    progress_pct: float = 0.0
    output_uri: Optional[str] = None
    thumbnail_uri: Optional[str] = None
    metadata_uri: Optional[str] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RenderMetadata(BaseModel):
    job_id: str
    preset_id: str
    archetype: Archetype
    engine_used: str = ""
    brand_safe: bool = True
    target_duration_seconds: int = 0
    segments: list[dict[str, Any]] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    seeds: list[int] = Field(default_factory=list)
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


# ---------------------------------------------------------------------------
# V2 enums and models  (P2-08 / P2-09)
# ---------------------------------------------------------------------------

class EnginePolicyV2(str, enum.Enum):
    """V2 engine policies extend V1 with multi-engine support."""
    LOCAL_ONLY = "local_only"
    LOCAL_PREFERRED = "local_preferred"
    API_ONLY = "api_only"
    MULTI_ENGINE = "multi_engine"
    SINGLE_ENGINE = "single_engine"


class JobStatusV2(str, enum.Enum):
    """Extended job states for V2 pipeline."""
    QUEUED = "QUEUED"
    PLANNING_SCENES = "PLANNING_SCENES"
    BUILDING_TIMELINE = "BUILDING_TIMELINE"
    RENDERING_SCENES = "RENDERING_SCENES"
    COMPOSING = "COMPOSING"
    AUDIO_ASSEMBLY = "AUDIO_ASSEMBLY"
    FINALIZING = "FINALIZING"
    DONE = "DONE"
    FAILED = "FAILED"


class SceneStatus(str, enum.Enum):
    """Per-scene render status for V2."""
    PENDING = "PENDING"
    RENDERING = "RENDERING"
    DONE = "DONE"
    FAILED = "FAILED"
    FALLBACK = "FALLBACK"


class CreateJobRequestV2(BaseModel):
    """V2 job creation request."""
    preset_id: str
    prompt: str = ""
    target_duration_seconds: int = Field(ge=1, le=60, default=15)
    brand_safe: Optional[bool] = None
    engine_preference: Optional[str] = None
    image_uris: list[str] = Field(default_factory=list)
    music_uri: Optional[str] = None
    voice_uri: Optional[str] = None


class SceneStatusInfo(BaseModel):
    """Per-scene status info for V2 job status response."""
    scene_id: int
    scene_index: int
    description: Optional[str] = None
    media_type: str
    engine_used: Optional[str] = None
    status: str
    fallback_used: bool = False
    asset_path: Optional[str] = None


class JobStatusResponseV2(BaseModel):
    """V2 job status response — includes scene-level progress."""
    job_id: str
    version: int = 2
    status: str
    preset_id: str
    target_duration_seconds: int
    progress_pct: float = 0.0
    scene_count: int = 0
    scenes: list[SceneStatusInfo] = Field(default_factory=list)
    output_uri: Optional[str] = None
    thumbnail_uri: Optional[str] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

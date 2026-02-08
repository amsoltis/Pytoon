"""Pydantic models for the V2 Timeline (schema version 2.0).

Translates the frozen Timeline JSON schema (schemas/timeline_v2.json) into
validated Python models.  The Timeline is the single authoritative source for
all timing in the final video — nothing appears without a timeline entry.

Ticket: P2-02
Acceptance Criteria: V2-AC-005, V2-AC-020
"""

from __future__ import annotations

import enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from pytoon.scene_graph.models import TransitionType


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class TransitionSpec(BaseModel):
    """Transition between two consecutive scenes."""

    type: TransitionType = TransitionType.FADE
    duration: int = Field(default=500, ge=0, le=2000, description="Duration in ms")


class Position(str, enum.Enum):
    CENTER = "center"
    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"
    CUSTOM = "custom"


class Transform(BaseModel):
    """Position, scale, and opacity transform for a video element."""

    position: Position = Position.CENTER
    scale: float = Field(default=1.0, ge=0.01, le=5.0)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    x: Optional[int] = None
    y: Optional[int] = None


class VideoTrack(BaseModel):
    """A video layer entry in the timeline."""

    sceneId: int = Field(ge=1)
    asset: Optional[str] = None
    effect: Optional[str] = None
    layer: int = Field(default=0, ge=0)
    transform: Optional[Transform] = None


class DuckRegion(BaseModel):
    """A region where audio volume should be ducked."""

    start: int = Field(ge=0, description="Start in ms")
    end: int = Field(ge=1, description="End in ms")
    duckAmount: float = Field(default=-12.0, ge=-40.0, le=0.0, description="dB reduction")
    fadeIn: float = Field(default=0.2, ge=0.0, le=2.0, description="Fade-down seconds")
    fadeOut: float = Field(default=0.2, ge=0.0, le=2.0, description="Fade-up seconds")

    @model_validator(mode="after")
    def _validate_range(self) -> "DuckRegion":
        if self.end <= self.start:
            raise ValueError("DuckRegion end must be greater than start")
        return self


class AudioTrackType(str, enum.Enum):
    VOICEOVER = "voiceover"
    MUSIC = "music"
    SFX = "sfx"


class AudioTrack(BaseModel):
    """An audio track entry in the timeline."""

    type: AudioTrackType
    file: Optional[str] = None
    start: int = Field(ge=0, description="Start in ms")
    end: Optional[int] = None
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    duckRegions: list[DuckRegion] = Field(default_factory=list)


class CaptionTrack(BaseModel):
    """A timed caption/subtitle entry."""

    text: str = Field(min_length=1)
    start: int = Field(ge=0, description="Display start in ms")
    end: int = Field(ge=1, description="Display end in ms")
    sceneId: Optional[int] = None
    style: Optional[str] = None

    @model_validator(mode="after")
    def _validate_range(self) -> "CaptionTrack":
        if self.end <= self.start:
            raise ValueError("Caption end must be greater than start")
        return self


# ---------------------------------------------------------------------------
# Tracks container
# ---------------------------------------------------------------------------

class Tracks(BaseModel):
    """Multi-track composition data."""

    video: list[VideoTrack] = Field(default_factory=list)
    audio: list[AudioTrack] = Field(default_factory=list)
    captions: list[CaptionTrack] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# TimelineEntry
# ---------------------------------------------------------------------------

class TimelineEntry(BaseModel):
    """A scene's time slot on the timeline."""

    sceneId: int = Field(ge=1)
    start: int = Field(ge=0, description="Start in ms")
    end: int = Field(ge=1, description="End in ms")
    transition: Optional[TransitionSpec] = None

    @model_validator(mode="after")
    def _validate_range(self) -> "TimelineEntry":
        if self.end <= self.start:
            raise ValueError("Timeline entry end must be greater than start")
        return self


# ---------------------------------------------------------------------------
# Timeline  — top-level model
# ---------------------------------------------------------------------------

class Timeline(BaseModel):
    """Top-level V2 Timeline.

    Validation rules:
    - At least one timeline entry is required.
    - Entries must be in ascending order by start time.
    - No overlapping entries (except transition overlap).
    - Caption times must fall within their scene's boundaries.
    - totalDuration must not exceed 60 000 ms.
    """

    version: str = "2.0"
    totalDuration: int = Field(ge=1000, le=60000, description="Total ms")
    timeline: list[TimelineEntry] = Field(min_length=1)
    tracks: Tracks = Field(default_factory=Tracks)

    @model_validator(mode="after")
    def _validate_timeline(self) -> "Timeline":
        entries = self.timeline

        # Ascending order
        for i in range(1, len(entries)):
            if entries[i].start < entries[i - 1].start:
                raise ValueError("Timeline entries must be in ascending start order")

        # No overlapping scenes (allow transition overlap)
        for i in range(1, len(entries)):
            prev = entries[i - 1]
            curr = entries[i]
            max_overlap = 0
            if prev.transition and prev.transition.duration:
                max_overlap = prev.transition.duration
            if curr.start < prev.end - max_overlap:
                raise ValueError(
                    f"Timeline entries overlap: scene {prev.sceneId} "
                    f"[{prev.start}-{prev.end}] and scene {curr.sceneId} "
                    f"[{curr.start}-{curr.end}]"
                )

        # Build scene boundary map for caption validation
        scene_bounds: dict[int, tuple[int, int]] = {}
        for entry in entries:
            scene_bounds[entry.sceneId] = (entry.start, entry.end)

        # Validate captions within scene boundaries
        for cap in self.tracks.captions:
            if cap.sceneId is not None and cap.sceneId in scene_bounds:
                s_start, s_end = scene_bounds[cap.sceneId]
                if cap.start < s_start or cap.end > s_end:
                    raise ValueError(
                        f"Caption '{cap.text[:30]}...' [{cap.start}-{cap.end}] "
                        f"exceeds scene {cap.sceneId} bounds [{s_start}-{s_end}]"
                    )

        return self

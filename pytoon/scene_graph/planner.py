"""Heuristic Scene Planner — converts user inputs into a validated SceneGraph.

Ticket: P2-03
Acceptance Criteria: V2-AC-001
"""

from __future__ import annotations

import re
from typing import Optional

from pytoon.config import get_preset
from pytoon.log import get_logger
from pytoon.scene_graph.models import (
    EngineId,
    GlobalAudio,
    MediaType,
    Scene,
    SceneGraph,
    SceneMedia,
    SceneStyle,
    TransitionType,
    VisualEffect,
)

logger = get_logger(__name__)

# Regex to split on <SHOT N> markers
_SHOT_PATTERN = re.compile(r"<SHOT\s*\d+\s*>", re.IGNORECASE)

# Sentence splitter: split on . ! ? followed by whitespace or end
_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")

# Default scene duration in ms
DEFAULT_SCENE_DURATION_MS = 5000

# Maximum total duration in ms
MAX_TOTAL_DURATION_MS = 60_000


class PlanningError(Exception):
    """Raised when the planner cannot produce a valid scene graph."""


def plan_scenes(
    *,
    media_files: list[str] | None = None,
    prompt: str = "",
    preset_id: str = "product_hero_clean",
    brand_safe: bool = True,
    target_duration_seconds: int = 15,
    voiceover_duration_ms: int | None = None,
    engine_preference: str | None = None,
) -> SceneGraph:
    """Produce a validated SceneGraph from user inputs.

    Planning strategies (evaluated in order):
    1. If prompt contains <SHOT> markers → explicit scene split.
    2. Otherwise split prompt by sentences → one scene per sentence.
    3. If no prompt, create one scene per image with defaults.
    4. If no prompt AND no images → fall back to preset template.
    """
    media_files = media_files or []
    preset = get_preset(preset_id) or {}
    target_ms = min(target_duration_seconds * 1000, MAX_TOTAL_DURATION_MS)

    # Resolve engine preference to EngineId or None
    engine_id: Optional[EngineId] = None
    if engine_preference:
        try:
            engine_id = EngineId(engine_preference)
        except ValueError:
            pass  # ignore unknown; Engine Manager will use default

    # --- Determine scenes ---------------------------------------------------
    scenes: list[Scene]

    if prompt and _SHOT_PATTERN.search(prompt):
        scenes = _plan_from_shots(prompt, media_files, preset, brand_safe, engine_id)
    elif prompt:
        scenes = _plan_from_sentences(prompt, media_files, preset, brand_safe, engine_id)
    elif media_files:
        scenes = _plan_from_images(media_files, preset, brand_safe)
    else:
        scenes = _plan_from_template(preset, brand_safe)

    if not scenes:
        raise PlanningError("Planner produced zero scenes — cannot proceed")

    # --- Assign durations ---------------------------------------------------
    scenes = _assign_durations(scenes, target_ms, voiceover_duration_ms)

    # --- Enforce brand-safe transitions ------------------------------------
    if brand_safe:
        for s in scenes:
            if s.transition not in (TransitionType.CUT, TransitionType.FADE):
                s.transition = TransitionType.FADE

    # --- Build global audio -------------------------------------------------
    voice_script = prompt if prompt else None
    bg_music = preset.get("background_music") or preset.get("music")
    global_audio = GlobalAudio(
        voiceScript=voice_script,
        voiceFile=None,
        backgroundMusic=bg_music,
    )

    sg = SceneGraph(version="2.0", scenes=scenes, globalAudio=global_audio)
    logger.info(
        "scene_plan_created",
        scene_count=len(sg.scenes),
        total_duration_ms=sum(s.duration for s in sg.scenes),
    )
    return sg


# ---------------------------------------------------------------------------
# Strategy 1: <SHOT> markers
# ---------------------------------------------------------------------------

def _plan_from_shots(
    prompt: str,
    media_files: list[str],
    preset: dict,
    brand_safe: bool,
    engine_id: Optional[EngineId],
) -> list[Scene]:
    # Split on <SHOT N> markers
    parts = _SHOT_PATTERN.split(prompt)
    # Filter empty strings
    shot_texts = [p.strip() for p in parts if p.strip()]

    scenes: list[Scene] = []
    for i, text in enumerate(shot_texts):
        scene_id = i + 1
        image = media_files[i] if i < len(media_files) else None
        style = _extract_style(text, preset)

        if image:
            media = SceneMedia(
                type=MediaType.IMAGE,
                asset=image,
                effect=VisualEffect.KEN_BURNS_ZOOM,
            )
        else:
            media = SceneMedia(
                type=MediaType.VIDEO,
                engine=engine_id,
                prompt=text,
            )

        scenes.append(Scene(
            id=scene_id,
            description=text[:120],
            duration=DEFAULT_SCENE_DURATION_MS,
            media=media,
            caption=text,
            style=style,
            transition=TransitionType.FADE,
        ))

    return scenes


# ---------------------------------------------------------------------------
# Strategy 2: sentence splitting
# ---------------------------------------------------------------------------

def _plan_from_sentences(
    prompt: str,
    media_files: list[str],
    preset: dict,
    brand_safe: bool,
    engine_id: Optional[EngineId],
) -> list[Scene]:
    sentences = [s.strip() for s in _SENTENCE_PATTERN.split(prompt) if s.strip()]
    if not sentences:
        sentences = [prompt.strip()]

    scenes: list[Scene] = []
    for i, sentence in enumerate(sentences):
        scene_id = i + 1
        # Cycle through images
        image = media_files[i % len(media_files)] if media_files else None
        style = _extract_style(sentence, preset)

        if image:
            media = SceneMedia(
                type=MediaType.IMAGE,
                asset=image,
                effect=VisualEffect.KEN_BURNS_ZOOM,
            )
        else:
            media = SceneMedia(
                type=MediaType.VIDEO,
                engine=engine_id,
                prompt=sentence,
            )

        scenes.append(Scene(
            id=scene_id,
            description=sentence[:120],
            duration=DEFAULT_SCENE_DURATION_MS,
            media=media,
            caption=sentence,
            style=style,
            transition=TransitionType.FADE,
        ))

    return scenes


# ---------------------------------------------------------------------------
# Strategy 3: images only
# ---------------------------------------------------------------------------

def _plan_from_images(
    media_files: list[str],
    preset: dict,
    brand_safe: bool,
) -> list[Scene]:
    scenes: list[Scene] = []
    for i, image_path in enumerate(media_files):
        scene_id = i + 1
        scenes.append(Scene(
            id=scene_id,
            description=f"Product image {scene_id}",
            duration=DEFAULT_SCENE_DURATION_MS,
            media=SceneMedia(
                type=MediaType.IMAGE,
                asset=image_path,
                effect=VisualEffect.KEN_BURNS_ZOOM,
            ),
            caption=preset.get("default_caption", ""),
            style=_style_from_preset(preset),
            transition=TransitionType.FADE,
        ))
    return scenes


# ---------------------------------------------------------------------------
# Strategy 4: template fallback
# ---------------------------------------------------------------------------

def _plan_from_template(preset: dict, brand_safe: bool) -> list[Scene]:
    """Generate a generic 3-scene template when no inputs are provided."""
    templates = [
        ("Intro — product reveal", "Introducing our product"),
        ("Feature highlight", "Discover the key features"),
        ("Call to action", "Get yours today"),
    ]
    scenes: list[Scene] = []
    for i, (desc, caption) in enumerate(templates):
        scenes.append(Scene(
            id=i + 1,
            description=desc,
            duration=DEFAULT_SCENE_DURATION_MS,
            media=SceneMedia(type=MediaType.IMAGE, effect=VisualEffect.STATIC),
            caption=caption,
            style=_style_from_preset(preset),
            transition=TransitionType.FADE,
        ))
    return scenes


# ---------------------------------------------------------------------------
# Duration assignment
# ---------------------------------------------------------------------------

def _assign_durations(
    scenes: list[Scene],
    target_ms: int,
    voiceover_duration_ms: int | None,
) -> list[Scene]:
    """Assign scene durations so that total ≤ target_ms."""
    n = len(scenes)

    if voiceover_duration_ms and voiceover_duration_ms > 0:
        # Distribute proportionally by character count (proxy for speech time)
        total_chars = max(sum(len(s.caption) for s in scenes), 1)
        effective_total = min(voiceover_duration_ms, MAX_TOTAL_DURATION_MS)
        for s in scenes:
            ratio = max(len(s.caption), 1) / total_chars
            s.duration = max(1000, int(ratio * effective_total))
    else:
        # Default: equal distribution within target
        per_scene = max(1000, target_ms // n)
        for s in scenes:
            s.duration = per_scene

    # Enforce total ≤ 60s — proportional reduction if needed
    total = sum(s.duration for s in scenes)
    if total > MAX_TOTAL_DURATION_MS:
        ratio = MAX_TOTAL_DURATION_MS / total
        for s in scenes:
            s.duration = max(1000, int(s.duration * ratio))

    return scenes


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

_MOOD_KEYWORDS = {
    "cinematic": "cinematic",
    "dramatic": "dramatic",
    "warm": "warm",
    "cool": "cool",
    "upbeat": "upbeat",
    "fun": "fun",
    "elegant": "elegant",
    "neon": "neon",
}

_CAMERA_KEYWORDS = {
    "slow zoom": "slow zoom in",
    "dolly": "slow dolly in",
    "pan left": "pan left",
    "pan right": "pan right",
    "orbit": "orbit",
    "static": "static",
}


def _extract_style(text: str, preset: dict) -> SceneStyle:
    """Extract mood / camera hints from text, falling back to preset."""
    text_lower = text.lower()
    mood = None
    camera = None

    for kw, val in _MOOD_KEYWORDS.items():
        if kw in text_lower:
            mood = val
            break

    for kw, val in _CAMERA_KEYWORDS.items():
        if kw in text_lower:
            camera = val
            break

    return SceneStyle(
        mood=mood or preset.get("mood"),
        camera_motion=camera or preset.get("camera_motion"),
        lighting=preset.get("lighting"),
    )


def _style_from_preset(preset: dict) -> SceneStyle:
    return SceneStyle(
        mood=preset.get("mood"),
        camera_motion=preset.get("camera_motion"),
        lighting=preset.get("lighting"),
    )

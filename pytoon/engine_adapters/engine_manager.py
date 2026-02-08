"""Engine Manager — per-scene engine selection, fallback chain, and parallel dispatch.

Combines P3-05 (multi-engine orchestrator), P3-07 (async parallel scenes),
and P3-09 (fallback chain) into one cohesive module.

Responsibilities:
  - Select the best engine for each scene based on metadata/style rules.
  - Execute generations concurrently across scenes.
  - Run the 3-level fallback chain on per-scene failures.
  - Validate results and track fallback usage.

Tickets: P3-05, P3-07, P3-09
Acceptance Criteria: V2-AC-010, V2-AC-011, V2-AC-013
"""

from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pytoon.config import get_engine_config
from pytoon.engine_adapters.external_base import EngineResult, ExternalEngineAdapter
from pytoon.engine_adapters.prompt_builder import build_prompt, rephrase_for_moderation
from pytoon.engine_adapters.validator import validate_clip
from pytoon.log import get_logger
from pytoon.scene_graph.models import MediaType, Scene, SceneGraph

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Engine Assignment
# ---------------------------------------------------------------------------

@dataclass
class EngineAssignment:
    """Which engine to use for a scene, plus the constructed prompt."""

    scene_id: int
    engine_name: str      # runway | pika | luma | local
    prompt: str
    image_path: Optional[str] = None
    duration_seconds: float = 5.0
    style_hints: dict[str, Any] | None = None


@dataclass
class SceneRenderResult:
    """Final outcome of rendering a single scene (after all fallback attempts)."""

    scene_id: int
    success: bool
    clip_path: Optional[str] = None
    engine_used: str = ""
    fallback_used: bool = False
    fallback_chain: list[str] | None = None     # engines attempted
    error: Optional[str] = None
    elapsed_ms: float = 0.0


# ---------------------------------------------------------------------------
# Engine Registry
# ---------------------------------------------------------------------------

_engine_cache: dict[str, ExternalEngineAdapter] = {}


def _get_engine(name: str) -> ExternalEngineAdapter | None:
    """Lazy-load and cache engine adapter instances."""
    if name in _engine_cache:
        return _engine_cache[name]

    try:
        if name == "runway":
            from pytoon.engine_adapters.runway import RunwayAdapter
            adapter = RunwayAdapter()
        elif name == "pika":
            from pytoon.engine_adapters.pika import PikaAdapter
            adapter = PikaAdapter()
        elif name == "luma":
            from pytoon.engine_adapters.luma import LumaAdapter
            adapter = LumaAdapter()
        else:
            return None

        _engine_cache[name] = adapter
        return adapter
    except Exception as exc:
        logger.warning("engine_load_failed", engine=name, error=str(exc))
        return None


def _is_engine_available(name: str) -> bool:
    """Check if an engine's API key is configured."""
    key_map = {"runway": "RUNWAY_API_KEY", "pika": "PIKA_API_KEY", "luma": "LUMA_API_KEY"}
    env_var = key_map.get(name, "")
    return bool(os.environ.get(env_var, ""))


# ---------------------------------------------------------------------------
# Engine Selection Rules (P3-05)
# ---------------------------------------------------------------------------

_FALLBACK_ORDER = ["runway", "pika", "luma"]


def select_engine_for_scene(
    scene: Scene,
    *,
    default_engine: str | None = None,
    brand_safe: bool = True,
    preset_keywords: list[str] | None = None,
) -> EngineAssignment:
    """Select the best engine for a scene based on the priority rules.

    Priority:
    1. Explicit media.engine → use that engine.
    2. media.type == "image" → "local" (FFmpeg Ken Burns).
    3. Style contains "realistic"/"cinematic" → runway.
    4. Style contains "stylized"/"creative"/"artistic" → pika.
    5. Style contains "physics"/"3D"/"product"/"showcase" → luma.
    6. No match → default engine from config.
    """
    # Read config defaults
    cfg = get_engine_config().get("v2", {})
    config_default = cfg.get("default_engine", "runway")
    effective_default = default_engine or config_default

    # Rule 1: Explicit engine in scene
    if scene.media.engine is not None:
        engine_name = scene.media.engine.value
    # Rule 2: Image-type → local
    elif scene.media.type == MediaType.IMAGE:
        engine_name = "local"
    else:
        # Rules 3-6: style-based selection
        engine_name = _select_by_style(scene, effective_default)

    # Build prompt
    prompt = build_prompt(
        scene,
        brand_safe=brand_safe,
        preset_keywords=preset_keywords,
    )

    return EngineAssignment(
        scene_id=scene.id,
        engine_name=engine_name,
        prompt=prompt,
        image_path=scene.media.asset,
        duration_seconds=scene.duration / 1000.0,
        style_hints={
            "mood": scene.style.mood,
            "camera_motion": scene.style.camera_motion,
            "lighting": scene.style.lighting,
        },
    )


def _select_by_style(scene: Scene, default: str) -> str:
    """Apply style-based engine selection rules."""
    style_str = " ".join(filter(None, [
        scene.style.mood,
        scene.style.camera_motion,
        scene.style.lighting,
        scene.description,
    ])).lower()

    # Rule 3: realistic/cinematic → runway
    if any(kw in style_str for kw in ("realistic", "cinematic", "photorealis")):
        return "runway"

    # Rule 4: stylized/creative/artistic → pika
    if any(kw in style_str for kw in ("stylized", "creative", "artistic", "anime", "abstract")):
        return "pika"

    # Rule 5: physics/3D/product/showcase → luma
    if any(kw in style_str for kw in ("physics", "3d", "product", "showcase", "rotation")):
        return "luma"

    # Rule 6: no match → default
    return default


# ---------------------------------------------------------------------------
# Fallback Chain (P3-09)
# ---------------------------------------------------------------------------

def _get_fallback_chain(primary: str) -> list[str]:
    """Return ordered fallback engines after the primary.

    Order: runway → pika → luma (skip primary).
    Always ends with "local" as Level 3 (deterministic).
    """
    cfg = get_engine_config().get("v2", {})
    chain = cfg.get("fallback_chain", _FALLBACK_ORDER)

    # Remove the primary and any unavailable engines
    alternates = [e for e in chain if e != primary and _is_engine_available(e)]

    # Always append local as final fallback
    alternates.append("local")
    return alternates


async def _render_with_engine(
    engine: ExternalEngineAdapter,
    assignment: EngineAssignment,
    output_dir: str,
) -> EngineResult:
    """Execute a single engine generation attempt."""
    return await engine.generate(
        prompt=assignment.prompt,
        duration_seconds=assignment.duration_seconds,
        image_path=assignment.image_path,
        style_hints=assignment.style_hints,
        output_dir=output_dir,
    )


async def _render_with_fallback(
    assignment: EngineAssignment,
    output_dir: str,
    brand_safe: bool = True,
) -> SceneRenderResult:
    """Render a scene with the full fallback chain.

    Level 1: Primary engine.
    Level 2: Alternate external engines.
    Level 3: Local FFmpeg fallback (always succeeds).
    """
    t0 = time.monotonic()
    engines_tried: list[str] = []
    primary = assignment.engine_name

    # Skip external engines for "local" assignments
    if primary == "local":
        clip_path = _render_local_fallback(assignment, output_dir)
        return SceneRenderResult(
            scene_id=assignment.scene_id,
            success=True,
            clip_path=str(clip_path),
            engine_used="local",
            elapsed_ms=(time.monotonic() - t0) * 1000,
        )

    # Level 1: Primary engine
    engine = _get_engine(primary)
    if engine and _is_engine_available(primary):
        engines_tried.append(primary)
        result = await _render_with_engine(engine, assignment, output_dir)

        if result.success and result.clip_path:
            # Validate clip
            vr = validate_clip(result.clip_path, assignment.duration_seconds)
            if vr.valid:
                return SceneRenderResult(
                    scene_id=assignment.scene_id,
                    success=True,
                    clip_path=result.clip_path,
                    engine_used=primary,
                    elapsed_ms=(time.monotonic() - t0) * 1000,
                )
            else:
                logger.warning("clip_validation_failed", scene_id=assignment.scene_id,
                               engine=primary, errors=vr.errors)

        # Auto-rephrase on moderation rejection, retry same engine once
        if result.moderation_flagged:
            logger.info("moderation_rephrase", scene_id=assignment.scene_id, engine=primary)
            rephrased = rephrase_for_moderation(assignment.prompt)
            assignment.prompt = rephrased
            result2 = await _render_with_engine(engine, assignment, output_dir)
            if result2.success and result2.clip_path:
                vr2 = validate_clip(result2.clip_path, assignment.duration_seconds)
                if vr2.valid:
                    return SceneRenderResult(
                        scene_id=assignment.scene_id,
                        success=True,
                        clip_path=result2.clip_path,
                        engine_used=primary,
                        fallback_used=False,
                        fallback_chain=engines_tried,
                        elapsed_ms=(time.monotonic() - t0) * 1000,
                    )

    # Level 2: Alternate external engines
    alternates = _get_fallback_chain(primary)
    for alt_name in alternates:
        if alt_name == "local":
            break  # Handle local separately at Level 3

        alt_engine = _get_engine(alt_name)
        if alt_engine is None:
            continue

        engines_tried.append(alt_name)
        logger.info("engine_fallback", scene_id=assignment.scene_id,
                     from_engine=primary, to_engine=alt_name)

        alt_result = await _render_with_engine(alt_engine, assignment, output_dir)
        if alt_result.success and alt_result.clip_path:
            vr = validate_clip(alt_result.clip_path, assignment.duration_seconds)
            if vr.valid:
                return SceneRenderResult(
                    scene_id=assignment.scene_id,
                    success=True,
                    clip_path=alt_result.clip_path,
                    engine_used=alt_name,
                    fallback_used=True,
                    fallback_chain=engines_tried,
                    elapsed_ms=(time.monotonic() - t0) * 1000,
                )

    # Level 3: Local FFmpeg fallback (always succeeds)
    engines_tried.append("local")
    logger.warning("local_fallback", scene_id=assignment.scene_id,
                    engines_tried=engines_tried)
    clip_path = _render_local_fallback(assignment, output_dir)

    return SceneRenderResult(
        scene_id=assignment.scene_id,
        success=True,
        clip_path=str(clip_path),
        engine_used="local",
        fallback_used=True,
        fallback_chain=engines_tried,
        elapsed_ms=(time.monotonic() - t0) * 1000,
    )


def _render_local_fallback(assignment: EngineAssignment, output_dir: str) -> Path:
    """Level 3: Deterministic local fallback using FFmpeg.

    - With image: Ken Burns pan/zoom.
    - Without image: Solid-color background with text overlay.
    """
    from pytoon.scene_graph.models import Scene, SceneMedia, MediaType, SceneStyle
    from pytoon.scene_graph.stub_renderer import render_scene_stub

    # Build a minimal Scene object for the stub renderer
    if assignment.image_path and Path(assignment.image_path).exists():
        media = SceneMedia(type=MediaType.IMAGE, asset=assignment.image_path)
    else:
        media = SceneMedia(
            type=MediaType.VIDEO,
            prompt=assignment.prompt[:80] if assignment.prompt else "Fallback scene",
        )

    scene = Scene(
        id=assignment.scene_id,
        description=assignment.prompt[:120] if assignment.prompt else "Fallback",
        duration=int(assignment.duration_seconds * 1000),
        media=media,
    )
    return render_scene_stub(scene, Path(output_dir))


# ---------------------------------------------------------------------------
# Parallel Scene Rendering (P3-07)
# ---------------------------------------------------------------------------

async def render_all_scenes(
    scene_graph: SceneGraph,
    output_dir: str,
    *,
    brand_safe: bool = True,
    default_engine: str | None = None,
    preset_keywords: list[str] | None = None,
    max_concurrent: int = 3,
    on_scene_complete: Any = None,
) -> list[SceneRenderResult]:
    """Render all scenes concurrently with fallback.

    Args:
        scene_graph: Validated SceneGraph.
        output_dir: Directory to store generated clips.
        brand_safe: Whether to sanitize prompts.
        default_engine: Override default engine selection.
        preset_keywords: Keywords to append to prompts.
        max_concurrent: Max concurrent engine invocations.
        on_scene_complete: Optional callback(SceneRenderResult).

    Returns:
        List of SceneRenderResult in scene order.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Step 1: Assign engines to all scenes
    assignments = [
        select_engine_for_scene(
            scene,
            default_engine=default_engine,
            brand_safe=brand_safe,
            preset_keywords=preset_keywords,
        )
        for scene in scene_graph.scenes
    ]

    logger.info(
        "engine_assignments",
        assignments={a.scene_id: a.engine_name for a in assignments},
    )

    # Step 2: Render concurrently with semaphore
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _render_one(assignment: EngineAssignment) -> SceneRenderResult:
        async with semaphore:
            result = await _render_with_fallback(
                assignment, output_dir, brand_safe=brand_safe,
            )
            if on_scene_complete:
                on_scene_complete(result)
            return result

    # Dispatch all scenes concurrently
    tasks = [_render_one(a) for a in assignments]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to failed results
    final_results: list[SceneRenderResult] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error("scene_render_exception", scene_id=assignments[i].scene_id,
                         error=str(r))
            final_results.append(SceneRenderResult(
                scene_id=assignments[i].scene_id,
                success=False,
                error=str(r),
            ))
        else:
            final_results.append(r)

    # Log summary
    succeeded = sum(1 for r in final_results if r.success)
    fallbacks = sum(1 for r in final_results if r.fallback_used)
    logger.info(
        "render_all_complete",
        total=len(final_results),
        succeeded=succeeded,
        fallbacks=fallbacks,
    )

    return final_results

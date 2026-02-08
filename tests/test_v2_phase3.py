"""Phase 3 tests — AI Engine Integration.

Tests:
  - ExternalEngineAdapter interface compliance
  - Prompt builder (construction + sanitization)
  - Engine selection rules
  - Fallback chain logic (mocked engines)
  - Clip validator
  - Engine Manager parallel dispatch (with mocked engines)

Tickets: P3-01 through P3-11
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pytoon.engine_adapters.external_base import EngineResult, ExternalEngineAdapter
from pytoon.engine_adapters.prompt_builder import (
    build_prompt,
    rephrase_for_moderation,
    sanitize_prompt,
)
from pytoon.engine_adapters.validator import ValidationResult, validate_clip
from pytoon.engine_adapters.engine_manager import (
    EngineAssignment,
    SceneRenderResult,
    select_engine_for_scene,
    _select_by_style,
    _get_fallback_chain,
    _render_local_fallback,
    render_all_scenes,
)
from pytoon.scene_graph.models import (
    EngineId,
    MediaType,
    Scene,
    SceneGraph,
    SceneMedia,
    SceneStyle,
    GlobalAudio,
    VisualEffect,
)
from pytoon.scene_graph.planner import plan_scenes


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _make_scene(
    scene_id: int = 1,
    description: str = "A beautiful cinematic product shot",
    media_type: MediaType = MediaType.VIDEO,
    engine: EngineId | None = None,
    prompt: str | None = "Product hero cinematic",
    mood: str | None = None,
    camera_motion: str | None = None,
) -> Scene:
    media = SceneMedia(type=media_type, engine=engine, prompt=prompt)
    style = SceneStyle(mood=mood, camera_motion=camera_motion)
    return Scene(
        id=scene_id,
        description=description,
        duration=5000,
        media=media,
        caption="Test caption",
        style=style,
    )


def _make_scene_graph(n: int = 3) -> SceneGraph:
    scenes = [
        _make_scene(scene_id=i + 1, description=f"Scene {i+1}")
        for i in range(n)
    ]
    return SceneGraph(scenes=scenes, globalAudio=GlobalAudio())


# ---------------------------------------------------------------------------
# P3-01: ExternalEngineAdapter interface
# ---------------------------------------------------------------------------

class TestExternalEngineInterface:
    def test_engine_result_defaults(self):
        r = EngineResult(success=True, engine_name="test")
        assert r.success is True
        assert r.clip_path is None
        assert r.moderation_flagged is False
        assert r.rate_limited is False

    def test_engine_result_error(self):
        r = EngineResult(
            success=False,
            engine_name="runway",
            error="Timeout",
            error_code="timeout",
        )
        assert not r.success
        assert r.error_code == "timeout"

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            ExternalEngineAdapter()


# ---------------------------------------------------------------------------
# P3-06: Prompt Builder
# ---------------------------------------------------------------------------

class TestPromptBuilder:
    def test_basic_prompt(self):
        scene = _make_scene(prompt="A beautiful sunset over the ocean")
        result = build_prompt(scene, brand_safe=True)
        assert "sunset" in result
        assert "brand-safe" in result

    def test_style_keywords_included(self):
        scene = _make_scene(
            prompt="Product showcase",
            mood="cinematic",
            camera_motion="slow dolly in",
        )
        result = build_prompt(scene, brand_safe=True)
        assert "cinematic mood" in result
        assert "camera: slow dolly in" in result

    def test_preset_keywords(self):
        scene = _make_scene(prompt="Product hero")
        result = build_prompt(scene, preset_keywords=["luxury", "premium"])
        assert "luxury" in result
        assert "premium" in result

    def test_sanitization_removes_flagged_terms(self):
        result = sanitize_prompt("shoot the product with a gun effect")
        assert "shoot" not in result.split()  # "shoot" replaced with "film"
        assert "gun" not in result.split()    # "gun" replaced with "device"
        assert "film" in result

    def test_moderation_rephrase(self):
        original = "Violent explosion with fire"
        rephrased = rephrase_for_moderation(original)
        assert "violent" not in rephrased.lower() or "intense" in rephrased.lower()
        assert "safe content" in rephrased.lower()

    def test_prompt_truncation(self):
        scene = _make_scene(prompt="A" * 1000)
        result = build_prompt(scene, engine_max_length=100)
        assert len(result) <= 100


# ---------------------------------------------------------------------------
# P3-08: Clip Validator
# ---------------------------------------------------------------------------

class TestClipValidator:
    def test_missing_file(self, tmp_dir):
        result = validate_clip(tmp_dir / "nonexistent.mp4", 5.0)
        assert not result.valid
        assert "does not exist" in result.errors[0]

    def test_empty_file(self, tmp_dir):
        empty = tmp_dir / "empty.mp4"
        empty.touch()
        result = validate_clip(empty, 5.0)
        assert not result.valid
        assert "empty" in result.errors[0].lower()


# ---------------------------------------------------------------------------
# P3-05: Engine Selection Rules
# ---------------------------------------------------------------------------

class TestEngineSelection:
    def test_explicit_engine_override(self):
        scene = _make_scene(engine=EngineId.PIKA, prompt="test")
        assignment = select_engine_for_scene(scene)
        assert assignment.engine_name == "pika"

    def test_image_type_uses_local(self):
        scene = _make_scene(
            media_type=MediaType.IMAGE,
            engine=None,
            prompt=None,
        )
        scene.media.asset = "/path/to/image.png"
        assignment = select_engine_for_scene(scene)
        assert assignment.engine_name == "local"

    def test_cinematic_style_selects_runway(self):
        result = _select_by_style(
            _make_scene(mood="cinematic"), default="runway"
        )
        assert result == "runway"

    def test_stylized_selects_pika(self):
        result = _select_by_style(
            _make_scene(description="Abstract visuals", mood="stylized"), default="runway"
        )
        assert result == "pika"

    def test_product_selects_luma(self):
        scene = _make_scene(description="Product showcase rotation")
        result = _select_by_style(scene, default="runway")
        assert result == "luma"

    def test_no_match_uses_default(self):
        scene = _make_scene(description="Generic scene", mood=None)
        result = _select_by_style(scene, default="pika")
        assert result == "pika"


# ---------------------------------------------------------------------------
# P3-09: Fallback Chain
# ---------------------------------------------------------------------------

class TestFallbackChain:
    def test_fallback_excludes_primary(self):
        chain = _get_fallback_chain("runway")
        assert "runway" not in chain
        assert "local" in chain  # Always ends with local

    def test_fallback_ends_with_local(self):
        for primary in ("runway", "pika", "luma"):
            chain = _get_fallback_chain(primary)
            assert chain[-1] == "local"

    def test_local_fallback_produces_clip(self, tmp_dir):
        assignment = EngineAssignment(
            scene_id=1,
            engine_name="local",
            prompt="Test fallback scene",
            duration_seconds=3.0,
        )
        clip_path = _render_local_fallback(assignment, str(tmp_dir))
        assert clip_path.exists()
        assert clip_path.stat().st_size > 0


# ---------------------------------------------------------------------------
# P3-07: Parallel Scene Rendering (mocked)
# ---------------------------------------------------------------------------

class TestParallelRendering:
    @pytest.mark.asyncio
    async def test_render_all_scenes_local_fallback(self, tmp_dir):
        """With no API keys set, all scenes should fall through to local."""
        sg = _make_scene_graph(3)
        results = await render_all_scenes(
            sg,
            str(tmp_dir),
            brand_safe=True,
            max_concurrent=2,
        )
        assert len(results) == 3
        for r in results:
            assert r.success
            assert r.engine_used == "local"  # No API keys → local fallback

    @pytest.mark.asyncio
    async def test_render_all_preserves_scene_order(self, tmp_dir):
        """Scene results should map back to correct scene IDs."""
        sg = _make_scene_graph(5)
        results = await render_all_scenes(sg, str(tmp_dir))
        scene_ids = [r.scene_id for r in results]
        assert scene_ids == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Integration: Planner → Engine Manager → Local Fallback
# ---------------------------------------------------------------------------

class TestPlannerToEngineFlow:
    @pytest.mark.asyncio
    async def test_full_flow_with_local_fallback(self, tmp_dir):
        """End-to-end: plan → assign engines → render (local) → validate."""
        sg = plan_scenes(
            prompt="Product reveal. Key features. Call to action.",
            preset_id="product_hero_clean",
            brand_safe=True,
            target_duration_seconds=15,
        )
        assert len(sg.scenes) == 3

        results = await render_all_scenes(
            sg,
            str(tmp_dir),
            brand_safe=True,
        )
        assert len(results) == 3
        for r in results:
            assert r.success
            assert r.clip_path is not None
            assert Path(r.clip_path).exists()

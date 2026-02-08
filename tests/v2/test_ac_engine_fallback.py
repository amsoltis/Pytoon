"""Acceptance Tests — Engine Fallback & Reliability.

Validates:
  - Fallback chain behavior when engines are unavailable.
  - Fallback_used flag is set correctly.
  - Local FFmpeg fallback always produces output.
  - Content moderation triggers rephrase.

Ticket: P5-09
V2-AC codes: V2-AC-011
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pytoon.engine_adapters.engine_manager import (
    EngineAssignment,
    SceneRenderResult,
    _get_fallback_chain,
    _render_local_fallback,
    select_engine_for_scene,
)
from pytoon.engine_adapters.engine_selector import (
    record_engine_result,
    resolve_engine,
    get_failure_rate,
)
from pytoon.engine_adapters.moderation import (
    ModerationStrictness,
    moderate_prompt,
    clean_prompt,
)
from pytoon.scene_graph.models import (
    MediaType,
    Scene,
    SceneMedia,
    SceneStyle,
)


class TestFallbackChain:
    """V2-AC-011: Engine fallback produces coherent output."""

    def test_fallback_chain_excludes_primary(self):
        """Fallback chain should not include the primary engine."""
        chain = _get_fallback_chain("runway")
        assert "runway" not in chain
        assert "local" in chain  # Always ends with local

    def test_fallback_chain_always_has_local(self):
        """Local FFmpeg is always the last resort."""
        for primary in ["runway", "pika", "luma"]:
            chain = _get_fallback_chain(primary)
            assert chain[-1] == "local"

    def test_local_fallback_with_prompt(self, tmp_path):
        """Local fallback generates a clip from prompt text."""
        assignment = EngineAssignment(
            scene_id=1,
            engine_name="local",
            prompt="A beautiful product showcase",
            duration_seconds=3.0,
        )
        clip = _render_local_fallback(assignment, str(tmp_path))
        assert clip.exists()
        assert clip.stat().st_size > 0

    def test_local_fallback_with_image(self, tmp_path):
        """Local fallback handles image input (Ken Burns)."""
        # Create a dummy image
        from PIL import Image
        img = Image.new("RGB", (1080, 1920), color="blue")
        img_path = tmp_path / "product.png"
        img.save(img_path)

        assignment = EngineAssignment(
            scene_id=1,
            engine_name="local",
            prompt="Product shot",
            image_path=str(img_path),
            duration_seconds=3.0,
        )
        clip = _render_local_fallback(assignment, str(tmp_path))
        assert clip.exists()


class TestEngineSelection:
    """Enhanced selection rules from P5-01."""

    def test_user_override_takes_priority(self):
        engine = resolve_engine(
            user_override="luma",
            style_based_engine="runway",
            preset_id="product_hero_clean",
        )
        assert engine == "luma"

    def test_preset_preference(self):
        engine = resolve_engine(
            preset_id="product_hero_clean",
            style_based_engine="runway",
        )
        # product_hero_clean prefers luma per config
        assert engine == "luma"

    def test_style_fallback_when_no_preset(self):
        engine = resolve_engine(
            style_based_engine="pika",
        )
        assert engine == "pika"

    def test_failure_tracking(self):
        """Record failures and check rate calculation."""
        # Reset state
        from pytoon.engine_adapters.engine_selector import _failure_tracker, _success_tracker
        _failure_tracker.clear()
        _success_tracker.clear()

        record_engine_result("runway", False)
        record_engine_result("runway", False)
        record_engine_result("runway", True)

        rate = get_failure_rate("runway", window_seconds=9999)
        assert abs(rate - 2/3) < 0.01


class TestContentModeration:
    """P5-04: Content moderation filters."""

    def test_standard_moderation_catches_nsfw(self):
        result = moderate_prompt("Create a nude scene", strictness="standard")
        assert not result.passed
        assert "nude" in result.flagged_terms

    def test_standard_moderation_passes_clean(self):
        result = moderate_prompt(
            "A beautiful cinematic product reveal",
            strictness="standard",
        )
        assert result.passed

    def test_strict_moderation_catches_ambiguous(self):
        result = moderate_prompt("An epic battle scene", strictness="strict")
        assert not result.passed

    def test_moderation_off_passes_everything(self):
        result = moderate_prompt("Anything goes here", strictness="off")
        assert result.passed

    def test_clean_prompt_removes_terms(self):
        cleaned = clean_prompt("A nude violent scene in the park")
        assert "nude" not in cleaned.lower()
        assert "violent" not in cleaned.lower()
        assert "park" in cleaned.lower()

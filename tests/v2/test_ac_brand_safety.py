"""Acceptance Tests — Brand Safety.

Validates:
  - Transition restriction in brand-safe mode.
  - Prompt sanitization removes blocklisted terms.
  - Product image protection.
  - Color palette enforcement.
  - Brand font enforcement.

Ticket: P5-10
V2-AC codes: V2-AC-012, V2-AC-016
"""

from __future__ import annotations

import pytest

from pytoon.assembler.transitions import (
    BRAND_SAFE_ALLOWED,
    resolve_transition,
    list_available_transitions,
)
from pytoon.engine_adapters.brand_safe import (
    BrandSafeConfig,
    enforce_color_palette,
    enforce_transition_restriction,
    is_product_image,
    load_brand_config,
    sanitize_prompt_brand_safe,
    validate_product_protection,
)
from pytoon.assembler.color_grading import (
    COLOR_PROFILES,
    ColorProfile,
    get_color_profile,
)


class TestTransitionRestriction:
    """V2-AC-012: Only cut and fade in brand-safe mode."""

    def test_brand_safe_allows_fade(self):
        result = enforce_transition_restriction("fade", brand_safe=True)
        assert result == "fade"

    def test_brand_safe_allows_cut(self):
        result = enforce_transition_restriction("cut", brand_safe=True)
        assert result == "cut"

    def test_brand_safe_blocks_swipe(self):
        result = enforce_transition_restriction("swipe_left", brand_safe=True)
        assert result == "fade"

    def test_non_brand_safe_allows_all(self):
        result = enforce_transition_restriction("swipe_left", brand_safe=False)
        assert result == "swipe_left"

    def test_resolve_transition_brand_safe(self):
        spec = resolve_transition("swipe_left", duration_ms=800, brand_safe=True)
        assert spec.xfade_name == "fade"  # Downgraded

    def test_resolve_transition_non_brand_safe(self):
        spec = resolve_transition("swipe_left", duration_ms=800, brand_safe=False)
        assert spec.xfade_name == "slideleft"

    def test_transition_duration_clamped(self):
        spec = resolve_transition("fade", duration_ms=5000, brand_safe=True)
        assert spec.duration_seconds <= 1.5

    def test_cut_has_zero_duration(self):
        spec = resolve_transition("cut", brand_safe=True)
        assert spec.is_cut
        assert spec.duration_seconds < 0.01

    def test_available_transitions_brand_safe(self):
        available = list_available_transitions(brand_safe=True)
        for t in available:
            assert t in BRAND_SAFE_ALLOWED

    def test_available_transitions_all(self):
        available = list_available_transitions(brand_safe=False)
        assert len(available) > len(BRAND_SAFE_ALLOWED)


class TestPromptSanitization:
    """V2-AC-016: Competitor name sanitization."""

    def test_blocklist_removal(self):
        config = BrandSafeConfig(competitor_blocklist=["CompetitorBrand"])
        result = sanitize_prompt_brand_safe(
            "Use CompetitorBrand style for the shot",
            brand_config=config,
        )
        assert "CompetitorBrand" not in result

    def test_substitution_applied(self):
        result = sanitize_prompt_brand_safe("shoot the product")
        assert "shoot" not in result.lower()
        assert "film" in result.lower()

    def test_brand_safe_suffix_appended(self):
        result = sanitize_prompt_brand_safe("A product showcase")
        assert "brand-safe" in result.lower()

    def test_max_length_enforced(self):
        long_prompt = "A" * 600
        result = sanitize_prompt_brand_safe(long_prompt)
        assert len(result) <= 500


class TestProductImageProtection:
    """V2-AC-016: Product images not fed to generative AI."""

    def test_product_image_detected(self):
        assert is_product_image({"type": "image", "asset": "/path/to/product.png"})

    def test_video_not_product_image(self):
        assert not is_product_image({"type": "video", "asset": "/path/to/clip.mp4"})

    def test_validation_catches_violation(self):
        scenes = [
            {"id": 1, "media": {"type": "image", "asset": "product.png", "engine": "runway"}},
        ]
        warnings = validate_product_protection(scenes, brand_safe=True)
        assert len(warnings) == 1

    def test_validation_passes_correct_usage(self):
        scenes = [
            {"id": 1, "media": {"type": "image", "asset": "product.png"}},  # No engine
            {"id": 2, "media": {"type": "video", "engine": "runway"}},
        ]
        warnings = validate_product_protection(scenes, brand_safe=True)
        assert len(warnings) == 0


class TestColorPalette:
    """V2-AC-012: Brand color enforcement."""

    def test_color_in_palette_passes(self):
        result = enforce_color_palette("#FFFFFF", ["#FFFFFF", "#000000"])
        assert result == "#FFFFFF"

    def test_color_not_in_palette_overrides(self):
        result = enforce_color_palette("#FF0000", ["#FFFFFF", "#000000"])
        assert result == "#FFFFFF"  # First palette color

    def test_empty_palette_passes_through(self):
        result = enforce_color_palette("#FF0000", [])
        assert result == "#FF0000"


class TestColorGrading:
    """P5-05: Color profile handling."""

    def test_default_profile_neutral(self):
        profile = get_color_profile()
        assert profile.name == "neutral"

    def test_preset_profiles_exist(self):
        for name in ["warm", "cool", "vintage", "cinematic", "vibrant"]:
            assert name in COLOR_PROFILES

    def test_warm_profile_values(self):
        profile = COLOR_PROFILES["warm"]
        assert profile.saturation > 1.0
        assert profile.temperature == "warm"

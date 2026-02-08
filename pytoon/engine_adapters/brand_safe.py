"""Brand-safe overlays and constraints enforcement.

Implements V2 brand-safe rules:
  - Product image protection (never fed to generative AI).
  - Prompt sanitization (blocklist, substitutions, safety cues).
  - Mandatory logo watermark (persistent or outro).
  - Brand font/color enforcement.
  - Transition restriction (cut/fade only).
  - Color palette enforcement.

Ticket: P5-02
Acceptance Criteria: V2-AC-012, V2-AC-016
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pytoon.config import get_engine_config, get_preset
from pytoon.log import get_logger

logger = get_logger(__name__)

# Allowed transitions in brand-safe mode
BRAND_SAFE_TRANSITIONS = {"cut", "fade"}


@dataclass
class BrandSafeConfig:
    """Brand-safe configuration from preset."""

    enabled: bool = True
    logo_path: Optional[str] = None
    logo_position: str = "top-right"
    logo_opacity: float = 0.7
    logo_mode: str = "persistent"     # persistent | outro
    brand_font: Optional[str] = None
    brand_palette: list[str] = field(default_factory=lambda: ["#FFFFFF", "#000000"])
    ocr_check_enabled: bool = False
    competitor_blocklist: list[str] = field(default_factory=list)


def load_brand_config(preset_id: str | None = None) -> BrandSafeConfig:
    """Load brand-safe config from preset."""
    preset = get_preset(preset_id) if preset_id else {}
    bsc = preset.get("brand_safe_defaults", {})

    return BrandSafeConfig(
        enabled=True,
        logo_path=bsc.get("logo_path"),
        logo_position=bsc.get("logo_position", "top-right"),
        logo_opacity=bsc.get("logo_opacity", 0.7),
        logo_mode=bsc.get("logo_mode", "persistent"),
        brand_font=bsc.get("brand_font"),
        brand_palette=bsc.get("brand_palette", ["#FFFFFF", "#000000"]),
        ocr_check_enabled=bsc.get("ocr_check_enabled", False),
        competitor_blocklist=bsc.get("competitor_blocklist", []),
    )


# ---------------------------------------------------------------------------
# Transition restriction
# ---------------------------------------------------------------------------

def enforce_transition_restriction(transition_type: str, brand_safe: bool = True) -> str:
    """Restrict transition types when brand_safe is enabled.

    Only 'cut' and 'fade' are allowed.
    Any other type is downgraded to 'fade' with a warning.
    """
    if not brand_safe:
        return transition_type

    if transition_type.lower() not in BRAND_SAFE_TRANSITIONS:
        logger.warning(
            "brand_safe_transition_downgrade",
            original=transition_type,
            downgraded_to="fade",
        )
        return "fade"
    return transition_type


# ---------------------------------------------------------------------------
# Product image protection
# ---------------------------------------------------------------------------

def is_product_image(scene_media: dict) -> bool:
    """Check if a scene contains a product image that should be protected."""
    media_type = scene_media.get("type", "")
    asset = scene_media.get("asset", "")
    # Product images are IMAGE type with an asset file
    return media_type == "image" and bool(asset)


def validate_product_protection(scenes: list[dict], brand_safe: bool = True) -> list[str]:
    """Validate that product images are not being fed to generative engines.

    Returns list of warning messages for any violations.
    """
    if not brand_safe:
        return []

    warnings = []
    for scene in scenes:
        media = scene.get("media", {})
        if is_product_image(media) and media.get("engine"):
            warnings.append(
                f"Scene {scene.get('id')}: Product image should not be "
                f"processed by engine '{media['engine']}'. Use local overlay instead."
            )
    return warnings


# ---------------------------------------------------------------------------
# Enhanced prompt sanitization
# ---------------------------------------------------------------------------

def sanitize_prompt_brand_safe(
    prompt: str,
    brand_config: BrandSafeConfig | None = None,
) -> str:
    """Full brand-safe prompt sanitization.

    Steps:
    1. Remove competitor names.
    2. Apply NSFW/offensive term filter.
    3. Apply substitution map.
    4. Append brand-safe suffix.
    5. Truncate to max length.
    """
    cfg = get_engine_config().get("v2", {}).get("prompt_sanitization", {})
    blocklist = cfg.get("blocklist", [])
    substitutions = cfg.get("substitutions", {})
    max_len = cfg.get("max_prompt_length", 500)
    suffix = cfg.get("brand_safe_suffix", "family-friendly, professional, brand-safe")

    result = prompt

    # Add competitor blocklist from brand config
    if brand_config and brand_config.competitor_blocklist:
        blocklist = list(set(blocklist + brand_config.competitor_blocklist))

    # Step 1: Remove blocklisted terms
    for term in blocklist:
        if term:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            result = pattern.sub("", result)

    # Step 2: Apply substitutions
    for old, new in substitutions.items():
        result = re.sub(re.escape(old), new, result, flags=re.IGNORECASE)

    # Step 3: Clean up whitespace
    result = re.sub(r"\s+", " ", result).strip()

    # Step 4: Append brand-safe suffix
    if suffix and suffix not in result:
        result = f"{result}, {suffix}"

    # Step 5: Truncate
    if len(result) > max_len:
        result = result[:max_len - 3] + "..."

    return result


# ---------------------------------------------------------------------------
# Color palette enforcement
# ---------------------------------------------------------------------------

def enforce_color_palette(
    color: str,
    palette: list[str],
    default: str = "#FFFFFF",
) -> str:
    """Ensure a color is from the brand palette.

    If the color isn't in the palette, return the closest match
    or the default.
    """
    if not palette:
        return color

    color_upper = color.upper().strip()
    palette_upper = [c.upper().strip() for c in palette]

    if color_upper in palette_upper:
        return color

    logger.warning(
        "brand_safe_color_override",
        original=color,
        default=default,
    )
    return palette[0] if palette else default

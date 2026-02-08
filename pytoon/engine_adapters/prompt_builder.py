"""Prompt construction pipeline for V2 engine invocations.

Builds optimized prompts from scene metadata, applying:
  - Style/mood/camera keywords
  - Brand-safe sanitization (competitor blocklist, substitutions)
  - Engine-specific length truncation
  - Automatic rephrase for moderation rejection retries

Ticket: P3-06
Acceptance Criteria: V2-AC-010
"""

from __future__ import annotations

import re
from typing import Any, Optional

from pytoon.config import get_engine_config
from pytoon.log import get_logger
from pytoon.scene_graph.models import Scene, SceneStyle

logger = get_logger(__name__)

# Default maximum prompt length per engine
_DEFAULT_MAX_PROMPT_LENGTH = 500

# Default substitution map for common moderation triggers
_DEFAULT_SUBSTITUTIONS: dict[str, str] = {
    "shoot": "film",
    "shooting": "filming",
    "explode": "burst open",
    "explosion": "dynamic burst",
    "kill": "eliminate",
    "weapon": "tool",
    "gun": "device",
    "blood": "red liquid",
    "violent": "intense",
    "nude": "exposed",
    "naked": "unclothed",
}


def build_prompt(
    scene: Scene,
    *,
    brand_safe: bool = True,
    preset_keywords: list[str] | None = None,
    engine_max_length: int | None = None,
) -> str:
    """Build an optimized prompt for an AI video generation engine.

    Composition order:
    1. Scene description (primary content)
    2. Style hints (mood, camera motion, lighting)
    3. Preset keywords (from preset configuration)
    4. Brand-safe cues (if enabled)

    Then apply:
    - Sanitization (blocklist removal, substitutions)
    - Truncation to engine max length
    """
    parts: list[str] = []

    # 1. Primary content — scene description or media prompt
    if scene.media.prompt:
        parts.append(scene.media.prompt)
    elif scene.description:
        parts.append(scene.description)

    # 2. Style hints
    style_parts = _style_to_keywords(scene.style)
    if style_parts:
        parts.append(style_parts)

    # 3. Preset keywords
    if preset_keywords:
        parts.append(", ".join(preset_keywords))

    # 4. Brand-safe cues
    if brand_safe:
        parts.append("professional, brand-safe, clean aesthetic")

    raw_prompt = ". ".join(parts)

    # Apply sanitization
    if brand_safe:
        raw_prompt = sanitize_prompt(raw_prompt)

    # Truncate
    max_len = engine_max_length or _get_max_prompt_length()
    if len(raw_prompt) > max_len:
        raw_prompt = raw_prompt[:max_len - 3] + "..."

    return raw_prompt.strip()


def sanitize_prompt(prompt: str) -> str:
    """Remove blocked terms and apply substitutions.

    Uses the configurable blocklist and substitution map from
    config/engine.yaml, falling back to built-in defaults.
    """
    config = _get_sanitization_config()
    blocklist = config.get("blocklist", [])
    substitutions = config.get("substitutions", {})

    # Merge with defaults
    all_substitutions = {**_DEFAULT_SUBSTITUTIONS, **substitutions}

    result = prompt

    # Remove blocklisted terms (whole word match, case-insensitive)
    for term in blocklist:
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        result = pattern.sub("", result)

    # Apply substitutions
    for old, new in all_substitutions.items():
        pattern = re.compile(r"\b" + re.escape(old) + r"\b", re.IGNORECASE)
        result = pattern.sub(new, result)

    # Clean up double spaces
    result = re.sub(r"\s{2,}", " ", result).strip()

    return result


def rephrase_for_moderation(prompt: str) -> str:
    """Rephrase a prompt that was rejected by content moderation.

    Strategy:
    1. Apply sanitization (substitutions).
    2. Soften aggressive language.
    3. Add "safe content" cues.
    """
    # First pass: sanitize
    result = sanitize_prompt(prompt)

    # Second pass: soften remaining aggressive words
    softeners = {
        "attack": "approach",
        "destroy": "transform",
        "crash": "collide gently",
        "fight": "compete",
        "death": "conclusion",
        "danger": "challenge",
        "fire": "energy",
        "burn": "glow",
    }
    for old, new in softeners.items():
        pattern = re.compile(r"\b" + re.escape(old) + r"\b", re.IGNORECASE)
        result = pattern.sub(new, result)

    # Append safe-content cue
    if "safe content" not in result.lower():
        result += ". Professional, safe content, suitable for all audiences"

    return result.strip()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _style_to_keywords(style: SceneStyle) -> str:
    """Convert SceneStyle to a comma-separated keyword string."""
    keywords: list[str] = []

    if style.mood:
        keywords.append(f"{style.mood} mood")
    if style.camera_motion:
        keywords.append(f"camera: {style.camera_motion}")
    if style.lighting:
        keywords.append(f"{style.lighting} lighting")

    return ", ".join(keywords)


def _get_sanitization_config() -> dict[str, Any]:
    """Load prompt sanitization config from engine.yaml."""
    config = get_engine_config()
    v2 = config.get("v2", {})
    return v2.get("prompt_sanitization", {})


def _get_max_prompt_length() -> int:
    """Get max prompt length from config or default."""
    config = _get_sanitization_config()
    return config.get("max_prompt_length", _DEFAULT_MAX_PROMPT_LENGTH)

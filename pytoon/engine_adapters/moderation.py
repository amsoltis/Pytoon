"""Content moderation and safety filters.

Pre-generation: prompt sanitization, blocklist enforcement.
Post-generation: NSFW classification (optional), content safety check.
Auto-rephrase on engine moderation rejection.

Ticket: P5-04
Acceptance Criteria: V2-AC-012, V2-AC-016
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from pytoon.config import get_engine_config
from pytoon.log import get_logger

logger = get_logger(__name__)


class ModerationStrictness(str, Enum):
    STRICT = "strict"
    STANDARD = "standard"
    OFF = "off"


@dataclass
class ModerationResult:
    """Result of a content moderation check."""

    passed: bool
    reason: Optional[str] = None
    flagged_terms: list[str] | None = None
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# NSFW / offensive term lists
# ---------------------------------------------------------------------------

_NSFW_TERMS = {
    "nude", "naked", "explicit", "pornograph", "sexual", "nsfw",
    "gore", "bloody", "violent", "drug", "weapon", "gun",
}

_OFFENSIVE_TERMS = {
    "hate", "racist", "discriminat", "slur",
}


# ---------------------------------------------------------------------------
# Pre-generation moderation
# ---------------------------------------------------------------------------

def moderate_prompt(
    prompt: str,
    *,
    strictness: ModerationStrictness | str = ModerationStrictness.STANDARD,
    brand_safe: bool = True,
) -> ModerationResult:
    """Check a prompt for content policy violations before sending to engines.

    Returns ModerationResult indicating pass/fail.
    """
    if strictness == ModerationStrictness.OFF or strictness == "off":
        return ModerationResult(passed=True)

    cfg = get_engine_config().get("v2", {}).get("content_moderation", {})
    effective_strictness = strictness if strictness != ModerationStrictness.STANDARD else cfg.get("strictness", "standard")

    prompt_lower = prompt.lower()
    flagged: list[str] = []

    # Check NSFW terms
    for term in _NSFW_TERMS:
        if term in prompt_lower:
            flagged.append(term)

    # Check offensive terms
    for term in _OFFENSIVE_TERMS:
        if term in prompt_lower:
            flagged.append(term)

    # Strict mode: also check for ambiguous terms
    if effective_strictness == "strict" or effective_strictness == ModerationStrictness.STRICT:
        _STRICT_TERMS = {"fight", "war", "battle", "crash", "death", "dead"}
        for term in _STRICT_TERMS:
            if re.search(rf"\b{re.escape(term)}\b", prompt_lower):
                flagged.append(term)

    # Brand-safe: check blocklist from config
    if brand_safe:
        blocklist = cfg.get("blocklist", [])
        sanitization = get_engine_config().get("v2", {}).get("prompt_sanitization", {})
        blocklist.extend(sanitization.get("blocklist", []))
        for term in blocklist:
            if term and term.lower() in prompt_lower:
                flagged.append(term)

    if flagged:
        logger.warning("prompt_moderation_flagged", terms=flagged, strictness=str(effective_strictness))
        return ModerationResult(
            passed=False,
            reason=f"Flagged terms: {', '.join(flagged)}",
            flagged_terms=flagged,
        )

    return ModerationResult(passed=True)


def clean_prompt(
    prompt: str,
    *,
    brand_safe: bool = True,
) -> str:
    """Remove flagged terms and clean up the prompt."""
    prompt_lower = prompt.lower()
    result = prompt

    all_terms = _NSFW_TERMS | _OFFENSIVE_TERMS
    for term in all_terms:
        if term in prompt_lower:
            result = re.sub(re.escape(term), "", result, flags=re.IGNORECASE)

    # Clean up whitespace
    result = re.sub(r"\s+", " ", result).strip()
    return result


# ---------------------------------------------------------------------------
# Post-generation safety check
# ---------------------------------------------------------------------------

def check_generated_content_safety(
    clip_path: str | Path,
    *,
    check_nsfw: bool = False,
) -> ModerationResult:
    """Check generated video clip for safety issues.

    Optional NSFW frame classification using a lightweight model.
    Returns ModerationResult.
    """
    clip = Path(clip_path)
    if not clip.exists():
        return ModerationResult(passed=False, reason="Clip not found")

    if not check_nsfw:
        return ModerationResult(passed=True, reason="NSFW check disabled")

    # Attempt frame extraction + classification
    try:
        return _run_nsfw_check(clip)
    except Exception as exc:
        logger.warning("nsfw_check_failed", error=str(exc))
        # Fail open — don't block on classification errors
        return ModerationResult(passed=True, reason=f"Check failed: {exc}", confidence=0.5)


def _run_nsfw_check(clip: Path) -> ModerationResult:
    """Extract frames and run NSFW classification.

    Uses a lightweight classifier if available, otherwise passes.
    """
    try:
        # Try to use transformers pipeline for NSFW detection
        from transformers import pipeline
        classifier = pipeline("image-classification", model="Falconsai/nsfw_image_detection")

        # Extract a sample frame
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            frame_path = tmp.name

        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-i", str(clip),
                "-ss", "1",
                "-frames:v", "1",
                "-q:v", "2",
                frame_path,
            ],
            capture_output=True, timeout=10,
        )

        result = classifier(frame_path)
        nsfw_score = 0.0
        for r in result:
            if r.get("label", "").lower() == "nsfw":
                nsfw_score = r.get("score", 0.0)

        if nsfw_score > 0.7:
            return ModerationResult(
                passed=False,
                reason=f"NSFW content detected (score: {nsfw_score:.2f})",
                confidence=nsfw_score,
            )

        return ModerationResult(passed=True, confidence=1.0 - nsfw_score)

    except ImportError:
        # No classifier available — pass
        return ModerationResult(passed=True, reason="No NSFW classifier available", confidence=0.5)

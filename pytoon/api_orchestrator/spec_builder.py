"""Build a RenderSpec from a CreateJobRequest + preset config."""

from __future__ import annotations

from typing import Any

from pytoon.config import get_defaults, get_preset
from pytoon.models import (
    Archetype,
    Assets,
    AudioPlan,
    Constraints,
    CreateJobRequest,
    EnginePolicy,
    RenderSpec,
)
from pytoon.api_orchestrator.planner import (
    default_prompt_for_segment,
    plan_captions,
    plan_segments,
)


def build_render_spec(req: CreateJobRequest) -> RenderSpec:
    """Construct a fully-populated RenderSpec from a job request."""
    defaults = get_defaults()
    preset = get_preset(req.preset_id)
    if preset is None:
        raise ValueError(f"Unknown preset: {req.preset_id}")

    # Resolve archetype (explicit > preset > default)
    archetype = req.archetype or Archetype(preset.get("archetype", "OVERLAY"))

    # Brand-safe
    brand_safe = req.brand_safe if req.brand_safe is not None else preset.get(
        "brand_safe", defaults.get("brand_safe_default", True)
    )

    # If brand_safe + PRODUCT_HERO requested, potentially override to OVERLAY
    # (engine adapter will handle this at render time as well)

    # Engine policy
    engine_policy = req.engine_policy or EnginePolicy(
        preset.get("engine_policy", defaults.get("engine_policy_default", "local_preferred"))
    )

    # Duration
    target_dur = req.target_duration_seconds
    seg_dur = defaults.get("segment_duration_seconds", 3)

    # Plan segments
    segments = plan_segments(target_dur, seg_dur)

    # Build per-segment prompts
    total_seg = len(segments)
    segment_prompts = [
        default_prompt_for_segment(archetype, req.prompt, i, total_seg)
        for i in range(total_seg)
    ]
    for i, sp in enumerate(segments):
        sp.prompt = segment_prompts[i]

    # Captions
    if req.captions:
        captions_plan = plan_captions(
            hook=req.captions.hook,
            beats=req.captions.beats,
            cta=req.captions.cta,
            target_duration=target_dur,
        )
    else:
        captions_plan = plan_captions(
            hook=req.prompt[:60] if req.prompt else "",
            beats=[],
            cta="",
            target_duration=target_dur,
        )

    # Audio
    audio_defaults = preset.get("audio", {})
    audio_plan = AudioPlan(
        music_level_db=audio_defaults.get("music_level_db", -18),
        voice_level_db=audio_defaults.get("voice_level_db", -6),
        duck_music=True,
    )

    # Assets
    assets = Assets(
        images=req.image_uris,
        mask=req.mask_uri,
        music=req.music_uri,
        voice=req.voice_uri,
    )

    # Constraints
    constraints = Constraints(
        keep_subject_static=brand_safe,
    )

    return RenderSpec(
        archetype=archetype,
        brand_safe=brand_safe,
        target_duration_seconds=target_dur,
        segment_duration_seconds=seg_dur,
        preset_id=req.preset_id,
        engine_policy=engine_policy,
        assets=assets,
        segment_prompts=segment_prompts,
        captions_plan=captions_plan,
        audio_plan=audio_plan,
        constraints=constraints,
        segments=segments,
    )

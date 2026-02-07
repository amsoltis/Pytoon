"""High-level assembly pipeline — ties together ffmpeg ops for a full job."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from pytoon.assembler.ffmpeg_ops import (
    burn_captions,
    burn_watermark,
    concat_segments,
    extract_thumbnail,
    loudness_normalize,
    mix_audio,
    overlay_image,
)
from pytoon.config import get_defaults, get_preset
from pytoon.db import SegmentRow
from pytoon.log import get_logger
from pytoon.models import Archetype, RenderSpec
from pytoon.storage import get_storage

logger = get_logger(__name__)


async def assemble_job(db: Session, spec: RenderSpec) -> tuple[str, str]:
    """Assemble all segments into the final MP4 + thumbnail.

    Returns (output_uri, thumbnail_uri).
    """
    storage = get_storage()
    defaults = get_defaults()
    preset = get_preset(spec.preset_id) or {}

    out_cfg = defaults.get("output", {})
    width = out_cfg.get("width", 1080)
    height = out_cfg.get("height", 1920)
    fps = out_cfg.get("fps", 30)
    transition_cfg = defaults.get("transition", {})
    crossfade_ms = transition_cfg.get("duration_ms", 150)

    # Gather segment artifacts
    seg_rows = (
        db.query(SegmentRow)
        .filter(SegmentRow.job_id == spec.job_id)
        .order_by(SegmentRow.index)
        .all()
    )

    segment_paths: list[Path] = []
    for seg in seg_rows:
        if not seg.artifact_uri:
            logger.warning("missing_artifact", job_id=spec.job_id, index=seg.index)
            continue
        key = storage.key_from_uri(seg.artifact_uri)
        local = storage.local_path(key)
        if local.exists():
            segment_paths.append(local)
        else:
            logger.warning("artifact_not_found", key=key)

    if not segment_paths:
        raise RuntimeError("No segment artifacts available for assembly")

    job_dir = Path(storage.root) / "jobs" / spec.job_id / "assembly"
    job_dir.mkdir(parents=True, exist_ok=True)

    # 1) Concat segments with crossfade
    concat_out = job_dir / "01_concat.mp4"
    concat_segments(
        segment_paths,
        concat_out,
        crossfade_ms=crossfade_ms,
        fps=fps,
        width=width,
        height=height,
    )
    current = concat_out
    logger.info("assembly_concat_done", job_id=spec.job_id)

    # 2) Overlay product/person image (OVERLAY and PRODUCT_HERO archetypes)
    if spec.archetype in (Archetype.OVERLAY, Archetype.PRODUCT_HERO):
        if spec.assets.images:
            img_key = storage.key_from_uri(spec.assets.images[0])
            img_local = storage.local_path(img_key)
            if img_local.exists():
                overlay_out = job_dir / "02_overlay.mp4"
                overlay_fx = preset.get("overlay_fx", {})
                overlay_image(
                    video_path=current,
                    image_path=img_local,
                    output_path=overlay_out,
                    shadow=overlay_fx.get("shadow", False),
                    glow=overlay_fx.get("glow", False),
                )
                current = overlay_out
                logger.info("assembly_overlay_done", job_id=spec.job_id)

    # 3) Burn captions (archetype-aware styling)
    caption_style = preset.get("caption_style", {})
    if spec.captions_plan.timings:
        captions_out = job_dir / "03_captions.mp4"
        captions_data = [
            {"text": t.text, "start": t.start, "end": t.end}
            for t in spec.captions_plan.timings
        ]
        burn_captions(
            video_path=current,
            output_path=captions_out,
            captions=captions_data,
            font=caption_style.get("font", "Arial"),
            fontsize=_fontsize_from_rules(caption_style.get("size_rules", "auto")),
            safe_margin=caption_style.get("safe_margin_px", 120),
            width=width,
            archetype=spec.archetype.value,
            position=caption_style.get("position", "lower_third"),
        )
        current = captions_out
        logger.info("assembly_captions_done", job_id=spec.job_id)

    # 3b) Brand watermark (if brand_safe and a logo exists in config)
    if spec.brand_safe:
        logo_path = _find_brand_logo(storage)
        if logo_path and logo_path.exists():
            watermark_out = job_dir / "03b_watermark.mp4"
            burn_watermark(
                video_path=current,
                output_path=watermark_out,
                watermark_path=logo_path,
                position="top-right",
                opacity=0.6,
            )
            current = watermark_out
            logger.info("assembly_watermark_done", job_id=spec.job_id)

    # 4) Mix audio
    music_path = None
    voice_path = None
    if spec.assets.music:
        mk = storage.key_from_uri(spec.assets.music)
        mp = storage.local_path(mk)
        if mp.exists():
            music_path = mp

    if spec.assets.voice:
        vk = storage.key_from_uri(spec.assets.voice)
        vp = storage.local_path(vk)
        if vp.exists():
            voice_path = vp

    if music_path or voice_path:
        audio_out = job_dir / "04_audio.mp4"
        mix_audio(
            video_path=current,
            output_path=audio_out,
            music_path=music_path,
            voice_path=voice_path,
            music_level_db=spec.audio_plan.music_level_db,
            voice_level_db=spec.audio_plan.voice_level_db,
            duck_music=spec.audio_plan.duck_music,
            duration_seconds=float(spec.target_duration_seconds),
        )
        current = audio_out
        logger.info("assembly_audio_done", job_id=spec.job_id)

    # 5) Loudness normalize (only if audio present)
    if music_path or voice_path:
        norm_out = job_dir / "05_normalized.mp4"
        loudness_normalize(current, norm_out)
        current = norm_out
        logger.info("assembly_normalize_done", job_id=spec.job_id)

    # 6) Final export (ensure correct settings)
    final_out = job_dir / "final.mp4"
    max_bitrate = out_cfg.get("max_bitrate", "12M")
    from pytoon.assembler.ffmpeg_ops import run_ffmpeg
    run_ffmpeg([
        "-i", str(current),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-s", f"{width}x{height}",
        "-maxrate", max_bitrate,
        "-bufsize", max_bitrate,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(final_out),
    ])

    # Persist to storage
    final_key = f"jobs/{spec.job_id}/output.mp4"
    output_uri = storage.save_file(final_key, final_out)

    # 7) Thumbnail
    thumb_local = job_dir / "thumbnail.jpg"
    extract_thumbnail(final_out, thumb_local, timestamp=1.0)
    thumb_key = f"jobs/{spec.job_id}/thumbnail.jpg"
    thumb_uri = storage.save_file(thumb_key, thumb_local)

    logger.info("assembly_complete", job_id=spec.job_id, output_uri=output_uri)
    return output_uri, thumb_uri


def _fontsize_from_rules(rules: str) -> int:
    mapping = {"small": 40, "auto": 56, "large": 72}
    return mapping.get(rules, 56)


def _find_brand_logo(storage) -> Path | None:
    """Look for a brand logo in well-known locations."""
    candidates = [
        Path(storage.root) / "brand" / "logo.png",
        Path(storage.root) / "brand" / "watermark.png",
        Path(storage.root) / ".." / "assets" / "brand_logo.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

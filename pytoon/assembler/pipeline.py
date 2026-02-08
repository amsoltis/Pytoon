"""High-level assembly pipeline — ties together ffmpeg ops for a full job."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from pytoon.assembler.ffmpeg_ops import (
    burn_captions,
    burn_captions_v2,
    burn_watermark,
    compose_scenes,
    concat_segments,
    extract_thumbnail,
    loudness_normalize,
    mix_audio,
    overlay_image,
    run_ffmpeg,
)
from pytoon.config import get_defaults, get_preset
from pytoon.db import SceneRow, SegmentRow
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


async def assemble_job_v2(
    db,
    job_id: str,
    timeline_data: dict,
    preset_id: str,
    brand_safe: bool = True,
    voice_path: str | None = None,
    voice_script: str | None = None,
    music_source: str | None = None,
) -> tuple[str, str]:
    """V2 timeline-driven assembly pipeline with full audio & caption support.

    Stages:
    1. Compose scenes with transitions.
    2. Generate/process voiceover (TTS or user audio).
    3. Map voice to scenes + forced alignment for captions.
    4. Prepare background music (trim/loop/volume).
    5. Apply audio ducking to music.
    6. Burn styled captions onto video.
    7. Mix voice + ducked music.
    8. Normalize volume to -14 LUFS.
    9. Mux audio onto video.
    10. Brand watermark.
    11. Final export.
    12. Generate SRT + thumbnail.

    Tickets: P2-09, P4-11
    Returns (output_uri, thumbnail_uri).
    """
    from pytoon.audio_manager.alignment import align_captions
    from pytoon.audio_manager.caption_renderer import (
        CaptionStyle,
        generate_srt,
        get_caption_style,
        render_styled_captions,
    )
    from pytoon.audio_manager.ducking import apply_ducking, detect_duck_regions
    from pytoon.audio_manager.mixer import mix_audio_tracks, mux_audio_to_video
    from pytoon.audio_manager.music import generate_silence_track, prepare_music
    from pytoon.audio_manager.tts import generate_voiceover
    from pytoon.audio_manager.voice_mapper import map_voice_to_scenes
    from pytoon.audio_manager.voice_processor import process_voice

    storage = get_storage()
    defaults = get_defaults()
    preset = get_preset(preset_id) or {}

    out_cfg = defaults.get("output", {})
    width = out_cfg.get("width", 1080)
    height = out_cfg.get("height", 1920)
    fps = out_cfg.get("fps", 30)
    total_duration_ms = timeline_data.get("totalDuration", 15000)
    total_duration_s = total_duration_ms / 1000.0

    job_dir = Path(storage.root) / "jobs" / job_id / "assembly"
    job_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = job_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Gather scene clips in order
    scene_rows = (
        db.query(SceneRow)
        .filter(SceneRow.job_id == job_id)
        .order_by(SceneRow.scene_index)
        .all()
    )

    scene_clips: list[Path] = []
    for sr in scene_rows:
        if sr.asset_path:
            p = Path(sr.asset_path)
            if p.exists():
                scene_clips.append(p)

    if not scene_clips:
        raise RuntimeError("No scene clips available for V2 assembly")

    # Build transitions list from timeline data
    tl_entries = timeline_data.get("timeline", [])
    transitions: list[dict | None] = []
    for entry in tl_entries:
        trans = entry.get("transition")
        transitions.append(trans)

    # Build scene boundary map for alignment
    scene_boundaries: list[tuple[int, int, int]] = []
    scene_ids: list[int] = []
    scene_durations_ms: list[int] = []
    for entry in tl_entries:
        sid = entry.get("sceneId", 0)
        s = entry.get("start", 0)
        e = entry.get("end", 0)
        scene_boundaries.append((sid, s, e))
        scene_ids.append(sid)
        scene_durations_ms.append(e - s)

    # ===== STAGE 1: Compose scenes with transitions =========================
    composed_out = job_dir / "01_composed.mp4"
    compose_scenes(
        scene_clips, composed_out, transitions,
        fps=fps, width=width, height=height,
    )
    current_video = composed_out
    logger.info("v2_assembly_compose_done", job_id=job_id)

    # ===== STAGE 2: Generate / process voiceover ============================
    processed_voice_path: str | None = None
    voice_duration_ms: int | None = None
    transcript: str | None = voice_script

    # Resolve voice from globalAudio in timeline or direct params
    global_audio = timeline_data.get("tracks", {}).get("audio", [])
    voice_file_from_tl = None
    music_file_from_tl = None
    for at in global_audio:
        if at.get("type") == "voiceover":
            voice_file_from_tl = at.get("file")
        elif at.get("type") == "music":
            music_file_from_tl = at.get("file")

    effective_voice = voice_path or voice_file_from_tl
    effective_music = music_source or music_file_from_tl

    if effective_voice and Path(effective_voice).exists():
        # User-provided voice file
        vr = process_voice(
            effective_voice, str(audio_dir),
            script=transcript,
            max_duration_ms=total_duration_ms,
        )
        if vr.success:
            processed_voice_path = vr.audio_path
            voice_duration_ms = vr.duration_ms
            if vr.transcript:
                transcript = vr.transcript
    elif transcript:
        # Generate via TTS
        tts_result = await generate_voiceover(
            transcript, str(audio_dir),
        )
        if tts_result.success:
            processed_voice_path = tts_result.audio_path
            voice_duration_ms = tts_result.duration_ms

    # ===== STAGE 3: Voice-to-scene mapping + forced alignment ===============
    captions_data: list[dict] = []

    if transcript and scene_ids:
        # Map voice to scenes
        mapping = map_voice_to_scenes(
            transcript, scene_ids, scene_durations_ms,
            voice_duration_ms=voice_duration_ms,
        )

        # Forced alignment
        if processed_voice_path:
            alignment = align_captions(
                processed_voice_path, transcript, scene_boundaries,
            )
            captions_data = [
                {
                    "text": ac.text,
                    "start": ac.start_ms,
                    "end": ac.end_ms,
                    "sceneId": ac.scene_id,
                }
                for ac in alignment.captions
            ]
        else:
            # Use even-time split from voice mapper
            captions_data = [
                {
                    "text": seg.text,
                    "start": seg.start_ms,
                    "end": seg.end_ms,
                    "sceneId": seg.scene_id,
                }
                for seg in mapping.segments
            ]

    # Fall back to timeline captions if no voice-derived captions
    if not captions_data:
        tl_captions = timeline_data.get("tracks", {}).get("captions", [])
        captions_data = tl_captions

    # ===== STAGE 4: Prepare background music ================================
    prepared_music_path: str | None = None
    if effective_music:
        prepared_music_path = prepare_music(
            effective_music, str(audio_dir), total_duration_s,
        )

    # ===== STAGE 5: Apply audio ducking =====================================
    ducked_music_path: str | None = prepared_music_path
    if prepared_music_path and processed_voice_path and captions_data:
        # Build voice-active segments from caption/voice timing
        voice_segments = []
        for cap in captions_data:
            voice_segments.append((cap.get("start", 0), cap.get("end", 0)))

        duck_regions = detect_duck_regions(voice_segments)
        if duck_regions:
            ducked_out = str(audio_dir / "music_ducked.wav")
            ducked_music_path = apply_ducking(
                prepared_music_path, ducked_out, duck_regions,
            )

    # ===== STAGE 6: Burn styled captions ====================================
    if captions_data:
        captions_out = job_dir / "02_captions.mp4"
        cap_style = get_caption_style(preset, brand_safe=brand_safe)
        render_styled_captions(
            current_video, captions_out, captions_data,
            style=cap_style, brand_safe=brand_safe,
            width=width, height=height,
        )
        current_video = captions_out
        logger.info("v2_assembly_styled_captions_done", job_id=job_id)

    # ===== STAGE 7: Brand watermark =========================================
    if brand_safe:
        logo_path = _find_brand_logo(storage)
        if logo_path and logo_path.exists():
            watermark_out = job_dir / "03_watermark.mp4"
            burn_watermark(
                video_path=current_video,
                output_path=watermark_out,
                watermark_path=logo_path,
                position="top-right",
                opacity=0.6,
            )
            current_video = watermark_out
            logger.info("v2_assembly_watermark_done", job_id=job_id)

    # ===== STAGE 8: Mix audio tracks ========================================
    mixed_audio_path: str | None = None
    if processed_voice_path or ducked_music_path:
        mixed_out = str(audio_dir / "mixed.wav")
        mixed_audio_path = mix_audio_tracks(
            mixed_out,
            voice_path=processed_voice_path,
            music_path=ducked_music_path,
            target_duration_seconds=total_duration_s,
        )

    # ===== STAGE 9: Volume normalization ====================================
    if mixed_audio_path:
        normalized_out = audio_dir / "normalized.wav"
        loudness_normalize(
            Path(mixed_audio_path), normalized_out,
            target_lufs=-14.0,
        )
        if normalized_out.exists():
            mixed_audio_path = str(normalized_out)
        logger.info("v2_assembly_normalized", job_id=job_id)

    # ===== STAGE 10: Mux audio onto video ===================================
    if mixed_audio_path:
        muxed_out = job_dir / "04_muxed.mp4"
        mux_audio_to_video(current_video, mixed_audio_path, muxed_out)
        current_video = muxed_out
    else:
        # No audio — add silent track
        silent_out = job_dir / "04_silent.mp4"
        run_ffmpeg([
            "-i", str(current_video),
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={total_duration_s}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(silent_out),
        ])
        current_video = silent_out

    # ===== STAGE 11: Final export ===========================================
    final_out = job_dir / "final.mp4"
    max_bitrate = out_cfg.get("max_bitrate", "12M")
    run_ffmpeg([
        "-i", str(current_video),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-s", f"{width}x{height}",
        "-maxrate", max_bitrate, "-bufsize", max_bitrate,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(final_out),
    ])

    final_key = f"jobs/{job_id}/output.mp4"
    output_uri = storage.save_file(final_key, final_out)

    # ===== STAGE 12: Thumbnail + SRT ========================================
    thumb_local = job_dir / "thumbnail.jpg"
    extract_thumbnail(final_out, thumb_local, timestamp=1.0)
    thumb_key = f"jobs/{job_id}/thumbnail.jpg"
    thumb_uri = storage.save_file(thumb_key, thumb_local)

    # Generate SRT captions file
    if captions_data:
        srt_path = job_dir / "captions.srt"
        generate_srt(captions_data, srt_path)
        srt_key = f"jobs/{job_id}/captions.srt"
        storage.save_file(srt_key, srt_path)

    logger.info("v2_assembly_complete", job_id=job_id, output_uri=output_uri)
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

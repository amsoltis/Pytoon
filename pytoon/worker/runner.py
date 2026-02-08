"""Segment render runner — orchestrates rendering of all segments for a job."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from pytoon.config import get_defaults
from pytoon.db import JobRow, SceneRow, SegmentRow, get_session_factory
from pytoon.engine_adapters.base import SegmentResult
from pytoon.engine_adapters.selector import (
    select_engine_with_fallback,
)
from pytoon.log import get_logger
from pytoon.metrics import (
    FALLBACK_USED,
    JOB_TOTAL_TIME,
    RENDER_FAILURE,
    RENDER_SUCCESS,
    SEGMENT_RENDER_TIME,
)
from pytoon.models import (
    Archetype,
    EnginePolicy,
    JobStatus,
    RenderMetadata,
    RenderSpec,
    SegmentStatus,
)
from pytoon.storage import get_storage
from pytoon.worker.state_machine import (
    all_segments_done,
    compute_progress,
    get_incomplete_segments,
    transition_job,
    transition_segment,
)
from pytoon.worker.template_fallback import generate_template_video

logger = get_logger(__name__)


async def run_job(job_id: str):
    """Full lifecycle for one job — dispatches to V1 or V2 pipeline."""
    factory = get_session_factory()
    db: Session = factory()

    try:
        job: JobRow | None = db.query(JobRow).filter(JobRow.id == job_id).first()
        if job is None:
            logger.error("job_not_found", job_id=job_id)
            return

        if getattr(job, "version", 1) == 2:
            db.close()
            await _run_job_v2(job_id)
            return

    except Exception:
        db.close()
        raise
    finally:
        if db.is_active:
            db.close()

    # V1 path — re-open session
    await _run_job_v1(job_id)


async def _run_job_v1(job_id: str):
    """V1 pipeline — original segment-based flow."""
    factory = get_session_factory()
    db: Session = factory()
    t_start = time.monotonic()

    try:
        job: JobRow | None = db.query(JobRow).filter(JobRow.id == job_id).first()
        if job is None:
            logger.error("job_not_found", job_id=job_id)
            return

        spec = RenderSpec.model_validate_json(job.render_spec_json)

        # --- PLANNING ---------------------------------------------------------
        transition_job(db, job_id, JobStatus.PLANNING)

        # --- RENDERING SEGMENTS -----------------------------------------------
        transition_job(db, job_id, JobStatus.RENDERING_SEGMENTS)

        incomplete = get_incomplete_segments(db, job_id)
        if not incomplete:
            # All segments already done (resume case)
            logger.info("all_segments_already_done", job_id=job_id)
        else:
            engine_fallback_used = False
            archetype_fallback_used = False

            for seg_row in incomplete:
                seg_result = await _render_one_segment(
                    db, spec, seg_row, engine_fallback_used,
                )
                if seg_result is None:
                    # Archetype fallback: if PRODUCT_HERO I2V fails, try OVERLAY
                    if spec.archetype == Archetype.PRODUCT_HERO:
                        logger.warning(
                            "archetype_fallback",
                            job_id=job_id,
                            from_archetype="PRODUCT_HERO",
                            to_archetype="OVERLAY",
                        )
                        FALLBACK_USED.labels(fallback_type="archetype_fallback").inc()
                        archetype_fallback_used = True
                        spec.archetype = Archetype.OVERLAY
                        seg_result = await _render_one_segment(
                            db, spec, seg_row, engine_fallback_used,
                        )

                    if seg_result is None:
                        # Total failure — template fallback
                        logger.error("total_segment_failure", job_id=job_id,
                                     segment=seg_row.index)
                        uri = generate_template_video(
                            job_id=job_id,
                            duration_seconds=int(seg_row.duration_seconds),
                            text=f"Segment {seg_row.index + 1}",
                        )
                        transition_segment(
                            db, job_id, seg_row.index, SegmentStatus.DONE,
                            artifact_uri=uri,
                            engine_used="template_fallback",
                        )
                        FALLBACK_USED.labels(fallback_type="template_fallback").inc()
                        engine_fallback_used = True

                # Update progress
                pct = compute_progress(db, job_id)
                transition_job(db, job_id, JobStatus.RENDERING_SEGMENTS, progress_pct=pct)

        # --- ASSEMBLING -------------------------------------------------------
        if all_segments_done(db, job_id):
            transition_job(db, job_id, JobStatus.ASSEMBLING, progress_pct=90.0)

            try:
                output_uri, thumb_uri = await _assemble(db, spec)

                # Build render metadata
                meta = _build_metadata(db, spec, engine_fallback_used=False)
                storage = get_storage()
                meta_key = f"jobs/{job_id}/metadata.json"
                storage.save_bytes(meta_key, meta.model_dump_json(indent=2).encode())
                meta_uri = storage.uri(meta_key)

                transition_job(
                    db, job_id, JobStatus.DONE,
                    progress_pct=100.0,
                    output_uri=output_uri,
                    thumbnail_uri=thumb_uri,
                    metadata_uri=meta_uri,
                )
                RENDER_SUCCESS.labels(archetype=spec.archetype.value).inc()
            except Exception as exc:
                logger.error("assembly_failed", job_id=job_id, error=str(exc))
                # Fallback: deliver template
                uri = generate_template_video(
                    job_id=job_id,
                    duration_seconds=spec.target_duration_seconds,
                    text="Assembly failed — template output",
                )
                transition_job(
                    db, job_id, JobStatus.DONE,
                    progress_pct=100.0,
                    output_uri=uri,
                    fallback_used=True,
                    fallback_reason=f"Assembly error: {exc}",
                )
        else:
            transition_job(
                db, job_id, JobStatus.FAILED,
                error="Not all segments completed",
                fallback_used=True,
            )
            RENDER_FAILURE.labels(
                archetype=spec.archetype.value,
                reason="segments_incomplete",
            ).inc()

    except Exception as exc:
        logger.exception("job_runner_crash", job_id=job_id, error=str(exc))
        try:
            # Last-resort: template fallback
            job_row = db.query(JobRow).filter(JobRow.id == job_id).first()
            dur = job_row.target_duration_seconds if job_row else 15
            uri = generate_template_video(
                job_id=job_id,
                duration_seconds=dur,
                text="Render failed — template output",
            )
            transition_job(
                db, job_id, JobStatus.FAILED,
                output_uri=uri,
                error=str(exc),
                fallback_used=True,
                fallback_reason=str(exc),
            )
        except Exception:
            pass
        RENDER_FAILURE.labels(archetype="unknown", reason="crash").inc()
    finally:
        elapsed = time.monotonic() - t_start
        JOB_TOTAL_TIME.labels(archetype="unknown").observe(elapsed)
        db.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _render_one_segment(
    db: Session,
    spec: RenderSpec,
    seg_row: SegmentRow,
    engine_fallback_used: bool,
) -> SegmentResult | None:
    """Render a single segment, returning SegmentResult or None on total failure."""
    transition_segment(db, spec.job_id, seg_row.index, SegmentStatus.RUNNING)

    try:
        adapter, fallback = await select_engine_with_fallback(
            spec.engine_policy,
            spec.archetype.value,
            spec.brand_safe,
        )
    except RuntimeError:
        transition_segment(
            db, spec.job_id, seg_row.index, SegmentStatus.FAILED,
            error="No engine available",
        )
        return None

    # Resolve image path
    storage = get_storage()
    image_path = None
    if spec.assets.images:
        img_uri = spec.assets.images[0]
        key = storage.key_from_uri(img_uri)
        if storage.exists(key):
            image_path = str(storage.local_path(key))

    mask_path = None
    if spec.assets.mask:
        key = storage.key_from_uri(spec.assets.mask)
        if storage.exists(key):
            mask_path = str(storage.local_path(key))

    prompt = seg_row.prompt or ""
    defaults = get_defaults()

    result = await adapter.render_segment(
        job_id=spec.job_id,
        segment_index=seg_row.index,
        prompt=prompt,
        duration_seconds=seg_row.duration_seconds,
        archetype=spec.archetype.value,
        brand_safe=spec.brand_safe,
        image_path=image_path,
        mask_path=mask_path,
        width=defaults.get("output", {}).get("width", 1080),
        height=defaults.get("output", {}).get("height", 1920),
    )

    SEGMENT_RENDER_TIME.labels(engine=adapter.name).observe(result.elapsed_ms / 1000)

    if result.success and result.artifact_path:
        # Persist artifact to storage
        artifact_key = f"jobs/{spec.job_id}/segments/seg_{seg_row.index:03d}.mp4"
        art_path = Path(result.artifact_path)
        if art_path.exists():
            uri = storage.save_file(artifact_key, art_path)
        else:
            # Might be a remote URL from API adapter
            uri = result.artifact_path

        transition_segment(
            db, spec.job_id, seg_row.index, SegmentStatus.DONE,
            engine_used=adapter.name,
            artifact_uri=uri,
            seed=result.seed,
        )
        return result
    else:
        transition_segment(
            db, spec.job_id, seg_row.index, SegmentStatus.FAILED,
            engine_used=adapter.name,
            error=result.error,
        )
        return None


async def _assemble(db: Session, spec: RenderSpec) -> tuple[str, str]:
    """Call the assembler and return (output_uri, thumbnail_uri)."""
    # Import here to avoid circular deps
    from pytoon.assembler.pipeline import assemble_job
    return await assemble_job(db, spec)


async def _run_job_v2(job_id: str):
    """V2 pipeline — scene-graph-based flow with AI engine integration.

    Stages:
    1. Scene Planning (already done at API time, load Scene Graph)
    2. Timeline Construction
    3. Scene Rendering via Engine Manager (with fallback chain)
    4. Media Processing (scale/crop/trim to timeline)
    5. Scene Composition with transitions
    6. Caption Burn-in
    7. Audio Assembly (silent for now — Phase 4 adds real audio)
    8. Final Export

    Tickets: P2-09, P3-11
    """
    from pytoon.assembler.pipeline import assemble_job_v2
    from pytoon.engine_adapters.engine_manager import render_all_scenes
    from pytoon.engine_adapters.media_processor import process_clip
    from pytoon.scene_graph.models import SceneGraph
    from pytoon.timeline.orchestrator import build_timeline
    from pytoon.worker.state_machine import (
        all_scenes_done,
        compute_scene_progress,
        transition_job_v2,
        transition_scene,
    )
    from pytoon.models import JobStatusV2

    factory = get_session_factory()
    db: Session = factory()
    t_start = time.monotonic()
    storage = get_storage()

    try:
        job: JobRow | None = db.query(JobRow).filter(JobRow.id == job_id).first()
        if job is None:
            logger.error("v2_job_not_found", job_id=job_id)
            return

        # --- PLANNING SCENES --------------------------------------------------
        transition_job_v2(db, job_id, JobStatusV2.PLANNING_SCENES)

        scene_graph = SceneGraph.model_validate_json(job.scene_graph_json)
        logger.info("v2_scene_graph_loaded", job_id=job_id, scenes=len(scene_graph.scenes))

        # --- BUILDING TIMELINE ------------------------------------------------
        transition_job_v2(db, job_id, JobStatusV2.BUILDING_TIMELINE, progress_pct=10.0)

        timeline = build_timeline(scene_graph)
        timeline_json = timeline.model_dump_json()
        transition_job_v2(
            db, job_id, JobStatusV2.BUILDING_TIMELINE,
            progress_pct=20.0,
            timeline_json=timeline_json,
        )

        # Persist timeline JSON to file
        tl_path = Path(storage.root) / "jobs" / job_id / "timeline.json"
        tl_path.parent.mkdir(parents=True, exist_ok=True)
        tl_path.write_text(timeline_json)

        # Persist scene graph JSON to file
        sg_path = Path(storage.root) / "jobs" / job_id / "scene_graph.json"
        sg_path.write_text(job.scene_graph_json)

        # --- RENDERING SCENES (via Engine Manager with fallback) ---------------
        transition_job_v2(db, job_id, JobStatusV2.RENDERING_SCENES, progress_pct=25.0)

        scenes_dir = Path(storage.root) / "jobs" / job_id / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)

        # Track per-scene progress via callback
        def _on_scene_complete(result):
            status = "DONE" if result.success else "FAILED"
            fallback_status = "FALLBACK" if result.fallback_used else status
            transition_scene(
                db, job_id, result.scene_id, fallback_status if result.fallback_used else status,
                engine_used=result.engine_used,
                asset_path=result.clip_path,
                fallback_used=result.fallback_used,
                render_duration_ms=int(result.elapsed_ms),
                error_message=result.error,
            )
            pct = 25.0 + compute_scene_progress(db, job_id) * 0.5
            transition_job_v2(db, job_id, JobStatusV2.RENDERING_SCENES, progress_pct=pct)

        # Mark all scenes as RENDERING
        for scene in scene_graph.scenes:
            transition_scene(db, job_id, scene.id, "RENDERING")

        # Render all scenes concurrently with Engine Manager
        render_results = await render_all_scenes(
            scene_graph,
            str(scenes_dir),
            brand_safe=job.brand_safe,
            on_scene_complete=_on_scene_complete,
        )

        # Process clips — scale/crop/trim to match timeline requirements
        processed_dir = Path(storage.root) / "jobs" / job_id / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)

        for result in render_results:
            if result.success and result.clip_path:
                scene = next((s for s in scene_graph.scenes if s.id == result.scene_id), None)
                if scene:
                    processed_path = processed_dir / f"scene_{result.scene_id}.mp4"
                    try:
                        process_clip(
                            result.clip_path,
                            processed_path,
                            target_duration_seconds=scene.duration / 1000.0,
                        )
                        # Update scene row with processed path
                        transition_scene(
                            db, job_id, result.scene_id, "DONE",
                            asset_path=str(processed_path),
                        )
                    except Exception as exc:
                        logger.warning(
                            "clip_processing_skipped",
                            scene_id=result.scene_id,
                            error=str(exc),
                        )
                        # Keep raw clip path (already set in callback)

        # --- COMPOSING --------------------------------------------------------
        if all_scenes_done(db, job_id):
            transition_job_v2(db, job_id, JobStatusV2.COMPOSING, progress_pct=80.0)

            try:
                tl_data = timeline.model_dump()
                output_uri, thumb_uri = await assemble_job_v2(
                    db, job_id, tl_data,
                    preset_id=job.preset_id,
                    brand_safe=job.brand_safe,
                )

                transition_job_v2(
                    db, job_id, JobStatusV2.DONE,
                    progress_pct=100.0,
                    output_uri=output_uri,
                    thumbnail_uri=thumb_uri,
                )
                logger.info("v2_job_done", job_id=job_id)
            except Exception as exc:
                logger.error("v2_assembly_failed", job_id=job_id, error=str(exc))
                transition_job_v2(
                    db, job_id, JobStatusV2.FAILED,
                    error=f"Assembly error: {exc}",
                )
        else:
            transition_job_v2(
                db, job_id, JobStatusV2.FAILED,
                error="Not all scenes completed",
            )

    except Exception as exc:
        logger.exception("v2_job_runner_crash", job_id=job_id, error=str(exc))
        try:
            transition_job_v2(
                db, job_id, JobStatusV2.FAILED,
                error=str(exc),
            )
        except Exception:
            pass
    finally:
        elapsed = time.monotonic() - t_start
        JOB_TOTAL_TIME.labels(archetype="scene_graph").observe(elapsed)
        db.close()


def _build_metadata(
    db: Session,
    spec: RenderSpec,
    engine_fallback_used: bool,
) -> RenderMetadata:
    segments = (
        db.query(SegmentRow)
        .filter(SegmentRow.job_id == spec.job_id)
        .order_by(SegmentRow.index)
        .all()
    )
    seg_info = [
        {
            "index": s.index,
            "engine": s.engine_used,
            "uri": s.artifact_uri,
            "seed": s.seed,
            "duration": s.duration_seconds,
        }
        for s in segments
    ]
    return RenderMetadata(
        job_id=spec.job_id,
        preset_id=spec.preset_id,
        archetype=spec.archetype,
        engine_used=segments[0].engine_used if segments else "",
        brand_safe=spec.brand_safe,
        target_duration_seconds=spec.target_duration_seconds,
        segments=seg_info,
        fallback_used=engine_fallback_used,
        seeds=[s.seed for s in segments if s.seed is not None],
        created_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
    )

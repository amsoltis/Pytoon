"""FastAPI routes for the Pytoon API."""

from __future__ import annotations

import io
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from PIL import Image
from sqlalchemy.orm import Session

from pytoon.api_orchestrator.auth import require_api_key
from pytoon.api_orchestrator.spec_builder import build_render_spec
from pytoon.api_orchestrator.validation import (
    validate_image_dimensions,
    validate_upload,
)
from pytoon.config import get_presets_map
from pytoon.db import JobRow, SceneRow, SegmentRow, get_db
from pytoon.log import get_logger
from pytoon.metrics import RENDER_JOBS_TOTAL
from pytoon.models import (
    CreateJobRequest,
    CreateJobRequestV2,
    JobStatus,
    JobStatusResponse,
    JobStatusResponseV2,
    JobStatusV2,
    SceneStatusInfo,
    SegmentStatus,
)
from pytoon.queue import enqueue_job
from pytoon.storage import get_storage

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


# ---- helpers ---------------------------------------------------------------

Auth = Annotated[None, Depends(require_api_key)]
DB = Annotated[Session, Depends(get_db)]


# ---- health (no auth) -----------------------------------------------------

health_router = APIRouter()


@health_router.get("/health")
async def health():
    return {"status": "ok"}


# ---- presets ---------------------------------------------------------------

@router.get("/presets")
async def list_presets():
    return {"presets": list(get_presets_map().values())}


# ---- asset upload ----------------------------------------------------------

@router.post("/assets/upload")
async def upload_asset(
    file: UploadFile = File(...),
    category: str = "image",
    db: Session = Depends(get_db),
):
    validate_upload(file, category)

    data = await file.read()

    # Validate image dimensions
    if category in ("image", "mask"):
        img = Image.open(io.BytesIO(data))
        validate_image_dimensions(img.width, img.height)

    key = f"uploads/{uuid.uuid4().hex}/{file.filename}"
    storage = get_storage()
    uri = storage.save_bytes(key, data)
    logger.info("asset_uploaded", key=key, category=category, size=len(data))
    return {"uri": uri, "key": key, "size": len(data)}


# ---- jobs ------------------------------------------------------------------

@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(req: CreateJobRequest, db: Session = Depends(get_db)):
    # Build RenderSpec
    try:
        spec = build_render_spec(req)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    # Persist job
    job = JobRow(
        id=spec.job_id,
        status=JobStatus.QUEUED.value,
        archetype=spec.archetype.value,
        preset_id=spec.preset_id,
        brand_safe=spec.brand_safe,
        engine_policy=spec.engine_policy.value,
        target_duration_seconds=spec.target_duration_seconds,
        render_spec_json=spec.model_dump_json(),
    )
    db.add(job)

    # Persist segment rows
    for seg in spec.segments:
        db.add(SegmentRow(
            job_id=spec.job_id,
            index=seg.index,
            status=SegmentStatus.PENDING.value,
            duration_seconds=seg.duration_seconds,
            prompt=seg.prompt,
        ))

    db.commit()

    RENDER_JOBS_TOTAL.labels(
        archetype=spec.archetype.value,
        preset=spec.preset_id,
    ).inc()

    # Enqueue for worker
    enqueue_job(spec.job_id)

    logger.info("job_created", job_id=spec.job_id, archetype=spec.archetype.value)
    return {
        "job_id": spec.job_id,
        "status": JobStatus.QUEUED.value,
        "segments": len(spec.segments),
    }


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job: JobRow | None = db.query(JobRow).filter(JobRow.id == job_id).first()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return JobStatusResponse(
        job_id=job.id,
        status=JobStatus(job.status),
        archetype=job.archetype,
        preset_id=job.preset_id,
        target_duration_seconds=job.target_duration_seconds,
        progress_pct=job.progress_pct or 0.0,
        output_uri=job.output_uri,
        thumbnail_uri=job.thumbnail_uri,
        metadata_uri=job.metadata_uri,
        fallback_used=job.fallback_used or False,
        fallback_reason=job.fallback_reason,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/jobs/{job_id}/segments")
async def get_segments(job_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(SegmentRow)
        .filter(SegmentRow.job_id == job_id)
        .order_by(SegmentRow.index)
        .all()
    )
    return {
        "job_id": job_id,
        "segments": [
            {
                "index": r.index,
                "status": r.status,
                "duration_seconds": r.duration_seconds,
                "engine_used": r.engine_used,
                "artifact_uri": r.artifact_uri,
                "error": r.error,
            }
            for r in rows
        ],
    }


# ============================================================================
# V2 API  (P2-08)
# ============================================================================

router_v2 = APIRouter(prefix="/api/v2", dependencies=[Depends(require_api_key)])


@router_v2.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job_v2(req: CreateJobRequestV2, db: Session = Depends(get_db)):
    """Create a V2 job — scene-graph-based pipeline."""
    import uuid as _uuid

    presets = get_presets_map()
    if req.preset_id not in presets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown preset: {req.preset_id}")

    job_id = _uuid.uuid4().hex

    # Resolve media file paths from URIs
    storage = get_storage()
    media_files: list[str] = []
    for uri in req.image_uris:
        key = storage.key_from_uri(uri)
        local = storage.local_path(key)
        if local.exists():
            media_files.append(str(local))

    # Run Scene Planner
    from pytoon.scene_graph.planner import plan_scenes, PlanningError
    try:
        scene_graph = plan_scenes(
            media_files=media_files,
            prompt=req.prompt,
            preset_id=req.preset_id,
            brand_safe=req.brand_safe if req.brand_safe is not None else True,
            target_duration_seconds=req.target_duration_seconds,
            engine_preference=req.engine_preference,
        )
    except PlanningError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    # Persist job
    job = JobRow(
        id=job_id,
        status=JobStatusV2.QUEUED.value,
        archetype="SCENE_GRAPH",
        preset_id=req.preset_id,
        brand_safe=req.brand_safe if req.brand_safe is not None else True,
        engine_policy="multi_engine",
        target_duration_seconds=req.target_duration_seconds,
        version=2,
        scene_graph_json=scene_graph.model_dump_json(),
    )
    db.add(job)

    # Persist scene rows
    for i, scene in enumerate(scene_graph.scenes):
        db.add(SceneRow(
            scene_id=scene.id,
            job_id=job_id,
            scene_index=i,
            description=scene.description,
            duration_ms=scene.duration,
            media_type=scene.media.type.value,
            status="PENDING",
        ))

    db.commit()

    # Enqueue for worker
    enqueue_job(job_id)

    logger.info("v2_job_created", job_id=job_id, scene_count=len(scene_graph.scenes))
    return {
        "job_id": job_id,
        "version": 2,
        "status": JobStatusV2.QUEUED.value,
        "scene_count": len(scene_graph.scenes),
    }


@router_v2.get("/jobs/{job_id}")
async def get_job_status_v2(job_id: str, db: Session = Depends(get_db)):
    """Get V2 job status with scene-level progress."""
    job: JobRow | None = db.query(JobRow).filter(JobRow.id == job_id).first()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    scene_rows = (
        db.query(SceneRow)
        .filter(SceneRow.job_id == job_id)
        .order_by(SceneRow.scene_index)
        .all()
    )

    scenes_info = [
        SceneStatusInfo(
            scene_id=sr.scene_id,
            scene_index=sr.scene_index,
            description=sr.description,
            media_type=sr.media_type,
            engine_used=sr.engine_used,
            status=sr.status,
            fallback_used=sr.fallback_used or False,
            asset_path=sr.asset_path,
        )
        for sr in scene_rows
    ]

    return JobStatusResponseV2(
        job_id=job.id,
        version=job.version or 2,
        status=job.status,
        preset_id=job.preset_id,
        target_duration_seconds=job.target_duration_seconds,
        progress_pct=job.progress_pct or 0.0,
        scene_count=len(scenes_info),
        scenes=scenes_info,
        output_uri=job.output_uri,
        thumbnail_uri=job.thumbnail_uri,
        fallback_used=job.fallback_used or False,
        fallback_reason=job.fallback_reason,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router_v2.get("/jobs/{job_id}/scene-graph")
async def get_scene_graph(job_id: str, db: Session = Depends(get_db)):
    """Return the persisted Scene Graph JSON for a V2 job."""
    job: JobRow | None = db.query(JobRow).filter(JobRow.id == job_id).first()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if not job.scene_graph_json:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No scene graph for this job")

    import json
    return json.loads(job.scene_graph_json)


@router_v2.get("/jobs/{job_id}/timeline")
async def get_timeline(job_id: str, db: Session = Depends(get_db)):
    """Return the persisted Timeline JSON for a V2 job."""
    job: JobRow | None = db.query(JobRow).filter(JobRow.id == job_id).first()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if not job.timeline_json:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No timeline for this job")

    import json
    return json.loads(job.timeline_json)

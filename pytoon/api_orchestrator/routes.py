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
from pytoon.db import JobRow, SegmentRow, get_db
from pytoon.log import get_logger
from pytoon.metrics import RENDER_JOBS_TOTAL
from pytoon.models import (
    CreateJobRequest,
    JobStatus,
    JobStatusResponse,
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

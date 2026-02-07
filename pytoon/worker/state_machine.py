"""Job state machine — transition helpers that persist to DB."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from pytoon.db import JobRow, SegmentRow
from pytoon.log import get_logger
from pytoon.models import JobStatus, SegmentStatus

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Job transitions
# ---------------------------------------------------------------------------

def transition_job(
    db: Session,
    job_id: str,
    new_status: JobStatus,
    *,
    progress_pct: float | None = None,
    output_uri: str | None = None,
    thumbnail_uri: str | None = None,
    metadata_uri: str | None = None,
    fallback_used: bool | None = None,
    fallback_reason: str | None = None,
    error: str | None = None,
):
    job: JobRow | None = db.query(JobRow).filter(JobRow.id == job_id).first()
    if job is None:
        logger.error("job_not_found_for_transition", job_id=job_id)
        return

    old = job.status
    job.status = new_status.value
    job.updated_at = datetime.now(timezone.utc)

    if progress_pct is not None:
        job.progress_pct = progress_pct
    if output_uri is not None:
        job.output_uri = output_uri
    if thumbnail_uri is not None:
        job.thumbnail_uri = thumbnail_uri
    if metadata_uri is not None:
        job.metadata_uri = metadata_uri
    if fallback_used is not None:
        job.fallback_used = fallback_used
    if fallback_reason is not None:
        job.fallback_reason = fallback_reason
    if error is not None:
        job.error = error

    db.commit()
    logger.info("job_transition", job_id=job_id, old=old, new=new_status.value)


# ---------------------------------------------------------------------------
# Segment transitions
# ---------------------------------------------------------------------------

def transition_segment(
    db: Session,
    job_id: str,
    segment_index: int,
    new_status: SegmentStatus,
    *,
    engine_used: str | None = None,
    artifact_uri: str | None = None,
    seed: int | None = None,
    error: str | None = None,
):
    seg: SegmentRow | None = (
        db.query(SegmentRow)
        .filter(SegmentRow.job_id == job_id, SegmentRow.index == segment_index)
        .first()
    )
    if seg is None:
        logger.error("segment_not_found", job_id=job_id, index=segment_index)
        return

    seg.status = new_status.value
    if new_status == SegmentStatus.RUNNING:
        seg.started_at = datetime.now(timezone.utc)
    if new_status in (SegmentStatus.DONE, SegmentStatus.FAILED):
        seg.completed_at = datetime.now(timezone.utc)
    if engine_used is not None:
        seg.engine_used = engine_used
    if artifact_uri is not None:
        seg.artifact_uri = artifact_uri
    if seed is not None:
        seg.seed = seed
    if error is not None:
        seg.error = error

    db.commit()
    logger.info(
        "segment_transition",
        job_id=job_id,
        index=segment_index,
        new=new_status.value,
    )


# ---------------------------------------------------------------------------
# Progress calculation
# ---------------------------------------------------------------------------

def compute_progress(db: Session, job_id: str) -> float:
    """Return 0.0–100.0 based on segment completion."""
    segments = (
        db.query(SegmentRow)
        .filter(SegmentRow.job_id == job_id)
        .all()
    )
    if not segments:
        return 0.0
    done = sum(1 for s in segments if s.status == SegmentStatus.DONE.value)
    return round(done / len(segments) * 100, 1)


def all_segments_done(db: Session, job_id: str) -> bool:
    segments = (
        db.query(SegmentRow)
        .filter(SegmentRow.job_id == job_id)
        .all()
    )
    return all(s.status == SegmentStatus.DONE.value for s in segments) and len(segments) > 0


def get_incomplete_segments(db: Session, job_id: str) -> list[SegmentRow]:
    """Return segments that are PENDING or FAILED (for resume)."""
    return (
        db.query(SegmentRow)
        .filter(
            SegmentRow.job_id == job_id,
            SegmentRow.status.in_([
                SegmentStatus.PENDING.value,
                SegmentStatus.FAILED.value,
                SegmentStatus.RUNNING.value,  # was running when we crashed
            ]),
        )
        .order_by(SegmentRow.index)
        .all()
    )

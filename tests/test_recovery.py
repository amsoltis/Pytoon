"""D) Recovery tests — job state persistence and resume."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from pytoon.db import Base, JobRow, SegmentRow
from pytoon.models import JobStatus, SegmentStatus
from pytoon.worker.state_machine import (
    all_segments_done,
    compute_progress,
    get_incomplete_segments,
    transition_job,
    transition_segment,
)


class TestStateMachine:
    def test_job_transitions(self, db_session: Session):
        """Job status persists through transitions."""
        job = JobRow(
            id="test-recover-1",
            status=JobStatus.QUEUED.value,
            archetype="OVERLAY",
            preset_id="overlay_classic",
            target_duration_seconds=15,
        )
        db_session.add(job)
        db_session.commit()

        transition_job(db_session, "test-recover-1", JobStatus.PLANNING)
        db_session.refresh(job)
        assert job.status == JobStatus.PLANNING.value

        transition_job(db_session, "test-recover-1", JobStatus.RENDERING_SEGMENTS)
        db_session.refresh(job)
        assert job.status == JobStatus.RENDERING_SEGMENTS.value

    def test_segment_transitions(self, db_session: Session):
        """Segment statuses persist."""
        db_session.add(JobRow(
            id="test-seg-1",
            status=JobStatus.RENDERING_SEGMENTS.value,
            archetype="OVERLAY",
            preset_id="overlay_classic",
        ))
        db_session.add(SegmentRow(
            job_id="test-seg-1",
            index=0,
            status=SegmentStatus.PENDING.value,
            duration_seconds=3.0,
        ))
        db_session.commit()

        transition_segment(db_session, "test-seg-1", 0, SegmentStatus.RUNNING)
        seg = db_session.query(SegmentRow).filter_by(job_id="test-seg-1", index=0).first()
        assert seg.status == SegmentStatus.RUNNING.value
        assert seg.started_at is not None

        transition_segment(
            db_session, "test-seg-1", 0, SegmentStatus.DONE,
            engine_used="mock", artifact_uri="file:///out.mp4", seed=42,
        )
        db_session.refresh(seg)
        assert seg.status == SegmentStatus.DONE.value
        assert seg.artifact_uri == "file:///out.mp4"
        assert seg.seed == 42

    def test_compute_progress(self, db_session: Session):
        db_session.add(JobRow(
            id="test-prog-1",
            status=JobStatus.RENDERING_SEGMENTS.value,
            archetype="OVERLAY",
            preset_id="overlay_classic",
        ))
        for i in range(5):
            db_session.add(SegmentRow(
                job_id="test-prog-1",
                index=i,
                status=SegmentStatus.PENDING.value,
                duration_seconds=3.0,
            ))
        db_session.commit()

        assert compute_progress(db_session, "test-prog-1") == 0.0

        # Mark 3 done
        for i in range(3):
            transition_segment(db_session, "test-prog-1", i, SegmentStatus.DONE)

        assert compute_progress(db_session, "test-prog-1") == 60.0

    def test_all_segments_done(self, db_session: Session):
        db_session.add(JobRow(
            id="test-done-1",
            status=JobStatus.RENDERING_SEGMENTS.value,
            archetype="OVERLAY",
            preset_id="overlay_classic",
        ))
        for i in range(3):
            db_session.add(SegmentRow(
                job_id="test-done-1",
                index=i,
                status=SegmentStatus.DONE.value,
                duration_seconds=3.0,
            ))
        db_session.commit()
        assert all_segments_done(db_session, "test-done-1") is True

    def test_incomplete_segments_resume(self, db_session: Session):
        """After crash, RUNNING segments show as incomplete for resume."""
        db_session.add(JobRow(
            id="test-resume-1",
            status=JobStatus.RENDERING_SEGMENTS.value,
            archetype="OVERLAY",
            preset_id="overlay_classic",
        ))
        db_session.add(SegmentRow(
            job_id="test-resume-1", index=0,
            status=SegmentStatus.DONE.value, duration_seconds=3.0,
        ))
        db_session.add(SegmentRow(
            job_id="test-resume-1", index=1,
            status=SegmentStatus.RUNNING.value, duration_seconds=3.0,
        ))
        db_session.add(SegmentRow(
            job_id="test-resume-1", index=2,
            status=SegmentStatus.PENDING.value, duration_seconds=3.0,
        ))
        db_session.commit()

        incomplete = get_incomplete_segments(db_session, "test-resume-1")
        assert len(incomplete) == 2
        assert incomplete[0].index == 1  # was RUNNING → needs retry
        assert incomplete[1].index == 2  # PENDING

    def test_job_persisted_across_sessions(self, db_engine):
        """Job state survives session close (simulating restart)."""
        from sqlalchemy.orm import sessionmaker
        factory = sessionmaker(bind=db_engine, expire_on_commit=False)

        # Session 1: create job
        s1 = factory()
        s1.add(JobRow(
            id="persist-test",
            status=JobStatus.RENDERING_SEGMENTS.value,
            archetype="OVERLAY",
            preset_id="overlay_classic",
            progress_pct=40.0,
        ))
        s1.add(SegmentRow(
            job_id="persist-test", index=0,
            status=SegmentStatus.DONE.value, duration_seconds=3.0,
        ))
        s1.add(SegmentRow(
            job_id="persist-test", index=1,
            status=SegmentStatus.RUNNING.value, duration_seconds=3.0,
        ))
        s1.commit()
        s1.close()

        # Session 2: "restart" — should see same state
        s2 = factory()
        job = s2.query(JobRow).filter_by(id="persist-test").first()
        assert job is not None
        assert job.status == JobStatus.RENDERING_SEGMENTS.value
        assert job.progress_pct == 40.0

        incomplete = get_incomplete_segments(s2, "persist-test")
        assert len(incomplete) == 1
        assert incomplete[0].index == 1
        s2.close()

    def test_fallback_flag_persisted(self, db_session: Session):
        """Fallback info persists in DB."""
        db_session.add(JobRow(
            id="fallback-test",
            status=JobStatus.QUEUED.value,
            archetype="OVERLAY",
            preset_id="overlay_classic",
        ))
        db_session.commit()

        transition_job(
            db_session, "fallback-test", JobStatus.DONE,
            fallback_used=True,
            fallback_reason="Engine unavailable, used template",
            output_uri="file:///fallback.mp4",
        )
        job = db_session.query(JobRow).filter_by(id="fallback-test").first()
        assert job.fallback_used is True
        assert "template" in job.fallback_reason
        assert job.output_uri == "file:///fallback.mp4"

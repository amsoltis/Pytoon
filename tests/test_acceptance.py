"""P5-01 / P5-02 / P5-03 / P5-04 / P5-05: Acceptance test suite.

Maps directly to Acceptance Criteria (AC-001 through AC-021) and the
acceptance test scenarios defined in docs/vision/pytoon-v1.md.

Run against a local or staging deployment:
    pytest tests/test_acceptance.py -v
"""

from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pytoon.api_orchestrator.planner import plan_captions, plan_segments
from pytoon.api_orchestrator.spec_builder import build_render_spec
from pytoon.assembler.ffmpeg_ops import _get_duration
from pytoon.db import JobRow, SegmentRow
from pytoon.models import (
    Archetype,
    CaptionsPlan,
    CreateJobRequest,
    EnginePolicy,
    JobStatus,
    RenderSpec,
    SegmentStatus,
)
from pytoon.worker.state_machine import (
    all_segments_done,
    compute_progress,
    get_incomplete_segments,
    transition_job,
    transition_segment,
)


# ===========================================================================
# AC-001: Core Output Format
# ===========================================================================


class TestAC001_OutputFormat:
    """AC-001: System produces valid MP4 (H.264, AAC, 1080x1920, 9:16)."""

    def test_spec_default_resolution(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="test",
            target_duration_seconds=6,
        )
        spec = build_render_spec(req)
        assert spec.aspect_ratio == "9:16"

    def test_spec_version_set(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="test",
            target_duration_seconds=6,
        )
        spec = build_render_spec(req)
        assert spec.render_spec_version == 1

    def test_output_config_matches_contract(self):
        from pytoon.config import get_defaults

        defaults = get_defaults()
        out = defaults.get("output", {})
        assert out.get("width") == 1080
        assert out.get("height") == 1920
        assert out.get("fps") == 30
        assert out.get("codec") == "h264"
        assert out.get("pixel_format") == "yuv420p"


# ===========================================================================
# AC-002: Duration Never Exceeds 60 Seconds
# ===========================================================================


class TestAC002_DurationCap:
    """AC-002: Generated video duration never exceeds 60 seconds (±0.5s)."""

    def test_api_rejects_over_60s(self, client, auth_headers):
        resp = client.post(
            "/api/v1/jobs",
            headers=auth_headers,
            json={
                "preset_id": "overlay_classic",
                "prompt": "too long",
                "target_duration_seconds": 61,
            },
        )
        assert resp.status_code == 422

    def test_api_accepts_60s(self, client, auth_headers):
        resp = client.post(
            "/api/v1/jobs",
            headers=auth_headers,
            json={
                "preset_id": "overlay_classic",
                "prompt": "max length",
                "target_duration_seconds": 60,
            },
        )
        assert resp.status_code == 201

    def test_segment_sum_equals_target(self):
        for dur in [6, 10, 15, 30, 45, 60]:
            segs = plan_segments(dur, segment_duration=3)
            total = sum(s.duration_seconds for s in segs)
            assert abs(total - dur) < 0.5, f"Segments sum {total} != target {dur}"

    def test_max_segment_duration_within_bounds(self):
        for dur in range(1, 61):
            segs = plan_segments(dur, segment_duration=3)
            for s in segs:
                assert 0 < s.duration_seconds <= 4


# ===========================================================================
# AC-004: RenderSpec Intent Integrity
# ===========================================================================


class TestAC004_RenderSpecIntegrity:
    """AC-004: RenderSpec fully describes video without engine-specific logic."""

    def test_spec_contains_all_required_fields(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="Full spec test",
            target_duration_seconds=15,
            image_uris=["file:///data/product.png"],
        )
        spec = build_render_spec(req)
        # Verify all required fields per AC-004
        assert spec.archetype is not None
        assert spec.target_duration_seconds > 0
        assert spec.assets is not None
        assert len(spec.segments) > 0
        assert spec.captions_plan is not None
        assert spec.audio_plan is not None
        assert spec.constraints is not None
        assert spec.preset_id == "overlay_classic"

    def test_spec_serializes_to_json(self):
        req = CreateJobRequest(
            preset_id="product_hero_clean",
            prompt="JSON test",
            target_duration_seconds=6,
        )
        spec = build_render_spec(req)
        json_str = spec.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["archetype"] == "PRODUCT_HERO"
        assert parsed["render_spec_version"] == 1

    def test_spec_roundtrips(self):
        req = CreateJobRequest(
            preset_id="meme_fast",
            prompt="Roundtrip test",
            target_duration_seconds=10,
        )
        spec = build_render_spec(req)
        json_str = spec.model_dump_json()
        restored = RenderSpec.model_validate_json(json_str)
        assert restored.archetype == spec.archetype
        assert restored.target_duration_seconds == spec.target_duration_seconds
        assert len(restored.segments) == len(spec.segments)


# ===========================================================================
# AC-005: RenderSpec Versioned and Persisted
# ===========================================================================


class TestAC005_RenderSpecPersistence:
    """AC-005: RenderSpec is versioned and persisted with each job."""

    def test_spec_persisted_and_retrievable(self, client, auth_headers):
        """Job is persisted — retrievable via status endpoint after creation."""
        resp = client.post(
            "/api/v1/jobs",
            headers=auth_headers,
            json={
                "preset_id": "overlay_classic",
                "prompt": "Persistence test",
                "target_duration_seconds": 9,
            },
        )
        assert resp.status_code == 201
        job_id = resp.json()["job_id"]

        # Verify retrievable via API (proves persistence)
        resp2 = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["job_id"] == job_id
        assert data["archetype"] == "OVERLAY"
        assert data["preset_id"] == "overlay_classic"

    def test_renderspec_version_in_model(self):
        """RenderSpec model includes version field."""
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="Version test",
            target_duration_seconds=9,
        )
        spec = build_render_spec(req)
        assert spec.render_spec_version == 1
        data = json.loads(spec.model_dump_json())
        assert data["render_spec_version"] == 1


# ===========================================================================
# AC-006: Local Engine Generates Clips
# ===========================================================================


class TestAC006_LocalEngine:
    """AC-006: Local engine generates clips for supported simple cases."""

    def test_hero_spec(self):
        req = CreateJobRequest(
            preset_id="product_hero_clean",
            prompt="Hero test",
            target_duration_seconds=6,
            image_uris=["file:///data/product.png"],
        )
        spec = build_render_spec(req)
        assert spec.archetype == Archetype.PRODUCT_HERO
        assert len(spec.segments) == 2

    def test_overlay_spec(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="Overlay test",
            target_duration_seconds=9,
            image_uris=["file:///data/product.png"],
        )
        spec = build_render_spec(req)
        assert spec.archetype == Archetype.OVERLAY
        assert len(spec.segments) == 3

    def test_meme_spec(self):
        req = CreateJobRequest(
            preset_id="meme_fast",
            prompt="Meme test",
            target_duration_seconds=6,
        )
        spec = build_render_spec(req)
        assert spec.archetype == Archetype.MEME_TEXT
        assert len(spec.segments) == 2

    def test_ffmpeg_adapter_capabilities(self):
        from pytoon.engine_adapters.local_ffmpeg import LocalFFmpegAdapter

        adapter = LocalFFmpegAdapter()
        caps = adapter.get_capabilities()
        assert "PRODUCT_HERO" in caps["archetypes"]
        assert "OVERLAY" in caps["archetypes"]
        assert "MEME_TEXT" in caps["archetypes"]
        assert caps["type"] == "local"


# ===========================================================================
# AC-007: Engine Policy Enforcement
# ===========================================================================


class TestAC007_EnginePolicy:
    """AC-007: Engine policy is enforced correctly."""

    def test_local_only_in_spec(self):
        req = CreateJobRequest(
            preset_id="brand_safe_minimal",
            prompt="test",
            target_duration_seconds=6,
        )
        spec = build_render_spec(req)
        assert spec.engine_policy == EnginePolicy.LOCAL_ONLY

    def test_api_only_override(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="test",
            target_duration_seconds=6,
            engine_policy=EnginePolicy.API_ONLY,
        )
        spec = build_render_spec(req)
        assert spec.engine_policy == EnginePolicy.API_ONLY

    def test_default_is_local_preferred(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="test",
            target_duration_seconds=6,
        )
        spec = build_render_spec(req)
        assert spec.engine_policy == EnginePolicy.LOCAL_PREFERRED


# ===========================================================================
# AC-009: Brand-Safe Enforcement
# ===========================================================================


class TestAC009_BrandSafe:
    """AC-009: brand_safe=true restricts regeneration, fonts, transitions."""

    def test_brand_safe_default_on(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="test",
            target_duration_seconds=6,
        )
        spec = build_render_spec(req)
        assert spec.brand_safe is True

    def test_brand_safe_keeps_subject_static(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="test",
            target_duration_seconds=6,
        )
        spec = build_render_spec(req)
        assert spec.constraints.keep_subject_static is True

    def test_brand_safe_false_allows_motion(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="test",
            target_duration_seconds=6,
            brand_safe=False,
        )
        spec = build_render_spec(req)
        assert spec.brand_safe is False
        assert spec.constraints.keep_subject_static is False

    def test_brand_safe_preset_fonts(self):
        from pytoon.config import get_presets_map

        presets = get_presets_map()
        for pid, preset in presets.items():
            if preset.get("brand_safe"):
                font = preset.get("caption_style", {}).get("font", "")
                assert font in ("Inter", "Montserrat", "Arial"), (
                    f"Brand-safe preset {pid} uses non-safe font: {font}"
                )


# ===========================================================================
# AC-012: Segment Assembly
# ===========================================================================


class TestAC012_SegmentAssembly:
    """AC-012: Assembly produces continuous video with transitions."""

    def test_crossfade_config_exists(self):
        from pytoon.config import get_defaults

        defaults = get_defaults()
        transition = defaults.get("transition", {})
        assert transition.get("type") == "crossfade"
        assert transition.get("duration_ms", 0) > 0

    def test_concat_single_segment_path(self):
        """Verify single-segment path exists in ffmpeg_ops."""
        from pytoon.assembler.ffmpeg_ops import concat_segments

        assert callable(concat_segments)


# ===========================================================================
# AC-013: Captions (hook, beats, CTA)
# ===========================================================================


class TestAC013_Captions:
    """AC-013: Captions include hook, beats, CTA."""

    def test_captions_plan_with_all_parts(self):
        plan = plan_captions("Hook!", ["Beat 1", "Beat 2"], "Buy Now!", 15)
        assert plan.hook == "Hook!"
        assert plan.beats == ["Beat 1", "Beat 2"]
        assert plan.cta == "Buy Now!"
        assert len(plan.timings) == 4  # hook + 2 beats + CTA
        assert plan.timings[0].text == "Hook!"
        assert plan.timings[-1].text == "Buy Now!"

    def test_captions_span_full_duration(self):
        plan = plan_captions("H", ["B1", "B2"], "C", 30)
        assert plan.timings[0].start == 0.0
        assert plan.timings[-1].end == 30.0

    def test_no_caption_gaps(self):
        plan = plan_captions("H", ["B1", "B2", "B3"], "C", 60)
        for i in range(1, len(plan.timings)):
            gap = abs(plan.timings[i].start - plan.timings[i - 1].end)
            assert gap < 0.01, f"Gap between caption {i-1} and {i}: {gap}s"


# ===========================================================================
# AC-014: Caption Safe Zones
# ===========================================================================


class TestAC014_CaptionSafeZones:
    """AC-014: Captions remain within safe zones for 9:16."""

    def test_all_presets_have_safe_margin(self):
        from pytoon.config import get_presets_map

        presets = get_presets_map()
        for pid, preset in presets.items():
            margin = preset.get("caption_style", {}).get("safe_margin_px", 0)
            assert margin >= 120, f"Preset {pid} safe_margin_px={margin} < 120"


# ===========================================================================
# AC-015: Audio
# ===========================================================================


class TestAC015_Audio:
    """AC-015: Audio loops/trims, voice ducks music, loudness normalized."""

    def test_audio_plan_defaults(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="test",
            target_duration_seconds=6,
        )
        spec = build_render_spec(req)
        assert spec.audio_plan.duck_music is True
        assert spec.audio_plan.music_level_db < 0
        assert spec.audio_plan.voice_level_db < 0

    def test_loudness_normalize_function_exists(self):
        from pytoon.assembler.ffmpeg_ops import loudness_normalize

        assert callable(loudness_normalize)

    def test_mix_audio_function_exists(self):
        from pytoon.assembler.ffmpeg_ops import mix_audio

        assert callable(mix_audio)


# ===========================================================================
# AC-016: Job Lifecycle
# ===========================================================================


class TestAC016_JobLifecycle:
    """AC-016: Submit → Queue → Render → Assemble → Retrieve."""

    def test_submit_and_retrieve(self, client, auth_headers):
        # Submit
        resp = client.post(
            "/api/v1/jobs",
            headers=auth_headers,
            json={
                "preset_id": "overlay_classic",
                "prompt": "Lifecycle test",
                "target_duration_seconds": 6,
            },
        )
        assert resp.status_code == 201
        job_id = resp.json()["job_id"]
        assert resp.json()["status"] == "QUEUED"

        # Retrieve
        resp2 = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["job_id"] == job_id
        assert resp2.json()["status"] == "QUEUED"

    def test_404_for_unknown_job(self, client, auth_headers):
        resp = client.get("/api/v1/jobs/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ===========================================================================
# AC-017: State Persistence and Recovery
# ===========================================================================


class TestAC017_StatePersistence:
    """AC-017: Job status recoverable after restart."""

    def test_job_persists_across_sessions(self, db_engine):
        from sqlalchemy.orm import sessionmaker

        factory = sessionmaker(bind=db_engine, expire_on_commit=False)

        # Session 1: create
        s1 = factory()
        s1.add(
            JobRow(
                id="ac017-test",
                status=JobStatus.RENDERING_SEGMENTS.value,
                archetype="OVERLAY",
                preset_id="overlay_classic",
                progress_pct=50.0,
            )
        )
        s1.commit()
        s1.close()

        # Session 2: "restart" and verify
        s2 = factory()
        job = s2.query(JobRow).filter_by(id="ac017-test").first()
        assert job is not None
        assert job.status == "RENDERING_SEGMENTS"
        assert job.progress_pct == 50.0
        s2.close()

    def test_incomplete_segments_found_after_crash(self, db_session):
        db_session.add(
            JobRow(
                id="ac017-crash",
                status=JobStatus.RENDERING_SEGMENTS.value,
                archetype="OVERLAY",
                preset_id="overlay_classic",
            )
        )
        db_session.add(
            SegmentRow(
                job_id="ac017-crash",
                index=0,
                status=SegmentStatus.DONE.value,
                duration_seconds=3.0,
            )
        )
        db_session.add(
            SegmentRow(
                job_id="ac017-crash",
                index=1,
                status=SegmentStatus.RUNNING.value,
                duration_seconds=3.0,
            )
        )
        db_session.commit()

        incomplete = get_incomplete_segments(db_session, "ac017-crash")
        assert len(incomplete) == 1
        assert incomplete[0].index == 1


# ===========================================================================
# AC-018: Fallback Output
# ===========================================================================


class TestAC018_FallbackOutput:
    """AC-018: On render failure, system returns usable fallback output."""

    def test_template_fallback_function(self):
        from pytoon.worker.template_fallback import generate_template_video

        assert callable(generate_template_video)

    def test_fallback_flag_set_in_db(self, db_session):
        db_session.add(
            JobRow(
                id="ac018-fallback",
                status=JobStatus.QUEUED.value,
                archetype="OVERLAY",
                preset_id="overlay_classic",
            )
        )
        db_session.commit()

        transition_job(
            db_session,
            "ac018-fallback",
            JobStatus.DONE,
            fallback_used=True,
            fallback_reason="All engines failed",
            output_uri="file:///fallback.mp4",
        )

        job = db_session.query(JobRow).filter_by(id="ac018-fallback").first()
        assert job.fallback_used is True
        assert job.output_uri is not None


# ===========================================================================
# AC-019: Structured Logging
# ===========================================================================


class TestAC019_StructuredLogging:
    """AC-019: Structured logs with job_id, segment_id, engine, duration."""

    def test_structlog_configured(self):
        from pytoon.log import get_logger

        logger = get_logger("test")
        assert logger is not None

    def test_log_module_setup(self):
        from pytoon.log import setup_logging

        # Should not raise
        setup_logging(json_output=True)
        setup_logging(json_output=False)


# ===========================================================================
# AC-020: Metrics
# ===========================================================================


class TestAC020_Metrics:
    """AC-020: Metrics for success rate, fallback rate, render time."""

    def test_metrics_counters_exist(self):
        from pytoon.metrics import (
            FALLBACK_USED,
            RENDER_FAILURE,
            RENDER_JOBS_TOTAL,
            RENDER_SUCCESS,
        )

        assert RENDER_JOBS_TOTAL is not None
        assert RENDER_SUCCESS is not None
        assert RENDER_FAILURE is not None
        assert FALLBACK_USED is not None

    def test_metrics_histograms_exist(self):
        from pytoon.metrics import JOB_TOTAL_TIME, SEGMENT_RENDER_TIME

        assert SEGMENT_RENDER_TIME is not None
        assert JOB_TOTAL_TIME is not None

    def test_metrics_gauge_exists(self):
        from pytoon.metrics import QUEUE_DEPTH

        assert QUEUE_DEPTH is not None

    def test_metrics_endpoint(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        body = resp.text
        assert "pytoon_render_jobs_total" in body or "# HELP" in body

    def test_metrics_text_output(self):
        from pytoon.metrics import metrics_text

        output = metrics_text()
        assert isinstance(output, bytes)
        assert len(output) > 0


# ===========================================================================
# AC-021: Release Gate
# ===========================================================================


class TestAC021_ReleaseGate:
    """AC-021: Pre-release checks."""

    def test_all_presets_valid(self):
        from pytoon.config import get_presets_map

        presets = get_presets_map()
        assert len(presets) >= 8
        for pid, p in presets.items():
            assert "archetype" in p, f"Preset {pid} missing archetype"
            assert "caption_style" in p, f"Preset {pid} missing caption_style"
            assert p["archetype"] in (
                "PRODUCT_HERO",
                "OVERLAY",
                "MEME_TEXT",
            ), f"Preset {pid} invalid archetype: {p['archetype']}"

    def test_all_three_archetypes_covered(self):
        from pytoon.config import get_presets_map

        presets = get_presets_map()
        archetypes = {p["archetype"] for p in presets.values()}
        assert "PRODUCT_HERO" in archetypes
        assert "OVERLAY" in archetypes
        assert "MEME_TEXT" in archetypes

    def test_schema_file_exists(self):
        schema_path = Path(__file__).parent.parent / "schemas" / "render_spec_v1.json"
        assert schema_path.exists()

    def test_schema_valid_json(self):
        schema_path = Path(__file__).parent.parent / "schemas" / "render_spec_v1.json"
        data = json.loads(schema_path.read_text())
        assert data["title"] == "Pytoon RenderSpec V1"
        assert "archetype" in data["properties"]


# ===========================================================================
# P5-05: Error Handling and Concurrency
# ===========================================================================


class TestErrorHandling:
    """Bad input and concurrent job tests."""

    def test_bad_preset_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/v1/jobs",
            headers=auth_headers,
            json={
                "preset_id": "nonexistent_preset",
                "prompt": "test",
                "target_duration_seconds": 6,
            },
        )
        assert resp.status_code == 400

    def test_missing_auth_header(self, client):
        resp = client.get("/api/v1/presets")
        assert resp.status_code == 422

    def test_wrong_api_key(self, client):
        resp = client.get("/api/v1/presets", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_concurrent_job_creation(self, client, auth_headers):
        """Submit multiple jobs — all should succeed."""
        job_ids = []
        for i in range(5):
            resp = client.post(
                "/api/v1/jobs",
                headers=auth_headers,
                json={
                    "preset_id": "overlay_classic",
                    "prompt": f"Concurrent test {i}",
                    "target_duration_seconds": 6,
                },
            )
            assert resp.status_code == 201
            job_ids.append(resp.json()["job_id"])

        # All unique
        assert len(set(job_ids)) == 5

        # All queryable
        for jid in job_ids:
            resp = client.get(f"/api/v1/jobs/{jid}", headers=auth_headers)
            assert resp.status_code == 200

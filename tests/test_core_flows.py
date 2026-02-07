"""A) Core flow tests — overlay 15s, hero I2V 6s, meme 10s."""

from __future__ import annotations

import json
import math
from unittest.mock import AsyncMock, patch

import pytest

from pytoon.api_orchestrator.planner import plan_segments, plan_captions
from pytoon.api_orchestrator.spec_builder import build_render_spec
from pytoon.models import (
    Archetype,
    CaptionsPlan,
    CreateJobRequest,
    EnginePolicy,
    JobStatus,
    RenderSpec,
    SegmentStatus,
)


# ---------------------------------------------------------------------------
# Planner unit tests
# ---------------------------------------------------------------------------

class TestPlanSegments:
    def test_15s_segments(self):
        segs = plan_segments(15, segment_duration=3)
        assert len(segs) == 5
        total = sum(s.duration_seconds for s in segs)
        assert total == 15.0

    def test_6s_segments(self):
        segs = plan_segments(6, segment_duration=3)
        assert len(segs) == 2

    def test_10s_segments(self):
        segs = plan_segments(10, segment_duration=3)
        assert len(segs) == 4  # ceil(10/3) = 4
        total = sum(s.duration_seconds for s in segs)
        assert total == 10.0

    def test_60s_segments(self):
        segs = plan_segments(60, segment_duration=3)
        assert len(segs) == 20
        total = sum(s.duration_seconds for s in segs)
        assert total == 60.0


class TestPlanCaptions:
    def test_captions_timing(self):
        plan = plan_captions("Hook!", ["Beat 1", "Beat 2"], "CTA!", 15)
        assert len(plan.timings) == 4
        assert plan.timings[0].start == 0.0
        assert plan.timings[-1].end == 15.0


# ---------------------------------------------------------------------------
# Spec builder tests
# ---------------------------------------------------------------------------

class TestSpecBuilder:
    def test_overlay_15s(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="Beautiful product shot",
            target_duration_seconds=15,
            image_uris=["file:///data/product.png"],
        )
        spec = build_render_spec(req)
        assert spec.archetype == Archetype.OVERLAY
        assert spec.target_duration_seconds == 15
        assert spec.brand_safe is True
        assert len(spec.segments) == 5
        assert spec.preset_id == "overlay_classic"

    def test_hero_6s(self):
        req = CreateJobRequest(
            preset_id="product_hero_clean",
            prompt="Showcase product",
            target_duration_seconds=6,
            image_uris=["file:///data/product.png"],
        )
        spec = build_render_spec(req)
        assert spec.archetype == Archetype.PRODUCT_HERO
        assert spec.target_duration_seconds == 6
        assert len(spec.segments) == 2

    def test_meme_10s(self):
        req = CreateJobRequest(
            preset_id="meme_fast",
            prompt="Funny meme about cats",
            target_duration_seconds=10,
        )
        spec = build_render_spec(req)
        assert spec.archetype == Archetype.MEME_TEXT
        assert spec.target_duration_seconds == 10
        assert len(spec.segments) == 4

    def test_unknown_preset_raises(self):
        req = CreateJobRequest(
            preset_id="nonexistent",
            prompt="test",
        )
        with pytest.raises(ValueError, match="Unknown preset"):
            build_render_spec(req)

    def test_brand_safe_override(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="test",
            brand_safe=False,
        )
        spec = build_render_spec(req)
        assert spec.brand_safe is False

    def test_engine_policy_override(self):
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="test",
            engine_policy=EnginePolicy.API_ONLY,
        )
        spec = build_render_spec(req)
        assert spec.engine_policy == EnginePolicy.API_ONLY


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------

class TestAPIRoutes:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_list_presets(self, client, auth_headers):
        resp = client.get("/api/v1/presets", headers=auth_headers)
        assert resp.status_code == 200
        presets = resp.json()["presets"]
        assert len(presets) >= 8

    def test_create_job_overlay_15s(self, client, auth_headers):
        resp = client.post("/api/v1/jobs", headers=auth_headers, json={
            "preset_id": "overlay_classic",
            "prompt": "Product showcase",
            "target_duration_seconds": 15,
            "image_uris": ["file:///data/product.png"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "QUEUED"
        assert data["segments"] == 5

    def test_create_job_hero_6s(self, client, auth_headers):
        resp = client.post("/api/v1/jobs", headers=auth_headers, json={
            "preset_id": "product_hero_clean",
            "prompt": "Product hero",
            "target_duration_seconds": 6,
            "image_uris": ["file:///data/product.png"],
        })
        assert resp.status_code == 201
        assert resp.json()["segments"] == 2

    def test_create_job_meme_10s(self, client, auth_headers):
        resp = client.post("/api/v1/jobs", headers=auth_headers, json={
            "preset_id": "meme_fast",
            "prompt": "Funny meme about cats",
            "target_duration_seconds": 10,
        })
        assert resp.status_code == 201
        assert resp.json()["segments"] == 4

    def test_get_job_status(self, client, auth_headers):
        # Create first
        resp = client.post("/api/v1/jobs", headers=auth_headers, json={
            "preset_id": "overlay_classic",
            "prompt": "test",
            "target_duration_seconds": 6,
        })
        job_id = resp.json()["job_id"]

        # Query
        resp2 = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "QUEUED"

    def test_get_segments(self, client, auth_headers):
        resp = client.post("/api/v1/jobs", headers=auth_headers, json={
            "preset_id": "overlay_classic",
            "prompt": "test",
            "target_duration_seconds": 9,
        })
        job_id = resp.json()["job_id"]

        resp2 = client.get(f"/api/v1/jobs/{job_id}/segments", headers=auth_headers)
        assert resp2.status_code == 200
        segs = resp2.json()["segments"]
        assert len(segs) == 3
        assert all(s["status"] == "PENDING" for s in segs)

    def test_auth_required(self, client):
        resp = client.get("/api/v1/presets")
        assert resp.status_code == 422  # missing header

    def test_bad_api_key(self, client):
        resp = client.get("/api/v1/presets", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_not_found_job(self, client, auth_headers):
        resp = client.get("/api/v1/jobs/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

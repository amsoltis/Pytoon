"""B) 60-second requirement tests."""

from __future__ import annotations

import math

import pytest

from pytoon.api_orchestrator.planner import plan_captions, plan_segments
from pytoon.api_orchestrator.spec_builder import build_render_spec
from pytoon.models import CreateJobRequest


class TestSixtySeconds:
    def test_overlay_60s_segments(self):
        """Output exactly 60s — correct number of segments."""
        segs = plan_segments(60, segment_duration=3)
        assert len(segs) == 20
        total = sum(s.duration_seconds for s in segs)
        assert abs(total - 60.0) < 0.5

    def test_overlay_60s_spec(self):
        """Full spec for 60s overlay."""
        req = CreateJobRequest(
            preset_id="overlay_classic",
            prompt="Long product video",
            target_duration_seconds=60,
            image_uris=["file:///data/product.png"],
        )
        spec = build_render_spec(req)
        assert spec.target_duration_seconds == 60
        assert len(spec.segments) == 20
        total_dur = sum(s.duration_seconds for s in spec.segments)
        assert abs(total_dur - 60.0) < 0.5

    def test_captions_consistent_60s(self):
        """Captions should span the entire 60s duration."""
        plan = plan_captions(
            "Hook line!", ["Beat 1", "Beat 2", "Beat 3"], "Check it out!", 60
        )
        assert plan.timings[0].start == 0.0
        assert plan.timings[-1].end == 60.0
        # No gaps
        for i in range(1, len(plan.timings)):
            assert abs(plan.timings[i].start - plan.timings[i - 1].end) < 0.01

    def test_crossfade_config_exists(self):
        """Ensure defaults specify crossfade."""
        from pytoon.config import get_defaults
        defaults = get_defaults()
        transition = defaults.get("transition", {})
        assert transition.get("type") == "crossfade"
        assert transition.get("duration_ms", 0) > 0

    def test_segment_duration_within_bounds(self):
        """Each segment must be 2–4 seconds."""
        for dur in range(1, 61):
            segs = plan_segments(dur, segment_duration=3)
            for s in segs:
                assert 0 < s.duration_seconds <= 4, f"Bad segment dur {s.duration_seconds} for total {dur}"

    def test_api_creates_60s_job(self, client, auth_headers):
        resp = client.post("/api/v1/jobs", headers=auth_headers, json={
            "preset_id": "overlay_classic",
            "prompt": "60 second product video",
            "target_duration_seconds": 60,
            "image_uris": ["file:///data/product.png"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["segments"] == 20

    def test_reject_over_60s(self, client, auth_headers):
        resp = client.post("/api/v1/jobs", headers=auth_headers, json={
            "preset_id": "overlay_classic",
            "prompt": "too long",
            "target_duration_seconds": 61,
        })
        assert resp.status_code == 422  # validation error

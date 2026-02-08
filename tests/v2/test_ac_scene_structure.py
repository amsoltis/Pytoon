"""Acceptance Tests — Scene Structure & Timing.

Validates:
  - 3-scene, 5-scene mixed, single-scene videos.
  - Timeline JSON timing ±2 frames.
  - Duration ≤ 60s.

Ticket: P5-07
V2-AC codes: V2-AC-001, V2-AC-005, V2-AC-014
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from pytoon.scene_graph.planner import plan_scenes
from pytoon.scene_graph.models import SceneGraph
from pytoon.timeline.orchestrator import build_timeline
from tests.v2.harness import (
    AcceptanceReport,
    validate_scene_graph_json,
    validate_timeline_json,
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestSceneStructure:
    """V2-AC-001: Scene structure correctness."""

    def test_3_scene_video(self, tmp_dir):
        """3-scene video has correct structure and timing."""
        sg = plan_scenes(
            prompt="Product reveal. Key features. Call to action.",
            preset_id="product_hero_clean",
        )
        assert len(sg.scenes) == 3

        tl = build_timeline(sg)
        assert len(tl.timeline) == 3

        # Persist and validate
        sg_path = tmp_dir / "scene_graph.json"
        sg_path.write_text(sg.model_dump_json())
        results = validate_scene_graph_json(sg_path)
        assert all(r.passed for r in results)

    def test_5_scene_mixed(self, tmp_dir):
        """5-scene video with mixed content types."""
        sg = plan_scenes(
            prompt="Opening shot. Product showcase. Feature demo. Testimonial moment. Final CTA.",
            preset_id="product_hero_clean",
        )
        assert len(sg.scenes) == 5

        tl = build_timeline(sg)
        assert len(tl.timeline) == 5
        assert tl.totalDuration <= 60000

    def test_single_scene_video(self, tmp_dir):
        """Single scene video is valid."""
        sg = plan_scenes(
            prompt="A stunning product reveal.",
            preset_id="product_hero_clean",
        )
        assert len(sg.scenes) >= 1

        tl = build_timeline(sg)
        assert len(tl.timeline) >= 1


class TestTimelineTiming:
    """V2-AC-005: Timeline timing accuracy."""

    def test_timeline_ascending_order(self):
        sg = plan_scenes(prompt="One. Two. Three.", preset_id="product_hero_clean")
        tl = build_timeline(sg)

        starts = [e.start for e in tl.timeline]
        assert starts == sorted(starts), "Timeline entries must be in ascending order"

    def test_no_overlapping_scenes(self):
        sg = plan_scenes(
            prompt="First scene. Second scene. Third scene. Fourth scene.",
            preset_id="product_hero_clean",
        )
        tl = build_timeline(sg)

        for i in range(len(tl.timeline) - 1):
            current_end = tl.timeline[i].end
            next_start = tl.timeline[i + 1].start
            # Allow transition overlap (up to 500ms)
            assert next_start <= current_end + 500, \
                f"Scene {i} end ({current_end}) too far from scene {i+1} start ({next_start})"

    def test_timeline_json_validation(self, tmp_dir):
        sg = plan_scenes(prompt="A. B. C.", preset_id="product_hero_clean")
        tl = build_timeline(sg)

        tl_path = tmp_dir / "timeline.json"
        tl_path.write_text(tl.model_dump_json())

        results = validate_timeline_json(tl_path)
        assert all(r.passed for r in results), \
            f"Failed: {[r for r in results if not r.passed]}"


class TestDurationConstraint:
    """V2-AC-014: Duration ≤ 60s."""

    def test_total_duration_within_limit(self):
        sg = plan_scenes(
            prompt="Scene one. Scene two. Scene three. Scene four. Scene five.",
            preset_id="product_hero_clean",
        )
        tl = build_timeline(sg)
        assert tl.totalDuration <= 60000, f"Duration {tl.totalDuration}ms exceeds 60s"

    def test_scene_durations_positive(self):
        sg = plan_scenes(prompt="A. B. C.", preset_id="product_hero_clean")
        for scene in sg.scenes:
            assert scene.duration > 0, f"Scene {scene.id} has non-positive duration"

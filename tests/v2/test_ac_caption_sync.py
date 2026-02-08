"""Acceptance Tests — Caption & Voice Synchronization.

Validates:
  - Caption scene containment.
  - Text accuracy.
  - Voice mapper distributes sentences correctly.
  - Alignment fallback works.
  - Ducking regions detected.

Ticket: P5-08
V2-AC codes: V2-AC-002, V2-AC-003, V2-AC-004, V2-AC-008, V2-AC-017
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pytoon.audio_manager.alignment import AlignedCaption, align_captions
from pytoon.audio_manager.ducking import detect_duck_regions
from pytoon.audio_manager.voice_mapper import map_voice_to_scenes
from pytoon.scene_graph.planner import plan_scenes
from pytoon.timeline.orchestrator import build_timeline
from tests.v2.harness import validate_caption_sync


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestCaptionContainment:
    """V2-AC-002/004: Captions only during correct scenes."""

    def test_captions_within_scene_bounds(self):
        """Each caption must fall within its assigned scene boundaries."""
        sg = plan_scenes(
            prompt="Opening line. Middle content. Closing statement.",
            preset_id="product_hero_clean",
        )
        tl = build_timeline(sg)

        scene_boundaries = [
            (e.sceneId, e.start, e.end) for e in tl.timeline
        ]

        captions = [
            {"text": c.text, "start": c.start, "end": c.end, "sceneId": c.sceneId}
            for c in tl.tracks.captions
        ]

        results = validate_caption_sync(captions, scene_boundaries, tolerance_ms=200)
        assert all(r.passed for r in results), \
            f"Caption sync failures: {[r for r in results if not r.passed]}"

    def test_4_scene_caption_coverage(self):
        """4+ scenes all get captions."""
        sg = plan_scenes(
            prompt="Intro hook. Feature one. Feature two. Call to action.",
            preset_id="product_hero_clean",
        )
        tl = build_timeline(sg)

        assert len(tl.tracks.captions) >= 4
        scene_ids_with_captions = {c.sceneId for c in tl.tracks.captions}
        scene_ids = {s.id for s in sg.scenes}
        assert scene_ids_with_captions == scene_ids


class TestVoiceMapping:
    """V2-AC-003: Voice-to-scene mapping accuracy."""

    def test_tts_path_maps_correctly(self):
        """TTS script maps sentences to scenes in order."""
        result = map_voice_to_scenes(
            "First sentence for scene one. Second for scene two. Third for three.",
            [1, 2, 3],
            [5000, 5000, 5000],
            voice_duration_ms=12000,
        )
        assert len(result.segments) == 3
        assert result.segments[0].scene_id == 1
        assert result.segments[1].scene_id == 2
        assert result.segments[2].scene_id == 3

    def test_user_voiceover_transcription_fallback(self, tmp_dir):
        """When no audio file exists, alignment falls back to even-split."""
        result = align_captions(
            tmp_dir / "nonexistent.wav",
            "Hello world. How are you. Goodbye.",
            [(1, 0, 5000), (2, 5000, 10000), (3, 10000, 15000)],
        )
        assert result.method == "even_split"
        assert len(result.captions) == 3

    def test_text_accuracy(self):
        """Caption text matches the original transcript sentences."""
        transcript = "Product launch. Amazing features. Buy now."
        mapping = map_voice_to_scenes(
            transcript,
            [1, 2, 3],
            [5000, 5000, 5000],
        )
        all_text = " ".join(s.text for s in mapping.segments)
        for sentence in ["Product launch", "Amazing features", "Buy now"]:
            assert sentence in all_text


class TestDuckingValidation:
    """V2-AC-008: Music ducks during speech."""

    def test_ducking_regions_detected_for_voice(self):
        """Duck regions are created for voice-active segments."""
        voice_segments = [(1000, 4000), (6000, 9000), (11000, 14000)]
        regions = detect_duck_regions(voice_segments)
        assert len(regions) == 3

    def test_ducking_minimum_db_difference(self):
        """Duck amount is at least 10dB."""
        regions = detect_duck_regions([(0, 5000)])
        assert abs(regions[0].duck_amount_db) >= 10

    def test_ducking_with_4_scenes(self):
        """4+ scenes worth of voice segments all get ducking."""
        segs = [(0, 3000), (4000, 7000), (8000, 11000), (12000, 15000)]
        regions = detect_duck_regions(segs)
        assert len(regions) == 4

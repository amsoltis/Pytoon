"""Phase 4 tests — Audio & Captions.

Tests:
  - Voice-to-scene mapping
  - Forced alignment (even-time fallback)
  - Caption styling + safe zone enforcement
  - Duck region detection
  - SRT generation
  - Background music pipeline
  - Audio mixing logic
  - End-to-end: planner → timeline → captions → SRT

Tickets: P4-01 through P4-11
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pytoon.audio_manager.alignment import (
    AlignedCaption,
    AlignmentResult,
    _even_time_split,
    align_captions,
)
from pytoon.audio_manager.caption_renderer import (
    CaptionStyle,
    _auto_wrap,
    _ms_to_srt_tc,
    _safe_position,
    generate_srt,
    get_caption_style,
)
from pytoon.audio_manager.ducking import DuckRegion, detect_duck_regions
from pytoon.audio_manager.music import _dbfs_to_multiplier
from pytoon.audio_manager.voice_mapper import (
    VoiceMappingResult,
    map_voice_to_scenes,
    _split_sentences,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# ---------------------------------------------------------------------------
# P4-03: Voice-to-scene mapping
# ---------------------------------------------------------------------------

class TestVoiceMapper:
    def test_equal_sentences_and_scenes(self):
        result = map_voice_to_scenes(
            "Scene one. Scene two. Scene three.",
            [1, 2, 3],
            [5000, 5000, 5000],
        )
        assert len(result.segments) == 3
        assert result.segments[0].scene_id == 1
        assert result.segments[1].scene_id == 2
        assert result.segments[2].scene_id == 3

    def test_more_sentences_than_scenes(self):
        result = map_voice_to_scenes(
            "One. Two. Three. Four. Five.",
            [1, 2],
            [5000, 5000],
        )
        assert len(result.segments) == 2
        # Both scenes get text
        assert result.segments[0].text != ""
        assert result.segments[1].text != ""

    def test_more_scenes_than_sentences(self):
        result = map_voice_to_scenes(
            "Only one sentence.",
            [1, 2, 3],
            [5000, 5000, 5000],
        )
        assert len(result.segments) == 1
        assert result.segments[0].scene_id == 1
        assert 2 in result.scenes_without_voice
        assert 3 in result.scenes_without_voice

    def test_empty_transcript(self):
        result = map_voice_to_scenes("", [1, 2, 3], [5000, 5000, 5000])
        assert len(result.segments) == 0

    def test_sentence_splitting(self):
        sentences = _split_sentences("Hello world. How are you? I'm fine!")
        assert len(sentences) == 3

    def test_voice_duration_proportional(self):
        result = map_voice_to_scenes(
            "Short. A much longer sentence with many words.",
            [1, 2],
            [5000, 5000],
            voice_duration_ms=8000,
        )
        # Longer sentence should get more time
        assert result.segments[1].estimated_duration_ms > result.segments[0].estimated_duration_ms


# ---------------------------------------------------------------------------
# P4-04: Forced alignment (even-time fallback)
# ---------------------------------------------------------------------------

class TestAlignment:
    def test_even_time_split_basic(self):
        result = _even_time_split(
            "First sentence. Second sentence. Third sentence.",
            [(1, 0, 5000), (2, 5000, 10000), (3, 10000, 15000)],
        )
        assert len(result.captions) == 3
        assert result.method == "even_split"
        for cap in result.captions:
            assert cap.start_ms < cap.end_ms

    def test_even_time_split_respects_scene_bounds(self):
        result = _even_time_split(
            "One. Two.",
            [(1, 0, 5000), (2, 5000, 10000)],
        )
        for cap in result.captions:
            # Find scene
            for sid, s, e in [(1, 0, 5000), (2, 5000, 10000)]:
                if cap.scene_id == sid:
                    assert cap.start_ms >= s
                    assert cap.end_ms <= e

    def test_even_time_split_more_sentences(self):
        result = _even_time_split(
            "A. B. C. D.",
            [(1, 0, 10000)],
        )
        assert len(result.captions) == 4
        # All within scene bounds
        for cap in result.captions:
            assert cap.start_ms >= 0
            assert cap.end_ms <= 10000

    def test_align_no_audio_falls_back(self, tmp_dir):
        """When audio file doesn't exist, falls back to even-time split."""
        result = align_captions(
            tmp_dir / "nonexistent.wav",
            "Hello. World.",
            [(1, 0, 5000), (2, 5000, 10000)],
        )
        assert result.method == "even_split"
        assert len(result.captions) == 2


# ---------------------------------------------------------------------------
# P4-05/06: Caption styling + safe zones
# ---------------------------------------------------------------------------

class TestCaptionStyling:
    def test_default_style(self):
        style = CaptionStyle()
        assert style.font_size == 48
        assert style.font_color == "white"
        assert style.position == "bottom-center"

    def test_get_style_from_preset(self):
        preset = {
            "caption_style": {
                "font": "Roboto",
                "fontsize": 56,
                "fontcolor": "yellow",
            }
        }
        style = get_caption_style(preset, brand_safe=False)
        assert style.font_family == "Roboto"
        assert style.font_size == 56
        assert style.font_color == "yellow"

    def test_brand_safe_min_font(self):
        preset = {"caption_style": {"font_size": 16}}
        style = get_caption_style(preset, brand_safe=True)
        assert style.font_size >= 24  # Brand-safe minimum

    def test_safe_position_bottom(self):
        x, y = _safe_position("bottom-center", 48, 1)
        assert "150" in y  # Bottom safe zone margin
        assert "text_w" in x  # Centered

    def test_safe_position_top(self):
        x, y = _safe_position("top-center", 48, 1)
        assert "100" in y or y == str(120)

    def test_auto_wrap_short_text(self):
        result = _auto_wrap("Short", 48, 1080)
        assert "\\n" not in result

    def test_auto_wrap_long_text(self):
        long_text = "This is a very long caption text that should be wrapped to multiple lines"
        result = _auto_wrap(long_text, 48, 1080)
        assert "\\n" in result

    def test_auto_wrap_max_lines(self):
        very_long = " ".join(["word"] * 100)
        result = _auto_wrap(very_long, 48, 1080)
        lines = result.split("\\n")
        assert len(lines) <= 2  # Max 2 lines

    def test_srt_timecode(self):
        assert _ms_to_srt_tc(0) == "00:00:00,000"
        assert _ms_to_srt_tc(1500) == "00:00:01,500"
        assert _ms_to_srt_tc(65000) == "00:01:05,000"
        assert _ms_to_srt_tc(3661234) == "01:01:01,234"


# ---------------------------------------------------------------------------
# P4-08: Audio ducking
# ---------------------------------------------------------------------------

class TestDucking:
    def test_detect_duck_regions_basic(self):
        voice_segments = [(1000, 3000), (5000, 7000)]
        regions = detect_duck_regions(voice_segments)
        assert len(regions) == 2
        assert regions[0].start_ms < 1000  # Padded before
        assert regions[0].end_ms > 3000    # Padded after

    def test_merge_overlapping_regions(self):
        voice_segments = [(1000, 3000), (3050, 5000)]  # Close together
        regions = detect_duck_regions(voice_segments)
        assert len(regions) == 1  # Merged due to padding

    def test_no_voice_no_regions(self):
        regions = detect_duck_regions([])
        assert len(regions) == 0

    def test_custom_duck_amount(self):
        regions = detect_duck_regions(
            [(0, 1000)], duck_amount_db=-18.0,
        )
        assert regions[0].duck_amount_db == -18.0


# ---------------------------------------------------------------------------
# SRT generation
# ---------------------------------------------------------------------------

class TestSRTGeneration:
    def test_generate_srt(self, tmp_dir):
        captions = [
            {"text": "Hello world", "start": 0, "end": 2000},
            {"text": "Second caption", "start": 2500, "end": 5000},
        ]
        srt_path = generate_srt(captions, tmp_dir / "test.srt")
        assert srt_path.exists()
        content = srt_path.read_text()
        assert "Hello world" in content
        assert "00:00:00,000 --> 00:00:02,000" in content
        assert "00:00:02,500 --> 00:00:05,000" in content

    def test_generate_srt_empty(self, tmp_dir):
        srt_path = generate_srt([], tmp_dir / "empty.srt")
        assert srt_path.exists()


# ---------------------------------------------------------------------------
# Music pipeline
# ---------------------------------------------------------------------------

class TestMusicPipeline:
    def test_dbfs_conversion(self):
        assert abs(_dbfs_to_multiplier(0) - 1.0) < 0.001
        assert abs(_dbfs_to_multiplier(-6) - 0.5012) < 0.01
        assert abs(_dbfs_to_multiplier(-12) - 0.2512) < 0.01


# ---------------------------------------------------------------------------
# Integration: planner → timeline → captions → SRT
# ---------------------------------------------------------------------------

class TestCaptionEndToEnd:
    def test_planner_to_captions_to_srt(self, tmp_dir):
        """Full flow: plan scenes → build timeline → extract captions → SRT."""
        from pytoon.scene_graph.planner import plan_scenes
        from pytoon.timeline.orchestrator import build_timeline

        sg = plan_scenes(
            prompt="Product reveal. Key features. Call to action.",
            preset_id="product_hero_clean",
            brand_safe=True,
        )
        tl = build_timeline(sg)

        # Extract caption data
        captions_data = [
            {
                "text": cap.text,
                "start": cap.start,
                "end": cap.end,
                "sceneId": cap.sceneId,
            }
            for cap in tl.tracks.captions
        ]
        assert len(captions_data) == 3

        # Generate SRT
        srt_path = generate_srt(captions_data, tmp_dir / "captions.srt")
        assert srt_path.exists()
        content = srt_path.read_text()
        assert "Product reveal" in content
        assert "Key features" in content

    def test_voice_mapper_to_alignment(self, tmp_dir):
        """Map voice to scenes then align with even-time fallback."""
        mapping = map_voice_to_scenes(
            "Introducing our product. Amazing features. Get yours today.",
            [1, 2, 3],
            [5000, 5000, 5000],
            voice_duration_ms=12000,
        )
        assert len(mapping.segments) == 3

        # Build scene boundaries from mapping
        scene_boundaries = [(1, 0, 5000), (2, 5000, 10000), (3, 10000, 15000)]

        alignment = align_captions(
            tmp_dir / "fake_audio.wav",  # Will fall back to even-split
            "Introducing our product. Amazing features. Get yours today.",
            scene_boundaries,
        )
        assert alignment.method == "even_split"
        assert len(alignment.captions) == 3

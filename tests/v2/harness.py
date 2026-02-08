"""V2 Acceptance Test Harness — programmatic validation framework.

Provides reusable validators for V2 output artifacts:
  - Video validation (resolution, duration, codec, corruption).
  - Timeline JSON validation (schema conformance, timing).
  - Scene Graph JSON validation.
  - Caption sync accuracy measurement.
  - Structured test report generation per V2-AC code.

Ticket: P5-06
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pytoon.log import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    ac_code: str              # V2-AC-XXX
    check_name: str
    passed: bool
    details: str = ""
    measured_value: Optional[str] = None
    expected_value: Optional[str] = None


@dataclass
class AcceptanceReport:
    """Structured acceptance report for a V2 job."""

    job_id: str
    results: list[ValidationResult] = field(default_factory=list)
    all_passed: bool = False

    def add(self, result: ValidationResult) -> None:
        self.results.append(result)

    def finalize(self) -> None:
        self.all_passed = all(r.passed for r in self.results)

    def summary(self) -> dict:
        return {
            "job_id": self.job_id,
            "total_checks": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "failed": sum(1 for r in self.results if not r.passed),
            "all_passed": self.all_passed,
            "details": [
                {
                    "ac_code": r.ac_code,
                    "check": r.check_name,
                    "passed": r.passed,
                    "details": r.details,
                }
                for r in self.results
            ],
        }


# ---------------------------------------------------------------------------
# Video validation
# ---------------------------------------------------------------------------

def validate_video_output(
    video_path: Path,
    expected_width: int = 1080,
    expected_height: int = 1920,
    max_duration_seconds: float = 60.0,
) -> list[ValidationResult]:
    """Validate a V2 output video against requirements."""
    results: list[ValidationResult] = []

    # Check file exists
    results.append(ValidationResult(
        ac_code="V2-AC-013",
        check_name="output_exists",
        passed=video_path.exists(),
        details=f"File: {video_path}",
    ))

    if not video_path.exists():
        return results

    # Probe video
    probe = _probe_video(video_path)
    if not probe:
        results.append(ValidationResult(
            ac_code="V2-AC-013",
            check_name="valid_mp4",
            passed=False,
            details="ffprobe failed",
        ))
        return results

    # Resolution
    width = probe.get("width", 0)
    height = probe.get("height", 0)
    results.append(ValidationResult(
        ac_code="V2-AC-014",
        check_name="resolution",
        passed=width == expected_width and height == expected_height,
        measured_value=f"{width}x{height}",
        expected_value=f"{expected_width}x{expected_height}",
    ))

    # Duration
    duration = probe.get("duration", 0.0)
    results.append(ValidationResult(
        ac_code="V2-AC-014",
        check_name="duration_within_limit",
        passed=0 < duration <= max_duration_seconds,
        measured_value=f"{duration:.2f}s",
        expected_value=f"<= {max_duration_seconds}s",
    ))

    # Codec
    video_codec = probe.get("video_codec", "")
    audio_codec = probe.get("audio_codec", "")
    results.append(ValidationResult(
        ac_code="V2-AC-013",
        check_name="video_codec_h264",
        passed="h264" in video_codec.lower(),
        measured_value=video_codec,
        expected_value="h264",
    ))
    results.append(ValidationResult(
        ac_code="V2-AC-013",
        check_name="audio_codec_aac",
        passed="aac" in audio_codec.lower(),
        measured_value=audio_codec,
        expected_value="aac",
    ))

    return results


def validate_timeline_json(timeline_path: Path) -> list[ValidationResult]:
    """Validate a Timeline JSON file."""
    results: list[ValidationResult] = []

    results.append(ValidationResult(
        ac_code="V2-AC-005",
        check_name="timeline_file_exists",
        passed=timeline_path.exists(),
    ))

    if not timeline_path.exists():
        return results

    try:
        data = json.loads(timeline_path.read_text())
    except json.JSONDecodeError as e:
        results.append(ValidationResult(
            ac_code="V2-AC-005",
            check_name="timeline_valid_json",
            passed=False,
            details=str(e),
        ))
        return results

    results.append(ValidationResult(
        ac_code="V2-AC-005",
        check_name="timeline_valid_json",
        passed=True,
    ))

    # Check required fields
    results.append(ValidationResult(
        ac_code="V2-AC-005",
        check_name="timeline_has_entries",
        passed=len(data.get("timeline", [])) > 0,
        measured_value=str(len(data.get("timeline", []))),
    ))

    # Check total duration
    total = data.get("totalDuration", 0)
    results.append(ValidationResult(
        ac_code="V2-AC-014",
        check_name="timeline_duration_valid",
        passed=1000 <= total <= 60000,
        measured_value=f"{total}ms",
        expected_value="1000-60000ms",
    ))

    # Check ascending order
    entries = data.get("timeline", [])
    is_ascending = all(
        entries[i].get("start", 0) <= entries[i + 1].get("start", 0)
        for i in range(len(entries) - 1)
    )
    results.append(ValidationResult(
        ac_code="V2-AC-005",
        check_name="timeline_ascending_order",
        passed=is_ascending,
    ))

    return results


def validate_scene_graph_json(sg_path: Path) -> list[ValidationResult]:
    """Validate a Scene Graph JSON file."""
    results: list[ValidationResult] = []

    results.append(ValidationResult(
        ac_code="V2-AC-001",
        check_name="scene_graph_file_exists",
        passed=sg_path.exists(),
    ))

    if not sg_path.exists():
        return results

    try:
        data = json.loads(sg_path.read_text())
    except json.JSONDecodeError:
        results.append(ValidationResult(
            ac_code="V2-AC-001",
            check_name="scene_graph_valid_json",
            passed=False,
        ))
        return results

    results.append(ValidationResult(
        ac_code="V2-AC-001",
        check_name="scene_graph_valid_json",
        passed=True,
    ))

    scenes = data.get("scenes", [])
    results.append(ValidationResult(
        ac_code="V2-AC-001",
        check_name="scene_graph_has_scenes",
        passed=len(scenes) >= 1,
        measured_value=str(len(scenes)),
    ))

    # Unique IDs
    ids = [s.get("id") for s in scenes]
    results.append(ValidationResult(
        ac_code="V2-AC-001",
        check_name="scene_graph_unique_ids",
        passed=len(ids) == len(set(ids)),
    ))

    return results


def validate_caption_sync(
    captions: list[dict],
    scene_boundaries: list[tuple[int, int, int]],
    tolerance_ms: int = 100,
) -> list[ValidationResult]:
    """Validate caption timing against scene boundaries."""
    results: list[ValidationResult] = []

    for cap in captions:
        scene_id = cap.get("sceneId")
        start = cap.get("start", 0)
        end = cap.get("end", 0)

        # Find scene
        scene_match = None
        for sid, s_start, s_end in scene_boundaries:
            if sid == scene_id:
                scene_match = (s_start, s_end)
                break

        if scene_match:
            s_start, s_end = scene_match
            within = (start >= s_start - tolerance_ms) and (end <= s_end + tolerance_ms)
            results.append(ValidationResult(
                ac_code="V2-AC-004",
                check_name=f"caption_within_scene_{scene_id}",
                passed=within,
                measured_value=f"[{start},{end}]ms",
                expected_value=f"[{s_start},{s_end}]ms ±{tolerance_ms}ms",
            ))

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _probe_video(path: Path) -> dict | None:
    """Probe video file and return key metadata."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries",
                "stream=codec_type,codec_name,width,height",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        info: dict = {}

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                info["video_codec"] = stream.get("codec_name", "")
                info["width"] = stream.get("width", 0)
                info["height"] = stream.get("height", 0)
            elif stream.get("codec_type") == "audio":
                info["audio_codec"] = stream.get("codec_name", "")

        fmt = data.get("format", {})
        info["duration"] = float(fmt.get("duration", 0))

        return info
    except Exception:
        return None

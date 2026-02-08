# Phase 2 Exit Gate — Scene Sequencing MVP

**Status:** PASS  
**Date:** 2026-02-07  
**Ticket:** P2-EXIT

---

## Exit Criteria Checklist

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Scene Graph Pydantic models validate against `scene_graph_v2.json` schema | PASS | `pytoon/scene_graph/models.py` — SceneGraph, Scene, SceneMedia with validators for unique IDs, total ≤60s, media constraints |
| 2 | Timeline Pydantic models validate against `timeline_v2.json` schema | PASS | `pytoon/timeline/models.py` — Timeline, TimelineEntry, Tracks with ascending order, overlap, caption-within-bounds validators |
| 3 | Heuristic Scene Planner produces valid SceneGraph from text, images, or both | PASS | `pytoon/scene_graph/planner.py` — 4 strategies (shot markers, sentences, images, template). 7 unit tests pass. |
| 4 | Timeline Orchestrator converts SceneGraph → Timeline | PASS | `pytoon/timeline/orchestrator.py` — sequential layout with transition overlap, track generation. 5 unit tests pass. |
| 5 | Stub renderer produces placeholder clips per scene | PASS | `pytoon/scene_graph/stub_renderer.py` — image Ken Burns & solid-color placeholder modes via FFmpeg |
| 6 | Scene composition with cut/crossfade transitions | PASS | `pytoon/assembler/ffmpeg_ops.py::compose_scenes()` — xfade filter chain with per-scene transition types |
| 7 | Timeline-based caption burn-in | PASS | `pytoon/assembler/ffmpeg_ops.py::burn_captions_v2()` — ms-precision drawtext with safe zones |
| 8 | V2 API endpoints under `/api/v2/` | PASS | `pytoon/api_orchestrator/routes.py` — POST/GET /api/v2/jobs, GET /scene-graph, GET /timeline |
| 9 | V2 worker pipeline dispatches V2 jobs through scene-based flow | PASS | `pytoon/worker/runner.py::_run_job_v2()` — plan→timeline→render→compose→export |
| 10 | DB extended with SceneRow and V2 columns on JobRow | PASS | `pytoon/db.py` — SceneRow table, version/scene_graph_json/timeline_json columns |
| 11 | State machine extended with V2 transitions | PASS | `pytoon/worker/state_machine.py` — transition_job_v2, transition_scene, compute_scene_progress |
| 12 | End-to-end integration tests pass | PASS | `tests/test_v2_e2e.py` — 13 tests covering planner, orchestrator, serialization |
| 13 | V1 backward compatibility — zero test regression | PASS | Full suite: **108/108 tests pass** (95 V1 + 13 V2) |
| 14 | V1 API endpoints (`/api/v1/`) remain operational | PASS | V1 router unchanged, all V1 API tests pass |
| 15 | JSON round-trip: SceneGraph → JSON → SceneGraph validates | PASS | `TestSceneGraphSerialization::test_json_round_trip` |
| 16 | JSON round-trip: Timeline → JSON → Timeline validates | PASS | `TestTimelineOrchestrator::test_json_round_trip` |

---

## New Files Created

| File | Purpose |
|------|---------|
| `pytoon/scene_graph/__init__.py` | Module init |
| `pytoon/scene_graph/models.py` | Scene Graph Pydantic models (P2-01) |
| `pytoon/scene_graph/planner.py` | Heuristic Scene Planner (P2-03) |
| `pytoon/scene_graph/stub_renderer.py` | Stub scene renderer (P2-05) |
| `pytoon/timeline/__init__.py` | Module init |
| `pytoon/timeline/models.py` | Timeline Pydantic models (P2-02) |
| `pytoon/timeline/orchestrator.py` | Timeline Orchestrator (P2-04) |
| `pytoon/audio_manager/__init__.py` | Module init (placeholder for Phase 4) |
| `tests/test_v2_e2e.py` | V2 integration tests (P2-11) |

## Files Extended (V1 preserved)

| File | Changes |
|------|---------|
| `pytoon/db.py` | Added `SceneRow` table, V2 columns on `JobRow` (P2-10) |
| `pytoon/models.py` | Added V2 enums and request/response models (P2-08) |
| `pytoon/api_orchestrator/routes.py` | Added `/api/v2/` router (P2-08) |
| `pytoon/api_orchestrator/app.py` | Registered `router_v2`, bumped version to 2.0.0 |
| `pytoon/assembler/ffmpeg_ops.py` | Added `compose_scenes()` (P2-06), `burn_captions_v2()` (P2-07) |
| `pytoon/assembler/pipeline.py` | Added `assemble_job_v2()` (P2-09) |
| `pytoon/worker/runner.py` | Added V2 dispatch and `_run_job_v2()` (P2-09) |
| `pytoon/worker/state_machine.py` | Added V2 state transition helpers (P2-09) |

---

## Data Flow Walkthrough

**Input:** `POST /api/v2/jobs` with prompt "Product reveal. Key features. Buy now." and 3 images.

1. **API** validates preset, calls Scene Planner → 3-scene SceneGraph.
2. **Worker** picks up job, loads SceneGraph from DB.
3. **Timeline Orchestrator** lays out 3 scenes sequentially with 500ms crossfade transitions → Timeline with video/caption/audio tracks.
4. **Stub Renderer** generates 3 placeholder clips (image Ken Burns for scenes with assets, teal placeholder for prompt-only).
5. **Composer** chains clips with xfade filters per timeline transition specs.
6. **Caption Burn-in** overlays timed text per timeline caption tracks.
7. **Final Export** produces 1080x1920 H.264 MP4 with AAC audio track.
8. **DB** updated with scene_graph_json, timeline_json, output_uri, thumbnail_uri.
9. **API** returns full scene-level progress via `GET /api/v2/jobs/{id}`.

---

## Phase 2 EXIT: SATISFIED

Phase 3 (AI Engine Integration) is now unblocked.

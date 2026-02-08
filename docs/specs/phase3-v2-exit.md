# Phase 3 Exit Gate — AI Engine Integration

**Status:** PASS  
**Date:** 2026-02-07  
**Ticket:** P3-EXIT

---

## Exit Criteria Checklist

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | ExternalEngineAdapter abstract base class defined | PASS | `pytoon/engine_adapters/external_base.py` — EngineResult dataclass + ABC with generate(), health_check(), max_duration(), supports_image_input() |
| 2 | Runway adapter with submit→poll→download, error handling | PASS | `pytoon/engine_adapters/runway.py` — Gen-3a turbo, moderation detection, rate limit handling, timeout |
| 3 | Pika adapter with submit→poll→download, error handling | PASS | `pytoon/engine_adapters/pika.py` — stylized effects, image upload, moderation/rate-limit/timeout |
| 4 | Luma adapter with submit→poll→download, error handling | PASS | `pytoon/engine_adapters/luma.py` — Dream Machine API, keyframe image support, fallback handling |
| 5 | Engine Manager with 6-priority selection rules | PASS | `pytoon/engine_adapters/engine_manager.py::select_engine_for_scene()` — explicit engine → image=local → cinematic=runway → stylized=pika → physics=luma → default |
| 6 | Prompt construction pipeline with style/mood/brand-safe cues | PASS | `pytoon/engine_adapters/prompt_builder.py` — build_prompt(), sanitize_prompt(), rephrase_for_moderation() |
| 7 | Async parallel scene rendering | PASS | `pytoon/engine_adapters/engine_manager.py::render_all_scenes()` — asyncio.Semaphore, concurrent dispatch, callback progress |
| 8 | Engine response validation (ffprobe) | PASS | `pytoon/engine_adapters/validator.py` — exists/non-empty/valid-MP4/duration±20%/resolution≥720p |
| 9 | 3-level fallback chain (primary→alternate→local) | PASS | `engine_manager.py::_render_with_fallback()` — Level 1/2/3, auto-rephrase on moderation, local always succeeds |
| 10 | Scene media integration (scale/crop/trim) | PASS | `pytoon/engine_adapters/media_processor.py` — process_clip() with freeze-frame extension, center-crop scaling |
| 11 | Wired into V2 worker pipeline | PASS | `pytoon/worker/runner.py::_run_job_v2()` — Engine Manager replaces stub renderer, media processing pipeline |
| 12 | Engine config in engine.yaml | PASS | `config/engine.yaml` — V2 section with all 3 engines, fallback chain, prompt sanitization |
| 13 | 23 Phase 3 tests pass | PASS | `tests/test_v2_phase3.py` — interface, prompt, sanitization, selection rules, fallback, parallel, e2e |
| 14 | Full suite: 131/131 tests pass | PASS | Zero regression across V1 (95) + V2-P2 (13) + V2-P3 (23) |
| 15 | Fallback guaranteed output: no API keys → all scenes → local | PASS | `TestParallelRendering::test_render_all_scenes_local_fallback` verified |

---

## New Files Created

| File | Purpose |
|------|---------|
| `pytoon/engine_adapters/external_base.py` | ExternalEngineAdapter ABC + EngineResult (P3-01) |
| `pytoon/engine_adapters/runway.py` | Runway Gen-3a adapter (P3-02) |
| `pytoon/engine_adapters/pika.py` | Pika Labs adapter (P3-03) |
| `pytoon/engine_adapters/luma.py` | Luma Dream Machine adapter (P3-04) |
| `pytoon/engine_adapters/engine_manager.py` | Engine Manager + fallback + parallel dispatch (P3-05/07/09) |
| `pytoon/engine_adapters/prompt_builder.py` | Prompt construction + sanitization (P3-06) |
| `pytoon/engine_adapters/validator.py` | Clip validation via ffprobe (P3-08) |
| `pytoon/engine_adapters/media_processor.py` | Scale/crop/trim clips to timeline (P3-10) |
| `tests/test_v2_phase3.py` | 23 Phase 3 tests |

## Files Extended

| File | Changes |
|------|---------|
| `config/engine.yaml` | Added V2 engine config section |
| `pytoon/worker/runner.py` | Replaced stub renderer with Engine Manager + media processor |

---

## Engine Selection Flow

```
Scene metadata
    │
    ├─ explicit engine? ───────────► use that engine
    ├─ media.type == image? ───────► local (FFmpeg Ken Burns)
    ├─ style = cinematic? ─────────► runway
    ├─ style = stylized? ──────────► pika
    ├─ style = physics/product? ───► luma
    └─ no match ───────────────────► default (config)
```

## Fallback Flow

```
Primary Engine → [fail/timeout/moderation]
    │
    ├─ moderation? → rephrase + retry same engine
    │
    ├─ still failed → Alternate Engine 1
    │                    └─ failed → Alternate Engine 2
    │                                   └─ failed → Local FFmpeg (always succeeds)
    │
    └─ Scene timeline slot preserved in all cases
```

---

## Phase 3 EXIT: SATISFIED

Phase 4 (Audio & Captions) is now unblocked.

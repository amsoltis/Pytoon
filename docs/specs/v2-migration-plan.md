# V2 Migration Plan from V1 Codebase

**Ticket:** P1-08  
**Acceptance Criteria:** V2-AC-021  
**Source:** pytoon-v2.md "Evolution from V1 to V2" (line 5), V1 codebase structure

---

## 1. Guiding Principle

V2 is an **evolution**, not a rewrite. The V1 codebase is the foundation. V1 modules are classified as REUSE (no changes), EXTEND (add V2 capabilities alongside V1 logic), or REPLACE/NEW (new modules that provide V2-only functionality). V1 API endpoints remain operational for backward compatibility.

---

## 2. Module Classification

### 2.1 REUSE (No Changes Required)

These V1 modules work as-is for both V1 and V2 jobs.

| Module | Path | Reason |
|--------|------|--------|
| Storage | `pytoon/storage.py` | File storage abstraction is version-agnostic |
| Queue | `pytoon/queue.py` | Redis job queue is version-agnostic |
| Logging | `pytoon/log.py` | Structlog foundation; V2 adds fields but core unchanged |
| Metrics | `pytoon/metrics.py` | Prometheus base; V2 adds counters but core unchanged |
| Authentication | `pytoon/api_orchestrator/auth.py` | API key auth is version-agnostic |
| Input Validation | `pytoon/api_orchestrator/validation.py` | File/content type validation reused; V2 adds new validators |

### 2.2 EXTEND (Add V2 Capabilities)

These modules gain V2 features while preserving V1 behavior.

| Module | Path | V2 Changes |
|--------|------|------------|
| Config | `pytoon/config.py` | Add `get_engine_config_v2()`, load V2 engine config section from `config/engine.yaml` |
| Database | `pytoon/db.py` | Add `SceneRow` table. Add columns to `JobRow`: `version`, `scene_graph_json`, `timeline_json`, `voiceover_path`, `caption_track_path`. V1 jobs use `version=1` and ignore new columns. |
| Models | `pytoon/models.py` | Add V2 enums (`SceneStatus`, extended `JobStatus` with V2 states, `EnginePolicyV2`). Add V2 API models (`CreateJobRequestV2`, `JobStatusResponseV2`). V1 models unchanged. |
| API Routes | `pytoon/api_orchestrator/routes.py` | Add V2 endpoints under `/api/v2/` alongside V1 routes. V1 endpoints unchanged. |
| Worker Runner | `pytoon/worker/runner.py` | Add V2 job detection (`job.version == 2`) and V2 pipeline dispatch. V1 pipeline path unchanged. |
| State Machine | `pytoon/worker/state_machine.py` | Add V2 job states (`PLANNING_SCENES`, `BUILDING_TIMELINE`, `RENDERING_SCENES`, `COMPOSING`, `AUDIO_ASSEMBLY`, `FINALIZING`). V1 states unchanged. |
| FFmpeg Ops | `pytoon/assembler/ffmpeg_ops.py` | Add `compose_scenes()` (scene-level composition with xfade), enhanced `burn_captions()` (timeline-driven, styled), caption safe zone enforcement. V1 functions unchanged. |
| Assembly Pipeline | `pytoon/assembler/pipeline.py` | Add `assemble_job_v2()` that uses timeline-driven assembly. V1's `assemble_job()` unchanged. |
| Planner | `pytoon/api_orchestrator/planner.py` | V1 planner unchanged. V2 uses new `pytoon/scene_graph/planner.py` (separate module). |
| Spec Builder | `pytoon/api_orchestrator/spec_builder.py` | V1 spec builder unchanged. V2 uses Scene Graph builder instead of RenderSpec builder for V2 jobs. |

### 2.3 NEW (V2-Only Modules)

| Module | Path | Purpose |
|--------|------|---------|
| Scene Graph Models | `pytoon/scene_graph/models.py` | Pydantic models for Scene Graph v2.0 |
| Scene Planner | `pytoon/scene_graph/planner.py` | Heuristic (and future AI) scene planning |
| Stub Renderer | `pytoon/scene_graph/stub_renderer.py` | Placeholder scene renderer for Phase 2 |
| Timeline Models | `pytoon/timeline/models.py` | Pydantic models for Timeline v2.0 |
| Timeline Orchestrator | `pytoon/timeline/orchestrator.py` | Timeline construction from Scene Graph |
| External Engine Base | `pytoon/engine_adapters/external_base.py` | Abstract base for external AI engine adapters |
| Runway Adapter | `pytoon/engine_adapters/runway.py` | Runway Gen-2/Gen-4 integration |
| Pika Adapter | `pytoon/engine_adapters/pika.py` | Pika Labs API integration |
| Luma Adapter | `pytoon/engine_adapters/luma.py` | Luma AI Dream Machine integration |
| Engine Manager | `pytoon/engine_adapters/engine_manager.py` | Multi-engine orchestrator with selection rules |
| Prompt Builder | `pytoon/engine_adapters/prompt_builder.py` | Engine prompt construction and sanitization |
| Engine Validator | `pytoon/engine_adapters/validator.py` | Post-generation clip validation |
| TTS Integration | `pytoon/audio_manager/tts.py` | Text-to-speech (primary + backup) |
| Voice Processor | `pytoon/audio_manager/voice_processor.py` | Voiceover ingestion and processing |
| Voice Mapper | `pytoon/audio_manager/voice_mapper.py` | Voice-to-scene mapping |
| Forced Aligner | `pytoon/audio_manager/alignment.py` | Caption synchronization (±100ms) |
| Music Processor | `pytoon/audio_manager/music.py` | Background music pipeline |
| Audio Ducker | `pytoon/audio_manager/ducking.py` | Audio ducking logic |
| Audio Mixer | `pytoon/audio_manager/mixer.py` | Multi-track audio mixing |

---

## 3. API Versioning Strategy

| Endpoint Pattern | Version | Handler |
|-----------------|---------|---------|
| `POST /api/v1/jobs` | V1 | Existing V1 handler → RenderSpec → V1 pipeline |
| `GET /api/v1/jobs/{id}` | V1 | Existing V1 handler |
| `GET /api/v1/jobs/{id}/segments` | V1 | Existing V1 handler |
| `GET /api/v1/presets` | V1 | Existing (shared) |
| `POST /api/v1/assets/upload` | V1 | Existing (shared) |
| `POST /api/v2/jobs` | V2 | New V2 handler → Scene Graph → V2 pipeline |
| `GET /api/v2/jobs/{id}` | V2 | New V2 handler (includes scene-level progress) |
| `GET /api/v2/jobs/{id}/scene-graph` | V2 | New -- returns persisted Scene Graph JSON |
| `GET /api/v2/jobs/{id}/timeline` | V2 | New -- returns persisted Timeline JSON |

Shared endpoints (`/presets`, `/assets/upload`) serve both versions.

---

## 4. Database Migration

### 4.1 New Table: `scene_row`

```sql
CREATE TABLE scene_row (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id    INTEGER NOT NULL,
    job_id      TEXT NOT NULL REFERENCES job_row(job_id),
    scene_index INTEGER NOT NULL,
    description TEXT,
    duration_ms INTEGER NOT NULL,
    media_type  TEXT NOT NULL,       -- 'image' | 'video'
    engine_used TEXT,                -- 'runway' | 'pika' | 'luma' | 'local' | NULL
    status      TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | RENDERING | DONE | FAILED | FALLBACK
    asset_path  TEXT,
    fallback_used BOOLEAN DEFAULT FALSE,
    render_duration_ms INTEGER,
    error_message TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 `job_row` New Columns

```sql
ALTER TABLE job_row ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE job_row ADD COLUMN scene_graph_json TEXT;
ALTER TABLE job_row ADD COLUMN timeline_json TEXT;
ALTER TABLE job_row ADD COLUMN voiceover_path TEXT;
ALTER TABLE job_row ADD COLUMN caption_track_path TEXT;
```

V1 jobs continue to use `version=1` and ignore new columns.

---

## 5. Worker Pipeline Dispatch

```python
# In runner.py
def run_job(job_id: str):
    job = get_job(job_id)
    if job.version == 2:
        run_v2_pipeline(job)   # Scene Graph → Timeline → Engines → Assembly
    else:
        run_v1_pipeline(job)   # RenderSpec → Segments → Assembly (existing)
```

The V1 pipeline path is completely untouched. V2 adds a parallel path.

---

## 6. Configuration Extension

### `config/engine.yaml` V2 Section

Add a `v2:` section alongside the existing V1 engine config (see hybrid-engine-strategy-v2.md for full schema).

### `config/defaults.yaml` V2 Section

Add V2-specific defaults:
```yaml
v2:
  scene_planner: "heuristic"        # heuristic | ai
  default_scene_duration_ms: 5000
  default_transition: "fade"
  default_transition_duration_ms: 500
  tts:
    primary_provider: "elevenlabs"
    backup_provider: "openai"
  audio:
    music_level_db: -12
    voice_level_db: -6
    duck_amount_db: -12
    target_lufs: -14
  caption:
    max_lines: 2
    min_font_size: 20
    default_font_size: 48
```

---

## 7. Testing Strategy

- **V1 regression:** All existing V1 tests must continue to pass after V2 code is added.
- **V2 unit tests:** Each new module gets its own test file in `tests/`.
- **V2 integration tests:** End-to-end tests for V2 pipeline in `tests/v2/`.
- **V1 + V2 coexistence:** Test that submitting a V1 job and a V2 job concurrently works correctly.

---

## 8. Migration Sequence

Phase 2 implements the migration in this order:
1. Add V2 Pydantic models (`scene_graph/models.py`, `timeline/models.py`).
2. Extend DB schema (new table + columns).
3. Implement Scene Planner and Timeline Orchestrator.
4. Add V2 API endpoints.
5. Add V2 worker pipeline dispatch.
6. Wire end-to-end with stub renderer.
7. Verify V1 backward compatibility.

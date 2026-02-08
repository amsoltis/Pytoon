# Pytoon — AI Video Generation Engine

**Version 2.0.0**

Pytoon is a production-grade video generation system that creates **platform-ready 9:16 MP4 short-form videos** from mixed inputs (images, text prompts, presets). V2 introduces cinematic scene composition, multi-engine AI video generation (Runway, Pika, Luma), TTS voiceover, forced-alignment captions, audio ducking, and comprehensive brand-safe controls — all with graceful degradation that always produces a usable output.

---

## Key Features

### V2 (Current)
- **Scene Graph architecture** — hierarchical scene definitions with per-scene media, style, and overlays
- **Timeline Authority** — millisecond-precise temporal orchestration with transition support
- **Multi-engine AI video** — Runway Gen-3, Pika Labs, Luma Dream Machine with 3-level fallback chain
- **Smart engine selection** — per-preset preferences, capability matrix matching, auto-rotation on failure
- **TTS voiceover** — ElevenLabs, OpenAI, Google Cloud TTS with multi-provider fallback
- **Forced-alignment captions** — WhisperX/stable-ts for ±100ms sync accuracy, with even-time fallback
- **Audio pipeline** — background music (trim/loop), ducking during speech, multi-track mixing, -14 LUFS normalization
- **Brand-safe mode** — product image protection, prompt sanitization, transition restriction, color palette enforcement
- **Content moderation** — pre-generation prompt filtering, configurable strictness (strict/standard/off)
- **Color grading** — 6 preset profiles (neutral, warm, cool, vintage, cinematic, vibrant) + LUT support
- **Advanced transitions** — fade, fade_black, swipe_left/right, dissolve (brand-safe restricts to cut/fade)
- **SRT export** — standard subtitle files for accessibility
- **Comprehensive observability** — 20+ Prometheus metrics, structured JSON logging with sensitive data redaction

### V1 (Maintained)
- 3 video archetypes: PRODUCT_HERO, OVERLAY, MEME_TEXT
- Segment-based rendering with crossfade assembly
- ComfyUI local GPU rendering
- 8 config-driven YAML presets
- Resumable jobs with DB state persistence

---

## Repository Layout

```
pytoon/                          # Main Python package
├── models.py                    # Pydantic models (V1 + V2)
├── config.py                    # Config loader (YAML + env)
├── db.py                        # SQLAlchemy (JobRow, SegmentRow, SceneRow)
├── storage.py                   # Filesystem storage
├── log.py                       # Structured logging (structlog + redaction)
├── metrics.py                   # Prometheus metrics (V1 + V2)
├── api_orchestrator/            # FastAPI (V1 + V2 routes)
│   ├── app.py                   # App factory + lifespan
│   └── routes.py                # /api/v1/ + /api/v2/ endpoints
├── scene_graph/                 # V2: Scene planning
│   ├── models.py                # SceneGraph, Scene, SceneMedia Pydantic models
│   ├── planner.py               # 4-strategy scene planner
│   └── stub_renderer.py         # Local FFmpeg fallback renderer
├── timeline/                    # V2: Temporal orchestration
│   ├── models.py                # Timeline, TimelineEntry, Track models
│   └── orchestrator.py          # Scene Graph → Timeline conversion
├── engine_adapters/             # Pluggable render backends
│   ├── base.py                  # V1 abstract interface
│   ├── external_base.py         # V2 abstract interface
│   ├── runway.py                # Runway Gen-3a adapter
│   ├── pika.py                  # Pika Labs adapter
│   ├── luma.py                  # Luma Dream Machine adapter
│   ├── engine_manager.py        # Multi-engine orchestrator + fallback chain
│   ├── engine_selector.py       # Per-preset prefs + smart rotation
│   ├── prompt_builder.py        # Prompt construction + sanitization
│   ├── validator.py             # Clip validation (ffprobe)
│   ├── media_processor.py       # Post-processing (scale/crop/trim)
│   ├── brand_safe.py            # Brand-safe constraint enforcement
│   └── moderation.py            # Content moderation filters
├── audio_manager/               # V2: Audio & caption pipeline
│   ├── tts.py                   # TTS (ElevenLabs/OpenAI/Google/local)
│   ├── voice_processor.py       # Audio ingestion, resampling, ASR
│   ├── voice_mapper.py          # Transcript → scene mapping
│   ├── alignment.py             # Forced alignment (WhisperX/stable-ts)
│   ├── caption_renderer.py      # Styled captions + safe zones + SRT
│   ├── music.py                 # Background music pipeline
│   ├── ducking.py               # Audio ducking during speech
│   └── mixer.py                 # Multi-track mixing + video muxing
├── assembler/                   # FFmpeg assembly pipeline
│   ├── pipeline.py              # V1 + V2 assembly (12-stage V2 pipeline)
│   ├── ffmpeg_ops.py            # Low-level FFmpeg operations
│   ├── transitions.py           # Advanced transition resolution
│   └── color_grading.py         # Color profiles + LUT application
└── worker/                      # Background job processing
    ├── runner.py                # V1/V2 job dispatch + full lifecycle
    ├── state_machine.py         # Job/segment/scene state transitions
    ├── performance.py           # Pipeline timing, caching, cleanup
    └── template_fallback.py     # Static template fallback

config/                          # Configuration
├── defaults.yaml                # System defaults + TTS + caption styling
├── presets.yaml                 # Visual presets
└── engine.yaml                  # Engine config, fallback chain, moderation

schemas/                         # JSON Schema definitions
├── render_spec_v1.json          # V1 RenderSpec
├── scene_graph_v2.json          # V2 Scene Graph schema
└── timeline_v2.json             # V2 Timeline schema

docs/                            # Documentation
├── v2-api-reference.md          # V2 API endpoint reference
├── runbooks-v2.md               # 8 operational runbooks
├── vision/
│   ├── pytoon-v1.md             # V1 vision document
│   └── pytoon-v2.md             # V2 vision document
└── specs/                       # Technical specifications
    ├── v2-architecture.md       # Architecture diagrams
    ├── v2-migration-plan.md     # V1 → V2 migration
    ├── hybrid-engine-strategy-v2.md
    ├── audio-caption-manager-v2.md
    ├── brand-safe-v2.md
    ├── output-contract-v2.md
    ├── scene-planner-v2.md
    └── phase{1-5}-v2-exit.md    # Phase gate sign-offs

tests/                           # Test suites (220 tests)
├── conftest.py                  # Shared fixtures
├── test_60s.py                  # V1 duration tests
├── test_v2_e2e.py               # V2 Phase 2 integration tests
├── test_v2_phase3.py            # V2 Phase 3 engine tests
├── test_v2_phase4.py            # V2 Phase 4 audio/caption tests
└── v2/                          # V2 acceptance tests
    ├── harness.py               # Programmatic validation framework
    ├── test_ac_scene_structure.py
    ├── test_ac_caption_sync.py
    ├── test_ac_engine_fallback.py
    ├── test_ac_brand_safety.py
    └── test_failure_injection.py
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- FFmpeg installed and on PATH
- Docker (optional, for full stack)

### Local Development

```bash
# 1. Clone and setup
git clone https://github.com/amsoltis/Pytoon.git
cd Pytoon
cp .env.example .env              # Add API keys for engines/TTS

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Run API server
uvicorn pytoon.api_orchestrator.app:app --reload --port 8000

# 4. Run worker (separate terminal)
python -m pytoon.worker.main

# 5. Run tests
pytest -v                         # All 220 tests
pytest tests/v2/ -v               # V2 acceptance tests only
```

### Docker (Full Stack)

```bash
# Basic (API + Worker + Redis)
docker compose up -d

# Full (+ MinIO storage)
docker compose --profile full up -d
```

Services: API (:8000), Worker, Redis (:6379), MinIO (:9000/:9001, optional)

---

## API Usage

### V2 API (Recommended)

```bash
# Create a V2 job
curl -X POST http://localhost:8000/api/v2/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Product reveal. Key features. Call to action.",
    "media_files": ["file:///data/storage/uploads/product.png"],
    "preset_id": "product_hero_clean",
    "brand_safe": true,
    "voice_script": "Introducing our amazing product.",
    "target_duration_seconds": 30
  }'

# Poll job status
curl http://localhost:8000/api/v2/jobs/{job_id}

# Get Scene Graph
curl http://localhost:8000/api/v2/jobs/{job_id}/scene-graph

# Get Timeline
curl http://localhost:8000/api/v2/jobs/{job_id}/timeline

# Prometheus metrics
curl http://localhost:8000/metrics
```

### V1 API (Legacy, Still Supported)

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "X-API-Key: dev-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "preset_id": "overlay_classic",
    "prompt": "Sleek product showcase",
    "target_duration_seconds": 15,
    "image_uris": ["file:///data/storage/uploads/product.png"]
  }'
```

---

## V2 Output Artifacts

Each V2 job produces:

```
storage/jobs/{job_id}/
├── output.mp4          # Final video (1080x1920, H.264/AAC)
├── thumbnail.jpg       # Key frame thumbnail
├── scene_graph.json    # Persisted Scene Graph
├── timeline.json       # Persisted Timeline
├── captions.srt        # SRT subtitle file
└── scenes/             # Per-scene rendered clips
```

---

## Configuration

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `RUNWAY_API_KEY` | Runway Gen-3 API key |
| `PIKA_API_KEY` | Pika Labs API key |
| `LUMA_API_KEY` | Luma Dream Machine API key |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS API key |
| `OPENAI_API_KEY` | OpenAI TTS API key |
| `REDIS_URL` | Redis connection URL |
| `DATABASE_URL` | SQLAlchemy database URL |
| `STORAGE_ROOT` | Storage root directory |

### Key Defaults

| Setting | Value |
|---------|-------|
| Resolution | 1080x1920 (9:16) |
| FPS | 30 |
| Max duration | 60 seconds |
| Codec | H.264 + AAC |
| Audio normalization | -14 LUFS |
| TTS primary | ElevenLabs |
| Default engine | Runway |
| Brand-safe | Enabled |

---

## V2 Pipeline Architecture

```
User Input → Scene Planner → Scene Graph → Timeline Orchestrator → Timeline
                                                    ↓
Engine Manager (Runway/Pika/Luma + fallback) → Rendered Scenes
                                                    ↓
TTS/Voice Processing → Voice Mapper → Forced Alignment → Captions
                                                    ↓
Music Pipeline → Ducking → Multi-track Mixing → Normalization
                                                    ↓
Scene Composition → Caption Burn-in → Watermark → Audio Mux → Final MP4
```

---

## Documentation

- [V2 API Reference](docs/v2-api-reference.md)
- [V2 Architecture](docs/specs/v2-architecture.md)
- [V2 Vision](docs/vision/pytoon-v2.md)
- [Operational Runbooks](docs/runbooks-v2.md)
- [V1 → V2 Migration](docs/specs/v2-migration-plan.md)

---

## Testing

```bash
# Full suite (220 tests)
pytest -v

# By phase
pytest tests/test_v2_e2e.py -v        # Phase 2: Scene Sequencing
pytest tests/test_v2_phase3.py -v     # Phase 3: Engine Integration
pytest tests/test_v2_phase4.py -v     # Phase 4: Audio & Captions
pytest tests/v2/ -v                    # Phase 5: Acceptance & Reliability
```

---

## License

Proprietary. All rights reserved.

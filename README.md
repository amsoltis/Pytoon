# Pytoon Render Engine (V1)

Local-first service that generates platform-ready **9:16 MP4** short-form videos
from mixed inputs (product/person/image/text + prompts + presets). The system
uses ComfyUI workflows for local GPU rendering, optionally falls back to hosted
API engines, and assembles outputs via ffmpeg.

## Features (V1)

- **3 video archetypes**: PRODUCT_HERO (I2V), OVERLAY (background + product), MEME_TEXT (T2V)
- **Segment-based rendering**: 1–60 second videos via 2–4s segments with crossfade
- **Brand-safe mode**: preserves product identity, no AI regeneration of assets
- **Engine policy**: `local_only` | `local_preferred` | `api_only`
- **Fallback chain**: engine fallback → archetype fallback → static template
- **8 presets**: config-driven YAML (caption style, motion, audio, transitions)
- **ffmpeg assembly**: concat, crossfade, overlay, captions, audio mix, EBU R128 normalization
- **Observability**: structured JSON logs, Prometheus metrics
- **Resumable jobs**: state persisted in DB; survives restarts

## Repository layout

```
pytoon/                     # Main Python package
├── __init__.py
├── models.py               # Pydantic models (RenderSpec, Job, etc.)
├── config.py               # Config loader (YAML + env vars)
├── db.py                   # SQLAlchemy models + session factory
├── storage.py              # Filesystem storage abstraction
├── log.py                  # Structured logging (structlog)
├── metrics.py              # Prometheus metrics
├── queue.py                # Redis job/segment queue
├── api_orchestrator/       # FastAPI API + orchestration
│   ├── app.py              # App factory + lifespan
│   ├── routes.py           # REST endpoints
│   ├── auth.py             # API key auth
│   ├── spec_builder.py     # RenderSpec builder
│   ├── planner.py          # Segment + caption planner
│   └── validation.py       # Upload validation
├── worker/                 # GPU worker
│   ├── main.py             # Entry point + queue loop
│   ├── runner.py           # Job runner (render all segments)
│   ├── state_machine.py    # Job/segment status transitions
│   └── template_fallback.py # Static template video fallback
├── engine_adapters/        # Pluggable render backends
│   ├── base.py             # Abstract interface
│   ├── selector.py         # Engine selection + fallback
│   ├── local_comfyui.py    # ComfyUI adapter
│   └── api_adapter.py      # Hosted API adapter
└── assembler/              # ffmpeg assembly pipeline
    ├── pipeline.py         # High-level assembly orchestration
    └── ffmpeg_ops.py       # Low-level ffmpeg operations

config/                     # Configuration files
├── defaults.yaml           # System defaults
├── presets.yaml            # 8 presets
└── engine.yaml             # Engine fallback chain

schemas/                    # JSON Schema
└── render_spec_v1.json     # RenderSpec V1 contract

tests/                      # Acceptance tests
├── conftest.py             # Fixtures
├── test_core_flows.py      # A) Overlay 15s, Hero 6s, Meme 10s
├── test_60s.py             # B) 60-second requirement
├── test_engine_policy.py   # C) Engine policy + fallback
└── test_recovery.py        # D) State persistence + resume

docs/                       # Extension guides
├── local-setup.md
├── add-preset.md
├── add-engine-adapter.md
└── add-comfyui-workflow.md
```

## Quick start

### Prerequisites
- Docker + NVIDIA Container Toolkit (for GPU rendering)
- Python 3.11+ (for local dev)
- ffmpeg installed

### Local development

```bash
# 1. Clone and setup
cp .env.example .env        # edit values as needed

# 2. Install deps
pip install -e ".[dev]"

# 3. Run API server
uvicorn pytoon.api_orchestrator.app:app --reload --port 8080

# 4. Run worker (separate terminal)
python -m pytoon.worker.main

# 5. Run tests
pytest -v
```

### Docker (full stack)

```bash
docker-compose up -d
```

Services: API (:8080), Worker, ComfyUI (:8188), Redis (:6379), MinIO (:9000/:9001)

## API usage

```bash
# List presets
curl -H "X-API-Key: dev-key-change-me" http://localhost:8080/api/v1/presets

# Create a job
curl -X POST http://localhost:8080/api/v1/jobs \
  -H "X-API-Key: dev-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "preset_id": "overlay_classic",
    "prompt": "Sleek product showcase",
    "target_duration_seconds": 15,
    "image_uris": ["file:///data/storage/uploads/product.png"]
  }'

# Poll job status
curl -H "X-API-Key: dev-key-change-me" http://localhost:8080/api/v1/jobs/{job_id}

# Get segment details
curl -H "X-API-Key: dev-key-change-me" http://localhost:8080/api/v1/jobs/{job_id}/segments

# Prometheus metrics
curl http://localhost:8080/metrics
```

## Defaults (V1)

| Setting | Value |
|---|---|
| segment_duration | 3s |
| transition | 150ms crossfade |
| fps | 30 |
| output | 1080x1920 H.264 yuv420p |
| engine_policy | local_preferred |
| brand_safe | true |

## Extending

- **Add a preset**: see `docs/add-preset.md`
- **Add an engine adapter**: see `docs/add-engine-adapter.md`
- **Add a ComfyUI workflow**: see `docs/add-comfyui-workflow.md`

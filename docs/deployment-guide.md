# Pytoon V1 — Deployment Guide

> **Ticket:** P5-10

---

## Prerequisites

- Python 3.11+
- FFmpeg (must be in PATH)
- Redis (optional — falls back to fakeredis in local mode)

---

## Local Development (Single Process)

The simplest way to run Pytoon for development:

```bash
# 1. Clone and install
pip install -e ".[dev]"

# 2. Run (API + embedded worker in one process)
python run_local.py
```

This starts:
- API server on http://localhost:8080
- Embedded worker in a background thread
- SQLite database at `data/pytoon.db`
- Filesystem storage at `storage/`
- Fakeredis in-memory queue (no Redis needed)

**Endpoints:**
- API docs: http://localhost:8080/docs
- Metrics: http://localhost:8080/metrics
- Health: http://localhost:8080/health

---

## Docker Compose (Full Stack)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api worker

# Stop
docker-compose down
```

**Services:**
| Service | Port | Description |
|---|---|---|
| `api` | 8080 | FastAPI server |
| `worker` | — | Background job processor |
| `comfyui` | 8188 | ComfyUI (requires NVIDIA GPU) |
| `redis` | 6379 | Job queue |
| `minio` | 9000/9001 | Object storage (optional) |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PYTOON_ENV` | `local` | Environment name |
| `API_PORT` | `8080` | API server port |
| `API_KEY` | `dev-key-change-me` | API authentication key |
| `DB_URL` | `sqlite:///data/pytoon.db` | Database connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `STORAGE_ROOT` | `./storage` | Filesystem storage root |
| `COMFYUI_BASE_URL` | `http://comfyui:8188` | ComfyUI service URL |
| `API_ENGINE_BASE_URL` | `` | Remote API engine URL |
| `API_ENGINE_KEY` | `` | Remote API engine key |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |

---

## System Dependencies

### FFmpeg (Required)

FFmpeg must be installed and available in PATH.

**Windows:**
```bash
winget install FFmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
apt-get install -y ffmpeg
```

### ComfyUI (Optional)

Required only for AI-powered video generation. Without ComfyUI, the system uses the local_ffmpeg adapter (Ken Burns, overlay composition, text rendering).

For GPU setup:
1. Install NVIDIA drivers and CUDA toolkit
2. Run ComfyUI via Docker: `docker-compose up comfyui`
3. Verify health: `curl http://localhost:8188/system_stats`

---

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]" fakeredis

# Run all tests
pytest tests/ -v

# Run acceptance tests only
pytest tests/test_acceptance.py -v

# Run with coverage
pytest tests/ --cov=pytoon --cov-report=term-missing
```

---

## Database

V1 uses SQLite by default. For production, set `DB_URL` to a PostgreSQL connection string:

```
DB_URL=postgresql://user:pass@host:5432/pytoon
```

Tables are created automatically on first startup (`init_db()`).

---

## Storage Layout

```
storage/
├── uploads/          # Uploaded assets
│   └── {uuid}/
│       └── filename.png
├── jobs/             # Job outputs
│   └── {job_id}/
│       ├── segments/
│       ├── assembly/
│       ├── output.mp4
│       ├── thumbnail.jpg
│       └── metadata.json
├── brand/            # Brand assets (optional)
│   └── logo.png
└── _engine_tmp/      # Temporary engine files (auto-cleaned)
```

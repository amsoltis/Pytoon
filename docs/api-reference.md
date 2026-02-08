# Pytoon V1 — API Reference

> **Ticket:** P5-10  
> **Base URL:** `http://localhost:8080`

---

## Authentication

All API endpoints (except `/health` and `/metrics`) require an API key header:

```
X-API-Key: <your-api-key>
```

Default dev key: `dev-key-change-me` (set via `API_KEY` env var).

| Response | Meaning |
|---|---|
| 401 | Invalid API key |
| 422 | Missing X-API-Key header |

---

## Endpoints

### `GET /health`

Health check. No authentication required.

**Response:**
```json
{"status": "ok"}
```

---

### `GET /metrics`

Prometheus metrics endpoint. No authentication required.

**Response:** Prometheus text exposition format.

**Key metrics:**
| Metric | Type | Description |
|---|---|---|
| `pytoon_render_jobs_total` | Counter | Jobs submitted (by archetype, preset) |
| `pytoon_render_success_total` | Counter | Successful renders (by archetype) |
| `pytoon_render_failure_total` | Counter | Failed renders (by archetype, reason) |
| `pytoon_fallback_total` | Counter | Fallback events (by type) |
| `pytoon_segment_render_seconds` | Histogram | Segment render time (by engine) |
| `pytoon_job_total_seconds` | Histogram | Total job time (by archetype) |
| `pytoon_queue_depth` | Gauge | Current queue depth |

---

### `GET /api/v1/presets`

List all available presets.

**Response:**
```json
{
  "presets": [
    {
      "id": "product_hero_clean",
      "name": "Product Hero Clean",
      "archetype": "PRODUCT_HERO",
      "brand_safe": true,
      "engine_policy": "local_preferred",
      "caption_style": {
        "font": "Inter",
        "size_rules": "auto",
        "position": "lower_third",
        "safe_margin_px": 120
      },
      "motion_profile": "subtle",
      "transitions": {"type": "crossfade", "duration_ms": 150},
      "audio": {"music_level_db": -18, "voice_level_db": -6}
    }
  ]
}
```

---

### `POST /api/v1/assets/upload`

Upload a media asset (image, mask, or audio).

**Request:** multipart/form-data
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | Yes | The asset file |
| `category` | string | No | `"image"` (default), `"mask"`, or `"audio"` |

**Constraints:**
- Images: PNG, JPEG, WebP; max 20 MB; max 4096px per edge
- Masks: PNG only (with alpha channel)
- Audio: MP3, WAV; max 20 MB

**Response (201):**
```json
{
  "uri": "file:///data/storage/uploads/<uuid>/<filename>",
  "key": "uploads/<uuid>/<filename>",
  "size": 102400
}
```

---

### `POST /api/v1/jobs`

Submit a new render job.

**Request body (JSON):**
```json
{
  "preset_id": "overlay_classic",
  "prompt": "Product showcase with elegance",
  "target_duration_seconds": 15,
  "brand_safe": true,
  "engine_policy": "local_preferred",
  "archetype": "OVERLAY",
  "image_uris": ["file:///data/storage/uploads/abc/product.png"],
  "mask_uri": null,
  "music_uri": "file:///data/storage/uploads/def/track.mp3",
  "voice_uri": null,
  "captions": {
    "hook": "New Collection",
    "beats": ["Premium quality", "Limited edition"],
    "cta": "Shop now"
  }
}
```

| Field | Type | Required | Default |
|---|---|---|---|
| `preset_id` | string | Yes | — |
| `prompt` | string | No | `""` |
| `target_duration_seconds` | int (1–60) | No | `15` |
| `brand_safe` | bool | No | Preset default |
| `engine_policy` | enum | No | Preset default |
| `archetype` | enum | No | Preset default |
| `image_uris` | string[] | No | `[]` |
| `mask_uri` | string | No | `null` |
| `music_uri` | string | No | `null` |
| `voice_uri` | string | No | `null` |
| `captions` | object | No | Auto-generated from prompt |

**Response (201):**
```json
{
  "job_id": "abc123def456",
  "status": "QUEUED",
  "segments": 5
}
```

**Error responses:**
| Code | Condition |
|---|---|
| 400 | Unknown preset_id |
| 422 | Invalid field values (e.g., duration > 60) |

---

### `GET /api/v1/jobs/{job_id}`

Get job status.

**Response (200):**
```json
{
  "job_id": "abc123def456",
  "status": "DONE",
  "archetype": "OVERLAY",
  "preset_id": "overlay_classic",
  "target_duration_seconds": 15,
  "progress_pct": 100.0,
  "output_uri": "file:///data/storage/jobs/abc123/output.mp4",
  "thumbnail_uri": "file:///data/storage/jobs/abc123/thumbnail.jpg",
  "metadata_uri": "file:///data/storage/jobs/abc123/metadata.json",
  "fallback_used": false,
  "fallback_reason": null,
  "error": null,
  "created_at": "2026-02-07T12:00:00Z",
  "updated_at": "2026-02-07T12:01:30Z"
}
```

**Job statuses:** `QUEUED` → `PLANNING` → `RENDERING_SEGMENTS` → `ASSEMBLING` → `DONE` / `FAILED`

**Error responses:**
| Code | Condition |
|---|---|
| 404 | Job not found |

---

### `GET /api/v1/jobs/{job_id}/segments`

Get per-segment status for a job.

**Response (200):**
```json
{
  "job_id": "abc123def456",
  "segments": [
    {
      "index": 0,
      "status": "DONE",
      "duration_seconds": 3.0,
      "engine_used": "local_ffmpeg",
      "artifact_uri": "file:///data/storage/jobs/abc123/segments/seg_000.mp4",
      "error": null
    }
  ]
}
```

---

## Typical Workflow

```
1. Upload assets    → POST /api/v1/assets/upload (repeat for each file)
2. List presets     → GET /api/v1/presets
3. Submit job       → POST /api/v1/jobs (include uploaded asset URIs)
4. Poll status      → GET /api/v1/jobs/{job_id} (repeat until DONE/FAILED)
5. Download video   → Access output_uri from status response
```

---

## Error Codes

| HTTP Status | Meaning |
|---|---|
| 200 | Success |
| 201 | Created (job or asset) |
| 400 | Bad request (invalid input) |
| 401 | Unauthorized (bad API key) |
| 404 | Not found |
| 422 | Validation error (Pydantic) |
| 500 | Internal server error |

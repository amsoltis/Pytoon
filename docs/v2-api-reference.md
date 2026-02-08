# Pytoon V2 — API Reference

**Version:** 2.0.0  
**Base URL:** `/api/v2`  
**Ticket:** P5-14

---

## Endpoints

### POST `/api/v2/jobs`

Create a new V2 video generation job.

**Request Body:**

```json
{
  "prompt": "Product reveal. Key features. Call to action.",
  "media_files": ["/path/to/product.png"],
  "preset_id": "product_hero_clean",
  "brand_safe": true,
  "voice_script": "Introducing our amazing product...",
  "music_source": "upbeat_corporate",
  "engine_override": null,
  "target_duration_seconds": 30,
  "max_scenes": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | Yes | Text prompt describing the video content |
| `media_files` | string[] | No | Paths to image/video assets |
| `preset_id` | string | No | Visual preset (default: `product_hero_clean`) |
| `brand_safe` | boolean | No | Enable brand-safe mode (default: `true`) |
| `voice_script` | string | No | Script for TTS voiceover generation |
| `music_source` | string | No | Background music track name or path |
| `engine_override` | string | No | Force a specific engine: `runway`, `pika`, `luma` |
| `target_duration_seconds` | int | No | Target video duration (max 60) |
| `max_scenes` | int | No | Maximum number of scenes to generate |

**Response (202):**

```json
{
  "job_id": "abc123",
  "status": "planning_scenes",
  "scene_count": 3
}
```

---

### GET `/api/v2/jobs/{job_id}`

Get V2 job status and progress.

**Response:**

```json
{
  "job_id": "abc123",
  "status": "composing",
  "progress_pct": 85.0,
  "output_uri": null,
  "thumbnail_uri": null,
  "scene_count": 3,
  "scenes": [
    {
      "scene_id": 1,
      "status": "DONE",
      "engine_used": "runway",
      "fallback_used": false,
      "render_duration_ms": 12500
    }
  ]
}
```

**Statuses:** `planning_scenes` → `building_timeline` → `rendering_scenes` → `composing` → `done` | `failed`

---

### GET `/api/v2/jobs/{job_id}/scene-graph`

Retrieve the Scene Graph JSON for a completed job.

---

### GET `/api/v2/jobs/{job_id}/timeline`

Retrieve the Timeline JSON for a completed job.

---

### GET `/metrics`

Prometheus metrics endpoint (V1 + V2 metrics).

---

### GET `/health`

Health check endpoint.

---

## Scene Graph Schema

See `schemas/scene_graph_v2.json` for the full JSON schema.

Key fields:
- `scenes[]`: Array of scene definitions
- `scenes[].media`: Media type, engine, asset, prompt
- `scenes[].style`: Camera motion, mood, lighting
- `scenes[].overlays`: Text/image overlays
- `globalAudio`: Voiceover script, music source

---

## Timeline Schema

See `schemas/timeline_v2.json` for the full JSON schema.

Key fields:
- `totalDuration`: Total video duration in milliseconds
- `timeline[]`: Ordered scene entries with start/end times
- `tracks.captions[]`: Caption timing and text
- `tracks.audio[]`: Audio track references

---

## Engine Configuration

See `config/engine.yaml` (v2 section):
- Per-engine settings: timeout, max duration, capabilities
- Fallback chain order
- Per-preset engine preferences
- Prompt sanitization rules
- Content moderation settings

---

## Output Artifacts

For each V2 job:

```
storage/jobs/{job_id}/
├── output.mp4          # Final video (1080x1920, H.264/AAC)
├── thumbnail.jpg       # Key frame thumbnail
├── scene_graph.json    # Persisted Scene Graph
├── timeline.json       # Persisted Timeline
├── captions.srt        # SRT subtitle file
└── scenes/             # Per-scene rendered clips
    ├── scene_1.mp4
    └── scene_N.mp4
```

---

## Error Handling

All errors return standard HTTP error codes with JSON body:

```json
{
  "detail": "Description of the error"
}
```

| Code | Meaning |
|------|---------|
| 400 | Invalid request (bad prompt, invalid preset) |
| 404 | Job not found |
| 500 | Internal server error |

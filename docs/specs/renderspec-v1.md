# RenderSpec V1 — Schema Specification

> **Status:** FROZEN  
> **Ticket:** P1-02  
> **AC:** AC-004, AC-005  
> **JSON Schema:** schemas/render_spec_v1.json  
> **Pydantic Models:** pytoon/models.py

---

## Design Principles

1. **Engine-agnostic** — no engine-specific or model-specific logic embedded in the spec.
2. **Complete** — the spec fully describes the intended video; no out-of-band decisions.
3. **Versioned** — `render_spec_version` field enables forward-compatible evolution.
4. **Persisted** — every job stores its RenderSpec JSON for reproducibility (AC-005).

---

## Schema Fields

### Top-Level (required unless noted)

| Field | Type | Default | Description |
|---|---|---|---|
| `render_spec_version` | int | `1` | Schema version. Must be `1` for V1. |
| `job_id` | string | auto-generated UUID hex | Unique job identifier. |
| `archetype` | enum | — | One of: `PRODUCT_HERO`, `OVERLAY`, `MEME_TEXT`. |
| `brand_safe` | bool | `true` | Enables brand-safe enforcement rules. |
| `aspect_ratio` | string | `"9:16"` | Output aspect ratio. Fixed for V1. |
| `target_duration_seconds` | int (1–60) | — | Requested total video duration. |
| `segment_duration_seconds` | int (2–4) | `3` | Target duration per segment. |
| `preset_id` | string | — | ID of the preset used (from config/presets.yaml). |
| `engine_policy` | enum | `"local_preferred"` | One of: `local_only`, `local_preferred`, `api_only`. |
| `assets` | Assets | `{}` | Media assets for the video. |
| `segment_prompts` | string[] | `[]` | Per-segment text prompts for engine. |
| `captions_plan` | CaptionsPlan | `{}` | Caption timing and content. |
| `audio_plan` | AudioPlan | `{}` | Audio mixing parameters. |
| `constraints` | Constraints | `{}` | Rendering constraints. |
| `segments` | SegmentSpec[] | `[]` | Planned segment list with index and duration. |

### Assets

| Field | Type | Required | Description |
|---|---|---|---|
| `images` | string[] | Yes | Storage URIs for input images. |
| `mask` | string | No | URI for transparency mask (PNG with alpha). |
| `music` | string | No | URI for background music track. |
| `voice` | string | No | URI for voiceover audio. |

### CaptionsPlan

| Field | Type | Description |
|---|---|---|
| `hook` | string | Opening attention text (first caption). |
| `beats` | string[] | Body content captions. |
| `cta` | string | Call-to-action text (final caption). |
| `timings` | CaptionTiming[] | Computed start/end/text for each caption. |

### CaptionTiming

| Field | Type | Description |
|---|---|---|
| `start` | float | Start time in seconds. |
| `end` | float | End time in seconds. |
| `text` | string | Caption text to display. |

### AudioPlan

| Field | Type | Default | Description |
|---|---|---|---|
| `music_level_db` | float | `-18.0` | Background music volume in dB. |
| `voice_level_db` | float | `-6.0` | Voice volume in dB. |
| `duck_music` | bool | `true` | Reduce music volume when voice is present. |

### Constraints

| Field | Type | Default | Description |
|---|---|---|---|
| `safe_zones` | string | `"default"` | Caption safe zone profile. |
| `keep_subject_static` | bool | `true` | When brand_safe, prevent product distortion. |

### SegmentSpec

| Field | Type | Description |
|---|---|---|
| `index` | int | Segment order (0-based). |
| `duration_seconds` | float | Duration of this segment. |
| `prompt` | string | Engine prompt for this segment. |
| `engine` | string (optional) | Engine override for this segment. |

---

## Validation Rules

1. `target_duration_seconds` must be between 1 and 60 inclusive.
2. `segment_duration_seconds` must be between 2 and 4 inclusive.
3. Sum of all `segments[].duration_seconds` must equal `target_duration_seconds`.
4. `archetype` must be one of the three defined enums.
5. `assets.images` must contain at least one URI (except for pure MEME_TEXT with prompt).
6. All caption timings must fall within `[0, target_duration_seconds]`.
7. No engine-specific or model-specific fields are permitted at the top level.

---

## Persistence Contract (AC-005)

The RenderSpec is serialized to JSON and stored in the `render_spec_json` column of the `jobs` database table at job creation time. This enables:

- **Reproducibility** — re-running the same spec produces equivalent output.
- **Debugging** — inspect exactly what was planned for any job.
- **Auditing** — trace every output back to its intent.

---

## Example

```json
{
  "render_spec_version": 1,
  "job_id": "abc123def456",
  "archetype": "PRODUCT_HERO",
  "brand_safe": true,
  "aspect_ratio": "9:16",
  "target_duration_seconds": 15,
  "segment_duration_seconds": 3,
  "preset_id": "product_hero_clean",
  "engine_policy": "local_preferred",
  "assets": {
    "images": ["file:///data/storage/uploads/aaa/product.png"],
    "music": "file:///data/storage/uploads/bbb/track.mp3"
  },
  "segment_prompts": [
    "subtle cinematic motion, product showcase, New Collection",
    "subtle cinematic motion, product showcase, New Collection",
    "subtle cinematic motion, product showcase, New Collection",
    "subtle cinematic motion, product showcase, New Collection",
    "subtle cinematic motion, product showcase, New Collection"
  ],
  "captions_plan": {
    "hook": "New Collection",
    "beats": [],
    "cta": "",
    "timings": [
      {"start": 0.0, "end": 15.0, "text": "New Collection"}
    ]
  },
  "audio_plan": {
    "music_level_db": -18,
    "voice_level_db": -6,
    "duck_music": true
  },
  "constraints": {
    "safe_zones": "default",
    "keep_subject_static": true
  },
  "segments": [
    {"index": 0, "duration_seconds": 3.0, "prompt": "..."},
    {"index": 1, "duration_seconds": 3.0, "prompt": "..."},
    {"index": 2, "duration_seconds": 3.0, "prompt": "..."},
    {"index": 3, "duration_seconds": 3.0, "prompt": "..."},
    {"index": 4, "duration_seconds": 3.0, "prompt": "..."}
  ]
}
```

# Input Validation Rules and Constraints

> **Status:** FROZEN  
> **Ticket:** P1-08  
> **AC:** AC-016  
> **Implementation:** pytoon/api_orchestrator/validation.py

---

## File Upload Validation

### Accepted File Types

| Category | MIME Types | Extensions |
|---|---|---|
| Image | `image/png`, `image/jpeg`, `image/webp` | `.png`, `.jpg`, `.jpeg`, `.webp` |
| Mask | `image/png` | `.png` (must have alpha channel) |
| Audio | `audio/mpeg`, `audio/wav`, `audio/x-wav` | `.mp3`, `.wav` |

### File Size Limits

| Constraint | Value | Source |
|---|---|---|
| Max file size per asset | 20 MB | `config/defaults.yaml > limits.max_asset_mb` |
| Max image dimension (any edge) | 4096 px | `config/defaults.yaml > limits.max_image_edge_px` |

### Rejection Behavior

| Condition | HTTP Status | Error Message |
|---|---|---|
| Unsupported image MIME type | 400 | "Unsupported image type: {type}" |
| Unsupported audio MIME type | 400 | "Unsupported audio type: {type}" |
| Mask not PNG | 400 | "Mask must be PNG with alpha, got: {type}" |
| File exceeds size limit | 400 | "File exceeds {max}MB limit" |
| Image dimensions exceed limit | 400 | "Image dimensions exceed {max}px limit: {w}x{h}" |

---

## Job Request Validation

### Required Fields

| Field | Type | Validation |
|---|---|---|
| `preset_id` | string | Must match a known preset in config/presets.yaml |
| `target_duration_seconds` | int | Must be 1–60 inclusive (Pydantic `ge=1, le=60`) |

### Optional Fields with Defaults

| Field | Type | Default | Validation |
|---|---|---|---|
| `prompt` | string | `""` | No length limit enforced in V1 (captions auto-truncate at render) |
| `brand_safe` | bool | Preset default | — |
| `engine_policy` | enum | Preset default | Must be `local_only`, `local_preferred`, or `api_only` |
| `archetype` | enum | Preset default | Must be `PRODUCT_HERO`, `OVERLAY`, or `MEME_TEXT` |
| `image_uris` | string[] | `[]` | Must be valid storage URIs (uploaded via `/assets/upload`) |
| `mask_uri` | string | `null` | Must be valid storage URI |
| `music_uri` | string | `null` | Must be valid storage URI |
| `voice_uri` | string | `null` | Must be valid storage URI |

### Rejection Behavior

| Condition | HTTP Status | Error Message |
|---|---|---|
| Unknown preset_id | 400 | "Unknown preset: {id}" |
| Duration out of range | 422 | Pydantic validation error |
| Invalid archetype | 422 | Pydantic validation error |
| Invalid engine_policy | 422 | Pydantic validation error |

---

## Minimum Asset Requirement

- **V1 policy:** At least one image is recommended but not strictly enforced at the API level.
- **MEME_TEXT archetype:** Can operate with prompt-only (text on colored background).
- **PRODUCT_HERO and OVERLAY:** Without images, render a solid dark background segment.
- The system does not reject zero-image requests; it produces a valid (if minimal) video.

---

## Segment Count Limits

| Constraint | Value | Enforcement |
|---|---|---|
| Min segments | 1 | Implied by min duration (1s) ÷ max segment duration (4s) |
| Max segments | 30 | Implied by max duration (60s) ÷ min segment duration (2s) |
| Duration cap | 60 seconds total | Segment planner caps total; API rejects >60s requests |

---

## Authentication

| Method | Header | Value |
|---|---|---|
| API Key | `X-API-Key` | Must match `API_KEY` env var |
| Missing header | 422 | Validation error |
| Invalid key | 401 | "Invalid API key" |
| Health endpoint | None | `/health` requires no authentication |
| Metrics endpoint | None | `/metrics` requires no authentication |

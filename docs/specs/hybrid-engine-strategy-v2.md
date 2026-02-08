# Hybrid Engine Strategy -- V2 Specification

**Ticket:** P1-04  
**Acceptance Criteria:** V2-AC-010, V2-AC-011  
**Source:** pytoon-v2.md "Hybrid Engine Strategy" (line 55), "Engine Invocation and Fallback" (lines 175-187)

---

## 1. Overview

Pytoon V2 employs a **Hybrid Engine Strategy** that splits creative responsibilities between AI-powered external engines and a deterministic local renderer (FFmpeg). AI engines generate cinematic motion footage; the local renderer ensures a reliable compile every time. No single engine is a point of failure.

---

## 2. External Engine Adapters

### 2.1 Runway (runway)

- **Strengths:** High-quality cinematics, precise camera control, smooth human/object motion, photorealism.
- **Best for:** Realistic product-in-context shots, cinematic beauty shots, scenes requiring camera trajectories (dolly, orbit, pan).
- **API model:** Runway Gen-2 / Gen-4 (configurable).
- **Supports image input:** Yes (reference/init image conditioning).
- **Max clip duration:** ~10s per generation (API-dependent).
- **Resolution:** Can request 9:16 (1080x1920) natively on supported models.

### 2.2 Pika (pika)

- **Strengths:** Stylized creative effects, fast generation, artistic/abstract visuals.
- **Best for:** Stylized scenes, creative transitions, energetic/fun visuals, meme-style content.
- **API model:** Pika Labs API.
- **Supports image input:** Yes (image + prompt conditioning).
- **Max clip duration:** ~4-8s per generation.
- **Resolution:** Variable; post-processing scales to 1080x1920.

### 2.3 Luma (luma)

- **Strengths:** Physics-realism, 3D-like rendering, naturalistic motion, product-centric shots.
- **Best for:** Product rotation/showcase, physics-based animations, realistic product-in-environment scenes.
- **API model:** Luma AI Dream Machine.
- **Supports image input:** Yes.
- **Max clip duration:** ~5-10s per generation.
- **Resolution:** Variable; post-processing scales to 1080x1920.

### 2.4 Local FFmpeg (local)

- **Strengths:** Deterministic, zero external dependency, always available.
- **Best for:** Image-type scenes (Ken Burns pan/zoom on static images), fallback for any failed engine.
- **Capabilities:** Scale/crop/pan/zoom on static images, solid-color backgrounds with text overlay, basic animation effects.

---

## 3. Engine Selection Rules

The Engine Manager assigns an engine to each scene based on the following priority rules, evaluated top-to-bottom:

| Priority | Condition | Engine Assigned |
|----------|-----------|-----------------|
| 1 | Scene has explicit `media.engine` set | Use that engine directly |
| 2 | `media.type == "image"` | `local` (FFmpeg -- no external engine needed) |
| 3 | Style contains "realistic" or "cinematic" | `runway` |
| 4 | Style contains "stylized", "creative", or "artistic" | `pika` |
| 5 | Style contains "physics", "3D", "product", or "showcase" | `luma` |
| 6 | No style match | Default engine from `config/engine.yaml` |

### 3.1 Engine Policy Extension from V1

V1 defined three engine policies: `local_only`, `local_preferred`, `api_only`.

V2 extends these with two new policies:
- **`multi_engine`** (default for V2): Per-scene engine selection using the rules above. Different scenes can use different engines.
- **`single_engine`**: One engine for all scenes. User specifies which engine via API parameter or preset.

V1 policies remain valid for V1 jobs. V2 jobs default to `multi_engine`.

---

## 4. Fallback Chain

When an engine fails, the system follows a multi-level fallback chain. Fallback is per-scene -- a failure in one scene does not affect others.

```
Level 1: Primary Engine (assigned by selection rules)
    │
    ├── On failure/timeout/validation-fail
    ▼
Level 2: Alternate Engine (next in priority list)
    │  Priority order: runway → pika → luma
    │  Skip the engine that already failed.
    │  If primary was runway, try pika, then luma.
    │  If primary was pika, try runway, then luma.
    │  If primary was luma, try runway, then pika.
    │
    ├── On failure of all alternates
    ▼
Level 3: Deterministic Local Fallback (FFmpeg)
    │  For scenes with a product image: Ken Burns pan/zoom on the image.
    │  For scenes without an image: Solid-color animated background
    │  with scene description text overlay.
    │
    └── Always succeeds. Scene timeline slot is preserved.
```

### 4.1 Fallback Triggers

- **HTTP error** from engine API (4xx, 5xx).
- **Timeout**: Engine does not return a result within the configured threshold (default: 60s).
- **Content moderation rejection**: Engine refuses the prompt.
- **Validation failure**: Returned clip fails validation (corrupt, wrong format, blank, duration severely off).

### 4.2 Content Moderation Auto-Rephrase

Before escalating to the next engine on a content moderation rejection:
1. Remove flagged terms from the prompt using the configurable substitution map (e.g., "shoot" → "film").
2. Retry the **same** engine once with the rephrased prompt.
3. If still rejected, escalate to the next engine in the fallback chain.

### 4.3 Fallback Bookkeeping

- `SceneRow.fallback_used = true` is set on any scene that used a non-primary engine or local fallback.
- `SceneRow.error_message` records the reason for fallback.
- Every fallback event is logged in structured format with: `job_id`, `scene_id`, `primary_engine`, `fallback_engine`, `reason`, `latency_ms`.

---

## 5. Timeout Thresholds

| Engine | Default Timeout | Configurable Key |
|--------|----------------|------------------|
| runway | 60s | `engine.runway.timeout_seconds` |
| pika | 60s | `engine.pika.timeout_seconds` |
| luma | 60s | `engine.luma.timeout_seconds` |

All thresholds configurable in `config/engine.yaml`.

---

## 6. API Key Management

- API keys are stored in environment variables or `.env` file, never in config files or source code.
- Environment variable naming: `RUNWAY_API_KEY`, `PIKA_API_KEY`, `LUMA_API_KEY`.
- The Engine Manager checks for key availability before attempting to use an engine. If a key is missing, that engine is skipped (treated as unavailable, not as a failure).

---

## 7. Rate Limit Handling

- Each engine adapter tracks rate limit headers from API responses (e.g., `X-RateLimit-Remaining`).
- If rate-limited (HTTP 429), the adapter waits for the `Retry-After` duration (up to the timeout threshold), then retries once.
- If still rate-limited after wait, escalate to the next engine in the fallback chain.
- No more than one concurrent request per engine per job (parallelism is across scenes, not within one scene).

---

## 8. Cost Awareness

- Each engine invocation logs the estimated cost (if available from API response).
- The Engine Manager does NOT enforce cost caps in V2 (this is a future optimization).
- Job metadata records total engine invocations and fallback counts for cost monitoring.

---

## 9. Configuration

All engine configuration lives in `config/engine.yaml`. V2 extends the existing V1 structure:

```yaml
# V2 Engine Configuration
v2:
  default_engine: runway
  timeout_seconds: 60
  engines:
    runway:
      enabled: true
      timeout_seconds: 60
      max_clip_duration_seconds: 10
      supports_image_input: true
      supported_resolutions: ["1080x1920", "720x1280"]
    pika:
      enabled: true
      timeout_seconds: 60
      max_clip_duration_seconds: 8
      supports_image_input: true
      supported_resolutions: ["1080x1920"]
    luma:
      enabled: true
      timeout_seconds: 60
      max_clip_duration_seconds: 10
      supports_image_input: true
      supported_resolutions: ["1080x1920"]
  fallback_chain: [runway, pika, luma]
  prompt_sanitization:
    blocklist: []          # Competitor names and banned terms
    substitutions: {}      # e.g., "shoot": "film"
    max_prompt_length: 500
```

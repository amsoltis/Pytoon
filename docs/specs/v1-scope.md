# Pytoon V1 — Scope and Non-Goals

> **Status:** APPROVED  
> **Ticket:** P1-01  
> **AC:** AC-002, AC-021  
> **Source of Record:** docs/vision/pytoon-v1.md

---

## In-Scope for V1

### Product Capabilities

1. **Short-form vertical video generation** from mixed media assets (images + text prompts).
2. **Three video archetypes:**
   - **PRODUCT_HERO (I2V)** — full-frame product showcase with Ken Burns motion.
   - **OVERLAY** — product image composited on a blurred/dark background.
   - **MEME_TEXT (T2V)** — bold caption text with image or colored background.
3. **Preset system** — 8 curated presets controlling archetype, caption style, transitions, audio levels, and motion profile.
4. **Brand-safe mode** (default ON) — restricts fonts, transitions, motion intensity; preserves product identity; optional logo watermark.
5. **Caption rendering** — hook, beats, and CTA burned into video within safe zones.
6. **Audio mixing** — background music with ducking, loudness normalization (EBU R128).
7. **Segment-based rendering** — videos composed of 2–4 second independently rendered segments.
8. **Crossfade transitions** — between segments (configurable: cut, fade, fade-through-black).
9. **Thumbnail generation** — JPG extracted from final video.

### System Capabilities

1. **REST API** — FastAPI with `/render` (POST) and `/render/{job_id}` (GET) endpoints.
2. **Async job pipeline** — Redis-backed queue with background worker processing.
3. **Job state machine** — QUEUED → PLANNING → RENDERING_SEGMENTS → ASSEMBLING → DONE / FAILED.
4. **State persistence** — SQLite/PostgreSQL; survives service and worker restarts.
5. **Pluggable engine adapters** — local FFmpeg, local ComfyUI, remote API engine.
6. **Engine fallback chain** — local_ffmpeg → local_comfyui → api_luma; automatic on failure/timeout.
7. **Three engine policies** — `local_only`, `local_preferred`, `api_only`.
8. **Template fallback** — static-template video returned when all engines fail (AC-018).
9. **Structured logging** — JSON via structlog with job_id, segment_id, engine_used, render_duration.
10. **Prometheus metrics** — success rate, fallback rate, segment render time, queue depth.
11. **Docker Compose deployment** — API, Worker, ComfyUI, Redis, MinIO.
12. **Local dev mode** — `run_local.py` with embedded worker, fakeredis, SQLite.

### Output Contract

- **Format:** MP4 (H.264 + AAC)
- **Resolution:** 1080×1920 (9:16)
- **Frame rate:** 30 fps
- **Max duration:** 60 seconds (±0.5s tolerance)
- **Max bitrate:** 12 Mbps

### Constraints

- **Local-first** — rendering prefers local engines; cloud is fallback only.
- **Brand-safe default ON** — all jobs default to brand-safe unless explicitly overridden.
- **Maximum video duration** — 60 seconds, enforced at API validation and assembly.
- **Segment duration** — 2–4 seconds per segment.

---

## Explicitly Out-of-Scope (Non-Goals)

The following are **NOT** part of V1. Any work on these items is forbidden until V1 is shipped.

| Non-Goal | Rationale |
|---|---|
| Auto-posting to social platforms | Growth feature; deferred to V2+ |
| Analytics or performance dashboards | Growth feature; deferred |
| Trend analysis or content suggestions | AI feature; deferred |
| Idea generation or prompt enhancement | AI feature; deferred |
| Feedback loops or A/B testing | Growth feature; deferred |
| Voiceover / TTS generation | AI feature; V1 accepts pre-recorded voice only |
| AI content moderation | Manual review suffices for V1 |
| Multi-user / multi-tenant support | Single-tenant for V1 |
| Real-time preview or interactive editing | Batch processing only |
| Videos longer than 60 seconds | Hard cap for platform compatibility |
| Non-vertical (landscape/square) output | 9:16 only |
| S3/MinIO write integration | Interface is ready; filesystem backend for V1 |
| GPU auto-scaling | Fixed infrastructure for V1 |
| Webhook or push notifications | Polling via API only |
| Custom workflow authoring UI | Developer/config only |

---

## Approval

This scope document is accepted as authoritative per the Phase Map enforcement rule. No feature outside this scope may be implemented without PM approval and a version bump to the System of Record.

# Engine Policy Rules Specification

> **Status:** FROZEN  
> **Ticket:** P1-05  
> **AC:** AC-007, AC-008  
> **Config file:** config/engine.yaml  
> **Implementation:** pytoon/engine_adapters/selector.py

---

## Three Engine Policies

### `local_only`

| Behavior | Detail |
|---|---|
| Engine selection | Only local-type adapters are considered |
| On local failure | RuntimeError raised; job marked FAILED |
| API usage | **Never** — no remote calls under any circumstance |
| Fallback | Template fallback only (static video with error text) |
| Use case | Air-gapped environments; brand assets must never leave local network |

### `local_preferred`

| Behavior | Detail |
|---|---|
| Engine selection | Try local adapters first (in chain order), then API adapters |
| On local failure | Automatically falls back to next adapter in chain |
| API usage | Only when all local adapters fail or are unhealthy |
| Fallback flag | `usedFallback=true` set on job record when API is used |
| Use case | Default policy; balances speed/privacy with reliability |

### `api_only`

| Behavior | Detail |
|---|---|
| Engine selection | Only API-type adapters are considered |
| On local availability | Local adapters are **skipped** even if healthy |
| API failure | RuntimeError raised; job marked FAILED |
| Use case | Testing remote engine; local GPU unavailable |

---

## Fallback Chain

Defined in `config/engine.yaml`:

```yaml
engine_fallback_chain:
  - local_ffmpeg
  - local_comfyui
  - api_luma
```

The chain is traversed in order. For each adapter:
1. Check `health_check()` — skip if unhealthy
2. Check `get_capabilities().archetypes` — skip if archetype not supported
3. If healthy and capable, use this adapter

If no adapter satisfies the policy, the `select_engine_with_fallback()` function performs an **absolute fallback**: tries every adapter in the chain regardless of policy, returning the first healthy one with `fallback_used=True`.

If even absolute fallback fails, the job runner invokes the **template fallback** (a static colored video with error text).

---

## Timeout Thresholds

| Parameter | Default | Description |
|---|---|---|
| FFmpeg subprocess timeout | 120s | Per-segment render timeout for local_ffmpeg |
| ComfyUI poll timeout | 300s | Max wait for ComfyUI prompt completion |
| API poll timeout | 300s | Max wait for remote API generation |
| Health check timeout | 5s | Per-adapter health check HTTP timeout |

---

## Retry Logic

| Scenario | Behavior |
|---|---|
| Local adapter render fails | Move to next adapter in chain (no retry of same adapter) |
| Remote API transient error | No automatic retry in V1; moves to next adapter or fails |
| All adapters exhausted | Template fallback invoked |
| Template fallback fails | Job marked FAILED with empty output file |

---

## `usedFallback` Flag

The `usedFallback` flag is set on the job database record when:

1. The engine selector had to deviate from the requested policy
2. An archetype fallback occurred (e.g., PRODUCT_HERO fell back to OVERLAY)
3. A template fallback was used

The flag is exposed in the `GET /api/v1/jobs/{job_id}` response and tracked by the `pytoon_fallback_total` Prometheus counter.

---

## Configuration Surface

| Setting | Source | Description |
|---|---|---|
| `engine_policy_default` | config/defaults.yaml, env `ENGINE_POLICY_DEFAULT` | System-wide default policy |
| `engine_fallback_chain` | config/engine.yaml | Ordered list of adapter names |
| `adapters.*` | config/engine.yaml | Per-adapter configuration |
| `COMFYUI_BASE_URL` | env var | ComfyUI service URL |
| `API_ENGINE_BASE_URL` | env var | Remote API engine URL |
| `API_ENGINE_KEY` | env var | Remote API authentication key |

---

## Adapter Registry

| Name | Type | Backend | Archetypes |
|---|---|---|---|
| `local_ffmpeg` | local | FFmpeg CLI | PRODUCT_HERO, OVERLAY, MEME_TEXT |
| `local_comfyui` | local | ComfyUI API | PRODUCT_HERO, OVERLAY, MEME_TEXT |
| `api_luma` | api | HTTP API | PRODUCT_HERO, OVERLAY, MEME_TEXT |

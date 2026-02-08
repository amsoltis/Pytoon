# Brand-Safe Mode -- V2 Specification

**Ticket:** P1-09  
**Acceptance Criteria:** V2-AC-012, V2-AC-016  
**Source:** pytoon-v2.md "Brand-Safe Overlays and Constraints" (lines 261-272)

---

## 1. Overview

V2 brand-safe mode extends V1's brand-safe constraints with protections specific to AI-generated content, multi-engine workflows, and cinematic composition. When `brand_safe = true`, the system enforces all constraints below in addition to V1 rules.

---

## 2. V2 Brand-Safe Constraints

### 2.1 Product Image Protection

- Product images are **composited as overlays only**. They are never fed through generative AI models for modification.
- When a scene includes both a product image and an AI-generated background, the product image is rendered on a separate layer (layer ≥ 1) on top of the AI content.
- The product image must not be distorted (no aspect ratio changes, no warping, no AI inpainting on the product).

### 2.2 Engine Prompt Sanitization

Before sending any prompt to an external engine:
1. **Competitor name blocklist:** Remove or replace competitor names (configurable list in `config/engine.yaml` under `prompt_sanitization.blocklist`).
2. **NSFW term filter:** Remove terms from the NSFW blocklist.
3. **Substitution map:** Apply term substitutions (e.g., "shoot" → "film") from `config/engine.yaml` under `prompt_sanitization.substitutions`.
4. **Safety cues appended:** Automatically append "family-friendly, professional, brand-safe" to prompts when `brand_safe = true`.

### 2.3 Generated Content Safety Check (Optional)

- When enabled (`brand_safe_ocr_check: true` in config), generated video frames are scanned for unexpected text/logos using OCR.
- If unexpected text is detected (text that is not from the user's captions or brand assets), log a warning.
- If the unexpected text matches a competitor name or offensive term, trigger the scene fallback (replace with static product image scene).
- This check is optional in V2 and can be disabled for performance.

### 2.4 Mandatory Logo Watermark

When `brand_safe = true`:
- A brand logo watermark overlay is **mandatory** on the output video.
- Modes:
  - **Persistent:** Logo visible throughout the entire video at a configurable position and opacity.
  - **Outro-only:** Logo appears in the last 2-3 seconds of the video as a full-screen or prominent overlay.
- Configuration per preset: `logo_path`, `logo_position` (top-left, top-right, bottom-left, bottom-right), `logo_opacity` (0.0-1.0), `logo_mode` (persistent | outro).
- If no logo file is configured, log a warning but do not fail the job.

### 2.5 Caption Brand Font Enforcement

- When `brand_safe = true`, captions **must** use the brand font specified in the preset.
- Fallback: If the brand font file is not available, use the system default sans-serif font and log a warning.
- Caption text color, outline color, and background color must match the preset's brand palette.
- No other fonts are permitted in brand-safe mode.

### 2.6 Color Palette Enforcement

- Overlay elements (caption backgrounds, text boxes, graphic overlays) must use colors from the brand palette defined in the preset.
- The brand palette is a list of hex color codes in the preset configuration.
- If no brand palette is defined, use neutral defaults (white text, black outline, 50% opacity black background).

### 2.7 Transition Restriction

- When `brand_safe = true`, only **`cut`** and **`fade`** transitions are permitted.
- Transitions like `swipe_left`, `swipe_right`, `fade_black` are blocked as they may be perceived as unprofessional for certain brand contexts.
- The Scene Planner enforces this at planning time; the Timeline Orchestrator validates it.

### 2.8 Engine Content Moderation Escalation

- If an engine returns potentially unsafe content (detected via the engine's own content filter or the optional OCR check), that scene is replaced with a static product image fallback.
- The fallback scene preserves the original scene's duration and caption.
- This is logged as a brand-safe fallback event.

---

## 3. Safe Visual Zones

On a 1080x1920 (9:16) frame, the following zones are reserved:

| Zone | Pixels from Edge | Purpose |
|------|-----------------|---------|
| Top margin | 100px from top | Platform status bar, profile info |
| Bottom margin | 150px from bottom | Platform UI, action buttons, comment bar |
| Left margin | 54px from left (5% of 1080) | Edge safety |
| Right margin | 54px from right (5% of 1080) | Edge safety |

**Safe content area:** 972px wide x 1670px tall, starting at (54, 100).

Rules:
- No caption text may be rendered outside the safe area.
- Logo watermarks should be positioned within the safe area.
- Critical visual content (product images, key text) should remain within the safe area.

---

## 4. Enforcement Points

Brand-safe constraints are enforced at multiple stages:

| Stage | Module | Constraints Enforced |
|-------|--------|---------------------|
| Planning | Scene Planner | Transition restriction, product image protection (not fed to engines) |
| Engine Invocation | Engine Manager / Prompt Builder | Prompt sanitization (blocklist, substitutions, safety cues) |
| Post-Generation | Engine Validator | Optional OCR check, content safety escalation |
| Assembly | Video Composer / Pipeline | Logo watermark, brand font, color palette, safe zones |
| Captioning | Caption Renderer | Brand font, brand colors, safe zone positioning |

---

## 5. Configuration

Brand-safe settings are primarily driven by the preset, with global defaults in `config/defaults.yaml`:

```yaml
# In preset configuration
brand_safe_defaults:
  logo_path: null               # Path to brand logo file
  logo_position: "top-right"    # top-left | top-right | bottom-left | bottom-right
  logo_opacity: 0.7             # 0.0 - 1.0
  logo_mode: "persistent"       # persistent | outro
  brand_font: null              # Path to .ttf/.otf font file
  brand_palette:                # List of hex color codes
    - "#FFFFFF"
    - "#000000"
  ocr_check_enabled: false      # Enable OCR check on generated frames
  competitor_blocklist: []      # List of competitor names to filter from prompts
```

---

## 6. V1 Compatibility

All V1 brand-safe rules remain active:
- `keep_subject_static: true` prevents distortion of product images.
- Safe zones are applied to caption placement.
- Brand watermark overlay is supported (V2 makes it mandatory when `brand_safe = true`).

V2 adds the engine-specific constraints (prompt sanitization, OCR check, mandatory watermark) on top of V1.

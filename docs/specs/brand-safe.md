# Brand-Safe Mode Specification

> **Status:** FROZEN  
> **Ticket:** P1-07  
> **AC:** AC-009, AC-010  
> **Source of Record:** docs/vision/pytoon-v1.md § "Brand-Safe Mode and Fallback Logic"

---

## Overview

Brand-safe mode (`brand_safe=true`) ensures that every generated video adheres to brand guidelines. It is the **default** for all jobs and all brand-safe presets.

---

## Enforcement Rules

### AC-009: Asset and Style Restrictions

When `brand_safe=true`, the following rules are enforced:

| Rule | Implementation Point | Behavior |
|---|---|---|
| **No asset regeneration** | Engine adapter | Product/person images are rendered as-is; no AI modification, style transfer, or generative alteration unless explicitly allowed |
| **Original overlays** | Assembly pipeline | Overlay images use original uploaded assets without modification |
| **Font restriction** | Caption burn-in | Only the preset-defined font or neutral safe default (Inter) is used; no decorative or novelty fonts |
| **Transition restriction** | Assembly pipeline | Only preset-safe transitions: `crossfade` and `cut`; no glitch, strobe, flash, or rapid-cut effects |
| **Motion intensity cap** | Engine adapter | Motion profile limited to preset value; profiles `chaotic` and `punchy` are overridden to `subtle` when brand_safe=true |
| **Conservative styling** | Spec builder | No wild colors, no neon effects, no unvetted creative variations |

### AC-010: Product Identity Preservation

When `brand_safe=true`, the system must prevent visible distortion of:

| Asset Type | Protection |
|---|---|
| **Product labels** | No scaling that makes text illegible; no color shift |
| **Logos** | Rendered at original aspect ratio; no stretching or cropping |
| **Text in product imagery** | Not obscured by captions or overlays; safe zone enforcement |
| **Overall product appearance** | `keep_subject_static=true` constraint prevents motion artifacts |

---

## Brand Watermark

When `brand_safe=true` and a brand logo file exists in a well-known location:

| Location checked (in order) | Priority |
|---|---|
| `storage/brand/logo.png` | First |
| `storage/brand/watermark.png` | Second |
| `assets/brand_logo.png` | Third |

If found, the logo is overlaid on the video with:
- Position: top-right
- Scale: 120px width
- Opacity: 60%
- Margin: 30px from edges
- Duration: entire video

---

## Preset-Safe Values

"Preset-safe values" means the preset's defined configuration values for:

1. **Font** — only the font specified in the preset's `caption_style.font`
2. **Transitions** — only the transition type in the preset's `transitions.type`
3. **Motion** — limited to the preset's `motion_profile` (or downgraded if brand_safe overrides)
4. **Audio levels** — preset's `audio.music_level_db` and `audio.voice_level_db`
5. **Safe margin** — preset's `caption_style.safe_margin_px` (minimum 120px)

No values outside the preset definition are introduced when brand_safe is active.

---

## Toggle Behavior

| Scenario | RenderSpec Effect |
|---|---|
| `brand_safe=true` (default) | `constraints.keep_subject_static=true`; watermark overlay added; font/transition restricted to preset values |
| `brand_safe=false` (user override) | No watermark; all preset transitions/fonts available; motion profiles unrestricted |
| Preset says `brand_safe=true`, user says `false` | User override wins; brand-safe disabled |
| Preset says `brand_safe=false`, user says nothing | Preset default applies; brand-safe disabled |

---

## What Brand-Safe Does NOT Do in V1

- **Content moderation** — no automated filtering of user-provided text
- **Color matching** — no automatic brand color extraction
- **Template locking** — presets can still be overridden by explicit user parameters
- **Legal compliance** — no copyright or trademark checking of uploaded images

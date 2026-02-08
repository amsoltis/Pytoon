# Preset System Specification

> **Status:** FROZEN  
> **Ticket:** P1-04  
> **AC:** AC-009, AC-013  
> **Config file:** config/presets.yaml

---

## What a Preset Contains

A preset is a named configuration bundle that controls all stylistic aspects of video generation. Each preset specifies:

| Property | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (used in API requests) |
| `name` | string | Human-readable display name |
| `archetype` | enum | PRODUCT_HERO, OVERLAY, or MEME_TEXT |
| `brand_safe` | bool | Default brand-safe setting for this preset |
| `engine_policy` | enum | Default engine policy |
| `caption_style.font` | string | Font family name |
| `caption_style.size_rules` | string | "small" (40px), "auto" (56px), or "large" (72px) |
| `caption_style.position` | string | "lower_third", "center", or "upper_third" |
| `caption_style.safe_margin_px` | int | Pixel margin from screen edges |
| `motion_profile` | string | "minimal", "subtle", "smooth", "punchy", or "chaotic" |
| `transitions.type` | string | "crossfade" or "cut" |
| `transitions.duration_ms` | int | Transition duration in milliseconds |
| `audio.music_level_db` | float | Background music volume |
| `audio.voice_level_db` | float | Voice volume |
| `overlay_fx` | object | Optional: `shadow` (bool), `glow` (bool) |

---

## V1 Preset Catalog (8 presets)

### PRODUCT_HERO Presets

| ID | Brand-Safe | Motion | Font | Transitions | Notes |
|---|---|---|---|---|---|
| `product_hero_clean` | Yes | subtle | Inter | crossfade 150ms | Conservative, brand-safe hero |
| `product_hero_punchy` | No | punchy | Bebas Neue | crossfade 150ms | Dynamic, attention-grabbing |

### OVERLAY Presets

| ID | Brand-Safe | Motion | Font | Effects | Notes |
|---|---|---|---|---|---|
| `overlay_classic` | Yes | subtle | Inter | None | Clean product showcase |
| `overlay_glow` | Yes | smooth | Inter | shadow + glow | Premium feel with effects |
| `overlay_bold` | Yes | punchy | Montserrat | None | Bold text, upper positioning |

### MEME_TEXT Presets

| ID | Brand-Safe | Motion | Font | Transitions | Notes |
|---|---|---|---|---|---|
| `meme_fast` | No | chaotic | Impact | cut (0ms) | Quick cuts, meme energy |
| `meme_smooth` | No | smooth | Arial Black | crossfade 150ms | Smoother meme style |

### Special Presets

| ID | Brand-Safe | Motion | Font | Notes |
|---|---|---|---|---|
| `brand_safe_minimal` | Yes | minimal | Inter | Most conservative; local_only engine policy |

---

## Preset Interaction with Brand-Safe Mode

When `brand_safe=true` (either from preset default or user override):

1. **Font restricted** to preset-defined font or neutral safe default (Inter)
2. **Transitions restricted** to preset-safe set (crossfade, cut only)
3. **Motion intensity** capped per preset's motion_profile
4. **No asset regeneration** — original product images used without AI modification
5. **Logo watermark** automatically included if brand logo exists in storage

When `brand_safe=false`:
- All stylistic controls still come from the preset
- Additional creative effects may be applied
- No watermark unless explicitly configured

---

## Preset Resolution Order

When building a RenderSpec, values are resolved in this priority (highest wins):

1. **Explicit user input** (API request fields)
2. **Preset defaults** (from config/presets.yaml)
3. **System defaults** (from config/defaults.yaml)

Example: if the user sends `brand_safe=false` with preset `overlay_classic` (which defaults to `brand_safe=true`), the user's explicit value wins.

---

## Adding New Presets

See `docs/add-preset.md` for the procedure. New presets must:
- Have a unique `id`
- Reference a valid archetype
- Define all required fields
- Be tested with at least one sample render before deployment

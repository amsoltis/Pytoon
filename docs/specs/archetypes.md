# Video Archetype Specifications

> **Status:** FROZEN  
> **Ticket:** P1-03  
> **AC:** AC-006  
> **Source of Record:** docs/vision/pytoon-v1.md § "Input Types and Video Archetypes"

---

## PRODUCT_HERO (I2V — Image-to-Video)

**Purpose:** Bold, full-frame treatment of the product with maximum focus.

| Property | Value |
|---|---|
| Frame layout | Single media asset fills entire 1080×1920 frame |
| Aspect handling | Crop center or scale-to-fill (no black bars) |
| Motion | Ken Burns effect: zoom_in, zoom_out, pan_up, pan_down (randomized by seed) |
| Default segment duration | 3 seconds |
| Pacing | 3–7 seconds per segment; one product per segment |
| Caption position | Lower third or center; brand font with shadow |
| Caption style | Elegant, minimal — shadow for contrast |
| Transition default | Crossfade (150ms) |
| Multiple inputs | One image per segment in sequence |
| No image provided | Solid dark background fallback (0x1a1a2e) |

**Engine prompt template:**  
`"subtle cinematic motion, product showcase, {user_prompt}"`

---

## OVERLAY (Background + Product Composite)

**Purpose:** Product image composited on a styled background layer.

| Property | Value |
|---|---|
| Frame layout | Two layers: background + foreground product |
| Background | Blurred/darkened copy of product image, or solid color (0x0d1117) |
| Product sizing | 60% of frame width, centered horizontally, positioned at ~38% from top |
| Motion | Subtle slow zoom on background layer |
| Default segment duration | 3 seconds |
| Caption position | Lower third with semi-transparent box |
| Caption style | Clean font (Inter), box behind text for readability |
| Transition default | Crossfade (150ms) |
| Transparent PNGs | Supported — alpha channel preserved for product cutouts |
| No image provided | Solid dark background only |
| Brand-safe effects | Optional shadow and glow via preset `overlay_fx` |

**Engine prompt template:**  
`"abstract motion background, smooth loop, {user_prompt}"`

**Fallback:** If complex split-filter rendering fails, falls back to two-input approach (solid background + centered product overlay).

---

## MEME_TEXT (T2V — Text-to-Video)

**Purpose:** Attention-grabbing meme-style content with bold text.

| Property | Value |
|---|---|
| Frame layout | Full-frame image/video with text bar overlay |
| With image | Image fills frame with slight zoom (1.02 base + 0.001/frame) |
| Without image | Solid color background (0x1a1a2e) with centered text |
| Text bar | Black bar (130px height, 75% opacity) at top of frame |
| Font | Impact or Arial Black, bold, white, size 52, with 2px black border |
| Caption position | Top of frame (y=40) centered horizontally |
| Transition default | Cut (no transition) for "meme_fast"; crossfade for "meme_smooth" |
| Text handling | Auto-truncate to 80 characters; special characters escaped |
| Multiple inputs | One image per segment |

**Engine prompt template (text-only):**  
`"{user_prompt} (part N/M)"`

---

## Segment-to-Archetype Mapping

When the RenderSpec generator creates segments, each segment is dispatched to the renderer based on:

1. **archetype** field from the spec (global for the job)
2. **image availability** — if no image is available for a segment, MEME_TEXT falls back to text-only rendering; PRODUCT_HERO and OVERLAY fall back to solid color backgrounds

The engine adapter uses the archetype to select the rendering path:

```
PRODUCT_HERO → _render_hero()     → Ken Burns zoom/pan
OVERLAY      → _render_overlay()  → Blurred background + centered product
MEME_TEXT    → _render_meme_*()   → Full-frame + text bars
```

---

## Duration Distribution

For multiple input images mapped to segments:

- Each image becomes one segment
- If more segments than images: images are reused (first image repeated)
- If more images than can fit in 60s at minimum segment duration: extra images are dropped
- Default segment duration: 3 seconds (configurable 2–4s)
- Total duration capped at 60 seconds

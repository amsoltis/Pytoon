# Add a preset

Presets are config-driven in `config/presets.yaml`.

## Steps

1. Create a new preset entry with a unique `id`
2. Set default `archetype`, `brand_safe`, and `engine_policy`
3. Define `caption_style`, `motion_profile`, `transitions`, and `audio`
4. Keep safe margins and caption positions within 9:16 safe zones

## Example

```
  - id: overlay_modern
    name: Overlay Modern
    archetype: OVERLAY
    brand_safe: true
    engine_policy: local_preferred
    caption_style:
      font: "Inter"
      size_rules: "auto"
      position: "lower_third"
      safe_margin_px: 120
    motion_profile: smooth
    transitions:
      type: crossfade
      duration_ms: 150
    audio:
      music_level_db: -18
      voice_level_db: -6
```

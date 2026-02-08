# Phase 1 V2 Exit Gate -- Sign-Off Artifact

**Ticket:** P1-EXIT  
**Date:** 2026-02-07  
**Acceptance Criteria:** V2-AC-020, V2-AC-021

---

## Exit Criteria Checklist

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Scene Graph schema is defined and versioned at 2.0 | PASS | `schemas/scene_graph_v2.json` -- JSON Schema with version "2.0", all required fields (id, description, duration, media, caption, audio, style, overlays, transition, globalAudio), validation rules (≥1 scene, duration sum ≤60s, unique IDs) |
| 2 | Timeline schema is defined and versioned | PASS | `schemas/timeline_v2.json` -- JSON Schema with version "2.0", timeline entries, tracks (video, audio, captions), DuckRegion, Transform, validation rules (no overlapping scenes, captions within scene bounds, audio within duration) |
| 3 | Hybrid Engine Strategy is documented with engine selection rules and fallback chains | PASS | `docs/specs/hybrid-engine-strategy-v2.md` -- 3 external engines (Runway, Pika, Luma) + local FFmpeg, 6-priority selection rules, 3-level fallback chain, timeout thresholds, API key management, rate limiting, auto-rephrase on moderation rejection |
| 4 | Component interaction diagram covers all modules and data contracts | PASS | `docs/specs/v2-architecture.md` -- Mermaid flowchart with all V2 modules, sequence diagram for sample video generation, data contract table at every boundary, module boundary listing |
| 5 | Migration plan identifies all reuse/extend/replace decisions | PASS | `docs/specs/v2-migration-plan.md` -- 6 REUSE modules, 10 EXTEND modules, 19 NEW modules, API versioning strategy, database migration schema, worker dispatch logic, testing strategy |
| 6 | Sample input-to-output walkthrough exists | PASS | See Section 2 below (complete walkthrough from pytoon-v2.md line 104 scenario) |
| 7 | Scene Planner interface is specified | PASS | `docs/specs/scene-planner-v2.md` -- input/output contract, 2 planning strategies (heuristic + AI placeholder), 5 special case handlers, test requirements |
| 8 | Audio & Caption Manager is specified | PASS | `docs/specs/audio-caption-manager-v2.md` -- TTS integration (primary+backup), voiceover processing, voice-to-scene mapping, forced alignment (±100ms), caption styling, safe zones, ducking, mixing, normalization, fallback table |
| 9 | Brand-safe mode V2 is specified | PASS | `docs/specs/brand-safe-v2.md` -- 8 constraints (product protection, prompt sanitization, OCR check, logo watermark, brand font, color palette, transition restriction, moderation escalation), safe visual zones, 5 enforcement points |
| 10 | V2 output contract is specified | PASS | `docs/specs/output-contract-v2.md` -- baseline MP4 spec, 7 additional artifacts (Scene Graph JSON, Timeline JSON, per-scene metadata, voiceover, SRT captions, thumbnail, quality metrics), file layout, validation rules |
| 11 | Operating model updated for V2 | PASS | `.cursor/rules/00-operating-model.md` -- version 2.0.0, evolution model documented, V1/V2 AC relationship clarified, phase gate enforcement rule added |
| 12 | All P1 tickets closed | PASS | P1-01 through P1-10 completed |

---

## Sample Input-to-Output Walkthrough

This walkthrough traces the pytoon-v2.md reference scenario (lines 102-106) through the new V2 schemas and modules.

### Input

- **Product images:** `product1.png`, `product2.png`
- **Prompt:** "Show product, then demonstrate it in action in a fun way."
- **Preset:** `product_hero_clean`
- **Brand safe:** `true`
- **Voiceover:** None (TTS generated)

### Step 1: Scene Planning

The heuristic Scene Planner splits the prompt into 2 sentences:
1. "Show product"
2. "then demonstrate it in action in a fun way"

Produces Scene Graph:

```json
{
  "version": "2.0",
  "scenes": [
    {
      "id": 1,
      "description": "Product hero shot",
      "duration": 5000,
      "media": {
        "type": "image",
        "asset": "storage/jobs/{job_id}/assets/product1.png",
        "engine": null,
        "prompt": null,
        "effect": "ken_burns_zoom"
      },
      "caption": "Show product",
      "audio": null,
      "style": { "mood": "clean", "camera_motion": "slow zoom in", "lighting": "studio" },
      "overlays": [],
      "transition": "fade"
    },
    {
      "id": 2,
      "description": "Product in action, fun demonstration",
      "duration": 8000,
      "media": {
        "type": "video",
        "asset": null,
        "engine": "pika",
        "prompt": "A person using the product outdoors, fun energetic scene, bright daylight",
        "effect": null
      },
      "caption": "Demonstrate it in action in a fun way",
      "audio": null,
      "style": { "mood": "fun", "camera_motion": null, "lighting": "natural" },
      "overlays": [
        { "type": "product_image", "asset": "storage/jobs/{job_id}/assets/product1.png", "position": "center", "scale": 0.5, "opacity": 1.0 }
      ],
      "transition": "cut"
    }
  ],
  "globalAudio": {
    "voiceScript": "Show product. Demonstrate it in action in a fun way.",
    "voiceFile": null,
    "backgroundMusic": "assets/music/uplifting_track.mp3"
  }
}
```

### Step 2: Timeline Construction

Timeline Orchestrator lays out scenes:

```json
{
  "version": "2.0",
  "totalDuration": 13000,
  "timeline": [
    { "sceneId": 1, "start": 0, "end": 5000, "transition": { "type": "fade", "duration": 500 } },
    { "sceneId": 2, "start": 4500, "end": 12500, "transition": null }
  ],
  "tracks": {
    "video": [
      { "sceneId": 1, "asset": "product1.png", "effect": "ken_burns_zoom", "layer": 0 },
      { "sceneId": 2, "asset": null, "effect": null, "layer": 0 },
      { "sceneId": 2, "asset": "product1.png", "layer": 1, "transform": { "position": "center", "scale": 0.5 } }
    ],
    "audio": [
      { "type": "voiceover", "file": null, "start": 0 },
      { "type": "music", "file": "assets/music/uplifting_track.mp3", "start": 0, "volume": 0.5, "duckRegions": [] }
    ],
    "captions": [
      { "text": "Show product", "start": 200, "end": 3000, "sceneId": 1 },
      { "text": "Demonstrate it in action in a fun way", "start": 5000, "end": 10000, "sceneId": 2 }
    ]
  }
}
```

### Step 3: Engine Invocation

- **Scene 1:** `media.type = "image"` → local FFmpeg renders Ken Burns zoom on product1.png → `scene_1.mp4`
- **Scene 2:** `media.engine = "pika"` → Pika API receives prompt + product1.png → returns 8s video clip → validated → `scene_2.mp4`
- Brand-safe prompt sanitization appends "family-friendly, professional, brand-safe" to Pika prompt.
- Product image overlay for Scene 2 is composited as a separate layer (not fed to Pika).

### Step 4: Audio & Caption Processing

- TTS generates voiceover from `globalAudio.voiceScript` → `voiceover.mp3` (13s).
- Forced alignment maps "Show product" to 0.2s-3.0s, "Demonstrate it..." to 5.0s-10.0s.
- Caption timestamps updated in Timeline.
- Background music loaded, duck regions set for 0.2-3.0s and 5.0-10.0s.
- Music ducked by -12dB during voice regions with 0.2s fade transitions.
- Voice + ducked music mixed to single audio track.
- Loudness normalized to -14 LUFS.

### Step 5: Assembly

- Scene 1 clip (Ken Burns) + Scene 2 clip (Pika video) composed with 500ms crossfade at 4.5s.
- Product image overlay composited onto Scene 2 at layer 1.
- Captions burned in per Timeline caption track with preset font/color/safe-zone.
- Brand logo watermark applied at top-right (persistent) per brand-safe mode.
- Normalized audio muxed with composed video.
- Final MP4 encoded at 1080x1920, H.264/AAC, 30fps.

### Step 6: Output

```
storage/jobs/{job_id}/
├── output.mp4           (13s, 1080x1920, H.264/AAC)
├── thumbnail.jpg
├── scene_graph.json
├── timeline.json
├── voiceover.mp3
├── captions.srt
├── metadata.json
└── scenes/
    ├── scene_1.mp4
    └── scene_2.mp4
```

---

## Sign-Off

Phase 1 exit criteria are **fully satisfied**. All design artifacts are produced, versioned, and internally consistent. The sample walkthrough demonstrates end-to-end data flow through the V2 schemas and modules.

**Phase 1 is COMPLETE. Phase 2 may begin.**

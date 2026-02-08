# Phase 4 Exit Gate — Sign-Off

> **Ticket:** P4-EXIT  
> **AC:** AC-001, AC-002, AC-009, AC-010, AC-012

---

## Exit Criteria Checklist

| Criterion | Status | Evidence |
|---|---|---|
| Videos are postable without manual fixes | PASS | Final export: H.264, AAC, 1080x1920, yuv420p, +faststart (pipeline.py line 178-189) |
| Product identity remains stable | PASS | brand_safe=true: keep_subject_static constraint, original images used (runner.py, brand-safe spec) |
| Presets produce consistent output | PASS | 8 presets defined with deterministic rendering params; seed-based Ken Burns selection |
| 60-second videos assemble correctly | PASS | Segment planner handles 60s (20 segments × 3s); test_60s.py validates |

## Implementation Traceability

| Ticket | Deliverable | Status |
|---|---|---|
| P4-01 | Segment concatenation | PASS — ffmpeg_ops.py `concat_segments()` with demuxer and xfade |
| P4-02 | Crossfade transitions | PASS — ffmpeg_ops.py `_concat_xfade()` with configurable duration |
| P4-03 | 9:16 scaling/cropping | PASS — concat forces scale={w}x{h}; hero/overlay renderers fill frame |
| P4-04 | Product/person overlay | PASS — ffmpeg_ops.py `overlay_image()` with positioning and alpha |
| P4-05 | Brand-safe enforcement | PASS — spec_builder sets constraints; pipeline applies watermark if brand_safe |
| P4-06 | Caption rendering | PASS — ffmpeg_ops.py `burn_captions()` with archetype-aware styling (MEME, HERO, OVERLAY) |
| P4-07 | Caption safe zones | PASS — `safe_margin_px` enforced in burn_captions (default 120px); preset minimum 120px |
| P4-08 | Audio mixing | PASS — ffmpeg_ops.py `mix_audio()` with music looping, voice ducking, fade-out |
| P4-09 | Loudness normalization | PASS — ffmpeg_ops.py `loudness_normalize()` with EBU R128 (loudnorm filter) |
| P4-10 | Preset system | PASS — spec_builder resolves preset → RenderSpec; pipeline reads preset config |
| P4-11 | 60-second support | PASS — test_60s.py validates 20 segments, caption spanning, duration bounds |
| P4-12 | Thumbnail generation | PASS — ffmpeg_ops.py `extract_thumbnail()` at t=1.0s |
| P4-13 | Assembly pipeline orchestrator | PASS — pipeline.py: concat → overlay → captions → watermark → audio → normalize → final → thumbnail |
| P4-14 | Full RenderSpec generator | PASS — spec_builder.py: segments, captions, audio, constraints, preset-derived values |

## Phase 4 Verdict: PASS

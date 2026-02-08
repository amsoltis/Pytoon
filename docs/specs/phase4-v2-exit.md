# Phase 4 Exit Gate — Audio & Captions

**Date:** 2026-02-07  
**Status:** PASS  
**Tests:** 159 total (28 new Phase 4 + 131 Phase 1-3) — all passing, zero regressions

---

## Criteria Checklist

| # | Criterion | Status |
|---|-----------|--------|
| 1 | TTS integration with primary+backup+local fallback | PASS |
| 2 | Voiceover ingestion: validate, resample, trim silence, ASR | PASS |
| 3 | Voice-to-scene mapping: sentence split, ordered assignment, uneven ratios | PASS |
| 4 | Forced alignment: WhisperX/stable-ts + even-time fallback | PASS |
| 5 | Caption rendering: preset-driven font/size/color/outline, fade animation | PASS |
| 6 | Safe zone enforcement: top 100px, bottom 150px, sides 54px, auto-wrap, min 20px | PASS |
| 7 | Background music pipeline: trim with fade-out, seamless loop, -12 dBFS base | PASS |
| 8 | Audio ducking: -12 dB during voice, 0.2s fade transitions, merged regions | PASS |
| 9 | Multi-track mixing: voice ~-6 dBFS + ducked music, limiter -1 dBFS | PASS |
| 10 | Volume normalization: FFmpeg loudnorm targeting -14 LUFS | PASS |
| 11 | Full pipeline wired: 12-stage assembly (compose → captions → audio → mux → export) | PASS |
| 12 | SRT subtitle file generation | PASS |

---

## New Modules

| Module | Purpose |
|--------|---------|
| `pytoon/audio_manager/tts.py` | TTS generation (ElevenLabs, OpenAI, Google, local, silence fallback) |
| `pytoon/audio_manager/voice_processor.py` | Audio ingestion, resampling, silence trimming, ASR transcription |
| `pytoon/audio_manager/voice_mapper.py` | Transcript-to-scene mapping with duration estimation |
| `pytoon/audio_manager/alignment.py` | Forced alignment (WhisperX, stable-ts, even-time fallback) |
| `pytoon/audio_manager/caption_renderer.py` | Styled caption burn-in with safe zones + SRT generation |
| `pytoon/audio_manager/music.py` | Background music pipeline (load, trim/loop, base volume) |
| `pytoon/audio_manager/ducking.py` | Audio ducking region detection + volume envelope application |
| `pytoon/audio_manager/mixer.py` | Multi-track audio mixing + video muxing |

## Updated Modules

| Module | Change |
|--------|--------|
| `pytoon/assembler/pipeline.py` | `assemble_job_v2` rewritten as 12-stage pipeline with full audio/caption support |
| `config/defaults.yaml` | Added `tts` and `caption_style` configuration sections |

---

## V2 Assembly Pipeline (12 Stages)

1. Compose scenes with transitions
2. Generate/process voiceover (TTS or user audio)
3. Map voice to scenes + forced alignment
4. Prepare background music (trim/loop/volume)
5. Apply audio ducking to music
6. Burn styled captions onto video
7. Brand watermark
8. Mix voice + ducked music
9. Normalize volume to -14 LUFS
10. Mux audio onto video
11. Final export (H.264/AAC, faststart)
12. Generate SRT + thumbnail

---

## Sign-off

Phase 4 is complete. Phase 5 (Final Polish & Delivery) is now unblocked.

# Audio & Caption Manager -- V2 Specification

**Ticket:** P1-06  
**Acceptance Criteria:** V2-AC-002, V2-AC-003, V2-AC-004, V2-AC-007, V2-AC-008, V2-AC-009  
**Source:** pytoon-v2.md "Audio & Caption Manager" (line 68), "Timeline-Based Captioning" (lines 189-197), "Audio Layering, Ducking, and Sync to Voice" (lines 249-259)

---

## 1. Overview

The Audio & Caption Manager is responsible for all spoken, musical, and textual content in the video. It handles voiceover generation/ingestion, voice-to-scene mapping, forced alignment for caption synchronization, caption styling, background music processing, audio ducking, multi-track mixing, and volume normalization.

---

## 2. Voiceover Handling

### 2.1 Input Sources

| Source | Behavior |
|--------|----------|
| User-provided audio file | Accept WAV, MP3, or AAC. Process and use directly. |
| Text script (via prompt or `globalAudio.voiceScript`) | Generate audio via TTS. |
| Neither provided | No voiceover; music-only or silent video with captions only. |

### 2.2 TTS Generation

**Primary provider:** Cloud TTS API (configurable -- ElevenLabs, Google Cloud TTS, or OpenAI TTS).  
**Backup provider:** Different cloud provider or local TTS engine (e.g., pyttsx3, Coqui TTS).

Process:
1. Send `globalAudio.voiceScript` to the primary TTS provider with voice preset settings (voice name, speed, pitch).
2. If primary fails (HTTP error, timeout, quality issue), try backup provider automatically.
3. If all TTS providers fail, return `null` -- the caller falls back to text-only video with extended caption display.
4. Output: audio file path (WAV or MP3), duration in milliseconds.

Configuration in `config/defaults.yaml`:
```yaml
tts:
  primary_provider: "elevenlabs"  # elevenlabs | google | openai | local
  backup_provider: "openai"
  voice_name: "default"
  speed: 1.0
  output_format: "mp3"
```

### 2.3 Voiceover Processing

For both user-provided and TTS-generated audio:
1. **Validate format:** Accept WAV, MP3, AAC only.
2. **Resample:** Convert to 44.1kHz or 48kHz stereo if needed.
3. **Trim silence:** Remove leading/trailing silence (configurable threshold, default -40dBFS).
4. **Measure duration:** Record total duration in milliseconds.
5. **Handle overlong audio:** If voiceover duration > total video duration:
   - Warn and either: (a) extend video timeline if within 60s budget, or (b) trim voiceover at the end with a 0.5s fade-out.
6. **ASR transcription:** If user provided audio without a script, run speech-to-text (Whisper or similar) to extract transcript text for captions.

Output: processed audio file path, duration_ms, transcript text.

---

## 3. Voice-to-Scene Mapping

### 3.1 Sentence Splitting

Split the transcript into sentences/phrases by punctuation (`.`, `!`, `?`) or semantic breaks.

### 3.2 Scene Assignment

- Assign sentences to scenes **in order**: sentence 1 → scene 1, sentence 2 → scene 2, etc.
- **More sentences than scenes:** Combine multiple sentences per scene (join with space).
- **More scenes than sentences:** Some scenes get no voice segment (music only during those scenes).

### 3.3 Duration Estimation

For each sentence mapped to a scene:
- Estimate audio duration from the TTS output or the voice file waveform.
- If a sentence's audio duration > its assigned scene's duration:
  - **Option A (preferred):** Extend the scene duration (if total stays within 60s budget).
  - **Option B:** Compress speech slightly (up to 1.1x speed) using FFmpeg `atempo` filter.
- If sentence audio is shorter than scene duration: that's fine -- the remaining time has music only.

### 3.4 Timeline Update

Update the Timeline's `tracks.audio[]` with a voiceover `AudioTrack` entry containing per-scene start/end times aligned to the voice segments.

---

## 4. Forced Alignment (Caption Sync ±100ms)

### 4.1 Target Accuracy

Caption display must sync to voiceover within **±100 milliseconds** of the spoken word onset.

### 4.2 Alignment Method

Use a forced alignment library to produce word-level or phrase-level timestamps:
- **Preferred tools:** WhisperX (word-level timestamps), `stable-ts`, `gentle`, or `aeneas`.
- Input: transcript text + voiceover audio file.
- Output: list of `AlignedCaption` objects, each with `text`, `start_ms`, `end_ms`.

### 4.3 Granularity

- Default: phrase/sentence level (one caption per sentence).
- Optional: word-level highlighting (future enhancement, not required for V2).

### 4.4 Fallback

If alignment fails or produces low-confidence results:
- Fall back to **even-time sentence splitting**: divide each scene's duration equally among its caption segments.
- Log a warning indicating alignment fallback.

### 4.5 Timeline Update

Update the Timeline's `tracks.captions[]` with `CaptionTrack` entries using the aligned timestamps. Each caption's `sceneId` is set to its owning scene. Validation: caption `[start, end]` must fall within the scene's `[start, end]` boundaries.

---

## 5. Caption Styling

### 5.1 Preset-Driven Styling

All caption styling is driven by the active preset:

| Property | Default | Description |
|----------|---------|-------------|
| `font_family` | System sans-serif | Font file path (.ttf/.otf) or name |
| `font_size` | 48px | Base font size at 1080x1920 |
| `font_color` | `#FFFFFF` (white) | Text color |
| `outline_color` | `#000000` (black) | Text outline/stroke color |
| `outline_width` | 2px | Outline thickness |
| `background_color` | `#000000` | Semi-transparent background bar color |
| `background_opacity` | 0.5 | Background bar opacity (0.0-1.0) |
| `position` | `bottom-center` | Caption position on frame |
| `max_lines` | 2 | Maximum number of lines for text wrapping |
| `animation` | `fade` | Caption entrance/exit animation (fade-in/fade-out, 0.2s) |

### 5.2 Auto Line-Wrap

- If caption text exceeds the safe zone width at the configured font size, auto-wrap to the next line.
- Maximum 2 lines. If text still doesn't fit at 2 lines, reduce font size (minimum 20px).
- If text still doesn't fit at minimum font size, truncate with ellipsis.

### 5.3 Brand-Safe Override

When `brand_safe = true`:
- Font is locked to the brand font from the preset.
- Colors are locked to the brand palette.
- No font size below 24px (ensures legibility).

---

## 6. Safe Zone Enforcement

On 1080x1920 frames:

| Zone | Margin |
|------|--------|
| Top | 100px (platform status bar) |
| Bottom | 150px (platform UI/buttons) |
| Left | 54px (5% of 1080) |
| Right | 54px (5% of 1080) |

- No caption text rendered outside these boundaries.
- Caption `position: bottom-center` places text 150px above the bottom edge.
- All caption types (voiceover captions, title text, CTA text) respect safe zones.

---

## 7. Background Music Pipeline

### 7.1 Music Source

- Load from preset default (`backgroundMusic` in globalAudio) or user upload.
- Music library location: `assets/music/` (royalty-free tracks).

### 7.2 Duration Fitting

| Scenario | Action |
|----------|--------|
| Music longer than video | Trim to video duration with 2s fade-out at end |
| Music shorter than video | Loop seamlessly (crossfade at loop point, 0.5s overlap) |
| No music available | Produce silence track |

### 7.3 Base Volume

- Solo (no voice): -12 dBFS.
- Under voice (before ducking): -12 dBFS (ducking further reduces this).

---

## 8. Audio Ducking

### 8.1 Duck Region Detection

Identify voice-active segments from the voiceover timestamps (where voice audio is present). Each voice-active segment becomes a `DuckRegion`.

### 8.2 Ducking Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `duck_amount` | -12 dB | Volume reduction during voice-active regions |
| `fade_in` | 0.2s | Fade-down transition at duck region start |
| `fade_out` | 0.2s | Fade-up transition at duck region end |

### 8.3 Behavior

- During voice-active regions: music volume drops by `duck_amount`.
- Between voice-active regions (pauses): music returns to base volume.
- Transitions are smooth (0.2s fade, not instant).

### 8.4 Output

- List of `DuckRegion` objects stored in the Timeline's `tracks.audio[]` music entry.
- Generate the ducked music audio file by applying volume envelopes using FFmpeg `volume` filter with keyframes or pydub.

---

## 9. Multi-Track Audio Mixing

### 9.1 Tracks

| Track | Level | Description |
|-------|-------|-------------|
| Voiceover | ~-6 dBFS average | Primary audio, natural level |
| Background music | -12 dBFS (ducked further during voice) | Already processed with duck regions |

### 9.2 Mixing Rules

1. Mix voiceover + ducked music into a single stereo output.
2. Apply 50ms crossfade at any audio track boundary to prevent pops/clicks.
3. Apply limiter at -1 dBFS peak to prevent clipping.
4. Handle edge cases: voice-only (no music), music-only (no voice), both present.

### 9.3 Implementation

Use FFmpeg `amix` / `amerge` filters or pydub for mixing.

---

## 10. Volume Normalization

### 10.1 Target

- Apply FFmpeg `loudnorm` filter targeting **-14 LUFS** (standard for social media platforms).
- Apply as the **last** audio processing step, after mixing.

### 10.2 Requirements

- Normalized audio must not clip.
- Voice clarity must be maintained.
- Measure and log pre-normalization and post-normalization LUFS values.

---

## 11. Fallback Behavior

| Failure | Fallback |
|---------|----------|
| TTS primary fails | Try backup TTS provider |
| All TTS fails | Text-only video with extended caption display, no voiceover |
| Forced alignment fails | Even-time sentence splitting per scene |
| Background music file missing | Proceed without music (voice-only or silent) |
| Voiceover too long for video | Trim with fade-out or extend video if within 60s budget |
| ASR transcription fails | Use prompt text as caption fallback |

---

## 12. Module Structure

```
pytoon/audio_manager/
├── __init__.py
├── tts.py              # TTS integration (primary + backup)
├── voice_processor.py  # Voiceover ingestion and processing
├── voice_mapper.py     # Voice-to-scene mapping
├── alignment.py        # Forced alignment (caption sync)
├── music.py            # Background music pipeline
├── ducking.py          # Audio ducking
├── mixer.py            # Multi-track audio mixing
```

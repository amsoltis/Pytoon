# V2 Output Contract and Delivery Specification

**Ticket:** P1-10  
**Acceptance Criteria:** V2-AC-013, V2-AC-014, V2-AC-015, V2-AC-020  
**Source:** pytoon-v2.md "Resolution and Aspect Ratio" (line 290), "Duration <= 60s" (line 291), "File Format Compatibility" (line 292), "Scene Graph and Timeline Persistence" (lines 317, 328)

---

## 1. Baseline Output (Same as V1)

| Property | Value |
|----------|-------|
| Container | MP4 |
| Video codec | H.264 (High Profile) |
| Audio codec | AAC (LC) |
| Resolution | 1080x1920 |
| Aspect ratio | 9:16 (vertical) |
| Frame rate | 30 fps |
| Max duration | 60 seconds |
| Video bitrate | ~5-8 Mbps (quality-dependent) |
| Audio bitrate | 192 kbps stereo |
| Audio sample rate | 44.1 kHz or 48 kHz |
| Keyframe interval | 2 seconds (60 frames) |

Output must be playable on common devices and social platforms (TikTok, Instagram Reels, YouTube Shorts).

---

## 2. V2 Additional Artifacts

V2 persists the following artifacts alongside the output video for traceability, re-rendering, and debugging.

### 2.1 Scene Graph JSON

- **File:** `storage/jobs/{job_id}/scene_graph.json`
- **Content:** The validated Scene Graph used to generate the video, conforming to `schemas/scene_graph_v2.json`.
- **Persisted at:** After scene planning completes (before engine invocation).
- **API access:** `GET /api/v2/jobs/{job_id}/scene-graph`

### 2.2 Timeline JSON

- **File:** `storage/jobs/{job_id}/timeline.json`
- **Content:** The final Timeline used to assemble the video, conforming to `schemas/timeline_v2.json`. Includes actual aligned caption timestamps and resolved asset paths.
- **Persisted at:** After assembly completes (final version with all actual paths and timestamps).
- **API access:** `GET /api/v2/jobs/{job_id}/timeline`

### 2.3 Per-Scene Metadata

Stored in the database `SceneRow` table and accessible via the job status API:

| Field | Description |
|-------|-------------|
| `engine_used` | Which engine rendered this scene (runway/pika/luma/local) |
| `fallback_used` | Boolean -- whether fallback was triggered for this scene |
| `render_duration_ms` | Time taken to render this scene |
| `error_message` | Error details if fallback was triggered |
| `asset_path` | Path to the rendered scene clip |

### 2.4 Voiceover Audio File

- **File:** `storage/jobs/{job_id}/voiceover.{mp3|wav}`
- **Content:** The processed voiceover audio (either TTS-generated or user-provided after processing).
- **Preserved for:** Re-rendering, re-alignment, debugging audio sync issues.

### 2.5 Caption Track (SRT/VTT)

- **File:** `storage/jobs/{job_id}/captions.srt`
- **Content:** Standard SRT subtitle file exported from the Timeline's caption track.
- **Purpose:** For platforms that accept separate subtitle files (YouTube, Vimeo), and for accessibility.
- **Format:** SRT with sequential numbering, timestamps in `HH:MM:SS,mmm` format.

### 2.6 Thumbnail

- **File:** `storage/jobs/{job_id}/thumbnail.jpg`
- **Content:** Key frame extracted from the video (same as V1).
- **Selection:** First frame of the first scene, or a configurable frame offset.

### 2.7 Quality Metrics

Stored in the job metadata:

| Metric | Description |
|--------|-------------|
| `output_lufs` | Final audio loudness (LUFS measurement) |
| `engine_success_count` | Number of scenes that used their primary engine successfully |
| `engine_fallback_count` | Number of scenes that triggered fallback |
| `total_render_duration_ms` | End-to-end pipeline duration |

---

## 3. Output File Layout

```
storage/jobs/{job_id}/
├── output.mp4              # Final video
├── thumbnail.jpg           # Key frame thumbnail
├── scene_graph.json        # Persisted Scene Graph
├── timeline.json           # Persisted Timeline (final)
├── voiceover.mp3           # Voiceover audio (if applicable)
├── captions.srt            # Caption track (SRT format)
├── metadata.json           # Render metadata (V1 compatible + V2 extensions)
└── scenes/                 # Per-scene rendered clips
    ├── scene_1.mp4
    ├── scene_2.mp4
    └── scene_N.mp4
```

---

## 4. Validation Rules

Before marking a V2 job as DONE:
1. `output.mp4` exists and is a valid MP4 (probe with ffprobe).
2. Resolution is exactly 1080x1920.
3. Duration does not exceed 60 seconds.
4. Codec is H.264 video + AAC audio.
5. `scene_graph.json` is valid against the Scene Graph schema.
6. `timeline.json` is valid against the Timeline schema.
7. `thumbnail.jpg` exists and is non-empty.
8. All referenced scene clip files in `scenes/` exist.

---

## 5. V1 Compatibility

V1 jobs (version=1) continue to produce the V1 output layout:
- `output.mp4`, `thumbnail.jpg`, `metadata.json`
- No scene_graph.json, timeline.json, captions.srt, or scenes/ directory.

V2 jobs (version=2) produce the full V2 layout. The `metadata.json` format is backward-compatible (V2 adds fields; does not remove V1 fields).

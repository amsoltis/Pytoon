# Output Contract and Delivery Specification

> **Status:** FROZEN  
> **Ticket:** P1-06  
> **AC:** AC-001, AC-002, AC-003

---

## Video Output Contract (AC-001)

Every completed job produces a final video with these exact specifications:

| Property | Value | Tolerance |
|---|---|---|
| Container | MP4 (.mp4) | — |
| Video codec | H.264 (libx264) | — |
| Audio codec | AAC | Only if audio is present |
| Audio bitrate | 192 kbps | — |
| Resolution | 1080×1920 | Exact; no variance |
| Aspect ratio | 9:16 | — |
| Frame rate | 30 fps | — |
| Pixel format | yuv420p | — |
| Max bitrate | 12 Mbps | — |
| MP4 flags | +faststart | For progressive download |

---

## Duration Contract (AC-002)

| Property | Value |
|---|---|
| Minimum duration | 1 second |
| Maximum duration | 60 seconds |
| Tolerance | ±0.5 seconds from `target_duration_seconds` |
| Enforcement point 1 | API validation (`target_duration_seconds` field: 1–60) |
| Enforcement point 2 | Segment planner (sum of segments = target duration) |
| Enforcement point 3 | Assembly pipeline (final re-encode enforces duration) |

---

## Thumbnail Contract (AC-003)

| Property | Value |
|---|---|
| Format | JPEG (.jpg) |
| Source | Frame extracted from final video at t=1.0s |
| Quality | FFmpeg quality level 2 |
| Storage location | `storage/jobs/{job_id}/thumbnail.jpg` |
| URI | Included in job status response as `thumbnail_uri` |

---

## Output File Layout

Every completed job produces the following files in storage:

```
storage/jobs/{job_id}/
├── segments/
│   ├── seg_000.mp4          # Rendered segment 0
│   ├── seg_001.mp4          # Rendered segment 1
│   └── ...
├── assembly/
│   ├── 01_concat.mp4        # Concatenated segments
│   ├── 02_overlay.mp4       # After product overlay (if applicable)
│   ├── 03_captions.mp4      # After caption burn-in
│   ├── 03b_watermark.mp4    # After brand watermark (if brand_safe)
│   ├── 04_audio.mp4         # After audio mixing (if audio present)
│   ├── 05_normalized.mp4    # After loudness normalization
│   ├── final.mp4            # Final export with correct settings
│   └── thumbnail.jpg        # Extracted thumbnail
├── output.mp4               # Final output (copied to persistent storage)
├── thumbnail.jpg            # Thumbnail (copied to persistent storage)
├── metadata.json            # Render metadata
└── fallback_template.mp4    # Only if template fallback was used
```

---

## Metadata Output

Each job produces a `metadata.json` with:

```json
{
  "job_id": "string",
  "preset_id": "string",
  "archetype": "PRODUCT_HERO | OVERLAY | MEME_TEXT",
  "engine_used": "string",
  "brand_safe": true,
  "target_duration_seconds": 15,
  "segments": [
    {
      "index": 0,
      "engine": "local_ffmpeg",
      "uri": "file:///...",
      "seed": 42,
      "duration": 3.0
    }
  ],
  "fallback_used": false,
  "fallback_reason": null,
  "seeds": [42, 43, 44],
  "created_at": "ISO-8601",
  "completed_at": "ISO-8601"
}
```

---

## Delivery

| Method | Endpoint | Response |
|---|---|---|
| Job status | `GET /api/v1/jobs/{job_id}` | `output_uri`, `thumbnail_uri`, `metadata_uri` |
| Direct file access | Filesystem path | `storage/jobs/{job_id}/output.mp4` |
| Storage URI scheme | `file://` | V1 uses filesystem; S3 URIs reserved for future |

---

## Platform Compatibility

The output contract is designed for direct upload to:
- Instagram Reels (1080×1920, H.264, ≤60s)
- TikTok (1080×1920, H.264, ≤60s)
- YouTube Shorts (1080×1920, H.264, ≤60s)

No additional transcoding should be needed.

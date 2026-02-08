# Pytoon V2 Architecture -- Component Interaction and Data Flow

**Ticket:** P1-07  
**Acceptance Criteria:** V2-AC-021  
**Source:** pytoon-v2.md "Major Components and Their Interactions" (lines 57-69), "Component Interaction Details" (lines 102-106)

---

## 1. Component Architecture Diagram

```mermaid
flowchart LR
    subgraph User_Inputs["User Inputs"]
        A1["Product Images"]
        A2["Text Prompt / Script"]
        A3["Style Preset"]
        A4["Voiceover File (optional)"]
        A5["Engine Preference (optional)"]
    end

    subgraph API_Layer["API Layer"]
        B1["Input Handler<br/>(routes.py, validation.py)"]
    end

    subgraph Planning["Planning Phase"]
        C1["Scene Planner<br/>(planner.py)"]
        C2[["Scene Graph JSON<br/>(scene_graph_v2.json)"]]
    end

    subgraph Orchestration["Orchestration Phase"]
        D1["Timeline Orchestrator<br/>(orchestrator.py)"]
        D2[["Timeline JSON<br/>(timeline_v2.json)"]]
    end

    subgraph Engine_Phase["Engine Phase"]
        E1["Engine Manager<br/>(engine_manager.py)"]
        E2["Prompt Builder<br/>(prompt_builder.py)"]
        E3["Runway Adapter"]
        E4["Pika Adapter"]
        E5["Luma Adapter"]
        E6["Local FFmpeg<br/>(fallback)"]
        E7["Engine Validator<br/>(validator.py)"]
    end

    subgraph Audio_Phase["Audio & Caption Phase"]
        F1["TTS Generator<br/>(tts.py)"]
        F2["Voice Processor<br/>(voice_processor.py)"]
        F3["Voice Mapper<br/>(voice_mapper.py)"]
        F4["Forced Aligner<br/>(alignment.py)"]
        F5["Music Processor<br/>(music.py)"]
        F6["Audio Ducker<br/>(ducking.py)"]
        F7["Audio Mixer<br/>(mixer.py)"]
    end

    subgraph Assembly_Phase["Assembly Phase"]
        G1["Scene Composer<br/>(ffmpeg_ops.py)"]
        G2["Caption Renderer<br/>(ffmpeg_ops.py)"]
        G3["Audio Muxer<br/>(pipeline.py)"]
        G4["Volume Normalizer<br/>(ffmpeg_ops.py)"]
        G5["Final Encoder<br/>(pipeline.py)"]
    end

    subgraph Output["Output"]
        H1["output.mp4"]
        H2["thumbnail.jpg"]
        H3["scene_graph.json"]
        H4["timeline.json"]
        H5["captions.srt"]
        H6["voiceover.mp3"]
        H7["metadata.json"]
    end

    A1 & A2 & A3 & A4 & A5 --> B1
    B1 --> C1
    C1 --> C2
    C2 --> D1
    D1 --> D2

    C2 --> E1
    E1 --> E2
    E2 --> E3 & E4 & E5
    E1 --> E6
    E3 & E4 & E5 --> E7
    E7 --> G1

    C2 --> F1
    A4 --> F2
    F1 --> F2
    F2 --> F3
    F2 --> F4
    F3 --> D2
    F4 --> D2
    F5 --> F6
    F3 --> F6
    F6 --> F7
    F2 --> F7

    D2 --> G1
    E7 --> G1
    G1 --> G2
    D2 --> G2
    F7 --> G3
    G2 --> G3
    G3 --> G4
    G4 --> G5

    G5 --> H1 & H2 & H7
    C2 --> H3
    D2 --> H4
    F4 --> H5
    F2 --> H6
```

---

## 2. Data Flow Narrative

### Step 1: Input Ingestion

**Module:** `pytoon/api_orchestrator/routes.py`, `validation.py`  
**Input:** Product images, text prompt, preset selection, optional voiceover, optional engine preference.  
**Output:** Validated `CreateJobRequestV2` → enqueued to Redis.  
**Contract:** V2 request model (Pydantic) with fields for media files, prompt, preset, brand_safe, voiceover, engine preference.

### Step 2: Scene Planning

**Module:** `pytoon/scene_graph/planner.py`  
**Input:** Media file list, prompt, preset_id, brand_safe, target_duration.  
**Output:** `SceneGraph` JSON (conforming to `schemas/scene_graph_v2.json`).  
**Contract:** Scene Graph schema v2.0 -- ordered scenes with media, captions, styles, overlays, transitions, and global audio.

### Step 3: Timeline Construction

**Module:** `pytoon/timeline/orchestrator.py`  
**Input:** `SceneGraph` JSON.  
**Output:** `Timeline` JSON (conforming to `schemas/timeline_v2.json`).  
**Contract:** Timeline schema v2.0 -- timed scene entries, video/audio/caption tracks, transition specs.

### Step 4: Engine Invocation (Parallel)

**Module:** `pytoon/engine_adapters/engine_manager.py`, individual adapters.  
**Input:** `SceneGraph` (scenes requiring video generation).  
**Output:** Per-scene video clips stored at `storage/jobs/{job_id}/scenes/scene_{id}.mp4`.  
**Contract:** `EngineResult` dataclass per scene (video_path, duration_ms, engine_name, success, error_message).

### Step 5: Audio & Caption Processing (Parallel with Step 4)

**Module:** `pytoon/audio_manager/` (tts.py → voice_processor.py → voice_mapper.py → alignment.py, music.py → ducking.py → mixer.py).  
**Input:** `SceneGraph.globalAudio`, optional voiceover file, Timeline.  
**Output:** Processed voiceover file, aligned caption timestamps, ducked music file, mixed audio file.  
**Contract:** Updated `Timeline.tracks.captions[]` and `Timeline.tracks.audio[]` with actual timestamps and file paths.

### Step 6: Video Composition

**Module:** `pytoon/assembler/ffmpeg_ops.py`, `pipeline.py`  
**Input:** Per-scene video clips, Timeline (with transitions, video tracks).  
**Output:** Composed video with transitions (intermediate file).  
**Contract:** Single video file with all scenes concatenated per Timeline timing, transitions applied.

### Step 7: Caption Burn-In

**Module:** `pytoon/assembler/ffmpeg_ops.py`  
**Input:** Composed video, Timeline caption tracks, preset styling.  
**Output:** Video with captions burned in (intermediate file).  
**Contract:** FFmpeg drawtext operations per caption entry with preset-driven styling and safe-zone compliance.

### Step 8: Audio Assembly & Normalization

**Module:** `pytoon/assembler/pipeline.py`, `pytoon/audio_manager/mixer.py`  
**Input:** Composed+captioned video, mixed audio.  
**Output:** Final muxed video with normalized audio.  
**Contract:** MP4 with H.264 video + AAC audio, loudness normalized to -14 LUFS.

### Step 9: Final Export & Persistence

**Module:** `pytoon/assembler/pipeline.py`, `pytoon/worker/runner.py`  
**Input:** Final muxed video, Scene Graph, Timeline, voiceover, caption track.  
**Output:** All artifacts written to `storage/jobs/{job_id}/`.  
**Contract:** V2 output layout (see output-contract-v2.md).

---

## 3. Sequence Diagram -- Sample Video Generation

```mermaid
sequenceDiagram
    participant User
    participant API as Input Handler
    participant Planner as Scene Planner
    participant TLO as Timeline Orchestrator
    participant EM as Engine Manager
    participant ACM as Audio & Caption Manager
    participant Comp as Video Composer
    participant Store as Storage

    User->>API: POST /api/v2/jobs<br/>(2 images, prompt, preset)
    API->>API: Validate inputs
    API->>Store: Save uploaded images
    API-->>User: 202 Accepted (job_id)

    Note over Planner: Worker dequeues job

    Planner->>Planner: Parse prompt → 2 scenes
    Planner->>Store: Persist scene_graph.json

    TLO->>TLO: Build timeline from Scene Graph
    TLO->>Store: Persist timeline.json (initial)

    par Engine Invocation
        EM->>EM: Scene 1: image → local FFmpeg (Ken Burns)
        EM->>EM: Scene 2: video → Runway API
        EM-->>Store: Save scene_1.mp4, scene_2.mp4
    and Audio Processing
        ACM->>ACM: TTS from voiceScript
        ACM->>ACM: Forced alignment → caption timestamps
        ACM->>ACM: Load music → duck → mix
        ACM-->>Store: Save voiceover.mp3
    end

    TLO->>TLO: Update timeline with actual paths/timestamps
    TLO->>Store: Persist timeline.json (final)

    Comp->>Comp: Compose scenes with crossfade
    Comp->>Comp: Burn captions (aligned timestamps)
    Comp->>Comp: Mux audio (voice + ducked music)
    Comp->>Comp: Normalize loudness (-14 LUFS)
    Comp->>Comp: Encode final MP4

    Comp-->>Store: Save output.mp4, thumbnail.jpg,<br/>captions.srt, metadata.json

    Note over User: GET /api/v2/jobs/{job_id} → DONE
    User->>API: GET /api/v2/jobs/{job_id}
    API-->>User: JobStatusResponse (DONE, output_uri)
```

---

## 4. Data Contract Summary

| Boundary | Producer | Consumer | Contract |
|----------|----------|----------|----------|
| Input → Planner | Input Handler | Scene Planner | `CreateJobRequestV2` (Pydantic) |
| Planner → Orchestrator | Scene Planner | Timeline Orchestrator | `SceneGraph` JSON (scene_graph_v2.json) |
| Orchestrator → Composer | Timeline Orchestrator | Video Composer | `Timeline` JSON (timeline_v2.json) |
| Planner → Engine Manager | Scene Planner | Engine Manager | `SceneGraph.scenes[]` (scenes needing engines) |
| Engine Manager → Composer | Engine Manager | Video Composer | `EngineResult` per scene (video_path, metadata) |
| Planner → Audio Manager | Scene Planner | Audio & Caption Manager | `SceneGraph.globalAudio`, scene captions |
| Audio Manager → Timeline | Audio & Caption Manager | Timeline Orchestrator | Updated `tracks.captions[]`, `tracks.audio[]` |
| Audio Manager → Composer | Audio & Caption Manager | Video Composer | Mixed audio file path |
| Composer → Storage | Video Composer | Storage / API | V2 output artifacts (output.mp4, JSON files, etc.) |

---

## 5. Module Boundaries

```
pytoon/
├── api_orchestrator/     # API layer (Input Handler)
│   ├── routes.py         # V1 + V2 endpoints
│   ├── validation.py     # Input validation
│   └── auth.py           # Authentication
├── scene_graph/          # NEW: Scene Graph (V2)
│   ├── models.py         # Pydantic models
│   ├── planner.py        # Scene Planner
│   └── stub_renderer.py  # Placeholder renderer (Phase 2)
├── timeline/             # NEW: Timeline Authority (V2)
│   ├── models.py         # Pydantic models
│   └── orchestrator.py   # Timeline Orchestrator
├── engine_adapters/      # EXTENDED: + external engine adapters (V2)
│   ├── base.py           # V1 abstract adapter (retained)
│   ├── external_base.py  # NEW: V2 external engine base
│   ├── runway.py         # NEW: Runway adapter
│   ├── pika.py           # NEW: Pika adapter
│   ├── luma.py           # NEW: Luma adapter
│   ├── engine_manager.py # NEW: Multi-engine orchestrator
│   ├── prompt_builder.py # NEW: Prompt construction
│   ├── validator.py      # NEW: Engine response validation
│   ├── local_ffmpeg.py   # V1 (retained)
│   ├── local_comfyui.py  # V1 (retained)
│   ├── api_adapter.py    # V1 (retained)
│   └── selector.py       # V1 (retained for V1 jobs)
├── audio_manager/        # NEW: Audio & Caption Manager (V2)
│   ├── tts.py
│   ├── voice_processor.py
│   ├── voice_mapper.py
│   ├── alignment.py
│   ├── music.py
│   ├── ducking.py
│   └── mixer.py
├── assembler/            # EXTENDED: timeline-driven assembly (V2)
│   ├── ffmpeg_ops.py     # Extended with V2 operations
│   └── pipeline.py       # Extended with V2 pipeline
├── worker/               # EXTENDED: V2 job states and pipeline
│   ├── runner.py         # Extended for V2 jobs
│   ├── state_machine.py  # Extended with V2 states
│   └── ...
├── models.py             # EXTENDED: + V2 models
├── db.py                 # EXTENDED: + SceneRow, V2 columns
├── config.py             # EXTENDED: V2 config loading
├── storage.py            # REUSE
├── queue.py              # REUSE
├── log.py                # REUSE (extend structured fields)
└── metrics.py            # REUSE (extend V2 metrics)
```

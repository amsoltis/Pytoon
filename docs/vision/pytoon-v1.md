> STATUS: BASELINED (V1)
> This document is stable enough to execute against.
> Changes require explicit PM approval and version bump.

# Pytoon V1 – System of Record

This document is the authoritative source of truth for:
- Product vision
- Architecture
- Scope boundaries
- Phase definitions
- Acceptance criteria

All tasks, architecture decisions, and tests must trace back to this document.
If ambiguity exists, agents must propose assumptions explicitly.

# Pytoon Video Generation System - V1 Design & Plan Document

## Product Vision and Goals

Pytoon is a short-form video compiler designed to empower users (especially brands and marketers) to turn mixed media assets into engaging, **platform-ready vertical videos**. The system's purpose is to streamline the creation of branded content for social platforms (TikTok, Instagram Reels, YouTube Shorts, etc.) by automatically assembling product images, text prompts, and style presets into polished 9:16 videos up to 60 seconds long. This duration aligns with the preferred length on major short-form platforms[\[1\]](https://www.creativewebconceptsusa.com/why-create-short-form-video-content-and-best-tips/#:~:text=Why%20create%20short,of%20consumption%20on%20mobile%20devices)[\[2\]](https://www.mediaplacepartners.com/short-form-video-success/#:~:text=TikTok), where **vertical videos under 60 seconds** often perform best for capturing attention. By focusing on the 9:16 format and "snackable" length, Pytoon ensures outputs are optimized for mobile consumption and high viewer retention (short videos under ~90s keep about 50% of viewers engaged, far higher than longer clips[\[3\]](https://www.creativewebconceptsusa.com/why-create-short-form-video-content-and-best-tips/#:~:text=The%20statistics%20are%20clear,This%20matches%20the%20preference)).

**Goals:** The Pytoon system aspires to be a "video compiler" for marketing teams - users can input their product photos, brief promotional text or **prompts** (e.g. a tagline or highlight to emphasize), and select from preset styles or **archetypes**. The system then **automatically generates a branded video** with minimal manual effort. Key goals include: - **Ease of Use:** Non-technical users should be able to create videos by simply providing assets and selecting options, **without needing video editing skills**. Pytoon interprets the intent and handles the technical assembly. - **Brand Consistency:** Ensure videos adhere to brand guidelines - e.g. using approved logos, colors, and fonts - via a **"brand-safe" mode**. In brand-safe mode, the system will only use pre-approved templates, transitions, and placements so that every video is on-brand and free of any inappropriate or off-brand content. - **Quality Output:** The videos produced should be immediately ready for upload - correct resolution and aspect ratio (1080×1920 9:16), proper encoding, and engaging styling. Success is measured by outputs that **look professional and require no further editing**. - **Efficiency and Speed:** The local-first design means most videos can be rendered on the user's machine or an on-prem server quickly. Typical short videos (e.g. 15-30 seconds with a few images and captions) should render in a reasonable time (a minute or two). For heavier jobs, a fallback cloud render is available to ensure delivery within acceptable time. - **Reliability:** By combining a local engine with a cloud fallback, Pytoon aims for high reliability - even if local resources are limited, the video can still be generated via the cloud. This redundancy ensures the system is robust against failures[\[4\]](https://sider.ai/blog/ai-tools/local-vs_cloud-ai-image-generation-which-one-won-t-crash-your-creative-flow#:~:text=,and%20get%20new%20features%20instantly) and can meet content deadlines consistently.

**Supported Inputs:** Pytoon accepts a mix of media and directives: - _Product Images or Short Clips:_ e.g. PNG/JPEG product photos, or short video snippets. These will form the visual basis of the video. - _Text Prompts:_ short text to be used as captions or inspiration for the video. For example, a product tagline, a call-to-action, or a description that the system can turn into on-screen text. (In future, prompts could even drive AI-generated visuals or voiceovers, but for V1 the focus is on text overlays and simple interpretations.) - _Style Presets / Archetypes:_ Users can choose a video style (template) from supported **archetypes** - for V1 we define three: - **Hero Video:** A bold, full-frame treatment of the product. Typically one media at a time taking the entire screen (like a hero shot), with dynamic pan/zoom effects and a big headline. This is great for highlighting a single product or feature per segment with maximum focus. - **Overlay Video:** A layout where product images are **overlaid** on backgrounds or together. For example, placing a product cut-out over a colored background or stock footage, with text alongside or above. This archetype might show multiple assets in one frame (picture-in-picture or split-screen) and often includes the brand's logo or additional graphic overlays throughout. - **Meme Video:** A fun, attention-grabbing style inspired by internet memes. Typically this means **bold text captions** (often one line at the top and/or bottom of the frame in large font) over either an image or video clip. The meme style is useful for relatable, humorous marketing content. Pytoon will support adding a top/bottom text bar in the classic meme format and subtitled punchlines, while still keeping it brand-appropriate. - _Configuration Flags:_ e.g. **Brand-Safe Mode** (a toggle). When enabled, Pytoon will restrict the video generation to use only brand-approved assets, refrain from any unvetted creative effects, and ensure all text or visuals are appropriate. This mode essentially ensures nothing "unexpected" or off-brand slips in - focusing on consistency over experimental creativity. (When off, the system might allow more playful transitions or use more of the prompt's language creatively, etc., as appropriate.)

**Output Formats:** The primary output is a rendered MP4 video (H.264 + AAC) in vertical orientation (9:16 aspect, typically 1080×1920 pixels). Videos can be anywhere from a few seconds up to 60 seconds in length. Pytoon ensures the file size and encoding meet social platform requirements. In addition to the video, the system may generate a **thumbnail image** (first or a key frame) and basic metadata (duration, resolution) for each output. The video will include any requested overlays (e.g. watermark logo) and burned-in captions as specified. Success means the video can be directly uploaded to Instagram, TikTok, etc. without further modification and passes those platforms' checks.

**Success Criteria:** For V1, success will be measured by: - The system correctly producing videos that match the user's intent and inputs in at least 95% of test cases (see Acceptance Tests). For example, if given 3 product images and a tagline, the output video should incorporate all 3 images and show the tagline text clearly. - Visual quality: Videos should have smooth transitions, legible text (proper font sizing and contrast), and no glaring technical issues (no desync of audio, no black frames, etc.). - Turnaround time: On a typical modern PC or a baseline cloud instance, a 15-second video with a few assets should render in well under a minute (exact performance benchmarks can be refined, but the user experience should feel fast). - Reliability: Even if the local engine fails (due to lack of codec, low resources, etc.), the fallback kicks in seamlessly so the user still gets a video. The goal is **zero failed videos** in normal use; all jobs either succeed locally or via fallback. We will track the percentage of jobs that require fallback and ensure it stays within acceptable limits. - Stakeholder satisfaction: Product and creative teams should approve the video styles and brand alignment. Essentially, the videos should meet marketing's standards for brand safety and message - this will be validated in final acceptance review.

In summary, the vision for Pytoon is to **dramatically speed up short-form video creation** while keeping it **on-brand and hassle-free**. It will do so by intelligently assembling user-provided content into compelling vertical videos, using a local-first approach for speed and privacy with cloud rendering as a safety net. Ultimately, Pytoon will help teams produce more video content (a medium with high ROI[\[5\]](https://www.mediaplacepartners.com/short-form-video-success/#:~:text=If%20your%20business%20has%20poured,to%20other%20top%20marketing%20trends)[\[6\]](https://www.mediaplacepartners.com/short-form-video-success/#:~:text=perfect%20for%20short,to%20other%20top%20marketing%20trends)) without investing in manual editing, thereby accelerating content output in the era of booming short-form video consumption.

## Phase Map (Execution Order)

This section defines the **authoritative execution order** for building the Pytoon Video Generation System.  
Work **MUST** proceed sequentially by phase. No phase may be skipped or partially entered.

Each phase grants **explicit permission boundaries** for what work is allowed and implicitly forbids all other work.

---

### PHASE-1: Scope Alignment & Design Confirmation

**Objective:**  
Lock intent, boundaries, and contracts before implementation begins.

**Permitted work:**
- Finalize V1 scope and non-goals
- Confirm supported video archetypes:
  - Product Hero (I2V)
  - Background + Product Overlay
  - Meme/Text (T2V)
- Confirm system constraints:
  - Local-first, API-optional
  - Brand-safe mode default = ON
  - Maximum video duration = 60 seconds
- Define and freeze:
  - RenderSpec structure (fields, versioning)
  - Preset system (initial list and defaults)
  - Engine policy rules (`local_only`, `local_preferred`, `api_only`)
- Confirm output contract (MP4, 9:16, metadata)

**Explicitly forbidden in this phase:**
- Writing production code
- Optimizing model quality
- Adding non-essential features
- Implementing posting, analytics, or idea generation

**Exit criteria (must be true):**
- V1 scope is written and approved
- RenderSpec is defined and versioned
- Phase Map is accepted as authoritative

---

### PHASE-2: System Skeleton Implementation

**Objective:**  
Build the system’s *spine* so jobs flow end-to-end, even with placeholder outputs.

**Permitted work:**
- API and Orchestrator service
- Job lifecycle and state machine
- Job queue and worker loop
- Metadata persistence (database)
- Object storage wiring
- `/render` and `/render/{job_id}` endpoints
- Placeholder rendering or dummy clips

**Explicitly forbidden in this phase:**
- Real video generation
- GPU optimization
- Caption styling or visual polish
- Preset tuning

**Exit criteria (must be true):**
- Jobs can be submitted, queued, processed, and completed
- Job state persists across restarts
- System runs unattended with placeholder outputs

---

### PHASE-3: Engine Integration

**Objective:**  
Enable **real video generation** behind a stable engine abstraction.

**Permitted work:**
- Engine Adapter interface
- Local engine integration (e.g., ComfyUI workflows)
  - Image → Video (I2V)
  - Text → Video (T2V background)
- Segment-based rendering (2–4 second segments)
- Engine health checks
- Engine fallback logic (local → API)

**Explicitly forbidden in this phase:**
- Caption polish
- Brand styling
- Preset refinement
- Uploading or analytics

**Exit criteria (must be true):**
- System generates real video clips locally
- Segments render independently and reliably
- Engine fallback works without breaking upstream logic

---

### PHASE-4: Feature Completion

**Objective:**  
Turn raw clips into **usable, brand-safe videos**.

**Permitted work:**
- ffmpeg assembly pipeline:
  - Segment concatenation
  - Crossfade transitions
  - Scaling and cropping to 9:16
- Product/person overlay system
- Brand-safe enforcement rules
- Caption rendering (hook, beats, CTA)
- Audio mixing and loudness normalization
- Preset implementation and tuning
- Full duration support up to 60 seconds

**Explicitly forbidden in this phase:**
- Growth features
- Trend analysis
- Auto-posting
- Feedback loops or analytics

**Exit criteria (must be true):**
- Videos are postable without manual fixes
- Product identity remains stable
- Presets produce consistent output
- 60-second videos assemble correctly

---

### PHASE-5: Testing, Hardening & Launch Prep

**Objective:**  
Make the system **boringly reliable**.

**Permitted work:**
- Acceptance testing
- Failure injection and recovery testing
- Fallback verification
- Observability (logs, metrics)
- Performance tuning within defined constraints
- Documentation
- Dockerization and operational runbooks

**Explicitly forbidden in this phase:**
- Adding new features
- Expanding scope
- Refactoring for elegance or aesthetics

**Exit criteria (must be true):**
- ≥80% render success rate across 50+ jobs
- System survives restarts and partial failures
- System always returns a usable output
- V1 is tagged and frozen

---

### Enforcement Rule (Non-Negotiable)

> **No work may be performed from a later phase unless all exit criteria of the current phase are satisfied.**

This rule exists to:
- Prevent scope creep
- Prevent premature optimization
- Protect delivery velocity
- Keep humans and agents aligned

## Architecture Overview

Pytoon's architecture is designed in modular layers to handle each stage of the video generation process, from user input to final output. At a high level, the system can be viewed as a **pipeline of services and components** that transform an initial user request into a finished video file. Below is an overview of the main layers and components, followed by schematic diagrams:

- **1\. Input Handling & Request API:** Users interact with Pytoon via an API (or a UI that calls the API) to submit their assets and choices. The API layer handles uploading of images/videos, receiving text prompts, and selecting presets. It validates the inputs (e.g., correct file formats, prompt length limits, etc.) and creates a job request in the system. This layer is also responsible for providing a response or job ID to the user and later delivering the result (or a link to it). For asynchronous processing, the API will typically enqueue the request into a background job system and immediately return a job identifier so the user can poll or be notified when the video is ready.
- **2\. Intent Normalization (RenderSpec Generation):** Once a request is received, the system translates the **user's intent and inputs into a structured representation** called a **RenderSpec**. The RenderSpec is essentially a JSON schema or blueprint that describes exactly what video to create - including segments, media asset references, text overlays, timing, transitions, etc. This normalization abstracts away any free-form aspects of the input. For example, if the user selected the "Meme" archetype and provided an image plus a caption, the RenderSpec will codify that as: _segment 1 uses the image full-screen for X seconds, with big bold text at top saying the caption_. If multiple images and a "Hero" style are chosen, the spec might create one segment per image with certain animations. This layer may also apply some default rules (e.g., if total video length would exceed 60s, it might cap durations or require fewer segments). By the end of this step, we have a complete plan for the video that is independent of how it will be rendered. Think of RenderSpec as the "source code" for the video - a JSON that any compliant engine can interpret to produce the video.
- **3\. Pluggable Video Engine Interface:** Pytoon uses a **pluggable engine architecture** - there is an Engine Adapter that takes the RenderSpec and produces the video according to it. The engine can be one of two implementations:
- **Local Engine:** the default choice, which runs on the local infrastructure (e.g., using a library like MoviePy/FFmpeg or a custom rendering library). The local engine executes the RenderSpec by assembling the media clips, applying text overlays, transitions, and audio, all on the user's machine or server. This avoids external dependencies and can be faster (no upload/download of assets) and more secure (brand assets don't leave the environment).
- **Remote Engine (Cloud API):** a fallback engine which runs the rendering on a cloud service or remote server. The RenderSpec is sent to a **Video Rendering API** in the cloud (which could be a third-party service or our own hosted rendering server with powerful hardware). This engine will perform the same steps to compose the video and then return the final output file (or a URL to it). The remote engine is used when the local engine is unavailable or fails, or potentially based on a policy (for example, if the job is very complex or if the user specifically requests cloud rendering).

Both engines adhere to the same **Engine Contract Interface**: they accept the RenderSpec JSON and either return a video file (plus any metadata) or an error. This interface abstraction means new engines could be plugged in later (for instance, a specialized engine for a different platform or a more advanced cloud renderer) without changing the rest of the system. The Engine Adapter first tries the local engine and monitors its success; if the local process raises an error or exceeds certain resource/time limits, the adapter will seamlessly invoke the remote engine with the same spec. This local-first-then-cloud approach provides **redundancy and reliability**, as recommended in hybrid cloud design practices[\[4\]](https://sider.ai/blog/ai-tools/local-vs_cloud-ai-image-generation-which-one-won-t-crash-your-creative-flow#:~:text=,and%20get%20new%20features%20instantly) - if the cloud is unreachable, local is there; if the local environment "cries" under heavy load, the cloud can take over.

- **4\. Video Assembly & Post-Processing Layer:** As the engine (local or remote) works through the RenderSpec, it generates the video segments and overlays. In some designs, the engine will output the final video in one go; in others, it might produce intermediate pieces that need assembly. Pytoon's architecture allows for an **Assembly layer** to finalize the output. This involves:
- Combining rendered segments in sequence (ensuring transitions between segments are added, e.g. crossfade or slide between clips).
- Overlaying any persistent elements (for example, a watermark or logo that should appear throughout, or adding an end card).
- Injecting background audio track if required (e.g., adding music that plays across the whole video).
- Ensuring captions/subtitles are synced and burned-in if they are meant to be visible text. (If "open captions" approach is used, the text is part of the video frames as we render; if closed captions were desired, that could be separate metadata, but V1 likely uses burned-in text for simplicity and guaranteed cross-platform consistency).
- Final encoding: making sure the video file is encoded in the target format and performing any compression/optimizations (e.g., ensuring file size is reasonable for web upload).

In practice for V1, much of the assembly is handled by the engine itself via the instructions in RenderSpec. For example, the RenderSpec might say "apply fade transition between segment 1 and 2" - the engine (especially if using a timeline-based library or cloud service) can incorporate that. However, we delineate the Assembly layer conceptually to emphasize that the output must undergo these final steps to meet all requirements (captions, transitions, overlays, audio mixing). In a local pipeline, this might involve calling FFmpeg to concatenate clips and overlay images/text. In a remote pipeline, the service would do it internally. The architecture ensures that whether local or remote, the resulting video has all the pieces assembled correctly before marking the job complete.

- **5\. Output Delivery:** Once the video is fully rendered and assembled, the final file is stored and delivered. The system will typically place the video in a storage service (for example, in cloud storage like S3 or a database, or on disk) and provide the user with a URL or download. The Output layer also handles thumbnail generation (for convenience in UIs, a small preview image can be created from the first frame or a key frame of the video) and any cleanup (e.g., deleting large intermediate files if local, freeing resources). Finally, the user is notified (via API response, callback, or message) that their video is ready. If the architecture uses an asynchronous flow, the user might call a "get result" endpoint or receive a webhook when the status is complete.

To illustrate the architecture, below is a high-level flowchart of the Pytoon system and a sequence diagram for the end-to-end workflow:

flowchart TD  
A\[User Input Request&lt;br/&gt;(images, text, preset)\] --> B\[API & Input Handling&lt;br/&gt;(validate & enqueue job)\]  
B --> C\[RenderSpec Generator&lt;br/&gt;(normalize intent to JSON spec)\]  
C --> D{Engine Selector&lt;br/&gt;(Local vs Remote?)}  
D -- Local available --> E\[Local Video Engine&lt;br/&gt;(FFmpeg/MoviePy pipeline)\]  
D -- Fallback needed --> F\[Remote Video API&lt;br/&gt;(Cloud render service)\]  
E --> G\[Assembly & Post-Processing&lt;br/&gt;(transitions, captions, audio)\]  
F --> G  
G --> H\[Output Video Stored&lt;br/&gt;(storage & URL)\]  
H --> I\[User Receives Video&lt;br/&gt;(link or download)\]

**Figure: Pytoon Architecture Flow.** The user's request is turned into a RenderSpec, which is executed by either a local engine or a remote engine. The video is assembled and stored, then delivered back to the user.

To show the interactions between components in time order, consider the following sequence for a typical request:

sequenceDiagram  
participant User  
participant API  
participant Queue  
participant Worker  
participant EngineAdapter  
participant LocalEngine  
participant RemoteEngine  
participant Storage  
<br/>User->>API: 1. Submit video request (assets + options)  
API-->>User: 2. Acknowledge & return Job ID  
API->>Queue: 3. Enqueue Render Job (with RenderSpec inputs)  
Worker->>Queue: 4. Dequeue Job from Queue  
Worker->>EngineAdapter: 5. Invoke Video Engine Adapter with RenderSpec  
EngineAdapter->>LocalEngine: 6. Try Local Engine render  
Note over LocalEngine: LocalEngine processes segments,&lt;br/&gt;applies text & transitions&lt;br/&gt;via FFmpeg/MoviePy.  
LocalEngine-->>EngineAdapter: 7. Success? (or error if fails)  
alt Local render failed or not possible  
EngineAdapter->>RemoteEngine: 8. Call Remote API with RenderSpec  
RemoteEngine-->>EngineAdapter: 9. Remote renders video and returns file/URL  
end  
EngineAdapter-->>Worker: 10. Return final video result (file path or URL)  
Worker->>Storage: 11. Save video file (e.g., upload to S3)  
Worker->>API: 12. Update job status = "completed" (with output location)  
API-->>User: 13. Notify user (poll or callback) that video is ready (provide URL)  
User->>Storage: 14. Download or stream the finished video 🎉

**Figure: Sequence of operations in Pytoon.** The job flows from API to a background worker, through the engine adapter which may use local or remote rendering, then the result is stored and returned to the user. This asynchronous queued design improves reliability and scalability[\[7\]](https://www.inngest.com/blog/banger-video-rendering-pipeline#:~:text=We%20have%20a%20sub,and%20handles%20new%20progress%20events) - for instance, multiple workers can render videos in parallel, and heavy tasks don't block the user interface.

**Key architectural decisions & notes:**

- _Asynchronous Job Processing:_ Pytoon uses a **queue + worker** model to handle rendering tasks. This decouples the user request from the intensive video processing. As shown above, the API enqueues a job and returns immediately. A worker process (which can run on a server or separate thread pool) picks up the job to do the actual rendering. This design prevents timeouts on the user-facing side and allows scaling (we can run multiple workers for concurrent jobs). It also naturally fits a state machine approach for job status (Pending, Processing, Completed, Failed). Many real-world video pipelines use this pattern to manage long-running rendering tasks[\[7\]](https://www.inngest.com/blog/banger-video-rendering-pipeline#:~:text=We%20have%20a%20sub,and%20handles%20new%20progress%20events).
- _Engine Selection Logic:_ The Engine Selector (within the Engine Adapter) decides at runtime whether to use the local or remote engine. By default, it will always attempt local first for speed and to avoid unnecessary cloud usage. However, there are conditions where it might skip directly to remote: e.g., if brand-safe mode is off and the user specifically requested some effect only available via the cloud engine; or if the system detects the local environment doesn't have required capabilities (like no GPU for a GPU-intensive effect). In general though, **fallback is only invoked on failure or incapability**. If the local engine fails midway, the adapter will catch the error, log it, and then try the remote engine automatically. This failover is transparent to the user (other than possible extra render time).
- _Modularity:_ Each layer of the architecture is decoupled via clear interfaces. The API doesn't need to know how rendering works - it just hands off a job. The RenderSpec is the contract between the intent parsing and the engines. The engines can be swapped or upgraded without changing how the spec is produced (for example, we could integrate a new AI-driven video engine later by just writing a new adapter that reads the same spec). This modularity also aids testing (each part can be tested in isolation with mocked inputs/outputs).
- _Local Engine Implementation:_ For V1, the local engine will likely leverage proven open-source tools. **FFmpeg** will be a core component (directly or via libraries like MoviePy) for tasks like concatenating clips, resizing/cropping for 9:16, overlaying text and images, encoding video and audio. We might create the video by generating short clips per segment (with text overlays, etc.) and then concatenate them, or directly build a timeline with ffmpeg complex filters. The exact method will be chosen based on complexity and reliability. The local engine runs as part of the worker process.
- _Remote Engine Implementation:_ The remote option could be an internal service (essentially the same code as the local engine but running on a powerful machine or cluster), or a third-party Video API. For example, there are cloud services where you can send a JSON video template and assets, and it renders a video. Since we already define our own spec, an internal service that runs the same FFmpeg pipeline on the cloud is one approach. Alternatively, if using a third-party, we'd write a converter from our RenderSpec to whatever format that API expects. In V1, an acceptable approach is to stand up a simple cloud VM or container that can receive jobs (maybe via a lightweight API) and run the same rendering code - effectively "remote = someone else's computer running FFmpeg" - this ensures identical outputs and minimal spec translation issues. We will have to implement secure transfer of input assets to the remote (upload images or have them accessible via a link) and retrieval of the output.
- _Data Storage:_ The system will need to handle storing media files at multiple stages. Input assets might be uploaded and stored (e.g., in a temporary file store or object storage) so that the worker can access them (especially if using remote, inputs need to be accessible remotely). The final video will be stored in a persistent storage for delivery. We'll likely use cloud storage for outputs to easily share via URL. Job states could be stored in a database or in-memory cache that the API can query to update the user on progress.
- _Scalability & Future Growth:_ While V1 is scoped to single videos on request, the architecture is built to scale. We can add more workers for higher throughput, and even autoscale the remote engine cluster if needed for bursts. The decoupling via queue means the system can handle spikes by queueing and processing as capacity allows. Observability (discussed later) will help identify any bottlenecks (CPU, memory, I/O) and we can optimize accordingly. Because the video length is capped at 60s and typically the amount of media is not huge, processing is manageable on modern hardware. If we later allow longer or more complex videos, we might need to chunk processing or employ more advanced rendering techniques (but that's beyond V1).

In summary, the architecture of Pytoon balances **flexibility, reliability, and performance** by layering the system into clear functional components and leveraging proven design patterns (like background jobs and engine abstraction). The following sections will delve into the development plan and detailed requirements to implement this architecture.

## Project Management Plan

To deliver the Pytoon system, we will execute a phased development plan over approximately 5 weeks. Each phase has specific **milestones, deliverables, and exit criteria** to ensure we build the system iteratively and mitigate risks early. Below is the timeline and plan:

**Phase 1: Scope Alignment & Design Confirmation (Week 1)**  
\- _Objectives:_ Finalize the project scope, requirements, and technical approach before heavy coding begins. Align all stakeholders (product, engineering, design) on what V1 includes and what is out-of-scope. Set up the development environment and project repo.  
\- _Activities:_ - Review and adjust this master design document with the team, ensuring everyone agrees on the vision, features, and architecture. Resolve any ambiguities (e.g., exact behavior of brand-safe mode, which cloud service to use for fallback, etc.). - Break down high-level requirements into a product backlog (user stories or task tickets) for implementation. - Decide on technology stack details: e.g., confirm using Python with MoviePy/FFmpeg for local engine, identify a cloud environment for remote engine (such as AWS EC2 or a specific video API), and choose infrastructure for the queue (perhaps Redis+RQ or Celery for the worker queue, and a simple DB or Redis for state). - Set up the project repository, CI/CD pipeline skeleton if needed, and ensure all developers have the tools (FFmpeg installed, etc.). - Create a high-level test plan outline for acceptance tests (even if we'll flesh out later). - _Deliverables:_ Updated design & specs (the outcome of any changes from discussions), a project plan with tasks and assignments, and an initial code repository structure. Also, an agreed timeline (possibly adjusting this plan if needed) and identification of owners for each component. - _Exit Criteria:_ Stakeholders sign off that the scope and design are satisfactory. We have a clear list of tasks for Phase 2 and beyond. All required resources (servers, accounts) are provisioned or requested. Any critical risks identified are documented with mitigation plans. - _Risks:_ Misalignment on scope is the biggest risk here - if some stakeholders expected a feature that the development team isn't planning to build, it must be caught and resolved now. Another risk is underestimation of complexity (for instance, if the team discovers that implementing certain video effects is harder than thought, we might need to de-scope or find alternatives early). We mitigate this by thorough discussion and possibly quick feasibility spikes on tricky components in this phase.

**Phase 2: System Skeleton Implementation (Week 2)**  
\- _Objectives:_ Build the basic end-to-end skeleton of the system without the full functionality. This means establishing the main components (API, queue, worker, stub engine) and verifying the pipeline flows from one end to the other with minimal logic. Essentially, by end of this phase, we want to see a "Hello World" video or a dummy output being processed through the system. - _Activities:_ - Implement a simple API endpoint for submitting a video job. It should accept a minimal input (maybe a static test payload or a single image upload) and enqueue a job. - Set up the **job queue and worker** process. The worker will dequeue jobs and call a placeholder engine function. - Define the RenderSpec data structure (as a Python class or just manipulate JSON). Implement a very basic RenderSpec generator: e.g., take one image and one line of text input and produce a JSON with one segment. - Implement a stub **Engine Adapter** that simply logs the spec or returns a dummy video. For instance, for now it could ignore the spec and just create a 5-second blank video or a solid color frame as a placeholder, to simulate the output. - Have the worker save this dummy video to storage (maybe local filesystem for now) and mark job done. - Implement status tracking (even if just in memory): e.g., when job starts, mark as Processing; when done, mark as Completed; and provide an API to get job status/result. - End-to-end test: run the API call with a sample input and verify you can retrieve a result (even if it's a dummy video). - _Deliverables:_ Running skeleton of the system. The deliverable is code: an API service (could be a Flask/FastAPI or similar) with the job submission and status endpoints, a worker process that picks up jobs, and integration of these parts. Documentation updated if any changes occurred. Possibly also a simple demo showing the pipeline working (even with fake video) to the team. - _Exit Criteria:_ The team can demonstrate a full cycle: "submit job -> job gets processed -> result obtainable." Even if the result isn't the real video yet, the plumbing is in place. We should be confident that the architecture is viable (for example, that the queue and worker system works in our environment). No major blockers remain on connectivity between components. If any fundamental issues arise (say, difficulty integrating the queue, or the API can't easily pass large files), those should be identified and solutions planned now. - _Risks:_ At this stage, most risks are technical integration issues. For instance, ensuring the chosen queue technology works with binary data or large payloads (we might instead pass references/IDs). Another risk is underestimating the complexity of real video generation once we replace the stub - but since Phase 3 tackles that, it's okay as long as we're aware. If the skeleton shows any performance red flags (like very slow job pick-up or issues with concurrency), we will address those early.

**Phase 3: Engine Integration (Week 3)**  
\- _Objectives:_ Integrate the actual video rendering capabilities into the pipeline. By the end of this phase, the system should be capable of producing a real, simple video based on user input using the **local engine**. Also, the fallback remote engine should be set up, at least in a basic form (even if it's a dummy at first or a simplified version). Essentially, Phase 3 is about turning the stub engine into a functional one that uses input media and outputs an MP4. - _Activities:_ - Implement the **Local Video Engine** module: using either direct FFmpeg commands or a library like MoviePy. Start with simple abilities: e.g., take one image and one text and create a video of a few seconds with the image on screen and text overlaid. This will involve generating a video clip (perhaps by converting the image to a video stream duration X, and drawing text on it). Test this in isolation (e.g., verify the MP4 plays and the text is seen). - Expand the RenderSpec and its usage: ensure the spec includes all info needed (like text content, position, font, etc.). The engine module should parse the RenderSpec JSON and perform the corresponding editing steps. - Support multiple segments: implement concatenation of two or more clips with a basic transition. For example, if RenderSpec has 2 segments (two images), produce two video clips and then join them. Pick a default transition (say, a quick crossfade or a simple cut) and implement it via FFmpeg filters or by generating an intermediate combined clip. Verify the output video flows through segments correctly. - Integrate audio: if we plan to support background music, at least allow the pipeline to attach a given audio file to the video (mixing it with a lower volume if there's original video audio, etc.). Possibly just a simple approach: if an audio track is specified in spec, use ffmpeg to add it as the audio stream, truncated or looped to match video length. - **Remote Engine Setup:** Decide on how to simulate or implement the remote engine. If using our own cloud VM, set it up (or at least outline the process). Possibly create a dummy cloud function or an endpoint that the Engine Adapter can call - for now, it could just return the same result as local to simulate. The focus in Phase 3 is local engine, but we should lay groundwork for remote: e.g., a configuration in the Engine Adapter that if useRemote is forced (maybe via an env var for testing), it would call a stub remote endpoint. If feasible, maybe deploy a simple service that just returns a canned video. The real remote rendering integration might come in Phase 4 when we refine it. - Error handling: Have the local engine deliberately throw an error in some condition (maybe if a flag is set) to test the fallback path. Ensure the Engine Adapter catches it and then attempts remote. At this point, remote might be just a fake call, but at least confirm the logic path. - Continue to flesh out features: for example, implement brand-safe restrictions in engine if any (though brand-safe might mostly influence content, which we might implement in Phase 4 when adding all overlays). - _Deliverables:_ A functioning **video rendering core**. We should be able to input real assets and get a real video out that includes those assets in sequence. Deliverables include sample output videos for a couple of scenarios (e.g., one hero-style video with 2 images and a caption, one meme-style video with one image and top text). The code for local engine is completed or nearly completed. Basic documentation for the RenderSpec format (so front-end or other devs know what fields to provide) may be updated as well. - _Exit Criteria:_ The system can render a multi-segment video with text overlays locally. We have demonstrated at least one end-to-end real example to stakeholders for feedback. Any issues like video quality problems or performance concerns are noted and have solutions in progress. The remote fallback path is stubbed or ready to be plugged in. Phase 3 is done when we no longer rely on dummy outputs - the outputs are real videos, albeit perhaps without all polish (captions style, etc. can be refined later). - _Risks:_ Video processing always carries the risk of unforeseen technical challenges - maybe the library chosen has bugs or performance issues (e.g., MoviePy could be slow for HD video; we might need to pivot to direct FFmpeg commands). If we hit major snags (like difficulty getting text positioned correctly, or very long render times), we may need to adjust approach or allocate more time. Another risk is ensuring the videos work on various platforms (we should test a generated video on a phone to be sure orientation, encoding is correct). Also, if the team is not deeply experienced with video, there's a learning curve; we mitigate by focusing on a small working subset first (which we did). We should also keep an eye on file sizes and memory usage (e.g., generating a 60s HD video could use a lot of RAM if done naïvely). These risks can be mitigated by consulting online examples, perhaps reducing resolution for interim testing, and incremental optimization.

**Phase 4: Feature Completion - Assembly, Captions & Presets (Week 4)**  
\- _Objectives:_ Build out the remaining features and polish the video output to be production-ready. This includes implementing all assembly rules (subtitle/caption styling, transitions variety, overlay logic), supporting all input types robustly, and ensuring brand-safe mode enforcement. By end of Phase 4, Pytoon should produce final-quality videos that meet the requirements in all supported scenarios. Essentially, this is the phase where we go from a basic working video to a **fully-featured, branded output**. - _Activities:_ - **Captions & Text Styling:** Improve how text is rendered on video. Ensure the font, size, color, and placement are appropriate for each archetype. For example, Meme style might use a bold Impact-like font with outline, centered at top/bottom; Hero style might use the brand's font (if provided) in a dynamic way (maybe fade in/out). Implement text word-wrapping if needed (long prompts may need to break into two lines). Also implement safe margins so text isn't cut off on screen edges (respecting title-safe areas). - **Transitions & Animations:** Expand beyond a default transition. If presets include specific transition styles (e.g., a fast swipe vs. a crossfade), implement those options. This could involve using different FFmpeg filter or editing techniques. Also consider simple animations for images: for instance, a Ken Burns effect (pan/zoom on a static image to give it life) in Hero segments. We want the video to not be just static cuts unless intended - some subtle motion on images makes it more engaging. - **Overlay Graphics:** Implement adding the brand logo or other overlays if required by brand-safe mode. For example, in brand-safe mode, always put the company logo PNG at top-left of the frame throughout the video (or at least at the end). Or if the preset calls for a final card with company info, add that. This requires handling an extra image layer possibly. Use the RenderSpec to specify any global overlays. - **Audio Handling:** Refine audio. Make sure if an audio track is provided or chosen (perhaps we have a default background music track for certain templates), it is properly added. Implement fade-in/out of audio if needed at transitions, and volume normalization so background music doesn't overpower any speech (for V1, we might not have voiceover, but if videos have any inherent audio in video clips, balancing is needed). Ensure the final muxing of audio/video is correct length (mute or extend audio as needed). - **Brand-Safe Mode Enforcement:** Audit the pipeline to see what could violate brand safety. This might involve: limiting which font is used (in brand-safe, use only the brand's official font/colors), ignoring any user prompt text that might be off-brand (or applying a filter - though content moderation is probably manual for now, but brand-safe might mean we do _not_ auto-generate any content not provided; e.g., if user prompt is an open description, maybe brand-safe means we just display it verbatim rather than, say, calling some generative API to embellish it, which we're not doing anyway in V1). Essentially, brand-safe mode might reduce variability: stick to templates, fixed transitions, no random effects. We ensure that if the mode is on, the output is predictable and approved. - **Finalize Remote Engine Integration:** Now ensure the remote fallback truly works end-to-end. If we haven't deployed the remote service yet, do so. The remote engine should be capable of everything the local engine can do. If it's our own server, deploy the code there (with necessary libraries and possibly better hardware). If using a third-party API, implement the translation layer from RenderSpec to their format and test a real call. Do a forced-fallback test: simulate local failing and ensure the remote result comes back correctly and is delivered. This likely requires robust error handling around the remote call (e.g., if remote itself fails or times out, ensure we handle that failure gracefully). - **Internal Testing and QA:** Begin thorough testing with various combinations of inputs. Try edge cases: zero images (only text? maybe we require at least one image), maximum number of images (what if user adds 10 images? does it gracefully handle making each segment shorter to fit 60s?), extremely long text (ensure it either wraps or truncates appropriately), weird characters in text (encoding issues?), high-resolution images (ensure we downscale if needed to not blow up memory). - **Performance Tuning:** If rendering is too slow for certain cases, identify bottlenecks. Possibly enable multi-threading in FFmpeg or tune settings for faster, or reduce resolution if needed for performance (though 1080x1920 is target, we should try to maintain that, but maybe we can allow an option for 720p if needed as fallback). - Complete any missing pieces of the **RenderSpec JSON schema** and document them. By now, we should have the final spec fields defined, so ensure the documentation (or at least comments in code) list all fields and their meaning so that others (e.g., front-end or API integrators) know how to format requests. - _Deliverables:_ The fully functional Pytoon system with all V1 features. All code for features above will be delivered. We will produce a set of **sample videos** demonstrating each archetype and scenario, which serve as a visual deliverable for stakeholders to approve. For example, deliver a "hero style" sample, an "overlay style" sample, and a "meme style" sample, each with brand-safe mode on, to show that branding is correct (using perhaps a dummy brand name/logo for demonstration). Also deliver documentation: an updated README or developer guide on how to deploy and run the system, and an API guide for how to call it (including the JSON request structure). - _Exit Criteria:_ All planned functionalities are implemented and have been verified in internal testing. We should have a checklist of the initial requirements (from this document) and mark them off. Particularly, ensure: - A user can choose each archetype and the output reflects the correct style. - Brand-safe mode actually toggles the appropriate behaviors. - The system does not crash on any tested input combinations. - Both local and remote rendering paths yield comparable results (quality and content). - We have sign-off from the product stakeholder on the visual style (they might review the sample outputs and request minor tweaks; those should be resolved). - The RenderSpec format is finalized and agreed upon (no further changes that would break API). - We have test results for all acceptance tests (possibly initially run by developers, but ready for formal testing in Phase 5). - _Risks:_ By this phase's end, any lingering bugs or quality issues are the main risk. We must be careful that the rush to add features doesn't introduce instability. There's risk that some edge cases were overlooked (e.g., a certain combination of segments causing a sync issue). Also risk of scope creep - stakeholders might see the output and ask for extra polish (like "can we also add animated emoji?" etc.) which we must be disciplined about deferring beyond V1 if not critical. Another risk is timing - Phase 4 is a heavy workload; if it slips, we may infringe on Phase 5 time. To mitigate, we should prioritize critical features first (like ensuring core video correctness and brand elements), and possibly leave very fine-tuning (like slight stylistic improvements) as stretch goals if time permits.

**Phase 5: Testing, Hardening, and Launch Prep (Week 5)**  
\- _Objectives:_ In the final phase, we focus on **stability, performance, and acceptance testing**. We will conduct formal acceptance tests (from the next section) to validate the system end-to-end. We'll also improve reliability: add comprehensive error handling, logging, and any final performance tweaks. This phase is about ensuring that when we launch, the system runs smoothly and maintainably. - _Activities:_ - Run the full suite of **Acceptance Tests** (detailed later) in a production-like environment. This means possibly deploying the system on a staging server or running it on different machines to simulate real usage. Document the results of each test case (pass/fail) and fix any defects uncovered. - **Error Handling & Retries:** Go through the code and make sure all potential failure points are handled. For example, if FFmpeg returns a non-zero status, ensure we catch it and mark the job as failed (and trigger fallback if not done). If remote API fails, implement a retry logic (maybe retry once or twice with exponential backoff) since network issues can be transient. Ensure that even if a job ultimately fails, it doesn't crash the worker - it should catch the exception, mark status = Failed, and perhaps store an error message for debugging. - **Logging and Monitoring:** Integrate logging such that important events are recorded. The worker should log start and end of each job, which engine was used, any fallback occurrence, and any errors. The API should log incoming requests (with an ID) and results. Set up these logs to be easily accessible (maybe integrate with a logging service or at least to files). Additionally, add metrics collection if possible: e.g., count of videos rendered, average render time, number of failures, etc. If a monitoring system is available, we can push metrics to it or at least output them for later analysis. - **Performance Optimization:** Analyze the performance from testing. If certain types of videos are close to any unacceptable threshold (e.g., a 60s video with many segments taking too long to render), consider optimizations: e.g., parallelize some operations if possible (maybe render segments in parallel threads and then join, if CPU allows; or use lower precision on some filters, etc.). Ensure memory usage is not growing unbounded (no large leaks; clear temp files). - **Security and Compliance Check:** If relevant, ensure that the system respects privacy (for instance, if user assets are uploaded, they should be stored securely and not accessible publicly until the video is ready). If brand assets (like fonts or logos) were used, ensure licensing is okay. Basic security for the API (authentication, input sanitization to avoid any code injection through prompts). - Write a brief **operations guide** for launch: how to deploy, how to scale workers, how to run the system in production, and who to alert on call if something goes wrong. - Final review with stakeholders: present the results of testing and a few final sample videos. Make sure product and QA teams are satisfied that it meets the acceptance criteria. - _Deliverables:_ Test report (list of test cases with outcomes), final updated documentation (user guide or README, plus an ops guide if needed), and the release candidate version of the system ready for deployment. - _Exit Criteria:_ All acceptance tests pass or any exceptions are agreed upon (with plan to fix soon). There are **zero known critical bugs**. Minor issues that won't severely affect usage can be documented for a post-launch patch if necessary, but V1 should have no showstoppers. Performance is within acceptable range (e.g., if we set a goal "a 30s video renders in < 30s on our server", we verify that; if anything is slower, we either optimize or deem it acceptable if still reasonable). The team and stakeholders agree that the system is ready to launch. We have monitoring in place to catch any runtime issues after launch. - _Risks:_ Right before launch, the main risk is discovering a critical issue late. Our mitigation is to test as thoroughly as possible and involve QA early. Another risk is launch environment differences - something that worked in dev might break in production due to configuration differences. We should mitigate by staging tests. Also, there's always the risk of last-minute change requests; by having clear exit criteria and sign-off, we aim to avoid scope changes at the last second. In this phase, we should avoid making any major code changes except those needed to fix issues, to minimize the introduction of new bugs (code freeze mentality, aside from bug fixes).

Overall, this 5-phase plan ensures we start from a solid foundation, gradually build functionality, and finish with rigorous testing. Regular check-ins and mini-milestones at each phase will keep the project on track. If any phase starts to slip or encounter issues, we will communicate immediately and adjust scope or resources as needed - but the phased approach is designed to surface problems early (like in Phase 2 and 3) rather than at the end. Each phase has explicit exit criteria to move forward, ensuring quality is built-in at every step.

## Technical Developer Requirements

This section details the full developer specification for Pytoon V1. It covers all functional components and behaviors that the implementation must support, serving as a guide for the engineering team. It is essentially a deeper dive into what needs to be built (some of which has been introduced conceptually above). Developers should use this as a reference to ensure all features are accounted for and built to specification.

### Input Types and Video Archetypes

**Supported Input Types:** Pytoon must accept and handle the following inputs from users: - **Images:** Static image files (e.g., product photos in JPEG/PNG). The system should ideally handle various dimensions by cropping or padding to fit the vertical frame (9:16). If a landscape image is provided, the engine might blur it as background and overlay the image centered, or zoom into a key area - but at minimum it shouldn't produce black bars unless explicitly desired. If multiple images are provided, they can be used in sequence (each image potentially becoming a segment or combined depending on style). - **Short Video Clips:** (If in scope) Small video files (e.g., a 5-second product demo clip). The system should be able to incorporate a video clip as a segment. For example, one segment might be a user-provided video (perhaps trimmed to a certain length if needed) and then proceed to next segment. If including video clips, handle scaling to vertical (maybe crop center or add background for non-vertical videos). _Note:_ If implementing video clips is too complex for V1, we can restrict inputs to images only and document that; but ideally supporting small videos increases flexibility. - **Text Prompts:** Any text input that the user provides. This can be a tagline, a call-to-action, a description, or even a script. The system will primarily use this text for **on-screen captions or titles**. There might be multiple text prompts (like a title and a subtitle, or one per image). For V1, simplest approach: treat the entire prompt as one caption to overlay somewhere. More advanced (could be optional): if the prompt is long, maybe split it into key parts and spread across segments, or scroll it if needed. Also, if no text is provided, the system should still create a video (just without captions, relying on visuals). - **Presets / Archetype Selection:** The user can specify which **video archetype** or template to use (Hero, Overlay, Meme). This choice heavily influences the composition: - _Hero:_ The specification here is each segment is one media asset taking full frame. Use dynamic motion (zoom/pan) on images so they feel like video. Text, if any, might appear as an overlay caption in a stylish way (e.g., appearing in the middle or bottom of the screen) but not taking away from the full-screen imagery. Pacing: perhaps ~3-7 seconds per segment, focusing on one product at a time. - _Overlay:_ This can mean that the video might show multiple assets at once or composite layers. For example, one could have a background (could be a stock motion background or a solid color with graphic) and then overlay the product image cutout and text on it. Or overlay text on top of an existing video. Essentially, the architecture should allow stacking media layers. The developer needs to ensure the engine can handle transparent PNGs (for logos or product cutouts), chroma-key or masking if needed for overlay, etc. In V1, we might simplify by not doing actual cutouts (unless images come pre-cutout). Overlay could also simply mean picture-in-picture: e.g., show a clip and overlay text or another smaller image. - _Meme:_ The meme format typically means adding **a bold text bar at the top and/or bottom** of the video. Often with a black or white background behind the text for contrast. It mimics the popular meme style where top text is the setup and bottom text is the punchline. In Pytoon's context, the user prompt might directly be used as the meme text. If only one line of text, likely it's put at top in a black banner. If two parts, top and bottom. The developer should implement this styling: e.g., black bars (if desired) of a certain height, white Impact-font text centered, with a slight outline. Meme videos often also include subtitles for any spoken parts, but since we may not have audio dialogues, we focus on the big meme text. Also ensure the video content behind the text is positioned such that important visuals aren't covered by the banners (or we use letterboxing intentionally). - **Brand Assets:** Under brand-safe mode, additional inputs might include brand-specific assets or settings: - Logo image file (to overlay). - Brand colors or font (the system might be pre-configured with these, or a preset could encode that). - If a brand style guide says "always include a final slide with company website," that could be handled via a preset as well. - The developer should provide a mechanism to incorporate these, likely via configuration rather than user input each time. For example, brand-safe mode could automatically know to fetch the brand's logo from a known location and include it.

**Input Validation and Constraints:** The system should validate inputs early: - File type and size checks for images/videos (to prevent bizarre formats or extremely large files that could break processing). - Prompt length or character check (e.g., maybe limit to 100 characters to keep text concise, or else auto-truncate or split). - At least one media asset is required (we cannot create a video with no visual content). If the user only gives text and no image, perhaps the system can either reject it or use a fallback (like generate a solid background or stock image behind the text). For V1, simplest is to **require at least one image or video**; we can document that we don't support pure text videos yet unless we include a default background.

**Multiple Inputs:** If multiple images/videos are given, the system should by default treat them as separate segments in a sequence (especially for Hero or Meme style). The RenderSpec will list them in order. If the user has an intended order, we take that; if not, maybe as uploaded order or by some logic. We might also allow a configuration like "randomize segments" but not necessary for V1.

**Summary for Developers:** Implement robust parsing of the incoming request to assemble: - A list of media items (with their type, e.g. image or video, and possibly metadata like duration if a video). - The chosen archetype (or a default if none specified, say default to Hero). - The text prompt(s). - Flags like brandSafe. - Then pass these into the RenderSpec construction.

### Brand-Safe Mode and Fallback Logic

**Brand-Safe Mode:** When brandSafe=true in a request, the system should enforce a subset of behaviors aimed at ensuring nothing in the video could jeopardize brand integrity. Developers should implement the following under brand-safe mode: - Use only **pre-approved assets and styles**: e.g., use the brand's official font for any text (if provided, else use a neutral clean font), and brand colors for backgrounds or text (no wild colors). If no specific brand style is configured, then just stick to conservative styling (no flashing neon, etc.). - **Include brand identifiers:** For instance, always include the company logo watermark in a corner of the video (unless the user explicitly opts out for some reason). The watermark should be semi-transparent and not too intrusive, but visible enough to mark the content. - **No unreviewed content:** If the prompt text is user-generated and brand-safe mode is on, the system might want to be careful. In V1, we likely won't have AI content generation or external sources, so that's fine. But if in the future, if brand-safe was off, maybe the system could pull random GIFs or internet memes to include; brand-safe on would restrict to only the provided images or a controlled stock library. For V1, it suffices that we do not do anything "fancy" beyond the user's inputs and preset template when brandSafe is true. - **Safe transitions:** Avoid anything jarring or too "edgy". Stick to simple fades or cuts rather than, say, crazy glitch effects or extremely rapid strobe cuts that might be off-brand. - **Moderation:** While automated content moderation is out-of-scope, brand-safe mode could log or flag if the text prompt contains potentially problematic words (for someone to review). We won't implement a full filter in V1, but it's something to note for future.

In implementation, brand-safe mode will likely influence the RenderSpec generation: - The code that picks styles will choose the tame options. - It might add a "watermark segment" or overlay field for the logo. - It might override font choices to the brand font. Developers should ensure that a single flag can toggle these changes in how the spec is built or post-processed.

**Fallback Logic (Local vs Remote):** The system should implement the following logic for engine selection: - **Attempt Local First:** By default, every job should try to render locally. The Engine Adapter can call the local engine and perhaps set a timer or monitor resource usage. - **Detect Failure/Timeout:** If the local engine throws an exception or returns an error code (e.g., FFmpeg fails), catch it. Also, if a rendering process hangs or exceeds a certain time threshold (maybe we decide 2 minutes is the max for local attempt for a 60s video, just as a guard), then consider it a failure scenario. - **Switch to Remote:** When a failure is caught, log the reason (for debugging) and then invoke the remote engine. The same RenderSpec will be used for remote - so it's important that the spec doesn't include anything the remote cannot handle. If using our own identical code remotely, it's fine. If using a third-party, make sure the spec translation covers everything; if the third-party can't do something (like a certain transition), perhaps our spec generator should avoid that when brandSafe is on or when we know fallback might occur. - **Data Transfer for Remote:** The developer must implement packaging of input assets for the remote call. Likely, we will upload images to a cloud storage and include their URLs in the RenderSpec (instead of raw pixel data). The remote engine then can fetch them. Alternatively, encode images in base64 in JSON (not great for large files) or use direct file transfer (if remote is our own API, we might allow direct upload in the request). - **Remote Response:** The remote engine might take some time. We have two patterns: 1. **Synchronous API** - if the remote can process quickly, the call might block until done and return the video (or a link). Possibly feasible for short videos if remote is powerful. 2. **Asynchronous** - remote returns a job ID and we need to poll. Since we already have our own job system, we might prefer synchronous for simplicity in V1. Perhaps our worker will actually call remote and just wait (with a timeout) for it to complete, effectively delegating the work but still keeping control. - **Error Handling:** If the remote engine also fails or times out, then the job should ultimately be marked as failed. We won't try infinitely. But maybe one retry for remote could be done if it's a transient error. - **Notification:** It would be useful to have a flag in the job result like usedFallback: true/false so we can track how often fallback is used (for monitoring and possibly billing if cloud usage costs money). - **Configuration:** For testing, allow a configuration to force use remote (to test that path easily). Also allow disabling remote (if, say, the cloud service is down, we might temporarily run local-only and let jobs fail if local fails). - **Engine Interface:** Define a clear function or API: e.g., render_video(render_spec) -> result. For local, it might directly produce result = {"filePath": "...", "duration": X}; for remote, perhaps result = {"url": "https://.../video.mp4"}. Our code then needs to handle both (if remote gives URL, maybe download it or directly hand that URL to the user if it's stable). - **Testing fallback:** Include unit tests or integration tests where we simulate local engine raising an exception to ensure the remote path kicks in.

### Segment-Based Rendering and Timeline

Pytoon should use a **segment-based approach** to construct videos up to 60 seconds. This means the video is composed of one or more discrete segments (scenes), each segment having its own content, and they are stitched together in order. Developers need to implement handling for segments as follows: - The RenderSpec will include a list of segments (in chronological order). Each segment entry describes what to show during that portion of time. - Each segment can be of a specified duration (either default or based on content; e.g., 5 seconds per image unless overridden). The total sum of segment durations should not exceed 60s. The system could automatically adjust durations if, say, 10 segments of 7s each were requested (total 70s) - options include trimming each a bit or warning the user. For V1, we might just cap at some number of segments or shorten uniformly. - Segment content types: - **Image segment:** Show an image (maybe with some slight zoom or movement) for X seconds, possibly with text overlay. Possibly with background if image not filling the frame (like blurred copy of itself or colored bars). - **Video segment:** Play a video clip from start (or a specified in-out range) for X seconds. Could include overlay text too. Ensure seamless continuation if the next segment is another clip. - **Generated segment:** Could be something like a title card (e.g., an intro or outro with just text on a background). We might support a segment that has no user media but just some text (like "Summer Sale!" on a colored background for 3s as opening). The spec can allow a segment type "text-only" or similar with a background color or stock video. - **Transitions between segments:** Implement at least one transition effect between segments. This could be done by overlapping the end of one segment with start of next with a crossfade, or by a hard cut, or sliding transition. The RenderSpec should allow specifying a transition type per segment boundary (or a default if not specified). Developers can implement a limited set for V1: say, "cut", "crossfade", maybe "fade through black". Keep it simple to ensure no jarring technical issues. - Ensure that transitions do not extend the total video length beyond segments sum (e.g., if two segments of 5s with a 0.5s crossfade, the total might be 9.5s if done by overlap; we can consider that crossfade means they overlap so total stays 10s, or one can treat it as a half-second overlap effectively). - **Concurrent or Sequential Rendering:** One reason to define segments is possibly to render them separately and join, which can sometimes be easier (modular) and use less memory than doing everything in one FFmpeg go. The developer can implement it either way: - Possibly generate each segment as its own video file (with its internal overlays done), then use FFmpeg to concatenate with transitions (like using filters or transitional videos). This is easier for development but may have slight quality or complexity overhead. - Or use a single FFmpeg complex filter chain to do it all (more advanced, maybe not needed if first approach suffices within performance). - **Segment Synchronization:** If we had voiceover or multiple elements, we'd worry about timeline sync. For V1 mainly it's straightforward sequential, so not much parallel tracks except maybe background audio across segments. - **Upper limit of segments:** Not strictly given, but practically if each segment is very short (say 3s), 20 segments would make a 60s video. That's probably more than enough; typical use might be 3-10 segments. But code should not assume a fixed small number; loop through whatever in spec.

By structuring the logic around segments, it will be easier to modify and extend (like adding a new segment type in future). Developers should ensure the code iterates through spec segments and handles each appropriately in rendering.

### Engine Adapter and Selection Policy

The **Engine Adapter** is a critical piece that sits between the high-level application logic and the actual rendering implementations. Developer requirements for this component: - Provide a unified interface: e.g., EngineAdapter.render(spec: RenderSpec) -> OutputResult. This function will encapsulate the logic of choosing local vs remote. - **Local Engine Integration:** The adapter should call the local engine functions (perhaps directly calling a function or script that processes the spec). The local engine code may be in the same process or an external process (like spawning an ffmpeg command). In either case, capture success/failure. If using external processes, capture their exit code and logs for debugging. If using a library, handle exceptions. - **Remote Engine Integration:** The adapter should have a method to call remote. Possibly something like call_remote_api(spec). Implement it using an HTTP client if it's a web API or an SDK if provided. Ensure the spec is properly serialized to JSON and include all needed info (likely the remote service will need URLs to assets, so ensure by this point if spec has local file paths, convert them to accessible URLs or attach files). - **Selection Policy:** The default policy is try local then remote on failure. However, design the code to allow more complex policies in future: - Could have a configuration flag force_remote or force_local for debugging. - Possibly decide based on spec content: e.g., if spec indicates use of a feature only remote supports (if that arises). - Or based on environment: if the local machine doesn't meet some requirements (we could have a check at startup like "no ffmpeg present or insufficient GPU" then automatically default to remote). - But for V1, implement simplest: always attempt local first. - **Performance Consideration:** If in some cases we know local will be slow and remote is much faster, one might consider skipping local to save time. This could be an advanced logic (like if video length >30s and user on a low-power device, maybe remote first). Not implementing that without concrete data, but leaving a possibility. - **Contract with Engines:** Both engines should: - Produce the final video (including audio, etc.). The output should be essentially the same whether local or remote. - Provide progress updates optionally (not required for V1, but nice if remote can stream progress events or local can print progress, we might not expose to user yet, but logs can capture progress percentage). - The adapter does not deeply care how engine does it, but it does care about the outcome. - **Output Handling:** The adapter will return some representation of the output. We need to unify that: - Perhaps the adapter always returns a path or URL to the video file. If local, it could be a path on disk (which the worker could then upload to storage, or if the storage is a shared mount, leave it). - If remote returned a downloadable URL, the adapter might choose to download it to local storage so that subsequent steps (like generating thumbnail or storing in our bucket) can happen easily. Or we can directly treat that URL as the final link (if it's on a CDN). - For simplicity, maybe remote will upload to our storage as well (like remote engine could accept an S3 bucket path to put output). But that's an implementation detail - anyway, adapter should handle post-processing to present output uniformly. - **Logging & Metrics:** The adapter should log which engine was used. Perhaps return or set a flag as noted to record fallback usage. This helps in metrics to ensure our local engine success rate. - **Resilience:** Wrap calls in try/except. If local fails, catch exceptions and also kill any lingering processes if needed. Similarly, if remote call times out, handle that to avoid the worker hanging indefinitely.

In summary, developers should create the Engine Adapter as a robust module that can toggle between engines seamlessly. The selection policy is straightforward for now, but structure it so future policies can plug in. The goal is any part of the system calling EngineAdapter.render() doesn't need to worry about how or where the rendering happens, just that it gets a result or an error.

### Assembly Rules: Captions, Transitions, Overlays, Audio

This is the meat of the video composition - many of these have been conceptually covered, but here we list the specific rules and requirements for each element that must be assembled in the final video:

**Captions / Text Overlays:** - Pytoon must support rendering text on video frames. Developers should utilize either a library's text overlay function or FFmpeg's drawtext filter. - Captions can be segment-specific (e.g., a caption that only appears during one segment) or global (e.g., a watermark text that persists). - For user-provided prompt text, the typical behavior: - In _Hero/Overlay_ mode, if a tagline is provided, perhaps show it in the final segment or throughout as a small title. Alternatively, each image might have its own caption if multiple prompts provided. - In _Meme_ mode, the text is front and center as the meme content (top/bottom). So ensure formatting accordingly. - Multi-line text: ensure if text is long it can wrap or shrink. Possibly define a maximum font size and reduce if text is too long to fit in screen width. Or split into two lines automatically if space allows. - Font: Ideally, allow using a custom font (especially for brand). We may need to package a TTF file with the program or allow specifying a font name. Ensure the environment can find it (with drawtext you can specify fontfile). - Positioning: By archetype: - Hero: maybe centered or bottom-center for a subtitle-like text. Possibly animated (like fade in). - Overlay: possibly off to the side of the product image or centrally over a background. - Meme: top and/or bottom, full width. - Duration: A text overlay can either be for the entire segment or a portion. For simplicity, V1 can assume text appears at segment start and stays till segment end (if needed to go away sooner, that might be overkill unless we specifically want such effect). - Accessibility: Keep in mind caption readability - use high contrast (white text with black outline or shadow often works on any background). This also ties to the stat that captions greatly increase view-through[\[8\]](https://www.mediaplacepartners.com/short-form-video-success/#:~:text=Add%20Captions%3A%20A%20large%20chunk,to%20watch%20an%20entire%20video), so it's an important feature to do right. - Implement the caption rendering in the local engine pipeline. For remote, ensure the spec clearly indicates text, position, style so it does similarly.

**Transitions:** - The system should implement at least a basic crossfade transition by default between segments, as it often looks smooth. If no transition is specified in spec, define a default (maybe 0.5 second crossfade). - If the spec indicates a specific transition (we could support a few keywords: "cut" = no transition, instant jump; "fade" = crossfade; "slide" = a slide animation; "none" could be treated same as cut). - The developer can use FFmpeg filters like xfade for crossfade, or do a manual overlap. For a cut, nothing special needed, just concatenation. For slide, could be complex (maybe leave for future if too hard; or simulate by moving image within frame). - Ensure that implementing transitions doesn't require decoding entire videos into memory at once (maybe handle via ffmpeg filter chain). We may accept a brief overlap and trust FFmpeg to manage it. - If building segments separately: one method is to actually extend each segment by the half transition on both ends and then overlap. Could do: first segment output is 5.5s with 0.5s blank at end, second starts with 0.5s blank then content; then overlap. But simpler is using xfade filter in one ffmpeg command that takes two inputs. - Test transitions thoroughly to ensure no black flashes or stutters.

**Graphic Overlays (Images/Logos):** - Pytoon should allow layering an image on top of the video frames. Use cases: - Brand logo: small image at corner for entire video or for a specific segment. - Perhaps an overlay graphic like a sticker or border as part of a style (e.g., an overlay template might have a semi-transparent border overlay). - Developer needs to handle transparent PNGs (e.g., logos usually have transparency). Ensure that the library or ffmpeg command used keeps alpha channel and overlays correctly. - Positioning: likely allow specifying (x,y) coordinates relative to frame (like top-left, bottom-right etc., maybe with some margin). For brand watermark, bottom-right is common. The RenderSpec could have something like overlay: {image: "logo.png", position: "top-left", opacity: 0.8}. - Size: might need to resize overlay (like logo should not take up more than, say, 10% of screen width). Could define a default or get instructions from spec. - If multiple overlays in spec, support layering multiple (should be rare; maybe at most one logo plus perhaps another decoration). - Overlays might also be used in the "Overlay archetype" where the product image itself is an overlay: e.g., place product image on a background. In that scenario, we treat background as one layer (maybe a color fill or blurred version of image), and then overlay the product image (possibly resized) and text. - If doing this, the spec for overlay archetype could for each segment specify a background (if not provided, maybe a default like a gradient or color) and a foreground image position. - To implement, one might need to composite two images (background and product) in one frame. MoviePy could do composite of ImageClips. Or FFmpeg can overlay filter for static images. Because those won't have motion, we might also choose to add a slight zoom or slide to them to keep movement. - In summary, overlay logic requires implementing multi-layer composition, but for V1 if strapped, a simpler approach is: - For overlay archetype, maybe don't do fancy background, just use a solid color or the first image as full background at some opacity and then overlay second image. It might not be heavily used if not needed, but we want at least one example of overlay usage.

**Audio:** - The system should allow adding background music to the video. If the user provides an audio file or chooses from preset music, include it. If not, possibly use a default if the preset demands (some templates might have a default jingle). - Ensure audio length matches video. If audio is longer, cut it. If shorter and it's meant to play throughout, you can loop it (but avoid jarring cut-maybe loop seamlessly or just stop when video ends, either is fine). - If input video segments have their own audio (e.g., if user gave a video clip that has sound, and we also add background music), we should mix appropriately: likely reduce background volume when main audio is present. But for simplicity, we might say we won't include user video audio in V1 (or we'll include it but since they are short product vids possibly without meaningful sound, we might just override with music). - Ensure the final video has exactly one audio track with correct encoding. (Using AAC codec, stereo, 44.1 or 48 kHz). - Fade-out the audio at end of video for a nice finish (prevent abrupt cut-off of music). - If brand-safe is on, ensure audio is royalty-free or licensed properly (we might only use a small set of safe tracks). Possibly, brand-safe could default to no audio or a generic corporate tune to avoid any issues.

**RenderSpec JSON Schema Fields:**

Developers will implement and maintain a JSON schema for the RenderSpec. This is crucial for both the system's internal communication and for any service interface (like if front-end were to send a RenderSpec directly). Key fields to include (and to be documented for use) are:

- **version** (optional): Schema version number or identifier. Could be useful for future changes.
- **archetype**: The chosen video archetype/style (e.g., "hero", "overlay", "meme"). This can influence defaults for other fields if not explicitly set.
- **brandSafe**: Boolean flag indicating brand-safe mode. The spec generation code will set this from user input, and the engine can also read it if needed to enforce any rendering differences.
- **segments**: An **array of segment objects**, each describing a part of the video. Each segment object may have the following fields:
- type: Type of segment content, e.g., "image", "video", "text".
- media (or more specific, like imageSrc, videoSrc): The source of media. Could be a file path or URL. For images/videos provided by user, this might be a local path that the engine knows how to access (or a pre-signed URL if remote needs it).
- duration: Duration of this segment in seconds (e.g., 5.0). Some segments like a provided video might also have a natural length; then duration could either match that or be a trimmed length.
- text: Any text caption to display during this segment. If absent, no text on this segment (unless a global text applies).
- textStyle: (optional) properties like position ("top", "bottom", "center" or even pixel coordinates), font name, color, size, etc. If not provided, the default style based on archetype is used. For meme segments, perhaps textStyle would default to top big white/black border.
- transition: (optional) transition after this segment into the next. Could be an enum like "fade", "cut", etc. If not present, use default or whatever the next segment might specify as incoming transition. (Alternatively, transition can be seen as a property of the boundary between segments rather than attached to one, but attaching to the segment or to a separate array is an implementation choice; developers can decide what's easier.)
- background: (optional, for overlay segments or text-only segments) could specify a background color ("#RRGGBB" or so) or background image to use.
- audio (optional, per segment): Typically we'll handle audio globally, but conceivably a segment might have a specific audio (like a voiceover clip for that segment).
- **audioTrack**: (optional, global) Background music file to use for the whole video. This could be a filename or a keyword for a stock track.
- **resolution**: Output resolution - e.g., width and height. Default 1080x1920 for vertical full HD. If we ever wanted lower, it could be specified.
- **frameRate**: Possibly allow specifying frame rate (default likely 30 fps or 24 fps; using 30 fps is safe for smooth motion).
- **outputFormat**: Container/codec info if needed (e.g., "mp4" container, video codec h264, audio codec aac - these are basically fixed for our use, but field might exist for completeness).
- **overlays**: (optional, global) A list of overlay elements that persist across the video or appear at certain times. For example,
- an entry could be { "image": "logo.png", "position": "top-left", "start": 0, "end": 60, "opacity": 0.5 } to overlay a logo for entire duration.
- If we want an end card, it could be an overlay that starts at video end minus 3 seconds, etc. But perhaps easier is to just make end card a segment.
- **metadata**: (optional) Could include things like title of video, or user ID, etc., not directly for rendering but for logging or referencing. Not critical for rendering itself.

The **developer must ensure** the RenderSpec is fully expressive enough for V1 needs. That means any effect we want in the video must be representable in these fields. Conversely, if something is in the spec, the engine should handle it or at least ignore gracefully if not crucial (for example, if textStyle.font is given as a font name we don't have, perhaps fall back to default font but continue).

Internally, we might not always expose the full JSON to outside - the API could accept simpler parameters and our system constructs the spec. But documenting the spec is still useful for clarity and for any internal or external engine interface.

An example (for clarity) of a simple RenderSpec might be:

{  
"archetype": "hero",  
"brandSafe": true,  
"segments": \[  
{  
"type": "image",  
"media": "uploads/product1.jpg",  
"duration": 5,  
"text": "New Collection",  
"textStyle": { "position": "center", "color": "#FFFFFF" },  
"transition": "fade"  
},  
{  
"type": "image",  
"media": "uploads/product2.jpg",  
"duration": 5,  
"text": "Available Now",  
"textStyle": { "position": "center", "color": "#FFFFFF" },  
"transition": "fade"  
}  
\],  
"audioTrack": "music/uplifting.mp3",  
"resolution": {"width": 1080, "height": 1920},  
"outputFormat": {"format": "mp4", "videoCodec": "h264", "audioCodec": "aac"},  
"overlays": \[  
{ "image": "assets/brandLogo.png", "position": "top-right", "start": 0, "end": 10 }  
\]  
}

This example would mean: two image segments (each 5s) with crossfade transitions, center white text overlay on each, background music, and a brand logo in the top-right throughout the 10s video. The developer's engine code would need to implement all aspects accordingly.

### Job State Machine and System Components

The system components include the API server, the job queue, worker processes, and storage. Together they implement a **job state machine** as follows:

**States:** - **Pending:** When a job is first created (user submits a request, and after initial validation), it goes into a "Pending" state in the queue. It's waiting to be processed. We might also mark it as queued in a database or simply consider anything not yet started as pending. - **Processing:** When a worker picks up the job, it transitions to Processing. At this point, we may update a status field (in a DB or in-memory map keyed by job ID) to indicate work is in progress. We may also note the start time. - **Completed:** If the rendering finishes successfully and the output is stored, the job becomes Completed. We record the completion time, and store the result location (e.g., file URL). - **Failed:** If something goes irrecoverably wrong (both local and remote engines failed, or an input was bad that we only caught inside processing, etc.), then the job is marked Failed. We should store an error message or code for debugging (not necessarily exposed to user except maybe a generic "Sorry, it failed" message). Possibly we have sub-states like "error" vs "stalled" (as seen in the Inngest example[\[9\]](https://www.inngest.com/blog/banger-video-rendering-pipeline#:~:text=,) where they handle stalled vs error), but for V1 we can treat any failure as final. - (Optional) **Cancelled:** If we ever implement job cancellation (user decides to cancel mid-way), that could be another state. Not required for V1 unless we think it's needed.

The developer should implement tracking of these states. This could be done with a simple dictionary in the API server for small scale, but better to use a persistent store so that if the server restarts, we don't lose statuses. A lightweight approach is to use the queue system's features (e.g., some queues allow status tracking, or use a Redis hash to store status).

**Components interaction:** - **API Server:** Responsible for creating the job (and thus initial state Pending) and for providing an endpoint to query status. So the API will need to: - On job submission: generate a unique job ID (could be UUID or an increment). Store initial job info (like inputs, maybe in spec form) somewhere if needed for debugging. Enqueue the job (depending on queue tech, e.g., push to Redis list). Mark status pending (maybe implicit if in queue, but we might explicitly store it). - Return the job ID to the client immediately. - Provide GET /job/{id} or similar to fetch status. That will check if the job is still pending, processing, completed, or failed. If completed, it can also return the result URL. If failed, possibly an error message. - Possibly provide a direct download endpoint for the output video or just give the URL (if using a cloud URL, client can directly access it if public). - **Job Queue:** We likely use an external system (like Redis) or internal structure to queue jobs for workers. The developer should ensure that the queue is configured to handle the potentially large data (though we pass mostly references, not the media itself). - **Worker:** This is a process (or set of processes) that continuously poll the queue for new jobs. When it gets one: - Update the status to Processing (this might be done by removing from queue and updating a status store, or the act of taking it from queue means it's processing). - Execute the RenderSpec creation (if not already done in API). Actually, question: do we generate RenderSpec in API or in Worker? - Possibly we generate it in API because that's part of "interpreting user input". But heavy tasks like analyzing media perhaps better in worker. However, generating spec is quick (some JSON assembly), so doing it in API is fine. But if API is stateless, maybe easier in worker. Either works. The design earlier suggested API calling a RenderSpec generator. We can also move that logic into worker as first step after dequeuing. Either way, ensure it's done exactly once. - Call the Engine Adapter to perform rendering. While doing so, it may update progress if we have hooks (not mandatory, but e.g., in remote we might receive progress events like 50% done - we could update a progress field). - Once engine returns, handle output (store file, etc.), then update job status to Completed and include result reference. - If an exception happens, catch it, update status to Failed with error info. Possibly attempt fallback (that's within engine adapter usually, so if that fails as well, then it's a true fail). - We might consider a retry mechanism at job level: e.g., if something fails due to a transient error not handled by fallback, maybe automatically retry the whole job once. But careful with duplicate output. Probably skip in V1, and rely on user to resubmit if needed. - **Storage:** The developer must integrate storing outputs in a location accessible to users. Likely usage: if we have a web server, maybe store in a static files directory or upload to an S3 bucket and get a public link. Implementation depends on environment. For local dev, saving to disk and returning a path is okay. For production, probably a cloud bucket with a known URL structure. - If storing in cloud, credentials need to be handled. Possibly the remote engine could directly store to the same bucket, to avoid an extra download-upload. - Also, consider cleaning up old files if needed (maybe out of scope for V1, but don't want unlimited accumulation of videos). - **Scalability Considerations:** With the queue/worker design, adding more workers can handle more concurrent jobs. Developers should ensure the system can handle at least a modest concurrency (like 5-10 jobs at once) without issues. That means be mindful of race conditions on shared resources (e.g., if all workers write to same temp directory, unique temp file names needed). - **State Updates Atomicity:** If using a DB or Redis, ensure operations updating state are thread-safe or atomic (most likely fine if each job ID is handled by one worker at a time). - **Notification (optional):** We rely on polling or manual checking by user. If wanting to be fancy, could implement a webhook or email on completion, but that's not required now.

By implementing this state machine, we can provide feedback to users about their video job, which is important for UX (they know if it's done or still processing). It also helps operations to see if a lot of jobs are stuck, etc.

### Engine Selection Policy and Contract Interface

We touched on engine selection in the adapter section, but to reiterate and add any specifics:

**Engine Contract Interface:** - Both LocalEngine and RemoteEngine (and any future engines) should adhere to a common interface. If we abstract it in code, maybe have an abstract base class VideoEngine with a method like render(spec: RenderSpec) -> Output. - The contract: - Input: a RenderSpec object (or JSON). The engine implementation is responsible for interpreting it correctly. - Output on success: some identifiable output. Could be a path to a file (if engine runs in same environment and writes to disk), or a binary blob, or a URL. We standardize it by, say, always outputting to a known directory and returning the path. - On failure: throw an exception or return an error object with details. - The engine should not itself do further steps outside its scope - e.g., it doesn't notify user or update DB; it just renders. - If an engine implementation needs to use external resources (like remote) internally, it should handle those and still conform to final output.

**Engine Capabilities/Policy:** - Document what the local engine can or cannot do: - E.g., if no GPU, it might struggle with heavy filters, but we ensure our spec doesn't demand something impossible. Local can do basically all the things we need via CPU albeit slower. - If there were any differences (e.g., remote might have a library for fancy animated text that local doesn't), we would note that and the selection policy might choose remote if that feature is requested. For V1, assume parity in features. - **Performance triggers:** Maybe in the future, if we detect a job will take extremely long locally (like a 60s video with 10 segments might be borderline, but probably still fine on CPU in a couple minutes), we could auto-route to remote. Not implementing now but keep architecture open to that idea. - **Cost consideration:** If the cloud engine costs money per render, we might treat fallback as a last resort and not an equal alternative. So we wouldn't want to use remote unless necessary. This is indeed our approach (fallback only). - **Testing both paths:** Ensure that both local and remote produce consistent output. There could be minor differences (e.g., fonts might render slightly differently on different platforms). Keep those minimal to avoid confusion. If needed, constrain ourselves to common denominator capabilities.

**API/Engine Versioning:** If the remote engine is a third-party, we might be constrained by their API changes. But since we plan possibly to use our own, not an issue. If third-party, ensure our contract mapping is correct and handle any differences (like maybe they can't do overlapping images - we might flatten something for them).

**Examples:** - If local fails on a certain video due to memory (maybe too many high-res images), remote with bigger memory can succeed. We should handle that scenario gracefully - it might not throw a clean error, possibly the process just crashes if out-of-memory. We need to detect such failure. One idea: maybe monitor the memory usage or catch system exceptions (hard, but if FFmpeg returns error code). - Another scenario: Suppose remote is slower - user might wonder why their job is taking longer. Perhaps in status we don't distinguish, but logs might show "fell back to remote for job X".

In code, the selection might look like:

try:  
local_engine.render(spec)  
result = {"path": "/out/videos/job123.mp4"}  
except Exception as e:  
log("Local engine failed: " + str(e))  
result = remote_engine.render(spec) # possibly also in try/except

It can be that simple. But if remote also fails, then propagate failure up.

**Conclusion:** The engine selection policy for V1 is straightforward: **local-first, cloud-second**. The interface between our system and either engine is the RenderSpec and a video file result. Developers should ensure minimal differences in handling, so the rest of the system doesn't need to know which one was used (except perhaps for logging metrics).

With all the above requirements defined, developers have a comprehensive blueprint of what to build: from how to parse inputs, how to generate and use the RenderSpec, how to implement rendering with all necessary video features, and how to orchestrate jobs through the system reliably.

## Acceptance Tests and Exit Criteria

To validate that the Pytoon system meets its goals and is ready for launch, we define a set of **acceptance tests** and criteria. These tests should be executed in an environment close to production, and each must pass to consider V1 successful. Additionally, we outline what metrics and monitoring should be in place (observability) and the final exit criteria for project completion.

### Acceptance Test Cases

Each test case describes an input scenario and the expected outcome. The development and QA teams will run these to ensure the system behaves as intended:

- **Single Image, Hero Style Test:**  
    _Input:_ One product image (portrait orientation), a short text prompt "Introducing our new product!", Hero archetype, brandSafe on.  
    _Expected Output:_ A video of ~5 seconds. The image fills the frame (no black bars - possibly slight crop or background fill if needed). The text "Introducing our new product!" appears centrally or bottom as a nice overlay in brand font/color. If brandSafe, the company logo should be visible (e.g., small in corner). Smooth fade-in or out as it ends, perhaps. Verify the video is 9:16 and not stretched. The text should be spelled correctly and clearly visible.  
    _Criteria:_ Video plays successfully on a phone, text is readable, image quality is good (not pixelated), and the logo is present (for brandSafe). No unexpected content.
- **Multiple Images Sequence, Hero Style:**  
    _Input:_ Three product images (mixed orientations), no text prompt, Hero archetype, brandSafe off (maybe the brand is okay with a bit flashier style).  
    _Expected Output:_ A video of ~9-12 seconds (3-4s per image segment by default). Each image is shown in full screen one after the other. Since no text prompt, perhaps the system either adds no text or could auto-add simple numbering or product name if available (but we didn't specify that, so likely just images). Transitions: should have a default crossfade (check that between each image we see a smooth transition, not a jump). Because brandSafe is off, maybe the transitions could be more dynamic (if we implemented something like a quick zoom or flashy effect, it could show here). No logo watermark in this one since brandSafe off (unless user explicitly wanted one).  
    _Criteria:_ All 3 images appear in the video in the correct order. The video length is <= 15s. The aspect ratio is correct and images are not distorted (some cropping is acceptable but important content should remain visible). Transitions are present and look smooth. No crashes during creation. Check file metadata to ensure resolution is 1080x1920 and playable.
- **Meme Style Video Test:**  
    _Input:_ One image (or short video clip) of a product being used in a funny way, text prompt "When you realize it's on sale", archetype Meme, brandSafe may be either (brandSafe on should still allow meme format, as it can be on-brand humor).  
    _Expected Output:_ A meme-style video ~5-6 seconds. The top of the frame has a black bar with white bold text "When you realize it's on sale". If we expected bottom text and we only gave one line, maybe just top text is fine. If the image was provided, it should be sized so that the text bar doesn't cover important parts (perhaps letterboxed slightly to create space for text). If a video clip was input, it should play with caption on it, possibly muted (meme vids often play silently with captions). The final result should feel like a typical internet meme video. Brand logo might or might not be present depending on brandSafe; if it is, ensure it doesn't clash with the meme text.  
    _Criteria:_ The caption text is correctly displayed (spelling and position). The stylistic elements (font, background bar) match standard meme conventions. The visual content is visible and comedic effect maintained. The output file meets format specs. Also, the system should handle this request without errors (text length fits in one line ideally or appropriately wrapped).
- **Overlay Style with Background and Foreground:**  
    _Input:_ Archetype Overlay, brandSafe on. Provide one product image and possibly select a preset background (or if we have none, we expect it to use a default background color or stock video). Text prompt "50% OFF!".  
    _Expected Output:_ Perhaps a 5-8 second video where the background is, say, a blurred version of the product image or a brand-colored screen with some simple animation, and the product image is overlaid (maybe scaled and centrally placed) with the text "50% OFF!" flashing or appearing next to it. The brand's logo might appear as well due to brandSafe. This tests that our layering works.  
    _Criteria:_ The product image is indeed overlaid on a distinct background (not just full screen like hero). The text "50% OFF!" is prominently shown (this is like an ad). The overall look is aesthetically pleasing and clearly conveys the message. No parts of the image are cut off weirdly, and the text is readable (not blending into background thanks to color choice or outline). The presence of brand styling (fonts/colors) should be verified according to input config.
- **Maximum Length Video Test:**  
    _Input:_ A combination of inputs that pushes towards the 60s limit. For example, 6 images with a short caption for each, Hero style, brandSafe off, maybe an audio track provided.  
    _Expected Output:_ A video that is about 60 seconds long (maybe 6 segments of ~10s each). It should not exceed 60s. If our system auto-adjusts durations, verify it did so (maybe each segment ended up slightly shorter). All 6 images should appear, each with its caption text on it. Background music should play throughout and end when video ends.  
    _Criteria:_ Total duration <= 60s. All assets included. The video doesn't show any sync issues (like music not aligned or text lingering too long). Rendering such a length should still succeed within a reasonable time (maybe a couple minutes at most). No memory crashes.
- **Engine Fallback (Failure Simulation) Test:**  
    _Input:_ (This is a test scenario rather than a user scenario.) We configure or simulate a condition that causes the local engine to fail - for example, we temporarily remove/rename the ffmpeg binary or deliberately insert a bug to throw an error. Then submit a standard job (e.g., 1 image, some text).  
    _Expected Output:_ The system should detect the local failure and automatically use the remote engine. The remote engine returns a valid video. The final user result is still correct (video file as expected). There might be a slight delay vs normal, but it should still complete. We expect a log or indicator that fallback happened (for internal verification). The user should not receive a failure, they get success albeit maybe after a bit more wait.  
    _Criteria:_ The job finishes successfully via remote. On the user side, it's indistinguishable except for possibly a longer processing time. Internally we confirm that the local error was caught and not propagated as a crash. The status maybe stayed "Processing" until remote finished, then "Completed". No manual intervention needed - fallback was automatic.
- **Error Handling Test (Bad Input):**  
    _Input:_ An intentionally bad input, e.g., a corrupt image file or an unsupported format file (say a PDF instead of image).  
    _Expected Output:_ The system should detect this either at upload or when rendering starts, and handle it gracefully. The job should end up in Failed state with an appropriate error message logged (and possibly a user-friendly message via API like "Unsupported file format").  
    _Criteria:_ The system does not hang or crash. It properly flags the job as failed. The user is informed of failure in a reasonable way (for example, the GET status endpoint shows status "failed" and maybe a generic error note). This test ensures robustness against bad input.
- **Concurrent Jobs Test:**  
    _Setup:_ Fire off multiple jobs in quick succession (say 5 jobs, with varying content).  
    _Expected Outcome:_ All jobs get processed, perhaps in parallel if multiple workers. The system should handle the load without deadlock or malfunction. Each job should produce correct output.  
    _Criteria:_ All 5 videos are completed and correct. The order doesn't matter, but ensure one job's processing doesn't interfere with another (e.g., check that outputs are distinct files, no mix-up of content). Also monitor memory/CPU during concurrency to ensure it's within limits (not an explicit pass/fail, but informational).

After running these tests, we should also perform a **cross-platform check**: e.g., take some output videos and upload them to Instagram or view on different devices to ensure compatibility (this is more a sanity check that our encoding is baseline H.264 which is universally accepted).

### Observability and Logging

For a successful launch, we need to have good observability in place from day one: - **Logging:** The system should produce logs that can help diagnose issues. Key events to log: - Job received (with job ID and brief details like number of assets). - Start and end of a job processing in worker, including which engine was used. - Any fallback trigger ("Local engine failed, switching to remote for job X"). - Any errors encountered, with stack trace or error code from ffmpeg, etc. - Warnings for any non-fatal issues (e.g., "Image too large, downscaled from 4K to 1080p"). These logs should be stored in a way accessible to developers (file or console if container logs, etc.). No sensitive personal data in logs, of course. - **Metrics:** We will collect the following metrics: - **Success Rate:** number of completed videos vs number of failed. This should ideally be ~100% for normal usage. If failures occur, we investigate. We set an internal SLO like "95%+ jobs succeed". - **Fallback Usage:** count how many jobs used remote fallback. If this number is high, it means local engine had issues often - we want to monitor that and improve local or see why (maybe users with huge videos). - **Render Duration:** measure time from job start to completion. Compute average, p95, etc. This helps identify performance improvements or regressions. We might aim for, say, average under 30s for typical video. - **Queue Time:** if applicable, measure time spent in queue before a worker picked it up (should be near zero unless system is busy). - **System Resource Utilization:** not exactly a metric we output to user, but we should monitor CPU, memory usage of the worker over time under load to catch any leaks or need for scaling. - Possibly metric for most used archetype (just for product insight). - **Alerting:** While perhaps not needed at launch immediately, we could set up simple alerts (like if failure rate in last hour > X% send an alert to team). Or if average render time spikes, etc. For now, developers should at least manually watch metrics after launch.

## Acceptance Criteria Index

This section defines the **authoritative, testable acceptance criteria** for the Pytoon Video Generation System.  
All claims of “done,” “complete,” or “working” MUST map directly to one or more Acceptance Criteria (AC).

No feature, phase, or release may be considered complete unless **all applicable ACs are satisfied and verifiable**.

This index is intentionally checklist-based to enable autonomous QA, development, and agent execution.

---

### Core Output & Format

**AC-001**  
System produces a valid MP4 video encoded with:
- Video: H.264  
- Audio: AAC (if audio is present)  
- Resolution: 1080x1920  
- Aspect ratio: 9:16  

**AC-002**  
Generated video duration **never exceeds 60 seconds**.  
Tolerance: ±0.5 seconds maximum.

**AC-003**  
System produces a thumbnail image (PNG or JPG) derived from the final video.

---

### RenderSpec & Intent Integrity

**AC-004**  
RenderSpec fully describes the intended video output and contains:
- Archetype
- Duration
- Assets
- Segment plan
- Caption plan
- Audio plan
- Constraints  
without embedding engine-specific or model-specific logic.

**AC-005**  
RenderSpec is versioned and persisted with each job for reproducibility.

---

### Engine Execution & Fallbacks

**AC-006**  
Local rendering engine successfully generates video clips for supported simple cases:
- Product overlay
- Short meme/text video
- Basic I2V hero shot

**AC-007**  
Engine policy is enforced correctly:
- `local_only` → no API usage
- `local_preferred` → API fallback on local failure
- `api_only` → API used regardless of local availability

**AC-008**  
Remote engine fallback activates automatically when:
- Local engine errors
- Local engine is unhealthy
- Local engine times out  
without breaking the job lifecycle.

---

### Brand-Safe Enforcement

**AC-009**  
When `brand_safe = true`:
- Product/person assets are not regenerated unless explicitly allowed
- Overlays use original assets
- Fonts, transitions, and motion intensity are restricted to preset-safe values

**AC-010**  
Brand-safe mode prevents visible distortion of:
- Product labels
- Logos
- Text embedded in product imagery

---

### Segmentation & Assembly

**AC-011**  
Videos longer than a single segment are rendered as multiple independent segments and assembled correctly.

**AC-012**  
Segment assembly produces a continuous final video using:
- Concatenation
- Optional crossfades (if enabled by preset)
- Consistent visual and caption styling across segments

---

### Captions & Audio

**AC-013**  
Captions are burned into the video and include:
- Hook
- One or more beats
- CTA (if defined by preset)

**AC-014**  
Captions remain within defined safe zones for 9:16 mobile viewing.

**AC-015**  
If audio is present:
- Music loops or trims to match video duration
- Voice (if present) ducks background music
- Final audio is loudness-normalized

---

### Job Lifecycle & Reliability

**AC-016**  
End-to-end job lifecycle functions correctly:
- Submit → Queue → Render → Assemble → Retrieve

**AC-017**  
Job status transitions are persisted and recoverable after:
- Service restart
- Worker restart
- Partial failure

**AC-018**  
On render failure, system returns a **usable fallback output** rather than no output.

---

### Observability & Proof

**AC-019**  
System records structured logs including:
- Job ID
- Segment ID
- Engine used
- Render duration
- Failure reason (if any)

**AC-020**  
System exposes metrics sufficient to calculate:
- Render success rate
- Engine fallback rate
- Average segment render time

---

### Release Gate

**AC-021**  
V1 release requires:
- ≥80% success rate across at least 50 jobs
- Zero manual intervention during rendering
- All applicable acceptance criteria above passing

---

### Enforcement Rule

> A feature, phase, or release is **not complete** unless it can be explicitly mapped to one or more Acceptance Criteria in this index.

This index is the system’s **“prove it” gate**.  
Narrative explanations do not satisfy acceptance. Only verifiable criteria do.


### Final Exit Criteria

Finally, before declaring the project complete and ready for V1 release, ensure the following exit criteria are met: - **All acceptance tests passed:** as detailed above. Any test that failed has been addressed with code changes and re-tested until pass. - **Stakeholder sign-off:** Product managers and designers (if involved) have reviewed the output videos and are satisfied that the system meets the vision (correct styles, brand compliance, etc.). Any UI or integration aspects (if Pytoon is integrated into a larger app) are also verified. - **Documentation completed:** All relevant documentation is ready. This includes user-facing documentation (how to use the API or tool), and internal docs (RenderSpec schema, how to deploy/operate the system, etc.). The master document (this one) can be updated to reflect the final state if some details changed during implementation. - **No critical bugs open:** our issue tracker should show zero high-severity bugs. Minor known issues, if any, are communicated and scheduled for fix in a patch or next version. - **Performance acceptable:** Through testing, we confirm the system can handle the expected load (e.g., if expecting maybe 10 videos per hour, we tested with equal or higher and it was fine). If any performance bottleneck was found, we have either resolved it or clearly documented the limitation and perhaps added it to known limitations if it's acceptable (e.g., "rendering more than 50s of video on a very low-end machine may take longer than X minutes" might be noted). - **Security check:** Ensure any user data (images/videos) are stored securely and there's no unintended exposure. For instance, if providing public URLs for output, they should be unguessable or time-limited if sensitive. BrandSafe content likely not sensitive but just to check. - **Recovery & fallback tested:** Not only engine fallback, but also system resilience: if a worker crashes mid-job, does the job get re-queued or stuck? Ideally, the queue system could re-queue if a worker dies. We should test a scenario of killing a worker and ensure the job isn't lost. This might depend on queue tech. At least we document what happens (maybe job will remain pending and get picked by another worker). - **Launch plan ready:** We have decided on the deployment for production (which server, how many workers, etc.), and it's prepared. Team is ready to support the launch.

When all the above is satisfied, we can confidently proceed to launch Pytoon V1. The system will have undergone rigorous testing and should deliver on its promise of compiling mixed media into engaging short-form videos automatically. Post-launch, we will closely monitor the metrics and user feedback, but the groundwork laid out ensures we have a robust, maintainable foundation for future enhancements (like possibly adding AI content generation, more templates, longer videos, etc.).

**In conclusion,** this master document provides a unified view of the Pytoon Video Generation System - from the high-level product vision down to the nitty-gritty technical requirements and tests. Following this plan will enable cross-functional stakeholders to stay aligned and developers to implement systematically. By the end of the project, Pytoon will be capable of quickly turning images and text into dynamic vertical videos, helping brands ride the wave of short-form video content with ease and confidence.

The combination of a clear vision, a solid architecture (with modern approaches like local/cloud hybrid rendering[\[4\]](https://sider.ai/blog/ai-tools/local-vs_cloud-ai-image-generation-which-one-won-t-crash-your-creative-flow#:~:text=,and%20get%20new%20features%20instantly) and background job processing[\[7\]](https://www.inngest.com/blog/banger-video-rendering-pipeline#:~:text=We%20have%20a%20sub,and%20handles%20new%20progress%20events)), a structured development plan, detailed specifications, and thorough testing will set up Pytoon V1 as a success. All teams should now have a shared understanding of the system, and we can move forward into implementation with this document as our guiding blueprint.

[\[1\]](https://www.creativewebconceptsusa.com/why-create-short-form-video-content-and-best-tips/#:~:text=Why%20create%20short,of%20consumption%20on%20mobile%20devices) [\[3\]](https://www.creativewebconceptsusa.com/why-create-short-form-video-content-and-best-tips/#:~:text=The%20statistics%20are%20clear,This%20matches%20the%20preference) Why Create Short-Form Video Content and Best Tips - Social Media Management, PR Media, Publishing, Creative Digital Marketing

<https://www.creativewebconceptsusa.com/why-create-short-form-video-content-and-best-tips/>

[\[2\]](https://www.mediaplacepartners.com/short-form-video-success/#:~:text=TikTok) [\[5\]](https://www.mediaplacepartners.com/short-form-video-success/#:~:text=If%20your%20business%20has%20poured,to%20other%20top%20marketing%20trends) [\[6\]](https://www.mediaplacepartners.com/short-form-video-success/#:~:text=perfect%20for%20short,to%20other%20top%20marketing%20trends) [\[8\]](https://www.mediaplacepartners.com/short-form-video-success/#:~:text=Add%20Captions%3A%20A%20large%20chunk,to%20watch%20an%20entire%20video) The Playbook for Short-Form Video Success | MPP

<https://www.mediaplacepartners.com/short-form-video-success/>

[\[4\]](https://sider.ai/blog/ai-tools/local-vs_cloud-ai-image-generation-which-one-won-t-crash-your-creative-flow#:~:text=,and%20get%20new%20features%20instantly) Local vs. Cloud AI Image Generation: Which One Won't Crash Your Creative Flow?

<https://sider.ai/blog/ai-tools/local-vs_cloud-ai-image-generation-which-one-won-t-crash-your-creative-flow>

[\[7\]](https://www.inngest.com/blog/banger-video-rendering-pipeline#:~:text=We%20have%20a%20sub,and%20handles%20new%20progress%20events) [\[9\]](https://www.inngest.com/blog/banger-video-rendering-pipeline#:~:text=,) A Deep Dive into a Video Rendering Pipeline - Inngest Blog

<https://www.inngest.com/blog/banger-video-rendering-pipeline>
# Scene Planner -- V2 Interface and Behavior Specification

**Ticket:** P1-05  
**Acceptance Criteria:** V2-AC-001  
**Source:** pytoon-v2.md "Scene Planner" (line 62), "Scene Planning and Segmentation" (lines 131-137)

---

## 1. Overview

The Scene Planner (also called the "Director AI") is the module that interprets user input and generates a valid Scene Graph JSON. It is the creative decision-maker for video structure: how many scenes, what each scene contains, and how scenes connect narratively.

---

## 2. Interface Contract

### 2.1 Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `media_files` | `list[str]` | No | File paths/URIs to uploaded product images or video assets. |
| `prompt` | `str` | No | Text prompt, script, or screenplay-style input. |
| `preset_id` | `str` | Yes | Preset identifier that provides style defaults, caption styling, and motion profiles. |
| `brand_safe` | `bool` | Yes | Whether brand-safe constraints apply (restricts transitions, engine prompts, overlays). |
| `target_duration_seconds` | `int` | No | Target total video duration (default: 15s, max: 60s). |
| `voiceover_duration_ms` | `int` | No | Duration of provided voiceover audio. If present, voice length drives scene timing. |
| `engine_preference` | `str` | No | User-selected engine override (e.g., "runway", "luma", "multi_engine"). |

### 2.2 Output

A validated `SceneGraph` JSON conforming to `schemas/scene_graph_v2.json` (schema version 2.0).

### 2.3 Error Behavior

If the planner cannot produce a valid scene graph from the inputs, it raises a `PlanningError` with a descriptive message. The caller handles this (e.g., by falling back to a preset template scene graph).

---

## 3. Planning Strategies

### 3.1 Strategy 1: Heuristic Planner

The default, non-AI planner. Deterministic and fast.

**Algorithm:**

1. **Check for `<SHOT>` markers:** If the prompt contains `<SHOT 1>`, `<SHOT 2>`, etc., split the prompt at those markers. Each `<SHOT>` block becomes one scene. Parse any embedded style hints (e.g., camera motion keywords) from the shot text.

2. **Sentence splitting:** If no `<SHOT>` markers, split the prompt by sentences (using punctuation: `.`, `!`, `?`). Each sentence becomes one scene.

3. **Image-to-scene mapping:** Assign one image per scene, cycling if there are more scenes than images. If there are more images than sentences, create additional scenes for the extra images (with generic captions from the preset or empty captions).

4. **Duration assignment:**
   - If `voiceover_duration_ms` is provided: distribute duration proportionally across scenes based on sentence length (character count as proxy for speech duration).
   - If no voiceover: default 5 seconds per scene.
   - Cap total at `target_duration_seconds` (max 60s). If sum exceeds target, reduce each scene proportionally.

5. **Media type assignment:**
   - Scenes with a product image: `media.type = "image"`, `media.asset = <image_path>`, `media.effect = "ken_burns_zoom"`.
   - Scenes without an image but with a prompt: `media.type = "video"`, `media.engine = <engine_preference or null>`, `media.prompt = <sentence>`.
   - Scenes with both image and prompt: `media.type = "image"` (image takes priority; the prompt becomes the caption).

6. **Style assignment:** Attach style/mood from the preset to all scenes. If the prompt contains mood keywords (e.g., "cinematic", "warm"), override the preset mood.

7. **Transition assignment:** Default `"fade"` between scenes. Last scene has no transition. If `brand_safe = true`, restrict to `"cut"` and `"fade"` only.

8. **Caption assignment:** Each sentence becomes the scene's caption text.

9. **Global audio:** Set `globalAudio.voiceScript` to the full prompt text (joined sentences). Set `globalAudio.backgroundMusic` from preset default.

### 3.2 Strategy 2: AI Planner (Future -- V2.1+)

Reserved for LLM-assisted scene decomposition. Not implemented in initial V2 release but the interface supports it. The AI planner would:
- Send the prompt to an LLM with a system prompt describing the Scene Graph schema.
- Receive a structured JSON response.
- Validate the response against the schema.
- Fall back to the heuristic planner if LLM output is invalid.

---

## 4. Handling Special Cases

### 4.1 Multiple Images, No Prompt

- Create one scene per image with default captions from the preset template.
- Default duration: 5s per scene (or distribute target_duration equally).
- `media.type = "image"` for all scenes.

### 4.2 Prompt Only, No Images

- Split prompt into sentences → one scene per sentence.
- All scenes use `media.type = "video"` with engine assignment.
- The prompt sentences become both the AI generation prompt and the caption.

### 4.3 No Prompt, No Images (Minimal Input)

- Fall back to preset template scene graph.
- Use a generic 3-scene structure from the preset: intro → feature → CTA.
- Fill with default captions and placeholder prompts from the preset.

### 4.4 Screenplay-Style Input with `<SHOT>` Markers

```
<SHOT 1> Close-up of the product, warm studio lighting, slow zoom in.
<SHOT 2> Product in use outdoors, cinematic golden hour, person walking.
<SHOT 3> Logo reveal, upbeat, fade to white.
```

Each `<SHOT>` block becomes an explicit scene. The planner respects these as hard scene boundaries and parses any embedded keywords (camera motion, lighting, mood) into the scene's `style` object.

### 4.5 Voice Length Drives Timing

When a voiceover file is provided:
1. Total video duration = voiceover duration (capped at 60s).
2. Scene durations are proportional to the speech segment lengths mapped to each scene.
3. If voiceover is shorter than minimum viable video (e.g., < 3s), pad with a brief intro/outro scene.

---

## 5. Continuity and Reuse

The planner ensures continuity across scenes:
- If the same product image appears in multiple scenes, the same `media.asset` reference is used.
- Overlay references (e.g., logo) are consistent across scenes.
- The `style` object is consistent unless explicitly varied by the prompt.

---

## 6. Contract with Timeline Orchestrator

The Scene Planner produces the Scene Graph. The Timeline Orchestrator consumes it:
- The orchestrator trusts scene order from the `scenes[]` array.
- The orchestrator trusts scene durations as initial estimates but may adjust them (proportional reduction if total > 60s).
- The orchestrator trusts `transition` values per scene.
- The orchestrator does NOT modify scene content (media, captions, overlays) -- only timing.

---

## 7. Module Location

`pytoon/scene_graph/planner.py`

---

## 8. Test Requirements

Unit tests must cover:
1. Prompt with 3 sentences → 3 scenes with correct captions.
2. Prompt with `<SHOT>` markers → scenes matching shot count.
3. 5 images, no prompt → 5 image scenes with default durations.
4. No prompt, no images → preset template fallback.
5. Voiceover duration drives scene timing.
6. Duration sum exceeds 60s → proportional reduction.
7. Brand-safe mode restricts transitions.
8. Engine preference propagates to `media.engine`.

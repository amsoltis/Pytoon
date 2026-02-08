"""Timeline Orchestrator — converts a SceneGraph into a Timeline.

The orchestrator lays out scenes sequentially, inserts transitions,
creates video / caption / audio track entries, and validates the
result against the 60-second limit.

Ticket: P2-04
Acceptance Criteria: V2-AC-005, V2-AC-014, V2-AC-020
"""

from __future__ import annotations

from pytoon.log import get_logger
from pytoon.scene_graph.models import SceneGraph, TransitionType
from pytoon.timeline.models import (
    AudioTrack,
    AudioTrackType,
    CaptionTrack,
    Timeline,
    TimelineEntry,
    Tracks,
    TransitionSpec,
    VideoTrack,
)

logger = get_logger(__name__)

# Defaults
DEFAULT_TRANSITION_MS = 500
MAX_TOTAL_MS = 60_000


def build_timeline(
    scene_graph: SceneGraph,
    *,
    default_transition_ms: int = DEFAULT_TRANSITION_MS,
) -> Timeline:
    """Build a Timeline from a validated SceneGraph.

    Algorithm:
    1. Lay out scenes sequentially with their durations.
    2. Insert transition entries (crossfade borrows from both scenes).
    3. Create video track entries for each scene's media.
    4. Create placeholder caption track entries from scene captions.
    5. Create audio track entries if globalAudio is present.
    6. Validate total ≤ 60s; proportionally reduce if over.
    """
    scenes = scene_graph.scenes

    # --- Step 1 & 2: Sequential layout with transition overlap ---------------
    entries: list[TimelineEntry] = []
    cursor = 0  # current time position in ms

    for i, scene in enumerate(scenes):
        is_last = i == len(scenes) - 1

        # Determine transition for this scene
        transition_spec: TransitionSpec | None = None
        overlap = 0

        if not is_last:
            t_type = scene.transition
            t_dur = default_transition_ms if t_type != TransitionType.CUT else 0
            transition_spec = TransitionSpec(type=t_type, duration=t_dur)
            overlap = t_dur

        entry = TimelineEntry(
            sceneId=scene.id,
            start=cursor,
            end=cursor + scene.duration,
            transition=transition_spec,
        )
        entries.append(entry)

        # Advance cursor; crossfade borrows overlap from both scenes
        cursor += scene.duration - overlap

    total_duration = entries[-1].end if entries else 0

    # --- Step 6: Enforce ≤ 60s -----------------------------------------------
    if total_duration > MAX_TOTAL_MS:
        entries, total_duration = _proportional_reduce(
            entries, scenes, default_transition_ms,
        )

    # --- Step 3: Video tracks ------------------------------------------------
    video_tracks: list[VideoTrack] = []
    for scene in scenes:
        video_tracks.append(VideoTrack(
            sceneId=scene.id,
            asset=scene.media.asset,
            effect=scene.media.effect.value if scene.media.effect else None,
            layer=0,
        ))
        # Add overlay tracks
        for overlay in scene.overlays:
            video_tracks.append(VideoTrack(
                sceneId=scene.id,
                asset=overlay.asset,
                layer=1,
            ))

    # --- Step 4: Caption tracks ----------------------------------------------
    caption_tracks: list[CaptionTrack] = []
    entry_map = {e.sceneId: e for e in entries}

    for scene in scenes:
        if scene.caption:
            te = entry_map[scene.id]
            # Place caption with small lead-in and before scene end
            cap_start = te.start + 200  # 200ms after scene start
            cap_end = te.end - 200      # 200ms before scene end
            if cap_end <= cap_start:
                cap_end = te.end
                cap_start = te.start
            caption_tracks.append(CaptionTrack(
                text=scene.caption,
                start=cap_start,
                end=cap_end,
                sceneId=scene.id,
            ))

    # --- Step 5: Audio tracks (placeholder) -----------------------------------
    audio_tracks: list[AudioTrack] = []

    if scene_graph.globalAudio.voiceScript or scene_graph.globalAudio.voiceFile:
        audio_tracks.append(AudioTrack(
            type=AudioTrackType.VOICEOVER,
            file=scene_graph.globalAudio.voiceFile,
            start=0,
            end=total_duration,
        ))

    if scene_graph.globalAudio.backgroundMusic:
        audio_tracks.append(AudioTrack(
            type=AudioTrackType.MUSIC,
            file=scene_graph.globalAudio.backgroundMusic,
            start=0,
            end=total_duration,
            volume=0.5,
        ))

    # --- Build Timeline -------------------------------------------------------
    timeline = Timeline(
        version="2.0",
        totalDuration=total_duration,
        timeline=entries,
        tracks=Tracks(
            video=video_tracks,
            audio=audio_tracks,
            captions=caption_tracks,
        ),
    )

    logger.info(
        "timeline_built",
        scene_count=len(entries),
        total_duration_ms=total_duration,
        caption_count=len(caption_tracks),
    )
    return timeline


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _proportional_reduce(
    entries: list[TimelineEntry],
    scenes: list,
    default_transition_ms: int,
) -> tuple[list[TimelineEntry], int]:
    """Reduce scene durations proportionally so total ≤ 60s."""
    # Compute current total (accounting for overlaps)
    original_total = entries[-1].end
    ratio = MAX_TOTAL_MS / original_total

    # Rebuild with reduced durations
    new_entries: list[TimelineEntry] = []
    cursor = 0

    for i, scene in enumerate(scenes):
        is_last = i == len(scenes) - 1
        new_duration = max(1000, int(scene.duration * ratio))

        transition_spec: TransitionSpec | None = None
        overlap = 0

        if not is_last:
            t_type = scene.transition
            t_dur = default_transition_ms if t_type != TransitionType.CUT else 0
            # Ensure overlap doesn't exceed scene duration
            t_dur = min(t_dur, new_duration // 2)
            transition_spec = TransitionSpec(type=t_type, duration=t_dur)
            overlap = t_dur

        new_entries.append(TimelineEntry(
            sceneId=scene.id,
            start=cursor,
            end=cursor + new_duration,
            transition=transition_spec,
        ))
        cursor += new_duration - overlap

    new_total = new_entries[-1].end if new_entries else 0

    logger.warning(
        "timeline_duration_reduced",
        original_ms=original_total,
        reduced_ms=new_total,
    )
    return new_entries, new_total

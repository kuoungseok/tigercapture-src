from __future__ import annotations

from app.timeline_model import VideoClip, VideoTrack
from app.timeline_nle_visual_overlay import (
    CLIP_ANCHOR_CUE_SCHEMA,
    DRAG_PREVIEW_VISUAL_SCHEMA,
    ROLE_FOCUS_CUE_SCHEMA,
    build_clip_anchor_cue,
    build_drag_preview_visual_cue,
    build_role_focus_cue,
)


def _clip(clip_id: int, start: int = 0, duration: int = 1000) -> VideoClip:
    return VideoClip(
        id=clip_id,
        source_path=f"clip_{clip_id}.mp4",
        source_duration_ms=duration,
        timeline_in_ms=start,
        source_in_ms=0,
        source_out_ms=duration,
    )


def test_clip_anchor_cue_marks_connected_clip_for_timeline_paint() -> None:
    parent = _clip(10, 0, 1000)
    child = _clip(20, 1200, 800)
    child.connected_parent_track_id = 1
    child.connected_parent_clip_id = 10
    child.connected_offset_ms = 1200
    child.clip_role = "b-roll"
    track = VideoTrack(id=2, clips=[child])

    cue = build_clip_anchor_cue(track, child, selected=True)

    assert cue["schema"] == CLIP_ANCHOR_CUE_SCHEMA
    assert cue["ready"] is True
    assert cue["connected"] is True
    assert cue["selected"] is True
    assert cue["clip_id"] == 20
    assert cue["role"] == "b_roll"
    assert cue["anchor_ms"] == 1200
    assert cue["connected_offset_ms"] == 1200


def test_clip_anchor_cue_skips_plain_primary_clip() -> None:
    clip = _clip(10)
    track = VideoTrack(id=1, clips=[clip])

    cue = build_clip_anchor_cue(track, clip)

    assert cue == {"schema": CLIP_ANCHOR_CUE_SCHEMA, "ready": False}


def test_drag_preview_visual_cue_normalizes_tones_for_painter() -> None:
    snap = build_drag_preview_visual_cue("snap")
    blocked = build_drag_preview_visual_cue("collision")
    move = build_drag_preview_visual_cue("")

    assert snap["schema"] == DRAG_PREVIEW_VISUAL_SCHEMA
    assert snap["tone"] == "snap"
    assert snap["label"] == "SNAP"
    assert snap["field_lines"] == 3
    assert snap["hatch"] is False
    assert blocked["tone"] == "blocked"
    assert blocked["hatch"] is True
    assert move["tone"] == "move"
    assert move["field_lines"] == 0


def test_role_focus_cue_dims_non_matching_roles() -> None:
    primary = _clip(10)
    overlay = _clip(11)
    overlay.clip_role = "overlay"
    track = VideoTrack(id=1, clips=[primary, overlay])

    primary_cue = build_role_focus_cue(track, primary, "overlay")
    overlay_cue = build_role_focus_cue(track, overlay, "overlay")
    clear_cue = build_role_focus_cue(track, primary, "")

    assert primary_cue["schema"] == ROLE_FOCUS_CUE_SCHEMA
    assert primary_cue["dimmed"] is True
    assert overlay_cue["dimmed"] is False
    assert clear_cue["ready"] is False

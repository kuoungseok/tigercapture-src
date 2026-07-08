from __future__ import annotations

from app.nle_visual_feedback import (
    build_connected_anchor_overlay,
    build_magnetic_drag_preview,
    build_role_lane_filter_model,
)
from app.timeline_model import VideoClip, VideoTrack


def _clip(clip_id: int, start: int, duration: int = 1000) -> VideoClip:
    return VideoClip(
        id=clip_id,
        source_path=f"clip_{clip_id}.mp4",
        source_duration_ms=duration,
        timeline_in_ms=start,
        source_in_ms=0,
        source_out_ms=duration,
    )


def test_connected_anchor_overlay_returns_ui_ready_lines() -> None:
    parent = _clip(10, 1000, 2000)
    child = _clip(20, 1500, 800)
    child.connected_parent_track_id = 1
    child.connected_parent_clip_id = 10
    child.connected_offset_ms = 500
    child.clip_role = "b-roll"

    overlay = build_connected_anchor_overlay(
        [VideoTrack(id=1, clips=[parent]), VideoTrack(id=2, clips=[child])],
        selected_track_id=2,
        selected_clip_id=20,
    )

    assert overlay["schema"] == "tigerstudio.nle.connected_anchor_overlay.v1"
    assert overlay["anchor_count"] == 1
    anchor = overlay["anchors"][0]
    assert anchor["state"] == "ok"
    assert anchor["selected"] is True
    assert anchor["anchor_ms"] == 1500
    assert anchor["parent"]["lane_index"] == 0
    assert anchor["child"]["lane_index"] == 1


def test_role_lane_filter_model_exposes_visible_and_dimmed_clip_sets() -> None:
    primary = _clip(10, 0, 2000)
    overlay = _clip(20, 500, 1000)
    overlay.clip_role = "overlay"
    overlay.connected_parent_track_id = 1
    overlay.connected_parent_clip_id = 10

    model = build_role_lane_filter_model(
        [VideoTrack(id=1, clips=[primary]), VideoTrack(id=2, clips=[overlay])],
        focused_role="overlay",
    )

    assert model["schema"] == "tigerstudio.nle.role_lane_filter_model.v1"
    assert model["focused_role"] == "overlay"
    assert model["visible_clips"] == [{"track_id": 2, "clip_id": 20}]
    assert {"track_id": 1, "clip_id": 10} in model["hidden_clips"]
    overlay_filter = next(row for row in model["filters"] if row["role"] == "overlay")
    assert overlay_filter["focused"] is True
    primary_filter = next(row for row in model["filters"] if row["role"] == "primary")
    assert primary_filter["dimmed"] is True


def test_magnetic_drag_preview_snaps_and_reports_push_feedback() -> None:
    track = VideoTrack(id=1, clips=[_clip(10, 0), _clip(11, 1200), _clip(12, 2600)])

    preview = build_magnetic_drag_preview(
        [track],
        track_id=1,
        clip_id=12,
        target_start_ms=980,
        snap_threshold_ms=80,
    )

    assert preview["schema"] == "tigerstudio.nle.magnetic_drag_preview.v1"
    assert preview["ready"] is True
    assert preview["snap"]["applied"] is True
    assert preview["snapped_start_ms"] == 1000
    assert preview["feedback"] == "push"
    target = next(row for row in preview["placements"] if row["target"])
    pushed = next(row for row in preview["placements"] if row["clip_id"] == 11)
    assert target["adjusted_start_ms"] == 1000
    assert pushed["pushed_by_magnetic"] is True
    assert pushed["adjusted_start_ms"] == 2000


def test_nle_visual_feedback_actions_are_registered_and_read_only() -> None:
    from app.actions import build_default_action_registry

    class Owner:
        pass

    owner = Owner()
    owner._tracks = [VideoTrack(id=1, clips=[_clip(10, 0), _clip(11, 1400)])]
    registry = build_default_action_registry(owner)

    overlay = registry.execute("timeline.connected_clips.anchor_overlay").to_dict()
    filters = registry.execute("timeline.role_lanes.filter_model", {"focused_role": "primary"}).to_dict()
    preview = registry.execute(
        "timeline.magnetic_storyline.drag_preview",
        {"track_id": 1, "clip_id": 11, "target_start_ms": 980},
    ).to_dict()

    assert overlay["ok"] is True
    assert filters["ok"] is True
    assert filters["result"]["focused_role"] == "primary"
    assert preview["ok"] is True
    assert preview["result"]["ready"] is True
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1400]

from __future__ import annotations

from app.nle_connected_clips import (
    build_connected_clip_status,
    build_role_color_status,
    connected_clip_contract_evidence,
    role_color_for,
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


def test_connected_clip_status_reports_parent_offset_health() -> None:
    parent = _clip(10, 1000, 2000)
    child = _clip(20, 1400, 800)
    child.connected_parent_track_id = 1
    child.connected_parent_clip_id = 10
    child.connected_offset_ms = 400
    child.clip_role = "b-roll"

    status = build_connected_clip_status(
        [
            VideoTrack(id=1, clips=[parent]),
            VideoTrack(id=2, clips=[child]),
        ]
    )

    assert status["schema"] == "tigerstudio.nle.connected_clips.v1"
    assert status["connected_count"] == 1
    assert status["issue_count"] == 0
    assert status["connected"][0]["in_sync"] is True
    assert status["connected"][0]["role"] == "b_roll"


def test_connected_clip_status_reports_missing_parent_and_role_palette() -> None:
    child = _clip(20, 1400, 800)
    child.connected_parent_track_id = 99
    child.connected_parent_clip_id = 10
    child.clip_role = "overlay"

    status = build_connected_clip_status([VideoTrack(id=2, clips=[child])])
    roles = build_role_color_status([VideoTrack(id=2, clips=[child])])

    assert status["issue_count"] == 1
    assert status["issues"][0]["type"] == "missing_parent"
    assert roles["role_counts"]["overlay"] == 1
    assert role_color_for("overlay") == "#8D7CFF"


def test_connected_clip_contract_evidence_requires_action_surface() -> None:
    evidence = connected_clip_contract_evidence(
        [
            "timeline.connected_clips.status",
            "timeline.connected_clips.connect",
            "timeline.clip_role.set",
            "timeline.role_colors.status",
        ]
    )

    assert evidence["ok"] is True
    assert "b_roll" in evidence["palette"]

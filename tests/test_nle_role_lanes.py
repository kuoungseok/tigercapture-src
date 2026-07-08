from __future__ import annotations

from pathlib import Path

from app.nle_role_lanes import build_role_lane_status, role_lane_contract_evidence
from app.timeline_model import VideoClip, VideoTrack


def _clip(clip_id: int, path: str, start: int = 0, duration: int = 1000) -> VideoClip:
    return VideoClip(
        id=clip_id,
        source_path=Path(path),
        source_duration_ms=duration,
        timeline_in_ms=start,
        source_in_ms=0,
        source_out_ms=duration,
    )


def test_role_lane_status_groups_clips_by_role_and_counts_nle_cues() -> None:
    primary = _clip(10, "primary.mp4", duration=2000)
    overlay = _clip(20, "overlay.mp4", start=500, duration=1000)
    overlay.clip_role = "overlay"
    overlay.connected_parent_track_id = 1
    overlay.connected_parent_clip_id = 10
    overlay.connected_offset_ms = 500
    overlay.audition_active_take_id = "take_a"
    overlay.audition_takes = [{"id": "take_a", "source_path": "overlay.mp4"}]

    status = build_role_lane_status(
        [
            VideoTrack(id=1, clips=[primary]),
            VideoTrack(id=2, clips=[overlay]),
        ],
        focused_role="overlay",
    )

    assert status["schema"] == "tigerstudio.nle.role_lanes.v1"
    assert status["focused_role"] == "overlay"
    assert status["lane_count"] == 2
    overlay_lane = next(row for row in status["lanes"] if row["role"] == "overlay")
    assert overlay_lane["connected_count"] == 1
    assert overlay_lane["audition_count"] == 1
    assert overlay_lane["clips"][0]["active_take_id"] == "take_a"


def test_role_lane_contract_evidence_requires_status_and_focus_actions() -> None:
    evidence = role_lane_contract_evidence(["timeline.role_lanes.status", "timeline.role_lanes.focus"])

    assert evidence["ok"] is True
    assert evidence["available_actions"] == evidence["required_actions"]

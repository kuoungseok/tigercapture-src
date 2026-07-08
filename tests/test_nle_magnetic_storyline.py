from __future__ import annotations

from app.nle_magnetic_storyline import (
    build_magnetic_storyline_plan,
    build_magnetic_storyline_status,
    magnetic_storyline_contract_evidence,
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


def test_magnetic_storyline_status_reports_gaps_and_overlaps() -> None:
    track = VideoTrack(id=1, clips=[_clip(10, 0), _clip(11, 1500), _clip(12, 2400)])

    status = build_magnetic_storyline_status([track], min_gap_ms=100)

    assert status["schema"] == "tigerstudio.nle.magnetic_storyline.v1"
    assert status["gap_count"] == 1
    assert status["overlap_count"] == 1
    assert status["tracks"][0]["gaps"][0]["duration_ms"] == 500
    assert status["tracks"][0]["overlaps"][0]["duration_ms"] == 100


def test_magnetic_storyline_plan_preserves_order_and_skips_locked_tracks() -> None:
    track = VideoTrack(id=1, clips=[_clip(10, 500), _clip(11, 2000), _clip(12, 3600)])
    locked = VideoTrack(id=2, locked=True, clips=[_clip(20, 0), _clip(21, 2500)])

    plan = build_magnetic_storyline_plan(
        [track, locked],
        min_gap_ms=100,
        pull_first_to_zero=True,
    )

    assert plan["move_count"] == 3
    assert [row["clip_id"] for row in plan["moves"]] == [10, 11, 12]
    assert [row["to_ms"] for row in plan["moves"]] == [0, 1000, 2000]
    assert "track 2 is locked" in plan["warnings"]


def test_magnetic_storyline_contract_evidence_requires_actions() -> None:
    evidence = magnetic_storyline_contract_evidence(
        action_ids=[
            "timeline.magnetic_storyline.status",
            "timeline.magnetic_storyline.apply",
            "timeline.close_all_gaps",
            "timeline.play_clip_range",
        ]
    )

    assert evidence["ok"] is True
    assert len(evidence["available_actions"]) == len(evidence["required_actions"])

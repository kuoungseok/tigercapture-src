from __future__ import annotations

from pathlib import Path

from app.nle_auditions import (
    build_audition_status,
    build_audition_compare_view,
    audition_contract_evidence,
    take_from_clip,
)
from app.nle_audition_visuals import build_audition_card_model
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


def test_audition_status_reports_active_take_health() -> None:
    host = _clip(10, "host.mp4", duration=2000)
    host.audition_group_id = 10
    host.audition_active_take_id = "take_b"
    host.audition_takes = [
        take_from_clip(host, take_id="take_a", label="A"),
        {
            "id": "take_b",
            "label": "B",
            "source_path": "alt.mp4",
            "source_duration_ms": 1500,
            "source_in_ms": 0,
            "source_out_ms": 1500,
        },
    ]

    status = build_audition_status([VideoTrack(id=1, clips=[host])])

    assert status["schema"] == "tigerstudio.nle.auditions.v1"
    assert status["audition_count"] == 1
    assert status["take_count"] == 2
    assert status["issue_count"] == 0
    assert status["auditions"][0]["active_take_id"] == "take_b"


def test_audition_status_reports_missing_active_take() -> None:
    host = _clip(10, "host.mp4")
    host.audition_group_id = 10
    host.audition_active_take_id = "missing"
    host.audition_takes = [take_from_clip(host, take_id="take_a", label="A")]

    status = build_audition_status([VideoTrack(id=1, clips=[host])])

    assert status["issue_count"] == 1
    assert status["issues"][0]["type"] == "active_take_missing"


def test_audition_contract_evidence_requires_action_surface() -> None:
    evidence = audition_contract_evidence(
        [
            "timeline.auditions.status",
            "timeline.audition.compare",
            "timeline.audition.add_take",
            "timeline.audition.switch_take",
            "timeline.audition.rename_take",
            "timeline.audition.remove_take",
        ]
    )

    assert evidence["ok"] is True


def test_audition_compare_view_marks_active_take_and_commands() -> None:
    host = _clip(10, "host.mp4", duration=2000)
    host.audition_group_id = 10
    host.audition_name = "Cut options"
    host.audition_active_take_id = "take_b"
    host.audition_takes = [
        take_from_clip(host, take_id="take_a", label="A"),
        {
            "id": "take_b",
            "label": "B",
            "source_path": "alt.mp4",
            "source_duration_ms": 1500,
            "source_in_ms": 100,
            "source_out_ms": 1400,
        },
    ]

    view = build_audition_compare_view(track_id=1, clip=host)

    assert view["schema"] == "tigerstudio.nle.audition_compare.v1"
    assert view["ready"] is True
    assert view["can_remove"] is True
    assert view["take_count"] == 2
    assert view["takes"][1]["active"] is True
    assert view["takes"][1]["commands"]["switch_action"] == "timeline.audition.switch_take"

    cards = build_audition_card_model(view)
    assert cards["schema"] == "tigerstudio.nle.audition_card_model.v1"
    assert cards["card_count"] == 2
    assert cards["cards"][1]["active"] is True
    assert cards["cards"][1]["badge"] == "ACTIVE"
    assert cards["cards"][1]["delta_tone"] == "shorter"


def test_project_io_persists_audition_takes() -> None:
    from app.project_io import _video_clip_from_dict, _video_clip_to_dict

    host = _clip(10, "host.mp4")
    host.audition_group_id = 10
    host.audition_name = "Cut options"
    host.audition_active_take_id = "take_a"
    host.audition_takes = [take_from_clip(host, take_id="take_a", label="A")]

    data = _video_clip_to_dict(host)
    restored = _video_clip_from_dict(data, None)

    assert restored.audition_group_id == 10
    assert restored.audition_name == "Cut options"
    assert restored.audition_active_take_id == "take_a"
    assert restored.audition_takes[0]["id"] == "take_a"

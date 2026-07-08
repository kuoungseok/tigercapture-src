from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.timeline_model import VideoClip, VideoTrack
from app.video_editor_nle_role_workflow import (
    apply_nle_role_focus_to_rows,
    refresh_nle_role_filter_bar,
    set_nle_role_lane_focus_from_ui,
)


def _clip(clip_id: int, role: str = "primary") -> VideoClip:
    clip = VideoClip(
        id=clip_id,
        source_path=Path(f"clip_{clip_id}.mp4"),
        source_duration_ms=1000,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=1000,
    )
    clip.clip_role = role
    return clip


class _FakeRoleFilterBar:
    def __init__(self) -> None:
        self.model: dict[str, object] = {}
        self.visible = False

    def set_model(self, model: dict[str, object]) -> None:
        self.model = model
        self.visible = bool(((model.get("lane_status") or {}) or {}).get("clip_count"))

    def setVisible(self, visible: bool) -> None:  # noqa: N802 - Qt-style test double
        self.visible = bool(visible)


class _FakeTrackRow:
    def __init__(self) -> None:
        self.focused_role = ""

    def set_focused_clip_role(self, role: str) -> None:
        self.focused_role = role


def test_refresh_nle_role_filter_bar_builds_visible_role_model() -> None:
    bar = _FakeRoleFilterBar()
    owner = SimpleNamespace(
        _nle_role_filter_bar=bar,
        _nle_role_lane_focus="overlay",
        _tracks=[
            VideoTrack(id=1, clips=[_clip(10, "primary")]),
            VideoTrack(id=2, clips=[_clip(20, "overlay")]),
        ],
    )

    refresh_nle_role_filter_bar(owner)

    assert bar.visible is True
    assert bar.model["focused_role"] == "overlay"
    assert ((bar.model["lane_status"] or {}) or {})["clip_count"] == 2
    roles = {row["role"] for row in bar.model["filters"]}
    assert {"primary", "overlay"} <= roles


def test_apply_nle_role_focus_to_rows_normalizes_and_updates_rows() -> None:
    row = _FakeTrackRow()
    owner = SimpleNamespace(_track_rows={1: row})

    apply_nle_role_focus_to_rows(owner, "b-roll")

    assert owner._nle_role_lane_focus == "b_roll"
    assert row.focused_role == "b_roll"


def test_role_focus_ui_fallback_updates_rows_and_status() -> None:
    bar = _FakeRoleFilterBar()
    row = _FakeTrackRow()
    calls: list[str] = []
    owner = SimpleNamespace(
        _nle_role_filter_bar=bar,
        _nle_role_lane_focus="",
        _track_rows={1: row},
        _tracks=[VideoTrack(id=1, clips=[_clip(10, "overlay")])],
        _update_timeline_status=lambda: calls.append("status"),
        _flash_status=lambda text: calls.append(text),
    )

    set_nle_role_lane_focus_from_ui(owner, "overlay")

    assert owner._nle_role_lane_focus == "overlay"
    assert row.focused_role == "overlay"
    assert bar.model["focused_role"] == "overlay"
    assert "status" in calls
    assert any("Overlay" in call for call in calls)

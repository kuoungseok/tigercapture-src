from __future__ import annotations

from types import SimpleNamespace

from app.video_editor_workflow_targeting import (
    actor_model_candidate,
    first_media_pool_path,
    first_video_clip_candidate,
    focus_preview_at_workflow_ms,
    select_workflow_video_clip,
    selected_video_clip,
    workflow_start_ms,
    workflow_target_video_clip,
)


def _clip(clip_id: int, start: int, end: int):
    return SimpleNamespace(id=clip_id, timeline_in_ms=start, timeline_out_ms=end)


def _track(track_id: int, *clips, duration_ms: int = 0):
    return SimpleNamespace(id=track_id, clips=list(clips), duration_ms=duration_ms)


class FakePlayer:
    def __init__(self, position_ms: int = 0) -> None:
        self._position_ms = int(position_ms)
        self.calls: list[tuple[str, int]] = []

    def position(self) -> int:
        return self._position_ms

    def set_position(self, ms: int) -> None:
        self._position_ms = int(ms)
        self.calls.append(("seek", int(ms)))


def _owner_with_tracks(*tracks, player=None):
    by_id = {int(track.id): track for track in tracks}
    owner = SimpleNamespace(
        _tracks=list(tracks),
        _player=player or FakePlayer(),
        _selected_clips=[],
        _active_track_id=int(tracks[0].id) if tracks else -1,
    )
    owner._find_track = lambda track_id: by_id.get(int(track_id))
    owner._active_track = lambda: by_id.get(int(owner._active_track_id))
    return owner


def test_selected_and_active_workflow_targets_are_resolved_from_owner_duck_typing():
    selected = _clip(101, 0, 1000)
    active_hit = _clip(202, 1200, 2200)
    selected_track = _track(1, selected)
    active_track = _track(2, _clip(201, 0, 1000), active_hit)
    owner = _owner_with_tracks(selected_track, active_track, player=FakePlayer(1500))
    owner._selected_clips = [(1, 101)]
    owner._active_track_id = 2

    assert selected_video_clip(owner) == (selected_track, selected)
    assert workflow_target_video_clip(owner) == (selected_track, selected)

    owner._workflow_target_mode = "active_track"

    assert workflow_target_video_clip(owner) == (active_track, active_hit)


def test_forced_workflow_target_overrides_auto_selection_and_uses_forced_ms():
    selected = _clip(101, 0, 1000)
    forced_hit = _clip(202, 1200, 2200)
    selected_track = _track(1, selected)
    forced_track = _track(2, _clip(201, 0, 1000), forced_hit)
    owner = _owner_with_tracks(selected_track, forced_track, player=FakePlayer(0))
    owner._selected_clips = [(1, 101)]
    owner._workflow_forced_track_id = 2
    owner._workflow_forced_ms = 1500

    assert workflow_target_video_clip(owner) == (forced_track, forced_hit)

    owner._workflow_forced_ms = 3000

    assert workflow_target_video_clip(owner) == (forced_track, None)

    owner._workflow_target_mode = "selected_clip"

    assert workflow_target_video_clip(owner) == (selected_track, selected)


def test_select_workflow_video_clip_updates_owner_selection_and_row_notifications():
    clip = _clip(7, 240, 700)
    track = _track(3, clip)
    calls: list[tuple[str, object]] = []

    class Row:
        def set_selected_clip_ids(self, clip_ids) -> None:
            calls.append(("selected", set(clip_ids)))

        def flash_timeline_burst(self, kind: str, ms: int) -> None:
            calls.append(("flash", (kind, int(ms))))

        def update(self) -> None:
            calls.append(("update", None))

    owner = SimpleNamespace(
        _track_rows={3: Row()},
        _broadcast_clip_selection=lambda: calls.append(("broadcast", None)),
        _refresh_workbench=lambda: calls.append(("workbench", None)),
    )

    assert select_workflow_video_clip(owner, track, clip) is True
    assert owner._active_track_id == 3
    assert owner._selected_clips == [(3, 7)]
    assert calls == [
        ("broadcast", None),
        ("selected", {7}),
        ("flash", ("select", 240)),
        ("update", None),
        ("workbench", None),
    ]


def test_first_clip_and_media_pool_actor_candidates_use_lightweight_owner_stubs(tmp_path):
    first = _clip(1, 0, 100)
    second = _clip(2, 100, 200)
    track = _track(5, first, second)
    model = tmp_path / "avatar.model3.json"
    ignored = tmp_path / "readme.txt"
    model.write_text("{}", encoding="utf-8")
    ignored.write_text("notes", encoding="utf-8")
    owner = SimpleNamespace(_tracks=[track], _media_pool=SimpleNamespace(items=lambda: [ignored, model]))

    assert first_video_clip_candidate(owner) == (track, first)
    assert first_media_pool_path(owner, lambda path: path.suffix == ".txt") == ignored
    assert actor_model_candidate(owner, "live2d") == str(model)


def test_workflow_start_and_focus_preview_call_player_and_preview_collaborators():
    clip = _clip(7, 500, 900)
    track = _track(3, clip, duration_ms=1000)
    player = FakePlayer(1200)
    calls: list[tuple[str, int | None]] = []
    owner = SimpleNamespace(
        _active_track_id=1,
        _player=player,
        _set_active_track=lambda track_id: calls.append(("active", int(track_id))),
        _refresh_preview_soft=lambda focus_track=None: calls.append(("refresh", getattr(focus_track, "id", None))),
        _ensure_playhead_visible=lambda: calls.append(("visible", None)),
    )

    assert workflow_start_ms(owner, track=track) == 1000
    assert workflow_start_ms(owner, clip=clip) == 500
    assert workflow_start_ms(owner, explicit_ms=-25) == 0

    focus_preview_at_workflow_ms(owner, 1234, track=track)

    assert owner._last_workflow_focus_ms == 1234
    assert owner._last_workflow_focus_track_id == 3
    assert player.calls == [("seek", 1234)]
    assert calls == [("active", 3), ("refresh", 3), ("visible", None)]

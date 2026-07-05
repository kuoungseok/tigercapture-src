from __future__ import annotations

from types import SimpleNamespace

import app.video_editor_context_menu_controller as ctx


def _tr(key: str) -> str:
    labels = {
        "veditor.clip_badge.menu.disable_fx": "FX off",
        "veditor.clip_badge.menu.enable_fx": "FX on",
        "veditor.clip_badge.menu.clear_fx": "Clear FX",
        "veditor.clip_badge.menu.clear_transition": "Clear Transition",
        "veditor.clip_badge.status.cleared_fx": "FX cleared",
        "veditor.clip_badge.status.no_transition_clear": "No transition",
        "veditor.menu.extract_audio": "Extract audio",
        "veditor.menu.blade_at_playhead": "Blade",
        "veditor.menu.ripple_delete": "Ripple delete",
        "veditor.menu.delete_track": "Delete track",
        "veditor.menu.cut_selection": "Cut selection",
        "veditor.menu.clear_cuts": "Clear cuts",
        "veditor.audio.ctx.trim": "Trim range",
        "veditor.audio.ctx.delete_clip": "Delete audio clip",
        "veditor.audio.ctx.remove": "Delete audio track",
        "paint.btn.clear_all": "Clear all",
    }
    return labels.get(key, key)


def _ids(rows):
    return [row.get("id") for row in rows if row.get("kind") == "action"]


def test_clip_badge_model_and_dispatch_use_owner_fx_and_transition_helpers():
    calls: list[tuple[str, object]] = []
    clip = SimpleNamespace(
        id=9,
        video_filters={"enabled": True, "sharp": 0.5},
        disabled_video_filters=None,
        chroma_key=None,
        bg_removal=None,
        disabled_chroma_key=None,
        disabled_bg_removal=None,
        transition_out_type="dissolve",
    )
    track = SimpleNamespace(id=4)

    def _set_fx_enabled(_track, _clip, enabled):
        calls.append(("set_fx", enabled))
        if enabled:
            _clip.video_filters = _clip.disabled_video_filters
            _clip.disabled_video_filters = None
        else:
            _clip.disabled_video_filters = _clip.video_filters
            _clip.video_filters = None
        return True

    def _clear_fx(_track, _clip):
        calls.append(("clear_fx", _clip.id))
        _clip.video_filters = None
        _clip.disabled_video_filters = None
        return True

    def _clear_transition(_track, _clip):
        calls.append(("clear_transition", _clip.id))
        _clip.transition_out_type = ""
        return True

    owner = SimpleNamespace(
        _clip_has_active_fx=lambda c: ctx.clip_has_active_fx(c),
        _clip_has_disabled_fx=lambda c: ctx.clip_has_disabled_fx(c),
        _set_clip_fx_enabled=_set_fx_enabled,
        _clear_clip_fx=_clear_fx,
        _clear_clip_transition=_clear_transition,
        _flash_status=lambda message: calls.append(("status", message)),
        _on_clip_badge_action_requested=lambda tid, cid, action: calls.append(("focus", (tid, cid, action))),
    )

    rows = ctx.build_clip_badge_menu_model(clip, "fx", translator=_tr)
    assert _ids(rows) == ["focus", "toggle_fx", "clear_fx"]
    assert rows[1]["label"] == "FX off"
    assert rows[1]["enabled"] is True

    assert ctx.dispatch_clip_badge_menu_action(owner, track, clip, "fx", "toggle_fx", translator=_tr) is True
    assert clip.video_filters is None
    assert clip.disabled_video_filters == {"enabled": True, "sharp": 0.5}

    rows = ctx.build_clip_badge_menu_model(clip, "fx", translator=_tr)
    assert rows[1]["label"] == "FX on"

    assert ctx.dispatch_clip_badge_menu_action(owner, track, clip, "fx", "clear_fx", translator=_tr) is True
    assert ("status", "FX cleared") in calls

    transition_rows = ctx.build_clip_badge_menu_model(clip, "transition", translator=_tr)
    assert transition_rows[1]["enabled"] is True
    assert ctx.dispatch_clip_badge_menu_action(owner, track, clip, "transition", "clear_transition", translator=_tr)
    assert clip.transition_out_type == ""


def test_video_clip_model_covers_nested_fx_transition_and_dispatch_commands():
    calls: list[tuple[str, object]] = []
    track = SimpleNamespace(id=7, source_path=None)
    clip = SimpleNamespace(
        id=33,
        source_path="clip.mp4",
        video_filters=None,
        disabled_video_filters={"enabled": True},
        chroma_key=None,
        bg_removal=None,
        disabled_chroma_key=None,
        disabled_bg_removal=None,
        transition_out_type="",
        is_nested_sequence=True,
    )
    owner = SimpleNamespace(
        _clip_has_active_fx=lambda c: ctx.clip_has_active_fx(c),
        _clip_has_disabled_fx=lambda c: ctx.clip_has_disabled_fx(c),
        _set_clip_fx_enabled=lambda _track, _clip, enabled: calls.append(("set_fx", enabled)) or True,
        _open_clip_effects=lambda _track, _clip: calls.append(("effects", _clip.id)),
        _on_clip_badge_action_requested=lambda tid, cid, action: calls.append(("focus", (tid, cid, action))),
        _extract_audio_from_video_selection=lambda _track, _clip: calls.append(("extract", _clip.id)),
        _blade_at_playhead=lambda **kwargs: calls.append(("blade", kwargs.get("track_id"))),
        _delete_selected_clips=lambda: calls.append(("delete", None)),
        _edit_nested_sequence_clip=lambda _track, _clip: calls.append(("edit_nested", _clip.id)),
        _open_nested_sequence_for_edit=lambda _track, _clip: calls.append(("expand_nested", _clip.id)),
    )

    rows = ctx.build_video_clip_context_menu_model(track, clip, translator=_tr)

    assert _ids(rows) == [
        "open_clip_effects",
        "focus_fx_stack",
        "toggle_fx",
        "clear_fx",
        "clear_transition",
        "edit_nested_sequence",
        "expand_nested_sequence",
        "extract_audio",
        "blade_at_playhead",
        "delete_selected_clips",
    ]
    assert rows[2]["label"] == "Enable Clip FX"
    assert rows[4]["enabled"] is False
    assert next(row for row in rows if row.get("id") == "extract_audio")["enabled"] is True

    assert ctx.dispatch_video_clip_context_menu_action(owner, track, clip, "toggle_fx") is True
    assert ctx.dispatch_video_clip_context_menu_action(owner, track, clip, "focus_fx_stack") is True
    assert ctx.dispatch_video_clip_context_menu_action(owner, track, clip, "extract_audio") is True
    assert ctx.dispatch_video_clip_context_menu_action(owner, track, clip, "blade_at_playhead") is True
    assert calls == [
        ("set_fx", True),
        ("focus", (7, 33, "fx")),
        ("extract", 33),
        ("blade", 7),
    ]


def test_track_model_and_dispatch_select_audio_extract_target_and_track_actions():
    calls: list[tuple[str, object]] = []
    selected = SimpleNamespace(id=11, source_path=None, linked_audio_id=91)
    source_clip = SimpleNamespace(id=12, source_path="fallback.mp4")
    other_track = SimpleNamespace(id=1, clips=[])
    track = SimpleNamespace(id=2, source_path=None, clips=[selected, source_clip], locked=False)
    tracks = [other_track, track]

    def _find_track(track_id):
        return {1: other_track, 2: track}.get(int(track_id))

    owner = SimpleNamespace(
        _tracks=tracks,
        _audio_tracks=[SimpleNamespace(id=20)],
        _selected_clips=[(2, 11)],
        _find_track=_find_track,
        _toggle_audio_link=lambda _track, _clip: calls.append(("link", (_track.id, _clip.id))),
        _extract_audio_from_video_selection=lambda _track, _clip: calls.append(("extract", (_track.id, _clip.id))),
        _move_track=lambda tid, delta: calls.append(("move", (tid, delta))),
        _cleanup_timeline_micro_edges=lambda tid: calls.append(("cleanup", tid)),
        _delete_track=lambda tid: calls.append(("delete_track", tid)),
    )

    rows = ctx.build_track_context_menu_model(
        track,
        tracks=tracks,
        audio_tracks=owner._audio_tracks,
        selected_clips=owner._selected_clips,
        selected_clip=selected,
        edge_summary={"auto_fixable_count": 2},
        translator=_tr,
    )

    assert "toggle_audio_link" in _ids(rows)
    assert next(row for row in rows if row.get("id") == "cleanup_micro_edges")["enabled"] is True
    assert next(row for row in rows if row.get("id") == "move_track_up")["enabled"] is True
    assert next(row for row in rows if row.get("id") == "move_track_down")["enabled"] is False
    assert next(row for row in rows if row.get("id") == "delete_track")["enabled"] is True

    assert ctx.dispatch_track_context_menu_action(owner, 2, "toggle_audio_link", track=track) is True
    assert ctx.dispatch_track_context_menu_action(owner, 2, "extract_audio", track=track) is True
    assert ctx.dispatch_track_context_menu_action(owner, 2, "move_track_up", track=track) is True
    assert ctx.dispatch_track_context_menu_action(owner, 2, "cleanup_micro_edges", track=track) is True
    assert ctx.dispatch_track_context_menu_action(owner, 2, "delete_track", track=track) is True
    assert calls == [
        ("link", (2, 11)),
        ("extract", (2, 11)),
        ("move", (2, -1)),
        ("cleanup", 2),
        ("delete_track", 2),
    ]


def test_audio_clip_model_dispatch_and_trim_helper_update_owner_collaborators():
    calls: list[tuple[str, object]] = []

    class Row:
        def __init__(self) -> None:
            self.updated = 0
            self.refreshed = 0

        def update(self) -> None:
            self.updated += 1

        def refresh_from_track(self) -> None:
            self.refreshed += 1

    class Mixer:
        def update_track(self, track) -> None:
            calls.append(("mixer", track.id))

    row = Row()
    clip = SimpleNamespace(
        id=5,
        selection_start_ms=10,
        selection_end_ms=40,
        cuts=[SimpleNamespace(start_ms=20, end_ms=30)],
        trim_start_ms=0,
        trim_end_ms=100,
    )
    track = SimpleNamespace(id=8, clips=[clip])
    owner = SimpleNamespace(
        _audio_rows={8: row},
        _audio_mixer=Mixer(),
        _refresh_player_tracks=lambda: calls.append(("refresh", None)),
        _split_audio_clip=lambda _track, _clip: calls.append(("split", _clip.id)),
        _remove_clip_from_waveform_jobs=lambda _clip: calls.append(("remove_waveform", _clip.id)),
    )

    rows = ctx.build_audio_clip_context_menu_model(clip, translator=_tr)
    assert _ids(rows) == ["cut_selection", "clear_cuts", "trim_range", "delete_audio_clip"]
    assert rows[0]["enabled"] is True
    assert rows[1]["enabled"] is True

    assert ctx.dispatch_audio_clip_context_menu_action(owner, track, clip, "cut_selection") is True
    assert ctx.dispatch_audio_clip_context_menu_action(owner, track, clip, "clear_cuts") is True
    assert clip.cuts == []
    assert row.updated == 1

    assert ctx.trim_audio_clip_to_range(owner, track, clip, 25, 90) is True
    assert (clip.trim_start_ms, clip.trim_end_ms) == (25, 90)
    assert row.updated == 2

    assert ctx.dispatch_audio_clip_context_menu_action(owner, track, clip, "delete_audio_clip") is True
    assert track.clips == []
    assert row.refreshed == 1
    assert ("remove_waveform", 5) in calls


def test_audio_row_and_preview_models_dispatch_to_owner():
    calls: list[tuple[str, object]] = []
    audio_rows = ctx.build_audio_row_context_menu_model(SimpleNamespace(id=3), translator=_tr)
    assert audio_rows == [
        {
            "kind": "action",
            "id": "delete_audio_track",
            "label": "Delete audio track",
            "enabled": True,
            "label_key": "veditor.audio.ctx.remove",
        }
    ]
    owner = SimpleNamespace(_delete_audio_track=lambda tid: calls.append(("delete_audio_track", tid)))
    assert ctx.dispatch_audio_row_context_menu_action(owner, 3, "delete_audio_track") is True

    class Canvas:
        def update(self) -> None:
            calls.append(("canvas", None))

    preview_owner = SimpleNamespace(_strokes=["a", "b"], _drawing_canvas=Canvas())
    disabled_rows = ctx.build_preview_context_menu_model(has_strokes=False, translator=_tr)
    assert disabled_rows[0]["enabled"] is False
    assert ctx.dispatch_preview_context_menu_action(preview_owner, "clear_paint_strokes") is True
    assert preview_owner._strokes == []
    assert calls == [("delete_audio_track", 3), ("canvas", None)]

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any


Translator = Callable[[str], str]
MenuRow = dict[str, object]


def _label(translator: Translator | None, key: str, fallback: str) -> str:
    if translator is None:
        return fallback
    try:
        text = translator(key)
    except Exception:
        return fallback
    return str(text or fallback)


def _action(
    action_id: str,
    label: str,
    *,
    enabled: bool = True,
    label_key: str = "",
    icon: str = "",
    tooltip: str = "",
) -> MenuRow:
    row: MenuRow = {
        "kind": "action",
        "id": str(action_id),
        "label": str(label),
        "enabled": bool(enabled),
    }
    if label_key:
        row["label_key"] = str(label_key)
    if icon:
        row["icon"] = str(icon)
    if tooltip:
        row["tooltip"] = str(tooltip)
    return row


def _separator(name: str = "") -> MenuRow:
    row: MenuRow = {"kind": "separator"}
    if name:
        row["id"] = f"separator:{name}"
    return row


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _call(owner: Any, name: str, *args: Any, **kwargs: Any) -> Any:
    fn = getattr(owner, name, None)
    if callable(fn):
        return fn(*args, **kwargs)
    return None


def _invoke(owner: Any, name: str, *args: Any, **kwargs: Any) -> bool:
    fn = getattr(owner, name, None)
    if not callable(fn):
        return False
    fn(*args, **kwargs)
    return True


def _call_bool(owner: Any, name: str, *args: Any, **kwargs: Any) -> bool:
    fn = getattr(owner, name, None)
    if not callable(fn):
        return False
    return bool(fn(*args, **kwargs))


def _flash_status(owner: Any, message: str) -> None:
    try:
        _call(owner, "_flash_status", message)
    except Exception:
        pass


def _effect_param_active(value: Any) -> bool:
    if value is None:
        return False
    is_identity = getattr(value, "is_identity", None)
    if callable(is_identity):
        try:
            return not bool(is_identity())
        except Exception:
            return True
    if isinstance(value, Mapping):
        if bool(value.get("enabled", False)):
            return True
        ignored = {
            "enabled",
            "name",
            "label",
            "preset_id",
            "preset_meta",
            "__preset_meta",
            "kind",
        }
        for key, item in value.items():
            if str(key) in ignored:
                continue
            if item not in (None, False, 0, 0.0, ""):
                return True
        return False
    return True


def clip_has_active_fx(clip: Any) -> bool:
    return any(
        _effect_param_active(getattr(clip, attr, None))
        for attr in ("video_filters", "chroma_key", "bg_removal")
    )


def clip_has_disabled_fx(clip: Any) -> bool:
    return any(
        _effect_param_active(getattr(clip, attr, None))
        for attr in (
            "disabled_video_filters",
            "disabled_chroma_key",
            "disabled_bg_removal",
        )
    )


def _owner_clip_has_active_fx(owner: Any, clip: Any) -> bool:
    fn = getattr(owner, "_clip_has_active_fx", None)
    if callable(fn):
        return bool(fn(clip))
    return clip_has_active_fx(clip)


def _owner_clip_has_disabled_fx(owner: Any, clip: Any) -> bool:
    fn = getattr(owner, "_clip_has_disabled_fx", None)
    if callable(fn):
        return bool(fn(clip))
    return clip_has_disabled_fx(clip)


def clip_has_transition(clip: Any) -> bool:
    return bool(str(getattr(clip, "transition_out_type", "") or ""))


def _iter_clips(track: Any) -> Iterable[Any]:
    return getattr(track, "clips", []) or []


def _find_clip(track: Any, clip_id: int) -> Any | None:
    for clip in _iter_clips(track):
        if _safe_int(getattr(clip, "id", -1), -1) == int(clip_id):
            return clip
    return None


def find_video_track(owner: Any, track_id: int) -> Any | None:
    finder = getattr(owner, "_find_track", None)
    if callable(finder):
        track = finder(int(track_id))
        if track is not None:
            return track
    for track in getattr(owner, "_tracks", []) or []:
        if _safe_int(getattr(track, "id", -1), -1) == int(track_id):
            return track
    return None


def find_video_clip(owner: Any, track_id: int, clip_id: int) -> tuple[Any | None, Any | None]:
    track = find_video_track(owner, int(track_id))
    if track is None:
        return None, None
    return track, _find_clip(track, int(clip_id))


def _selected_clip_pairs(owner: Any) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for item in getattr(owner, "_selected_clips", []) or []:
        try:
            track_id, clip_id = item
        except Exception:
            continue
        pairs.append((_safe_int(track_id), _safe_int(clip_id)))
    return pairs


def _selected_video_clip(owner: Any) -> tuple[Any | None, Any | None]:
    selected = _selected_clip_pairs(owner)
    if len(selected) != 1:
        return None, None
    track_id, clip_id = selected[0]
    return find_video_clip(owner, track_id, clip_id)


def _track_has_any_source(track: Any) -> bool:
    if getattr(track, "source_path", None) is not None:
        return True
    return any(getattr(clip, "source_path", None) is not None for clip in _iter_clips(track))


def build_clip_badge_menu_model(
    clip: Any,
    action: str,
    *,
    translator: Translator | None = None,
    has_active_fx: bool | None = None,
    has_disabled_fx: bool | None = None,
) -> list[MenuRow]:
    action = str(action or "inspect").casefold()
    rows: list[MenuRow] = [
        _action(
            "focus",
            _label(translator, "veditor.clip_badge.menu.focus", "Focus / edit"),
            label_key="veditor.clip_badge.menu.focus",
        )
    ]
    if action == "fx":
        active = clip_has_active_fx(clip) if has_active_fx is None else bool(has_active_fx)
        disabled = clip_has_disabled_fx(clip) if has_disabled_fx is None else bool(has_disabled_fx)
        rows.append(
            _action(
                "toggle_fx",
                _label(
                    translator,
                    "veditor.clip_badge.menu.disable_fx"
                    if active
                    else "veditor.clip_badge.menu.enable_fx",
                    "Disable FX" if active else "Enable FX",
                ),
                enabled=bool(active or disabled),
                label_key=(
                    "veditor.clip_badge.menu.disable_fx"
                    if active
                    else "veditor.clip_badge.menu.enable_fx"
                ),
            )
        )
        rows.append(
            _action(
                "clear_fx",
                _label(translator, "veditor.clip_badge.menu.clear_fx", "Clear FX"),
                enabled=bool(active or disabled),
                label_key="veditor.clip_badge.menu.clear_fx",
            )
        )
    elif action == "transition":
        rows.append(
            _action(
                "clear_transition",
                _label(
                    translator,
                    "veditor.clip_badge.menu.clear_transition",
                    "Clear Transition",
                ),
                enabled=clip_has_transition(clip),
                label_key="veditor.clip_badge.menu.clear_transition",
            )
        )
    elif action == "color":
        rows[0]["label"] = _label(
            translator,
            "veditor.clip_badge.menu.open_color",
            "Open Color controls",
        )
        rows[0]["label_key"] = "veditor.clip_badge.menu.open_color"
    elif action == "title":
        rows[0]["label"] = _label(
            translator,
            "veditor.clip_badge.menu.focus_title",
            "Focus title actor",
        )
        rows[0]["label_key"] = "veditor.clip_badge.menu.focus_title"
    elif action == "motion":
        rows[0]["label"] = _label(
            translator,
            "veditor.clip_badge.menu.focus_motion",
            "Focus motion actor",
        )
        rows[0]["label_key"] = "veditor.clip_badge.menu.focus_motion"
    elif action == "nested":
        rows[0]["label"] = _label(
            translator,
            "veditor.clip_badge.menu.open_nested",
            "Open nested sequence",
        )
        rows[0]["label_key"] = "veditor.clip_badge.menu.open_nested"
    elif action == "audition":
        rows[0]["label"] = "Open audition takes"
        rows[0]["label_key"] = "veditor.clip_badge.menu.open_audition"
    elif action == "connected":
        rows[0]["label"] = "Focus connected parent"
        rows[0]["label_key"] = "veditor.clip_badge.menu.focus_connected"
    return rows


def dispatch_clip_badge_menu_action(
    owner: Any,
    track: Any,
    clip: Any,
    badge_action: str,
    command: str,
    *,
    translator: Translator | None = None,
) -> bool:
    if track is None or clip is None:
        return False
    command = str(command or "")
    if command == "focus":
        _call(
            owner,
            "_on_clip_badge_action_requested",
            _safe_int(getattr(track, "id", 0)),
            _safe_int(getattr(clip, "id", 0)),
            badge_action,
        )
        if str(badge_action or "").casefold() == "color":
            _call(owner, "_open_color_page")
        return True
    if command == "toggle_fx":
        if _owner_clip_has_active_fx(owner, clip):
            return _call_bool(owner, "_set_clip_fx_enabled", track, clip, False)
        if _owner_clip_has_disabled_fx(owner, clip):
            return _call_bool(owner, "_set_clip_fx_enabled", track, clip, True)
        _flash_status(
            owner,
            _label(
                translator,
                "veditor.clip_badge.status.no_fx",
                "Selected clip has no clip FX",
            ),
        )
        return False
    if command == "clear_fx":
        if _call_bool(owner, "_clear_clip_fx", track, clip):
            _flash_status(
                owner,
                _label(
                    translator,
                    "veditor.clip_badge.status.cleared_fx",
                    "Cleared clip FX",
                ),
            )
            return True
        _flash_status(
            owner,
            _label(
                translator,
                "veditor.clip_badge.status.no_fx_clear",
                "Selected clip has no clip FX to clear",
            ),
        )
        return False
    if command == "clear_transition":
        if _call_bool(owner, "_clear_clip_transition", track, clip):
            return True
        _flash_status(
            owner,
            _label(
                translator,
                "veditor.clip_badge.status.no_transition_clear",
                "Selected clip has no transition to clear",
            ),
        )
        return False
    return False


def build_video_clip_context_menu_model(
    track: Any,
    clip: Any,
    *,
    translator: Translator | None = None,
    has_active_fx: bool | None = None,
    has_disabled_fx: bool | None = None,
) -> list[MenuRow]:
    active = clip_has_active_fx(clip) if has_active_fx is None else bool(has_active_fx)
    disabled = clip_has_disabled_fx(clip) if has_disabled_fx is None else bool(has_disabled_fx)
    has_fx = bool(active or disabled)
    rows: list[MenuRow] = [
        _action("open_clip_effects", "Clip effects...", icon="color"),
        _action("focus_fx_stack", "FX stack in Workbench"),
        _action("toggle_fx", "Enable Clip FX" if disabled and not active else "Disable Clip FX", enabled=has_fx),
        _action("clear_fx", "Clear Clip FX", enabled=has_fx),
        _action("clear_transition", "Clear Transition", enabled=clip_has_transition(clip)),
    ]
    if bool(getattr(clip, "is_nested_sequence", False)):
        rows.extend(
            [
                _separator("nested"),
                _action("edit_nested_sequence", "Edit nested sequence..."),
                _action("expand_nested_sequence", "Expand nested sequence"),
            ]
        )
    rows.extend(
        [
            _separator("media"),
            _action(
                "extract_audio",
                _label(
                    translator,
                    "veditor.menu.extract_audio",
                    "Extract audio from video",
                ),
                enabled=(
                    getattr(clip, "source_path", None) is not None
                    or getattr(track, "source_path", None) is not None
                ),
                label_key="veditor.menu.extract_audio",
            ),
            _separator("edit"),
            _action(
                "blade_at_playhead",
                _label(
                    translator,
                    "veditor.menu.blade_at_playhead",
                    "Blade at playhead (B)",
                ),
                label_key="veditor.menu.blade_at_playhead",
                icon="scissors",
            ),
            _separator("move"),
            _action("move_clip_to_playhead", "Move clip to playhead"),
            _action("move_clip_to_time", "Move clip to time..."),
            _action("nudge_clip_left_frame", "Nudge left 1 frame"),
            _action("nudge_clip_right_frame", "Nudge right 1 frame"),
            _action("nudge_clip_left_5_frames", "Nudge left 5 frames"),
            _action("nudge_clip_right_5_frames", "Nudge right 5 frames"),
            _separator("delete"),
            _action("delete_clip_leave_gap", "Delete clip (leave gap)", icon="trash"),
            _action("ripple_delete_clip", "Ripple delete clip (close gap)"),
        ]
    )
    return rows


def dispatch_video_clip_context_menu_action(
    owner: Any,
    track: Any,
    clip: Any,
    command: str,
) -> bool:
    if track is None or clip is None:
        return False
    command = str(command or "")
    track_id = _safe_int(getattr(track, "id", 0))
    clip_id = _safe_int(getattr(clip, "id", 0))
    if command == "open_clip_effects":
        return _invoke(owner, "_open_clip_effects", track, clip)
    if command == "focus_fx_stack":
        return _invoke(owner, "_on_clip_badge_action_requested", track_id, clip_id, "fx")
    if command == "toggle_fx":
        if _owner_clip_has_active_fx(owner, clip):
            return _call_bool(owner, "_set_clip_fx_enabled", track, clip, False)
        if _owner_clip_has_disabled_fx(owner, clip):
            return _call_bool(owner, "_set_clip_fx_enabled", track, clip, True)
        return False
    if command == "clear_fx":
        if _call_bool(owner, "_clear_clip_fx", track, clip):
            _flash_status(owner, "Cleared clip FX")
            return True
        _flash_status(owner, "Selected clip has no clip FX to clear")
        return False
    if command == "clear_transition":
        if _call_bool(owner, "_clear_clip_transition", track, clip):
            return True
        _flash_status(owner, "Selected clip has no transition to clear")
        return False
    if command == "edit_nested_sequence":
        return _invoke(owner, "_edit_nested_sequence_clip", track, clip)
    if command == "expand_nested_sequence":
        return _invoke(owner, "_open_nested_sequence_for_edit", track, clip)
    if command == "extract_audio":
        return _invoke(owner, "_extract_audio_from_video_selection", track, clip)
    if command == "blade_at_playhead":
        return _invoke(owner, "_blade_at_playhead", track_id=track_id)
    if command == "move_clip_to_playhead":
        return _invoke(owner, "_move_video_clip_to_playhead", track, clip)
    if command == "move_clip_to_time":
        return _invoke(owner, "_prompt_move_video_clip_to_time", track, clip)
    if command == "nudge_clip_left_frame":
        return _invoke(owner, "_nudge_video_clip_frames", track, clip, -1)
    if command == "nudge_clip_right_frame":
        return _invoke(owner, "_nudge_video_clip_frames", track, clip, 1)
    if command == "nudge_clip_left_5_frames":
        return _invoke(owner, "_nudge_video_clip_frames", track, clip, -5)
    if command == "nudge_clip_right_5_frames":
        return _invoke(owner, "_nudge_video_clip_frames", track, clip, 5)
    if command == "delete_clip_leave_gap":
        return _invoke(owner, "_delete_video_clip_leave_gap", track, clip)
    if command == "ripple_delete_clip":
        return _invoke(owner, "_ripple_delete_video_clip", track, clip)
    if command == "delete_selected_clips":
        return _invoke(owner, "_delete_selected_clips")
    return False


def build_track_context_menu_model(
    track: Any,
    *,
    tracks: Iterable[Any] = (),
    audio_tracks: Iterable[Any] = (),
    selected_clips: Iterable[tuple[int, int]] = (),
    edge_summary: Mapping[str, Any] | None = None,
    selected_clip: Any | None = None,
    translator: Translator | None = None,
) -> list[MenuRow]:
    tracks_list = list(tracks or ())
    audio_tracks_list = list(audio_tracks or ())
    selected_pairs = list(selected_clips or ())
    edge_summary = edge_summary or {}
    try:
        track_index = tracks_list.index(track)
    except ValueError:
        track_index = -1

    rows: list[MenuRow] = [
        _action(
            "blade_at_playhead",
            _label(
                translator,
                "veditor.menu.blade_at_playhead",
                "Blade at playhead (B)",
            ),
            enabled=bool(getattr(track, "clips", None)),
            label_key="veditor.menu.blade_at_playhead",
        ),
        _action(
            "ripple_delete",
            _label(translator, "veditor.menu.ripple_delete", "Delete (Ripple)"),
            enabled=bool(selected_pairs),
            label_key="veditor.menu.ripple_delete",
        ),
        _action(
            "cleanup_micro_edges",
            "Clean 1-frame gaps/overlaps",
            enabled=(
                _safe_int(edge_summary.get("auto_fixable_count", 0), 0) > 0
                and not bool(getattr(track, "locked", False))
            ),
            tooltip="Close one-frame gaps and trim one-frame overlaps on this track.",
        ),
        _separator("media"),
        _action(
            "extract_audio",
            _label(
                translator,
                "veditor.menu.extract_audio",
                "Extract audio from video",
            ),
            enabled=_track_has_any_source(track),
            label_key="veditor.menu.extract_audio",
        ),
    ]
    if len(selected_pairs) == 1 and selected_clip is not None and audio_tracks_list:
        is_linked = getattr(selected_clip, "linked_audio_id", None) is not None
        rows.extend(
            [
                _separator("audio_link"),
                _action(
                    "toggle_audio_link",
                    "Unlink audio" if is_linked else "Link audio",
                ),
            ]
        )
    rows.extend(
        [
            _separator("reorder"),
            _action("move_track_up", "Move up (raise layer)", enabled=track_index > 0),
            _action(
                "move_track_down",
                "Move down (lower layer)",
                enabled=0 <= track_index < len(tracks_list) - 1,
            ),
            _separator("delete"),
            _action(
                "delete_track",
                _label(translator, "veditor.menu.delete_track", "Delete track"),
                enabled=len(tracks_list) > 1 or bool(audio_tracks_list),
                label_key="veditor.menu.delete_track",
            ),
        ]
    )
    return rows


def build_track_context_menu_model_for_owner(
    owner: Any,
    track: Any,
    *,
    translator: Translator | None = None,
) -> list[MenuRow]:
    edge_summary: Mapping[str, Any] = {}
    summary = getattr(owner, "_timeline_edge_issue_summary", None)
    if callable(summary):
        edge_summary = summary([track], getattr(owner, "_project_settings", None)) or {}
    _selected_track, selected_clip = _selected_video_clip(owner)
    return build_track_context_menu_model(
        track,
        tracks=getattr(owner, "_tracks", []) or [],
        audio_tracks=getattr(owner, "_audio_tracks", []) or [],
        selected_clips=_selected_clip_pairs(owner),
        edge_summary=edge_summary,
        selected_clip=selected_clip,
        translator=translator,
    )


def _extract_audio_target_clip(owner: Any, track_id: int, track: Any) -> Any | None:
    selected = _selected_clip_pairs(owner)
    if len(selected) == 1:
        selected_track_id, selected_clip_id = selected[0]
        if int(selected_track_id) == int(track_id):
            selected_clip = _find_clip(track, int(selected_clip_id))
            if selected_clip is not None:
                return selected_clip
    for candidate in _iter_clips(track):
        if getattr(candidate, "source_path", None) is not None:
            return candidate
    return None


def dispatch_track_context_menu_action(
    owner: Any,
    track_id: int,
    command: str,
    *,
    track: Any | None = None,
) -> bool:
    command = str(command or "")
    track = track if track is not None else find_video_track(owner, int(track_id))
    if track is None:
        return False
    if command == "toggle_audio_link":
        selected_track, selected_clip = _selected_video_clip(owner)
        if selected_track is None or selected_clip is None:
            return False
        return _invoke(owner, "_toggle_audio_link", selected_track, selected_clip)
    if command == "blade_at_playhead":
        return _invoke(owner, "_blade_at_playhead")
    if command == "ripple_delete":
        return _invoke(owner, "_delete_selected_clips")
    if command == "cleanup_micro_edges":
        return _invoke(owner, "_cleanup_timeline_micro_edges", int(track_id))
    if command == "move_track_up":
        return _invoke(owner, "_move_track", int(track_id), -1)
    if command == "move_track_down":
        return _invoke(owner, "_move_track", int(track_id), +1)
    if command == "extract_audio":
        target_clip = _extract_audio_target_clip(owner, int(track_id), track)
        return _invoke(owner, "_extract_audio_from_video_selection", track, target_clip)
    if command == "delete_track":
        return _invoke(owner, "_delete_track", int(track_id))
    return False


def build_audio_row_context_menu_model(
    track: Any,
    *,
    translator: Translator | None = None,
) -> list[MenuRow]:
    if track is None:
        return []
    return [
        _action(
            "delete_audio_track",
            _label(translator, "veditor.audio.ctx.remove", "Delete audio track"),
            label_key="veditor.audio.ctx.remove",
        )
    ]


def dispatch_audio_row_context_menu_action(owner: Any, track_id: int, command: str) -> bool:
    if str(command or "") != "delete_audio_track":
        return False
    return _invoke(owner, "_delete_audio_track", int(track_id))


def audio_clip_has_selection(clip: Any) -> bool:
    return (
        _safe_int(getattr(clip, "selection_start_ms", -1), -1) >= 0
        and _safe_int(getattr(clip, "selection_end_ms", -1), -1)
        > _safe_int(getattr(clip, "selection_start_ms", -1), -1)
    )


def build_audio_clip_context_menu_model(
    clip: Any,
    *,
    translator: Translator | None = None,
) -> list[MenuRow]:
    return [
        _action(
            "cut_selection",
            _label(translator, "veditor.menu.cut_selection", "Cut selection"),
            enabled=audio_clip_has_selection(clip),
            label_key="veditor.menu.cut_selection",
        ),
        _action(
            "clear_cuts",
            _label(translator, "veditor.menu.clear_cuts", "Clear all cuts"),
            enabled=bool(getattr(clip, "cuts", None)),
            label_key="veditor.menu.clear_cuts",
        ),
        _separator("trim"),
        _action(
            "trim_range",
            _label(translator, "veditor.audio.ctx.trim", "Trim range..."),
            label_key="veditor.audio.ctx.trim",
        ),
        _separator("delete"),
        _action(
            "delete_audio_clip",
            _label(translator, "veditor.audio.ctx.delete_clip", "Delete this clip only"),
            label_key="veditor.audio.ctx.delete_clip",
        ),
    ]


def _audio_row_for_track(owner: Any, track: Any) -> Any | None:
    rows = getattr(owner, "_audio_rows", {}) or {}
    getter = getattr(rows, "get", None)
    if callable(getter):
        return getter(_safe_int(getattr(track, "id", 0)))
    return None


def _refresh_audio_after_clip_change(owner: Any, track: Any, *, refresh_row: bool = False) -> None:
    row = _audio_row_for_track(owner, track)
    if row is not None:
        if refresh_row:
            refresh = getattr(row, "refresh_from_track", None)
            if callable(refresh):
                refresh()
            else:
                _call(row, "update")
        else:
            _call(row, "update")
    mixer = getattr(owner, "_audio_mixer", None)
    if mixer is not None:
        _call(mixer, "update_track", track)
    _call(owner, "_refresh_player_tracks")


def trim_audio_clip_to_range(owner: Any, track: Any, clip: Any, start_ms: int, end_ms: int) -> bool:
    if track is None or clip is None:
        return False
    start_ms = max(0, int(start_ms))
    end_ms = max(start_ms + 1, int(end_ms))
    clip.trim_start_ms = start_ms
    clip.trim_end_ms = end_ms
    _refresh_audio_after_clip_change(owner, track)
    return True


def dispatch_audio_clip_context_menu_action(
    owner: Any,
    track: Any,
    clip: Any,
    command: str,
) -> bool:
    if track is None or clip is None:
        return False
    command = str(command or "")
    if command == "cut_selection":
        if not audio_clip_has_selection(clip):
            return False
        return _invoke(owner, "_split_audio_clip", track, clip)
    if command == "clear_cuts":
        cuts = getattr(clip, "cuts", None)
        if not cuts:
            return False
        clear = getattr(cuts, "clear", None)
        if callable(clear):
            clear()
        else:
            clip.cuts = []
        _refresh_audio_after_clip_change(owner, track)
        return True
    if command == "trim_range":
        prompt = getattr(owner, "_prompt_trim_audio_clip", None)
        if callable(prompt):
            return bool(prompt(track, clip) is not False)
        return False
    if command == "delete_audio_clip":
        clips = getattr(track, "clips", None)
        if clips is None:
            return False
        try:
            clips.remove(clip)
        except ValueError:
            return False
        _call(owner, "_remove_clip_from_waveform_jobs", clip)
        _refresh_audio_after_clip_change(owner, track, refresh_row=True)
        return True
    return False


def build_preview_context_menu_model(
    *,
    has_strokes: bool,
    translator: Translator | None = None,
) -> list[MenuRow]:
    return [
        _action(
            "clear_paint_strokes",
            _label(translator, "paint.btn.clear_all", "Clear all"),
            enabled=bool(has_strokes),
            label_key="paint.btn.clear_all",
        )
    ]


def build_preview_context_menu_model_for_owner(
    owner: Any,
    *,
    translator: Translator | None = None,
) -> list[MenuRow]:
    return build_preview_context_menu_model(
        has_strokes=bool(getattr(owner, "_strokes", None)),
        translator=translator,
    )


def dispatch_preview_context_menu_action(owner: Any, command: str) -> bool:
    if str(command or "") != "clear_paint_strokes":
        return False
    strokes = getattr(owner, "_strokes", None)
    if strokes is None:
        return False
    clear = getattr(strokes, "clear", None)
    if callable(clear):
        clear()
    else:
        setattr(owner, "_strokes", [])
    canvas = getattr(owner, "_drawing_canvas", None)
    if canvas is not None:
        _call(canvas, "update")
    return True


__all__ = [
    "MenuRow",
    "audio_clip_has_selection",
    "build_audio_clip_context_menu_model",
    "build_audio_row_context_menu_model",
    "build_clip_badge_menu_model",
    "build_preview_context_menu_model",
    "build_preview_context_menu_model_for_owner",
    "build_track_context_menu_model",
    "build_track_context_menu_model_for_owner",
    "build_video_clip_context_menu_model",
    "clip_has_active_fx",
    "clip_has_disabled_fx",
    "clip_has_transition",
    "dispatch_audio_clip_context_menu_action",
    "dispatch_audio_row_context_menu_action",
    "dispatch_clip_badge_menu_action",
    "dispatch_preview_context_menu_action",
    "dispatch_track_context_menu_action",
    "dispatch_video_clip_context_menu_action",
    "find_video_clip",
    "find_video_track",
    "trim_audio_clip_to_range",
]

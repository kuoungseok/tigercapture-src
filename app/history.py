"""10-step undo / redo history for the video editor.

Two pieces:

- ``HistoryStack`` is a generic bounded stack with a cursor. ``push``
  drops any entries past the cursor (the redo tail) so a fresh edit
  after an undo doesn't leave dangling future state. ``undo`` /
  ``redo`` move the cursor; ``current`` returns the snapshot at the
  cursor. Bounded at ``max_undo_steps + 1`` entries (the +1 is the
  initial state every fresh editor window starts with).

- ``capture_editor_snapshot`` / ``apply_editor_snapshot`` operate on
  the editor instance: they freeze and restore the per-track mutable
  state the user can edit (clips, cuts, fades, speed segments,
  typography, zoom actors, color grade, subtitles, active track id).
  Thumbnails / waveforms are left out — those are lazily rebuilt
  from sources, so omitting them keeps the snapshot size bounded
  AND avoids snapshotting Qt pixmap state that wouldn't deepcopy
  cleanly.

Trigger sites in the editor call ``register_change(label)`` at the
end of a user gesture (cut, clip drag commit, subtitle add/edit/
delete, workbench fade tweak). Mid-gesture transients — e.g. live
``offset_changed`` ticks during a drag — must not call this; the
drag-commit signal is what fires it.
"""
from __future__ import annotations

import copy
from dataclasses import fields, is_dataclass
from types import SimpleNamespace
from typing import Any, Optional


class HistoryStack:
    """Bounded undo/redo stack. ``max_undo_steps=10`` allows 10
    Ctrl+Z presses from the latest state — internally that's 11
    snapshots (initial + 10 changes)."""

    def __init__(self, max_undo_steps: int = 10) -> None:
        self._max_entries: int = int(max_undo_steps) + 1
        self._stack: list[tuple[Any, str]] = []
        self._cursor: int = -1     # index of the snapshot reflecting current state

    def push(self, snapshot: Any, label: str = "") -> None:
        """Append ``snapshot`` after the cursor (dropping any redo
        tail). Trims the head when the stack exceeds capacity."""
        if 0 <= self._cursor < len(self._stack):
            try:
                if self._stack[self._cursor][0] == snapshot:
                    return
            except Exception:
                pass
        # Drop redo tail.
        del self._stack[self._cursor + 1:]
        self._stack.append((snapshot, label))
        # Trim head.
        if len(self._stack) > self._max_entries:
            overflow = len(self._stack) - self._max_entries
            self._stack = self._stack[overflow:]
        self._cursor = len(self._stack) - 1

    def undo(self) -> Optional[Any]:
        """Move the cursor one step back; return the snapshot to
        restore. ``None`` when there's nothing further to undo."""
        if self._cursor <= 0:
            return None
        self._cursor -= 1
        return self._stack[self._cursor][0]

    def redo(self) -> Optional[Any]:
        """Move the cursor one step forward; return the snapshot to
        re-apply. ``None`` when at the head of the stack."""
        if self._cursor >= len(self._stack) - 1:
            return None
        self._cursor += 1
        return self._stack[self._cursor][0]

    def can_undo(self) -> bool:
        return self._cursor > 0

    def can_redo(self) -> bool:
        return self._cursor < len(self._stack) - 1

    def depth(self) -> int:
        """Number of entries currently in the stack."""
        return len(self._stack)

    def labels(self) -> list[str]:
        """All entry labels, oldest first. Useful for an "edit
        history" debug panel; not currently exposed in the UI."""
        return [lbl for _, lbl in self._stack]

    def undo_label(self) -> str:
        """Label of the edit that would be undone next."""
        if self._cursor <= 0 or self._cursor >= len(self._stack):
            return ""
        return str(self._stack[self._cursor][1] or "")

    def redo_label(self) -> str:
        """Label of the edit that would be redone next."""
        idx = self._cursor + 1
        if idx < 0 or idx >= len(self._stack):
            return ""
        return str(self._stack[idx][1] or "")


# ---------------------------------------------------------------------------
#  Per-track state capture
# ---------------------------------------------------------------------------


# Fields snapshot/restored by ``serialize_video_track`` /
# ``apply_video_track_state``. Each field is independently
# deep-copied so mutations after an undo can't leak back through
# the snapshot's references. ``thumbnails`` is intentionally NOT
# in this list — pixmaps don't deepcopy and they're rebuilt lazily
# from the source by the thumbnail extractor.
_VIDEO_TRACK_FIELDS = (
    "source_path",
    "duration_ms",
    "offset_ms",
    "speed_segments",
    "cuts",
    "fades",
    "selection_start_ms",
    "selection_end_ms",
    "typography_actors",
    "zoom_actors",
    "clips",
    "node_graph",
)


def _is_qt_render_value(value: Any) -> bool:
    """Return True for transient Qt image/icon values that history must skip."""
    if value is None:
        return False
    cls = type(value)
    module = str(getattr(cls, "__module__", ""))
    name = str(getattr(cls, "__name__", ""))
    return module.startswith("PySide6.") and name in {"QPixmap", "QImage", "QIcon", "QPicture"}


def _history_copy(value: Any, *, _memo: dict[int, Any] | None = None) -> Any:
    """Deep-copy editable state while dropping derived Qt render caches."""
    if _memo is None:
        _memo = {}
    if _is_qt_render_value(value):
        return None
    if isinstance(value, (str, bytes, int, float, bool, type(None))):
        return value
    obj_id = id(value)
    if obj_id in _memo:
        return _memo[obj_id]
    if isinstance(value, list):
        out: list[Any] = []
        _memo[obj_id] = out
        for item in value:
            copied = _history_copy(item, _memo=_memo)
            if copied is not None:
                out.append(copied)
        return out
    if isinstance(value, tuple):
        out = tuple(
            copied
            for copied in (_history_copy(item, _memo=_memo) for item in value)
            if copied is not None
        )
        _memo[obj_id] = out
        return out
    if isinstance(value, set):
        out: set[Any] = set()
        _memo[obj_id] = out
        for item in value:
            copied = _history_copy(item, _memo=_memo)
            if copied is not None:
                out.add(copied)
        return out
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        _memo[obj_id] = out
        for key, item in value.items():
            copied_key = _history_copy(key, _memo=_memo)
            copied_value = _history_copy(item, _memo=_memo)
            if copied_key is not None and copied_value is not None:
                out[copied_key] = copied_value
        return out
    if is_dataclass(value) and not isinstance(value, type):
        clone = copy.copy(value)
        _memo[obj_id] = clone
        for field in fields(value):
            field_value = [] if field.name == "thumbnails" else _history_copy(getattr(value, field.name), _memo=_memo)
            try:
                object.__setattr__(clone, field.name, field_value)
            except Exception:
                pass
        return clone
    if hasattr(value, "__dict__") and not str(type(value).__module__).startswith("PySide6."):
        try:
            clone = copy.copy(value)
        except Exception:
            return value
        _memo[obj_id] = clone
        for name, item in vars(value).items():
            copied = [] if name == "thumbnails" else _history_copy(item, _memo=_memo)
            try:
                setattr(clone, name, copied)
            except Exception:
                pass
        return clone
    try:
        return copy.deepcopy(value)
    except Exception:
        return value


def serialize_video_track(track) -> dict:
    """Capture the editable state of a single legacy ``VideoTrack``."""
    snap: dict = {"id": int(track.id), "__track_class__": type(track)}
    for field in _VIDEO_TRACK_FIELDS:
        value = getattr(track, field, None)
        snap[field] = _history_copy(value)
    return snap


def apply_video_track_state(track, snap: dict) -> None:
    """Write a snapshot back onto ``track``. ID must already match —
    this assumes the caller has already paired snapshots to tracks."""
    for field in _VIDEO_TRACK_FIELDS:
        if field in snap:
            setattr(track, field, _history_copy(snap[field]))


# ---------------------------------------------------------------------------
#  Per-track audio state — separate because the AudioTrack shape
#  diverges from the legacy VideoTrack (its mutation is via
#  ``track.clips: list[AudioClip]`` already).
# ---------------------------------------------------------------------------


_AUDIO_TRACK_FIELDS = (
    "volume",
    "pan",
    "muted",
    "solo",
    "label",
    "bus_id",
    "track_type",
    "insert_slots",
    "sends",
    "automation_read",
    "automation_write",
    "automation_points",
    "automation_lanes",
    "clips",
)


def serialize_audio_track(track) -> dict:
    snap: dict = {"id": int(track.id), "__track_class__": type(track)}
    for field in _AUDIO_TRACK_FIELDS:
        if hasattr(track, field):
            snap[field] = _history_copy(getattr(track, field))
    return snap


def apply_audio_track_state(track, snap: dict) -> None:
    for field in _AUDIO_TRACK_FIELDS:
        if field in snap:
            setattr(track, field, _history_copy(snap[field]))


# ---------------------------------------------------------------------------
#  Editor-level capture / restore
# ---------------------------------------------------------------------------


def capture_editor_snapshot(editor) -> dict:
    """Freeze the editor's per-track + per-overlay mutable state into
    a plain dict. Returned dict is safe to keep across mutations —
    it's fully deep-copied. Doesn't capture playback position,
    selection-row text, or thumbnails (all of those are derived /
    transient state that the user wouldn't expect undo to revert)."""
    video_tracks = [
        serialize_video_track(t)
        for t in getattr(editor, "_tracks", [])
    ]
    audio_tracks = [
        serialize_audio_track(t)
        for t in getattr(editor, "_audio_tracks", [])
    ]
    subtitles: list = []
    panel = getattr(editor, "_subtitle_panel", None)
    if panel is not None and hasattr(panel, "layer"):
        subtitles = [_history_copy(s) for s in panel.layer.items()]
    return {
        "video_tracks": video_tracks,
        "audio_tracks": audio_tracks,
        "subtitles": subtitles,
        "active_track_id": getattr(editor, "_active_track_id", None),
        "timeline_markers": _history_copy(getattr(editor, "_timeline_markers", [])),
        "audio_mixer_snapshots": _history_copy(getattr(editor, "_audio_mixer_snapshots", [])),
        "spine_actor_tracks": _history_copy(getattr(editor, "_spine_actor_tracks", [])),
        "live2d_actor_tracks": _history_copy(getattr(editor, "_live2d_actor_tracks", [])),
        "ar_pbr_tracks": _history_copy(getattr(editor, "_ar_pbr_tracks", [])),
        "motion_compositions": [
            item.to_dict() if hasattr(item, "to_dict") else _history_copy(item)
            for item in (getattr(editor, "_motion_compositions", {}) or {}).values()
        ],
        "motion_clips": _history_copy(getattr(editor, "_motion_clips", [])),
        "selected_clips": _history_copy(getattr(editor, "_selected_clips", [])),
        "px_per_sec": getattr(editor, "_px_per_sec", None),
        "playhead_ms": _safe_player_position(editor),
    }


def apply_editor_snapshot(editor, snap: dict) -> None:
    """Restore a snapshot, including track add/remove/order."""
    removed_video_ids = _restore_track_collection(
        editor,
        attr_name="_tracks",
        row_map_name="_track_rows",
        insert_widget_name="_insert_track_widget",
        snap_tracks=snap.get("video_tracks", []),
        apply_state=apply_video_track_state,
    )
    removed_audio_ids = _restore_track_collection(
        editor,
        attr_name="_audio_tracks",
        row_map_name="_audio_rows",
        insert_widget_name="_insert_audio_track_widget",
        snap_tracks=snap.get("audio_tracks", []),
        apply_state=apply_audio_track_state,
    )
    _sync_audio_mixer(editor, removed_audio_ids)
    _reorder_timeline_rows(editor)
    _sync_next_ids(editor)
    # Video tracks — match by id, apply state.
    track_by_id = {t.id: t for t in getattr(editor, "_tracks", [])}
    for snap_track in snap.get("video_tracks", []):
        live = track_by_id.get(snap_track["id"])
        if live is not None:
            apply_video_track_state(live, snap_track)
    # Audio tracks — same pattern.
    audio_by_id = {t.id: t for t in getattr(editor, "_audio_tracks", [])}
    for snap_track in snap.get("audio_tracks", []):
        live = audio_by_id.get(snap_track["id"])
        if live is not None:
            apply_audio_track_state(live, snap_track)
    if "audio_mixer_snapshots" in snap:
        editor._audio_mixer_snapshots = _history_copy(snap.get("audio_mixer_snapshots", []))
    # Subtitles — wholesale replace.
    panel = getattr(editor, "_subtitle_panel", None)
    if panel is not None and hasattr(panel, "layer"):
        panel.layer.replace_all(snap.get("subtitles", []))
        # Keep the panel list view in sync (replace_all only fires
        # the layer's on_change; the list refresh hooks the panel's
        # subtitles_changed signal which we emit next).
        if hasattr(panel, "_refresh_list"):
            panel._refresh_list()
        if hasattr(panel, "subtitles_changed"):
            panel.subtitles_changed.emit()
    # Active track id — only restore if the track still exists.
    new_active = snap.get("active_track_id")
    if new_active in track_by_id and hasattr(editor, "_set_active_track"):
        try:
            editor._set_active_track(new_active)
        except Exception:
            pass
    # Timeline markers.
    if "timeline_markers" in snap and hasattr(editor, "_timeline_markers"):
        editor._timeline_markers = _history_copy(snap.get("timeline_markers", []))
        _call_if_present(editor, "_sync_markers_to_ruler")

    # Actor lanes. These are plain dataclasses, so a deepcopy is enough to
    # restore the editable state. Rebuild rows/player bindings when the editor
    # exposes the relevant refresh hooks.
    if "spine_actor_tracks" in snap and hasattr(editor, "_spine_actor_tracks"):
        editor._spine_actor_tracks = _history_copy(snap.get("spine_actor_tracks", []))
        _call_if_present(editor, "_rebuild_spine_actor_lanes")
    if "live2d_actor_tracks" in snap and hasattr(editor, "_live2d_actor_tracks"):
        editor._live2d_actor_tracks = _history_copy(snap.get("live2d_actor_tracks", []))
        _call_if_present(editor, "_rebuild_live2d_actor_lanes")
    if "ar_pbr_tracks" in snap and hasattr(editor, "_ar_pbr_tracks"):
        editor._ar_pbr_tracks = _history_copy(snap.get("ar_pbr_tracks", []))
        _call_if_present(editor, "_sync_ar_pbr_tracks_to_player")
        _call_if_present(editor, "_refresh_player_tracks")
    if "motion_compositions" in snap and hasattr(editor, "_motion_compositions"):
        try:
            from app.motion_designer.schema import MotionComposition
            values = [MotionComposition.from_dict(item) for item in snap.get("motion_compositions", [])]
            editor._motion_compositions = {item.id: item for item in values}
        except Exception:
            editor._motion_compositions = {}
    if "motion_clips" in snap and hasattr(editor, "_motion_clips"):
        editor._motion_clips = _history_copy(snap.get("motion_clips", []))
        _call_if_present(editor, "_rebuild_motion_lanes")
        _call_if_present(editor, "_sync_motion_state_to_player")

    if "selected_clips" in snap:
        _restore_selected_clips(editor, snap.get("selected_clips", []))

    px = snap.get("px_per_sec", None)
    if px is not None and hasattr(editor, "_px_per_sec"):
        try:
            editor._px_per_sec = float(px)
            _refresh_timeline_zoom(editor, float(px))
        except Exception:
            pass

    playhead_ms = snap.get("playhead_ms", None)
    if playhead_ms is not None:
        try:
            player = getattr(editor, "_player", None)
            if player is not None and hasattr(player, "set_position"):
                player.set_position(int(playhead_ms))
        except Exception:
            pass

    _restore_active_track_id(editor, snap.get("active_track_id"))
    _refresh_actor_player_tracks(editor)
    _stop_removed_video_extractors(editor, removed_video_ids)


def _new_track_from_snapshot(snap: dict[str, Any], fallback_cls: type | None):
    track_id = int(snap.get("id", 0) or 0)
    cls = snap.get("__track_class__") or fallback_cls
    if cls is not None:
        for args, kwargs in (((), {"id": track_id}), ((track_id,), {})):
            try:
                return cls(*args, **kwargs)
            except Exception:
                pass
    return SimpleNamespace(id=track_id)


def _restore_track_collection(
    editor,
    *,
    attr_name: str,
    row_map_name: str,
    insert_widget_name: str,
    snap_tracks: list[dict[str, Any]],
    apply_state,
) -> set[int]:
    live_tracks = list(getattr(editor, attr_name, []) or [])
    live_by_id = {
        int(getattr(track, "id")): track
        for track in live_tracks
        if hasattr(track, "id")
    }
    snap_ids = [int(row.get("id", 0) or 0) for row in snap_tracks]
    snap_id_set = set(snap_ids)
    removed_ids = set(live_by_id) - snap_id_set
    fallback_cls = type(live_tracks[0]) if live_tracks else None
    restored = []
    created_ids: set[int] = set()

    for snap_track in snap_tracks:
        track_id = int(snap_track.get("id", 0) or 0)
        track = live_by_id.get(track_id)
        if track is None:
            track = _new_track_from_snapshot(snap_track, fallback_cls)
            created_ids.add(track_id)
        apply_state(track, snap_track)
        restored.append(track)

    setattr(editor, attr_name, restored)

    for track_id in removed_ids:
        _detach_timeline_row(editor, row_map_name, track_id)

    row_map = getattr(editor, row_map_name, None)
    insert_widget = getattr(editor, insert_widget_name, None)
    if isinstance(row_map, dict) and callable(insert_widget):
        for track in restored:
            track_id = int(getattr(track, "id", 0) or 0)
            if track_id in created_ids or track_id not in row_map:
                try:
                    insert_widget(track)
                except Exception:
                    pass

    return removed_ids


def _detach_timeline_row(editor, row_map_name: str, track_id: int) -> None:
    row_map = getattr(editor, row_map_name, None)
    row = None
    if isinstance(row_map, dict):
        row = row_map.pop(int(track_id), None)
    if row is None:
        return
    layout = getattr(editor, "_tracks_layout", None)
    if layout is not None and hasattr(layout, "removeWidget"):
        try:
            layout.removeWidget(row)
        except Exception:
            pass
    if hasattr(row, "setParent"):
        try:
            row.setParent(None)
        except Exception:
            pass
    if hasattr(row, "deleteLater"):
        try:
            row.deleteLater()
        except Exception:
            pass


def _reorder_timeline_rows(editor) -> None:
    layout = getattr(editor, "_tracks_layout", None)
    if layout is None or not hasattr(layout, "insertWidget"):
        return
    rows = []
    track_rows = getattr(editor, "_track_rows", None)
    if isinstance(track_rows, dict):
        for track in getattr(editor, "_tracks", []) or []:
            row = track_rows.get(int(getattr(track, "id", -1)))
            if row is not None:
                rows.append(row)
    audio_rows = getattr(editor, "_audio_rows", None)
    if isinstance(audio_rows, dict):
        for track in getattr(editor, "_audio_tracks", []) or []:
            row = audio_rows.get(int(getattr(track, "id", -1)))
            if row is not None:
                rows.append(row)
    if not rows:
        return
    for row in rows:
        try:
            layout.removeWidget(row)
        except Exception:
            pass
    try:
        insert_idx = max(0, int(layout.count()) - 1)
    except Exception:
        insert_idx = 0
    for row in rows:
        try:
            layout.insertWidget(insert_idx, row)
            insert_idx += 1
        except Exception:
            pass
    for name in ("invalidate", "activate"):
        fn = getattr(layout, name, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass


def _sync_audio_mixer(editor, removed_audio_ids: set[int]) -> None:
    mixer = getattr(editor, "_audio_mixer", None)
    if mixer is not None:
        for track_id in removed_audio_ids:
            try:
                mixer.remove_track(int(track_id))
            except Exception:
                pass
        for track in getattr(editor, "_audio_tracks", []) or []:
            try:
                if hasattr(mixer, "update_track"):
                    mixer.update_track(track)
                elif hasattr(mixer, "add_track"):
                    mixer.add_track(track)
            except Exception:
                pass
    panel = getattr(editor, "_audio_mixer_panel", None)
    if panel is not None and hasattr(panel, "rebuild"):
        try:
            if not hasattr(panel, "isVisible") or panel.isVisible():
                panel.rebuild(getattr(editor, "_audio_tracks", []))
        except Exception:
            pass


def _stop_removed_video_extractors(editor, removed_video_ids: set[int]) -> None:
    extractors = getattr(editor, "_extractors", None)
    if not isinstance(extractors, dict):
        return
    for track_id in removed_video_ids:
        ex = extractors.pop(int(track_id), None)
        if ex is None:
            continue
        for name in ("stop", "deleteLater"):
            fn = getattr(ex, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass


def _sync_next_ids(editor) -> None:
    tracks = list(getattr(editor, "_tracks", []) or []) + list(getattr(editor, "_audio_tracks", []) or [])
    max_track_id = max((int(getattr(t, "id", 0) or 0) for t in tracks), default=0)
    if hasattr(editor, "_next_track_id"):
        try:
            editor._next_track_id = max(int(editor._next_track_id), max_track_id + 1)
        except Exception:
            editor._next_track_id = max_track_id + 1
    max_audio_clip_id = 0
    for track in getattr(editor, "_audio_tracks", []) or []:
        for clip in getattr(track, "clips", []) or []:
            max_audio_clip_id = max(max_audio_clip_id, int(getattr(clip, "id", 0) or 0))
    if max_audio_clip_id and hasattr(editor, "_next_audio_clip_id"):
        try:
            editor._next_audio_clip_id = max(int(editor._next_audio_clip_id), max_audio_clip_id + 1)
        except Exception:
            editor._next_audio_clip_id = max_audio_clip_id + 1


def _restore_selected_clips(editor, selected_clips) -> None:
    if not hasattr(editor, "_selected_clips"):
        return
    live_keys: set[tuple[int, int]] = set()
    for track in getattr(editor, "_tracks", []) or []:
        try:
            track_id = int(getattr(track, "id"))
        except Exception:
            continue
        for clip in getattr(track, "clips", []) or []:
            try:
                live_keys.add((track_id, int(getattr(clip, "id"))))
            except Exception:
                continue

    restored: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for raw in selected_clips or []:
        try:
            track_id, clip_id = raw
            key = (int(track_id), int(clip_id))
        except Exception:
            continue
        if key in live_keys and key not in seen:
            restored.append(key)
            seen.add(key)
    editor._selected_clips = restored

    broadcaster = getattr(editor, "_broadcast_clip_selection", None)
    if callable(broadcaster):
        try:
            broadcaster()
            return
        except Exception:
            pass

    per_track: dict[int, set[int]] = {}
    for track_id, clip_id in restored:
        per_track.setdefault(int(track_id), set()).add(int(clip_id))
    row_map = getattr(editor, "_track_rows", None)
    if isinstance(row_map, dict):
        for track_id, row in row_map.items():
            try:
                row.set_selected_clip_ids(per_track.get(int(track_id), set()))
                row.update()
            except Exception:
                pass


def _restore_active_track_id(editor, track_id) -> None:
    live_ids = {
        int(getattr(t, "id"))
        for t in list(getattr(editor, "_tracks", []) or []) + list(getattr(editor, "_audio_tracks", []) or [])
        if hasattr(t, "id")
    }
    if track_id in live_ids:
        _set_active_track_safely(editor, int(track_id))
        return
    if hasattr(editor, "_active_track_id"):
        fallback = next(iter(live_ids), None)
        if fallback is None:
            editor._active_track_id = None
        else:
            _set_active_track_safely(editor, int(fallback))


def _set_active_track_safely(editor, track_id: int) -> None:
    setter = getattr(editor, "_set_active_track", None)
    if callable(setter):
        try:
            setter(int(track_id))
            return
        except Exception:
            pass
    if hasattr(editor, "_active_track_id"):
        editor._active_track_id = int(track_id)


def _safe_player_position(editor) -> int | None:
    player = getattr(editor, "_player", None)
    if player is None or not hasattr(player, "position"):
        return None
    try:
        return int(player.position())
    except Exception:
        return None


def _call_if_present(editor, name: str) -> None:
    fn = getattr(editor, name, None)
    if not callable(fn):
        return
    try:
        fn()
    except Exception:
        pass


def _refresh_actor_player_tracks(editor) -> None:
    player = getattr(editor, "_player", None)
    if player is not None:
        try:
            if hasattr(player, "set_spine_actor_tracks"):
                player.set_spine_actor_tracks(getattr(editor, "_spine_actor_tracks", []))
            if hasattr(player, "set_live2d_actor_tracks"):
                player.set_live2d_actor_tracks(getattr(editor, "_live2d_actor_tracks", []))
        except Exception:
            pass
    _call_if_present(editor, "_refresh_player_tracks")


def _refresh_timeline_zoom(editor, px_per_sec: float) -> None:
    for row_map_name in ("_track_rows", "_audio_rows"):
        row_map = getattr(editor, row_map_name, None)
        if isinstance(row_map, dict):
            for row in row_map.values():
                if hasattr(row, "set_px_per_sec"):
                    try:
                        row.set_px_per_sec(px_per_sec)
                    except Exception:
                        pass
    for row_list_name in ("_actor_lane_rows", "_live2d_lane_rows", "_motion_lane_rows"):
        rows = getattr(editor, row_list_name, None)
        if rows:
            for row in rows:
                if hasattr(row, "set_px_per_sec"):
                    try:
                        row.set_px_per_sec(px_per_sec)
                    except Exception:
                        pass
    ruler = getattr(editor, "_timeline_ruler", None)
    if ruler is not None and hasattr(ruler, "set_px_per_sec"):
        try:
            ruler.set_px_per_sec(px_per_sec)
        except Exception:
            pass
    subtitle_lane = getattr(editor, "_subtitle_lane", None)
    if subtitle_lane is not None and hasattr(subtitle_lane, "set_px_per_sec"):
        try:
            subtitle_lane.set_px_per_sec(px_per_sec)
        except Exception:
            pass

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


def serialize_video_track(track) -> dict:
    """Capture the editable state of a single legacy ``VideoTrack``."""
    snap: dict = {"id": int(track.id)}
    for field in _VIDEO_TRACK_FIELDS:
        value = getattr(track, field, None)
        snap[field] = copy.deepcopy(value)
    return snap


def apply_video_track_state(track, snap: dict) -> None:
    """Write a snapshot back onto ``track``. ID must already match —
    this assumes the caller has already paired snapshots to tracks."""
    for field in _VIDEO_TRACK_FIELDS:
        if field in snap:
            setattr(track, field, copy.deepcopy(snap[field]))


# ---------------------------------------------------------------------------
#  Per-track audio state — separate because the AudioTrack shape
#  diverges from the legacy VideoTrack (its mutation is via
#  ``track.clips: list[AudioClip]`` already).
# ---------------------------------------------------------------------------


_AUDIO_TRACK_FIELDS = (
    "volume",
    "clips",
)


def serialize_audio_track(track) -> dict:
    snap: dict = {"id": int(track.id)}
    for field in _AUDIO_TRACK_FIELDS:
        if hasattr(track, field):
            snap[field] = copy.deepcopy(getattr(track, field))
    return snap


def apply_audio_track_state(track, snap: dict) -> None:
    for field in _AUDIO_TRACK_FIELDS:
        if field in snap:
            setattr(track, field, copy.deepcopy(snap[field]))


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
        subtitles = [copy.deepcopy(s) for s in panel.layer.items()]
    return {
        "video_tracks": video_tracks,
        "audio_tracks": audio_tracks,
        "subtitles": subtitles,
        "active_track_id": getattr(editor, "_active_track_id", None),
    }


def apply_editor_snapshot(editor, snap: dict) -> None:
    """Restore the editor to the state recorded by
    ``capture_editor_snapshot``. Tracks are matched by id; tracks
    present in the snapshot but not in the editor are skipped (Phase
    1 scope: undo doesn't re-create deleted tracks). Subtitle layer
    is wholesale replaced so the panel + ruler markers + lane row
    refresh through the layer's ``on_change`` hook."""
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

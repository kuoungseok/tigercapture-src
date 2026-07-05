from __future__ import annotations

from app.editor_observability import append_ux_event as _append_ux_event
from app.history import apply_editor_snapshot, capture_editor_snapshot


def _register_change(self, label: str = "") -> None:
    """Capture the editor's state and push it onto the history stack."""
    if self._history_suspended:
        return
    self._history.push(capture_editor_snapshot(self), label=label)
    self._autosave_dirty = True


def _on_undo(self) -> None:
    detail = ""
    try:
        detail = self._history.undo_label()
    except Exception:
        detail = ""
    snap = self._history.undo()
    if snap is None:
        self._flash_status("Nothing to undo")
        return
    self._apply_history_snapshot(snap)
    self._show_history_feedback("Undo", detail)
    _append_ux_event("history.undo", label=detail)


def _on_redo(self) -> None:
    detail = ""
    try:
        detail = self._history.redo_label()
    except Exception:
        detail = ""
    snap = self._history.redo()
    if snap is None:
        self._flash_status("Nothing to redo")
        return
    self._apply_history_snapshot(snap)
    self._show_history_feedback("Redo", detail)
    _append_ux_event("history.redo", label=detail)


def _show_history_feedback(self, label: str, detail: str = "") -> None:
    msg = str(label or "History")
    if detail:
        msg = f"{msg}: {detail}"
    self._flash_status(msg)
    try:
        self._update_timeline_status()
    except Exception:
        pass
    row = getattr(self, "_track_rows", {}).get(getattr(self, "_active_track_id", None))
    if row is None:
        return
    try:
        pos = int(self._player.position()) if hasattr(self, "_player") else 0
    except Exception:
        pos = 0
    try:
        row.flash_timeline_burst(str(label or "history").casefold(), pos)
    except Exception:
        try:
            row.update()
        except Exception:
            pass


def _apply_history_snapshot(self, snap) -> None:
    """Restore a captured editor snapshot and refresh dependent views."""
    self._clear_preset_live_preview()
    self._history_suspended = True
    try:
        apply_editor_snapshot(self, snap)
        for row in self._track_rows.values():
            row._recalc_width()
            row.update()
        for row in self._audio_rows.values():
            row.refresh_from_track()
        self._refresh_player_tracks()
        self._refresh_workbench()
        self._update_subtitle_overlay(self._player.position())
        if hasattr(self, "_subtitle_lane"):
            self._subtitle_lane.update()
        self._update_tracks_host_width()
    finally:
        self._history_suspended = False

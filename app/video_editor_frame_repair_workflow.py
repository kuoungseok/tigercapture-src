from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu, QPushButton

from app.icons import app_icon, icon_size
from app.video_editor_transport_workflow import _timeline_frame_ms
from app.video_editor_workflow_targeting import workflow_target_video_clip


def _frame_repair_settings(self) -> dict:
    settings = getattr(self, "_frame_repair_settings", None)
    if not isinstance(settings, dict):
        settings = {
            "enabled": False,
            "frame_count": 1,
            "algorithm": "optical_flow",
            "last_range": None,
        }
        self._frame_repair_settings = settings
    return settings


def _frame_repair_frame_ms(self) -> int:
    return _timeline_frame_ms(getattr(self, "_project_settings", {}) or {})


def _frame_repair_snap_ms(self, ms: int) -> int:
    frame_ms = max(1, _frame_repair_frame_ms(self))
    return max(0, int(ms) // frame_ms * frame_ms)


def _frame_repair_current_range(self) -> tuple[int, int, int]:
    settings = _frame_repair_settings(self)
    frame_count = max(1, int(settings.get("frame_count", 1) or 1))
    player = getattr(self, "_player", None)
    pos = int(player.position()) if player is not None and hasattr(player, "position") else 0
    start = _frame_repair_snap_ms(self, pos)
    end = start + frame_count * _frame_repair_frame_ms(self)
    return start, end, frame_count


def _frame_repair_target_clip(self) -> tuple[Any | None, Any | None]:
    track, clip = workflow_target_video_clip(self)
    if track is None or clip is None:
        return None, None
    return track, clip


def _frame_repair_set_frame_count(self, count: int) -> None:
    settings = _frame_repair_settings(self)
    settings["frame_count"] = max(1, min(24, int(count)))
    _frame_repair_select_current(self)
    _frame_repair_flash_selection(self)


def _frame_repair_select_current(self) -> tuple[int, int, int]:
    start, end, frame_count = _frame_repair_current_range(self)
    settings = _frame_repair_settings(self)
    settings["last_range"] = {"start_ms": start, "end_ms": end, "frame_count": frame_count}
    return start, end, frame_count


def _frame_repair_flash_selection(self) -> None:
    start, end, frame_count = _frame_repair_select_current(self)
    flash = getattr(self, "_flash_status", None)
    if callable(flash):
        flash(f"Frame Fix: {frame_count} frame(s) selected at {start}-{end} ms")


def _frame_repair_sync_button(self) -> None:
    btn = getattr(self, "frame_repair_btn", None)
    if btn is None:
        return
    enabled = bool(_frame_repair_settings(self).get("enabled", False))
    btn.blockSignals(True)
    try:
        btn.setChecked(enabled)
    finally:
        btn.blockSignals(False)
    btn.setToolTip(
        "Frame Fix mode: wheel over the viewer to step frames; click to repair the current frame."
        if enabled
        else "Enable Frame Fix mode"
    )


def _toggle_frame_repair_mode(self, checked: bool | None = None) -> None:
    settings = _frame_repair_settings(self)
    enabled = (not bool(settings.get("enabled"))) if checked is None else bool(checked)
    settings["enabled"] = enabled
    _frame_repair_sync_button(self)
    flash = getattr(self, "_flash_status", None)
    if callable(flash):
        flash("Frame Fix mode on: wheel steps frames, click opens repair actions" if enabled else "Frame Fix mode off")


def _frame_repair_add_clip_repair(self, *, method: str, algorithm: str = "optical_flow") -> bool:
    track, clip = _frame_repair_target_clip(self)
    if track is None or clip is None:
        flash = getattr(self, "_flash_status", None)
        if callable(flash):
            flash("Frame Fix: no video clip under the playhead")
        return False
    start, end, frame_count = _frame_repair_select_current(self)
    clip_start = int(getattr(clip, "timeline_in_ms", 0))
    clip_end = int(getattr(clip, "timeline_out_ms", clip_start))
    if start < clip_start or start >= clip_end:
        flash = getattr(self, "_flash_status", None)
        if callable(flash):
            flash("Frame Fix: selected frame is outside the target clip")
        return False
    end = min(end, clip_end)
    source_start = int(clip.timeline_to_source_ms(start)) if hasattr(clip, "timeline_to_source_ms") else start - clip_start
    source_end = int(clip.timeline_to_source_ms(end)) if hasattr(clip, "timeline_to_source_ms") else source_start + (end - start)
    registry_fn = getattr(self, "_ensure_python_action_registry", None)
    if not callable(registry_fn):
        flash = getattr(self, "_flash_status", None)
        if callable(flash):
            flash("Frame Fix: action registry is unavailable")
        return False
    result = registry_fn().execute(
        "clip.frame_repair.add",
        {
            "track_id": int(getattr(track, "id", -1)),
            "clip_id": int(getattr(clip, "id", -1)),
            "source_start_ms": source_start,
            "source_end_ms": max(source_start + 1, source_end),
            "method": method,
            "algorithm": algorithm,
            "label": f"{frame_count} frame repair",
        },
    )
    if not bool(getattr(result, "ok", False)):
        flash = getattr(self, "_flash_status", None)
        if callable(flash):
            flash(f"Frame Fix failed: {getattr(result, 'error', '')}")
        return False
    flash = getattr(self, "_flash_status", None)
    if callable(flash):
        flash(f"Frame Fix: {frame_count} frame(s) repaired")
    return True


def _frame_repair_interpolate_selected(self) -> bool:
    algorithm = str(_frame_repair_settings(self).get("algorithm") or "optical_flow")
    return _frame_repair_add_clip_repair(self, method="interpolate", algorithm=algorithm)


def _frame_repair_hold_previous_selected(self) -> bool:
    return _frame_repair_add_clip_repair(self, method="hold_previous")


def _frame_repair_hold_next_selected(self) -> bool:
    return _frame_repair_add_clip_repair(self, method="hold_next")


def _frame_repair_extract_selected(self) -> bool:
    track, clip = _frame_repair_target_clip(self)
    if track is None or clip is None:
        flash = getattr(self, "_flash_status", None)
        if callable(flash):
            flash("Frame Fix: no video clip under the playhead")
        return False
    start, end, frame_count = _frame_repair_select_current(self)
    start = max(start, int(getattr(clip, "timeline_in_ms", start)))
    end = min(end, int(getattr(clip, "timeline_out_ms", end)))
    if end <= start:
        return False
    registry_fn = getattr(self, "_ensure_python_action_registry", None)
    if not callable(registry_fn):
        return False
    result = registry_fn().execute(
        "timeline.extract",
        {
            "start_ms": int(start),
            "end_ms": int(end),
            "track_id": int(getattr(track, "id", -1)),
        },
        confirm_destructive=True,
    )
    ok = bool(getattr(result, "ok", False))
    flash = getattr(self, "_flash_status", None)
    if callable(flash):
        flash(f"Frame Fix: extracted {frame_count} frame(s)" if ok else f"Frame Fix failed: {getattr(result, 'error', '')}")
    return ok


def _show_frame_repair_popover(self, global_pos=None) -> None:
    _frame_repair_select_current(self)
    menu = QMenu(self)
    start, end, frame_count = _frame_repair_current_range(self)
    menu.addSection(f"Frame Fix: {frame_count} frame(s)")
    interpolate = menu.addAction("Interpolate Repair")
    interpolate.setToolTip("Replace selected bad frame(s) with optical-flow interpolation. Duration and audio stay unchanged.")
    hold_prev = menu.addAction("Hold Previous Frame")
    hold_next = menu.addAction("Hold Next Frame")
    menu.addSeparator()
    length_menu = menu.addMenu("Selection Length")
    for count in (1, 2, 3, 5, 10):
        act = length_menu.addAction(f"{count} frame{'s' if count != 1 else ''}")
        act.setCheckable(True)
        act.setChecked(count == frame_count)
        act.triggered.connect(lambda _checked=False, c=count: _frame_repair_set_frame_count(self, c))
    algorithm_menu = menu.addMenu("Interpolation Quality")
    optical = algorithm_menu.addAction("Optical Flow")
    optical.setCheckable(True)
    optical.setChecked(str(_frame_repair_settings(self).get("algorithm")) == "optical_flow")
    optical.triggered.connect(lambda _checked=False: _frame_repair_settings(self).__setitem__("algorithm", "optical_flow"))
    linear = algorithm_menu.addAction("Linear Fallback")
    linear.setCheckable(True)
    linear.setChecked(str(_frame_repair_settings(self).get("algorithm")) == "linear")
    linear.triggered.connect(lambda _checked=False: _frame_repair_settings(self).__setitem__("algorithm", "linear"))
    menu.addSeparator()
    extract = menu.addAction("Delete and Ripple")
    extract.setToolTip("Remove selected frame(s) and pull later frames left. This shortens the video track.")

    chosen = menu.exec(global_pos or QCursor.pos())
    if chosen is interpolate:
        _frame_repair_interpolate_selected(self)
    elif chosen is hold_prev:
        _frame_repair_hold_previous_selected(self)
    elif chosen is hold_next:
        _frame_repair_hold_next_selected(self)
    elif chosen is extract:
        _frame_repair_extract_selected(self)


def _handle_frame_repair_preview_event(self, obj, event) -> bool:
    settings = _frame_repair_settings(self)
    if not bool(settings.get("enabled", False)):
        return False
    if obj not in (
        getattr(self, "_preview_host", None),
        getattr(self, "_preview_label", None),
        getattr(self, "_preview_gl", None),
    ):
        return False
    if event.type() == QEvent.Type.Wheel:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return False
        delta = event.angleDelta().y()
        if delta == 0:
            return True
        amount = 5 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        direction = -1 if delta > 0 else 1
        step = getattr(self, "_step_timeline_frames", None)
        if callable(step):
            step(direction * amount)
            _frame_repair_select_current(self)
        return True
    if event.type() == QEvent.Type.MouseButtonPress and event.button() in (
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.RightButton,
    ):
        _show_frame_repair_popover(self, event.globalPosition().toPoint())
        return True
    return False


def install_frame_repair_transport_button(self, transport) -> None:
    self.frame_repair_btn = QPushButton("Frame Fix")
    self.frame_repair_btn.setObjectName("ViewerDropdownButton")
    self.frame_repair_btn.setCheckable(True)
    self.frame_repair_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.frame_repair_btn.setFixedSize(76, 30)
    self.frame_repair_btn.setIcon(app_icon("spark", size=12, color="#D7DAE7"))
    self.frame_repair_btn.setIconSize(icon_size(12))
    self.frame_repair_btn.clicked.connect(self._toggle_frame_repair_mode)
    _frame_repair_sync_button(self)
    transport.addWidget(self.frame_repair_btn)


__all__ = [
    "_frame_repair_extract_selected",
    "_frame_repair_flash_selection",
    "_frame_repair_hold_next_selected",
    "_frame_repair_hold_previous_selected",
    "_frame_repair_interpolate_selected",
    "_frame_repair_select_current",
    "_frame_repair_set_frame_count",
    "_handle_frame_repair_preview_event",
    "_show_frame_repair_popover",
    "_toggle_frame_repair_mode",
    "install_frame_repair_transport_button",
]

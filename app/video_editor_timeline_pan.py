from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, Qt


def _horizontal_bar(owner: Any):
    scroll = getattr(owner, "_tracks_scroll", None)
    if scroll is None:
        return None
    try:
        return scroll.horizontalScrollBar()
    except Exception:
        return None


def _timeline_pan_clamp(value: int, maximum: int) -> int:
    return max(0, min(int(value), max(0, int(maximum))))


def timeline_pan_by(owner: Any, delta_px: int | float) -> dict[str, Any]:
    bar = _horizontal_bar(owner)
    if bar is None:
        before = int(getattr(owner, "_action_timeline_scroll", 0) or 0)
        after = max(0, before + int(round(float(delta_px or 0))))
        setattr(owner, "_action_timeline_scroll", after)
        return {"old_scroll": before, "scroll": after, "delta_px": after - before, "maximum": 0}
    before = int(bar.value())
    after = _timeline_pan_clamp(before + int(round(float(delta_px or 0))), int(bar.maximum()))
    if after != before:
        bar.setValue(after)
    return {
        "old_scroll": before,
        "scroll": after,
        "delta_px": after - before,
        "maximum": int(bar.maximum()),
    }


def timeline_pan_to(owner: Any, scroll_px: int | float) -> dict[str, Any]:
    bar = _horizontal_bar(owner)
    if bar is None:
        before = int(getattr(owner, "_action_timeline_scroll", 0) or 0)
        after = max(0, int(round(float(scroll_px or 0))))
        setattr(owner, "_action_timeline_scroll", after)
        return {"old_scroll": before, "scroll": after, "delta_px": after - before, "maximum": 0}
    before = int(bar.value())
    after = _timeline_pan_clamp(int(round(float(scroll_px or 0))), int(bar.maximum()))
    if after != before:
        bar.setValue(after)
    return {
        "old_scroll": before,
        "scroll": after,
        "delta_px": after - before,
        "maximum": int(bar.maximum()),
    }


def _is_timeline_pan_surface(owner: Any, obj: Any) -> bool:
    scroll = getattr(owner, "_tracks_scroll", None)
    if scroll is not None:
        try:
            if obj is scroll.viewport():
                return True
        except Exception:
            pass
    if obj in (
        getattr(owner, "_tracks_host", None),
        getattr(owner, "_timeline_ruler", None),
    ):
        return True
    for name in (
        "_track_rows",
        "_audio_rows",
        "_actor_lane_rows",
        "_live2d_lane_rows",
        "_ar_pbr_lane_rows",
        "_mmd_lane_rows",
    ):
        rows = getattr(owner, name, None)
        if isinstance(rows, dict):
            if obj in rows.values():
                return True
        elif rows and obj in rows:
            return True
    return False


def _set_pan_cursor(owner: Any, obj: Any, active: bool) -> None:
    cursor = Qt.CursorShape.ClosedHandCursor if active else Qt.CursorShape.OpenHandCursor
    for widget in (obj, getattr(owner, "_tracks_scroll", None), getattr(owner, "_timeline_ruler", None)):
        if widget is None:
            continue
        try:
            if active:
                widget.setCursor(cursor)
            else:
                widget.unsetCursor()
        except Exception:
            pass


def handle_timeline_pan_event(owner: Any, obj: Any, event: Any) -> bool:
    if not _is_timeline_pan_surface(owner, obj):
        return False
    etype = event.type()
    if etype == QEvent.Type.Wheel:
        if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            return False
        delta = int(event.angleDelta().x() or event.angleDelta().y() or 0)
        if delta:
            timeline_pan_by(owner, -delta)
        event.accept()
        return True

    if etype == QEvent.Type.MouseButtonPress:
        button = event.button()
        alt_left = button == Qt.MouseButton.LeftButton and bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        if button != Qt.MouseButton.MiddleButton and not alt_left:
            return False
        try:
            start_x = float(event.globalPosition().x())
        except Exception:
            start_x = float(event.position().x())
        setattr(owner, "_timeline_pan_drag_active", True)
        setattr(owner, "_timeline_pan_drag_last_x", start_x)
        _set_pan_cursor(owner, obj, True)
        event.accept()
        return True

    if etype == QEvent.Type.MouseMove and bool(getattr(owner, "_timeline_pan_drag_active", False)):
        try:
            x = float(event.globalPosition().x())
        except Exception:
            x = float(event.position().x())
        last = float(getattr(owner, "_timeline_pan_drag_last_x", x))
        setattr(owner, "_timeline_pan_drag_last_x", x)
        timeline_pan_by(owner, last - x)
        event.accept()
        return True

    if etype == QEvent.Type.MouseButtonRelease and bool(getattr(owner, "_timeline_pan_drag_active", False)):
        button = event.button()
        if button in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            setattr(owner, "_timeline_pan_drag_active", False)
            _set_pan_cursor(owner, obj, False)
            event.accept()
            return True
    return False

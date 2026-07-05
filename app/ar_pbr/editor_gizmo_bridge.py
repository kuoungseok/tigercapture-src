"""Qt-bound AR/PBR preview gizmo helpers for the video editor."""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)

from app.ar_pbr import editor_bridge as _base_bridge


def runtime_image_point_for_track(self: Any, track_id: str) -> tuple[float, float] | None:
    if not track_id:
        return None
    player = getattr(self, "_player", None)
    diagnostics = getattr(player, "_ar_pbr_last_diagnostics", None)
    if not isinstance(diagnostics, dict):
        return None
    rows = diagnostics.get("runtime_scene_anchor")
    if not isinstance(rows, list):
        return None
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        if str(row.get("track_id") or "") != track_id:
            continue
        point = row.get("image_point")
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            return (
                _base_bridge.clamp01(float(point[0])),
                _base_bridge.clamp01(float(point[1])),
            )
        except Exception:
            return None
    return None


def track_by_id(self: Any, track_id: str, *, active_only: bool = True) -> dict | None:
    wanted = str(track_id or "")
    if not wanted:
        return None
    tracks = self._ar_pbr_active_tracks_at_playhead() if active_only else getattr(self, "_ar_pbr_tracks", []) or []
    for track in tracks:
        if str(track.get("id") or "") == wanted:
            return track
    return None


def selected_track(self: Any) -> dict | None:
    return self._ar_pbr_track_by_id(str(getattr(self, "_selected_ar_pbr_track_id", "") or ""))


def gizmo_visible_track(self: Any) -> dict | None:
    return self._ar_pbr_track_by_id(str(getattr(self, "_ar_pbr_gizmo_visible_track_id", "") or ""))


def gizmo_hit_test(self: Any, nx: float, ny: float, canvas_w: int, canvas_h: int) -> tuple[dict | None, str]:
    from app.ar_pbr.gizmo import gizmo_hit_test as _gizmo_hit_test

    return _gizmo_hit_test(
        self._ar_pbr_active_tracks_at_playhead(),
        str(getattr(self, "_ar_pbr_gizmo_visible_track_id", "") or ""),
        nx,
        ny,
        canvas_w,
        canvas_h,
        center_lookup=self._ar_pbr_track_center_norm,
    )


def refresh_preview_after_gizmo_change(self: Any) -> None:
    self._sync_ar_pbr_tracks_to_player()
    selected = self._ar_pbr_selected_track()
    panel = getattr(self, "_workbench_panel", None)
    if selected is not None and panel is not None and hasattr(panel, "set_ar_pbr_track"):
        try:
            panel.set_ar_pbr_track(selected)
        except Exception:
            pass
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    try:
        self._drawing_canvas.update()
    except Exception:
        pass
    popout = getattr(self, "_preview_popout", None)
    if popout is not None:
        try:
            popout.overlay_canvas().update()
        except Exception:
            pass


def begin_depth_interaction_cue(self: Any, track: dict) -> None:
    if not isinstance(track, dict):
        return
    track_id = str(track.get("id") or "")
    if not track_id:
        return
    restore = getattr(self, "_ar_pbr_depth_cue_restore", None)
    if not isinstance(restore, dict):
        restore = {}
        self._ar_pbr_depth_cue_restore = restore
    from app.ar_pbr.gizmo import begin_depth_interaction_cue as _begin_depth_interaction_cue

    _begin_depth_interaction_cue(track, restore)


def end_depth_interaction_cue(self: Any, track_id: str = "") -> None:
    restore = getattr(self, "_ar_pbr_depth_cue_restore", None)
    if not isinstance(restore, dict) or not restore:
        return
    ids = [str(track_id)] if track_id else list(restore.keys())
    for current_id in ids:
        if not current_id:
            continue
        saved = restore.pop(current_id, None)
        if not isinstance(saved, dict):
            continue
        track = next(
            (
                row
                for row in getattr(self, "_ar_pbr_tracks", []) or []
                if isinstance(row, dict) and str(row.get("id") or "") == current_id
            ),
            None,
        )
        if track is None:
            continue
        from app.ar_pbr.gizmo import restore_depth_interaction_cue

        restore_depth_interaction_cue(track, saved)


def promote_track_to_scene_anchor(self: Any, track: dict, *, reason: str = "") -> bool:
    frame = None
    try:
        frame = self._current_preview_rgb()
    except Exception:
        frame = None
    if frame is None:
        return False
    try:
        from app.ar_pbr.scene_anchor import promote_track_to_scene_anchor as _promote_track_to_scene_anchor

        time_ms = int(self._player.position()) if hasattr(self, "_player") else 0
        source_id = f"preview:{time_ms}:{track.get('id', '')}"
        anchored, diagnostics = _promote_track_to_scene_anchor(
            track,
            frame,
            time_ms=time_ms,
            source_id=source_id,
        )
        track_id = str(track.get("id") or anchored.get("id") or "")
        replaced = False
        for idx, candidate in enumerate(getattr(self, "_ar_pbr_tracks", []) or []):
            if str(candidate.get("id") or "") == track_id:
                self._ar_pbr_tracks[idx] = anchored
                replaced = True
                break
        if not replaced:
            track.clear()
            track.update(anchored)
        else:
            track.clear()
            track.update(anchored)
        self._ar_pbr_scene_anchor_diagnostics = diagnostics
        self._sync_ar_pbr_tracks_to_player()
        self._refresh_preview_canvas_interaction_hook()
        self._refresh_ar_pbr_preview_after_gizmo_change()
        if diagnostics.get("ok"):
            if reason:
                self._flash_status("3D scene anchor solved")
            return True
    except Exception as exc:
        self._ar_pbr_scene_anchor_diagnostics = {
            "ok": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    return False


def cursor_for_gizmo_mode(mode: str):
    mode = str(mode or "")
    if mode.startswith("rotate_"):
        return Qt.CursorShape.CrossCursor
    if mode.endswith("_x"):
        return Qt.CursorShape.SizeHorCursor
    if mode.endswith("_y"):
        return Qt.CursorShape.SizeVerCursor
    if mode.endswith("_z"):
        return Qt.CursorShape.SizeBDiagCursor
    if mode.startswith("scale"):
        return Qt.CursorShape.SizeFDiagCursor
    if mode in {"move", "move_xy"}:
        return Qt.CursorShape.SizeAllCursor
    return Qt.CursorShape.ArrowCursor


def gizmo_interaction_for_canvas(
    self: Any,
    canvas: Any,
    phase: str,
    nx: float,
    ny: float,
    event: QMouseEvent,
) -> bool:
    if canvas is None or not (getattr(self, "_ar_pbr_tracks", []) or []):
        self._ar_pbr_gizmo_drag = None
        return False
    canvas_w = max(1, int(canvas.width()))
    canvas_h = max(1, int(canvas.height()))
    if phase == "double":
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        track, _mode = self._ar_pbr_gizmo_hit_test(nx, ny, canvas_w, canvas_h)
        if track is None:
            return False
        self._selected_ar_pbr_track_id = str(track.get("id") or "")
        self._ar_pbr_gizmo_visible_track_id = self._selected_ar_pbr_track_id
        self._set_ar_pbr_row_selection(self._selected_ar_pbr_track_id)
        self._ar_pbr_gizmo_drag = None
        canvas.setCursor(Qt.CursorShape.ArrowCursor)
        canvas.update()
        self._open_ar_pbr_track_model_view(track)
        return True
    if phase == "press":
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        track, mode = self._ar_pbr_gizmo_hit_test(nx, ny, canvas_w, canvas_h)
        if track is None:
            if getattr(self, "_ar_pbr_gizmo_visible_track_id", ""):
                self._ar_pbr_gizmo_visible_track_id = ""
                self._end_ar_pbr_depth_interaction_cue()
                self._ar_pbr_gizmo_drag = None
                canvas.setCursor(Qt.CursorShape.ArrowCursor)
                canvas.update()
                popout = getattr(self, "_preview_popout", None)
                if popout is not None:
                    try:
                        popout.overlay_canvas().update()
                    except Exception:
                        pass
                return True
            return False
        center_x, center_y = self._ar_pbr_track_center_norm(track)
        pointer_angle = math.degrees(
            math.atan2(
                (float(ny) - center_y) * canvas_h,
                (float(nx) - center_x) * canvas_w,
            )
        )
        start_dist = math.hypot(
            (float(nx) - center_x) * canvas_w,
            (float(ny) - center_y) * canvas_h,
        )
        geom = self._ar_pbr_gizmo_geometry(track, canvas_w, canvas_h)
        axis_name = mode.rsplit("_", 1)[-1] if "_" in mode else ""
        axis_vec = (0.0, 0.0)
        axis_projection = 1.0
        axes = geom.get("axes") if isinstance(geom, dict) else {}
        if isinstance(axes, dict) and axis_name in axes:
            row = axes.get(axis_name) or {}
            axis_vec = tuple(row.get("vec", (0.0, 0.0)))
            axis_projection = (
                (float(nx) - center_x) * canvas_w * float(axis_vec[0])
                + (float(ny) - center_y) * canvas_h * float(axis_vec[1])
            )
        self._selected_ar_pbr_track_id = str(track.get("id") or "")
        self._ar_pbr_gizmo_drag = {
            "mode": mode,
            "track_id": self._selected_ar_pbr_track_id,
            "start_nx": float(nx),
            "start_ny": float(ny),
            "center_x": center_x,
            "center_y": center_y,
            "scale": self._ar_pbr_track_uniform_scale(track),
            "scale_values": self._ar_pbr_track_scale_values(track),
            "yaw": self._ar_pbr_track_yaw(track),
            "rotation_values": [
                self._ar_pbr_track_rotation_value(track, 0),
                self._ar_pbr_track_rotation_value(track, 1),
                self._ar_pbr_track_rotation_value(track, 2),
            ],
            "position_z": self._ar_pbr_track_position_z(track),
            "angle": pointer_angle,
            "distance": max(1.0, start_dist),
            "axis_name": axis_name,
            "axis_vec": axis_vec,
            "axis_projection": max(8.0, abs(axis_projection)),
            "axis_projection_sign": -1.0 if axis_projection < 0 else 1.0,
            "axis_pixels": max(1.0, float(geom.get("length", min(canvas_w, canvas_h) * 0.2))),
            "changed": False,
        }
        self._begin_ar_pbr_depth_interaction_cue(track)
        self._ar_pbr_gizmo_visible_track_id = self._selected_ar_pbr_track_id
        self._set_ar_pbr_row_selection(self._selected_ar_pbr_track_id)
        canvas.setCursor(self._ar_pbr_cursor_for_gizmo_mode(mode))
        self._refresh_ar_pbr_preview_after_gizmo_change()
        canvas.update()
        popout = getattr(self, "_preview_popout", None)
        if popout is not None:
            try:
                popout.overlay_canvas().update()
            except Exception:
                pass
        return True
    if phase == "move":
        drag = getattr(self, "_ar_pbr_gizmo_drag", None)
        if not isinstance(drag, dict):
            track, mode = self._ar_pbr_gizmo_hit_test(nx, ny, canvas_w, canvas_h)
            if track is None:
                canvas.setCursor(Qt.CursorShape.ArrowCursor)
                return False
            canvas.setCursor(self._ar_pbr_cursor_for_gizmo_mode(mode))
            return True
        track_id = str(drag.get("track_id") or "")
        track = next((row for row in getattr(self, "_ar_pbr_tracks", []) or [] if str(row.get("id") or "") == track_id), None)
        if track is None:
            self._end_ar_pbr_depth_interaction_cue(track_id)
            self._ar_pbr_gizmo_drag = None
            return False
        mode = str(drag.get("mode") or "move")
        if mode in {"move", "move_xy"}:
            dx = float(nx) - float(drag.get("start_nx", nx))
            dy = float(ny) - float(drag.get("start_ny", ny))
            self._set_ar_pbr_track_center_norm(
                track,
                float(drag.get("center_x", 0.5)) + dx,
                float(drag.get("center_y", 0.5)) + dy,
            )
            drag["changed"] = True
        elif mode == "move_x":
            dx = float(nx) - float(drag.get("start_nx", nx))
            self._set_ar_pbr_track_center_norm(
                track,
                float(drag.get("center_x", 0.5)) + dx,
                float(drag.get("center_y", 0.5)),
            )
            drag["changed"] = True
        elif mode == "move_y":
            dy = float(ny) - float(drag.get("start_ny", ny))
            self._set_ar_pbr_track_center_norm(
                track,
                float(drag.get("center_x", 0.5)),
                float(drag.get("center_y", 0.5)) + dy,
            )
            drag["changed"] = True
        elif mode == "move_z":
            vx, vy = drag.get("axis_vec", (0.0, 0.0))
            delta_px = (
                (float(nx) - float(drag.get("start_nx", nx))) * canvas_w * float(vx)
                + (float(ny) - float(drag.get("start_ny", ny))) * canvas_h * float(vy)
            )
            delta_z = delta_px / max(1.0, float(drag.get("axis_pixels", 1.0)))
            self._set_ar_pbr_track_position_z(track, float(drag.get("position_z", 0.0)) + delta_z)
            drag["changed"] = True
        elif mode == "scale_uniform":
            center_x = float(drag.get("center_x", 0.5))
            center_y = float(drag.get("center_y", 0.5))
            dist = math.hypot((float(nx) - center_x) * canvas_w, (float(ny) - center_y) * canvas_h)
            ratio = max(0.15, min(5.0, dist / max(1.0, float(drag.get("distance", 1.0)))))
            self._set_ar_pbr_track_uniform_scale(track, float(drag.get("scale", 1.0)) * ratio)
            drag["changed"] = True
        elif mode.startswith("scale_"):
            axis_name = str(drag.get("axis_name") or mode.rsplit("_", 1)[-1])
            axis_index = self._ar_pbr_gizmo_axis_index(axis_name)
            vx, vy = drag.get("axis_vec", (0.0, 0.0))
            center_x = float(drag.get("center_x", 0.5))
            center_y = float(drag.get("center_y", 0.5))
            proj = (
                (float(nx) - center_x) * canvas_w * float(vx)
                + (float(ny) - center_y) * canvas_h * float(vy)
            )
            sign = float(drag.get("axis_projection_sign", 1.0) or 1.0)
            ratio = max(0.15, min(5.0, (proj * sign) / max(1.0, float(drag.get("axis_projection", 1.0)))))
            scale_values = list(drag.get("scale_values") or [1.0, 1.0, 1.0])
            while len(scale_values) < 3:
                scale_values.append(1.0)
            self._set_ar_pbr_track_axis_scale(track, axis_index, float(scale_values[axis_index]) * ratio)
            drag["changed"] = True
        elif mode.startswith("rotate_"):
            center_x = float(drag.get("center_x", 0.5))
            center_y = float(drag.get("center_y", 0.5))
            angle = math.degrees(
                math.atan2(
                    (float(ny) - center_y) * canvas_h,
                    (float(nx) - center_x) * canvas_w,
                )
            )
            axis_name = str(drag.get("axis_name") or mode.rsplit("_", 1)[-1])
            axis_index = self._ar_pbr_gizmo_axis_index(axis_name)
            rotation_values = list(drag.get("rotation_values") or [0.0, 0.0, 0.0])
            while len(rotation_values) < 3:
                rotation_values.append(0.0)
            self._set_ar_pbr_track_rotation_value(
                track,
                axis_index,
                float(rotation_values[axis_index]) + angle - float(drag.get("angle", 0.0)),
            )
            drag["changed"] = True
        self._refresh_ar_pbr_preview_after_gizmo_change()
        return True
    if phase == "release":
        drag = getattr(self, "_ar_pbr_gizmo_drag", None)
        if isinstance(drag, dict):
            self._ar_pbr_gizmo_drag = None
            canvas.setCursor(Qt.CursorShape.ArrowCursor)
            self._end_ar_pbr_depth_interaction_cue(str(drag.get("track_id") or ""))
            self._refresh_ar_pbr_preview_after_gizmo_change()
            if bool(drag.get("changed")):
                track_id = str(drag.get("track_id") or "")
                current = next(
                    (row for row in getattr(self, "_ar_pbr_tracks", []) or [] if str(row.get("id") or "") == track_id),
                    None,
                )
                if current is not None:
                    self._promote_ar_pbr_track_to_scene_anchor(current, reason="gizmo")
                try:
                    self._register_change("adjust ar/pbr object")
                except Exception:
                    pass
            return True
    return False


def paint_gizmo_overlay(self: Any, painter: QPainter, canvas_w: int, canvas_h: int) -> None:
    track = self._ar_pbr_gizmo_visible_track()
    if track is None:
        return
    geom = self._ar_pbr_gizmo_geometry(track, canvas_w, canvas_h)
    cx = float(geom["cx"])
    cy = float(geom["cy"])
    center_radius = float(geom["center_radius"])
    axes = geom.get("axes") if isinstance(geom, dict) else {}
    drag = getattr(self, "_ar_pbr_gizmo_drag", None)
    active_mode = str(drag.get("mode") or "") if isinstance(drag, dict) else ""
    active_axis = active_mode.rsplit("_", 1)[-1] if "_" in active_mode else ""

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    colors = {
        "x": QColor("#FF5B5F"),
        "y": QColor("#46E07E"),
        "z": QColor("#42A5FF"),
        "uniform": QColor("#F8F4EA"),
    }

    def _with_alpha(color: QColor, alpha: int) -> QColor:
        out = QColor(color)
        out.setAlpha(max(0, min(255, int(alpha))))
        return out

    def _is_active(mode_prefix: str, axis_name: str = "") -> bool:
        if not active_mode:
            return False
        if axis_name and active_axis == axis_name and active_mode.startswith(mode_prefix):
            return True
        return active_mode == mode_prefix

    painter.setBrush(Qt.BrushStyle.NoBrush)
    rings = geom.get("rings") if isinstance(geom, dict) else {}
    for axis_name in ("x", "y", "z"):
        points = rings.get(axis_name) if isinstance(rings, dict) else None
        if not isinstance(points, list) or len(points) < 3:
            continue
        color = colors[axis_name]
        pen = QPen(_with_alpha(color, 235 if _is_active("rotate_", axis_name) else 118), 3.0 if _is_active("rotate_", axis_name) else 1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        path = QPainterPath()
        first = points[0]
        path.moveTo(float(first[0]), float(first[1]))
        for point in points[1:]:
            path.lineTo(float(point[0]), float(point[1]))
        path.closeSubpath()
        painter.drawPath(path)

    def _draw_axis(axis_name: str, label: str) -> None:
        if not isinstance(axes, dict):
            return
        row = axes.get(axis_name)
        if not isinstance(row, dict):
            return
        vx, vy = row.get("vec", (0.0, 0.0))
        ex, ey = row.get("end", (cx, cy))
        sx, sy = row.get("scale", (cx, cy))
        color = colors[axis_name]
        active_move = _is_active("move_", axis_name)
        active_scale = _is_active("scale_", axis_name)
        start = QPointF(cx + float(vx) * center_radius, cy + float(vy) * center_radius)
        end = QPointF(float(ex), float(ey))

        shadow = QPen(QColor(5, 8, 14, 205), 8.0 if active_move else 6.0)
        shadow.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(shadow)
        painter.drawLine(start, end)

        pen = QPen(_with_alpha(color, 255), 5.2 if active_move else 3.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(start, end)

        angle = math.atan2(float(vy), float(vx))
        head_len = 16.0 if active_move else 13.0
        head_w = 8.0 if active_move else 6.5
        bx = float(ex) - math.cos(angle) * head_len
        by = float(ey) - math.sin(angle) * head_len
        px = -math.sin(angle)
        py = math.cos(angle)
        head = QPainterPath()
        head.moveTo(float(ex), float(ey))
        head.lineTo(bx + px * head_w, by + py * head_w)
        head.lineTo(bx - px * head_w, by - py * head_w)
        head.closeSubpath()
        painter.setPen(QPen(QColor(5, 8, 14, 230), 1.6))
        painter.setBrush(color)
        painter.drawPath(head)

        cube = QRectF(float(sx) - 7.5, float(sy) - 7.5, 15.0, 15.0)
        painter.setPen(QPen(QColor(5, 8, 14, 230), 1.8))
        painter.setBrush(_with_alpha(color, 255 if active_scale else 218))
        painter.drawRoundedRect(cube, 3.0, 3.0)

        old_font = painter.font()
        font = QFont(old_font)
        font.setPointSize(max(8, old_font.pointSize()))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(_with_alpha(color, 240))
        painter.drawText(QRectF(float(ex) - 16, float(ey) - 16, 32, 32), Qt.AlignmentFlag.AlignCenter, label)
        painter.setFont(old_font)

    axis_order = sorted(
        (("x", "X"), ("y", "Y"), ("z", "Z")),
        key=lambda row: float(((axes or {}).get(row[0]) or {}).get("depth", 0.0)) if isinstance(axes, dict) else 0.0,
    )
    for axis_name, label in axis_order:
        _draw_axis(axis_name, label)

    painter.setPen(QPen(QColor(5, 8, 14, 235), 2.0))
    center_grad = QLinearGradient(cx - center_radius, cy - center_radius, cx + center_radius, cy + center_radius)
    center_grad.setColorAt(0.0, QColor("#FFFFFF"))
    center_grad.setColorAt(1.0, QColor("#AAB4C9"))
    painter.setBrush(QBrush(center_grad))
    painter.drawEllipse(QPointF(cx, cy), center_radius * 0.74, center_radius * 0.74)

    usx, usy = geom.get("uniform_scale", (cx, cy))
    active_uniform = active_mode == "scale_uniform"
    guide_pen = QPen(QColor(248, 244, 234, 145), 1.4)
    guide_pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(guide_pen)
    painter.drawLine(QPointF(cx, cy), QPointF(float(usx), float(usy)))
    uniform_rect = QRectF(float(usx) - 9.0, float(usy) - 9.0, 18.0, 18.0)
    painter.setPen(QPen(QColor(5, 8, 14, 230), 2.0))
    painter.setBrush(_with_alpha(colors["uniform"], 255 if active_uniform else 225))
    painter.drawRoundedRect(uniform_rect, 4.0, 4.0)
    painter.setPen(QPen(QColor("#1A2233"), 1.6))
    painter.drawLine(QPointF(float(usx) - 4.5, float(usy) + 4.5), QPointF(float(usx) + 4.5, float(usy) - 4.5))
    painter.restore()


def preview_drop_frame_point(self: Any, obj: Any, event: Any) -> tuple[float, float]:
    try:
        pos = event.position().toPoint()
    except Exception:
        pos = QPoint(0, 0)
    gl = getattr(self, "_preview_gl", None)
    if obj is gl and gl is not None and gl.width() > 0 and gl.height() > 0:
        return (
            max(0.0, min(1.0, pos.x() / max(1, gl.width()))),
            max(0.0, min(1.0, pos.y() / max(1, gl.height()))),
        )
    label = getattr(self, "_preview_label", None)
    if label is None or label.width() <= 0 or label.height() <= 0:
        return (0.5, 0.62)
    if obj is not label:
        try:
            pos = label.mapFrom(obj, pos)
        except Exception:
            pass
    if self._preview_pixmap is not None and not self._preview_pixmap.isNull():
        src_w = self._preview_pixmap.width()
        src_h = self._preview_pixmap.height()
    else:
        src_w, src_h = getattr(self, "_preview_gl_frame_size", (0, 0))
    if int(src_w) > 0 and int(src_h) > 0:
        rect = self._preview_frame_rect_in_label(int(src_w), int(src_h))
    else:
        rect = QRect(0, 0, label.width(), label.height())
    x = (pos.x() - rect.x()) / max(1, rect.width())
    y = (pos.y() - rect.y()) / max(1, rect.height())
    return (
        max(0.0, min(1.0, float(x))),
        max(0.0, min(1.0, float(y))),
    )

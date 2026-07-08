"""Viewport overlay for Final Cut-style connected clip anchor lines."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QPoint, QRect, QEvent, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from app.nle_visual_feedback import build_connected_anchor_overlay


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class ConnectedAnchorOverlay(QWidget):
    """Transparent overlay that draws connected-clip lines across track rows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConnectedAnchorOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._owner: Any = None
        if parent is not None:
            parent.installEventFilter(self)
            self.setGeometry(parent.rect())
        self.hide()

    def set_owner(self, owner: Any) -> None:
        self._owner = owner
        self.refresh()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parentWidget() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            parent = self.parentWidget()
            if parent is not None:
                self.setGeometry(parent.rect())
                self.raise_()
                self.update()
        return False

    def refresh(self) -> None:
        owner = self._owner
        if owner is None:
            self.hide()
            return
        tracks = list(getattr(owner, "_tracks", []) or [])
        payload = build_connected_anchor_overlay(tracks)
        self.setVisible(bool(payload.get("anchor_count")))
        self.raise_()
        self.update()

    def paintEvent(self, _event) -> None:
        owner = self._owner
        if owner is None:
            return
        tracks = list(getattr(owner, "_tracks", []) or [])
        rows = getattr(owner, "_track_rows", {}) or {}
        payload = build_connected_anchor_overlay(tracks)
        anchors = [row for row in list(payload.get("anchors") or []) if isinstance(row, dict)]
        if not anchors:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for anchor in anchors:
            self._paint_anchor(painter, anchor, rows)
        painter.end()

    def _clip_center(self, rows: dict[Any, Any], *, track_id: int, clip_id: int, fallback_ms: int) -> QPoint | None:
        row = rows.get(track_id)
        if row is None or not hasattr(row, "_clip_rect"):
            return None
        clip = None
        track = getattr(row, "track", None)
        for candidate in list(getattr(track, "clips", []) or []):
            if _int(getattr(candidate, "id", -1), -1) == clip_id:
                clip = candidate
                break
        try:
            rect = row._clip_rect(clip) if clip is not None else QRect(row._ms_to_x(fallback_ms), row.LABEL_H + 4, 1, row.TIMELINE_H - 8)
        except Exception:
            return None
        if rect.width() <= 0 or rect.height() <= 0:
            return None
        local = QPoint(rect.center().x(), rect.top() + max(8, min(rect.height() - 8, rect.height() // 2)))
        try:
            return row.mapTo(self, local)
        except Exception:
            return None

    def _paint_anchor(self, painter: QPainter, anchor: dict[str, Any], rows: dict[Any, Any]) -> None:
        parent = dict(anchor.get("parent") or {})
        child = dict(anchor.get("child") or {})
        parent_tid = _int(parent.get("track_id"), -1)
        parent_cid = _int(parent.get("clip_id"), -1)
        child_tid = _int(child.get("track_id"), -1)
        child_cid = _int(child.get("clip_id"), -1)
        if parent_tid < 0 or child_tid < 0:
            return
        parent_pt = self._clip_center(
            rows,
            track_id=parent_tid,
            clip_id=parent_cid,
            fallback_ms=_int(parent.get("start_ms"), _int(anchor.get("anchor_ms"), 0)),
        )
        child_pt = self._clip_center(
            rows,
            track_id=child_tid,
            clip_id=child_cid,
            fallback_ms=_int(child.get("start_ms"), _int(anchor.get("anchor_ms"), 0)),
        )
        if parent_pt is None or child_pt is None:
            return
        if not self.rect().adjusted(-80, -80, 80, 80).contains(parent_pt) and not self.rect().adjusted(-80, -80, 80, 80).contains(child_pt):
            return

        color = QColor(str(anchor.get("color") or "#7EDBFF"))
        if not color.isValid():
            color = QColor("#7EDBFF")
        color.setAlpha(185 if anchor.get("state") == "ok" else 225)
        shadow = QColor(0, 0, 0, 150)
        path = QPainterPath(parent_pt)
        mid_y = int(round((parent_pt.y() + child_pt.y()) / 2))
        path.cubicTo(parent_pt.x(), mid_y, child_pt.x(), mid_y, child_pt.x(), child_pt.y())

        painter.save()
        painter.setPen(QPen(shadow, 4.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)
        pen_style = Qt.PenStyle.DotLine if anchor.get("state") == "missing_parent" else Qt.PenStyle.SolidLine
        painter.setPen(QPen(color, 2.0, pen_style, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)
        node = QColor(color)
        node.setAlpha(235)
        painter.setBrush(node)
        painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
        for point in (parent_pt, child_pt):
            painter.drawEllipse(point, 4, 4)
        painter.restore()


__all__ = ["ConnectedAnchorOverlay"]

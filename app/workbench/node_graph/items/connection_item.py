"""Bezier connection between two ports.

The visual is a horizontal-out / horizontal-in cubic so a straight
left-to-right chain reads as a smooth ribbon. Control point offset
scales with the horizontal distance so dragging an output far away
keeps the entry / exit angles consistent.

Phase 2B: connections always represent a *finished* link (or a
mid-drag preview when the target hasn't been chosen yet — handled by
``_temp_target_pos``).
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
)
from PySide6.QtWidgets import QGraphicsItem, QMenu

from app.icons import app_icon


class ConnectionItem(QGraphicsItem):

    def __init__(self, source_port, target_port=None) -> None:
        super().__init__()
        self.source = source_port
        self.target = target_port
        self.setZValue(-1)        # behind nodes
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._temp_target_pos: QPointF | None = None

    def boundingRect(self) -> QRectF:
        if self.target is not None:
            p0 = self.source.scene_pos()
            p3 = self.target.scene_pos()
        elif self._temp_target_pos is not None:
            p0 = self.source.scene_pos()
            p3 = self._temp_target_pos
        else:
            return QRectF()
        return QRectF(p0, p3).normalized().adjusted(-20, -20, 20, 20)

    def shape(self) -> QPainterPath:
        path = self._build_path()
        stroker = QPainterPathStroker()
        stroker.setWidth(10)       # thicker than visual so clicks land easily
        return stroker.createStroke(path)

    def _build_path(self) -> QPainterPath:
        if self.target is not None:
            p0 = self.source.scene_pos()
            p3 = self.target.scene_pos()
        elif self._temp_target_pos is not None:
            p0 = self.source.scene_pos()
            p3 = self._temp_target_pos
        else:
            return QPainterPath()
        dx = abs(p3.x() - p0.x())
        offset = max(50.0, dx * 0.5)
        p1 = QPointF(p0.x() + offset, p0.y())
        p2 = QPointF(p3.x() - offset, p3.y())
        path = QPainterPath()
        path.moveTo(p0)
        path.cubicTo(p1, p2, p3)
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = self._build_path()
        if path.isEmpty():
            return

        if self.source.port_type == "rgb":
            base = QColor("#7C735F")
        else:
            base = QColor("#617789")
        base.setAlpha(205)

        if self.isSelected():
            glow = QColor("#AEB7C4")
            glow.setAlpha(24)
            painter.setPen(QPen(glow, 3.0))
            painter.drawPath(path)
            color = QColor("#D7DCE4")
            width = 1.45
        else:
            color = base
            width = 1.15

        shadow = QColor("#000000")
        shadow.setAlpha(36)
        painter.setPen(QPen(shadow, width + 0.8))
        painter.drawPath(path)

        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        if self.source.port_type == "key":
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawPath(path)

    def update_temp_target(self, scene_pos: QPointF) -> None:
        self.prepareGeometryChange()
        self._temp_target_pos = scene_pos
        self.update()

    def update_endpoints(self) -> None:
        """Repaint after either endpoint moved (node drag)."""
        self.prepareGeometryChange()
        self.update()

    def contextMenuEvent(self, event) -> None:
        """Right-click on a connection → disconnect menu."""
        menu = QMenu()
        act = menu.addAction(app_icon("scissors", size=16), "Disconnect")
        chosen = menu.exec(event.screenPos().toPoint())
        if chosen is act:
            scene = self.scene()
            if scene is not None and hasattr(scene, "remove_connection"):
                scene.remove_connection(self)
                try:
                    scene.graph_mutated.emit()
                except Exception:
                    pass

    def detach(self) -> None:
        """Disconnect this line from its endpoint port lists.
        ``scene().removeItem(self)`` should follow this call."""
        if self.source is not None and self in self.source.connections:
            self.source.connections.remove(self)
        if self.target is not None and self in self.target.connections:
            self.target.connections.remove(self)

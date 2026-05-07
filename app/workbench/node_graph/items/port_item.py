"""Input / output port — small circle on the node's edge.

Phase 2B introduces ports + connections. Each Serial node carries
four ports (RGB IN, RGB OUT, KEY IN, KEY OUT) at fixed offsets;
IN/OUT special nodes carry just the one matching their role.

Drag from an OUTPUT port and release on a compatible INPUT port to
make a connection. Port colour follows the DaVinci convention:
green for RGB, blue for Key (rendered with a dashed line).
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QMenu


class PortItem(QGraphicsItem):

    RADIUS = 6
    HOVER_HALO = 4   # extra paintable margin so the hover glow doesn't clip

    def __init__(
        self, port_id: str, port_type: str, is_input: bool, parent=None,
    ) -> None:
        super().__init__(parent)
        self.port_id = port_id
        self.port_type = port_type        # "rgb" or "key"
        self.is_input = is_input
        self.connections: list = []       # list[ConnectionItem]
        self.setAcceptHoverEvents(True)
        self._hovered = False
        # Z stacking: ports must paint over the body rectangle.
        self.setZValue(2)

    def boundingRect(self) -> QRectF:
        r = self.RADIUS + self.HOVER_HALO
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.port_type == "rgb":
            color = QColor("#5DCAA5")
        else:
            color = QColor("#4A9BEE")

        if self._hovered:
            glow = QColor("#D85A30")
            glow.setAlpha(150)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                QPointF(0, 0),
                self.RADIUS + self.HOVER_HALO,
                self.RADIUS + self.HOVER_HALO,
            )
            scale = 1.5
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(150), 2))
            painter.drawEllipse(
                QPointF(0, 0),
                self.RADIUS * scale,
                self.RADIUS * scale,
            )
        else:
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(150), 2))
            painter.drawEllipse(QPointF(0, 0), self.RADIUS, self.RADIUS)
            if self.connections:
                # Inner dot — "this port is wired up" feedback.
                painter.setBrush(QColor("#000000"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(0, 0), 2, 2)

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()

    def mousePressEvent(self, event) -> None:
        # Only OUTPUT ports start a drag — input ports receive drops.
        if event.button() == Qt.MouseButton.LeftButton and not self.is_input:
            scene = self.scene()
            if scene is not None and hasattr(scene, "start_connection_drag"):
                scene.start_connection_drag(self, event.scenePos())
                event.accept()
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        """Right-click on a port → disconnect all connections from this port."""
        if not self.connections:
            event.ignore()
            return
        menu = QMenu()
        n = len(self.connections)
        label = f"✂ 연결 해제 ({n}개)" if n > 1 else "✂ 연결 해제"
        act = menu.addAction(label)
        chosen = menu.exec(event.screenPos().toPoint())
        if chosen is act:
            scene = self.scene()
            if scene is not None and hasattr(scene, "remove_connection"):
                for conn in list(self.connections):
                    scene.remove_connection(conn)
                try:
                    scene.graph_mutated.emit()
                except Exception:
                    pass

    def scene_pos(self) -> QPointF:
        """Top-level scene position (for connection-line endpoints)."""
        return self.scenePos()

    def is_compatible_with(self, other) -> bool:
        """Connection sanity check — same channel type, opposite
        direction, not on the same node."""
        if not isinstance(other, PortItem):
            return False
        if self.port_type != other.port_type:
            return False
        if self.is_input == other.is_input:
            return False
        if self.parentItem() is other.parentItem():
            return False
        return True

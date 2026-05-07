"""Parallel Mixer (Phase 2E) — purple diamond combiner.

DaVinci's Parallel Mixer accepts an arbitrary number of upstream
RGB streams and emits one combined stream (no priority — all inputs
sum together with equal weight). The shape is the visual cue: a
diamond, not a rectangle, separates it from Serial nodes at a glance.

Phase 2E ships with two RGB inputs by default and one RGB output.
``add_input_port`` is exposed so future Phase 2F UI can grow the
input count from a context menu without restructuring the item.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QGraphicsItem

from app.workbench.node_graph.items.port_item import PortItem


class ParallelMixerItem(QGraphicsItem):

    NODE_KIND = "parallel"
    SIZE = 88

    def __init__(self, node_id: str) -> None:
        super().__init__()
        self.node_id = node_id
        self.label = "Parallel"
        self.bypassed: bool = False
        self.user_color: str | None = None
        # Parallel mixers don't grade themselves — they just sum the
        # branches. Keep a default ColorGrade for symmetry with
        # NodeItem so iteration code stays uniform.
        from app.color_grading import ColorGrade
        self.color_grade = ColorGrade()
        self.masks: list = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True,
        )
        self.setAcceptHoverEvents(True)
        self._hovered = False
        self._setup_ports()

    def _setup_ports(self) -> None:
        s = self.SIZE
        # Two RGB inputs at 1/3 and 2/3 of the left edge (centred on
        # the diamond's left vertex) plus one RGB output on the right.
        # Phase 2F will grow this to support N inputs.
        self.rgb_in = PortItem("rgb_in", "rgb", is_input=True, parent=self)
        self.rgb_in.setPos(0, s * 0.35)
        self.rgb_in_b = PortItem("rgb_in_b", "rgb", is_input=True, parent=self)
        self.rgb_in_b.setPos(0, s * 0.65)
        self.rgb_out = PortItem("rgb_out", "rgb", is_input=False, parent=self)
        self.rgb_out.setPos(s, s * 0.5)
        # Key channel passes through the mixer untouched.
        self.key_in = PortItem("key_in", "key", is_input=True, parent=self)
        self.key_in.setPos(s * 0.5, s)
        self.key_out = PortItem("key_out", "key", is_input=False, parent=self)
        self.key_out.setPos(s * 0.5, 0)

    def all_ports(self) -> list[PortItem]:
        return [
            self.rgb_in, self.rgb_in_b, self.rgb_out,
            self.key_in, self.key_out,
        ]

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for port in self.all_ports():
                for conn in port.connections:
                    conn.update_endpoints()
        return super().itemChange(change, value)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.SIZE, self.SIZE)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = self.SIZE
        cx, cy = s / 2, s / 2

        # Diamond path
        path = QPainterPath()
        path.moveTo(cx, 0)
        path.lineTo(s, cy)
        path.lineTo(cx, s)
        path.lineTo(0, cy)
        path.closeSubpath()

        # Selection glow
        if self.isSelected():
            glow = QColor("#D85A30")
            glow.setAlpha(80)
            big = QPainterPath()
            big.moveTo(cx, -3)
            big.lineTo(s + 3, cy)
            big.lineTo(cx, s + 3)
            big.lineTo(-3, cy)
            big.closeSubpath()
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(big)

        # Body
        if self.bypassed:
            body = QColor("#3A2E55")
        else:
            body = QColor("#6B47B8")          # DaVinci-ish purple
        painter.setBrush(QBrush(body))
        if self.isSelected():
            painter.setPen(QPen(QColor("#D85A30"), 2))
        elif self._hovered:
            painter.setPen(QPen(QColor("#A06BD0"), 1))
        else:
            painter.setPen(QPen(QColor("#8A6BD0"), 1))
        painter.drawPath(path)

        # Label
        painter.setPen(QColor("#ffffff"))
        f = QFont(painter.font())
        f.setBold(True)
        f.setPointSize(8)
        painter.setFont(f)
        painter.drawText(
            QRectF(0, cy - 12, s, 24),
            Qt.AlignmentFlag.AlignCenter,
            "◆",
        )

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()

    def toggle_bypass(self) -> None:
        self.bypassed = not self.bypassed
        self.update()

"""IN / OUT special anchors.

Phase 2A: visual placeholder (no ports).
Phase 2B: single port — IN exposes RGB OUT, OUT exposes RGB IN.
          Real connections can flow through them.

These nodes can't be deleted (the context menu has no delete entry
for IO nodes), but they CAN be dragged — keeping them anchored
turned out to make inserting effect nodes between them painful,
since the user had to slot new nodes into a tight pre-set gap.
Position is persisted as part of the scene snapshot so a moved
IN / OUT survives a session reload.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem

from app.workbench.node_graph.items.port_item import PortItem
from app.workbench.node_graph.theme import (
    NODE_GRAPH_COLORS as C,
    NODE_GRAPH_SIZES as S,
)


class IONodeItem(QGraphicsItem):

    def __init__(self, kind: str) -> None:
        super().__init__()
        self.kind = kind                      # "IN" or "OUT"
        self.thumbnail = None                  # live source/output preview
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True,
        )
        self.setAcceptHoverEvents(True)
        self._hovered = False

        # Single port matching the role. We mirror the same attribute
        # name (``rgb_out`` / ``rgb_in``) the regular NodeItem uses
        # so the connection drag code can stay duck-typed.
        h = S["io_height"]
        w = S["io_width"]
        if kind == "IN":
            self.rgb_out = PortItem(
                "rgb_out", "rgb", is_input=False, parent=self,
            )
            self.rgb_out.setPos(w, h / 2)
            self.rgb_in = None
        else:                                  # OUT
            self.rgb_in = PortItem(
                "rgb_in", "rgb", is_input=True, parent=self,
            )
            self.rgb_in.setPos(0, h / 2)
            self.rgb_out = None

    def set_thumbnail(self, pix) -> None:
        self.thumbnail = pix
        self.update()

    def all_ports(self) -> list[PortItem]:
        return [p for p in (self.rgb_in, self.rgb_out) if p is not None]

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for port in self.all_ports():
                for conn in list(port.connections):
                    conn.update_endpoints()
        return super().itemChange(change, value)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, S["io_width"], S["io_height"])

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.boundingRect()
        radius = S["node_border_radius"]
        shadow = QColor("#000000")
        shadow.setAlpha(38)
        painter.setBrush(QBrush(shadow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            rect.adjusted(0.0, 1.0, 0.0, 1.8),
            radius + 1,
            radius + 1,
        )
        if self.isSelected():
            border_color = QColor(C["node_border_selected"])
            border_w = 1.2
        elif self._hovered:
            border_color = QColor("#626970")
            border_w = 1
        else:
            border_color = QColor(C["io_node_border"])
            border_w = 1
        fill = QLinearGradient(0, 0, 0, rect.height())
        fill.setColorAt(0.0, QColor(C["io_node_bg"]).lighter(101))
        fill.setColorAt(1.0, QColor(C["io_node_bg"]).darker(101))
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border_color, border_w))
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(QPen(QColor(255, 255, 255, 7), 1))
        painter.drawLine(6, 1, int(rect.width()) - 7, 1)

        # Thumbnail strip — small live preview centred above the
        # label. Falls back to the label-only layout when no frame
        # has been pushed yet.
        tw = S.get("io_thumbnail_width", 0)
        th = S.get("io_thumbnail_height", 0)
        label_h = 22
        if self.thumbnail is not None and tw > 0 and th > 0:
            tx = (rect.width() - tw) / 2
            ty = 8
            thumb_rect = QRectF(tx, ty, tw, th)
            painter.setBrush(QColor("#000000"))
            painter.setPen(QPen(QColor("#1a1a1a"), 1))
            painter.drawRoundedRect(thumb_rect, 3, 3)
            painter.drawPixmap(thumb_rect.toRect(), self.thumbnail)
            label_rect = QRectF(0, ty + th + 2, rect.width(), label_h)
        else:
            label_rect = rect

        painter.setPen(QColor(C["node_label_color"]))
        f = QFont(painter.font())
        f.setBold(True)
        f.setPointSize(7)
        painter.setFont(f)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self.kind)

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

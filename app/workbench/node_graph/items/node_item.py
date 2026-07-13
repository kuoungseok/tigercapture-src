"""Generic Serial NodeItem.

Phase 2A: visual shell, drag-to-move, hover/selected.
Phase 2B: 4 ports (RGB IN/OUT + KEY IN/OUT). Position changes
          repaint every connected line.
Phase 2C: Bypass mode (Ctrl+D) — diagonal hatch + greyed-out
          appearance. Double-click → rename via QInputDialog.
Phase 2D: ``color_grade`` field stores the per-node ColorGrade so
          the editor can route the Color panel to the selected node.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QGraphicsItem, QInputDialog

from app.workbench.node_graph.items.port_item import PortItem
from app.workbench.node_graph.theme import (
    NODE_GRAPH_COLORS as C,
    NODE_GRAPH_SIZES as S,
)


class NodeItem(QGraphicsItem):

    NODE_KIND = "serial"   # subclass override for parallel/layer

    def __init__(self, node_id: str, label: str) -> None:
        super().__init__()
        self.node_id = node_id
        self.label = label
        self.thumbnail = None
        self.bypassed: bool = False
        self.user_color: str | None = None       # Phase 2C colour coding
        self.track_context_color: str | None = None
        self.track_context_label: str = ""
        # Per-node ColorGrade — DaVinci semantics where each node
        # contributes its own grade and the chain IN→OUT applies them
        # in sequence. Lazy-instantiated so adding 100 nodes without
        # ever editing them doesn't waste 100 dataclasses.
        from app.color_grading import ColorGrade
        self.color_grade = ColorGrade()
        # Local masks (Power Window / Qualifier / Magic Mask /
        # Tracker). When non-empty the node's grade only affects
        # pixels inside the union of its enabled masks — same
        # semantics as DaVinci's Window + Qualifier stack.
        self.masks: list = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._hovered = False
        self._setup_ports()

    def set_track_context(self, color: QColor | str | None, label: str = "") -> None:
        if color is None:
            self.track_context_color = None
        else:
            candidate = QColor(color)
            self.track_context_color = candidate.name() if candidate.isValid() else None
        self.track_context_label = str(label or "")
        self.update()

    # ---- ports ----

    def _setup_ports(self) -> None:
        w = S["node_width"]
        h = S["node_height"]
        header_h = S["node_header_height"]
        rgb_y = header_h + max(14, int((h - header_h) * 0.34))
        key_y = header_h + max(30, int((h - header_h) * 0.68))
        self.rgb_in = PortItem(
            "rgb_in", "rgb", is_input=True, parent=self,
        )
        self.rgb_in.setPos(0, rgb_y)
        self.rgb_out = PortItem(
            "rgb_out", "rgb", is_input=False, parent=self,
        )
        self.rgb_out.setPos(w, rgb_y)
        self.key_in = PortItem(
            "key_in", "key", is_input=True, parent=self,
        )
        self.key_in.setPos(0, key_y)
        self.key_out = PortItem(
            "key_out", "key", is_input=False, parent=self,
        )
        self.key_out.setPos(w, key_y)

    def all_ports(self) -> list[PortItem]:
        return [self.rgb_in, self.rgb_out, self.key_in, self.key_out]

    def itemChange(self, change, value):
        # Repaint connections on the new path whenever this node moves.
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for port in self.all_ports():
                for conn in list(port.connections):
                    conn.update_endpoints()
        return super().itemChange(change, value)

    # ---- geometry ----

    # Selection glow paints 3 px outside the node body; the bounding
    # rect has to cover that (plus a tiny anti-aliasing fudge) or Qt
    # leaves smudges behind when the node moves.
    _BB_MARGIN = 4

    def boundingRect(self) -> QRectF:
        m = self._BB_MARGIN
        return QRectF(-m, -m, S["node_width"] + 2 * m, S["node_height"] + 2 * m)

    # Shape path is identical for every NodeItem (same body size /
    # corner radius), and ``shape()`` is called once per mouse move
    # per item by Qt's hit test. Building a fresh QPainterPath each
    # call dragged the whole scene to a crawl, so we lazy-build once
    # at class level and hand the same object back forever.
    _shape_cache = None

    @classmethod
    def _build_shape(cls):
        from PySide6.QtGui import QPainterPath
        p = QPainterPath()
        p.addRoundedRect(
            QRectF(0, 0, S["node_width"], S["node_height"]),
            S["node_border_radius"], S["node_border_radius"],
        )
        return p

    def shape(self):  # noqa: N802
        cls = type(self)
        if cls._shape_cache is None:
            cls._shape_cache = NodeItem._build_shape()
        return cls._shape_cache

    # ---- paint ----

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Use the body rect for drawing, NOT boundingRect — the latter
        # includes the selection-glow margin so that Qt clears it on
        # move (see _BB_MARGIN above).
        rect = QRectF(0, 0, S["node_width"], S["node_height"])
        radius = S["node_border_radius"]

        # Catalog-style depth: a thin soft shadow plus one-pixel
        # highlights reads better than heavy gradients at this scale.
        shadow = QColor("#000000")
        shadow.setAlpha(42)
        painter.setBrush(QBrush(shadow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            rect.adjusted(0.0, 1.0, 0.0, 1.8),
            radius + 1,
            radius + 1,
        )

        # Selection glow behind body.
        if self.isSelected():
            glow = QColor(C["node_border_selected"])
            glow.setAlpha(18)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                rect.adjusted(-1.5, -1.5, 1.5, 1.5), radius + 1, radius + 1,
            )

        # Body fill (gradient — disabled when bypassed).
        if self.bypassed:
            gradient = QLinearGradient(0, 0, 0, rect.height())
            gradient.setColorAt(0, QColor(C["node_bg_disabled"]).lighter(104))
            gradient.setColorAt(1, QColor(C["node_bg_disabled"]))
        else:
            gradient = QLinearGradient(0, 0, 0, rect.height())
            gradient.setColorAt(0, QColor(C["node_bg_normal"]).lighter(101))
            gradient.setColorAt(1, QColor(C["node_bg_normal"]).darker(101))

        if self.isSelected():
            border_color = QColor(C["node_border_selected"])
            border_w = 1.2
        elif self.user_color is not None and not self.bypassed:
            border_color = QColor(self.user_color)
            border_w = 1.1
        elif self._hovered:
            border_color = QColor(C["node_border_hover"])
            border_w = 1
        elif self.bypassed:
            border_color = QColor(C["node_border_disabled"])
            border_w = 1
        else:
            border_color = QColor(C["node_border_normal"])
            border_w = 1

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(border_color, border_w))
        painter.drawRoundedRect(rect, radius, radius)
        paint_node_track_context_strip(self, painter, rect, radius)

        painter.setPen(QPen(QColor(255, 255, 255, 8), 1))
        painter.drawLine(6, 1, int(rect.width()) - 7, 1)
        painter.setPen(QPen(QColor(0, 0, 0, 32), 1))
        painter.drawLine(7, int(rect.height()) - 1, int(rect.width()) - 8, int(rect.height()) - 1)

        # Header (clipped to body's rounded corners).
        header_h = S["node_header_height"]
        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)
        header_color = QColor(C["node_header_bg"])
        if self.bypassed:
            header_color = header_color.darker(130)
        header_grad = QLinearGradient(0, 0, 0, header_h)
        header_grad.setColorAt(0.0, header_color.lighter(103))
        header_grad.setColorAt(1.0, header_color.darker(101))
        painter.fillRect(QRectF(0, 0, rect.width(), header_h), header_grad)
        accent = QColor(self.user_color or C["node_border_selected"])
        accent.setAlpha(70 if self.isSelected() else 30)
        painter.fillRect(QRectF(0, 0, rect.width(), 1), accent)
        painter.restore()

        # ID badge.
        id_color = QColor(C["node_id_color"])
        if self.bypassed:
            id_color = id_color.darker(160)
        painter.setPen(id_color)
        f = QFont(painter.font())
        f.setFamily("Segoe UI Variable")
        f.setBold(True)
        f.setPointSize(6)
        painter.setFont(f)
        painter.drawText(
            QRectF(8, 0, 28, header_h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.node_id,
        )

        # Label
        label_color = QColor(C["node_label_color"])
        if self.bypassed:
            label_color = QColor("#5A5A5A")
        painter.setPen(label_color)
        f.setBold(False)
        f.setPointSize(7)
        painter.setFont(f)
        painter.drawText(
            QRectF(30, 0, rect.width() - 36, header_h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.label,
        )

        # Mask indicator — small Tiger Orange dot in the top-right
        # corner when this node has any active masks. Same affordance
        # DaVinci uses (a small "key" badge on the node header).
        active_masks = sum(
            1 for m in (self.masks or []) if getattr(m, "enabled", True)
        )
        if active_masks > 0:
            painter.save()
            painter.setBrush(QColor("#8FA6C8"))
            painter.setPen(QPen(QColor("#B6C5DA"), 1))
            badge_x = rect.width() - 19
            badge_y = (header_h - 9) / 2
            painter.drawEllipse(QRectF(badge_x, badge_y, 9, 9))
            if active_masks > 1:
                painter.setPen(QColor("#ffffff"))
                f.setPointSize(7)
                f.setBold(True)
                painter.setFont(f)
                painter.drawText(
                    QRectF(badge_x, badge_y, 9, 9),
                    Qt.AlignmentFlag.AlignCenter,
                    str(active_masks),
                )
            painter.restore()

        # Thumbnail placeholder
        tw = S["thumbnail_width"]
        th = S["thumbnail_height"]
        tx = (rect.width() - tw) / 2
        ty = header_h + 6
        thumb_rect = QRectF(tx, ty, tw, th)
        painter.setBrush(QColor("#111213"))
        painter.setPen(QPen(QColor("#33363A"), 1))
        painter.drawRoundedRect(thumb_rect, 4, 4)
        if self.thumbnail is None:
            painter.setPen(QColor("#8E98A6"))
            f.setPointSize(6)
            painter.setFont(f)
            painter.drawText(
                thumb_rect,
                Qt.AlignmentFlag.AlignCenter,
                "Color Grade",
            )
        else:
            painter.drawPixmap(thumb_rect.toRect(), self.thumbnail)

        # Bypass hatch — diagonal striped overlay.
        if self.bypassed:
            painter.save()
            painter.setClipPath(clip)
            hatch_pen = QPen(QColor(255, 255, 255, 25), 1)
            painter.setPen(hatch_pen)
            step = 8
            x = -int(rect.height())
            while x < int(rect.width()) + int(rect.height()):
                painter.drawLine(
                    int(x), 0,
                    int(x + rect.height()), int(rect.height()),
                )
                x += step
            painter.restore()

    # ---- hover ----

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    # ---- interactions ----

    def mouseDoubleClickEvent(self, event) -> None:
        # Phase 2C: rename via modal. F2 shortcut on the widget does
        # the same; double-click is the discoverable path.
        new_label, ok = QInputDialog.getText(
            None, "Rename node", "Label:", text=self.label,
        )
        if ok and new_label.strip():
            self.label = new_label.strip()
            self.update()
            scene = self.scene()
            if scene is not None and hasattr(scene, "_emit_selection_label"):
                scene._emit_selection_label()
            if scene is not None and hasattr(scene, "graph_mutated"):
                scene.graph_mutated.emit()

    def toggle_bypass(self) -> None:
        self.bypassed = not self.bypassed
        self.update()


def paint_node_track_context_strip(
    node,
    painter: QPainter,
    rect: QRectF,
    radius: float,
) -> None:
    color = QColor(getattr(node, "track_context_color", "") or "")
    if not color.isValid():
        return
    selected = bool(node.isSelected())
    color.setAlpha(204 if selected else 132)
    glow = QColor(color)
    glow.setAlpha(34 if selected else 18)
    painter.save()
    clip = QPainterPath()
    clip.addRoundedRect(rect, radius, radius)
    painter.setClipPath(clip)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(glow)
    painter.drawRect(QRectF(0.0, 0.0, 8.0, rect.height()))
    painter.setBrush(color)
    painter.drawRect(QRectF(0.0, 0.0, 4.0, rect.height()))
    painter.restore()

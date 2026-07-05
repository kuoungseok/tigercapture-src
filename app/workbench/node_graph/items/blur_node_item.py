"""BlurNodeItem — out-of-focus / bokeh effect node.

Extends NodeItem so it lives in the same graph, shares the same
port / selection / bypass / masking infrastructure, but carries
``BlurParams`` instead of ``ColorGrade``.

Visual differences from a regular serial node:
  - Blue header (teal accent vs Tiger Orange for colour nodes).
  - Label defaults to "Blur".
  - NODE_KIND = "blur" so the chain evaluator knows to call
    ``blur_params.apply_with_mask`` instead of ``apply_to_rgb``.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen

from app.blur_params import BlurParams
from app.workbench.node_graph.items.node_item import NodeItem
from app.workbench.node_graph.theme import (
    NODE_GRAPH_COLORS as C,
    NODE_GRAPH_SIZES as S,
)


_BLUR_HEADER = "#34424D"
_BLUR_BORDER_SEL = "#7E9ED6"
_BLUR_BG = "#20262C"


class BlurNodeItem(NodeItem):

    NODE_KIND = "blur"

    def __init__(self, node_id: str, label: str = "Blur") -> None:
        super().__init__(node_id, label)
        # Replace the ColorGrade with BlurParams.
        self.color_grade = None
        self.blur_params = BlurParams()
        # Mask inversion flag — default True (background blur).
        self.blur_invert_mask: bool = True

    # ---- paint override — teal theme ----

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, S["node_width"], S["node_height"])
        radius = S["node_border_radius"]

        shadow = QColor("#000000")
        shadow.setAlpha(78)
        painter.setBrush(QBrush(shadow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            rect.adjusted(0.0, 1.5, 0.0, 2.6),
            radius + 1,
            radius + 1,
        )

        if self.isSelected():
            glow = QColor(_BLUR_BORDER_SEL)
            glow.setAlpha(30)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect.adjusted(-1.5, -1.5, 1.5, 1.5), radius + 1, radius + 1)

        gradient = QLinearGradient(0, 0, 0, rect.height())
        if self.bypassed:
            gradient.setColorAt(0, QColor(C["node_bg_disabled"]).lighter(110))
            gradient.setColorAt(1, QColor(C["node_bg_disabled"]))
        else:
            gradient.setColorAt(0, QColor(_BLUR_BG).lighter(104))
            gradient.setColorAt(1, QColor(_BLUR_BG))

        if self.isSelected():
            border_color = QColor(_BLUR_BORDER_SEL)
            border_w = 1.35
        elif self._hovered:
            border_color = QColor("#758391")
            border_w = 1
        elif self.bypassed:
            border_color = QColor(C["node_border_disabled"])
            border_w = 1
        else:
            border_color = QColor("#38414B")
            border_w = 1

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(border_color, border_w))
        painter.drawRoundedRect(rect, radius, radius)

        # Teal header
        header_h = S["node_header_height"]
        from PySide6.QtGui import QPainterPath
        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)
        hdr_color = QColor(_BLUR_HEADER)
        if self.bypassed:
            hdr_color = hdr_color.darker(130)
        header_grad = QLinearGradient(0, 0, 0, header_h)
        header_grad.setColorAt(0.0, hdr_color.lighter(112))
        header_grad.setColorAt(1.0, hdr_color.darker(108))
        painter.fillRect(QRectF(0, 0, rect.width(), header_h), header_grad)
        accent = QColor(_BLUR_BORDER_SEL)
        accent.setAlpha(128 if self.isSelected() else 72)
        painter.fillRect(QRectF(0, 0, rect.width(), 2), accent)
        painter.restore()

        # ID badge — teal accent
        from PySide6.QtGui import QFont
        id_color = QColor("#A8B5C4") if not self.bypassed else QColor("#59636E")
        painter.setPen(id_color)
        f = QFont(painter.font())
        f.setFamily("Segoe UI Variable")
        f.setBold(True)
        f.setPointSize(6)
        painter.setFont(f)
        painter.drawText(QRectF(8, 0, 28, header_h),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.node_id)

        # Label
        lbl_color = QColor(C["node_label_color"]) if not self.bypassed else QColor("#5A5A5A")
        painter.setPen(lbl_color)
        f.setBold(False)
        f.setPointSize(7)
        painter.setFont(f)
        painter.drawText(QRectF(34, 0, rect.width() - 42, header_h),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.label)

        # Mask indicator
        active_masks = sum(1 for m in (self.masks or []) if getattr(m, "enabled", True))
        if active_masks > 0:
            painter.save()
            painter.setBrush(QColor("#8FA6C8"))
            painter.setPen(QPen(QColor("#B6C5DA"), 1))
            painter.drawEllipse(QRectF(rect.width() - 19, (header_h - 9) / 2, 9, 9))
            painter.restore()

        # Thumbnail
        tw = S["thumbnail_width"]
        th = S["thumbnail_height"]
        tx = (rect.width() - tw) / 2
        ty = header_h + 6
        thumb_rect = QRectF(tx, ty, tw, th)
        painter.setBrush(QColor("#0D1013"))
        painter.setPen(QPen(QColor("#414852"), 1))
        painter.drawRoundedRect(thumb_rect, 4, 4)
        if self.thumbnail is None:
            painter.setPen(QColor("#9AA6B3"))
            f.setPointSize(6)
            painter.setFont(f)
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "Blur")
        else:
            painter.drawPixmap(thumb_rect.toRect(), self.thumbnail)

        # Bypass hatch
        if self.bypassed:
            from PySide6.QtGui import QPainterPath as _PP
            painter.save()
            clip2 = _PP()
            clip2.addRoundedRect(rect, radius, radius)
            painter.setClipPath(clip2)
            painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
            step = 8
            x = -int(rect.height())
            while x < int(rect.width()) + int(rect.height()):
                painter.drawLine(int(x), 0, int(x + rect.height()), int(rect.height()))
                x += step
            painter.restore()

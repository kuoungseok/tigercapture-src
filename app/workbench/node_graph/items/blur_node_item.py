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


_BLUR_HEADER = "#1e3a4f"      # deep teal header
_BLUR_BORDER_SEL = "#3ba3c8"  # cyan when selected
_BLUR_BG = "#212f38"          # slightly bluer body


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
        rect = self.boundingRect()
        radius = S["node_border_radius"]

        if self.isSelected():
            glow = QColor(_BLUR_BORDER_SEL)
            glow.setAlpha(80)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), radius + 3, radius + 3)

        gradient = QLinearGradient(0, 0, 0, rect.height())
        if self.bypassed:
            gradient.setColorAt(0, QColor(C["node_bg_disabled"]).lighter(110))
            gradient.setColorAt(1, QColor(C["node_bg_disabled"]))
        else:
            gradient.setColorAt(0, QColor(_BLUR_BG).lighter(115))
            gradient.setColorAt(1, QColor(_BLUR_BG))

        if self.isSelected():
            border_color = QColor(_BLUR_BORDER_SEL)
            border_w = 2
        elif self._hovered:
            border_color = QColor("#4abde0")
            border_w = 1
        elif self.bypassed:
            border_color = QColor(C["node_border_disabled"])
            border_w = 1
        else:
            border_color = QColor("#2a4a5e")
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
        painter.fillRect(QRectF(0, 0, rect.width(), header_h), hdr_color)
        painter.restore()

        # ID badge — teal accent
        from PySide6.QtGui import QFont
        id_color = QColor("#3ba3c8") if not self.bypassed else QColor("#2a5a70")
        painter.setPen(id_color)
        f = QFont(painter.font())
        f.setBold(True)
        f.setPointSize(8)
        painter.setFont(f)
        painter.drawText(QRectF(8, 0, 32, header_h),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.node_id)

        # Label
        lbl_color = QColor(C["node_label_color"]) if not self.bypassed else QColor("#5A5A5A")
        painter.setPen(lbl_color)
        f.setBold(False)
        f.setPointSize(9)
        painter.setFont(f)
        painter.drawText(QRectF(40, 0, rect.width() - 48, header_h),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.label)

        # Mask indicator
        active_masks = sum(1 for m in (self.masks or []) if getattr(m, "enabled", True))
        if active_masks > 0:
            painter.save()
            painter.setBrush(QColor("#3ba3c8"))
            painter.setPen(QPen(QColor("#7dd4f0"), 1))
            painter.drawEllipse(QRectF(rect.width() - 22, (header_h - 12) / 2, 12, 12))
            painter.restore()

        # Thumbnail
        tw = S["thumbnail_width"]
        th = S["thumbnail_height"]
        tx = (rect.width() - tw) / 2
        ty = header_h + 8
        thumb_rect = QRectF(tx, ty, tw, th)
        painter.setBrush(QColor("#0a0f14"))
        painter.setPen(QPen(QColor("#1a2a36"), 1))
        painter.drawRoundedRect(thumb_rect, 4, 4)
        if self.thumbnail is None:
            painter.setPen(QColor("#3a6a80"))
            f.setPointSize(8)
            painter.setFont(f)
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "🔵 Blur")
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

"""EffectNodeItem — generic node for all effect_node_params types."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient,
    QPainter, QPainterPath, QPen,
)

from app.workbench.node_graph.items.node_item import NodeItem
from app.workbench.node_graph.theme import (
    NODE_GRAPH_COLORS as C,
    NODE_GRAPH_SIZES as S,
)


def _muted_hex(hex_color: str) -> str:
    color = QColor(hex_color)
    if not color.isValid():
        return hex_color
    hue, saturation, value, alpha = color.getHsv()
    if hue < 0:
        return color.name()
    return QColor.fromHsv(hue, min(saturation, 78), min(max(value, 112), 150), alpha).name()


class EffectNodeItem(NodeItem):
    """Node item for the 10 new effect types (Curves, Levels, Glow, etc.)."""

    def __init__(self, effect_kind: str, node_id: str, label: str = "") -> None:
        from app.effect_node_params import _KIND_META, _KIND_TO_CLASS
        meta = _KIND_META.get(effect_kind, (label or effect_kind, "#607D8B", None))
        super().__init__(node_id, label or meta[0])

        self.NODE_KIND = effect_kind          # type: ignore[assignment]
        self.color_grade = None               # not a colour node

        cls = _KIND_TO_CLASS.get(effect_kind)
        self.effect_params = cls() if cls else None
        self._header_hex: str = _muted_hex(meta[1])

    # ── paint override ────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, S["node_width"], S["node_height"])
        radius = S["node_border_radius"]
        header_h = S["node_header_height"]
        hdr_color = QColor(self._header_hex)

        shadow = QColor("#000000")
        shadow.setAlpha(42)
        painter.setBrush(QBrush(shadow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            rect.adjusted(0.0, 1.0, 0.0, 1.8),
            radius + 1,
            radius + 1,
        )

        # ── Selection glow ─────────────────────────────────────────────────
        if self.isSelected():
            glow = QColor(hdr_color)
            glow.setAlpha(18)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect.adjusted(-1.5, -1.5, 1.5, 1.5), radius + 1, radius + 1)

        # ── Body fill ──────────────────────────────────────────────────────
        if self.bypassed:
            gradient = QLinearGradient(0, 0, 0, rect.height())
            gradient.setColorAt(0, QColor(C["node_bg_disabled"]).lighter(104))
            gradient.setColorAt(1, QColor(C["node_bg_disabled"]))
        else:
            gradient = QLinearGradient(0, 0, 0, rect.height())
            gradient.setColorAt(0, QColor(C["node_bg_normal"]).lighter(101))
            gradient.setColorAt(1, QColor(C["node_bg_normal"]).darker(101))

        border_color = (QColor(hdr_color) if self.isSelected()
                        else QColor(C["node_border_hover"]) if self._hovered
                        else QColor(C["node_border_disabled"]) if self.bypassed
                        else QColor(C["node_border_normal"]))
        border_w = 1.2 if self.isSelected() else 1

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(border_color, border_w))
        painter.drawRoundedRect(rect, radius, radius)

        painter.setPen(QPen(QColor(255, 255, 255, 8), 1))
        painter.drawLine(6, 1, int(rect.width()) - 7, 1)
        painter.setPen(QPen(QColor(0, 0, 0, 32), 1))
        painter.drawLine(7, int(rect.height()) - 1, int(rect.width()) - 8, int(rect.height()) - 1)

        # ── Header ─────────────────────────────────────────────────────────
        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)
        if self.bypassed:
            hdr_color = hdr_color.darker(150)
        header_grad = QLinearGradient(0, 0, 0, header_h)
        header_grad.setColorAt(0.0, hdr_color.lighter(104))
        header_grad.setColorAt(1.0, hdr_color.darker(102))
        painter.fillRect(QRectF(0, 0, rect.width(), header_h), header_grad)
        accent = QColor(hdr_color).lighter(130)
        accent.setAlpha(76 if self.isSelected() else 36)
        painter.fillRect(QRectF(0, 0, rect.width(), 1), accent)
        painter.restore()

        # ── ID badge ───────────────────────────────────────────────────────
        id_color = QColor(self._header_hex).lighter(160) if not self.bypassed else QColor("#555")
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

        # ── Label ─────────────────────────────────────────────────────────
        lbl_color = QColor(C["node_label_color"]) if not self.bypassed else QColor("#5A5A5A")
        painter.setPen(lbl_color)
        f.setBold(False)
        f.setPointSize(7)
        painter.setFont(f)
        painter.drawText(
            QRectF(30, 0, rect.width() - 36, header_h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.label,
        )

        # ── Thumbnail ─────────────────────────────────────────────────────
        tw = S["thumbnail_width"]
        th = S["thumbnail_height"]
        tx = (rect.width() - tw) / 2
        ty = float(header_h) + 6
        thumb_rect = QRectF(tx, ty, tw, th)
        painter.setPen(QPen(QColor("#33363A"), 1))
        painter.setBrush(QBrush(QColor("#111213")))
        painter.drawRoundedRect(thumb_rect, 4, 4)
        if self.thumbnail:
            painter.drawPixmap(thumb_rect.toRect(), self.thumbnail)

        # ── Effect kind badge ──────────────────────────────────────────────
        if not self.thumbnail:
            from app.effect_node_params import _KIND_META
            meta_label = _KIND_META.get(self.NODE_KIND, (self.label,))[0]
            painter.setPen(QColor(self._header_hex).lighter(130))
            f2 = QFont(painter.font())
            f2.setPointSize(6)
            painter.setFont(f2)
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, meta_label)

        # ── Bypass hatch ──────────────────────────────────────────────────
        if self.bypassed:
            painter.save()
            painter.setOpacity(0.10)
            painter.setPen(QPen(QColor("#aaa"), 1))
            step = 14
            for i in range(-int(rect.height()), int(rect.width()) + step, step):
                painter.drawLine(int(i), 0, int(i + rect.height()), int(rect.height()))
            painter.restore()

        # ── Mask indicator dot ────────────────────────────────────────────
        active_masks = sum(1 for m in (self.masks or []) if getattr(m, "enabled", True))
        if active_masks > 0:
            painter.save()
            painter.setBrush(QColor(self._header_hex))
            painter.setPen(QPen(QColor(self._header_hex).lighter(160), 1))
            r = 5
            painter.drawEllipse(
                QRectF(rect.width() - r*2 - 6, (header_h - r*2) / 2, r*2, r*2)
            )
            painter.restore()

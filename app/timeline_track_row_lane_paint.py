"""Lane header painting helpers for timeline track rows."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen


def paint_timeline_lane_header(
    self,
    painter: QPainter,
    *,
    is_perf_track: bool,
    is_image_track: bool = False,
) -> None:
    painter.save()
    lane_rect = QRect(0, 0, self.MARGIN, self.LABEL_H + self.TIMELINE_H)
    body_rect = QRect(0, self.LABEL_H, self.MARGIN, self.TIMELINE_H)
    lane_grad = QLinearGradient(lane_rect.topLeft(), lane_rect.bottomLeft())
    lane_grad.setColorAt(0.0, QColor("#171819"))
    lane_grad.setColorAt(1.0, QColor("#101111"))
    body_grad = QLinearGradient(body_rect.topLeft(), body_rect.bottomLeft())
    body_grad.setColorAt(0.0, QColor("#161717"))
    body_grad.setColorAt(1.0, QColor("#111111"))
    painter.fillRect(lane_rect, lane_grad)
    painter.fillRect(body_rect, body_grad)
    painter.setPen(QColor(255, 255, 255, 14))
    painter.drawLine(0, body_rect.top(), self.MARGIN - 1, body_rect.top())
    painter.setPen(QColor("#242424"))
    painter.drawLine(self.MARGIN - 1, 0, self.MARGIN - 1, lane_rect.bottom())
    painter.drawLine(0, body_rect.bottom(), self.MARGIN - 1, body_rect.bottom())
    accent = QColor("#C7CBD0" if self._is_active else "#6D7074")
    if is_perf_track:
        accent = QColor("#B4B8CC" if self._is_active else "#85899A")
    elif is_image_track:
        accent = QColor("#9BC8FF" if self._is_active else "#6F9DCC")
    accent.setAlpha(82 if self._is_active else 22)
    painter.fillRect(0, body_rect.top() + 8, 2, max(12, body_rect.height() - 16), accent)
    tab_rect = QRect(14, body_rect.top() + 5, 86, max(18, body_rect.height() - 10))
    tab_grad = QLinearGradient(tab_rect.topLeft(), tab_rect.bottomLeft())
    tab_grad.setColorAt(0.0, QColor(255, 255, 255, 7 if self._is_active else 4))
    tab_grad.setColorAt(1.0, QColor(0, 0, 0, 10))
    painter.setPen(QPen(QColor(255, 255, 255, 15 if self._is_active else 8), 1))
    painter.setBrush(QBrush(tab_grad))
    painter.drawRoundedRect(tab_rect, 3, 3)
    painter.setPen(QPen(QColor(0, 0, 0, 38), 1))
    painter.drawLine(tab_rect.right(), tab_rect.top() + 5, tab_rect.right(), tab_rect.bottom() - 5)
    label_color = QColor("#D8DADD") if self._is_active else QColor("#9A9A9A")
    lane_font = painter.font()
    lane_font.setFamily("Segoe UI Variable")
    lane_font.setPixelSize(12)
    lane_font.setWeight(QFont.Weight.Medium)
    painter.setFont(lane_font)
    painter.setPen(label_color)
    lane_index = max(1, int(getattr(self, "_lane_index", 1) or 1))
    if is_perf_track:
        lane_code = f"PS{lane_index}"
        lane_role = "Perf Source"
    elif is_image_track:
        lane_code = f"I{lane_index}"
        lane_role = "Image"
    else:
        lane_code = f"V{lane_index}"
        lane_role = "Video"
    label_y = body_rect.top() + max(0, (body_rect.height() - 16) // 2)
    painter.drawText(
        QRect(tab_rect.left(), label_y, tab_rect.width(), 16),
        Qt.AlignmentFlag.AlignCenter,
        lane_code,
    )
    lane_font.setFamily("Segoe UI Variable")
    lane_font.setPixelSize(10)
    lane_font.setWeight(QFont.Weight.Normal)
    painter.setFont(lane_font)
    painter.setPen(QColor("#7E7E7E"))
    painter.drawText(
        QRect(112, label_y, self.MARGIN - 126, 16),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        lane_role,
    )
    painter.restore()


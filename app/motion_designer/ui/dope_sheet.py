from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from app.motion_designer.schema import MotionComposition


class DopeSheet(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.composition: MotionComposition | None = None
        self.playhead_ms = 0

    def set_state(self, composition: MotionComposition, playhead_ms: int) -> None:
        self.composition = composition
        self.playhead_ms = int(playhead_ms)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#11141a"))
        composition = self.composition
        if composition is None:
            return
        duration = max(1, composition.duration_ms)
        painter.setPen(QPen(QColor("#303743"), 1))
        for second in range(0, duration + 1, 1000):
            x = int(second / duration * self.width())
            painter.drawLine(x, 0, x, self.height())
        painter.setBrush(QColor("#64c8a5"))
        painter.setPen(Qt.NoPen)
        row_height = max(12, int(self.height() / max(1, len(composition.layers))))
        for row, layer in enumerate(composition.layers):
            times = {key.time_ms for prop in layer.transform.properties().values() for key in prop.keyframes}
            for time_ms in times:
                x = time_ms / duration * self.width()
                y = row * row_height + row_height * .5
                polygon = QPolygonF()
                from PySide6.QtCore import QPointF
                polygon << QPointF(x, y - 4) << QPointF(x + 4, y) << QPointF(x, y + 4) << QPointF(x - 4, y)
                painter.drawPolygon(polygon)
        painter.setPen(QPen(QColor("#f4b860"), 2))
        playhead_x = int(self.playhead_ms / duration * self.width())
        painter.drawLine(playhead_x, 0, playhead_x, self.height())

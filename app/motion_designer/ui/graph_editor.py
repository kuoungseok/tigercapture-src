from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.motion_designer.keyframes import evaluate_property
from app.motion_designer.schema import AnimatedProperty


class GraphEditor(QWidget):
    keyframe_changed = Signal(str, int, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.property: AnimatedProperty | None = None
        self.duration_ms = 1
        self._value_min = 0.0
        self._value_max = 1.0
        self._markers: list[tuple[QPointF, str, int]] = []
        self._drag: tuple[str, int] | None = None
        self.setMouseTracking(True)

    def set_property(self, prop: AnimatedProperty | None, *, duration_ms: int = 1) -> None:
        self.property = prop
        self.duration_ms = max(1, int(duration_ms))
        self.update()

    @staticmethod
    def _channels(value) -> list[float]:
        if isinstance(value, (list, tuple)):
            return [float(item) for item in value]
        return [float(value)]

    def _point(self, time_ms: float, value: float) -> QPointF:
        x = max(0.0, min(1.0, float(time_ms) / self.duration_ms)) * max(1, self.width() - 1)
        ratio = (float(value) - self._value_min) / max(1e-9, self._value_max - self._value_min)
        y = (1.0 - max(0.0, min(1.0, ratio))) * max(1, self.height() - 1)
        return QPointF(x, y)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#11141a"))
        painter.setPen(QPen(QColor("#303743"), 1))
        for ratio in (.25, .5, .75):
            painter.drawLine(0, int(self.height() * ratio), self.width(), int(self.height() * ratio))
        prop = self.property
        self._markers = []
        if prop is None or not prop.keyframes:
            return
        keys = sorted(prop.keyframes, key=lambda key: key.time_ms)
        key_values = [channel for key in keys for channel in self._channels(key.value)]
        sample_values = [evaluate_property(prop, self.duration_ms * index / 99.0)
                         for index in range(80)]
        first = sample_values[0]
        channels = len(first) if isinstance(first, (list, tuple)) else 1
        rows = [[float(value[channel]) if isinstance(value, (list, tuple)) else float(value)
                 for value in sample_values] for channel in range(channels)]
        flattened = [value for row in rows for value in row]
        min_value = min([*flattened, *key_values])
        max_value = max([*flattened, *key_values])
        padding = max(1.0, (max_value - min_value) * .12)
        self._value_min = min_value - padding
        self._value_max = max_value + padding
        colors = (QColor("#64c8a5"), QColor("#e47f69"), QColor("#6f9fe8"), QColor("#d4b25f"))
        for channel, values in enumerate(rows):
            painter.setPen(QPen(colors[channel % len(colors)], 2))
            previous = None
            for index, value in enumerate(values):
                point = self._point(self.duration_ms * index / max(1, len(values) - 1), value)
                x, y = point.x(), point.y()
                if previous is not None:
                    painter.drawLine(previous[0], previous[1], int(x), int(y))
                previous = (int(x), int(y))
        for key in keys:
            for channel, value in enumerate(self._channels(key.value)):
                point = self._point(key.time_ms, value)
                self._markers.append((point, key.id, channel))
                painter.setPen(QPen(colors[channel % len(colors)], 2))
                painter.setBrush(QColor("#101216"))
                painter.drawEllipse(point, 4.5, 4.5)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        nearest = min(
            self._markers,
            key=lambda marker: (marker[0] - event.position()).manhattanLength(),
            default=None,
        )
        if nearest is not None and (nearest[0] - event.position()).manhattanLength() <= 12:
            self._drag = (nearest[1], nearest[2])
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag is not None:
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        is_near = any((point - event.position()).manhattanLength() <= 12 for point, _key, _channel in self._markers)
        self.setCursor(Qt.OpenHandCursor if is_near else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        drag = self._drag
        self._drag = None
        self.unsetCursor()
        prop = self.property
        if drag is None or prop is None:
            return
        keyframe_id, channel = drag
        key = next((item for item in prop.keyframes if item.id == keyframe_id), None)
        if key is None:
            return
        time_ms = int(round(max(0.0, min(1.0, event.position().x() / max(1, self.width() - 1))) * self.duration_ms))
        y_ratio = 1.0 - max(0.0, min(1.0, event.position().y() / max(1, self.height() - 1)))
        value = self._value_min + y_ratio * (self._value_max - self._value_min)
        if isinstance(key.value, (list, tuple)):
            changed = list(key.value)
            if channel < len(changed):
                changed[channel] = value
            value = changed
        self.keyframe_changed.emit(keyframe_id, time_ms, value)

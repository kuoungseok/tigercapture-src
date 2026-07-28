from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.motion_designer.keyframes import evaluate_property
from app.motion_designer.schema import AnimatedProperty


class GraphEditor(QWidget):
    keyframe_changed = Signal(str, int, object)
    keyframe_selected = Signal(str)
    tangent_changed = Signal(str, str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.property: AnimatedProperty | None = None
        self.duration_ms = 1
        self._value_min = 0.0
        self._value_max = 1.0
        self._markers: list[tuple[QPointF, str, int]] = []
        self._tangent_markers: list[
            tuple[QPointF, str, str, float, float, float, float]
        ] = []
        self._drag: tuple[str, int] | None = None
        self._tangent_drag: tuple[
            str, str, float, float, float, float
        ] | None = None
        self._selected_keyframe_id = ""
        self.mode = "value"
        self.setMouseTracking(True)

    def set_property(self, prop: AnimatedProperty | None, *, duration_ms: int = 1) -> None:
        self.property = prop
        self.duration_ms = max(1, int(duration_ms))
        self.update()

    def set_mode(self, mode: str) -> None:
        self.mode = "speed" if str(mode).lower() == "speed" else "value"
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
        self._tangent_markers = []
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
        if self.mode == "speed":
            sample_step = self.duration_ms / max(1, len(sample_values) - 1)
            rows = [
                [
                    0.0 if index == 0 else (
                        values[index] - values[index - 1]
                    ) / max(1e-9, sample_step) * 1000.0
                    for index in range(len(values))
                ]
                for values in rows
            ]
            key_values = [value for row in rows for value in row]
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
        if self.mode == "value":
            handle_pen = QPen(QColor("#9aa7b8"), 1)
            for left, right in zip(keys, keys[1:]):
                if (
                    left.interpolation != "bezier"
                    and right.interpolation != "bezier"
                ):
                    continue
                left_value = self._channels(left.value)[0]
                right_value = self._channels(right.value)[0]
                delta_time = max(1.0, float(right.time_ms - left.time_ms))
                delta_value = float(right_value - left_value)
                left_point = self._point(left.time_ms, left_value)
                right_point = self._point(right.time_ms, right_value)
                out_time = left.time_ms + left.out_tangent[0] * delta_time
                out_value = left_value + left.out_tangent[1] * delta_value
                in_time = left.time_ms + right.in_tangent[0] * delta_time
                in_value = left_value + right.in_tangent[1] * delta_value
                out_point = self._point(out_time, out_value)
                in_point = self._point(in_time, in_value)
                painter.setPen(handle_pen)
                painter.drawLine(left_point, out_point)
                painter.drawLine(right_point, in_point)
                painter.setBrush(QColor("#d8dee8"))
                painter.drawRect(
                    int(out_point.x() - 3),
                    int(out_point.y() - 3),
                    6,
                    6,
                )
                painter.drawRect(
                    int(in_point.x() - 3),
                    int(in_point.y() - 3),
                    6,
                    6,
                )
                common = (
                    float(left.time_ms),
                    float(right.time_ms),
                    float(left_value),
                    float(right_value),
                )
                self._tangent_markers.append(
                    (out_point, left.id, "out", *common),
                )
                self._tangent_markers.append(
                    (in_point, right.id, "in", *common),
                )
        for key in keys:
            for channel, value in enumerate(self._channels(key.value)):
                display_value = value
                if self.mode == "speed" and channel < len(rows):
                    sample_index = max(0, min(
                        len(rows[channel]) - 1,
                        round(
                            key.time_ms
                            / max(1, self.duration_ms)
                            * (len(rows[channel]) - 1)
                        ),
                    ))
                    display_value = rows[channel][sample_index]
                point = self._point(key.time_ms, display_value)
                self._markers.append((point, key.id, channel))
                painter.setPen(QPen(colors[channel % len(colors)], 2))
                painter.setBrush(
                    QColor("#f2c14e")
                    if key.id == self._selected_keyframe_id
                    else QColor("#101216")
                )
                painter.drawEllipse(point, 4.5, 4.5)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        tangent = min(
            self._tangent_markers,
            key=lambda marker: (
                marker[0] - event.position()
            ).manhattanLength(),
            default=None,
        )
        if tangent is not None and (
            tangent[0] - event.position()
        ).manhattanLength() <= 10:
            self._tangent_drag = (
                tangent[1],
                tangent[2],
                tangent[3],
                tangent[4],
                tangent[5],
                tangent[6],
            )
            self._selected_keyframe_id = tangent[1]
            self.keyframe_selected.emit(tangent[1])
            event.accept()
            return
        nearest = min(
            self._markers,
            key=lambda marker: (marker[0] - event.position()).manhattanLength(),
            default=None,
        )
        if nearest is not None and (nearest[0] - event.position()).manhattanLength() <= 12:
            self._drag = (nearest[1], nearest[2])
            self._selected_keyframe_id = nearest[1]
            self.keyframe_selected.emit(nearest[1])
            self.update()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag is not None or self._tangent_drag is not None:
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        is_near = any((point - event.position()).manhattanLength() <= 12 for point, _key, _channel in self._markers)
        self.setCursor(Qt.OpenHandCursor if is_near else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        tangent_drag = self._tangent_drag
        self._tangent_drag = None
        if tangent_drag is not None:
            keyframe_id, side, left_time, right_time, left_value, right_value = (
                tangent_drag
            )
            time_value = (
                max(0.0, min(
                    1.0,
                    event.position().x() / max(1, self.width() - 1),
                ))
                * self.duration_ms
            )
            y_ratio = 1.0 - max(0.0, min(
                1.0,
                event.position().y() / max(1, self.height() - 1),
            ))
            graph_value = self._value_min + y_ratio * (
                self._value_max - self._value_min
            )
            x = max(0.0, min(
                1.0,
                (time_value - left_time) / max(1.0, right_time - left_time),
            ))
            delta = right_value - left_value
            y = (
                (graph_value - left_value) / delta
                if abs(delta) > 1e-9
                else 0.0
            )
            self.tangent_changed.emit(
                keyframe_id,
                side,
                [x, y],
            )
            self.unsetCursor()
            return
        drag = self._drag
        self._drag = None
        self.unsetCursor()
        prop = self.property
        if drag is None or prop is None or self.mode == "speed":
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

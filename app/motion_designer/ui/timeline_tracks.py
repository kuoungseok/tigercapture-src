from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from app.motion_designer.schema import AnimatedProperty, MotionComposition, MotionLayer


LAYER_COLORS = {
    "text": QColor("#4f87c8"), "image": QColor("#3a9b78"),
    "shape": QColor("#8b6cc1"), "line": QColor("#9b7b55"),
    "group": QColor("#4f657d"), "adjustment": QColor("#ad7042"),
    "null": QColor("#687078"),
}


class LayerTimelineView(QWidget):
    time_changed = Signal(int)
    layer_selected = Signal(str)
    layer_timing_changed = Signal(str, int, int)

    LABEL_WIDTH = 176
    HEADER_HEIGHT = 24
    ROW_HEIGHT = 25

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.composition: MotionComposition | None = None
        self.playhead_ms = 0
        self.selected_layer_id = ""
        self._drag: dict | None = None
        self.setMinimumHeight(130)
        self.setMouseTracking(True)

    def set_state(self, composition: MotionComposition, playhead_ms: int) -> None:
        self.composition = composition
        self.playhead_ms = int(playhead_ms)
        self.setMinimumHeight(self.HEADER_HEIGHT + max(4, len(composition.layers)) * self.ROW_HEIGHT + 2)
        self.update()

    def set_selected_layer(self, layer_id: str) -> None:
        self.selected_layer_id = str(layer_id or "")
        self.update()

    def _timeline_width(self) -> float:
        return max(1.0, self.width() - self.LABEL_WIDTH)

    def _x(self, time_ms: int) -> float:
        duration = max(1, self.composition.duration_ms if self.composition else 1)
        return self.LABEL_WIDTH + max(0, min(duration, int(time_ms))) / duration * self._timeline_width()

    def _time(self, x: float) -> int:
        duration = max(1, self.composition.duration_ms if self.composition else 1)
        return max(0, min(duration, int(round((x - self.LABEL_WIDTH) / self._timeline_width() * duration))))

    def _layers(self) -> list[MotionLayer]:
        return list(reversed(self.composition.layers)) if self.composition else []

    def _quality_markers(self) -> list[tuple[int, str]]:
        markers: list[tuple[int, str]] = []
        if self.composition is None:
            return markers
        for layer in self.composition.layers:
            for mask in layer.masks:
                tracking = mask.metadata.get("tracking_cache")
                if not isinstance(tracking, dict):
                    continue
                metadata = tracking.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                report = metadata.get("temporal_matte_quality")
                if not isinstance(report, dict):
                    continue
                stop_at = report.get("auto_stop_at_ms")
                if stop_at is not None:
                    markers.append((int(stop_at), "error"))
                markers.extend(
                    (int(value), "warning")
                    for value in report.get("correction_times_ms", [])
                    if stop_at is None or int(value) != int(stop_at)
                )
        return sorted(set(markers))

    def _row_layer(self, y: float) -> MotionLayer | None:
        row = int((y - self.HEADER_HEIGHT) // self.ROW_HEIGHT)
        layers = self._layers()
        return layers[row] if 0 <= row < len(layers) else None

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0f1115"))
        painter.fillRect(0, 0, self.LABEL_WIDTH, self.height(), QColor("#15181d"))
        painter.fillRect(0, 0, self.width(), self.HEADER_HEIGHT, QColor("#191c22"))
        composition = self.composition
        if composition is None:
            return
        duration = max(1, composition.duration_ms)
        painter.setPen(QPen(QColor("#323740"), 1))
        seconds = max(1, duration // 1000)
        step_seconds = 1 if seconds <= 20 else 5 if seconds <= 120 else 10
        for time_ms in range(0, duration + 1, step_seconds * 1000):
            x = int(self._x(time_ms))
            painter.drawLine(x, 0, x, self.height())
            painter.setPen(QColor("#8f969f"))
            painter.drawText(x + 4, 16, f"{time_ms / 1000:g}")
            painter.setPen(QPen(QColor("#323740"), 1))
        for time_ms, severity in self._quality_markers():
            x = self._x(time_ms)
            color = QColor("#ff4f64" if severity == "error" else "#f2b34d")
            painter.setBrush(color)
            painter.setPen(QPen(color.darker(135), 1))
            painter.drawPolygon(QPolygonF((
                QPointF(x - 5, 1),
                QPointF(x + 5, 1),
                QPointF(x, 10),
            )))
        for row, layer in enumerate(self._layers()):
            top = self.HEADER_HEIGHT + row * self.ROW_HEIGHT
            if layer.id == self.selected_layer_id:
                painter.fillRect(0, top, self.width(), self.ROW_HEIGHT, QColor("#25313a"))
            painter.setPen(QColor("#d4d8de"))
            name = painter.fontMetrics().elidedText(layer.name, Qt.ElideRight, self.LABEL_WIDTH - 28)
            painter.drawText(22, top + 17, name)
            painter.setBrush(QColor("#64c8a5") if layer.visible else QColor("#4c525a"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(8, top + 9, 6, 6)
            preview = self._drag if self._drag and self._drag["layer_id"] == layer.id else None
            start = int(preview["in_ms"] if preview else layer.in_ms)
            end = int(preview["out_ms"] if preview else layer.out_ms)
            rect = QRectF(self._x(start), top + 4, max(3.0, self._x(end) - self._x(start)), self.ROW_HEIGHT - 8)
            color = LAYER_COLORS.get(layer.layer_type, QColor("#4f657d"))
            painter.setBrush(color)
            painter.setPen(QPen(color.lighter(125), 1))
            painter.drawRoundedRect(rect, 2, 2)
            painter.setBrush(QColor("#efb45c"))
            painter.setPen(Qt.NoPen)
            key_times = {
                layer.in_ms + key.time_ms
                for prop in layer.transform.properties().values()
                for key in prop.keyframes
            }
            if layer.layer_type == "image":
                for name in ("tilt_x", "tilt_y", "perspective"):
                    value = layer.source.params.get(name)
                    if not isinstance(value, dict) or (
                        "default" not in value and "keyframes" not in value
                    ):
                        continue
                    prop = AnimatedProperty.from_dict(value)
                    key_times.update(
                        layer.in_ms + key.time_ms for key in prop.keyframes
                    )
            for key_time in key_times:
                x = self._x(key_time)
                y = top + self.ROW_HEIGHT * .5
                painter.drawPolygon(QPolygonF((QPointF(x, y - 4), QPointF(x + 4, y),
                                                QPointF(x, y + 4), QPointF(x - 4, y))))
            painter.setPen(QPen(QColor("#292e35"), 1))
            painter.drawLine(0, top + self.ROW_HEIGHT - 1, self.width(), top + self.ROW_HEIGHT - 1)
        playhead_x = int(self._x(self.playhead_ms))
        painter.setPen(QPen(QColor("#f0a44b"), 2))
        painter.drawLine(playhead_x, 0, playhead_x, self.height())
        painter.setBrush(QColor("#f0a44b"))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygonF((QPointF(playhead_x - 5, 0), QPointF(playhead_x + 5, 0),
                                        QPointF(playhead_x, 7))))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        layer = self._row_layer(event.position().y())
        if layer is None:
            if event.position().x() >= self.LABEL_WIDTH:
                self.time_changed.emit(self._time(event.position().x()))
            return
        self.selected_layer_id = layer.id
        self.layer_selected.emit(layer.id)
        if event.position().x() < self.LABEL_WIDTH:
            self.update()
            return
        time_ms = self._time(event.position().x())
        self.time_changed.emit(time_ms)
        start_x, end_x = self._x(layer.in_ms), self._x(layer.out_ms)
        if abs(event.position().x() - start_x) <= 7:
            mode = "trim_start"
        elif abs(event.position().x() - end_x) <= 7:
            mode = "trim_end"
        elif start_x <= event.position().x() <= end_x:
            mode = "move"
        else:
            return
        self._drag = {"layer_id": layer.id, "mode": mode, "press_ms": time_ms,
                      "original_in": layer.in_ms, "original_out": layer.out_ms,
                      "in_ms": layer.in_ms, "out_ms": layer.out_ms}

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._drag or not self.composition:
            return
        duration = self.composition.duration_ms
        current = self._time(event.position().x())
        delta = current - self._drag["press_ms"]
        if self._drag["mode"] == "trim_start":
            self._drag["in_ms"] = max(0, min(self._drag["original_out"] - 1,
                                               self._drag["original_in"] + delta))
        elif self._drag["mode"] == "trim_end":
            self._drag["out_ms"] = min(duration, max(self._drag["original_in"] + 1,
                                                self._drag["original_out"] + delta))
        else:
            span = self._drag["original_out"] - self._drag["original_in"]
            start = max(0, min(duration - span, self._drag["original_in"] + delta))
            self._drag["in_ms"], self._drag["out_ms"] = start, start + span
        self.update()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        if self._drag:
            drag = self._drag
            self._drag = None
            if (drag["in_ms"], drag["out_ms"]) != (drag["original_in"], drag["original_out"]):
                self.layer_timing_changed.emit(drag["layer_id"], int(drag["in_ms"]), int(drag["out_ms"]))
            self.update()

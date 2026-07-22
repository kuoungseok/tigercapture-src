from __future__ import annotations

from copy import deepcopy
from math import hypot
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem, QGraphicsPathItem,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView,
)

from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.adapters.typography import render_typography
from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.vector_shapes import (
    VectorPath,
    evaluate_source_param,
    flatten_path,
    path_from_params,
)
from app.motion_designer.vector_tessellation import (
    build_vector_painter_path,
    painter_path_from_vector,
)


class _VectorHandleItem(QGraphicsEllipseItem):
    def __init__(self, position: QPointF, color: QColor, callback, parent: QGraphicsItem) -> None:
        super().__init__(-5, -5, 10, 10, parent)
        self._callback = callback
        self.setPos(position)
        self.setPen(QPen(QColor("#111317"), 1))
        self.setBrush(QBrush(color))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setZValue(100)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self._callback(self.pos())


class MotionCanvas(QGraphicsView):
    layer_selected = Signal(str)
    layer_moved = Signal(str, float, float)
    vector_path_changed = Signal(str, object)
    typography_path_changed = Signal(str, object)
    typography_path_offset_changed = Signal(str, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(QColor("#0b0d11"))
        self._composition: MotionComposition | None = None
        self._time_ms = 0
        self._stage: QGraphicsRectItem | None = None
        self._show_grid = False
        self._show_safe_guides = True
        self._fit_mode = True
        self._selected_layer_id = ""
        self._loading_scene = False
        self._scene.selectionChanged.connect(self._selection_changed)

    def set_composition(self, composition: MotionComposition, time_ms: int = 0) -> None:
        self._composition = composition
        self._time_ms = int(time_ms)
        self.refresh()

    def set_time(self, time_ms: int) -> None:
        self._time_ms = int(time_ms)
        self.refresh(preserve_view=True)

    def refresh(self, *, preserve_view: bool = False) -> None:
        composition = self._composition
        if composition is None:
            return
        transform = self.transform()
        self._loading_scene = True
        self._scene.clear()
        stage_rect = QRectF(0, 0, composition.width, composition.height)
        self._stage = self._scene.addRect(stage_rect, QPen(QColor("#6b7280"), 2), QBrush(QColor("#f7f7f5")))
        self._stage.setZValue(-10000)
        if self._show_grid:
            grid_pen = QPen(QColor(80, 92, 105, 75), 1)
            for ratio in (.25, .5, .75):
                x, y = composition.width * ratio, composition.height * ratio
                self._scene.addLine(x, 0, x, composition.height, grid_pen).setZValue(8990)
                self._scene.addLine(0, y, composition.width, y, grid_pen).setZValue(8990)
        safe_pen = QPen(QColor(70, 125, 160, 120), 1, Qt.DashLine)
        margin_x, margin_y = composition.width * .05, composition.height * .05
        if self._show_safe_guides:
            self._scene.addRect(stage_rect.adjusted(margin_x, margin_y, -margin_x, -margin_y), safe_pen).setZValue(9000)
        states = {state.id: state for state in evaluate_composition(composition, self._time_ms)}
        from app.motion_designer.boolean_layers import consumed_boolean_operand_ids, resolve_boolean_layer
        consumed_operand_ids = consumed_boolean_operand_ids(composition, states)
        for z_index, layer in enumerate(composition.layers):
            state = states[layer.id]
            if not state.active or layer.layer_type in {"group", "adjustment"} or layer.id in consumed_operand_ids:
                continue
            item = self._make_item(resolve_boolean_layer(composition, layer, states))
            item.setData(0, layer.id)
            item.setFlag(QGraphicsItem.ItemIsSelectable, not layer.locked)
            item.setFlag(QGraphicsItem.ItemIsMovable, not layer.locked)
            item.setOpacity(state.opacity)
            a, b, c, d, tx, ty = state.matrix
            item.setTransform(QTransform(a, b, 0.0, c, d, 0.0, tx, ty, 1.0))
            item.setZValue(z_index)
            self._scene.addItem(item)
            if layer.id == self._selected_layer_id:
                item.setSelected(True)
                self._add_vector_handles(layer, item)
                self._add_typography_path_handles(layer, item)
        scene_rect = stage_rect if self._fit_mode else stage_rect.adjusted(-100, -100, 100, 100)
        self._scene.setSceneRect(scene_rect)
        if preserve_view and not self._fit_mode:
            self.setTransform(transform)
        else:
            self.fitInView(stage_rect, Qt.KeepAspectRatio)
        self._loading_scene = False

    def set_selected_layer(self, layer_id: str) -> None:
        layer_id = str(layer_id or "")
        if layer_id == self._selected_layer_id:
            return
        self._selected_layer_id = layer_id
        self.refresh(preserve_view=True)

    def _make_item(self, layer: MotionLayer) -> QGraphicsItem:
        params = layer.source.params
        width = float(evaluate_source_param(params, "width", self._time_ms, 400.0))
        height = float(evaluate_source_param(params, "height", self._time_ms, 220.0))
        rect = QRectF(-width * .5, -height * .5, width, height)
        fill = QColor(str(evaluate_source_param(params, "fill", self._time_ms, "#3f8fba")))
        if layer.layer_type == "text":
            container = QGraphicsRectItem(rect)
            container.setPen(QPen(Qt.NoPen))
            container.setBrush(QBrush(Qt.NoBrush))
            image = render_typography(layer, self._time_ms)
            if not image.isNull():
                pixmap = QGraphicsPixmapItem(QPixmap.fromImage(image), container)
                pixmap.setOffset(-image.width() * .5, -image.height() * .5)
                pixmap.setAcceptedMouseButtons(Qt.NoButton)
            return container
        if layer.layer_type == "image" and layer.source.uri and Path(layer.source.uri).is_file():
            pixmap = QPixmap(layer.source.uri)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(int(width), int(height), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                item = QGraphicsPixmapItem(pixmap)
                item.setOffset(-pixmap.width() * .5, -pixmap.height() * .5)
                return item
        if layer.layer_type == "line":
            item = QGraphicsLineItem(-width * .5, 0, width * .5, 0)
            item.setPen(QPen(fill, float(params.get("stroke_width", 4.0))))
            return item
        shape = str(params.get("shape", "rectangle"))
        if (
            shape in {"path", "polygon", "star"}
            or isinstance(params.get("path"), dict)
            or isinstance(params.get("boolean"), dict)
        ):
            path = build_vector_painter_path(params, self._time_ms)
            path = QTransform.fromTranslate(-width * .5, -height * .5).map(path)
            item = QGraphicsPathItem(path)
            item.setPen(QPen(
                QColor(str(evaluate_source_param(params, "stroke", self._time_ms, "#20242b"))),
                float(evaluate_source_param(params, "stroke_width", self._time_ms, 2.0)),
            ))
            item.setBrush(QBrush(fill))
            return item
        pen = QPen(QColor(str(params.get("stroke", "#20242b"))), 2)
        if shape == "ellipse":
            item = QGraphicsEllipseItem(rect)
        else:
            item = QGraphicsRectItem(rect)
        item.setPen(pen)
        item.setBrush(QBrush(fill))
        return item

    def _add_vector_handles(self, layer: MotionLayer, item: QGraphicsItem) -> None:
        params = layer.source.params
        if layer.layer_type != "shape" or str(params.get("shape", "")) != "path":
            return
        width = float(params.get("width", 400.0))
        height = float(params.get("height", 220.0))
        path = path_from_params(params, self._time_ms)
        for index, point in enumerate(path.points):
            center = QPointF(point.position[0] - width * .5, point.position[1] - height * .5)
            for component, tangent, color in (
                ("in", point.in_tangent, QColor("#e47f69")),
                ("out", point.out_tangent, QColor("#64c8a5")),
            ):
                if tangent == (0.0, 0.0):
                    continue
                handle = QPointF(center.x() + tangent[0], center.y() + tangent[1])
                line = QGraphicsLineItem(center.x(), center.y(), handle.x(), handle.y(), item)
                line.setPen(QPen(QColor("#8d949d"), 1))
                line.setZValue(90)
                child = _VectorHandleItem(
                    handle, color,
                    lambda position, row=index, kind=component: self._move_vector_handle(
                        layer, row, kind, position, width, height,
                    ),
                    item,
                )
                child.setData(0, layer.id)
                child.setData(1, "vector_handle")
                child.setData(2, index)
                child.setData(3, component)
            anchor = _VectorHandleItem(
                center, QColor("#f0a44b"),
                lambda position, row=index: self._move_vector_handle(
                    layer, row, "position", position, width, height,
                ),
                item,
            )
            anchor.setData(0, layer.id)
            anchor.setData(1, "vector_handle")
            anchor.setData(2, index)
            anchor.setData(3, "position")

    def _add_typography_path_handles(self, layer: MotionLayer, item: QGraphicsItem) -> None:
        if layer.layer_type != "text":
            return
        params = layer.source.params
        path_data = evaluate_source_param(params, "text_path", self._time_ms, None)
        if not isinstance(path_data, dict) or not path_data.get("points"):
            return
        try:
            path = VectorPath.from_dict(path_data)
        except (TypeError, ValueError):
            return
        width = float(evaluate_source_param(params, "width", self._time_ms, 640.0))
        height = float(evaluate_source_param(params, "height", self._time_ms, 240.0))
        display_path = painter_path_from_vector(path)
        display_path.translate(-width * .5, -height * .5)
        guide = QGraphicsPathItem(display_path, item)
        guide.setPen(QPen(QColor("#56d7c4"), 2, Qt.DashLine))
        guide.setBrush(QBrush(Qt.NoBrush))
        guide.setAcceptedMouseButtons(Qt.NoButton)
        guide.setZValue(89)

        for index, point in enumerate(path.points):
            center = QPointF(point.position[0] - width * .5, point.position[1] - height * .5)
            for component, tangent, color in (
                ("in", point.in_tangent, QColor("#e47f69")),
                ("out", point.out_tangent, QColor("#64c8a5")),
            ):
                if tangent == (0.0, 0.0):
                    continue
                handle = QPointF(center.x() + tangent[0], center.y() + tangent[1])
                line = QGraphicsLineItem(center.x(), center.y(), handle.x(), handle.y(), item)
                line.setPen(QPen(QColor("#8d949d"), 1))
                line.setZValue(90)
                child = _VectorHandleItem(
                    handle,
                    color,
                    lambda position, row=index, kind=component: self._move_typography_path_handle(
                        layer, row, kind, position, width, height,
                    ),
                    item,
                )
                self._set_typography_handle_data(child, layer.id, index, component)
            anchor = _VectorHandleItem(
                center,
                QColor("#f0a44b"),
                lambda position, row=index: self._move_typography_path_handle(
                    layer, row, "position", position, width, height,
                ),
                item,
            )
            self._set_typography_handle_data(anchor, layer.id, index, "position")

        samples = flatten_path(path, tolerance=.45)
        offset = float(evaluate_source_param(params, "text_path_offset", self._time_ms, .5) or 0.0)
        marker_point = self._polyline_point(samples, offset)
        if marker_point is not None:
            marker = _VectorHandleItem(
                QPointF(marker_point[0] - width * .5, marker_point[1] - height * .5),
                QColor("#f5de72"),
                lambda position: self._move_typography_path_offset(
                    layer, position, samples, width, height,
                ),
                item,
            )
            marker.setRect(-7, -7, 14, 14)
            marker.setData(0, layer.id)
            marker.setData(1, "typography_path_offset")

    @staticmethod
    def _set_typography_handle_data(item: QGraphicsItem, layer_id: str,
                                     index: int, component: str) -> None:
        item.setData(0, layer_id)
        item.setData(1, "typography_path_handle")
        item.setData(2, index)
        item.setData(3, component)

    @staticmethod
    def _polyline_point(points: list[tuple[float, float]], offset: float) -> tuple[float, float] | None:
        if len(points) < 2:
            return None
        lengths = [hypot(end[0] - start[0], end[1] - start[1]) for start, end in zip(points, points[1:])]
        remaining = max(0.0, min(1.0, float(offset))) * sum(lengths)
        for (start, end), length in zip(zip(points, points[1:]), lengths):
            if remaining <= length or length <= 1e-9:
                amount = 0.0 if length <= 1e-9 else remaining / length
                return (
                    start[0] + (end[0] - start[0]) * amount,
                    start[1] + (end[1] - start[1]) * amount,
                )
            remaining -= length
        return points[-1]

    def _editable_path_payload(self, layer: MotionLayer) -> tuple[dict, dict, bool]:
        raw = deepcopy(layer.source.params.get("path"))
        animated = isinstance(raw, dict) and ("default" in raw or "keyframes" in raw)
        path_data = deepcopy(raw.get("default")) if animated else deepcopy(raw)
        if not isinstance(path_data, dict) or not path_data.get("points"):
            path_data = path_from_params(layer.source.params, self._time_ms).to_dict()
        return raw if isinstance(raw, dict) else {}, path_data, animated

    def _emit_path_payload(self, layer: MotionLayer, raw: dict, path_data: dict, animated: bool) -> None:
        if animated:
            raw["default"] = path_data
            self.vector_path_changed.emit(layer.id, raw)
        else:
            self.vector_path_changed.emit(layer.id, path_data)

    def _editable_typography_path_payload(self, layer: MotionLayer) -> tuple[dict, dict, bool]:
        raw = deepcopy(layer.source.params.get("text_path"))
        animated = isinstance(raw, dict) and ("default" in raw or "keyframes" in raw)
        path_data = deepcopy(raw.get("default")) if animated else deepcopy(raw)
        if not isinstance(path_data, dict) or not path_data.get("points"):
            width = float(evaluate_source_param(layer.source.params, "width", self._time_ms, 640.0))
            height = float(evaluate_source_param(layer.source.params, "height", self._time_ms, 240.0))
            from app.motion_designer.vector_shapes import default_pen_path
            path_data = default_pen_path(width, height).to_dict()
        return raw if isinstance(raw, dict) else {}, path_data, animated

    def _emit_typography_path_payload(self, layer: MotionLayer, raw: dict,
                                      path_data: dict, animated: bool) -> None:
        if animated:
            raw["default"] = path_data
            self.typography_path_changed.emit(layer.id, raw)
        else:
            self.typography_path_changed.emit(layer.id, path_data)

    def _move_vector_handle(self, layer: MotionLayer, index: int, component: str,
                            position: QPointF, width: float, height: float) -> None:
        raw, path_data, animated = self._editable_path_payload(layer)
        points = path_data.get("points", [])
        if not 0 <= index < len(points):
            return
        absolute = [position.x() + width * .5, position.y() + height * .5]
        if component == "position":
            points[index]["position"] = absolute
        else:
            anchor = points[index].get("position") or [0.0, 0.0]
            points[index][component] = [
                absolute[0] - float(anchor[0]), absolute[1] - float(anchor[1]),
            ]
        self._emit_path_payload(layer, raw, path_data, animated)

    def _move_typography_path_handle(self, layer: MotionLayer, index: int, component: str,
                                     position: QPointF, width: float, height: float) -> None:
        raw, path_data, animated = self._editable_typography_path_payload(layer)
        points = path_data.get("points", [])
        if not 0 <= index < len(points):
            return
        absolute = [position.x() + width * .5, position.y() + height * .5]
        if component == "position":
            points[index]["position"] = absolute
        else:
            anchor = points[index].get("position") or [0.0, 0.0]
            points[index][component] = [
                absolute[0] - float(anchor[0]),
                absolute[1] - float(anchor[1]),
            ]
        self._emit_typography_path_payload(layer, raw, path_data, animated)

    def _move_typography_path_offset(self, layer: MotionLayer, position: QPointF,
                                     samples: list[tuple[float, float]],
                                     width: float, height: float) -> None:
        if len(samples) < 2:
            return
        point = (position.x() + width * .5, position.y() + height * .5)
        lengths = [hypot(end[0] - start[0], end[1] - start[1]) for start, end in zip(samples, samples[1:])]
        total = sum(lengths)
        if total <= 1e-9:
            return
        best_distance = float("inf")
        best_offset = 0.0
        elapsed = 0.0
        for (start, end), length in zip(zip(samples, samples[1:]), lengths):
            dx, dy = end[0] - start[0], end[1] - start[1]
            amount = 0.0 if length <= 1e-9 else max(0.0, min(1.0, (
                (point[0] - start[0]) * dx + (point[1] - start[1]) * dy
            ) / (length * length)))
            projected = (start[0] + dx * amount, start[1] + dy * amount)
            distance = hypot(point[0] - projected[0], point[1] - projected[1])
            if distance < best_distance:
                best_distance = distance
                best_offset = (elapsed + length * amount) / total
            elapsed += length
        self.typography_path_offset_changed.emit(layer.id, best_offset)

    @staticmethod
    def _distance_to_segment(point: tuple[float, float], start: tuple[float, float],
                             end: tuple[float, float]) -> float:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-9:
            return hypot(point[0] - start[0], point[1] - start[1])
        amount = max(0.0, min(1.0, (
            (point[0] - start[0]) * dx + (point[1] - start[1]) * dy
        ) / length_sq))
        projected = (start[0] + dx * amount, start[1] + dy * amount)
        return hypot(point[0] - projected[0], point[1] - projected[1])

    def _add_vector_point(self, layer_id: str, scene_position: QPointF) -> None:
        if self._composition is None:
            return
        layer = next((row for row in self._composition.layers if row.id == layer_id), None)
        if layer is None or layer.layer_type != "shape" or str(layer.source.params.get("shape")) != "path":
            return
        layer_item = next((
            item for item in self._scene.items()
            if str(item.data(0) or "") == layer_id and item.data(1) != "vector_handle"
            and item.parentItem() is None
        ), None)
        if layer_item is None:
            return
        width = float(evaluate_source_param(layer.source.params, "width", self._time_ms, 400.0))
        height = float(evaluate_source_param(layer.source.params, "height", self._time_ms, 220.0))
        local = layer_item.mapFromScene(scene_position)
        source_point = (local.x() + width * .5, local.y() + height * .5)
        raw, path_data, animated = self._editable_path_payload(layer)
        points = path_data.get("points", [])
        segment_count = len(points) if bool(path_data.get("closed", True)) else max(0, len(points) - 1)
        insert_at = len(points)
        if segment_count:
            best_segment = min(
                range(segment_count),
                key=lambda index: self._distance_to_segment(
                    source_point,
                    tuple(float(value) for value in points[index]["position"][:2]),
                    tuple(float(value) for value in points[(index + 1) % len(points)]["position"][:2]),
                ),
            )
            insert_at = best_segment + 1
        points.insert(insert_at, {
            "position": [source_point[0], source_point[1]],
            "in": [0.0, 0.0],
            "out": [0.0, 0.0],
        })
        self._emit_path_payload(layer, raw, path_data, animated)

    def _add_typography_path_point(self, layer_id: str, scene_position: QPointF) -> bool:
        if self._composition is None:
            return False
        layer = next((row for row in self._composition.layers if row.id == layer_id), None)
        if layer is None or layer.layer_type != "text":
            return False
        path_value = evaluate_source_param(layer.source.params, "text_path", self._time_ms, None)
        if not isinstance(path_value, dict) or not path_value.get("points"):
            return False
        layer_item = next((
            item for item in self._scene.items()
            if str(item.data(0) or "") == layer_id
            and item.data(1) not in {"typography_path_handle", "typography_path_offset"}
            and item.parentItem() is None
        ), None)
        if layer_item is None:
            return False
        width = float(evaluate_source_param(layer.source.params, "width", self._time_ms, 640.0))
        height = float(evaluate_source_param(layer.source.params, "height", self._time_ms, 240.0))
        local = layer_item.mapFromScene(scene_position)
        source_point = (local.x() + width * .5, local.y() + height * .5)
        raw, path_data, animated = self._editable_typography_path_payload(layer)
        points = path_data.get("points", [])
        segment_count = len(points) if bool(path_data.get("closed", False)) else max(0, len(points) - 1)
        insert_at = len(points)
        if segment_count:
            best_segment = min(
                range(segment_count),
                key=lambda index: self._distance_to_segment(
                    source_point,
                    tuple(float(value) for value in points[index]["position"][:2]),
                    tuple(float(value) for value in points[(index + 1) % len(points)]["position"][:2]),
                ),
            )
            insert_at = best_segment + 1
        points.insert(insert_at, {
            "position": [source_point[0], source_point[1]],
            "in": [0.0, 0.0],
            "out": [0.0, 0.0],
        })
        self._emit_typography_path_payload(layer, raw, path_data, animated)
        return True

    def _delete_vector_component(self, layer_id: str, index: int, component: str) -> None:
        if self._composition is None:
            return
        layer = next((row for row in self._composition.layers if row.id == layer_id), None)
        if layer is None:
            return
        raw, path_data, animated = self._editable_path_payload(layer)
        points = path_data.get("points", [])
        if not 0 <= index < len(points):
            return
        if component in {"in", "out"}:
            points[index][component] = [0.0, 0.0]
        else:
            minimum = 3 if bool(path_data.get("closed", True)) else 2
            if len(points) <= minimum:
                return
            points.pop(index)
        self._emit_path_payload(layer, raw, path_data, animated)

    def _delete_typography_path_component(self, layer_id: str, index: int,
                                          component: str) -> None:
        if self._composition is None:
            return
        layer = next((row for row in self._composition.layers if row.id == layer_id), None)
        if layer is None or layer.layer_type != "text":
            return
        raw, path_data, animated = self._editable_typography_path_payload(layer)
        points = path_data.get("points", [])
        if not 0 <= index < len(points):
            return
        if component in {"in", "out"}:
            points[index][component] = [0.0, 0.0]
        elif len(points) > 2:
            points.pop(index)
        else:
            return
        self._emit_typography_path_payload(layer, raw, path_data, animated)

    def mouseDoubleClickEvent(self, event) -> None:
        hit = self.itemAt(event.position().toPoint())
        if event.button() == Qt.LeftButton and (hit is None or hit.data(1) != "vector_handle"):
            layer_id = self._selected_layer_id
            if layer_id:
                scene_position = self.mapToScene(event.position().toPoint())
                if self._add_typography_path_point(layer_id, scene_position):
                    event.accept()
                    return
                self._add_vector_point(layer_id, scene_position)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in {Qt.Key_Delete, Qt.Key_Backspace}:
            handle = next((
                item for item in self._scene.selectedItems()
                if item.data(1) in {"vector_handle", "typography_path_handle"}
            ), None)
            if handle is not None:
                if handle.data(1) == "typography_path_handle":
                    self._delete_typography_path_component(
                        str(handle.data(0) or ""), int(handle.data(2)),
                        str(handle.data(3) or "position"),
                    )
                else:
                    self._delete_vector_component(
                        str(handle.data(0) or ""), int(handle.data(2)),
                        str(handle.data(3) or "position"),
                    )
                event.accept()
                return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        self._fit_mode = False
        if self._stage is not None:
            self._scene.setSceneRect(self._stage.rect().adjusted(-100, -100, 100, 100))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def set_zoom_mode(self, value: str) -> None:
        if self._stage is None:
            return
        if str(value).lower() == "fit":
            self._fit_mode = True
            self._scene.setSceneRect(self._stage.rect())
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.fitInView(self._stage.rect(), Qt.KeepAspectRatio)
            return
        self._fit_mode = False
        self._scene.setSceneRect(self._stage.rect().adjusted(-100, -100, 100, 100))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        try:
            ratio = max(.05, float(str(value).rstrip("%")) / 100.0)
        except ValueError:
            return
        self.resetTransform()
        self.scale(ratio, ratio)
        self.centerOn(self._stage.rect().center())

    def set_grid_visible(self, visible: bool) -> None:
        self._show_grid = bool(visible)
        self.refresh(preserve_view=True)

    def set_safe_guides_visible(self, visible: bool) -> None:
        self._show_safe_guides = bool(visible)
        self.refresh(preserve_view=True)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        for item in self._scene.selectedItems():
            if item.data(1) in {
                "vector_handle", "typography_path_handle", "typography_path_offset",
            }:
                continue
            layer_id = str(item.data(0) or "")
            if layer_id and not item.pos().isNull():
                self.layer_moved.emit(layer_id, item.pos().x(), item.pos().y())
                item.setPos(0, 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_mode and self._stage is not None and not self.sceneRect().isEmpty():
            self._scene.setSceneRect(self._stage.rect())
            self.fitInView(self._stage.rect(), Qt.KeepAspectRatio)

    def _selection_changed(self) -> None:
        if self._loading_scene:
            return
        items = self._scene.selectedItems()
        self.layer_selected.emit(str(items[0].data(0) or "") if items else "")

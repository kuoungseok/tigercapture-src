from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QRadialGradient

from app.motion_designer.schema import MotionLayer
from app.motion_designer.source_frame import transparent_image
from app.motion_designer.vector_shapes import evaluate_source_param, repeater_instances
from app.motion_designer.vector_tessellation import build_vector_painter_path


def _color(value, fallback: str) -> QColor:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        channels = [float(channel) for channel in value]
        if len(channels) >= 3:
            scale = 1.0 if max(channels[:3]) <= 1.0 else 255.0
            alpha = channels[3] if len(channels) >= 4 else scale
            return QColor.fromRgbF(
                channels[0] / scale, channels[1] / scale, channels[2] / scale, alpha / scale,
            )
    color = QColor(str(value if value is not None else fallback))
    return color if color.isValid() else QColor(fallback)


def _brush(params: Mapping[str, object], time_ms: float, width: int, height: int):
    fill = _color(evaluate_source_param(params, "fill", time_ms, "#3f8fba"), "#3f8fba")
    gradient_data = evaluate_source_param(params, "gradient", time_ms, None)
    if isinstance(gradient_data, list) and len(gradient_data) >= 2:
        gradient = QLinearGradient(0, 0, width, height)
        for index, color in enumerate(gradient_data):
            gradient.setColorAt(index / max(1, len(gradient_data) - 1), _color(color, "#ffffff"))
        return gradient
    if not isinstance(gradient_data, Mapping):
        return fill
    kind = str(gradient_data.get("type") or "linear").lower()
    start = list(gradient_data.get("start") or [0.0, 0.0])
    end = list(gradient_data.get("end") or [1.0, 1.0])
    if kind == "radial":
        center = QPointF(float(start[0]) * width, float(start[1]) * height)
        radius = max(1.0, float(gradient_data.get("radius", 1.0) or 1.0) * max(width, height))
        gradient = QRadialGradient(center, radius)
    else:
        gradient = QLinearGradient(
            float(start[0]) * width, float(start[1]) * height,
            float(end[0]) * width, float(end[1]) * height,
        )
    stops = list(gradient_data.get("stops") or [])
    for index, stop in enumerate(stops):
        if isinstance(stop, Mapping):
            position, color = float(stop.get("position", 0.0)), stop.get("color")
        elif isinstance(stop, Sequence) and len(stop) >= 2:
            position, color = float(stop[0]), stop[1]
        else:
            position, color = index / max(1, len(stops) - 1), stop
        gradient.setColorAt(max(0.0, min(1.0, position)), _color(color, "#ffffff"))
    return gradient if stops else fill


def _pen(params: Mapping[str, object], time_ms: float) -> QPen:
    stroke = _color(evaluate_source_param(params, "stroke", time_ms, "#20242b"), "#20242b")
    width = float(evaluate_source_param(params, "stroke_width", time_ms, 2.0))
    pen = QPen(stroke, max(0.0, width))
    cap = str(evaluate_source_param(params, "cap", time_ms, "square")).lower()
    join = str(evaluate_source_param(params, "join", time_ms, "miter")).lower()
    pen.setCapStyle({"round": Qt.RoundCap, "flat": Qt.FlatCap}.get(cap, Qt.SquareCap))
    pen.setJoinStyle({"round": Qt.RoundJoin, "bevel": Qt.BevelJoin}.get(join, Qt.MiterJoin))
    dash = evaluate_source_param(params, "dash", time_ms, [])
    if isinstance(dash, Sequence) and not isinstance(dash, (str, bytes)) and dash:
        pen.setDashPattern([max(.01, float(value)) for value in dash])
    return pen


def render_shape(layer: MotionLayer, time_ms: float = 0.0):
    params = layer.source.params
    width = max(1, int(round(float(evaluate_source_param(params, "width", time_ms, 400)))))
    height = max(1, int(round(float(evaluate_source_param(params, "height", time_ms, 220)))))
    image = transparent_image(width, height)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    if layer.layer_type == "line":
        painter.setPen(_pen(params, time_ms))
        painter.drawLine(0, height // 2, width, height // 2)
    else:
        path = build_vector_painter_path(params, time_ms)
        trim = evaluate_source_param(params, "trim", time_ms, {})
        partial_trim = isinstance(trim, Mapping) and (
            float(trim.get("start", 0.0) or 0.0) > 0.0
            or float(trim.get("end", 1.0) if trim.get("end", 1.0) is not None else 1.0) < 1.0
            or float(trim.get("offset", 0.0) or 0.0) != 0.0
        )
        painter.setPen(_pen(params, time_ms))
        painter.setBrush(Qt.NoBrush if partial_trim else _brush(params, time_ms, width, height))
        repeater = evaluate_source_param(params, "repeater", time_ms, {})
        for instance in repeater_instances(repeater if isinstance(repeater, Mapping) else {}):
            painter.save()
            painter.setOpacity(float(instance["opacity"]))
            painter.translate(width * .5, height * .5)
            painter.translate(*instance["translate"])
            painter.rotate(float(instance["rotation"]))
            painter.scale(*instance["scale"])
            painter.translate(-width * .5, -height * .5)
            painter.drawPath(path)
            painter.restore()
    painter.end()
    return image

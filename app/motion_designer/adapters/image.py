from __future__ import annotations

from math import cos, radians, sin
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPolygonF, QTransform

from app.motion_designer.schema import MotionLayer
from app.motion_designer.source_frame import premultiplied, transparent_image
from app.motion_designer.vector_shapes import evaluate_source_param


def _perspective_tilt(
    image: QImage,
    *,
    tilt_x_degrees: float,
    tilt_y_degrees: float,
    perspective: float,
) -> QImage:
    if image.isNull() or (
        abs(float(tilt_x_degrees)) < 1e-4
        and abs(float(tilt_y_degrees)) < 1e-4
    ):
        return image
    width, height = image.width(), image.height()
    center_x, center_y = width * 0.5, height * 0.5
    angle_x = radians(max(-70.0, min(70.0, float(tilt_x_degrees))))
    angle_y = radians(max(-70.0, min(70.0, float(tilt_y_degrees))))
    cosine_x, sine_x = cos(angle_x), sin(angle_x)
    cosine_y, sine_y = cos(angle_y), sin(angle_y)
    camera_distance = max(width, height) * max(1.2, min(8.0, float(perspective)))

    projected: list[QPointF] = []
    for x, y in (
        (-center_x, -center_y),
        (center_x, -center_y),
        (center_x, center_y),
        (-center_x, center_y),
    ):
        rotated_y = y * cosine_x
        rotated_z = y * sine_x
        rotated_x = x * cosine_y + rotated_z * sine_y
        rotated_z = -x * sine_y + rotated_z * cosine_y
        factor = camera_distance / max(camera_distance * 0.25, camera_distance - rotated_z)
        projected.append(QPointF(
            center_x + rotated_x * factor,
            center_y + rotated_y * factor,
        ))

    source_quad = QPolygonF([
        QPointF(0.0, 0.0),
        QPointF(float(width), 0.0),
        QPointF(float(width), float(height)),
        QPointF(0.0, float(height)),
    ])
    transform = QTransform.quadToQuad(source_quad, QPolygonF(projected))
    output = transparent_image(width, height)
    painter = QPainter(output)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.setTransform(transform)
    painter.drawImage(0, 0, image)
    painter.end()
    return output


def render_image(layer: MotionLayer, time_ms: float = 0.0):
    path = Path(layer.source.uri)
    if not path.is_file():
        return transparent_image(1, 1)
    source = QImage(str(path))
    if source.isNull():
        return transparent_image(1, 1)
    params = layer.source.params
    crop = params.get("crop")
    if isinstance(crop, (list, tuple)) and len(crop) >= 4:
        cx, cy, cw, ch = [float(value) for value in crop[:4]]
        if max(abs(cx), abs(cy), abs(cw), abs(ch)) <= 1.0:
            cx, cy, cw, ch = cx * source.width(), cy * source.height(), cw * source.width(), ch * source.height()
        source = source.copy(int(cx), int(cy), max(1, int(cw)), max(1, int(ch)))
    width = int(params.get("width", source.width()))
    height = int(params.get("height", source.height()))
    output = transparent_image(width, height)
    painter = QPainter(output)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    radius = float(params.get("radius", 0.0))
    if radius > 0:
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
        painter.setClipPath(clip)
    fit = str(params.get("fit", "contain"))
    aspect = Qt.KeepAspectRatioByExpanding if fit == "cover" else Qt.KeepAspectRatio
    scaled = source.scaled(width, height, aspect, Qt.SmoothTransformation)
    painter.drawImage((width - scaled.width()) // 2, (height - scaled.height()) // 2, scaled)
    painter.end()
    output = _perspective_tilt(
        output,
        tilt_x_degrees=float(evaluate_source_param(params, "tilt_x", time_ms, 0.0)),
        tilt_y_degrees=float(evaluate_source_param(params, "tilt_y", time_ms, 0.0)),
        perspective=float(evaluate_source_param(params, "perspective", time_ms, 2.6)),
    )
    return premultiplied(output)

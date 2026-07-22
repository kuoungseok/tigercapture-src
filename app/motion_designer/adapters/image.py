from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QPainterPath

from app.motion_designer.schema import MotionLayer
from app.motion_designer.source_frame import premultiplied, transparent_image


def render_image(layer: MotionLayer):
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
    return premultiplied(output)

"""Animated masks shared by Motion Designer preview and export."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QTransform

from .keyframes import evaluate_property
from .mask_tracking import MotionTrackingCache, evaluate_tracking_cache
from .schema import MotionLayer, MotionMaskRef
from .source_frame import transparent_image
from .vector_shapes import VectorPath
from .vector_tessellation import painter_path_from_vector


TRACKING_METADATA_KEY = "tracking_cache"


def mask_value(mask: MotionMaskRef, key: str, time_ms: float, default: Any) -> Any:
    prop = mask.params.get(key)
    return evaluate_property(prop, time_ms) if prop is not None else default


def _mask_path(mask: MotionMaskRef, width: int, height: int, time_ms: float) -> QPainterPath:
    x = float(mask_value(mask, "x", time_ms, 0.0))
    y = float(mask_value(mask, "y", time_ms, 0.0))
    mask_width = float(mask_value(mask, "width", time_ms, width))
    mask_height = float(mask_value(mask, "height", time_ms, height))
    radius = float(mask_value(mask, "radius", time_ms, 0.0))
    path = QPainterPath()
    if mask.kind == "path":
        path_data = mask_value(mask, "path", time_ms, {})
        if isinstance(path_data, Mapping):
            path = painter_path_from_vector(VectorPath.from_dict(path_data))
        if x or y:
            path = QTransform.fromTranslate(x, y).map(path)
    else:
        rect = QRectF(x, y, mask_width, mask_height)
        if mask.kind == "ellipse":
            path.addEllipse(rect)
        else:
            path.addRoundedRect(rect, radius, radius)

    cache = MotionTrackingCache.from_dict(mask.metadata.get(TRACKING_METADATA_KEY))
    tracked = evaluate_tracking_cache(cache, time_ms)
    if cache.enabled and cache.samples:
        transform = QTransform()
        transform.translate(tracked.translate[0], tracked.translate[1])
        if cache.mode == "planar":
            transform.translate(cache.origin[0], cache.origin[1])
            transform.rotate(tracked.rotation)
            transform.scale(tracked.scale[0], tracked.scale[1])
            transform.translate(-cache.origin[0], -cache.origin[1])
        path = transform.map(path)
    return path


def _rgba_array(image: QImage):
    import numpy as np

    straight = image.convertToFormat(QImage.Format_RGBA8888)
    array = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(
        straight.height(), straight.bytesPerLine()
    )
    return array[:, : straight.width() * 4].reshape(straight.height(), straight.width(), 4).copy()


def _image_from_alpha(alpha) -> QImage:
    import numpy as np

    clipped = np.ascontiguousarray(np.clip(alpha, 0, 255).astype(np.uint8))
    rgba = np.full((*clipped.shape, 4), 255, dtype=np.uint8)
    rgba[..., 3] = clipped
    height, width = clipped.shape
    return QImage(
        rgba.data, width, height, rgba.strides[0], QImage.Format_RGBA8888
    ).copy().convertToFormat(QImage.Format_RGBA8888_Premultiplied)


def render_mask_alpha(mask: MotionMaskRef, width: int, height: int, time_ms: float) -> Any:
    import cv2
    import numpy as np

    surface = transparent_image(width, height)
    opacity = max(0.0, min(1.0, float(mask_value(mask, "opacity", time_ms, 1.0))))
    painter = QPainter(surface)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 255, 255, int(round(opacity * 255.0))))
    painter.drawPath(_mask_path(mask, width, height, time_ms))
    painter.end()
    alpha = _rgba_array(surface)[..., 3]

    expansion = float(mask_value(mask, "expansion", time_ms, 0.0))
    if abs(expansion) >= 0.5:
        radius = max(1, int(round(abs(expansion))))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
        alpha = cv2.dilate(alpha, kernel) if expansion > 0.0 else cv2.erode(alpha, kernel)
    feather = max(0.0, float(mask_value(mask, "feather", time_ms, 0.0)))
    if feather > 0.01:
        alpha = cv2.GaussianBlur(alpha, (0, 0), sigmaX=feather, sigmaY=feather)
    if mask.inverted:
        alpha = 255 - alpha
    return np.asarray(alpha, dtype=np.uint8)


def apply_masks(image: QImage, layer: MotionLayer, time_ms: float) -> QImage:
    if not layer.masks:
        return image
    import numpy as np

    width, height = image.width(), image.height()
    combined = None
    for mask in layer.masks:
        alpha = render_mask_alpha(mask, width, height, time_ms).astype(np.float32) / 255.0
        mode = str(mask.mode or "add").lower()
        if combined is None:
            combined = 1.0 - alpha if mode in {"subtract", "exclude", "garbage", "holdout"} else alpha
        elif mode in {"subtract", "garbage", "holdout"}:
            combined *= 1.0 - alpha
        elif mode in {"exclude", "xor"}:
            combined = np.abs(combined - alpha)
        elif mode in {"intersect", "alpha"}:
            combined = np.minimum(combined, alpha)
        else:
            combined = np.maximum(combined, alpha)

    output = image.copy()
    painter = QPainter(output)
    painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    painter.drawImage(0, 0, _image_from_alpha(combined * 255.0))
    painter.end()
    return output

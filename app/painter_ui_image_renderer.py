"""Image fitting and 9-slice rendering for Painter UI objects."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QTransform


_IMAGE_MODES = {"fit", "fill", "stretch", "crop", "tile"}
_IMAGE_CACHE: dict[str, tuple[int, int, QImage]] = {}
_IMAGE_CACHE_LIMIT = 32


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _ui_color(value: object, fallback: str = "#FFFFFFFF") -> QColor:
    """Parse the Painter contract's CSS-style ``#RRGGBBAA`` colors."""
    text = str(value or "").strip()
    if text.startswith("#") and len(text) == 9:
        try:
            return QColor(
                int(text[1:3], 16),
                int(text[3:5], 16),
                int(text[5:7], 16),
                int(text[7:9], 16),
            )
        except ValueError:
            pass
    color = QColor(text)
    return color if color.isValid() else _ui_color(fallback, "#FFFFFFFF")


def normalize_ui_image_content(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = dict(value or {})
    mode = str(source.get("image_fit") or "fit").strip().casefold()
    source["image_fit"] = mode if mode in _IMAGE_MODES else "fit"
    source["source_path"] = str(
        source.get("source_path") or source.get("path") or ""
    )
    source["tile_scale"] = max(
        0.05,
        min(16.0, _number(source.get("tile_scale"), 1.0)),
    )
    source["image_rotation"] = _number(
        source.get("image_rotation", source.get("rotation")),
        0.0,
    )
    transform = source.get("figma_image_transform")
    normalized_transform: list[list[float]] = []
    if (
        isinstance(transform, (list, tuple))
        and len(transform) == 2
        and all(
            isinstance(axis, (list, tuple)) and len(axis) >= 3
            for axis in transform
        )
    ):
        candidate = [
            [_number(transform[row][column], math.nan) for column in range(3)]
            for row in range(2)
        ]
        if all(math.isfinite(value) for axis in candidate for value in axis):
            normalized_transform = candidate
    source["figma_image_transform"] = normalized_transform
    source["focal_x"] = max(
        0.0,
        min(1.0, _number(source.get("focal_x"), 0.5)),
    )
    source["focal_y"] = max(
        0.0,
        min(1.0, _number(source.get("focal_y"), 0.5)),
    )
    source["original_width"] = max(
        0,
        int(_number(source.get("original_width"), 0)),
    )
    source["original_height"] = max(
        0,
        int(_number(source.get("original_height"), 0)),
    )
    margins = source.get("nine_slice")
    margins = margins if isinstance(margins, Mapping) else {}
    source["nine_slice_enabled"] = bool(
        source.get("nine_slice_enabled", False)
    )
    source["nine_slice"] = {
        edge: max(0.0, _number(margins.get(edge), 0.0))
        for edge in ("left", "top", "right", "bottom")
    }
    crop = source.get("image_crop") or source.get("crop")
    crop = crop if isinstance(crop, Mapping) else {}
    crop_units = str(
        crop.get("Units", crop.get("units", "normalized"))
    ).strip().casefold()
    if crop_units in {"normalized", "normalised", "relative", "uv"}:
        crop_units = "normalized"
    elif crop_units in {"pixel", "pixels", "px"}:
        crop_units = "pixels"
    else:
        crop_units = "normalized"
    source["image_crop"] = {
        "enabled": bool(crop.get("Enabled", crop.get("enabled", False))),
        "units": crop_units,
        "x": _number(crop.get("X", crop.get("x", 0.0)), 0.0),
        "y": _number(crop.get("Y", crop.get("y", 0.0)), 0.0),
        "width": _number(crop.get("Width", crop.get("width", 1.0)), 1.0),
        "height": _number(
            crop.get("Height", crop.get("height", 1.0)),
            1.0,
        ),
    }
    source["image_opacity"] = max(
        0.0,
        min(1.0, _number(source.get("image_opacity"), 1.0)),
    )
    source["image_tint"] = str(
        source.get("image_tint") or "#FFFFFFFF"
    )
    corner_radii = source.get("image_corner_radii")
    corner_radii = (
        corner_radii if isinstance(corner_radii, Mapping) else {}
    )
    source["image_corner_radii"] = {
        key: max(0.0, _number(corner_radii.get(key), 0.0))
        for key in (
            "top_left",
            "top_right",
            "bottom_right",
            "bottom_left",
        )
    }
    return source


def _figma_affine_image_transform(
    value: object,
    target: QRectF,
    source_width: float,
    source_height: float,
) -> QTransform | None:
    """Map source pixels into a Figma image-fill target.

    The REST ``imageTransform`` is expressed in normalized object space and
    maps target positions to normalized source-image positions.  QPainter
    needs the inverse mapping (source pixels to target coordinates).
    """

    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or not all(
            isinstance(axis, (list, tuple)) and len(axis) >= 3
            for axis in value
        )
        or source_width <= 0.0
        or source_height <= 0.0
        or target.width() <= 0.0
        or target.height() <= 0.0
    ):
        return None
    a, c, offset_x = (_number(item, math.nan) for item in value[0][:3])
    b, d, offset_y = (_number(item, math.nan) for item in value[1][:3])
    if not all(
        math.isfinite(item)
        for item in (a, b, c, d, offset_x, offset_y)
    ):
        return None
    determinant = a * d - b * c
    if abs(determinant) <= 1.0e-9:
        return None
    inverse_a = d / determinant
    inverse_b = -b / determinant
    inverse_c = -c / determinant
    inverse_d = a / determinant
    inverse_x = (c * offset_y - d * offset_x) / determinant
    inverse_y = (b * offset_x - a * offset_y) / determinant
    return QTransform(
        target.width() * inverse_a / source_width,
        target.height() * inverse_b / source_width,
        target.width() * inverse_c / source_height,
        target.height() * inverse_d / source_height,
        target.left() + target.width() * inverse_x,
        target.top() + target.height() * inverse_y,
    )


def _rotated_image_and_size(
    image: QImage,
    logical_width: float,
    logical_height: float,
    rotation: float,
) -> tuple[QImage, float, float]:
    normalized = math.fmod(float(rotation), 360.0)
    if abs(normalized) <= 0.0001:
        return image, logical_width, logical_height
    transform = QTransform()
    transform.rotate(normalized)
    rotated = image.transformed(
        transform,
        Qt.TransformationMode.SmoothTransformation,
    )
    radians = math.radians(normalized)
    cosine = abs(math.cos(radians))
    sine = abs(math.sin(radians))
    return (
        rotated,
        logical_width * cosine + logical_height * sine,
        logical_width * sine + logical_height * cosine,
    )


def _bounded_pair(
    first: float,
    second: float,
    available: float,
) -> tuple[float, float]:
    first = max(0.0, float(first))
    second = max(0.0, float(second))
    total = first + second
    if total <= max(0.0, available) or total <= 0.0:
        return first, second
    scale = max(0.0, available) / total
    return first * scale, second * scale


def _image_corner_path(
    rect: QRectF,
    radii: Mapping[str, Any] | None,
) -> QPainterPath:
    source = radii if isinstance(radii, Mapping) else {}
    maximum = max(0.0, min(rect.width(), rect.height()) * 0.5)
    top_left, top_right, bottom_right, bottom_left = (
        min(maximum, max(0.0, _number(source.get(key), 0.0)))
        for key in (
            "top_left",
            "top_right",
            "bottom_right",
            "bottom_left",
        )
    )
    path = QPainterPath()
    path.moveTo(rect.left() + top_left, rect.top())
    path.lineTo(rect.right() - top_right, rect.top())
    path.quadTo(
        rect.topRight(),
        QPointF(rect.right(), rect.top() + top_right),
    )
    path.lineTo(rect.right(), rect.bottom() - bottom_right)
    path.quadTo(
        rect.bottomRight(),
        QPointF(rect.right() - bottom_right, rect.bottom()),
    )
    path.lineTo(rect.left() + bottom_left, rect.bottom())
    path.quadTo(
        rect.bottomLeft(),
        QPointF(rect.left(), rect.bottom() - bottom_left),
    )
    path.lineTo(rect.left(), rect.top() + top_left)
    path.quadTo(
        rect.topLeft(),
        QPointF(rect.left() + top_left, rect.top()),
    )
    path.closeSubpath()
    return path


def image_draw_plan(
    source_size: QSizeF,
    target: QRectF,
    content: Mapping[str, Any] | None,
) -> list[tuple[QRectF, QRectF]]:
    settings = normalize_ui_image_content(content)
    source_width = max(0.0, float(source_size.width()))
    source_height = max(0.0, float(source_size.height()))
    if (
        source_width <= 0.0
        or source_height <= 0.0
        or target.width() <= 0.0
        or target.height() <= 0.0
    ):
        return []

    source_rect = QRectF(0.0, 0.0, source_width, source_height)
    crop = settings["image_crop"]
    if crop["enabled"]:
        if crop["units"] == "normalized":
            crop_rect = QRectF(
                crop["x"] * source_width,
                crop["y"] * source_height,
                crop["width"] * source_width,
                crop["height"] * source_height,
            )
        else:
            crop_rect = QRectF(
                crop["x"],
                crop["y"],
                crop["width"],
                crop["height"],
            )
        crop_rect = crop_rect.normalized().intersected(source_rect)
        if crop_rect.width() > 0.0 and crop_rect.height() > 0.0:
            source_rect = crop_rect
    source_width = source_rect.width()
    source_height = source_rect.height()
    source_origin_x = source_rect.left()
    source_origin_y = source_rect.top()
    if settings["nine_slice_enabled"]:
        margins = settings["nine_slice"]
        margin_left, margin_right = _bounded_pair(
            margins["left"],
            margins["right"],
            source_width,
        )
        margin_top, margin_bottom = _bounded_pair(
            margins["top"],
            margins["bottom"],
            source_height,
        )
        target_left, target_right = _bounded_pair(
            margin_left,
            margin_right,
            target.width(),
        )
        target_top, target_bottom = _bounded_pair(
            margin_top,
            margin_bottom,
            target.height(),
        )
        source_x = (
            source_origin_x,
            source_origin_x + margin_left,
            source_rect.right() - margin_right,
            source_rect.right(),
        )
        source_y = (
            source_origin_y,
            source_origin_y + margin_top,
            source_rect.bottom() - margin_bottom,
            source_rect.bottom(),
        )
        target_x = (
            target.left(),
            target.left() + target_left,
            target.right() - target_right,
            target.right(),
        )
        target_y = (
            target.top(),
            target.top() + target_top,
            target.bottom() - target_bottom,
            target.bottom(),
        )
        plan: list[tuple[QRectF, QRectF]] = []
        for y_index in range(3):
            for x_index in range(3):
                destination = QRectF(
                    target_x[x_index],
                    target_y[y_index],
                    target_x[x_index + 1] - target_x[x_index],
                    target_y[y_index + 1] - target_y[y_index],
                )
                source = QRectF(
                    source_x[x_index],
                    source_y[y_index],
                    source_x[x_index + 1] - source_x[x_index],
                    source_y[y_index + 1] - source_y[y_index],
                )
                if destination.width() > 0.0 and destination.height() > 0.0:
                    if source.width() > 0.0 and source.height() > 0.0:
                        plan.append((destination, source))
        return plan

    mode = settings["image_fit"]
    if mode in {"stretch", "crop"}:
        return [(QRectF(target), source_rect)]
    if mode == "tile":
        tile_width = source_width * float(settings["tile_scale"])
        tile_height = source_height * float(settings["tile_scale"])
        columns = min(256, max(1, math.ceil(target.width() / tile_width)))
        rows = min(256, max(1, math.ceil(target.height() / tile_height)))
        plan = []
        for row in range(rows):
            for column in range(columns):
                x = target.left() + column * tile_width
                y = target.top() + row * tile_height
                width = min(tile_width, target.right() - x)
                height = min(tile_height, target.bottom() - y)
                if width <= 0.0 or height <= 0.0:
                    continue
                plan.append(
                    (
                        QRectF(x, y, width, height),
                        QRectF(
                            source_origin_x,
                            source_origin_y,
                            source_width * width / tile_width,
                            source_height * height / tile_height,
                        ),
                    )
                )
        return plan

    source_aspect = source_width / source_height
    target_aspect = target.width() / target.height()
    if mode == "fill":
        if source_aspect > target_aspect:
            crop_width = source_height * target_aspect
            source = QRectF(
                source_origin_x
                + (source_width - crop_width) * settings["focal_x"],
                source_origin_y,
                crop_width,
                source_height,
            )
        else:
            crop_height = source_width / target_aspect
            source = QRectF(
                source_origin_x,
                source_origin_y
                + (source_height - crop_height) * settings["focal_y"],
                source_width,
                crop_height,
            )
        return [(QRectF(target), source)]

    if source_aspect > target_aspect:
        width = target.width()
        height = width / source_aspect
    else:
        height = target.height()
        width = height * source_aspect
    destination = QRectF(
        target.center().x() - width * 0.5,
        target.center().y() - height * 0.5,
        width,
        height,
    )
    return [(destination, source_rect)]


def load_ui_image(content: Mapping[str, Any] | None) -> QImage:
    settings = normalize_ui_image_content(content)
    path_text = settings["source_path"]
    if not path_text:
        return QImage()
    path = Path(path_text).expanduser()
    try:
        stat = path.stat()
    except OSError:
        return QImage()
    key = str(path.resolve())
    cached = _IMAGE_CACHE.get(key)
    stamp = int(stat.st_mtime_ns)
    size = int(stat.st_size)
    if cached is not None and cached[0] == stamp and cached[1] == size:
        return QImage(cached[2])
    image = QImage(key)
    if image.isNull():
        return image
    _IMAGE_CACHE[key] = (stamp, size, QImage(image))
    while len(_IMAGE_CACHE) > _IMAGE_CACHE_LIMIT:
        _IMAGE_CACHE.pop(next(iter(_IMAGE_CACHE)))
    return image


def draw_ui_image(
    painter: QPainter,
    target: QRectF,
    content: Mapping[str, Any] | None,
) -> bool:
    image = load_ui_image(content)
    if image.isNull():
        return False
    settings = normalize_ui_image_content(content)
    logical_width = float(settings["original_width"])
    logical_height = float(settings["original_height"])
    if logical_width <= 0.0 or logical_height <= 0.0:
        logical_width = float(image.width())
        logical_height = float(image.height())
    tint = _ui_color(settings["image_tint"])
    draw_image = image
    if (tint.red(), tint.green(), tint.blue()) != (255, 255, 255):
        draw_image = image.convertToFormat(
            QImage.Format.Format_ARGB32_Premultiplied
        )
        tint_painter = QPainter(draw_image)
        tint_painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Multiply
        )
        tint_painter.fillRect(
            draw_image.rect(),
            QColor(tint.red(), tint.green(), tint.blue(), 255),
        )
        tint_painter.end()
    figma_transform = settings["figma_image_transform"]
    if not figma_transform:
        draw_image, logical_width, logical_height = _rotated_image_and_size(
            draw_image,
            logical_width,
            logical_height,
            float(settings["image_rotation"]),
        )
    plan = (
        []
        if figma_transform
        else image_draw_plan(
            QSizeF(logical_width, logical_height),
            target,
            settings,
        )
    )
    if not figma_transform and not plan:
        return False
    painter.save()
    painter.setOpacity(
        painter.opacity()
        * float(settings["image_opacity"])
        * float(tint.alphaF())
    )
    painter.setClipRect(
        target,
        Qt.ClipOperation.IntersectClip,
    )
    corner_radii = settings["image_corner_radii"]
    if any(float(value) > 0.0001 for value in corner_radii.values()):
        corner_rect = (
            plan[0][0]
            if (
                not figma_transform
                and settings["image_fit"] == "fit"
                and len(plan) == 1
            )
            else target
        )
        painter.setClipPath(
            _image_corner_path(corner_rect, corner_radii),
            Qt.ClipOperation.IntersectClip,
        )
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    if figma_transform:
        transform = _figma_affine_image_transform(
            figma_transform,
            target,
            float(draw_image.width()),
            float(draw_image.height()),
        )
        if transform is None:
            painter.restore()
            return False
        # Preserve the caller's document/view transform while replacing the
        # image-local mapping. QTransform composes left-to-right in Qt's
        # row-vector convention, hence image_to_document * document_to_view.
        painter.setWorldTransform(
            transform * painter.worldTransform(),
            False,
        )
        painter.drawImage(QPointF(0.0, 0.0), draw_image)
        painter.restore()
        return True
    source_scale_x = float(draw_image.width()) / logical_width
    source_scale_y = float(draw_image.height()) / logical_height
    for destination, source in plan:
        painter.drawImage(
            destination,
            draw_image,
            QRectF(
                source.left() * source_scale_x,
                source.top() * source_scale_y,
                source.width() * source_scale_x,
                source.height() * source_scale_y,
            ),
        )
    painter.restore()
    return True


__all__ = [
    "draw_ui_image",
    "image_draw_plan",
    "load_ui_image",
    "normalize_ui_image_content",
]

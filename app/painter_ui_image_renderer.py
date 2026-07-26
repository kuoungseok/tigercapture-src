"""Image fitting and 9-slice rendering for Painter UI objects."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import QRectF, QSizeF, Qt
from PySide6.QtGui import QImage, QPainter


_IMAGE_MODES = {"fit", "fill", "stretch", "tile"}
_IMAGE_CACHE: dict[str, tuple[int, int, QImage]] = {}
_IMAGE_CACHE_LIMIT = 32


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


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
    margins = source.get("nine_slice")
    margins = margins if isinstance(margins, Mapping) else {}
    source["nine_slice_enabled"] = bool(
        source.get("nine_slice_enabled", False)
    )
    source["nine_slice"] = {
        edge: max(0.0, _number(margins.get(edge), 0.0))
        for edge in ("left", "top", "right", "bottom")
    }
    return source


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
    if settings["nine_slice_enabled"]:
        margins = settings["nine_slice"]
        source_left, source_right = _bounded_pair(
            margins["left"],
            margins["right"],
            source_width,
        )
        source_top, source_bottom = _bounded_pair(
            margins["top"],
            margins["bottom"],
            source_height,
        )
        target_left, target_right = _bounded_pair(
            source_left,
            source_right,
            target.width(),
        )
        target_top, target_bottom = _bounded_pair(
            source_top,
            source_bottom,
            target.height(),
        )
        source_x = (
            0.0,
            source_left,
            source_width - source_right,
            source_width,
        )
        source_y = (
            0.0,
            source_top,
            source_height - source_bottom,
            source_height,
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
    if mode == "stretch":
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
                            0.0,
                            0.0,
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
                (source_width - crop_width) * 0.5,
                0.0,
                crop_width,
                source_height,
            )
        else:
            crop_height = source_width / target_aspect
            source = QRectF(
                0.0,
                (source_height - crop_height) * 0.5,
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
    plan = image_draw_plan(QSizeF(image.size()), target, content)
    if not plan:
        return False
    painter.save()
    painter.setClipRect(target)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for destination, source in plan:
        painter.drawImage(destination, image, source)
    painter.restore()
    return True


__all__ = [
    "draw_ui_image",
    "image_draw_plan",
    "load_ui_image",
    "normalize_ui_image_content",
]

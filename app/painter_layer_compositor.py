"""Provider-neutral raster composition rules for Painter layer trees."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath

from app.painter_dimensions import positive_integer


BLEND_MODES = (
    "normal",
    "darken",
    "multiply",
    "color_burn",
    "lighten",
    "screen",
    "color_dodge",
    "overlay",
    "soft_light",
    "hard_light",
    "difference",
    "exclusion",
)


def _composition_mode(name: str) -> QPainter.CompositionMode:
    return {
        "darken": QPainter.CompositionMode.CompositionMode_Darken,
        "multiply": QPainter.CompositionMode.CompositionMode_Multiply,
        "color_burn": QPainter.CompositionMode.CompositionMode_ColorBurn,
        "lighten": QPainter.CompositionMode.CompositionMode_Lighten,
        "screen": QPainter.CompositionMode.CompositionMode_Screen,
        "color_dodge": QPainter.CompositionMode.CompositionMode_ColorDodge,
        "overlay": QPainter.CompositionMode.CompositionMode_Overlay,
        "soft_light": QPainter.CompositionMode.CompositionMode_SoftLight,
        "hard_light": QPainter.CompositionMode.CompositionMode_HardLight,
        "difference": QPainter.CompositionMode.CompositionMode_Difference,
        "exclusion": QPainter.CompositionMode.CompositionMode_Exclusion,
    }.get(str(name or "normal"), QPainter.CompositionMode.CompositionMode_SourceOver)


def _transparent(width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    return image


def _raster_layer_mask(
    layer: object,
    layer_masks: Mapping[str, QImage],
    width: int,
    height: int,
) -> QImage | None:
    if not bool(getattr(layer, "mask_enabled", False)):
        return None
    candidate = layer_masks.get(str(getattr(layer, "layer_id", "") or ""))
    if not isinstance(candidate, QImage) or candidate.isNull():
        return None
    from app.painter_layer_masks import normalized_alpha8

    return normalized_alpha8(candidate, width, height)


def _apply_layer_mask(
    image: QImage,
    layer: object,
    layer_masks: Mapping[str, QImage],
) -> QImage:
    raster_mask = _raster_layer_mask(layer, layer_masks, image.width(), image.height())
    if raster_mask is not None:
        from app.painter_layer_masks import apply_alpha8_mask

        return apply_alpha8_mask(image, raster_mask)
    mask = list(getattr(layer, "mask", []) or [])
    if not bool(getattr(layer, "mask_enabled", False)) or len(mask) < 3:
        return image
    mask_image = _transparent(image.width(), image.height())
    path = QPainterPath(QPointF(float(mask[0][0]) * image.width(), float(mask[0][1]) * image.height()))
    for x, y in mask[1:]:
        path.lineTo(float(x) * image.width(), float(y) * image.height())
    path.closeSubpath()
    painter = QPainter(mask_image)
    try:
        painter.fillPath(path, QColor("white"))
    finally:
        painter.end()
    out = image.copy()
    painter = QPainter(out)
    try:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, mask_image)
    finally:
        painter.end()
    return out


def _layer_mask_alpha(
    layer: object,
    layer_masks: Mapping[str, QImage],
    width: int,
    height: int,
) -> QImage | None:
    raster_mask = _raster_layer_mask(layer, layer_masks, width, height)
    if raster_mask is not None:
        return raster_mask
    mask = list(getattr(layer, "mask", []) or [])
    if not bool(getattr(layer, "mask_enabled", False)) or len(mask) < 3:
        return None
    image = _transparent(width, height)
    path = QPainterPath(QPointF(float(mask[0][0]) * width, float(mask[0][1]) * height))
    for x, y in mask[1:]:
        path.lineTo(float(x) * width, float(y) * height)
    path.closeSubpath()
    painter = QPainter(image)
    painter.fillPath(path, QColor("white"))
    painter.end()
    return image


def _clip_to_base(image: QImage, base_alpha: QImage | None) -> QImage:
    if base_alpha is None or base_alpha.isNull():
        return _transparent(image.width(), image.height())
    out = image.copy()
    painter = QPainter(out)
    try:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, base_alpha)
    finally:
        painter.end()
    return out


def composite_layer_images(
    layers: Sequence[object],
    layer_images: Mapping[str, QImage],
    width: int,
    height: int,
    *,
    layer_masks: Mapping[str, QImage] | None = None,
) -> QImage:
    """Composite ordered layer images with groups, clipping, masks and blends."""
    width = positive_integer(width, field="compositor width")
    height = positive_integer(height, field="compositor height")
    rows = list(layers or [])
    raster_masks = dict(layer_masks or {})
    by_id = {str(getattr(row, "layer_id", "")): row for row in rows}
    children: dict[str, list[object]] = {"": []}
    for row in rows:
        layer_id = str(getattr(row, "layer_id", ""))
        parent_id = str(getattr(row, "parent_id", "") or "")
        if parent_id == layer_id or parent_id not in by_id:
            parent_id = ""
        children.setdefault(parent_id, []).append(row)

    visiting: set[str] = set()

    def render_siblings(parent_id: str) -> QImage:
        output = _transparent(width, height)
        base_alpha: QImage | None = None
        for layer in children.get(parent_id, []):
            if not bool(getattr(layer, "visible", True)):
                continue
            layer_id = str(getattr(layer, "layer_id", ""))
            if layer_id in visiting:
                continue
            node_type = str(getattr(layer, "node_type", "paint") or "paint")
            if node_type == "adjustment":
                if not bool(getattr(layer, "adjustment_enabled", True)):
                    continue
                from app.painter_adjustments import apply_adjustment_qimage

                mask = _layer_mask_alpha(layer, raster_masks, width, height)
                if bool(getattr(layer, "clipping", False)) and base_alpha is not None:
                    mask = base_alpha.copy() if mask is None else _clip_to_base(mask, base_alpha)
                output = apply_adjustment_qimage(
                    output,
                    str(getattr(layer, "adjustment_type", "") or ""),
                    dict(getattr(layer, "adjustment_settings", {}) or {}),
                    mask=mask,
                    opacity=max(0.0, min(1.0, float(getattr(layer, "opacity", 100)) / 100.0)),
                )
                continue
            if node_type == "group":
                visiting.add(layer_id)
                source = render_siblings(layer_id)
                visiting.discard(layer_id)
            else:
                candidate = layer_images.get(layer_id)
                source = (
                    candidate.copy()
                    if isinstance(candidate, QImage) and not candidate.isNull()
                    else _transparent(width, height)
                )
            source = _apply_layer_mask(source, layer, raster_masks)
            if bool(getattr(layer, "clipping", False)):
                source = _clip_to_base(source, base_alpha)
            else:
                base_alpha = source.copy()
            painter = QPainter(output)
            painter.setOpacity(
                max(0.0, min(1.0, float(getattr(layer, "opacity", 100)) / 100.0))
            )
            painter.setCompositionMode(
                _composition_mode(str(getattr(layer, "blend_mode", "normal")))
            )
            painter.drawImage(0, 0, source)
            painter.end()
        return output

    return render_siblings("")


__all__ = ["BLEND_MODES", "composite_layer_images"]

"""Read-only Painter preview projection for the generated TigerStudio UMG tree.

The simulator deliberately consumes the Tiger UMG document produced by
``painter_ui_umg_adapter`` instead of reinterpreting Painter features.  This
keeps the local preview aligned with the widgets and properties currently used
by ``TigerStudioUMGGeneration.cpp``.  It is a compatibility proxy, not proof of
Unreal rendering parity; the real Unreal generation/capture path remains the
authority for delivery claims.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import create_ui_document, normalize_ui_document
from app.painter_ui_umg_adapter import (
    TIGER_UMG_SCHEMA_VERSION,
    painter_ui_to_umg_document,
    preflight_painter_umg,
)
from app.unreal_umg_material import (
    umg_material_preview_style,
    validate_umg_material_record,
)


PAINTER_UMG_SIMULATOR_SCHEMA = "tigerstudio.painter.ui.umg_simulator.v3"

_DISPOSITIONS = ("Native", "Material", "Baked", "Blocked")
_COMMON_CONSUMED_PROPERTIES = (
    "Id",
    "ParentId",
    "Kind",
    "Disposition",
    "Scale",
    "RotationDegrees",
    "Opacity",
)

_V4_LAYOUT_CONSUMED_PROPERTIES = ("Position", "Size", "Anchor")

_V5_LAYOUT_CONSUMED_PROPERTIES = (
    "CanvasSlot.AnchorMinimum",
    "CanvasSlot.AnchorMaximum",
    "CanvasSlot.Offsets",
    "CanvasSlot.Alignment",
    "RenderTransformPivot",
)

# Matrix layout is (a, b, c, d, tx, ty):
# x' = a*x + c*y + tx, y' = b*x + d*y + ty.
_Matrix = tuple[float, float, float, float, float, float]


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return result if math.isfinite(result) else float(default)


def _vector(
    value: object,
    *,
    default_x: float,
    default_y: float,
) -> tuple[float, float]:
    row = value if isinstance(value, Mapping) else {}
    return (
        _number(row.get("X"), default_x),
        _number(row.get("Y"), default_y),
    )


def _margin(value: object) -> tuple[float, float, float, float]:
    row = value if isinstance(value, Mapping) else {}
    return (
        _number(row.get("Left"), 0.0),
        _number(row.get("Top"), 0.0),
        _number(row.get("Right"), 100.0),
        _number(row.get("Bottom"), 100.0),
    )


def _payload(value: object) -> dict[str, Any]:
    try:
        decoded = json.loads(str(value or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(decoded) if isinstance(decoded, Mapping) else {}


def _compose(left: _Matrix, right: _Matrix) -> _Matrix:
    """Return the affine matrix ``left * right``."""
    la, lb, lc, ld, ltx, lty = left
    ra, rb, rc, rd, rtx, rty = right
    return (
        la * ra + lc * rb,
        lb * ra + ld * rb,
        la * rc + lc * rd,
        lb * rc + ld * rd,
        la * rtx + lc * rty + ltx,
        lb * rtx + ld * rty + lty,
    )


def _translate(x: float, y: float) -> _Matrix:
    return (1.0, 0.0, 0.0, 1.0, float(x), float(y))


def _rotate_scale(degrees: float, scale_x: float, scale_y: float) -> _Matrix:
    radians = math.radians(float(degrees))
    cosine = math.cos(radians)
    sine = math.sin(radians)
    return (
        cosine * scale_x,
        sine * scale_x,
        -sine * scale_y,
        cosine * scale_y,
        0.0,
        0.0,
    )


def _apply(matrix: _Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, tx, ty = matrix
    return (a * x + c * y + tx, b * x + d * y + ty)


def _canvas_slot(
    layer: Mapping[str, Any],
    *,
    schema_version: int,
) -> dict[str, Any]:
    """Return the exact CanvasPanelSlot inputs consumed by the generator."""
    if schema_version >= 5 and isinstance(layer.get("CanvasSlot"), Mapping):
        row = dict(layer.get("CanvasSlot") or {})
        anchor_minimum = _vector(
            row.get("AnchorMinimum"),
            default_x=0.0,
            default_y=0.0,
        )
        anchor_maximum = _vector(
            row.get("AnchorMaximum"),
            default_x=anchor_minimum[0],
            default_y=anchor_minimum[1],
        )
        alignment = _vector(
            row.get("Alignment"),
            default_x=0.5,
            default_y=0.5,
        )
        offsets = _margin(row.get("Offsets"))
    else:
        # v4 leaves UCanvasPanelSlot::Anchors at UE's (0, 0) default and
        # writes Position/Size through SetPosition/SetSize.
        position = _vector(
            layer.get("Position"),
            default_x=0.0,
            default_y=0.0,
        )
        size = _vector(
            layer.get("Size"),
            default_x=100.0,
            default_y=100.0,
        )
        alignment = _vector(
            layer.get("Anchor"),
            default_x=0.5,
            default_y=0.5,
        )
        anchor_minimum = (0.0, 0.0)
        anchor_maximum = (0.0, 0.0)
        offsets = (position[0], position[1], size[0], size[1])
    return {
        "anchor_minimum": anchor_minimum,
        "anchor_maximum": anchor_maximum,
        "offsets": offsets,
        "alignment": alignment,
        "auto_size": False,
    }


def _slot_geometry(
    slot: Mapping[str, Any],
    *,
    parent_width: float,
    parent_height: float,
) -> dict[str, float]:
    minimum_x, minimum_y = slot["anchor_minimum"]
    maximum_x, maximum_y = slot["anchor_maximum"]
    left, top, right, bottom = slot["offsets"]
    alignment_x, alignment_y = slot["alignment"]
    if abs(maximum_x - minimum_x) > 1e-9:
        x = minimum_x * parent_width + left
        width = maximum_x * parent_width - x - right
    else:
        width = right
        x = minimum_x * parent_width + left - width * alignment_x
    if abs(maximum_y - minimum_y) > 1e-9:
        y = minimum_y * parent_height + top
        height = maximum_y * parent_height - y - bottom
    else:
        height = bottom
        y = minimum_y * parent_height + top - height * alignment_y
    return {
        "x": float(x),
        "y": float(y),
        "width": max(0.001, float(width)),
        "height": max(0.001, float(height)),
    }


def _render_transform_pivot(
    layer: Mapping[str, Any],
    *,
    schema_version: int,
) -> tuple[float, float]:
    return _vector(
        (
            layer.get("RenderTransformPivot")
            if schema_version >= 5
            else layer.get("Anchor")
        ),
        default_x=0.5,
        default_y=0.5,
    )


def _widget_transform(
    layer: Mapping[str, Any],
    *,
    geometry: Mapping[str, float],
    render_pivot: tuple[float, float],
) -> _Matrix:
    slot_x = float(geometry["x"])
    slot_y = float(geometry["y"])
    width = float(geometry["width"])
    height = float(geometry["height"])
    anchor_x, anchor_y = render_pivot
    scale_x, scale_y = _vector(
        layer.get("Scale"),
        default_x=1.0,
        default_y=1.0,
    )
    pivot_x = width * anchor_x
    pivot_y = height * anchor_y
    transform = _translate(slot_x, slot_y)
    transform = _compose(transform, _translate(pivot_x, pivot_y))
    transform = _compose(
        transform,
        _rotate_scale(
            _number(layer.get("RotationDegrees"), 0.0),
            scale_x,
            scale_y,
        ),
    )
    return _compose(transform, _translate(-pivot_x, -pivot_y))


def _proxy_geometry(
    transform: _Matrix,
    *,
    width: float,
    height: float,
    anchor_x: float,
    anchor_y: float,
) -> dict[str, Any]:
    a, b, c, d, _tx, _ty = transform
    scale_x = math.hypot(a, b)
    scale_y = math.hypot(c, d)
    orthogonality = (
        0.0
        if scale_x <= 1e-9 or scale_y <= 1e-9
        else (a * c + b * d) / (scale_x * scale_y)
    )
    determinant = a * d - b * c
    exact = abs(orthogonality) <= 1e-6 and determinant >= -1e-9
    if exact:
        proxy_width = max(0.001, abs(width * scale_x))
        proxy_height = max(0.001, abs(height * scale_y))
        pivot_x, pivot_y = _apply(
            transform,
            width * anchor_x,
            height * anchor_y,
        )
        return {
            "x": pivot_x - proxy_width * anchor_x,
            "y": pivot_y - proxy_height * anchor_y,
            "width": proxy_width,
            "height": proxy_height,
            "rotation": math.degrees(math.atan2(b, a)),
            "accuracy": "exact_affine",
        }
    corners = (
        _apply(transform, 0.0, 0.0),
        _apply(transform, width, 0.0),
        _apply(transform, width, height),
        _apply(transform, 0.0, height),
    )
    left = min(point[0] for point in corners)
    top = min(point[1] for point in corners)
    right = max(point[0] for point in corners)
    bottom = max(point[1] for point in corners)
    return {
        "x": left,
        "y": top,
        "width": max(0.001, right - left),
        "height": max(0.001, bottom - top),
        "rotation": 0.0,
        "accuracy": "axis_aligned_bounds",
    }


def _widget_class(kind: str) -> str:
    if kind == "Group":
        return "UCanvasPanel"
    if kind == "Text":
        return "UTextBlock"
    if kind == "Button":
        return "UTigerStudioButton"
    return "UImage"


def _consumed_properties(kind: str, *, schema_version: int) -> list[str]:
    result = list(_COMMON_CONSUMED_PROPERTIES)
    if schema_version >= 5:
        result.extend(_V5_LAYOUT_CONSUMED_PROPERTIES)
    else:
        result.extend(_V4_LAYOUT_CONSUMED_PROPERTIES)
    if kind == "Group":
        result.append("PayloadJson.clip_content")
    elif kind == "Text":
        result.extend(
            (
                "Name",
                "PayloadJson.text",
                "PayloadJson.fill",
                "PayloadJson.font_size",
            )
        )
    elif kind == "Button":
        result.extend(("Name", "AssetId", "PayloadJson.text"))
    else:
        result.extend(("AssetId", "PayloadJson.fill"))
    return result


def _image_fill_consumed_properties() -> list[str]:
    """Return the provider-neutral ImageFill fields used by the widget path."""
    return [
        "AssetId",
        "ImageFill.AssetId",
        "ImageFill.Mode",
        "ImageFill.FocalPoint",
        "ImageFill.TileScale",
        "ImageFill.SourceSize",
        "ImageFill.Crop",
        "ImageFill.NineSlice",
        "ImageFill.CornerRadii",
        "ImageFill.Opacity",
        "ImageFill.Tint",
        "ImageFill.Adjustments",
    ]


def _material_consumed_properties(
    material: Mapping[str, Any] | None,
) -> list[str]:
    """Describe the provider-neutral fields consumed by the UI material."""
    source = material if isinstance(material, Mapping) else {}
    common = [
        "Material.Schema",
        "Material.Generator",
        "Material.Kind",
        "Material.CoordinateSpace",
    ]
    if str(source.get("Kind") or "") == "RoundedCard":
        return [
            *common,
            "Material.Size",
            "Material.FillKind",
            "Material.FillColor",
            "Material.Start",
            "Material.End",
            "Material.Width",
            "Material.Stops",
            "Material.Opacity",
            "Material.CornerRadii",
            "Material.CornerSmoothing",
            "Material.Stroke",
            "Material.DropShadow",
            "Material.InnerShadow",
            "Material.VisualPadding",
        ]
    return [
        *common,
        "Material.Start",
        "Material.End",
        "Material.Stops",
    ]


def _is_rounded_card_material(value: object) -> bool:
    source = value if isinstance(value, Mapping) else {}
    return (
        str(source.get("Schema") or "") == "tigerstudio.umg.ui_material.v2"
        and str(source.get("Kind") or "") == "RoundedCard"
    )


def _rounded_card_host_consumed_properties(*, schema_version: int) -> list[str]:
    result = list(_COMMON_CONSUMED_PROPERTIES)
    result.extend(
        _V5_LAYOUT_CONSUMED_PROPERTIES
        if schema_version >= 5
        else _V4_LAYOUT_CONSUMED_PROPERTIES
    )
    return result


def _resource_map(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("Id") or ""): copy.deepcopy(dict(row))
        for row in document.get("Resources", [])
        if isinstance(row, Mapping) and str(row.get("Id") or "")
    }


def _mapping_value(value: object, *keys: str) -> object:
    source = value if isinstance(value, Mapping) else {}
    for key in keys:
        if key in source:
            return source[key]
    return None


def _normalize_image_fit(value: object) -> tuple[str, str]:
    requested = str(value or "stretch").strip().casefold()
    aliases = {
        "fit": "fit",
        "contain": "fit",
        "scale_down": "fit",
        "fill": "fill",
        "cover": "fill",
        "crop": "crop",
        "stretch": "stretch",
        "scale_to_fill": "stretch",
        "tile": "tile",
        "repeat": "tile",
    }
    normalized = aliases.get(requested)
    return (
        normalized if normalized is not None else "fit",
        "" if normalized is not None else requested,
    )


def _image_fill_binding(
    layer: Mapping[str, Any],
    payload: Mapping[str, Any],
    resources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve the texture/fitting record consumed by the preview surface."""
    source_params = payload.get("source_params")
    source_params = source_params if isinstance(source_params, Mapping) else {}
    direct_payload = (
        payload
        if any(
            key in payload
            for key in ("source_path", "SourcePath", "path", "Path")
        )
        else None
    )
    direct_source_params = (
        source_params
        if any(
            key in source_params
            for key in ("source_path", "SourcePath", "path", "Path")
        )
        else None
    )
    candidates = [
        layer.get("ImageFill"),
        layer.get("image_fill"),
        payload.get("image_fill"),
        payload.get("ImageFill"),
        source_params.get("image_fill"),
        source_params.get("ImageFill"),
        direct_payload,
        direct_source_params,
    ]
    fills = source_params.get("fills")
    if isinstance(fills, list):
        candidates.extend(
            row
            for row in fills
            if isinstance(row, Mapping)
            and bool(row.get("visible", row.get("Visible", True)))
            and str(row.get("type", row.get("Type", ""))).casefold()
            == "image"
        )
    candidate = next(
        (
            dict(row)
            for row in candidates
            if isinstance(row, Mapping) and bool(row)
        ),
        {},
    )
    layer_resource_id = str(layer.get("AssetId") or "")
    resource_id = str(
        _mapping_value(
            candidate,
            "ResourceId",
            "resource_id",
            "AssetId",
            "asset_id",
        )
        or layer_resource_id
        or ""
    )
    resource = resources.get(resource_id)
    source_path = str(
        _mapping_value(
            candidate,
            "SourcePath",
            "source_path",
            "path",
            "Path",
        )
        or (resource or {}).get("SourcePath")
        or ""
    )
    requested_fit = (
        _mapping_value(
            candidate,
            "Fit",
            "fit",
            "ImageFit",
            "image_fit",
            "ScaleMode",
            "scale_mode",
            "Mode",
            "mode",
        )
        or payload.get("image_fit")
        or payload.get("ImageFit")
        or source_params.get("image_fit")
        or source_params.get("ImageFit")
        or "stretch"
    )
    image_fit, unsupported_fit = _normalize_image_fit(requested_fit)
    present = bool(candidate or resource_id or source_path)
    resource_kind = str((resource or {}).get("Kind") or "texture").casefold()
    if not present:
        status = "none"
    elif resource_id and resource is None:
        status = "missing_resource"
    elif resource is not None and resource_kind != "texture":
        status = "unsupported_resource_kind"
    elif not source_path:
        status = "missing_resource_path"
    elif not Path(source_path).expanduser().is_file():
        status = "missing_file"
    elif unsupported_fit:
        status = "unsupported_fit"
    else:
        status = "ready"
    nine_slice_record = _mapping_value(candidate, "NineSlice", "nine_slice")
    nine_slice_record = (
        dict(nine_slice_record)
        if isinstance(nine_slice_record, Mapping)
        else {}
    )
    nine_slice = {
        "left": max(
            0.0,
            _number(_mapping_value(nine_slice_record, "Left", "left"), 0.0),
        ),
        "top": max(
            0.0,
            _number(_mapping_value(nine_slice_record, "Top", "top"), 0.0),
        ),
        "right": max(
            0.0,
            _number(_mapping_value(nine_slice_record, "Right", "right"), 0.0),
        ),
        "bottom": max(
            0.0,
            _number(_mapping_value(nine_slice_record, "Bottom", "bottom"), 0.0),
        ),
    }
    focal_point = _mapping_value(candidate, "FocalPoint", "focal_point")
    focal_point = (
        focal_point if isinstance(focal_point, Mapping) else {}
    )
    crop = _mapping_value(candidate, "Crop", "crop")
    crop = dict(crop) if isinstance(crop, Mapping) else {}
    source_size_record = _mapping_value(
        candidate,
        "SourceSize",
        "source_size",
    )
    source_size_record = (
        source_size_record
        if isinstance(source_size_record, Mapping)
        else {}
    )
    adjustments = _mapping_value(candidate, "Adjustments", "adjustments")
    adjustments = dict(adjustments) if isinstance(adjustments, Mapping) else {}
    corner_radii_record = _mapping_value(
        candidate,
        "CornerRadii",
        "corner_radii",
    )
    corner_radii_record = (
        corner_radii_record
        if isinstance(corner_radii_record, Mapping)
        else {}
    )
    corner_radii = {
        "top_left": max(
            0.0,
            _number(
                _mapping_value(corner_radii_record, "X", "top_left"),
                0.0,
            ),
        ),
        "top_right": max(
            0.0,
            _number(
                _mapping_value(corner_radii_record, "Y", "top_right"),
                0.0,
            ),
        ),
        "bottom_right": max(
            0.0,
            _number(
                _mapping_value(corner_radii_record, "Z", "bottom_right"),
                0.0,
            ),
        ),
        "bottom_left": max(
            0.0,
            _number(
                _mapping_value(corner_radii_record, "W", "bottom_left"),
                0.0,
            ),
        ),
    }
    return {
        "present": present,
        "resource_id": resource_id,
        "source_path": source_path,
        "resource_kind": resource_kind,
        "image_fit": image_fit,
        "requested_fit": str(requested_fit),
        "unsupported_fit": unsupported_fit,
        "status": status,
        "focal_x": max(
            0.0,
            min(
                1.0,
                _number(
                    _mapping_value(candidate, "FocalX", "focal_x"),
                    _number(
                        _mapping_value(focal_point, "X", "x"),
                        0.5,
                    ),
                ),
            ),
        ),
        "focal_y": max(
            0.0,
            min(
                1.0,
                _number(
                    _mapping_value(candidate, "FocalY", "focal_y"),
                    _number(
                        _mapping_value(focal_point, "Y", "y"),
                        0.5,
                    ),
                ),
            ),
        ),
        "tile_scale": max(
            0.05,
            min(
                16.0,
                _number(
                    _mapping_value(candidate, "TileScale", "tile_scale"),
                    1.0,
                ),
            ),
        ),
        "source_size": {
            "width": max(
                0.0,
                _number(
                    _mapping_value(source_size_record, "X", "width"),
                    0.0,
                ),
            ),
            "height": max(
                0.0,
                _number(
                    _mapping_value(source_size_record, "Y", "height"),
                    0.0,
                ),
            ),
        },
        "nine_slice_enabled": bool(
            _mapping_value(
                candidate,
                "NineSliceEnabled",
                "nine_slice_enabled",
            )
            or _mapping_value(nine_slice_record, "Enabled", "enabled")
        ),
        "nine_slice": copy.deepcopy(nine_slice),
        "crop": copy.deepcopy(crop),
        "corner_radii": corner_radii,
        "opacity": max(
            0.0,
            min(
                1.0,
                _number(
                    _mapping_value(candidate, "Opacity", "opacity"),
                    1.0,
                ),
            ),
        ),
        "tint": str(
            _mapping_value(candidate, "Tint", "tint") or "#FFFFFFFF"
        ),
        "adjustments": copy.deepcopy(adjustments),
        "record": copy.deepcopy(candidate),
    }


def _image_fill_warning(
    *,
    layer_id: str,
    name: str,
    binding: Mapping[str, Any],
) -> dict[str, Any]:
    status = str(binding.get("status") or "none")
    requested_fit = str(binding.get("requested_fit") or "")
    resource_id = str(binding.get("resource_id") or "")
    source_path = str(binding.get("source_path") or "")
    if status == "missing_resource":
        message = f"Image resource not found: {resource_id or '(empty id)'}"
    elif status == "unsupported_resource_kind":
        kind = str(binding.get("resource_kind") or "unknown")
        message = f"Image resource must be a texture, got: {kind}"
    elif status == "missing_resource_path":
        message = "Image source path is missing"
    elif status == "missing_file":
        message = f"Image file not found: {source_path or '(empty path)'}"
    elif status == "unsupported_fit":
        message = (
            f"Unsupported image mode: {requested_fit or '(empty)'}; "
            f"preview uses {binding.get('image_fit') or 'fit'}"
        )
    else:
        message = f"Image preview unavailable: {status}"
    return {
        "object_id": str(layer_id),
        "name": str(name),
        "status": status,
        "resource_id": resource_id,
        "source_path": source_path,
        "requested_fit": requested_fit,
        "fallback_fit": str(binding.get("image_fit") or "fit"),
        "message": message,
    }


def _image_preview_content(
    binding: Mapping[str, Any],
    *,
    fallback_text: str = "",
) -> dict[str, Any]:
    content = {
        "source_path": str(binding.get("source_path") or ""),
        "image_fit": str(binding.get("image_fit") or "fit"),
        "focal_x": _number(binding.get("focal_x"), 0.5),
        "focal_y": _number(binding.get("focal_y"), 0.5),
        "tile_scale": _number(binding.get("tile_scale"), 1.0),
        "nine_slice_enabled": bool(
            binding.get("nine_slice_enabled", False)
        ),
        "nine_slice": copy.deepcopy(dict(binding.get("nine_slice") or {})),
        "image_crop": copy.deepcopy(dict(binding.get("crop") or {})),
        "image_opacity": max(
            0.0,
            min(1.0, _number(binding.get("opacity"), 1.0)),
        ),
        "image_tint": str(binding.get("tint") or "#FFFFFFFF"),
        "image_corner_radii": copy.deepcopy(
            dict(binding.get("corner_radii") or {})
        ),
        "image_ref": str(binding.get("resource_id") or "image-fill"),
        "image_preview_status": str(binding.get("status") or "none"),
    }
    source_size = binding.get("source_size")
    source_size = source_size if isinstance(source_size, Mapping) else {}
    content["original_width"] = max(
        0,
        int(round(_number(source_size.get("width"), 0.0))),
    )
    content["original_height"] = max(
        0,
        int(round(_number(source_size.get("height"), 0.0))),
    )
    if fallback_text:
        content["text"] = str(fallback_text)
    return content


def _image_corner_style(binding: Mapping[str, Any]) -> dict[str, Any]:
    source = binding.get("corner_radii")
    source = source if isinstance(source, Mapping) else {}
    radii = {
        key: max(0.0, _number(source.get(key), 0.0))
        for key in (
            "top_left",
            "top_right",
            "bottom_right",
            "bottom_left",
        )
    }
    values = list(radii.values())
    uniform = values[0] if values and max(values) - min(values) <= 1e-6 else 0.0
    return {"radius": uniform, "corner_radii": radii}


def _projection_style_and_content(
    *,
    kind: str,
    name: str,
    payload: Mapping[str, Any],
    image_binding: Mapping[str, Any] | None,
    material: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if material:
        return "rectangle", umg_material_preview_style(material), {}
    fill = str(payload.get("fill") or "#FFFFFFFF")
    image = image_binding if isinstance(image_binding, Mapping) else {}
    has_image = bool(image.get("present"))
    image_ready = str(image.get("status") or "none") in {
        "ready",
        "unsupported_fit",
    }
    image_error_text = (
        ""
        if image_ready or not has_image
        else "Missing image"
    )
    corner_style = _image_corner_style(image) if has_image else {}
    if kind == "Group":
        return (
            "frame",
            {
                "fill": "#00000000",
                "stroke": "#00000000",
                "stroke_width": 0.0,
                "radius": 0.0,
                **corner_style,
            },
            (
                _image_preview_content(
                    image,
                    fallback_text=image_error_text,
                )
                if has_image
                else {}
            ),
        )
    if kind == "Text":
        font_size = max(1, int(math.floor(_number(payload.get("font_size"), 48.0) + 0.5)))
        return (
            "text",
            {
                "fill": "#00000000",
                "stroke": "#00000000",
                "text_color": fill,
                "font_size": float(font_size),
            },
            {"text": str(payload.get("text") or name)},
        )
    if kind == "Button":
        # The generator does not consume Painter button paint/radius/text style.
        # These neutral values approximate UE's default button and text widgets.
        return (
            "button",
            {
                "fill": "#00000000" if has_image else "#4A4A4AFF",
                "stroke": "#777777FF",
                "stroke_width": 1.0,
                "radius": 2.0,
                **corner_style,
                "text_color": "#FFFFFFFF",
                "font_size": 24.0,
                "font_weight": 700,
            },
            (
                _image_preview_content(
                    image,
                    fallback_text=str(payload.get("text") or name),
                )
                if has_image
                else {"text": str(payload.get("text") or name)}
            ),
        )
    source_kind = str(payload.get("source_kind") or "").casefold()
    if has_image:
        proxy_kind = (
            source_kind
            if source_kind in {"rectangle", "ellipse"}
            else "image"
        )
        return (
            proxy_kind,
            {
                "fill": "#00000000",
                "stroke": "#00000000",
                "stroke_width": 0.0,
                "radius": 0.0,
                **corner_style,
                "text_color": "#FFBE55FF",
                "font_size": 12.0,
            },
            _image_preview_content(
                image,
                fallback_text=image_error_text,
            ),
        )
    return (
        "ellipse" if source_kind == "ellipse" else "rectangle",
        {
            "fill": fill,
            "stroke": "#00000000",
            "stroke_width": 0.0,
            "radius": 0.0,
        },
        {},
    )


def _projection_shell(
    umg_document: Mapping[str, Any],
    *,
    artboard_id: str,
    artboard_name: str,
    selection: Mapping[str, Any] | None,
) -> dict[str, Any]:
    width = max(1, int(round(_number(umg_document.get("Width"), 1920.0))))
    height = max(1, int(round(_number(umg_document.get("Height"), 1080.0))))
    document = create_ui_document(width, height, name=artboard_name)
    document["document_id"] = str(
        umg_document.get("DocumentId") or "tiger-umg-simulation"
    )
    document["revision"] = max(0, int(_number(umg_document.get("Revision"), 0.0)))
    document["active_artboard_id"] = artboard_id
    document["pages"][0]["active_artboard_id"] = artboard_id
    document["artboards"][0].update(
        {
            "id": artboard_id,
            "name": artboard_name,
            "background": "#00000000",
        }
    )
    selected = selection if isinstance(selection, Mapping) else {}
    document["selection"] = {
        "object_id": str(selected.get("object_id") or ""),
        "object_ids": [
            str(value)
            for value in selected.get("object_ids", [])
            if str(value or "")
        ],
    }
    return document


def project_tiger_umg_document(
    value: Mapping[str, Any],
    *,
    artboard_id: str = "umg-artboard",
    artboard_name: str = "UMG Widget",
    selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project the exact currently-generated UMG subset into a Painter document.

    Every Tiger layer is returned in ``widgets``. Native layers and validated
    Custom-HLSL UI Material layers are put in the preview ``document``.
    RoundedCard layers mirror Unreal's stable ``Layer.Id`` CanvasPanel host
    plus padded ``Layer.Id_Visual`` UImage child instead of flattening the two.
    Baked, Blocked, and unknown Material layers remain explicit without being
    falsely rendered.
    """
    umg_document = copy.deepcopy(dict(value))
    schema_version = int(_number(umg_document.get("SchemaVersion"), 0.0))
    resource_by_id = _resource_map(umg_document)
    raw_layers = [
        copy.deepcopy(dict(row))
        for row in umg_document.get("Layers", [])
        if isinstance(row, Mapping)
    ]
    counts = {key: 0 for key in _DISPOSITIONS}
    widgets: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    unrendered: list[dict[str, Any]] = []
    resource_warnings: list[dict[str, Any]] = []

    generated_layers: list[dict[str, Any]] = []
    for layer in raw_layers:
        disposition = str(layer.get("Disposition") or "Blocked")
        reasons = [str(reason) for reason in layer.get("BlockReasons", []) if str(reason)]
        if disposition not in _DISPOSITIONS:
            disposition = "Blocked"
            reasons.append("unknown_umg_disposition")
        if disposition == "Blocked" and not reasons:
            reasons.append("unsupported_layer")
        counts[disposition] += 1
        layer["_sim_disposition"] = disposition
        layer["_sim_reasons"] = reasons
        material_reasons = (
            validate_umg_material_record(
                layer.get("Material"),
                layer_kind=str(layer.get("Kind") or ""),
                document_schema_version=schema_version,
            )
            if disposition == "Material"
            else []
        )
        layer["_sim_material_reasons"] = material_reasons
        if disposition == "Native" or (
            disposition == "Material" and not material_reasons
        ):
            generated_layers.append(layer)

    # Mirror TigerStudioUMGGeneration.cpp: native groups are inserted first and
    # only already-created group panels can parent another group.
    parent_panels: set[str] = {""}
    effective_parent: dict[str, str] = {}
    children: dict[str, list[str]] = {"": []}
    generated_by_id: dict[str, dict[str, Any]] = {}
    for layer in generated_layers:
        layer_id = str(layer.get("Id") or "")
        generated_by_id[layer_id] = layer
        if str(layer.get("Kind") or "Unsupported") != "Group":
            continue
        requested_parent = str(layer.get("ParentId") or "")
        parent_id = requested_parent if requested_parent in parent_panels else ""
        effective_parent[layer_id] = parent_id
        children.setdefault(parent_id, []).append(layer_id)
        children.setdefault(layer_id, [])
        parent_panels.add(layer_id)
    # The leaf pass runs after all native groups are known.
    for layer in generated_layers:
        layer_id = str(layer.get("Id") or "")
        if str(layer.get("Kind") or "Unsupported") == "Group":
            continue
        requested_parent = str(layer.get("ParentId") or "")
        parent_id = requested_parent if requested_parent in parent_panels else ""
        effective_parent[layer_id] = parent_id
        children.setdefault(parent_id, []).append(layer_id)

    paint_order: list[str] = []
    seen: set[str] = set()

    def append_subtree(parent_id: str) -> None:
        for layer_id in children.get(parent_id, []):
            if layer_id in seen:
                continue
            seen.add(layer_id)
            paint_order.append(layer_id)
            append_subtree(layer_id)

    append_subtree("")
    for layer in generated_layers:
        layer_id = str(layer.get("Id") or "")
        if layer_id not in seen:
            seen.add(layer_id)
            paint_order.append(layer_id)
    z_index_by_id = {layer_id: index for index, layer_id in enumerate(paint_order)}

    world_transform: dict[str, _Matrix] = {}
    cumulative_opacity: dict[str, float] = {}
    canvas_slot_by_id: dict[str, dict[str, Any]] = {}
    local_geometry_by_id: dict[str, dict[str, float]] = {}

    def resolve_layout(
        layer_id: str,
        resolving: set[str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, float]]:
        cached_slot = canvas_slot_by_id.get(layer_id)
        cached_geometry = local_geometry_by_id.get(layer_id)
        if cached_slot is not None and cached_geometry is not None:
            return cached_slot, cached_geometry
        layer = generated_by_id[layer_id]
        parent_id = effective_parent.get(layer_id, "")
        resolving = set(resolving or ())
        if layer_id in resolving:
            parent_id = ""
        resolving.add(layer_id)
        if parent_id in generated_by_id:
            _parent_slot, parent_geometry = resolve_layout(
                parent_id,
                resolving,
            )
            parent_width = float(parent_geometry["width"])
            parent_height = float(parent_geometry["height"])
        else:
            parent_width = max(
                1.0,
                _number(umg_document.get("Width"), 1920.0),
            )
            parent_height = max(
                1.0,
                _number(umg_document.get("Height"), 1080.0),
            )
        slot = _canvas_slot(layer, schema_version=schema_version)
        geometry = _slot_geometry(
            slot,
            parent_width=parent_width,
            parent_height=parent_height,
        )
        canvas_slot_by_id[layer_id] = slot
        local_geometry_by_id[layer_id] = geometry
        return slot, geometry

    def resolve_transform(layer_id: str, resolving: set[str] | None = None) -> _Matrix:
        cached = world_transform.get(layer_id)
        if cached is not None:
            return cached
        layer = generated_by_id[layer_id]
        parent_id = effective_parent.get(layer_id, "")
        resolving = set(resolving or ())
        if layer_id in resolving:
            parent_id = ""
        resolving.add(layer_id)
        parent_transform = (
            resolve_transform(parent_id, resolving)
            if parent_id in generated_by_id
            else (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        )
        _slot, local_geometry = resolve_layout(layer_id)
        render_pivot = _render_transform_pivot(
            layer,
            schema_version=schema_version,
        )
        result = _compose(
            parent_transform,
            _widget_transform(
                layer,
                geometry=local_geometry,
                render_pivot=render_pivot,
            ),
        )
        world_transform[layer_id] = result
        parent_opacity = cumulative_opacity.get(parent_id)
        if parent_opacity is None and parent_id in generated_by_id:
            resolve_transform(parent_id, resolving)
            parent_opacity = cumulative_opacity.get(parent_id, 1.0)
        cumulative_opacity[layer_id] = (
            float(parent_opacity if parent_opacity is not None else 1.0)
            * _number(layer.get("Opacity"), 1.0)
        )
        return result

    projection = _projection_shell(
        umg_document,
        artboard_id=str(artboard_id or "umg-artboard"),
        artboard_name=str(artboard_name or "UMG Widget"),
        selection=selection,
    )
    projected_objects: list[dict[str, Any]] = []
    widget_by_id: dict[str, dict[str, Any]] = {}
    for source_index, layer in enumerate(raw_layers):
        layer_id = str(layer.get("Id") or f"umg-layer-{source_index + 1}")
        name = str(layer.get("Name") or layer_id)
        kind = str(layer.get("Kind") or "Unsupported")
        disposition = str(layer["_sim_disposition"])
        reasons = list(layer["_sim_reasons"])
        material_reasons = list(layer["_sim_material_reasons"])
        all_reasons = sorted(set([*reasons, *material_reasons]))
        resource_id = str(layer.get("AssetId") or "")
        resource = resource_by_id.get(resource_id)
        payload = _payload(layer.get("PayloadJson"))
        image_binding = _image_fill_binding(
            layer,
            payload,
            resource_by_id,
        )
        if image_binding.get("present"):
            resource_id = str(image_binding.get("resource_id") or resource_id)
            resource = resource_by_id.get(resource_id)
        rendered = disposition == "Native" or (
            disposition == "Material" and not material_reasons
        )
        material_record = (
            copy.deepcopy(dict(layer.get("Material") or {}))
            if disposition == "Material"
            and isinstance(layer.get("Material"), Mapping)
            else {}
        )
        rounded_card = rendered and _is_rounded_card_material(material_record)
        scroll_overflow = str(layer.get("ScrollOverflow") or "None")
        scroll_position = str(layer.get("ScrollPosition") or "Scroll")
        generated_container_classes: list[str] = []
        if rendered and kind == "Group" and scroll_overflow != "None":
            generated_container_classes = ["UOverlay", "UScrollBox"]
            if scroll_overflow == "Both":
                generated_container_classes.append("UScrollBox")
            generated_container_classes.append("UCanvasPanel")
        widget = {
            "id": layer_id,
            "name": name,
            "source_index": source_index,
            "kind": kind,
            "widget_class": (
                "UCanvasPanel"
                if rounded_card
                else _widget_class(kind)
                if rendered
                else ""
            ),
            "disposition": disposition,
            "rendered": rendered,
            "reasons": all_reasons,
            "requested_parent_id": str(layer.get("ParentId") or ""),
            "effective_parent_id": effective_parent.get(layer_id, "") if rendered else "",
            "consumed_properties": (
                _rounded_card_host_consumed_properties(
                    schema_version=schema_version
                )
                if rounded_card
                else _consumed_properties(kind, schema_version=schema_version)
                if rendered
                else []
            ),
            "generator_action": (
                "construct_material"
                if rendered and disposition == "Material"
                else "construct"
                if rendered
                else "skip"
            ),
            "resource_id": resource_id,
            "resource_path": (
                str(image_binding.get("source_path") or "")
                if image_binding.get("present")
                else str((resource or {}).get("SourcePath") or "")
            ),
            "image_fill": (
                copy.deepcopy(image_binding)
                if image_binding.get("present")
                else {}
            ),
            # Keep the provider-neutral record on the report widget so UI
            # inspectors can show the exact graph Unreal will construct.
            # This remains separate from the Painter proxy style, which is
            # only a visual approximation of the generated material.
            "material": material_record,
            "panel_kind": str(layer.get("PanelKind") or "None"),
            "scroll_overflow": scroll_overflow,
            "scroll_position": scroll_position,
            "generated_container_classes": generated_container_classes,
        }
        widgets.append(widget)
        if rendered and disposition == "Material" and not rounded_card:
            widget["consumed_properties"].extend(
                _material_consumed_properties(layer.get("Material"))
            )
        if rendered and image_binding.get("present"):
            for property_name in _image_fill_consumed_properties():
                if property_name not in widget["consumed_properties"]:
                    widget["consumed_properties"].append(property_name)
        widget_by_id[layer_id] = widget
        if disposition == "Blocked":
            blockers.append(
                {"object_id": layer_id, "name": name, "reasons": reasons}
            )
        elif disposition == "Material" and material_reasons:
            blockers.append(
                {
                    "object_id": layer_id,
                    "name": name,
                    "reasons": material_reasons,
                }
            )
        if not rendered:
            unrendered.append(
                {
                    "object_id": layer_id,
                    "name": name,
                    "disposition": disposition,
                    "reasons": all_reasons,
                }
            )
            continue

        image_status = str(image_binding.get("status") or "none")
        if image_status not in {"none", "ready"}:
            warning = _image_fill_warning(
                layer_id=layer_id,
                name=name,
                binding=image_binding,
            )
            resource_warnings.append(warning)
            widget["preview_warnings"] = [copy.deepcopy(warning)]

        slot, local_geometry = resolve_layout(layer_id)
        width = float(local_geometry["width"])
        height = float(local_geometry["height"])
        render_pivot_x, render_pivot_y = _render_transform_pivot(
            layer,
            schema_version=schema_version,
        )
        transform = resolve_transform(layer_id)
        geometry = _proxy_geometry(
            transform,
            width=width,
            height=height,
            anchor_x=render_pivot_x,
            anchor_y=render_pivot_y,
        )
        proxy_kind, style, content = _projection_style_and_content(
            kind=kind,
            name=name,
            payload=payload,
            image_binding=image_binding,
            material=(
                dict(layer.get("Material") or {})
                if disposition == "Material"
                else None
            ),
        )
        if rendered and disposition == "Material":
            # Preserve the exact preview projection alongside the normalized
            # Painter object. This keeps independent corners, stroke alignment,
            # and both shadow records inspectable even if a future Painter
            # normalizer adds or changes legacy aliases.
            widget["material_preview_style"] = copy.deepcopy(style)
        widget["world_transform"] = {
            key: value
            for key, value in zip(("a", "b", "c", "d", "tx", "ty"), transform)
        }
        widget["proxy_accuracy"] = geometry["accuracy"]
        anchor_minimum_x, anchor_minimum_y = slot["anchor_minimum"]
        anchor_maximum_x, anchor_maximum_y = slot["anchor_maximum"]
        alignment_x, alignment_y = slot["alignment"]
        offset_left, offset_top, offset_right, offset_bottom = slot["offsets"]
        position_x, position_y = _vector(
            layer.get("Position"),
            default_x=0.0,
            default_y=0.0,
        )
        widget["slot"] = {
            "anchor_minimum": {
                "x": anchor_minimum_x,
                "y": anchor_minimum_y,
            },
            "anchor_maximum": {
                "x": anchor_maximum_x,
                "y": anchor_maximum_y,
            },
            "offsets": {
                "left": offset_left,
                "top": offset_top,
                "right": offset_right,
                "bottom": offset_bottom,
            },
            "position": {"x": position_x, "y": position_y},
            "size": {"x": width, "y": height},
            "resolved_geometry": copy.deepcopy(local_geometry),
            "alignment": {"x": alignment_x, "y": alignment_y},
            "auto_size": bool(slot["auto_size"]),
        }
        widget["render_transform_pivot"] = {
            "x": render_pivot_x,
            "y": render_pivot_y,
        }
        object_opacity = max(
            0.0,
            min(1.0, cumulative_opacity.get(layer_id, 1.0)),
        )
        object_z_index = z_index_by_id.get(layer_id, source_index)
        projected_object = {
            "id": layer_id,
            "kind": "frame" if rounded_card else proxy_kind,
            "name": name,
            "artboard_id": str(artboard_id or "umg-artboard"),
            "parent_id": effective_parent.get(layer_id, ""),
            "x": geometry["x"],
            "y": geometry["y"],
            "width": geometry["width"],
            "height": geometry["height"],
            "rotation": geometry["rotation"],
            "opacity": object_opacity,
            "visible": True,
            "locked": True,
            "clip_content": (
                bool(payload.get("clip_content", False))
                if kind == "Group" and not rounded_card
                else False
            ),
            "scroll": {
                "overflow": scroll_overflow.casefold(),
                "position": scroll_position.casefold(),
                "preserve_position": True,
            },
            "z_index": object_z_index,
            "style": (
                {
                    "fill": "#00000000",
                    "stroke": "#00000000",
                    "stroke_width": 0.0,
                    "radius": 0.0,
                }
                if rounded_card
                else style
            ),
            "content": {} if rounded_card else content,
            "constraints": {
                "horizontal": "left",
                "vertical": "top",
                "pivot_x": render_pivot_x,
                "pivot_y": render_pivot_y,
            },
        }
        projected_objects.append(projected_object)

        if rounded_card:
            visual_id = f"{layer_id}_Visual"
            padding = material_record.get("VisualPadding")
            padding = padding if isinstance(padding, Mapping) else {}
            padding_left = max(0.0, _number(padding.get("Left"), 0.0))
            padding_top = max(0.0, _number(padding.get("Top"), 0.0))
            padding_right = max(0.0, _number(padding.get("Right"), 0.0))
            padding_bottom = max(0.0, _number(padding.get("Bottom"), 0.0))
            material_width, material_height = _vector(
                material_record.get("Size"),
                default_x=width,
                default_y=height,
            )
            material_width = max(0.001, material_width)
            material_height = max(0.001, material_height)
            surface_width = material_width + padding_left + padding_right
            surface_height = material_height + padding_top + padding_bottom
            visual_transform = _compose(
                transform,
                _translate(-padding_left, -padding_top),
            )
            visual_pivot_x = (
                padding_left + width * render_pivot_x
            ) / surface_width
            visual_pivot_y = (
                padding_top + height * render_pivot_y
            ) / surface_height
            visual_geometry = _proxy_geometry(
                visual_transform,
                width=surface_width,
                height=surface_height,
                anchor_x=visual_pivot_x,
                anchor_y=visual_pivot_y,
            )
            visual_consumed = [
                *_material_consumed_properties(material_record),
                "DesiredSizeOverride",
                "CanvasSlot.Anchors",
                "CanvasSlot.Alignment",
                "CanvasSlot.Position",
                "CanvasSlot.Size",
                "CanvasSlot.AutoSize",
            ]
            visual_widget = {
                "id": visual_id,
                "name": f"{name} Visual",
                "source_index": source_index,
                "source_layer_id": layer_id,
                "synthetic": True,
                "kind": "Image",
                "widget_class": "UImage",
                "disposition": "Material",
                "rendered": True,
                "reasons": [],
                "requested_parent_id": layer_id,
                "effective_parent_id": layer_id,
                "consumed_properties": visual_consumed,
                "generator_action": "construct_material_visual",
                "resource_id": "",
                "resource_path": "",
                "material": copy.deepcopy(material_record),
                "material_preview_style": copy.deepcopy(style),
                "world_transform": {
                    key: value
                    for key, value in zip(
                        ("a", "b", "c", "d", "tx", "ty"),
                        visual_transform,
                    )
                },
                "proxy_accuracy": visual_geometry["accuracy"],
                "slot": {
                    "anchor_minimum": {"x": 0.0, "y": 0.0},
                    "anchor_maximum": {"x": 0.0, "y": 0.0},
                    "offsets": {
                        "left": -padding_left,
                        "top": -padding_top,
                        "right": surface_width,
                        "bottom": surface_height,
                    },
                    "position": {
                        "x": -padding_left,
                        "y": -padding_top,
                    },
                    "size": {"x": surface_width, "y": surface_height},
                    "resolved_geometry": {
                        "x": -padding_left,
                        "y": -padding_top,
                        "width": surface_width,
                        "height": surface_height,
                    },
                    "alignment": {"x": 0.0, "y": 0.0},
                    "auto_size": False,
                },
                "render_transform_pivot": {
                    "x": visual_pivot_x,
                    "y": visual_pivot_y,
                },
            }
            widget["generated_children"] = [visual_id]
            widget["visual_widget_id"] = visual_id
            widgets.append(visual_widget)
            widget_by_id[visual_id] = visual_widget
            projected_objects.append(
                {
                    "id": visual_id,
                    "kind": "rectangle",
                    "name": f"{name} Visual",
                    "artboard_id": str(artboard_id or "umg-artboard"),
                    "parent_id": layer_id,
                    "x": visual_geometry["x"],
                    "y": visual_geometry["y"],
                    "width": visual_geometry["width"],
                    "height": visual_geometry["height"],
                    "rotation": visual_geometry["rotation"],
                    "opacity": 1.0,
                    "visible": True,
                    "locked": True,
                    "clip_content": False,
                    "z_index": object_z_index,
                    "style": style,
                    "content": {},
                    "constraints": {
                        "horizontal": "left",
                        "vertical": "top",
                        "pivot_x": visual_pivot_x,
                        "pivot_y": visual_pivot_y,
                    },
                }
            )

    projection["objects"] = projected_objects
    projection = normalize_ui_document(projection)
    rendered_ids = {row["id"] for row in projected_objects}
    projection["selection"] = {
        "object_id": (
            str((selection or {}).get("object_id") or "")
            if str((selection or {}).get("object_id") or "") in rendered_ids
            else ""
        ),
        "object_ids": [
            str(value)
            for value in (selection or {}).get("object_ids", [])
            if str(value) in rendered_ids
        ],
    }

    missing_resources = [
        str(resource.get("SourcePath") or "")
        for resource in resource_by_id.values()
        if not Path(str(resource.get("SourcePath") or "")).expanduser().is_file()
    ]
    for warning in resource_warnings:
        if str(warning.get("status") or "") != "missing_file":
            continue
        source_path = str(warning.get("source_path") or "")
        if source_path and source_path not in missing_resources:
            missing_resources.append(source_path)
    return {
        "schema": PAINTER_UMG_SIMULATOR_SCHEMA,
        "contract": {
            "schema_version": schema_version,
            "supported_schema_version": TIGER_UMG_SCHEMA_VERSION,
            "supported_schema_versions": list(
                range(4, TIGER_UMG_SCHEMA_VERSION + 1)
            ),
            "generator": "TigerStudioUMGGeneration.cpp",
            "authority": "unreal_generation_and_capture",
            "local_preview": "compatibility_proxy",
        },
        "source": {
            "provider": str(umg_document.get("Provider") or ""),
            "document_id": str(umg_document.get("DocumentId") or ""),
            "revision": max(0, int(_number(umg_document.get("Revision"), 0.0))),
            "artboard_id": str(artboard_id or "umg-artboard"),
        },
        "canvas": {
            "width": int(projection["artboards"][0]["width"]),
            "height": int(projection["artboards"][0]["height"]),
            "root_widget_class": "UCanvasPanel",
            "generated_root_widget_class": "UCanvasPanel",
            "background": "transparent",
        },
        "document": projection,
        "widgets": widgets,
        "widgets_by_id": widget_by_id,
        "counts": counts,
        "blockers": blockers,
        "unrendered": unrendered,
        "missing_resources": missing_resources,
        "resource_warnings": resource_warnings,
        "resource_count": len(resource_by_id),
        "interaction_count": len(
            [row for row in umg_document.get("Interactions", []) if isinstance(row, Mapping)]
        ),
        "ready": (
            schema_version in range(4, TIGER_UMG_SCHEMA_VERSION + 1)
            and not blockers
            and not missing_resources
            and not resource_warnings
        ),
        "complete": not unrendered,
    }


def project_painter_ui_umg_widgets(
    value: Mapping[str, Any],
    *,
    artboard_id: str = "",
) -> dict[str, Any]:
    """Build the non-mutating UMG widget projection for a Painter document."""
    source = normalize_ui_document(value)
    selected_artboard_id = str(artboard_id or source["active_artboard_id"])
    selected_artboard = next(
        (
            row
            for row in source["artboards"]
            if row["id"] == selected_artboard_id
        ),
        None,
    )
    if selected_artboard is None:
        raise ValueError(f"Painter UI artboard not found: {selected_artboard_id}")
    umg_document = painter_ui_to_umg_document(
        source,
        artboard_id=selected_artboard_id,
    )
    preflight = preflight_painter_umg(
        source,
        artboard_id=selected_artboard_id,
    )
    result = project_tiger_umg_document(
        umg_document,
        artboard_id=selected_artboard_id,
        artboard_name=f"{selected_artboard['name']} - UMG Widget",
        selection=source.get("selection"),
    )
    result["source"].update(
        {
            "painter_document_id": source["document_id"],
            "painter_revision": source["revision"],
        }
    )
    result["preflight"] = copy.deepcopy(preflight)
    # Keep the exact adapter report authoritative for Painter-facing readiness.
    result["ready"] = bool(preflight["ok"]) and not bool(
        result.get("resource_warnings")
    )
    return result


__all__ = [
    "PAINTER_UMG_SIMULATOR_SCHEMA",
    "project_painter_ui_umg_widgets",
    "project_tiger_umg_document",
]

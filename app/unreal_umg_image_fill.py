"""Provider-neutral image-fill records for Tiger Studio UMG documents.

Painter and Motion Designer store image placement differently.  This module
is the one normalization boundary between those provider contracts and the
typed ``Layer.ImageFill`` record consumed by TigerStudioUMG.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence


IMAGE_FILL_MODES = frozenset({"Stretch", "Fit", "Fill", "Crop", "Tile"})
IMAGE_ADJUSTMENT_KEYS = (
    "Exposure",
    "Contrast",
    "Saturation",
    "Temperature",
    "Tint",
    "Highlights",
)
_PAINTER_IMAGE_FILL_KINDS = frozenset(
    {"button", "ellipse", "frame", "image", "rectangle"}
)
_MODE_ALIASES = {
    "stretch": "Stretch",
    "fit": "Fit",
    "contain": "Fit",
    "scale_down": "Fit",
    "fill": "Fill",
    "cover": "Fill",
    "crop": "Crop",
    "tile": "Tile",
    "repeat": "Tile",
}


@dataclass(slots=True)
class UMGImageFillConversion:
    """One provider image fill before its texture resource is registered."""

    source_path: str
    record: dict[str, Any]
    block_reasons: list[str]

    def bind_asset(self, asset_id: str) -> dict[str, Any]:
        bound = dict(self.record)
        bound["AssetId"] = str(asset_id or "")
        return bound


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return result if math.isfinite(result) else float(default)


def _bounded(value: object, minimum: float, maximum: float, default: float) -> float:
    return max(minimum, min(maximum, _number(value, default)))


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence4(value: object) -> list[object] | None:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        row = list(value)
        return row[:4] if len(row) >= 4 else None
    return None


def _hex_channel(value: float) -> str:
    return f"{max(0, min(255, int(round(value)))):02X}"


def _color_hex(value: object, default: str = "#FFFFFFFF") -> str:
    if isinstance(value, str):
        source = value.strip()
        if source.startswith("#"):
            source = source[1:]
        if len(source) in {3, 4} and all(ch in "0123456789abcdefABCDEF" for ch in source):
            source = "".join(ch * 2 for ch in source)
        if len(source) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in source):
            return f"#{source.upper()}FF"
        if len(source) == 8 and all(ch in "0123456789abcdefABCDEF" for ch in source):
            return f"#{source.upper()}"
        return default
    if isinstance(value, Mapping):
        channels = [value.get(key, fallback) for key, fallback in (
            ("r", 1.0), ("g", 1.0), ("b", 1.0), ("a", 1.0),
        )]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        channels = list(value)[:4]
        channels.extend([1.0] * (4 - len(channels)))
    else:
        return default
    values = [_number(channel, 1.0) for channel in channels]
    scale = 255.0 if max(values, default=1.0) <= 1.0 else 1.0
    return "#" + "".join(_hex_channel(channel * scale) for channel in values)


def _canonical_mode(value: object) -> tuple[str, list[str]]:
    raw = str(value or "stretch").strip().casefold()
    mode = _MODE_ALIASES.get(raw)
    if mode is None:
        return "Stretch", [f"image_fill_mode_unsupported:{raw or 'empty'}"]
    return mode, []


def _source_size(source: Mapping[str, Any]) -> dict[str, float]:
    return {
        "X": max(
            0.0,
            _number(
                source.get("original_width", source.get("source_width")),
                0.0,
            ),
        ),
        "Y": max(
            0.0,
            _number(
                source.get("original_height", source.get("source_height")),
                0.0,
            ),
        ),
    }


def _crop_record(value: object) -> tuple[dict[str, Any], list[str]]:
    source = _mapping(value)
    sequence = _sequence4(value)
    enabled = (
        bool(source.get("enabled", source.get("Enabled", True)))
        if source
        else sequence is not None
    )
    if not source and sequence is None:
        return {
            "Enabled": False,
            "Units": "Normalized",
            "X": 0.0,
            "Y": 0.0,
            "Width": 1.0,
            "Height": 1.0,
        }, []
    values = sequence or [
        source.get("x", source.get("X", 0.0)),
        source.get("y", source.get("Y", 0.0)),
        source.get("width", source.get("Width", 0.0)),
        source.get("height", source.get("Height", 0.0)),
    ]
    x, y, width, height = (_number(item, 0.0) for item in values)
    units_raw = str(source.get("units") or source.get("Units") or "").casefold()
    if units_raw in {"normalized", "normalised", "uv", "ratio"}:
        units = "Normalized"
    elif units_raw in {"pixel", "pixels", "px"}:
        units = "Pixels"
    else:
        units = (
            "Normalized"
            if x >= 0.0
            and y >= 0.0
            and width > 0.0
            and height > 0.0
            and x + width <= 1.000001
            and y + height <= 1.000001
            else "Pixels"
        )
    reasons: list[str] = []
    if enabled and (x < 0.0 or y < 0.0 or width <= 0.0 or height <= 0.0):
        reasons.append("image_fill_crop_rect_invalid")
    if enabled and units == "Normalized" and (
        x + width > 1.000001 or y + height > 1.000001
    ):
        reasons.append("image_fill_crop_rect_out_of_bounds")
    return {
        "Enabled": enabled,
        "Units": units,
        "X": x,
        "Y": y,
        "Width": width,
        "Height": height,
    }, reasons


def _nine_slice_record(value: Mapping[str, Any]) -> dict[str, Any]:
    margins = _mapping(value.get("nine_slice"))
    enabled = bool(value.get("nine_slice_enabled", margins.get("enabled", False)))
    return {
        "Enabled": enabled,
        "Units": "Pixels",
        "Left": max(0.0, _number(margins.get("left"), 0.0)),
        "Top": max(0.0, _number(margins.get("top"), 0.0)),
        "Right": max(0.0, _number(margins.get("right"), 0.0)),
        "Bottom": max(0.0, _number(margins.get("bottom"), 0.0)),
    }


def _adjustment_record(value: object) -> tuple[dict[str, float], list[str]]:
    source = _mapping(value)
    result = {
        key: _number(source.get(key.casefold(), source.get(key)), 0.0)
        for key in IMAGE_ADJUSTMENT_KEYS
    }
    reasons = (
        ["image_fill_adjustments_require_ui_material_or_bake"]
        if any(abs(number) > 0.0001 for number in result.values())
        else []
    )
    return result, reasons


def _corner_radii(
    style: Mapping[str, Any],
    size: Mapping[str, Any] | None,
) -> dict[str, float]:
    radius = max(0.0, _number(style.get("radius"), 0.0))
    source = _mapping(style.get("corner_radii"))
    values = [
        max(0.0, _number(source.get(key), radius))
        for key in ("top_left", "top_right", "bottom_right", "bottom_left")
    ]
    width = max(0.0001, _number(_mapping(size).get("width", _mapping(size).get("X")), 100.0))
    height = max(0.0001, _number(_mapping(size).get("height", _mapping(size).get("Y")), 100.0))
    scale = min(
        1.0,
        width / max(width, values[0] + values[1], values[3] + values[2]),
        height / max(height, values[0] + values[3], values[1] + values[2]),
    )
    values = [value * scale for value in values]
    return dict(zip(("X", "Y", "Z", "W"), values, strict=True))


def _normalized_conversion(
    source: Mapping[str, Any],
    *,
    source_path: str,
    default_mode: str,
    corner_radii: Mapping[str, Any] | None = None,
    extra_reasons: Sequence[str] = (),
) -> UMGImageFillConversion:
    mode, reasons = _canonical_mode(
        source.get("image_fit", source.get("fit", default_mode))
    )
    crop, crop_reasons = _crop_record(
        source.get("image_crop", source.get("crop"))
    )
    nine_slice = _nine_slice_record(source)
    adjustments, adjustment_reasons = _adjustment_record(
        source.get("adjustments", source.get("image_adjustments"))
    )
    reasons.extend(crop_reasons)
    reasons.extend(adjustment_reasons)
    reasons.extend(str(reason) for reason in extra_reasons if str(reason))
    if mode == "Crop" and not crop["Enabled"]:
        reasons.append("image_fill_crop_rect_missing")
    # Painter's own renderer gives nine-slice precedence over image_fit, so
    # canonicalizing it to Stretch preserves the authored result exactly.
    if nine_slice["Enabled"]:
        mode = "Stretch"
    radii = dict(corner_radii or {"X": 0.0, "Y": 0.0, "Z": 0.0, "W": 0.0})
    if nine_slice["Enabled"] and any(float(value) > 0.0001 for value in radii.values()):
        reasons.append(
            "image_fill_nine_slice_rounded_corners_require_ui_material_or_bake"
        )
    if mode == "Tile" and any(float(value) > 0.0001 for value in radii.values()):
        reasons.append(
            "image_fill_tile_rounded_corners_require_ui_material_or_bake"
        )
    if not str(source_path or "").strip():
        reasons.append("image_fill_missing_source_path")
    if abs(_number(source.get("rotation"), 0.0)) > 0.0001:
        reasons.append("image_fill_rotation_requires_ui_material_or_bake")
    if source.get("figma_image_transform") not in (None, [], {}):
        reasons.append(
            "image_fill_transform_requires_ui_material_or_bake"
        )
    blend_mode = str(source.get("blend_mode") or "normal").strip().casefold()
    if blend_mode != "normal":
        reasons.append("image_fill_blend_mode_requires_ui_material_or_bake")
    opacity = _bounded(
        source.get("image_opacity", source.get("opacity")),
        0.0,
        1.0,
        1.0,
    )
    tint_source = source.get("image_tint", source.get("tint", source.get("color")))
    return UMGImageFillConversion(
        source_path=str(source_path or ""),
        record={
            "AssetId": "",
            "Mode": mode,
            "FocalPoint": {
                "X": _bounded(source.get("focal_x"), 0.0, 1.0, 0.5),
                "Y": _bounded(source.get("focal_y"), 0.0, 1.0, 0.5),
            },
            "TileScale": max(0.0001, _number(source.get("tile_scale"), 1.0)),
            "SourceSize": _source_size(source),
            "Crop": crop,
            "NineSlice": nine_slice,
            "CornerRadii": radii,
            "Opacity": opacity,
            "Tint": _color_hex(tint_source, "#FFFFFFFF"),
            "Adjustments": adjustments,
        },
        block_reasons=sorted(set(reasons)),
    )


def painter_image_fill_conversion(
    row: Mapping[str, Any],
    style: Mapping[str, Any],
    content: Mapping[str, Any],
    *,
    size: Mapping[str, Any] | None = None,
) -> UMGImageFillConversion | None:
    """Convert Painter content/image paint to one typed UMG image fill.

    ``content.source_path`` is authoritative because it is the contract used
    by Painter's image-fill inspector for shapes, frames and buttons.  An
    advanced ``style.fills[type=image]`` paint is the fallback.
    """

    kind = str(row.get("kind") or "").strip().casefold()
    content_path = str(content.get("source_path") or content.get("path") or "")
    image_paints = [
        paint
        for paint in (style.get("fills") if isinstance(style.get("fills"), list) else [])
        if isinstance(paint, Mapping)
        and bool(paint.get("visible", True))
        and str(paint.get("type") or "").strip().casefold() == "image"
    ]
    paint = image_paints[0] if image_paints else {}
    paint_path = str(paint.get("source_path") or paint.get("path") or paint.get("uri") or "")
    if not content_path and not image_paints:
        return None
    source = (
        dict(paint)
        if not content_path
        else {**dict(paint), **dict(content)}
    )
    source_path = content_path or paint_path
    extra_reasons: list[str] = []
    if kind not in _PAINTER_IMAGE_FILL_KINDS:
        extra_reasons.append(f"image_fill_unsupported_object_kind:{kind or 'unknown'}")
    if kind == "ellipse":
        extra_reasons.append("image_fill_ellipse_clip_requires_ui_material_or_bake")
    if len(image_paints) > 1:
        extra_reasons.append("multiple_image_fills_require_ui_material_or_bake")
    if content_path and paint_path and content_path != paint_path:
        extra_reasons.append("multiple_image_fill_sources_require_ui_material_or_bake")
    if _number(style.get("corner_smoothing"), 0.0) > 0.0001:
        extra_reasons.append("image_fill_corner_smoothing_requires_ui_material_or_bake")
    return _normalized_conversion(
        source,
        source_path=source_path,
        default_mode="fill" if kind != "image" else "fit",
        corner_radii=_corner_radii(style, size),
        extra_reasons=extra_reasons,
    )


def motion_image_fill_conversion(layer: Any) -> UMGImageFillConversion | None:
    """Convert a Motion image layer or ``source.params.image_fill`` record."""

    layer_type = str(getattr(layer, "layer_type", "") or "").strip().casefold()
    source_ref = getattr(layer, "source", None)
    params = dict(getattr(source_ref, "params", {}) or {})
    nested = params.get("image_fill")
    if layer_type != "image" and not isinstance(nested, Mapping):
        return None
    source = (
        {**dict(params), **dict(nested)}
        if isinstance(nested, Mapping)
        else dict(params)
    )
    source_path = str(
        source.get("source_path")
        or source.get("path")
        or source.get("uri")
        or getattr(source_ref, "uri", "")
        or ""
    )
    primitive = str(params.get("shape") or params.get("primitive") or "rectangle").casefold()
    extra_reasons: list[str] = []
    if layer_type == "shape" and primitive != "rectangle":
        extra_reasons.append("image_fill_shape_clip_requires_ui_material_or_bake")
    style = {
        "radius": source.get("radius", params.get("radius", 0.0)),
        "corner_radii": source.get("corner_radii", params.get("corner_radii", {})),
    }
    size = {
        "width": params.get("width", 100.0),
        "height": params.get("height", 100.0),
    }
    return _normalized_conversion(
        source,
        source_path=source_path,
        default_mode="contain" if layer_type == "image" else "fill",
        corner_radii=_corner_radii(style, size),
        extra_reasons=extra_reasons,
    )


def validate_umg_image_fill_record(
    value: object,
    *,
    layer_asset_id: str = "",
    runtime_size_dynamic: bool = False,
) -> list[str]:
    """Validate the typed record without accepting provider-specific fields."""

    if not isinstance(value, Mapping) or not value:
        return []
    reasons: list[str] = []
    asset_id = str(value.get("AssetId") or "")
    if not asset_id:
        reasons.append("image_fill_asset_id_missing")
    if layer_asset_id and asset_id != str(layer_asset_id):
        reasons.append("image_fill_asset_id_mismatch")
    mode = str(value.get("Mode") or "")
    if mode not in IMAGE_FILL_MODES:
        reasons.append(f"image_fill_mode_unsupported:{mode or 'empty'}")
    if mode == "Fill" and runtime_size_dynamic:
        reasons.append("image_fill_runtime_resize_requires_dynamic_uv_binding")
    focal = _mapping(value.get("FocalPoint"))
    focal_x = _number(focal.get("X"), -1.0)
    focal_y = _number(focal.get("Y"), -1.0)
    if not (0.0 <= focal_x <= 1.0 and 0.0 <= focal_y <= 1.0):
        reasons.append("image_fill_focal_point_invalid")
    if _number(value.get("TileScale"), 0.0) <= 0.0:
        reasons.append("image_fill_tile_scale_invalid")
    opacity = _number(value.get("Opacity"), -1.0)
    if not 0.0 <= opacity <= 1.0:
        reasons.append("image_fill_opacity_invalid")
    tint = str(value.get("Tint") or "")
    if not (
        len(tint) == 9
        and tint.startswith("#")
        and all(ch in "0123456789abcdefABCDEF" for ch in tint[1:])
    ):
        reasons.append("image_fill_tint_invalid")
    crop = _mapping(value.get("Crop"))
    if bool(crop.get("Enabled", False)):
        units = str(crop.get("Units") or "")
        x = _number(crop.get("X"), -1.0)
        y = _number(crop.get("Y"), -1.0)
        width = _number(crop.get("Width"), 0.0)
        height = _number(crop.get("Height"), 0.0)
        if units not in {"Normalized", "Pixels"}:
            reasons.append("image_fill_crop_units_invalid")
        if x < 0.0 or y < 0.0 or width <= 0.0 or height <= 0.0:
            reasons.append("image_fill_crop_rect_invalid")
        if units == "Normalized" and (
            x + width > 1.000001 or y + height > 1.000001
        ):
            reasons.append("image_fill_crop_rect_out_of_bounds")
    if mode == "Crop" and not bool(crop.get("Enabled", False)):
        reasons.append("image_fill_crop_rect_missing")
    adjustments = _mapping(value.get("Adjustments"))
    if any(
        abs(_number(adjustments.get(key), 0.0)) > 0.0001
        for key in IMAGE_ADJUSTMENT_KEYS
    ):
        reasons.append("image_fill_adjustments_require_ui_material_or_bake")
    radii = _mapping(value.get("CornerRadii"))
    radius_values = [_number(radii.get(key), -1.0) for key in ("X", "Y", "Z", "W")]
    if any(radius < 0.0 for radius in radius_values):
        reasons.append("image_fill_corner_radii_invalid")
    has_radius = any(radius > 0.0001 for radius in radius_values)
    nine_slice = _mapping(value.get("NineSlice"))
    if bool(nine_slice.get("Enabled", False)):
        if mode != "Stretch":
            reasons.append("image_fill_nine_slice_requires_stretch")
        if str(nine_slice.get("Units") or "") != "Pixels":
            reasons.append("image_fill_nine_slice_units_invalid")
        if any(
            _number(nine_slice.get(edge), -1.0) < 0.0
            for edge in ("Left", "Top", "Right", "Bottom")
        ):
            reasons.append("image_fill_nine_slice_margins_invalid")
        if has_radius:
            reasons.append(
                "image_fill_nine_slice_rounded_corners_require_ui_material_or_bake"
            )
    if mode == "Tile" and has_radius:
        reasons.append(
            "image_fill_tile_rounded_corners_require_ui_material_or_bake"
        )
    return sorted(set(reasons))


__all__ = [
    "IMAGE_ADJUSTMENT_KEYS",
    "IMAGE_FILL_MODES",
    "UMGImageFillConversion",
    "motion_image_fill_conversion",
    "painter_image_fill_conversion",
    "validate_umg_image_fill_record",
]

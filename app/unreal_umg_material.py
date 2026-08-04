"""Provider-neutral UMG UI material records and fixed Custom HLSL code."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


# The v1 names are public and intentionally remain the defaults for legacy
# linear/radial-gradient records.
TIGER_UMG_UI_MATERIAL_SCHEMA = "tigerstudio.umg.ui_material.v1"
TIGER_UMG_CUSTOM_HLSL_GENERATOR = "tiger_ui_gradient_custom_hlsl_v1"
TIGER_UMG_UI_MATERIAL_DOCUMENT_SCHEMA_VERSION = 6

TIGER_UMG_ROUNDED_CARD_SCHEMA = "tigerstudio.umg.ui_material.v2"
TIGER_UMG_ROUNDED_CARD_GENERATOR = (
    "tiger_ui_rounded_card_sdf_custom_hlsl_v1"
)
TIGER_UMG_ROUNDED_CARD_DOCUMENT_SCHEMA_VERSION = 8
TIGER_UMG_MATERIAL_KINDS = {
    "LinearGradient",
    "RadialGradient",
    "RoundedCard",
}
TIGER_UMG_MATERIAL_LAYER_KINDS = {"Image", "Shape"}

_FILL_KINDS = {"Solid", "LinearGradient", "RadialGradient"}
_STROKE_ALIGNMENTS = {"Inside", "Center", "Outside"}
_EPSILON = 0.000001


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return result if math.isfinite(result) else float(default)


def _finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _point(value: object, fallback: tuple[float, float]) -> dict[str, float]:
    source = value if isinstance(value, Mapping) else {}
    return {
        "X": _number(source.get("X", source.get("x")), fallback[0]),
        "Y": _number(source.get("Y", source.get("y")), fallback[1]),
    }


def _size(value: object, fallback: tuple[float, float] = (100.0, 100.0)) -> dict[str, float]:
    if isinstance(value, Mapping):
        width = value.get("X", value.get("x", value.get("width")))
        height = value.get("Y", value.get("y", value.get("height")))
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        rows = list(value)
        width = rows[0] if rows else fallback[0]
        height = rows[1] if len(rows) > 1 else fallback[1]
    else:
        width, height = fallback
    return {
        "X": max(_EPSILON, _number(width, fallback[0])),
        "Y": max(_EPSILON, _number(height, fallback[1])),
    }


def _color(value: object, fallback: str = "#FFFFFFFF") -> str:
    text = str(value or fallback).strip()
    if not text.startswith("#"):
        return fallback
    digits = text[1:]
    if len(digits) == 3:
        digits = "".join(character * 2 for character in digits) + "FF"
    elif len(digits) == 4:
        digits = "".join(character * 2 for character in digits)
    elif len(digits) == 6:
        digits += "FF"
    if len(digits) != 8 or any(
        character not in "0123456789abcdefABCDEF" for character in digits
    ):
        return fallback
    return f"#{digits.upper()}"


def _valid_color(value: object) -> bool:
    text = str(value or "").strip()
    return (
        len(text) == 9
        and text.startswith("#")
        and all(character in "0123456789abcdefABCDEF" for character in text[1:])
    )


def _multiply_color_alpha(color: object, opacity: object) -> str:
    normalized = _color(color)
    alpha = round(
        int(normalized[7:9], 16)
        * max(0.0, min(1.0, _number(opacity, 1.0)))
    )
    return f"{normalized[:7]}{max(0, min(255, alpha)):02X}"


def _stop_rows(value: object) -> list[dict[str, Any]]:
    rows = value if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ) else []
    result: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            position = row.get("Position", row.get("position"))
            color = row.get("Color", row.get("color"))
        elif isinstance(row, Sequence) and not isinstance(
            row,
            (str, bytes, bytearray),
        ):
            values = list(row)
            position = values[0] if values else 0.0
            color = values[1] if len(values) > 1 else "#FFFFFFFF"
        else:
            continue
        result.append(
            {
                "Position": max(0.0, min(1.0, _number(position))),
                "Color": _color(color),
            }
        )
    result.sort(key=lambda item: item["Position"])
    if len(result) < 2:
        return [
            {"Position": 0.0, "Color": "#FFFFFFFF"},
            {"Position": 1.0, "Color": "#000000FF"},
        ]
    return result


def normalize_umg_gradient(value: object) -> dict[str, Any]:
    """Normalize Painter/Motion gradient data into the shared legacy v1 record."""
    source = value if isinstance(value, Mapping) else {}
    kind_value = str(
        source.get("Kind")
        or source.get("kind")
        or source.get("Type")
        or source.get("type")
        or "linear"
    ).strip().casefold()
    kind = "RadialGradient" if "radial" in kind_value else "LinearGradient"
    return {
        "Schema": TIGER_UMG_UI_MATERIAL_SCHEMA,
        "Generator": TIGER_UMG_CUSTOM_HLSL_GENERATOR,
        "Kind": kind,
        "CoordinateSpace": "LocalUV",
        "Start": _point(source.get("Start", source.get("start")), (0.0, 0.5)),
        "End": _point(source.get("End", source.get("end")), (1.0, 0.5)),
        "Width": _point(source.get("Width", source.get("width")), (0.0, 1.0)),
        "Stops": _stop_rows(source.get("Stops", source.get("stops"))),
        "Opacity": max(
            0.0,
            min(1.0, _number(source.get("Opacity", source.get("opacity")), 1.0)),
        ),
    }


def _visible_rows(value: object) -> list[Mapping[str, Any]]:
    rows = value if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ) else []
    return [
        row
        for row in rows
        if isinstance(row, Mapping) and bool(row.get("visible", True))
    ]


def _fill_kind(value: object) -> str:
    text = str(value or "Solid").strip().casefold()
    return {
        "solid": "Solid",
        "linear": "LinearGradient",
        "lineargradient": "LinearGradient",
        "radial": "RadialGradient",
        "radialgradient": "RadialGradient",
    }.get(text, "Solid")


def _stroke_alignment(value: object) -> str:
    text = str(value or "Center").strip().casefold()
    return {
        "inside": "Inside",
        "center": "Center",
        "outside": "Outside",
    }.get(text, "Center")


def _normalized_corner_radii(
    value: object,
    card_size: Mapping[str, float],
    fallback: object = 0.0,
) -> dict[str, float]:
    source = value if isinstance(value, Mapping) else {}
    fallback_radius = max(0.0, _number(fallback))
    values = [
        max(
            0.0,
            _number(
                source.get(primary, source.get(secondary)),
                fallback_radius,
            ),
        )
        for primary, secondary in (
            ("X", "top_left"),
            ("Y", "top_right"),
            ("Z", "bottom_right"),
            ("W", "bottom_left"),
        )
    ]
    width = max(_EPSILON, float(card_size["X"]))
    height = max(_EPSILON, float(card_size["Y"]))
    pair_limits = (
        (width, values[0] + values[1]),
        (width, values[3] + values[2]),
        (height, values[0] + values[3]),
        (height, values[1] + values[2]),
    )
    scale = min(
        [1.0]
        + [limit / total for limit, total in pair_limits if total > _EPSILON]
    )
    return {
        key: float(radius * min(1.0, max(0.0, scale)))
        for key, radius in zip(("X", "Y", "Z", "W"), values)
    }


def _normalize_stroke(value: object) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    return {
        "Width": max(0.0, _number(source.get("Width", source.get("width")))),
        "Alignment": _stroke_alignment(
            source.get("Alignment", source.get("alignment", source.get("align")))
        ),
        "Color": _multiply_color_alpha(
            source.get("Color", source.get("color", "#00000000")),
            source.get("Opacity", source.get("opacity", 1.0)),
        ),
    }


def _normalize_shadow(value: object, *, enabled: bool = False) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    offset = source.get("Offset", source.get("offset"))
    offset_source = offset if isinstance(offset, Mapping) else source
    return {
        "Enabled": bool(source.get("Enabled", source.get("enabled", enabled))),
        "Color": _color(
            source.get("Color", source.get("color")),
            "#00000040" if enabled else "#00000000",
        ),
        "Offset": {
            "X": _number(offset_source.get("X", offset_source.get("x"))),
            "Y": _number(offset_source.get("Y", offset_source.get("y"))),
        },
        "Blur": max(0.0, _number(source.get("Blur", source.get("blur")))),
        "Spread": _number(source.get("Spread", source.get("spread"))),
    }


def _visual_padding(
    stroke: Mapping[str, Any],
    drop_shadow: Mapping[str, Any],
) -> dict[str, float]:
    stroke_width = max(0.0, _number(stroke.get("Width")))
    alignment = str(stroke.get("Alignment") or "Center")
    outside_stroke = (
        stroke_width
        if alignment == "Outside"
        else stroke_width * 0.5 if alignment == "Center" else 0.0
    )
    if not bool(drop_shadow.get("Enabled")):
        extent = offset_x = offset_y = 0.0
    else:
        extent = max(
            0.0,
            _number(drop_shadow.get("Blur"))
            + _number(drop_shadow.get("Spread")),
        )
        offset = drop_shadow.get("Offset")
        offset = offset if isinstance(offset, Mapping) else {}
        offset_x = _number(offset.get("X"))
        offset_y = _number(offset.get("Y"))
    return {
        "Left": outside_stroke + max(0.0, extent - offset_x),
        "Top": outside_stroke + max(0.0, extent - offset_y),
        "Right": outside_stroke + max(0.0, extent + offset_x),
        "Bottom": outside_stroke + max(0.0, extent + offset_y),
    }


def _painter_fill(style: Mapping[str, Any]) -> tuple[str, str, dict[str, Any], float]:
    legacy_gradient = style.get("fill_gradient")
    paints = _visible_rows(style.get("fills"))
    paint = paints[0] if paints else {}
    paint_type = str(paint.get("type") or "solid").strip().casefold()
    opacity = max(0.0, min(1.0, _number(paint.get("opacity"), 1.0)))
    if paint_type in {"linear", "radial"}:
        nested = paint.get("gradient")
        gradient_source = dict(nested) if isinstance(nested, Mapping) else dict(paint)
        gradient_source["type"] = paint_type
        gradient_source["opacity"] = opacity
        gradient = normalize_umg_gradient(gradient_source)
        return gradient["Kind"], "#FFFFFFFF", gradient, opacity
    if isinstance(legacy_gradient, Mapping):
        gradient = normalize_umg_gradient(legacy_gradient)
        return gradient["Kind"], "#FFFFFFFF", gradient, gradient["Opacity"]
    fill_color = paint.get("color", style.get("fill", "#FFFFFFFF"))
    return "Solid", _color(fill_color), normalize_umg_gradient({}), opacity


def _painter_effects(style: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    effects = _visible_rows(style.get("effects"))
    drop = next(
        (
            row
            for row in effects
            if str(row.get("type") or "").strip().casefold() == "drop_shadow"
        ),
        None,
    )
    inner = next(
        (
            row
            for row in effects
            if str(row.get("type") or "").strip().casefold() == "inner_shadow"
        ),
        None,
    )
    if drop is None and isinstance(style.get("shadow"), Mapping):
        drop = style["shadow"]
    return (
        _normalize_shadow(drop, enabled=drop is not None),
        _normalize_shadow(inner, enabled=inner is not None),
    )


def normalize_umg_rounded_card(
    style: object,
    *,
    size: object | None = None,
) -> dict[str, Any]:
    """Normalize a Painter style or v2 record into a bounded RoundedCard."""
    source = style if isinstance(style, Mapping) else {}
    direct_record = (
        str(source.get("Schema") or "") == TIGER_UMG_ROUNDED_CARD_SCHEMA
        or str(source.get("Kind") or "") == "RoundedCard"
        or str(source.get("Generator") or "")
        == TIGER_UMG_ROUNDED_CARD_GENERATOR
    )
    card_size = _size(size if size is not None else source.get("Size"))
    if direct_record:
        fill_kind = _fill_kind(source.get("FillKind"))
        fill_color = _color(source.get("FillColor"))
        gradient = normalize_umg_gradient(
            {
                "Kind": fill_kind,
                "Start": source.get("Start"),
                "End": source.get("End"),
                "Width": source.get("Width"),
                "Stops": source.get("Stops"),
                "Opacity": source.get("Opacity"),
            }
        )
        opacity = max(0.0, min(1.0, _number(source.get("Opacity"), 1.0)))
        radii_source = source.get("CornerRadii")
        radius_fallback = 0.0
        smoothing = source.get("CornerSmoothing")
        stroke = _normalize_stroke(source.get("Stroke"))
        drop_shadow = _normalize_shadow(source.get("DropShadow"))
        inner_shadow = _normalize_shadow(source.get("InnerShadow"))
    else:
        fill_kind, fill_color, gradient, opacity = _painter_fill(source)
        radii_source = source.get("corner_radii")
        radius_fallback = source.get("radius")
        smoothing = source.get("corner_smoothing")
        visible_strokes = _visible_rows(source.get("strokes"))
        if visible_strokes:
            stroke = _normalize_stroke(visible_strokes[0])
        else:
            stroke = _normalize_stroke(
                {
                    "width": source.get("stroke_width"),
                    "align": source.get("stroke_align"),
                    "color": source.get("stroke"),
                }
            )
        drop_shadow, inner_shadow = _painter_effects(source)
    corner_radii = _normalized_corner_radii(
        radii_source,
        card_size,
        radius_fallback,
    )
    record = {
        "Schema": TIGER_UMG_ROUNDED_CARD_SCHEMA,
        "Generator": TIGER_UMG_ROUNDED_CARD_GENERATOR,
        "Kind": "RoundedCard",
        "CoordinateSpace": "LocalUV",
        "Size": card_size,
        "FillKind": fill_kind,
        "FillColor": fill_color,
        "Start": dict(gradient["Start"]),
        "End": dict(gradient["End"]),
        "Width": dict(gradient["Width"]),
        "Stops": list(gradient["Stops"]),
        "Opacity": opacity,
        "CornerRadii": corner_radii,
        "CornerSmoothing": max(0.0, min(1.0, _number(smoothing))),
        "Stroke": stroke,
        "DropShadow": drop_shadow,
        "InnerShadow": inner_shadow,
    }
    record["VisualPadding"] = _visual_padding(stroke, drop_shadow)
    return record


def _style_has_rounded_card_features(style: Mapping[str, Any]) -> bool:
    radius = max(0.0, _number(style.get("radius")))
    radii = style.get("corner_radii")
    radii = radii if isinstance(radii, Mapping) else {}
    has_radii = radius > _EPSILON or any(
        max(0.0, _number(value)) > _EPSILON for value in radii.values()
    )
    has_smoothing = _number(style.get("corner_smoothing")) > _EPSILON
    strokes = _visible_rows(style.get("strokes"))
    has_stroke = any(_number(row.get("width"), 1.0) > _EPSILON for row in strokes)
    has_stroke = has_stroke or (
        _number(style.get("stroke_width")) > _EPSILON
        and _color(style.get("stroke"), "#00000000")[7:9] != "00"
    )
    has_effect = bool(_visible_rows(style.get("effects"))) or isinstance(
        style.get("shadow"),
        Mapping,
    )
    return has_radii or has_smoothing or has_stroke or has_effect


def painter_style_umg_material(
    style: Mapping[str, Any] | None,
    *,
    source_kind: str,
    size: object | None = None,
) -> dict[str, Any] | None:
    """Return the supported v1/v2 material for a leaf Painter rectangle."""
    if str(source_kind or "").strip().casefold() != "rectangle":
        return None
    source = dict(style or {})
    legacy_gradient = source.get("fill_gradient")
    paints = _visible_rows(source.get("fills"))
    paint_type = (
        str(paints[0].get("type") or "solid").strip().casefold()
        if paints
        else "solid"
    )
    has_gradient = isinstance(legacy_gradient, Mapping) or paint_type in {
        "linear",
        "radial",
    }
    if paint_type not in {"solid", "linear", "radial"} and not isinstance(
        legacy_gradient,
        Mapping,
    ):
        return None
    if not _style_has_rounded_card_features(source):
        if not has_gradient:
            return None
        if paint_type in {"linear", "radial"}:
            paint = paints[0]
            nested = paint.get("gradient")
            gradient_source = (
                dict(nested) if isinstance(nested, Mapping) else dict(paint)
            )
            gradient_source["type"] = paint_type
            gradient_source["opacity"] = paint.get("opacity", 1.0)
            return normalize_umg_gradient(gradient_source)
        if isinstance(legacy_gradient, Mapping):
            return normalize_umg_gradient(legacy_gradient)
    return normalize_umg_rounded_card(source, size=size)


def painter_style_gradient_material(
    style: Mapping[str, Any] | None,
    *,
    source_kind: str,
    size: object | None = None,
) -> dict[str, Any] | None:
    """Backward-compatible name for the Painter UI material classifier."""
    return painter_style_umg_material(
        style,
        source_kind=source_kind,
        size=size,
    )


def motion_shape_gradient_material(
    params: Mapping[str, Any] | None,
    *,
    layer_type: str,
) -> dict[str, Any] | None:
    """Return a legacy material record for Motion's plain rectangle gradient."""
    if str(layer_type or "").strip().casefold() != "shape":
        return None
    source = dict(params or {})
    primitive = str(
        source.get("shape") or source.get("primitive") or "rectangle"
    ).strip().casefold()
    gradient = source.get("gradient")
    if primitive != "rectangle" or not isinstance(gradient, (Mapping, list)):
        return None
    if isinstance(gradient, list):
        gradient = {"type": "linear", "stops": gradient}
    return normalize_umg_gradient(gradient)


def _gradient_validation_reasons(source: Mapping[str, Any]) -> list[str]:
    stops = source.get("Stops")
    if not isinstance(stops, list) or len(stops) < 2:
        return ["ui_material_gradient_requires_two_stops"]
    if len(stops) > 16:
        return ["ui_material_gradient_stop_limit_exceeded"]
    if any(
        not isinstance(row, Mapping)
        or not _finite_number(row.get("Position"))
        or not 0.0 <= float(row["Position"]) <= 1.0
        or not _valid_color(row.get("Color"))
        for row in stops
    ):
        return ["ui_material_gradient_stop_invalid"]
    if any(
        float(stops[index]["Position"])
        < float(stops[index - 1]["Position"])
        for index in range(1, len(stops))
    ):
        return ["ui_material_gradient_stops_not_sorted"]
    return []


def _rounded_card_validation_reasons(source: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    size = source.get("Size")
    if (
        not isinstance(size, Mapping)
        or not _finite_number(size.get("X"))
        or not _finite_number(size.get("Y"))
        or float(size.get("X", 0.0)) <= 0.0
        or float(size.get("Y", 0.0)) <= 0.0
    ):
        reasons.append("ui_material_rounded_card_size_invalid")
        width = height = 0.0
    else:
        width = float(size["X"])
        height = float(size["Y"])
    if str(source.get("FillKind") or "") not in _FILL_KINDS:
        reasons.append("ui_material_rounded_card_fill_kind_unsupported")
    if not _valid_color(source.get("FillColor")):
        reasons.append("ui_material_rounded_card_fill_color_invalid")
    if not _finite_number(source.get("Opacity")) or not 0.0 <= _number(
        source.get("Opacity"),
        -1.0,
    ) <= 1.0:
        reasons.append("ui_material_rounded_card_opacity_invalid")
    if any(
        not isinstance(source.get(key), Mapping)
        or not _finite_number(source[key].get("X"))
        or not _finite_number(source[key].get("Y"))
        for key in ("Start", "End", "Width")
    ):
        reasons.append("ui_material_gradient_geometry_invalid")
    reasons.extend(_gradient_validation_reasons(source))

    radii = source.get("CornerRadii")
    if not isinstance(radii, Mapping) or any(
        not _finite_number(radii.get(key)) or _number(radii.get(key), -1.0) < 0.0
        for key in ("X", "Y", "Z", "W")
    ):
        reasons.append("ui_material_rounded_card_radii_invalid")
    elif width > 0.0 and height > 0.0:
        tl, tr, br, bl = (float(radii[key]) for key in ("X", "Y", "Z", "W"))
        if (
            tl + tr > width + _EPSILON
            or bl + br > width + _EPSILON
            or tl + bl > height + _EPSILON
            or tr + br > height + _EPSILON
        ):
            reasons.append("ui_material_rounded_card_radii_exceed_size")
    if not _finite_number(source.get("CornerSmoothing")) or not 0.0 <= _number(
        source.get("CornerSmoothing"),
        -1.0,
    ) <= 1.0:
        reasons.append("ui_material_rounded_card_smoothing_invalid")

    stroke = source.get("Stroke")
    if (
        not isinstance(stroke, Mapping)
        or not _finite_number(stroke.get("Width"))
        or _number(stroke.get("Width"), -1.0) < 0.0
        or str(stroke.get("Alignment") or "") not in _STROKE_ALIGNMENTS
        or not _valid_color(stroke.get("Color"))
    ):
        reasons.append("ui_material_rounded_card_stroke_invalid")

    for key, label in (
        ("DropShadow", "drop_shadow"),
        ("InnerShadow", "inner_shadow"),
    ):
        shadow = source.get(key)
        offset = shadow.get("Offset") if isinstance(shadow, Mapping) else None
        if (
            not isinstance(shadow, Mapping)
            or not isinstance(shadow.get("Enabled"), bool)
            or not _valid_color(shadow.get("Color"))
            or not isinstance(offset, Mapping)
            or not _finite_number(offset.get("X"))
            or not _finite_number(offset.get("Y"))
            or not _finite_number(shadow.get("Blur"))
            or _number(shadow.get("Blur"), -1.0) < 0.0
            or not _finite_number(shadow.get("Spread"))
        ):
            reasons.append(f"ui_material_rounded_card_{label}_invalid")

    padding = source.get("VisualPadding")
    padding_valid = isinstance(padding, Mapping) and all(
        _finite_number(padding.get(key)) and _number(padding.get(key), -1.0) >= 0.0
        for key in ("Left", "Top", "Right", "Bottom")
    )
    if not padding_valid:
        reasons.append("ui_material_visual_padding_invalid")
    elif isinstance(stroke, Mapping) and isinstance(source.get("DropShadow"), Mapping):
        expected = _visual_padding(stroke, source["DropShadow"])
        if any(
            abs(float(padding[key]) - expected[key]) > 0.0001
            for key in ("Left", "Top", "Right", "Bottom")
        ):
            reasons.append("ui_material_visual_padding_invalid")
    return reasons


def _is_rounded_card(value: Mapping[str, Any]) -> bool:
    return (
        str(value.get("Schema") or "") == TIGER_UMG_ROUNDED_CARD_SCHEMA
        or str(value.get("Generator") or "") == TIGER_UMG_ROUNDED_CARD_GENERATOR
        or str(value.get("Kind") or "") == "RoundedCard"
    )


def validate_umg_material_record(
    value: object,
    *,
    layer_kind: str = "",
    document_schema_version: int | None = None,
) -> list[str]:
    source = value if isinstance(value, Mapping) else {}
    rounded_card = _is_rounded_card(source)
    if document_schema_version is not None:
        try:
            schema_version = int(document_schema_version)
        except (TypeError, ValueError):
            schema_version = 0
        required = (
            TIGER_UMG_ROUNDED_CARD_DOCUMENT_SCHEMA_VERSION
            if rounded_card
            else TIGER_UMG_UI_MATERIAL_DOCUMENT_SCHEMA_VERSION
        )
        if schema_version < required:
            return [f"ui_material_requires_schema_{required}"]
    reasons: list[str] = []
    expected_schema = (
        TIGER_UMG_ROUNDED_CARD_SCHEMA
        if rounded_card
        else TIGER_UMG_UI_MATERIAL_SCHEMA
    )
    expected_generator = (
        TIGER_UMG_ROUNDED_CARD_GENERATOR
        if rounded_card
        else TIGER_UMG_CUSTOM_HLSL_GENERATOR
    )
    expected_kinds = {"RoundedCard"} if rounded_card else {
        "LinearGradient",
        "RadialGradient",
    }
    if str(source.get("Schema") or "") != expected_schema:
        reasons.append("ui_material_schema_unsupported")
    if str(source.get("Generator") or "") != expected_generator:
        reasons.append("ui_material_generator_unsupported")
    if str(source.get("Kind") or "") not in expected_kinds:
        reasons.append("ui_material_kind_unsupported")
    if str(source.get("CoordinateSpace") or "") != "LocalUV":
        reasons.append("ui_material_coordinate_space_unsupported")
    if layer_kind and str(layer_kind) not in TIGER_UMG_MATERIAL_LAYER_KINDS:
        reasons.append("ui_material_layer_kind_unsupported")
    reasons.extend(
        _rounded_card_validation_reasons(source)
        if rounded_card
        else _gradient_validation_reasons(source)
    )
    return reasons


def umg_material_graph(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return the fixed, inspectable graph for either supported generator."""
    source = value if isinstance(value, Mapping) else {}
    rounded_card = _is_rounded_card(source)
    material = (
        normalize_umg_rounded_card(source)
        if rounded_card
        else normalize_umg_gradient(source)
    )
    if rounded_card:
        nodes = [
            {
                "id": "geometry_uv",
                "type": "TextureCoordinate",
                "label": "Local UV + Card Size",
                "position": [0.0, 40.0],
            },
            {
                "id": "fill",
                "type": "Fill",
                "label": material["FillKind"],
                "position": [0.0, 190.0],
            },
            {
                "id": "corners_border",
                "type": "RoundedCardSDF",
                "label": "Corners + Smoothing + Stroke",
                "position": [250.0, 20.0],
            },
            {
                "id": "shadows",
                "type": "Shadows",
                "label": "Drop + Inner Shadow",
                "position": [250.0, 220.0],
            },
            {
                "id": "custom_hlsl",
                "type": "CustomHLSL",
                "label": "RoundedCard",
                "position": [510.0, 105.0],
            },
            {
                "id": "output",
                "type": "UIOutput",
                "label": "Final Color / Opacity",
                "position": [790.0, 105.0],
            },
        ]
        connections = [
            {"from": "geometry_uv", "to": "corners_border", "port": "UV / Size"},
            {"from": "fill", "to": "custom_hlsl", "port": "Fill"},
            {"from": "corners_border", "to": "custom_hlsl", "port": "SDF / Stroke"},
            {"from": "shadows", "to": "custom_hlsl", "port": "Shadows"},
            {"from": "custom_hlsl", "to": "output", "port": "Final Color / Opacity"},
        ]
        return {
            "schema": "tigerstudio.umg.ui_material_graph.v2",
            "material": material,
            "nodes": nodes,
            "connections": connections,
        }
    stop_count = len(material["Stops"])
    nodes = [
        {
            "id": "uv",
            "type": "TextureCoordinate",
            "label": "Texture Coordinate",
            "position": [0.0, 40.0],
        },
        {
            "id": "parameters",
            "type": "Parameters",
            "label": f"Gradient Parameters / {stop_count} stops",
            "position": [0.0, 190.0],
        },
        {
            "id": "custom_hlsl",
            "type": "CustomHLSL",
            "label": material["Kind"],
            "position": [280.0, 95.0],
        },
        {
            "id": "output",
            "type": "UIOutput",
            "label": "Final Color / Opacity",
            "position": [570.0, 95.0],
        },
    ]
    return {
        "schema": "tigerstudio.umg.ui_material_graph.v1",
        "material": material,
        "nodes": nodes,
        "connections": [
            {"from": "uv", "to": "custom_hlsl", "port": "UV"},
            {"from": "parameters", "to": "custom_hlsl", "port": "Parameters"},
            {
                "from": "custom_hlsl",
                "to": "output",
                "port": "Final Color / Opacity",
            },
        ],
    }


def _gradient_result_lines(material: Mapping[str, Any], result: str) -> list[str]:
    if material["Kind"] == "RadialGradient":
        coordinate = [
            "float Radius = max(length(End.xy - Start.xy), 0.000001);",
            "float T = saturate(length(UV - Start.xy) / Radius);",
        ]
    else:
        coordinate = [
            "float2 Axis = End.xy - Start.xy;",
            "float Denominator = max(dot(Axis, Axis), 0.000001);",
            "float T = saturate(dot(UV - Start.xy, Axis) / Denominator);",
        ]
    stops = list(material["Stops"])
    lines = [*coordinate, f"float4 {result} = Color0;"]
    lines.append(f"if (T <= {stops[0]['Position']:.9g}) {result} = Color0;")
    for index in range(1, len(stops)):
        previous = stops[index - 1]["Position"]
        position = stops[index]["Position"]
        span = max(_EPSILON, float(position) - float(previous))
        lines.append(
            "else if (T <= {position:.9g}) {result} = lerp(Color{before}, Color{after}, "
            "saturate((T - {previous:.9g}) / {span:.9g}));".format(
                position=position,
                result=result,
                before=index - 1,
                after=index,
                previous=previous,
                span=span,
            )
        )
    lines.append(f"else {result} = Color{len(stops) - 1};")
    return lines


def gradient_custom_hlsl(value: Mapping[str, Any]) -> str:
    """Generate the fixed legacy gradient code mirrored by the UE plugin."""
    material = normalize_umg_gradient(value)
    lines = _gradient_result_lines(material, "Result")
    lines.append("Result.a *= saturate(FillOpacity);")
    lines.append("return Result;")
    return "\n".join(lines)


def _rounded_distance_hlsl(prefix: str, point_expression: str) -> list[str]:
    return [
        f"float2 {prefix}P = {point_expression};",
        f"float {prefix}Radius = ({prefix}P.x < 0.0) ? (({prefix}P.y < 0.0) ? CornerRadii.x : CornerRadii.w) : (({prefix}P.y < 0.0) ? CornerRadii.y : CornerRadii.z);",
        f"float2 {prefix}Q = abs({prefix}P) - max(CardSize.xy * 0.5 - float2({prefix}Radius, {prefix}Radius), float2(0.0, 0.0));",
        f"float2 {prefix}Outside = max({prefix}Q, 0.0);",
        f"float {prefix}Power = lerp(2.0, 4.0, saturate(CornerSmoothing));",
        f"float {prefix}Curve = pow(pow({prefix}Outside.x, {prefix}Power) + pow({prefix}Outside.y, {prefix}Power), 1.0 / {prefix}Power);",
        f"float {prefix}Distance = {prefix}Curve + min(max({prefix}Q.x, {prefix}Q.y), 0.0) - {prefix}Radius;",
    ]


def rounded_card_custom_hlsl(value: Mapping[str, Any]) -> str:
    """Generate the fixed RoundedCard SDF program mirrored by the UE plugin."""
    material = normalize_umg_rounded_card(value)
    lines = [
        "// Tiger Rounded Card SDF / validated Custom HLSL",
        "float2 SurfaceSize = max(CardSize.xy + float2(VisualPadding.x + VisualPadding.z, VisualPadding.y + VisualPadding.w), float2(1.0, 1.0));",
        "float2 PixelPosition = UV * SurfaceSize - VisualPadding.xy;",
        "float2 CardUV = saturate(PixelPosition / max(CardSize.xy, float2(0.000001, 0.000001)));",
        "float2 CardPoint = PixelPosition - CardSize.xy * 0.5;",
        *_rounded_distance_hlsl("Base", "CardPoint"),
        *_rounded_distance_hlsl("Drop", "CardPoint - DropShadowOffset.xy"),
        *_rounded_distance_hlsl("Inner", "CardPoint - InnerShadowOffset.xy"),
    ]
    if material["FillKind"] == "RadialGradient":
        lines.extend(
            [
                "float2 GradientBasisX = GradientEnd.xy - GradientStart.xy;",
                "float2 GradientBasisY = GradientWidth.xy - GradientStart.xy;",
                "float GradientDeterminant = GradientBasisX.x * GradientBasisY.y - GradientBasisX.y * GradientBasisY.x;",
                "float SafeGradientDeterminant = (abs(GradientDeterminant) < 0.000001) ? ((GradientDeterminant < 0.0) ? -0.000001 : 0.000001) : GradientDeterminant;",
                "float2 GradientDelta = CardUV - GradientStart.xy;",
                "float2 GradientLocal = float2((GradientDelta.x * GradientBasisY.y - GradientDelta.y * GradientBasisY.x) / SafeGradientDeterminant, (GradientBasisX.x * GradientDelta.y - GradientBasisX.y * GradientDelta.x) / SafeGradientDeterminant);",
                "float GradientT = saturate(length(GradientLocal));",
            ]
        )
    elif material["FillKind"] == "LinearGradient":
        lines.extend(
            [
                "float2 GradientAxis = GradientEnd.xy - GradientStart.xy;",
                "float GradientDenominator = max(dot(GradientAxis, GradientAxis), 0.000001);",
                "float GradientT = saturate(dot(CardUV - GradientStart.xy, GradientAxis) / GradientDenominator);",
            ]
        )
    if material["FillKind"] == "Solid":
        lines.append("float4 Fill = FillColor;")
    else:
        stops = list(material["Stops"])
        lines.append("float4 Fill = Color0;")
        lines.append(f"if (GradientT <= {stops[0]['Position']:.9g}) Fill = Color0;")
        for index in range(1, len(stops)):
            previous = float(stops[index - 1]["Position"])
            position = float(stops[index]["Position"])
            span = max(_EPSILON, position - previous)
            lines.append(
                "else if (GradientT <= {position:.9g}) Fill = lerp(Color{before}, Color{after}, saturate((GradientT - {previous:.9g}) / {span:.9g}));".format(
                    position=position,
                    before=index - 1,
                    after=index,
                    previous=previous,
                    span=span,
                )
            )
        lines.append(f"else Fill = Color{len(stops) - 1};")
    lines.extend(
        [
            "float BaseAA = max(fwidth(BaseDistance), 0.75);",
            "float ShapeMask = 1.0 - smoothstep(-BaseAA, BaseAA, BaseDistance);",
            "float Alignment = clamp(StrokeAlignment, 0.0, 2.0);",
            "float OuterOffset = (Alignment < 0.5) ? 0.0 : ((Alignment < 1.5) ? StrokeWidth * 0.5 : StrokeWidth);",
            "float InnerOffset = (Alignment < 0.5) ? StrokeWidth : ((Alignment < 1.5) ? StrokeWidth * 0.5 : 0.0);",
            "float StrokeOuter = 1.0 - smoothstep(-BaseAA, BaseAA, BaseDistance - OuterOffset);",
            "float StrokeInner = 1.0 - smoothstep(-BaseAA, BaseAA, BaseDistance + InnerOffset);",
            "float StrokeMask = saturate(StrokeOuter - StrokeInner) * step(0.0001, StrokeWidth);",
            "Fill.a *= saturate(FillOpacity) * ShapeMask;",
            "float3 BasePremultiplied = Fill.rgb * Fill.a;",
            "float BaseAlpha = Fill.a;",
            "float StrokeAlpha = StrokeColor.a * StrokeMask;",
            "BasePremultiplied = StrokeColor.rgb * StrokeAlpha + BasePremultiplied * (1.0 - StrokeAlpha);",
            "BaseAlpha = StrokeAlpha + BaseAlpha * (1.0 - StrokeAlpha);",
            "float DropAA = max(fwidth(DropDistance), 0.75);",
            "float DropSoftness = max(DropShadowBlur, DropAA);",
            "float DropMask = (1.0 - smoothstep(-DropSoftness, DropSoftness, DropDistance - DropShadowSpread)) * saturate(DropShadowEnabled);",
            "float DropAlpha = DropShadowColor.a * DropMask;",
            "float3 AccumulatedRGB = DropShadowColor.rgb * DropAlpha;",
            "float AccumulatedAlpha = DropAlpha;",
            "AccumulatedRGB = BasePremultiplied + AccumulatedRGB * (1.0 - BaseAlpha);",
            "AccumulatedAlpha = BaseAlpha + AccumulatedAlpha * (1.0 - BaseAlpha);",
            "float InnerAA = max(fwidth(InnerDistance), 0.75);",
            "float InnerSoftness = max(InnerShadowBlur, InnerAA);",
            "float InnerMask = smoothstep(-InnerSoftness, InnerSoftness, InnerDistance + InnerShadowSpread) * ShapeMask * saturate(InnerShadowEnabled);",
            "float InnerAlpha = InnerShadowColor.a * InnerMask;",
            "AccumulatedRGB = InnerShadowColor.rgb * InnerAlpha + AccumulatedRGB * (1.0 - InnerAlpha);",
            "AccumulatedAlpha = InnerAlpha + AccumulatedAlpha * (1.0 - InnerAlpha);",
            "float3 ResultRGB = (AccumulatedAlpha > 0.00001) ? (AccumulatedRGB / AccumulatedAlpha) : float3(0.0, 0.0, 0.0);",
            "return float4(ResultRGB, saturate(AccumulatedAlpha));",
        ]
    )
    return "\n".join(lines)


def material_custom_hlsl(value: Mapping[str, Any]) -> str:
    """Dispatch to the fixed generator selected by the material contract."""
    return (
        rounded_card_custom_hlsl(value)
        if _is_rounded_card(value)
        else gradient_custom_hlsl(value)
    )


umg_material_custom_hlsl = material_custom_hlsl


def _preview_gradient(material: Mapping[str, Any]) -> dict[str, Any]:
    opacity = float(material["Opacity"])
    return {
        "type": "radial" if material["FillKind"] == "RadialGradient" else "linear",
        "start": {"x": material["Start"]["X"], "y": material["Start"]["Y"]},
        "end": {"x": material["End"]["X"], "y": material["End"]["Y"]},
        "width": {"x": material["Width"]["X"], "y": material["Width"]["Y"]},
        "stops": [
            {
                "position": row["Position"],
                "color": _multiply_color_alpha(row["Color"], opacity),
            }
            for row in material["Stops"]
        ],
    }


def umg_material_preview_style(value: Mapping[str, Any]) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    if not _is_rounded_card(source):
        material = normalize_umg_gradient(source)
        gradient = _preview_gradient({**material, "FillKind": material["Kind"]})
        return {
            "fill": "#FFFFFFFF",
            "fill_gradient": gradient,
            "fills": [
                {
                    "type": gradient["type"],
                    "visible": True,
                    "opacity": 1.0,
                    "color": "#FFFFFFFF",
                    "blend_mode": "normal",
                    "gradient": gradient,
                }
            ],
        }

    material = normalize_umg_rounded_card(source)
    radii = material["CornerRadii"]
    corner_radii = {
        "top_left": radii["X"],
        "top_right": radii["Y"],
        "bottom_right": radii["Z"],
        "bottom_left": radii["W"],
    }
    fill_color = _multiply_color_alpha(material["FillColor"], material["Opacity"])
    if material["FillKind"] == "Solid":
        fill_row: dict[str, Any] = {
            "type": "solid",
            "visible": True,
            "opacity": 1.0,
            "color": fill_color,
            "blend_mode": "normal",
        }
        gradient = None
    else:
        gradient = _preview_gradient(material)
        fill_row = {
            "type": gradient["type"],
            "visible": True,
            "opacity": 1.0,
            "color": "#FFFFFFFF",
            "blend_mode": "normal",
            "gradient": gradient,
        }
    stroke = material["Stroke"]
    stroke_row = {
        "type": "solid",
        "visible": stroke["Width"] > _EPSILON,
        "opacity": 1.0,
        "color": stroke["Color"],
        "blend_mode": "normal",
        "width": stroke["Width"],
        "align": stroke["Alignment"].casefold(),
    }
    effects: list[dict[str, Any]] = []
    for key, effect_type in (
        ("DropShadow", "drop_shadow"),
        ("InnerShadow", "inner_shadow"),
    ):
        shadow = material[key]
        if shadow["Enabled"]:
            effects.append(
                {
                    "type": effect_type,
                    "color": shadow["Color"],
                    "x": shadow["Offset"]["X"],
                    "y": shadow["Offset"]["Y"],
                    "blur": shadow["Blur"],
                    "spread": shadow["Spread"],
                    "blend_mode": "normal",
                }
            )
    result: dict[str, Any] = {
        "fill": fill_color,
        "fills": [fill_row],
        "radius": radii["X"],
        "corner_radii": corner_radii,
        "corner_smoothing": material["CornerSmoothing"],
        "stroke": stroke["Color"],
        "stroke_width": stroke["Width"],
        "stroke_align": stroke["Alignment"].casefold(),
        "strokes": [stroke_row] if stroke["Width"] > _EPSILON else [],
        "effects": effects,
        "material_size": dict(material["Size"]),
        "visual_padding": {
            key.casefold(): value
            for key, value in material["VisualPadding"].items()
        },
    }
    if gradient is not None:
        result["fill_gradient"] = gradient
    drop = next((row for row in effects if row["type"] == "drop_shadow"), None)
    if drop is not None:
        result["shadow"] = {
            key: value
            for key, value in drop.items()
            if key not in {"type", "blend_mode"}
        }
    return result


__all__ = [
    "TIGER_UMG_CUSTOM_HLSL_GENERATOR",
    "TIGER_UMG_MATERIAL_KINDS",
    "TIGER_UMG_ROUNDED_CARD_DOCUMENT_SCHEMA_VERSION",
    "TIGER_UMG_ROUNDED_CARD_GENERATOR",
    "TIGER_UMG_ROUNDED_CARD_SCHEMA",
    "TIGER_UMG_UI_MATERIAL_DOCUMENT_SCHEMA_VERSION",
    "TIGER_UMG_UI_MATERIAL_SCHEMA",
    "gradient_custom_hlsl",
    "material_custom_hlsl",
    "motion_shape_gradient_material",
    "normalize_umg_gradient",
    "normalize_umg_rounded_card",
    "painter_style_gradient_material",
    "painter_style_umg_material",
    "rounded_card_custom_hlsl",
    "umg_material_custom_hlsl",
    "umg_material_graph",
    "umg_material_preview_style",
    "validate_umg_material_record",
]

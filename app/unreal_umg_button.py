"""Provider-neutral native button-style records for Tiger Studio UMG.

Schema 16 gives ``UButton`` the same authored visual states in every Tiger
provider.  Providers supply one normal style; the remaining states are
derived here so Painter, Motion Designer, the local simulator, and Unreal do
not each invent subtly different hover/press colours.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import math
from typing import Any, Mapping, Sequence


TIGER_UMG_BUTTON_STYLE_DOCUMENT_SCHEMA_VERSION = 16
TIGER_UMG_BUTTON_STYLE_SCHEMA = "tigerstudio.umg.button_style.v1"
UMG_BUTTON_STYLE_STATES = ("Normal", "Hovered", "Pressed", "Disabled")
_STATE_FIELDS = frozenset(
    {
        "Fill",
        "Stroke",
        "StrokeWidth",
        "CornerRadii",
        "TextColor",
        "FontSize",
        "FontWeight",
        "Opacity",
    }
)
_RECORD_FIELDS = frozenset({"Schema", "Enabled", *UMG_BUTTON_STYLE_STATES})
_RADII_FIELDS = frozenset({"X", "Y", "Z", "W"})


@dataclass(slots=True)
class UMGButtonStyleConversion:
    """One provider conversion before it is attached to a UMG layer."""

    record: dict[str, Any]
    block_reasons: list[str]


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return result if math.isfinite(result) else float(default)


def _hex_channel(value: float) -> str:
    return f"{max(0, min(255, int(round(value)))):02X}"


def _color_hex(value: object, default: str = "#FFFFFFFF") -> str:
    if isinstance(value, str):
        source = value.strip().removeprefix("#")
        if len(source) in {3, 4} and all(
            character in "0123456789abcdefABCDEF" for character in source
        ):
            source = "".join(character * 2 for character in source)
        if len(source) == 6 and all(
            character in "0123456789abcdefABCDEF" for character in source
        ):
            return f"#{source.upper()}FF"
        if len(source) == 8 and all(
            character in "0123456789abcdefABCDEF" for character in source
        ):
            return f"#{source.upper()}"
        return default
    if isinstance(value, Mapping):
        channels = [
            value.get(key, fallback)
            for key, fallback in (
                ("r", 1.0),
                ("g", 1.0),
                ("b", 1.0),
                ("a", 1.0),
            )
        ]
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        channels = list(value)[:4]
        channels.extend([1.0] * (4 - len(channels)))
    else:
        return default
    values = [_number(channel, 1.0) for channel in channels]
    scale = 255.0 if max(values, default=1.0) <= 1.0 else 1.0
    return "#" + "".join(_hex_channel(channel * scale) for channel in values)


def _valid_color(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 9
        and value.startswith("#")
        and all(
            character in "0123456789abcdefABCDEF" for character in value[1:]
        )
    )


def _color_channels(value: object) -> tuple[int, int, int, int]:
    source = _color_hex(value)[1:]
    return tuple(int(source[index : index + 2], 16) for index in range(0, 8, 2))  # type: ignore[return-value]


def _multiply_alpha(value: object, opacity: object) -> str:
    red, green, blue, alpha = _color_channels(value)
    bounded = max(0.0, min(1.0, _number(opacity, 1.0)))
    return "#" + "".join(
        _hex_channel(channel)
        for channel in (red, green, blue, alpha * bounded)
    )


def _mix_color(value: object, target: tuple[int, int, int], amount: float) -> str:
    red, green, blue, alpha = _color_channels(value)
    bounded = max(0.0, min(1.0, float(amount)))
    mixed = (
        red + (target[0] - red) * bounded,
        green + (target[1] - green) * bounded,
        blue + (target[2] - blue) * bounded,
        alpha,
    )
    return "#" + "".join(_hex_channel(channel) for channel in mixed)


def _corner_radii(value: object, fallback: object = 0.0) -> dict[str, float]:
    source = value if isinstance(value, Mapping) else {}
    fallback_value = max(0.0, _number(fallback, 0.0))
    aliases = (
        ("X", "top_left"),
        ("Y", "top_right"),
        ("Z", "bottom_right"),
        ("W", "bottom_left"),
    )
    return {
        target: max(
            0.0,
            _number(source.get(target, source.get(provider)), fallback_value),
        )
        for target, provider in aliases
    }


def _state_record(
    *,
    fill: object,
    stroke: object,
    stroke_width: object,
    corner_radii: object,
    text_color: object,
    font_size: object,
    font_weight: object,
    opacity: object,
) -> dict[str, Any]:
    return {
        "Fill": _color_hex(fill, "#4A4A4AFF"),
        "Stroke": _color_hex(stroke, "#777777FF"),
        "StrokeWidth": max(0.0, _number(stroke_width, 0.0)),
        "CornerRadii": _corner_radii(corner_radii),
        "TextColor": _color_hex(text_color, "#FFFFFFFF"),
        "FontSize": max(1.0, _number(font_size, 16.0)),
        "FontWeight": max(100, min(900, int(round(_number(font_weight, 400.0))))),
        "Opacity": max(0.0, min(1.0, _number(opacity, 1.0))),
    }


def make_umg_button_style(
    *,
    fill: object = "#4A4A4AFF",
    stroke: object = "#777777FF",
    stroke_width: object = 1.0,
    corner_radii: object = None,
    radius: object = 2.0,
    text_color: object = "#FFFFFFFF",
    font_size: object = 16.0,
    font_weight: object = 400,
    opacity: object = 1.0,
    enabled: bool = True,
) -> dict[str, Any]:
    """Build the canonical four-state record from one authored normal state.

    Hover brightens paint by 8%, press darkens it by 12%, and disabled keeps
    the authored paints while multiplying state opacity by 0.45.  These fixed
    transforms are intentionally small and deterministic.
    """

    radii = _corner_radii(corner_radii, radius)
    normal = _state_record(
        fill=fill,
        stroke=stroke,
        stroke_width=stroke_width,
        corner_radii=radii,
        text_color=text_color,
        font_size=font_size,
        font_weight=font_weight,
        opacity=opacity,
    )
    hovered = copy.deepcopy(normal)
    hovered["Fill"] = _mix_color(normal["Fill"], (255, 255, 255), 0.08)
    hovered["Stroke"] = _mix_color(normal["Stroke"], (255, 255, 255), 0.08)
    pressed = copy.deepcopy(normal)
    pressed["Fill"] = _mix_color(normal["Fill"], (0, 0, 0), 0.12)
    pressed["Stroke"] = _mix_color(normal["Stroke"], (0, 0, 0), 0.12)
    disabled = copy.deepcopy(normal)
    disabled["Opacity"] = max(0.0, min(1.0, float(normal["Opacity"]) * 0.45))
    return {
        "Schema": TIGER_UMG_BUTTON_STYLE_SCHEMA,
        "Enabled": bool(enabled),
        "Normal": normal,
        "Hovered": hovered,
        "Pressed": pressed,
        "Disabled": disabled,
    }


def _visible_paints(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        row
        for row in value
        if isinstance(row, Mapping) and bool(row.get("visible", True))
    ]


def painter_button_style_conversion(
    row: Mapping[str, Any],
    style: Mapping[str, Any],
    content: Mapping[str, Any] | None = None,
) -> UMGButtonStyleConversion | None:
    """Convert Painter's supported native Button appearance."""

    if str(row.get("kind") or "").strip().casefold() != "button":
        return None
    reasons: list[str] = []
    resolved_tokens = row.get("resolved_tokens")
    resolved_tokens = (
        resolved_tokens if isinstance(resolved_tokens, Mapping) else {}
    )
    fills = _visible_paints(style.get("fills"))
    fill = style.get("fill", "#00000000")
    if len(fills) == 1:
        paint = fills[0]
        paint_type = str(paint.get("type") or "solid").strip().casefold()
        if paint_type == "solid":
            fill = _multiply_alpha(
                (
                    style.get("fill", fill)
                    if "style.fill" in resolved_tokens
                    else paint.get("color", fill)
                ),
                paint.get("opacity", 1.0),
            )
        elif paint_type == "image":
            # The typed ImageFill record owns the background image.
            fill = "#00000000"
        else:
            reasons.append("button_style_fill_requires_solid_or_image")
    elif len(fills) > 1:
        reasons.append("button_style_multiple_fills_unsupported")

    strokes = [
        paint
        for paint in _visible_paints(style.get("strokes"))
        if _number(paint.get("width"), 1.0) > 0.0001
    ]
    stroke = "#00000000"
    stroke_width = 0.0
    if len(strokes) == 1:
        paint = strokes[0]
        if str(paint.get("type") or "solid").strip().casefold() != "solid":
            reasons.append("button_style_stroke_requires_solid")
        elif str(paint.get("blend_mode") or "normal").casefold() != "normal":
            reasons.append("button_style_stroke_blend_mode_unsupported")
        elif str(
            paint.get("align") or style.get("stroke_align") or "center"
        ).casefold() not in {"center", "inside"}:
            reasons.append("button_style_stroke_alignment_unsupported")
        else:
            stroke = _multiply_alpha(
                paint.get("color", style.get("stroke", stroke)),
                paint.get("opacity", 1.0),
            )
            stroke_width = max(0.0, _number(paint.get("width"), 1.0))
    elif len(strokes) > 1:
        reasons.append("button_style_multiple_strokes_unsupported")

    if _number(style.get("corner_smoothing"), 0.0) > 0.0001:
        reasons.append("button_style_corner_smoothing_unsupported")
    if _visible_paints(style.get("effects")) or isinstance(
        style.get("shadow"), Mapping
    ):
        reasons.append("button_style_effect_requires_material_or_bake")

    record = make_umg_button_style(
        fill=fill,
        stroke=stroke,
        stroke_width=stroke_width,
        corner_radii=style.get("corner_radii"),
        radius=style.get("radius", 0.0),
        text_color=style.get("text_color", "#FFFFFFFF"),
        font_size=style.get("font_size", 16.0),
        font_weight=style.get("font_weight", 400),
    )
    reasons.extend(
        validate_umg_button_style_record(
            record,
            layer_kind="Button",
            document_schema_version=TIGER_UMG_BUTTON_STYLE_DOCUMENT_SCHEMA_VERSION,
            required=True,
        )
    )
    return UMGButtonStyleConversion(record, sorted(set(reasons)))


def motion_button_style_record(
    params: Mapping[str, Any],
    *,
    layer_type: str = "",
    has_image_fill: bool = False,
) -> dict[str, Any]:
    """Convert one Motion button layer's static source parameters."""

    kind = str(layer_type or "").strip().casefold()
    if has_image_fill or kind in {"group", "image"}:
        fill = "#00000000"
    elif kind == "text":
        fill = params.get("background_color", "#00000000")
    else:
        fill = params.get("fill", params.get("color", "#4A4A4AFF"))
    text_color = params.get(
        "text_color",
        params.get("fill", "#FFFFFFFF") if kind == "text" else "#FFFFFFFF",
    )
    return make_umg_button_style(
        fill=fill,
        stroke=params.get("stroke", "#00000000"),
        stroke_width=params.get("stroke_width", 0.0),
        corner_radii=params.get("corner_radii"),
        radius=params.get("radius", 0.0),
        text_color=text_color,
        font_size=params.get("font_size", 16.0),
        font_weight=params.get("font_weight", 400),
    )


def umg_button_style_preview(value: object) -> dict[str, Any]:
    """Return schema-16 states in Painter's normalized style vocabulary."""

    source = value if isinstance(value, Mapping) else {}
    enabled = source.get("Enabled") is True
    states: dict[str, dict[str, Any]] = {}
    for serialized, preview_name in (
        ("Normal", "normal"),
        ("Hovered", "hovered"),
        ("Pressed", "pressed"),
        ("Disabled", "disabled"),
    ):
        state = source.get(serialized)
        state = state if isinstance(state, Mapping) else {}
        radii = state.get("CornerRadii")
        radii = radii if isinstance(radii, Mapping) else {}
        corner_radii = {
            "top_left": _number(radii.get("X"), 0.0),
            "top_right": _number(radii.get("Y"), 0.0),
            "bottom_right": _number(radii.get("Z"), 0.0),
            "bottom_left": _number(radii.get("W"), 0.0),
        }
        values = list(corner_radii.values())
        radius = (
            values[0]
            if values and max(values) - min(values) <= 0.000001
            else 0.0
        )
        states[preview_name] = {
            "fill": str(state.get("Fill") or "#4A4A4AFF"),
            "stroke": str(state.get("Stroke") or "#777777FF"),
            "stroke_width": _number(state.get("StrokeWidth"), 0.0),
            "radius": radius,
            "corner_radii": corner_radii,
            "text_color": str(state.get("TextColor") or "#FFFFFFFF"),
            "font_size": _number(state.get("FontSize"), 16.0),
            "font_weight": int(round(_number(state.get("FontWeight"), 400.0))),
            "opacity": max(0.0, min(1.0, _number(state.get("Opacity"), 1.0))),
        }
    return {"enabled": enabled, "states": states}


def validate_umg_button_style_record(
    value: object,
    *,
    layer_kind: str = "",
    document_schema_version: int | None = None,
    required: bool = False,
) -> list[str]:
    """Strictly validate one typed ButtonStyle without provider coercion."""

    if not isinstance(value, Mapping) or not value:
        return ["button_style_missing"] if required else []
    source = value
    reasons: list[str] = []
    if document_schema_version is not None:
        try:
            schema_version = int(document_schema_version)
        except (TypeError, ValueError):
            schema_version = 0
        if schema_version < TIGER_UMG_BUTTON_STYLE_DOCUMENT_SCHEMA_VERSION:
            reasons.append("button_style_requires_schema_16")
    if layer_kind and str(layer_kind) != "Button":
        reasons.append("button_style_layer_kind_unsupported")
    if set(source) != _RECORD_FIELDS:
        reasons.append("button_style_record_fields_invalid")
    if str(source.get("Schema") or "") != TIGER_UMG_BUTTON_STYLE_SCHEMA:
        reasons.append("button_style_schema_unsupported")
    if not isinstance(source.get("Enabled"), bool):
        reasons.append("button_style_enabled_invalid")

    for state_name in UMG_BUTTON_STYLE_STATES:
        state = source.get(state_name)
        label = state_name.casefold()
        if not isinstance(state, Mapping):
            reasons.append(f"button_style_{label}_invalid")
            continue
        if set(state) != _STATE_FIELDS:
            reasons.append(f"button_style_{label}_fields_invalid")
        if not _valid_color(state.get("Fill")):
            reasons.append(f"button_style_{label}_fill_invalid")
        if not _valid_color(state.get("Stroke")):
            reasons.append(f"button_style_{label}_stroke_invalid")
        if not _finite_number(state.get("StrokeWidth")) or float(
            state.get("StrokeWidth", -1.0)
        ) < 0.0:
            reasons.append(f"button_style_{label}_stroke_width_invalid")
        radii = state.get("CornerRadii")
        if (
            not isinstance(radii, Mapping)
            or set(radii) != _RADII_FIELDS
            or any(
                not _finite_number(radii.get(key))
                or float(radii.get(key, -1.0)) < 0.0
                for key in _RADII_FIELDS
            )
        ):
            reasons.append(f"button_style_{label}_corner_radii_invalid")
        if not _valid_color(state.get("TextColor")):
            reasons.append(f"button_style_{label}_text_color_invalid")
        if not _finite_number(state.get("FontSize")) or float(
            state.get("FontSize", 0.0)
        ) <= 0.0:
            reasons.append(f"button_style_{label}_font_size_invalid")
        weight = state.get("FontWeight")
        if (
            not isinstance(weight, int)
            or isinstance(weight, bool)
            or not 100 <= weight <= 900
        ):
            reasons.append(f"button_style_{label}_font_weight_invalid")
        if not _finite_number(state.get("Opacity")) or not 0.0 <= float(
            state.get("Opacity", -1.0)
        ) <= 1.0:
            reasons.append(f"button_style_{label}_opacity_invalid")
    return sorted(set(reasons))


# Short aliases used by provider adapters and tests.
BUTTON_STYLE_SCHEMA_VERSION = TIGER_UMG_BUTTON_STYLE_DOCUMENT_SCHEMA_VERSION
button_style_preview = umg_button_style_preview


__all__ = [
    "BUTTON_STYLE_SCHEMA_VERSION",
    "TIGER_UMG_BUTTON_STYLE_DOCUMENT_SCHEMA_VERSION",
    "TIGER_UMG_BUTTON_STYLE_SCHEMA",
    "UMG_BUTTON_STYLE_STATES",
    "UMGButtonStyleConversion",
    "button_style_preview",
    "make_umg_button_style",
    "motion_button_style_record",
    "painter_button_style_conversion",
    "umg_button_style_preview",
    "validate_umg_button_style_record",
]

"""Translate decoded ``.fig`` node changes into the Figma REST node shape.

``.fig`` stores a flat ``nodeChanges`` array where every entry carries a GUID and
a ``parentIndex`` back-reference, with geometry expressed as a parent-relative
affine transform. The REST ``/v1/files`` response instead nests children and
publishes absolute bounds. :func:`fig_archive_to_rest_payload` rebuilds the tree,
composes transforms into ``absoluteBoundingBox``, and renames the internal
fields onto their REST equivalents so
:func:`app.painter_ui_figma.import_figma_payload` runs unchanged.

Field coverage is deliberately scoped to what the importer consumes. Anything
unmapped is reported through the returned warnings rather than dropped silently.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

from app.painter_ui_figma_fig import FigArchive
from app.painter_ui_figma_fig_vector import fig_vector_geometry

__all__ = [
    "FIG_REST_SCHEMA",
    "fig_archive_to_rest_payload",
    "fig_guid_to_id",
]

FIG_REST_SCHEMA = "tigerstudio.painter.ui.fig_rest.v1"

# Internal node type names that differ from their REST spelling. Types absent
# from this table pass through unchanged when the REST schema already knows
# them.
_NODE_TYPE_ALIASES: Mapping[str, str] = {
    "ROUNDED_RECTANGLE": "RECTANGLE",
    "SYMBOL": "COMPONENT",
}

_REST_NODE_TYPES: frozenset[str] = frozenset(
    {
        "BOOLEAN_OPERATION",
        "CANVAS",
        "COMPONENT",
        "COMPONENT_SET",
        "CONNECTOR",
        "DOCUMENT",
        "ELLIPSE",
        "FRAME",
        "GROUP",
        "INSTANCE",
        "LINE",
        "RECTANGLE",
        "REGULAR_POLYGON",
        "SECTION",
        "SHAPE_WITH_TEXT",
        "SLICE",
        "STAR",
        "STICKY",
        "TABLE",
        "TABLE_CELL",
        "TEXT",
        "VECTOR",
        "WASHI_TAPE",
    }
)

_EFFECT_TYPE_ALIASES: Mapping[str, str] = {
    "FOREGROUND_BLUR": "LAYER_BLUR",
}

_PAINT_TYPE_ALIASES: Mapping[str, str] = {
    "EMOJI": "SOLID",
}

# Figma stores the typeface style as a display name; the REST payload publishes
# a numeric weight. Only unambiguous names are mapped, everything else stays at
# the regular weight so text does not silently render bold.
_FONT_WEIGHTS: Mapping[str, int] = {
    "thin": 100,
    "hairline": 100,
    "extralight": 200,
    "ultralight": 200,
    "light": 300,
    "regular": 400,
    "normal": 400,
    "book": 400,
    "medium": 500,
    "semibold": 600,
    "demibold": 600,
    "bold": 700,
    "extrabold": 800,
    "ultrabold": 800,
    "black": 900,
    "heavy": 900,
}

_IDENTITY_TRANSFORM: tuple[float, float, float, float, float, float] = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)

# Internal ``StackSize`` has three members, not two: both hug variants must
# become the REST ``AUTO`` sizing mode or hug frames import as fixed-size.
_HUG_SIZING: frozenset[str] = frozenset({"RESIZE_TO_FIT", "RESIZE_TO_FIT_WITH_IMPLICIT_SIZE"})

# REST ``primaryAxisAlignItems`` has no SPACE_EVENLY member, so the closest
# representable distribution is used and the downgrade is reported.
_STACK_JUSTIFY_DOWNGRADES: Mapping[str, str] = {"SPACE_EVENLY": "SPACE_BETWEEN"}


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else default
    return default


def fig_guid_to_id(guid: Any) -> str:
    """Render an internal ``{sessionID, localID}`` pair as a REST node id."""

    if not isinstance(guid, Mapping):
        return ""
    session = guid.get("sessionID")
    local = guid.get("localID")
    if session is None or local is None:
        return ""
    return f"{int(_number(session)):d}:{int(_number(local)):d}"


# -- affine helpers ------------------------------------------------------


def _transform_tuple(value: Any) -> tuple[float, float, float, float, float, float]:
    if not isinstance(value, Mapping):
        return _IDENTITY_TRANSFORM
    return (
        _number(value.get("m00"), 1.0),
        _number(value.get("m01"), 0.0),
        _number(value.get("m02"), 0.0),
        _number(value.get("m10"), 0.0),
        _number(value.get("m11"), 1.0),
        _number(value.get("m12"), 0.0),
    )


def _compose(
    outer: tuple[float, float, float, float, float, float],
    inner: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    a0, b0, c0, d0, e0, f0 = outer
    a1, b1, c1, d1, e1, f1 = inner
    return (
        a0 * a1 + b0 * d1,
        a0 * b1 + b0 * e1,
        a0 * c1 + b0 * f1 + c0,
        d0 * a1 + e0 * d1,
        d0 * b1 + e0 * e1,
        d0 * c1 + e0 * f1 + f0,
    )


def _apply(
    transform: tuple[float, float, float, float, float, float],
    x: float,
    y: float,
) -> tuple[float, float]:
    a, b, c, d, e, f = transform
    return (a * x + b * y + c, d * x + e * y + f)


def _invert(
    transform: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float] | None:
    a, b, c, d, e, f = transform
    determinant = a * e - b * d
    if abs(determinant) < 1e-12:
        return None
    inverse = 1.0 / determinant
    return (
        e * inverse,
        -b * inverse,
        (b * f - c * e) * inverse,
        -d * inverse,
        a * inverse,
        (c * d - a * f) * inverse,
    )


def _bounding_box(
    transform: tuple[float, float, float, float, float, float],
    width: float,
    height: float,
) -> dict[str, float]:
    corners = [
        _apply(transform, 0.0, 0.0),
        _apply(transform, width, 0.0),
        _apply(transform, 0.0, height),
        _apply(transform, width, height),
    ]
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return {
        "x": min(xs),
        "y": min(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }


# -- leaf converters -----------------------------------------------------


def _color(value: Any) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    return {
        "r": _number(value.get("r")),
        "g": _number(value.get("g")),
        "b": _number(value.get("b")),
        "a": _number(value.get("a"), 1.0),
    }


def _image_ref(image: Any) -> str:
    if not isinstance(image, Mapping):
        return ""
    digest = image.get("hash")
    if isinstance(digest, (bytes, bytearray)):
        return bytes(digest).hex()
    if isinstance(digest, str):
        return digest
    return ""


def _gradient_handles(transform: Any) -> list[dict[str, float]]:
    """Recover the three REST gradient handles from the internal matrix.

    Figma stores a transform that maps normalized node space into gradient
    space; REST publishes the inverse as explicit handle positions.
    """

    inverse = _invert(_transform_tuple(transform))
    if inverse is None:
        return []
    points = [_apply(inverse, 0.0, 0.0), _apply(inverse, 1.0, 0.0), _apply(inverse, 0.0, 1.0)]
    return [{"x": point[0], "y": point[1]} for point in points]


def _paint(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    raw_type = str(raw.get("type") or "SOLID").upper()
    paint_type = _PAINT_TYPE_ALIASES.get(raw_type, raw_type)
    paint: dict[str, Any] = {
        "type": paint_type,
        "visible": bool(raw.get("visible", True)),
        "opacity": _number(raw.get("opacity"), 1.0),
        "blendMode": str(raw.get("blendMode") or "NORMAL").upper(),
    }
    color = _color(raw.get("color"))
    if color is not None:
        paint["color"] = color
    if paint_type.startswith("GRADIENT"):
        stops = raw.get("stops")
        gradient_stops: list[dict[str, Any]] = []
        if isinstance(stops, Sequence) and not isinstance(stops, (str, bytes)):
            for stop in stops:
                if not isinstance(stop, Mapping):
                    continue
                stop_color = _color(stop.get("color"))
                gradient_stops.append(
                    {
                        "color": stop_color if stop_color is not None else {"r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0},
                        "position": _number(stop.get("position")),
                    }
                )
        paint["gradientStops"] = gradient_stops
        handles = _gradient_handles(raw.get("transform"))
        if handles:
            paint["gradientHandlePositions"] = handles
    if paint_type == "IMAGE":
        image_ref = _image_ref(raw.get("image"))
        if image_ref:
            paint["imageRef"] = image_ref
        scale_mode = str(raw.get("imageScaleMode") or "").upper()
        if scale_mode:
            paint["scaleMode"] = scale_mode
    return paint


def _paints(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    result: list[dict[str, Any]] = []
    for entry in raw:
        paint = _paint(entry)
        if paint is not None:
            result.append(paint)
    return result


def _effects(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    result: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        raw_type = str(entry.get("type") or "").upper()
        effect: dict[str, Any] = {
            "type": _EFFECT_TYPE_ALIASES.get(raw_type, raw_type),
            "visible": bool(entry.get("visible", True)),
            "radius": _number(entry.get("radius")),
        }
        color = _color(entry.get("color"))
        if color is not None:
            effect["color"] = color
        offset = entry.get("offset")
        if isinstance(offset, Mapping):
            effect["offset"] = {"x": _number(offset.get("x")), "y": _number(offset.get("y"))}
        if "spread" in entry:
            effect["spread"] = _number(entry.get("spread"))
        blend_mode = str(entry.get("blendMode") or "").upper()
        if blend_mode:
            effect["blendMode"] = blend_mode
        result.append(effect)
    return result


def _font_weight(style: str) -> int:
    normalized = style.replace(" ", "").replace("-", "").casefold()
    for suffix in ("italic", "oblique"):
        if normalized.endswith(suffix) and normalized != suffix:
            normalized = normalized[: -len(suffix)]
            break
    return _FONT_WEIGHTS.get(normalized, 400)


def _text_style(node: Mapping[str, Any]) -> dict[str, Any]:
    font_name = node.get("fontName")
    family = ""
    style_name = "Regular"
    postscript = ""
    if isinstance(font_name, Mapping):
        family = str(font_name.get("family") or "")
        style_name = str(font_name.get("style") or "Regular")
        postscript = str(font_name.get("postscript") or "")
    font_size = _number(node.get("fontSize"), 12.0)
    style: dict[str, Any] = {
        "fontFamily": family,
        "fontPostScriptName": postscript,
        "fontWeight": _font_weight(style_name),
        "fontSize": font_size,
        "italic": "italic" in style_name.casefold(),
    }
    auto_resize = str(node.get("textAutoResize") or "").upper()
    if auto_resize:
        # The importer turns WIDTH_AND_HEIGHT into the renderer's auto_width
        # mode, which is what stops text being clipped to a box Figma only
        # derived.  Leaving the field out clipped the last glyph of every
        # hugging label, because our font measures a hair wider than Figma's.
        style["textAutoResize"] = auto_resize
    horizontal = str(node.get("textAlignHorizontal") or "").upper()
    if horizontal:
        style["textAlignHorizontal"] = horizontal
    vertical = str(node.get("textAlignVertical") or "").upper()
    if vertical:
        style["textAlignVertical"] = vertical

    letter_spacing = node.get("letterSpacing")
    if isinstance(letter_spacing, Mapping):
        units = str(letter_spacing.get("units") or "PIXELS").upper()
        value = _number(letter_spacing.get("value"))
        style["letterSpacing"] = value * font_size / 100.0 if units == "PERCENT" else value

    line_height = node.get("lineHeight")
    if isinstance(line_height, Mapping):
        units = str(line_height.get("units") or "RAW").upper()
        value = _number(line_height.get("value"))
        if units == "PIXELS":
            if value > 0.0:
                style["lineHeightPx"] = value
                style["lineHeightUnit"] = "PIXELS"
            # Zero pixels is how ``.fig`` spells "auto": Figma derives the line
            # box from the font.  Passing the zero through collapsed the text to
            # nothing, so the field is left out and the renderer measures.
        elif units == "PERCENT":
            style["lineHeightPercent"] = value
            style["lineHeightPx"] = font_size * value / 100.0
            style["lineHeightUnit"] = "FONT_SIZE_%"
        else:
            # RAW is a multiplier of the font size rather than an absolute size.
            style["lineHeightPx"] = font_size * value if value else font_size
            style["lineHeightUnit"] = "RAW"
    return style


def _corner_radii(node: Mapping[str, Any]) -> tuple[float | None, list[float] | None]:
    keys = (
        "rectangleTopLeftCornerRadius",
        "rectangleTopRightCornerRadius",
        "rectangleBottomRightCornerRadius",
        "rectangleBottomLeftCornerRadius",
    )
    if any(key in node for key in keys):
        radii = [_number(node.get(key)) for key in keys]
        if len(set(radii)) == 1:
            return radii[0], None
        return None, radii
    if "cornerRadius" in node:
        return _number(node.get("cornerRadius")), None
    return None, None


def _auto_layout(node: Mapping[str, Any], rest: dict[str, Any], warnings: list[str]) -> None:
    stack_mode = str(node.get("stackMode") or "").upper()
    if stack_mode in {"HORIZONTAL", "VERTICAL"}:
        rest["layoutMode"] = stack_mode
    elif stack_mode == "NONE":
        rest["layoutMode"] = "NONE"
    if "stackSpacing" in node:
        rest["itemSpacing"] = _number(node.get("stackSpacing"))
    # Figma keeps one horizontal and one vertical padding plus explicit
    # trailing overrides; REST publishes all four edges.
    horizontal_padding = _number(node.get("stackHorizontalPadding"))
    vertical_padding = _number(node.get("stackVerticalPadding"))
    rest["paddingLeft"] = horizontal_padding
    rest["paddingTop"] = vertical_padding
    rest["paddingRight"] = _number(node.get("stackPaddingRight"), horizontal_padding)
    rest["paddingBottom"] = _number(node.get("stackPaddingBottom"), vertical_padding)
    primary = str(node.get("stackPrimaryAlignItems") or "").upper()
    if primary:
        downgraded = _STACK_JUSTIFY_DOWNGRADES.get(primary)
        if downgraded:
            warnings.append(f"fig_stack_justify_downgraded:{primary}")
            primary = downgraded
        rest["primaryAxisAlignItems"] = primary
    counter = str(node.get("stackCounterAlignItems") or "").upper()
    if counter:
        rest["counterAxisAlignItems"] = counter
    primary_sizing = str(node.get("stackPrimarySizing") or "").upper()
    if primary_sizing:
        rest["primaryAxisSizingMode"] = "AUTO" if primary_sizing in _HUG_SIZING else "FIXED"
    counter_sizing = str(node.get("stackCounterSizing") or "").upper()
    if counter_sizing:
        rest["counterAxisSizingMode"] = "AUTO" if counter_sizing in _HUG_SIZING else "FIXED"
    child_align = str(node.get("stackChildAlignSelf") or "").upper()
    if child_align and child_align != "AUTO":
        rest["layoutAlign"] = "STRETCH" if child_align == "STRETCH" else "INHERIT"
    if "stackChildPrimaryGrow" in node:
        rest["layoutGrow"] = _number(node.get("stackChildPrimaryGrow"))
    if str(node.get("stackPositioning") or "").upper() == "ABSOLUTE":
        rest["layoutPositioning"] = "ABSOLUTE"


def _constraints(node: Mapping[str, Any]) -> dict[str, str] | None:
    horizontal = node.get("horizontalConstraint")
    vertical = node.get("verticalConstraint")
    if horizontal is None and vertical is None:
        return None
    return {
        "horizontal": str(horizontal or "MIN").upper(),
        "vertical": str(vertical or "MIN").upper(),
    }


def _strokes(node: Mapping[str, Any], rest: dict[str, Any]) -> None:
    strokes = _paints(node.get("strokePaints"))
    if strokes:
        rest["strokes"] = strokes
    if "strokeWeight" in node:
        rest["strokeWeight"] = _number(node.get("strokeWeight"))
    align = str(node.get("strokeAlign") or "").upper()
    if align:
        rest["strokeAlign"] = align
    cap = str(node.get("strokeCap") or "").upper()
    if cap:
        rest["strokeCap"] = cap
    join = str(node.get("strokeJoin") or "").upper()
    if join:
        rest["strokeJoin"] = join
    dashes = node.get("dashPattern")
    if isinstance(dashes, Sequence) and not isinstance(dashes, (str, bytes)) and dashes:
        rest["strokeDashes"] = [_number(entry) for entry in dashes]
    individual = {
        "top": node.get("borderTopWeight"),
        "right": node.get("borderRightWeight"),
        "bottom": node.get("borderBottomWeight"),
        "left": node.get("borderLeftWeight"),
    }
    if any(value is not None for value in individual.values()):
        rest["individualStrokeWeights"] = {
            key: _number(value) for key, value in individual.items()
        }


# -- tree assembly -------------------------------------------------------


class _FigNode:
    __slots__ = ("raw", "node_id", "parent_id", "position", "children")

    def __init__(self, raw: Mapping[str, Any], node_id: str, parent_id: str, position: str) -> None:
        self.raw = raw
        self.node_id = node_id
        self.parent_id = parent_id
        self.position = position
        self.children: list[_FigNode] = []


def _collect_nodes(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, _FigNode], list[str]]:
    nodes: dict[str, _FigNode] = {}
    warnings: list[str] = []
    for raw in rows:
        node_id = fig_guid_to_id(raw.get("guid"))
        if not node_id:
            warnings.append("fig_node_missing_guid")
            continue
        parent_index = raw.get("parentIndex")
        parent_id = ""
        position = ""
        if isinstance(parent_index, Mapping):
            parent_id = fig_guid_to_id(parent_index.get("guid"))
            position = str(parent_index.get("position") or "")
        if node_id in nodes:
            # Later changes in the stream supersede earlier ones for the same
            # GUID, which is how incremental .fig payloads express edits.
            nodes[node_id] = _FigNode(raw, node_id, parent_id, position)
            continue
        nodes[node_id] = _FigNode(raw, node_id, parent_id, position)
    return nodes, warnings


def _link_tree(nodes: Mapping[str, _FigNode]) -> list[_FigNode]:
    roots: list[_FigNode] = []
    for node in nodes.values():
        parent = nodes.get(node.parent_id) if node.parent_id else None
        if parent is None or parent is node:
            roots.append(node)
        else:
            parent.children.append(node)
    for node in nodes.values():
        # ``position`` is a fractional index; lexicographic order is the
        # intended sibling order. The id breaks ties deterministically.
        node.children.sort(key=lambda child: (child.position, child.node_id))
    roots.sort(key=lambda child: (child.position, child.node_id))
    return roots


_MAX_INSTANCE_DEPTH = 12
_MAX_EXPANDED_INSTANCE_NODES = 400_000


def _guid_path_key(value: Any) -> tuple[str, ...]:
    """Identify one descendant of a component, as an override addresses it."""
    guids = (value or {}).get("guids") if isinstance(value, Mapping) else None
    if not isinstance(guids, Sequence) or isinstance(guids, (str, bytes)):
        return ()
    return tuple(fig_guid_to_id(item) for item in guids)


def _symbol_overrides(symbol_data: Any) -> dict[tuple[str, ...], dict[str, Any]]:
    rows = (symbol_data or {}).get("symbolOverrides") if isinstance(symbol_data, Mapping) else None
    result: dict[tuple[str, ...], dict[str, Any]] = {}
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return result
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        key = _guid_path_key(row.get("guidPath"))
        if not key:
            continue
        fields = {name: value for name, value in row.items() if name != "guidPath"}
        # Later overrides for the same descendant supersede earlier ones.
        result.setdefault(key, {}).update(fields)
    return result


def _derived_symbol_data(raw: Mapping[str, Any]) -> dict[tuple[str, ...], dict[str, Any]]:
    rows = raw.get("derivedSymbolData")
    result: dict[tuple[str, ...], dict[str, Any]] = {}
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return result
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        key = _guid_path_key(row.get("guidPath"))
        if not key:
            continue
        fields = {
            name: value
            for name, value in row.items()
            if name != "guidPath" and value not in (None, [])
        }
        if fields:
            result.setdefault(key, {}).update(fields)
    return result


def _library_guid_remap(
    node: Mapping[str, Any],
    symbol_subtree: list[str],
    known: Mapping[str, Any],
) -> dict[str, str]:
    """Map a published component's own guids onto this file's renumbered copy.

    A component published to a library keeps addressing its descendants by the
    library's guids, which the local copy has renumbered, so the overrides that
    carry the instance's text and colour name nodes this file has never heard
    of.  Both sides are allocated in document order, so sorting the unknown
    guids and zipping them against the component's subtree recovers the pairing.

    Returns an empty map unless the two sides line up exactly, because a
    misaligned guess would write an instance's text onto the wrong node.
    """

    unknown: set[str] = set()
    for row in (node.get("symbolData") or {}).get("symbolOverrides") or []:
        if not isinstance(row, Mapping):
            continue
        path = _guid_path_key(row.get("guidPath"))
        if path and path[0] not in known:
            unknown.add(path[0])
    for row in node.get("derivedSymbolData") or []:
        if not isinstance(row, Mapping):
            continue
        path = _guid_path_key(row.get("guidPath"))
        if path and path[0] not in known:
            unknown.add(path[0])
    if not unknown:
        return {}

    def order(guid: str) -> tuple[int, ...]:
        try:
            return tuple(int(part) for part in guid.split(":"))
        except ValueError:
            return (0, 0)

    ordered = sorted(unknown, key=order)
    if len(ordered) != len(symbol_subtree):
        # Anything but an exact match is ambiguous: with one guid too few there
        # is no way to tell whether the missing one is the component root or a
        # leaf, and guessing shifts every override onto its neighbour.
        return {}
    return dict(zip(ordered, symbol_subtree))


# What a remapped override may carry.  The pairing is recovered positionally,
# so it is trusted for the content Figma clearly resolved through it - the text
# and its metrics - and not for paint.  Those overrides pair a black paint with
# ``styleIdForFill`` set to the null sentinel (all 189 in this file do), which
# records "no shared style" rather than a colour: the component child keeps the
# white it gets from its library style, which is what Figma draws.
_REMAPPED_OVERRIDE_FIELDS: frozenset[str] = frozenset(
    {
        "textData",
        "characters",
        "fontName",
        "fontSize",
        "lineHeight",
        "letterSpacing",
        "textCase",
        "textDecoration",
        "textAlignHorizontal",
        "textAlignVertical",
        "size",
        "visible",
        "name",
    }
)


# Fields that only make sense on a particular node type.  A positional remap is
# sound but not certain, so an override that would land somewhere impossible is
# dropped rather than applied.
_OVERRIDE_TYPE_GUARDS: Mapping[str, frozenset[str]] = {
    "textData": frozenset({"TEXT"}),
    "derivedTextData": frozenset({"TEXT"}),
    "fontName": frozenset({"TEXT"}),
    "fontSize": frozenset({"TEXT"}),
    "textDecoration": frozenset({"TEXT"}),
    "textAlignHorizontal": frozenset({"TEXT"}),
    "textAlignVertical": frozenset({"TEXT"}),
}


def _guarded_override(
    fields: Mapping[str, Any],
    node_type: str,
) -> dict[str, Any]:
    kind = str(node_type or "").upper()
    return {
        name: value
        for name, value in fields.items()
        if kind in _OVERRIDE_TYPE_GUARDS.get(name, frozenset({kind}))
    }


def _expand_instances(
    nodes: Mapping[str, "_FigNode"],
    warnings: list[str],
) -> dict[str, int]:
    """Give every instance the children its component defines.

    A ``.fig`` instance stores only a reference to its component plus the
    overrides that make it differ; the REST API publishes the whole subtree.
    Without this the importer sees an empty node and everything inside the
    instance - text, icons, nested frames - disappears.
    """

    symbols = {
        node.node_id: node
        for node in nodes.values()
        if str(node.raw.get("type") or "").upper() == "SYMBOL"
    }
    budget = [_MAX_EXPANDED_INSTANCE_NODES]
    report = {
        "instances": 0,
        "nodes": 0,
        "unresolved": 0,
        "truncated": 0,
        "remapped": 0,
    }

    def _symbol_subtree(root: "_FigNode") -> list[str]:
        out = [root.node_id]
        for child in root.children:
            out.extend(_symbol_subtree(child))
        return out

    def _remapped(
        table: Mapping[tuple[str, ...], Mapping[str, Any]],
        remap: Mapping[str, str],
        *,
        restrict: bool = False,
    ) -> dict[tuple[str, ...], dict[str, Any]]:
        if not remap and not restrict:
            return {key: dict(value) for key, value in table.items()}
        result: dict[tuple[str, ...], dict[str, Any]] = {}
        for key, value in table.items():
            moved = tuple(remap.get(item, item) for item in key)
            fields = (
                {
                    name: item
                    for name, item in value.items()
                    if name in _REMAPPED_OVERRIDE_FIELDS
                }
                if restrict
                else dict(value)
            )
            if fields:
                result.setdefault(moved, {}).update(fields)
        return result

    def clone(
        source: "_FigNode",
        instance_id: str,
        path: tuple[str, ...],
        overrides: Mapping[tuple[str, ...], Mapping[str, Any]],
        derived: Mapping[tuple[str, ...], Mapping[str, Any]],
        seen_symbols: frozenset[str],
        depth: int,
    ) -> "_FigNode | None":
        if budget[0] <= 0:
            report["truncated"] += 1
            return None
        budget[0] -= 1
        step = path + (source.node_id,)
        raw = dict(source.raw)
        raw.update(derived.get(step) or {})
        # A descendant that is itself an instance already stores the state
        # Figma resolved for it, so the outer instance's override for that path
        # is a stale delta - applying it repainted resolved nested instances
        # with a colour Figma never renders.  Its own nested overrides still
        # apply, one level down.
        if str(source.raw.get("type") or "").upper() != "INSTANCE":
            raw.update(
                _guarded_override(
                    overrides.get(step) or {},
                    str(source.raw.get("type") or ""),
                )
            )
        # REST spells an instance child ``I<instance>;<component child>``.
        node_id = "I" + ";".join((instance_id, *step))
        copy_node = _FigNode(raw, node_id, instance_id, source.position)
        report["nodes"] += 1
        nested_type = str(raw.get("type") or "").upper()
        if nested_type == "INSTANCE" and not source.children:
            expand(copy_node, seen_symbols, depth + 1, path=step, outer=(overrides, derived))
        else:
            for child in source.children:
                cloned = clone(
                    child,
                    instance_id,
                    step,
                    overrides,
                    derived,
                    seen_symbols,
                    depth,
                )
                if cloned is not None:
                    copy_node.children.append(cloned)
            copy_node.children.sort(key=lambda item: (item.position, item.node_id))
        return copy_node

    def expand(
        node: "_FigNode",
        seen_symbols: frozenset[str],
        depth: int,
        *,
        path: tuple[str, ...] = (),
        outer: tuple[Mapping[Any, Any], Mapping[Any, Any]] | None = None,
    ) -> None:
        if depth > _MAX_INSTANCE_DEPTH:
            warnings.append(f"fig_instance_nesting_too_deep:{node.node_id}")
            return
        data = node.raw.get("symbolData")
        symbol_id = fig_guid_to_id((data or {}).get("symbolID") if isinstance(data, Mapping) else None)
        symbol = symbols.get(symbol_id)
        if symbol is None:
            report["unresolved"] += 1
            warnings.append(f"fig_instance_component_missing:{node.node_id}")
            return
        if symbol_id in seen_symbols:
            # A component that contains itself would expand forever.
            warnings.append(f"fig_instance_recursive_component:{symbol_id}")
            return
        subtree = _symbol_subtree(symbol)
        remap = _library_guid_remap(node.raw, subtree, nodes)
        overrides = _remapped(_symbol_overrides(data), remap, restrict=bool(remap))
        derived = _remapped(_derived_symbol_data(node.raw), remap)
        if remap:
            report["remapped"] += 1
        if outer is not None:
            # A nested instance also inherits the outer instance's overrides
            # that address through it, rebased onto this symbol.
            outer_overrides, outer_derived = outer
            for key, fields in outer_overrides.items():
                if len(key) > len(path) and key[: len(path)] == path:
                    overrides.setdefault(key[len(path):], {}).update(fields)
            for key, fields in outer_derived.items():
                if len(key) > len(path) and key[: len(path)] == path:
                    derived.setdefault(key[len(path):], {}).update(fields)
        children = []
        for child in symbol.children:
            cloned = clone(
                child,
                node.node_id,
                (),
                overrides,
                derived,
                seen_symbols | {symbol_id},
                depth,
            )
            if cloned is not None:
                children.append(cloned)
        children.sort(key=lambda item: (item.position, item.node_id))
        node.children = children
        report["instances"] += 1

    for node in list(nodes.values()):
        if str(node.raw.get("type") or "").upper() != "INSTANCE":
            continue
        if node.children:
            continue
        expand(node, frozenset(), 0)
    if report["truncated"]:
        warnings.append(
            f"fig_instance_expansion_truncated:{_MAX_EXPANDED_INSTANCE_NODES}"
        )
    return report


def _node_type(raw: Mapping[str, Any], warnings: list[str]) -> str:
    internal = str(raw.get("type") or "").upper()
    if not internal:
        return "FRAME"
    if internal == "SYMBOL" and bool(raw.get("isStateGroup")):
        return "COMPONENT_SET"
    mapped = _NODE_TYPE_ALIASES.get(internal, internal)
    if mapped not in _REST_NODE_TYPES:
        warnings.append(f"fig_unmapped_node_type:{internal}")
    return mapped


def _convert_node(
    node: _FigNode,
    parent_transform: tuple[float, float, float, float, float, float],
    warnings: list[str],
    blobs: Sequence[Any] = (),
) -> dict[str, Any]:
    raw = node.raw
    local_transform = _transform_tuple(raw.get("transform"))
    absolute = _compose(parent_transform, local_transform)

    size = raw.get("size")
    width = _number(size.get("x")) if isinstance(size, Mapping) else 0.0
    height = _number(size.get("y")) if isinstance(size, Mapping) else 0.0
    if (
        height <= 0.0
        and str(raw.get("type") or "").upper() == "TEXT"
        and "HEIGHT" in str(raw.get("textAutoResize") or "").upper()
    ):
        # Text that hugs its height stores zero and lets Figma lay it out. REST
        # publishes the laid-out height, so one is derived here from the line
        # height or, failing that, the font size - otherwise the glyphs land in
        # a box a pixel tall and never appear.
        line_height = raw.get("lineHeight")
        measured = (
            _number(line_height.get("value"))
            if isinstance(line_height, Mapping)
            and str(line_height.get("units") or "").upper() == "PIXELS"
            else 0.0
        )
        height = measured if measured > 0.0 else _number(raw.get("fontSize"), 12.0) * 1.25

    rest: dict[str, Any] = {
        "id": node.node_id,
        "name": str(raw.get("name") or ""),
        "type": _node_type(raw, warnings),
        "visible": bool(raw.get("visible", True)),
    }
    if "opacity" in raw:
        rest["opacity"] = _number(raw.get("opacity"), 1.0)
    blend_mode = str(raw.get("blendMode") or "").upper()
    if blend_mode:
        rest["blendMode"] = blend_mode

    if rest["type"] not in {"DOCUMENT", "CANVAS"}:
        rest["absoluteBoundingBox"] = _bounding_box(absolute, width, height)
        rest["size"] = {"x": width, "y": height}
        a, b, c, d, e, f = local_transform
        rest["relativeTransform"] = [[a, b, c], [d, e, f]]
        rest["rotation"] = math.degrees(math.atan2(d, a))

    fills = _paints(raw.get("fillPaints"))
    if fills:
        rest["fills"] = fills
    _strokes(raw, rest)

    effects = _effects(raw.get("effects"))
    if effects:
        rest["effects"] = effects

    radius, radii = _corner_radii(raw)
    if radius is not None:
        rest["cornerRadius"] = radius
    if radii is not None:
        rest["rectangleCornerRadii"] = radii

    if "frameMaskDisabled" in raw:
        rest["clipsContent"] = not bool(raw.get("frameMaskDisabled"))
    elif "clipsContent" in raw:
        rest["clipsContent"] = bool(raw.get("clipsContent"))

    if raw.get("mask"):
        # REST - and therefore the importer - spells these ``isMask`` and
        # ``isMaskOutline``.  Emitting ``mask`` meant nothing read them, so
        # every mask was imported as an ordinary shape: Figma fills mask
        # rectangles with a loud colour precisely because they never render.
        rest["isMask"] = True
        if raw.get("maskIsOutline"):
            rest["isMaskOutline"] = True
        mask_type = str(raw.get("maskType") or "").upper()
        if mask_type:
            rest["maskType"] = mask_type

    constraints = _constraints(raw)
    if constraints is not None:
        rest["constraints"] = constraints
    _auto_layout(raw, rest, warnings)

    if rest["type"] == "TEXT":
        text_data = raw.get("textData")
        characters = ""
        if isinstance(text_data, Mapping):
            characters = str(text_data.get("characters") or "")
        elif isinstance(raw.get("characters"), str):
            characters = str(raw.get("characters"))
        rest["characters"] = characters
        rest["style"] = _text_style(raw)

    # .fig keeps editable vector networks instead of the flattened path strings
    # REST publishes, so rebuild fillGeometry or the importer blocks the node
    # with missing_geometry_paths.
    if "vectorData" in raw:
        geometry, vector_warning = fig_vector_geometry(raw, blobs, width=width, height=height)
        if geometry:
            rest["fillGeometry"] = geometry
        if vector_warning:
            warnings.append(vector_warning)

    if rest["type"] == "BOOLEAN_OPERATION":
        # Without this every boolean imported as the default UNION, so a shape
        # cut out of another one came through as the uncut original.
        operation = str(raw.get("booleanOperation") or "").upper()
        if operation:
            rest["booleanOperation"] = operation

    if rest["type"] == "INSTANCE":
        symbol_data = raw.get("symbolData")
        component_id = ""
        if isinstance(symbol_data, Mapping):
            component_id = fig_guid_to_id(symbol_data.get("symbolID"))
        if component_id:
            rest["componentId"] = component_id

    children = [_convert_node(child, absolute, warnings, blobs) for child in node.children]
    if children:
        rest["children"] = children
    elif rest["type"] in {"DOCUMENT", "CANVAS", "FRAME", "GROUP", "COMPONENT", "COMPONENT_SET", "SECTION"}:
        rest["children"] = []
    return rest


def _document_root(
    roots: Sequence[_FigNode],
    warnings: list[str],
    blobs: Sequence[Any] = (),
) -> dict[str, Any]:
    document_nodes = [node for node in roots if str(node.raw.get("type") or "").upper() == "DOCUMENT"]
    if document_nodes:
        if len(document_nodes) > 1:
            warnings.append(f"fig_multiple_document_roots:{len(document_nodes)}")
        return _convert_node(document_nodes[0], _IDENTITY_TRANSFORM, warnings, blobs)

    # Fragments exported without their DOCUMENT node still import cleanly once
    # wrapped in the page structure the REST importer expects.
    warnings.append("fig_synthesized_document_root")
    converted = [_convert_node(node, _IDENTITY_TRANSFORM, warnings, blobs) for node in roots]
    pages = [row for row in converted if row.get("type") == "CANVAS"]
    loose = [row for row in converted if row.get("type") != "CANVAS"]
    if loose:
        pages.append(
            {
                "id": "fig:synthetic-canvas",
                "name": "Page 1",
                "type": "CANVAS",
                "children": loose,
            }
        )
    return {
        "id": "fig:synthetic-document",
        "name": "Document",
        "type": "DOCUMENT",
        "children": pages,
    }


def fig_archive_to_rest_payload(archive: FigArchive) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a REST ``/v1/files``-shaped payload from a decoded ``.fig`` archive.

    Returns the payload and a report describing what was translated.
    """

    rows = archive.node_changes
    nodes, warnings = _collect_nodes(rows)
    if not nodes:
        raise ValueError("The .fig document contains no node changes")
    roots = _link_tree(nodes)
    # After linking: expansion copies a component's children, so the tree has
    # to exist first.
    instance_report = _expand_instances(nodes, warnings)
    raw_blobs = archive.message.get("blobs")
    blobs = raw_blobs if isinstance(raw_blobs, list) else []
    document = _document_root(roots, warnings, blobs)

    name = str(archive.meta.get("file_name") or archive.meta.get("name") or "")
    if not name:
        name = str(archive.message.get("fileName") or "") or "Figma Document"

    payload: dict[str, Any] = {
        "name": name,
        "role": "owner",
        "editorType": "figma",
        "version": str(archive.version),
        "document": document,
        "components": {},
        "componentSets": {},
        "styles": {},
    }

    unmapped = sorted({entry for entry in warnings if entry.startswith("fig_unmapped_node_type:")})
    report: dict[str, Any] = {
        "schema": FIG_REST_SCHEMA,
        "source": archive.source,
        "fig_version": archive.version,
        "node_change_count": len(rows),
        "node_count": len(nodes),
        "root_count": len(roots),
        "image_count": len(archive.images),
        "instance_expansion": dict(instance_report),
        "unmapped_node_types": [entry.split(":", 1)[1] for entry in unmapped],
        "warnings": sorted(set(warnings)),
    }
    return payload, report

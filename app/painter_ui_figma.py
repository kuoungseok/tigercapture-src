"""Figma REST import and Figma Plugin export for Painter UI documents."""
from __future__ import annotations

import base64
import copy
import json
import math
import mimetypes
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from app.painter_ui_appearance import ui_effect_render_block_reasons
from app.painter_ui_document import normalize_ui_document, validate_ui_document


FIGMA_EXCHANGE_SCHEMA = "tigerstudio.painter.ui.figma_exchange.v1"
FIGMA_IMPORT_SCHEMA = "tigerstudio.painter.ui.figma_import.v1"
FIGMA_API_ROOT = "https://api.figma.com/v1"
_FIGMA_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?figma\.com/(?:design|file|proto|board)/([^/?#]+)",
    re.IGNORECASE,
)


class PainterUIFigmaError(ValueError):
    pass


def default_figma_asset_root(file_key: str) -> Path:
    return Path.home() / "TigerStudio" / "PainterFigmaAssets" / _stable_id(
        "file", file_key
    )


def figma_file_key(value: str) -> str:
    text = str(value or "").strip()
    match = _FIGMA_URL_PATTERN.search(text)
    candidate = match.group(1) if match else text
    candidate = candidate.split("?")[0].split("#")[0].strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,256}", candidate):
        raise PainterUIFigmaError("Enter a Figma file URL or file key")
    return candidate


def _stable_id(prefix: str, value: object) -> str:
    source = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-")
    return f"figma-{prefix}-{source or 'node'}"


def _figma_property_name(value: object) -> str:
    name = str(value or "").strip()
    return re.sub(r"#\d+:\d+$", "", name).strip() or name


def _tigerstudio_plugin_json(
    node: Mapping[str, Any],
    key: str,
) -> object:
    """Read shared plugin data from REST fixtures without requiring it."""
    shared = node.get("sharedPluginData")
    shared = shared if isinstance(shared, Mapping) else {}
    namespace = shared.get("tigerstudio")
    namespace = namespace if isinstance(namespace, Mapping) else {}
    raw = namespace.get(str(key))
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _tigerstudio_plugin_text(
    node: Mapping[str, Any],
    key: str,
) -> str:
    """Read a non-JSON Tiger Studio shared-plugin-data value."""
    shared = node.get("sharedPluginData")
    shared = shared if isinstance(shared, Mapping) else {}
    namespace = shared.get("tigerstudio")
    namespace = namespace if isinstance(namespace, Mapping) else {}
    return str(namespace.get(str(key)) or "").strip()


def _figma_node_stable_id(node: Mapping[str, Any], prefix: str = "node") -> str:
    return _tigerstudio_plugin_text(node, "stable_id") or _stable_id(
        prefix, node.get("id")
    )


def _figma_component_stable_id(node: Mapping[str, Any]) -> str:
    return _tigerstudio_plugin_text(node, "component_id") or _stable_id(
        "component", node.get("id")
    )


def _figma_component_property_definitions(
    *sources: object,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    type_map = {
        "BOOLEAN": "boolean",
        "TEXT": "text",
        "INSTANCE_SWAP": "instance_swap",
        "VARIANT": "enum",
        "SLOT": "slot",
    }
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for raw_name, raw_definition in source.items():
            if not isinstance(raw_definition, Mapping):
                continue
            name = _figma_property_name(raw_name)
            figma_type = str(raw_definition.get("type") or "TEXT").upper()
            values = (
                list(raw_definition.get("variantOptions") or [])
                if figma_type == "VARIANT"
                else []
            )
            slot_settings = raw_definition.get("slotSettings")
            slot_settings = (
                dict(slot_settings) if isinstance(slot_settings, Mapping) else {}
            )
            result[name] = {
                "type": type_map.get(figma_type, figma_type.casefold()),
                "default": copy.deepcopy(raw_definition.get("defaultValue")),
                "values": [str(value) for value in values],
                "preferred_values": [
                    str(item.get("key") or "")
                    for item in raw_definition.get("preferredValues", [])
                    if isinstance(item, Mapping) and str(item.get("key") or "")
                ],
                "description": str(raw_definition.get("description") or ""),
                "slot_settings": {
                    "stretch_child_on_insert": bool(
                        slot_settings.get("stretchChildOnInsert", False)
                    ),
                    "display_empty_by_default": bool(
                        slot_settings.get("displayEmptyByDefault", False)
                    ),
                    "min_children": slot_settings.get("minChildren"),
                    "max_children": slot_settings.get("maxChildren"),
                    "allow_preferred_values_only": bool(
                        slot_settings.get("allowPreferredValuesOnly", False)
                    ),
                },
            }
    return result


def _figma_component_properties(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for raw_name, raw_property in value.items():
        name = _figma_property_name(raw_name)
        if isinstance(raw_property, Mapping):
            result[name] = copy.deepcopy(raw_property.get("value"))
        else:
            result[name] = copy.deepcopy(raw_property)
    return result


def _figma_component_property_bindings(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    path_map = {
        "characters": "content.text",
        "visible": "visible",
        "mainComponent": "component_id",
    }
    return {
        path_map[field]: _figma_property_name(property_name)
        for field, property_name in value.items()
        if field in path_map and str(property_name or "").strip()
    }


def _figma_unmapped_component_property_bindings(
    value: object,
) -> dict[str, Any]:
    """Preserve reference entries that cannot enter Painter's active map."""

    if not isinstance(value, Mapping):
        return {}
    supported_fields = {"characters", "visible", "mainComponent"}
    return {
        f"figma_field:{field}": copy.deepcopy(property_name)
        for field, property_name in value.items()
        if field not in supported_fields or not str(property_name or "").strip()
    }


def _detach_figma_component_property_bindings(
    row: dict[str, Any],
    warnings: list[str],
    *,
    reason: str = "remote_component_property_bindings_detached",
) -> None:
    """Preserve bindings that cannot remain active after remote fallback."""

    bindings = dict(row.get("component_property_bindings") or {})
    if not bindings:
        return
    content = row.get("content")
    content = dict(content) if isinstance(content, Mapping) else {}
    recovery = content.get("figma_component_property_bindings")
    recovery = dict(recovery) if isinstance(recovery, Mapping) else {}
    recovery.update(copy.deepcopy(bindings))
    content["figma_component_property_bindings"] = recovery
    row["content"] = content
    row["component_property_bindings"] = {}
    warnings.append(f"converted:{row['id']}:{reason}")


def _link_expanded_instance_descendants(
    objects: list[dict[str, Any]],
    objects_by_id: Mapping[str, dict[str, Any]],
    warnings: list[str],
) -> None:
    """Record which definition node each expanded instance descendant clones.

    Figma expands an instance into editable descendants that carry the authored
    values, while the reusable definition keeps the defaults. Both subtrees are
    present here, but only the instance *root* records the definition it came
    from, so a consumer holding one descendant cannot tell an override from a
    default and has to fall back to the definition.

    Descendants are paired positionally in z-order, and only when the two
    subtrees agree exactly on length and kind at every level. Anything else --
    a swapped nested instance, grafted slot content, a variant with different
    children -- leaves the descendants unlinked, which is the behaviour that
    already existed. Nested instance roots are paired but not descended into:
    each one is linked against its own definition by its own pass.
    """

    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    for row in objects:
        children_by_parent.setdefault(
            str(row.get("parent_id") or ""),
            [],
        ).append(row)
    for rows in children_by_parent.values():
        rows.sort(
            key=lambda item: (
                int(item.get("z_index") or 0),
                str(item.get("id") or ""),
            )
        )

    def paired(
        instance_id: str,
        definition_id: str,
    ) -> list[tuple[dict[str, Any], dict[str, Any]]] | None:
        instance_rows = children_by_parent.get(instance_id, [])
        definition_rows = children_by_parent.get(definition_id, [])
        if len(instance_rows) != len(definition_rows):
            return None
        pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for instance_row, definition_row in zip(instance_rows, definition_rows):
            if str(instance_row.get("kind") or "") != str(
                definition_row.get("kind") or ""
            ):
                return None
            pairs.append((instance_row, definition_row))
            if str(instance_row.get("component_role") or "") == "instance":
                continue
            nested = paired(
                str(instance_row.get("id") or ""),
                str(definition_row.get("id") or ""),
            )
            if nested is None:
                return None
            pairs.extend(nested)
        return pairs

    for row in objects:
        if str(row.get("component_role") or "") != "instance":
            continue
        definition_id = str(row.get("component_source_object_id") or "")
        if not definition_id or definition_id not in objects_by_id:
            continue
        pairs = paired(str(row.get("id") or ""), definition_id)
        if pairs is None:
            warnings.append(
                f"unlinked:{row['id']}"
                ":instance_subtree_shape_differs_from_definition"
            )
            continue
        component_id = str(row.get("component_id") or "")
        for instance_row, definition_row in pairs:
            definition_object_id = str(definition_row.get("id") or "")
            if not str(instance_row.get("component_source_object_id") or ""):
                instance_row["component_source_object_id"] = (
                    definition_object_id
                )
                continue
            # A definition row of an enclosing component already points at
            # itself, which is correct for that component. Its link to the
            # nested component it also belongs to is the scope pair, and
            # leaving it empty is what made a nested instance replay the
            # nested default instead of the value authored one level up.
            # The scope pair only means something when the row belongs to some
            # other component as well; a scope equal to the row's own component
            # is rejected as redundant by the document contract.
            if (
                component_id
                and str(instance_row.get("component_id") or "") != component_id
                and not str(instance_row.get("component_scope_id") or "")
                and not str(
                    instance_row.get("component_scope_source_object_id") or ""
                )
                and instance_row.get("component_source_object_id")
                != definition_object_id
            ):
                instance_row["component_scope_id"] = component_id
                instance_row["component_scope_source_object_id"] = (
                    definition_object_id
                )


def _figma_variant_key(node: Mapping[str, Any]) -> str:
    properties = node.get("variantProperties")
    if isinstance(properties, Mapping) and properties:
        return ", ".join(
            f"{_figma_property_name(name)}={value}"
            for name, value in properties.items()
        )
    return str(node.get("name") or "")


def _figma_variant_source_map(node: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}

    def visit(current: Mapping[str, Any], path: str) -> None:
        result[path] = _figma_node_stable_id(current)
        child_index = 0
        for child in current.get("children", []):
            if not isinstance(child, Mapping):
                continue
            visit(child, f"{path}/{child_index}")
            child_index += 1

    visit(node, "root")
    return result


def _figma_component_set_index(
    root: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    def visit(node: Mapping[str, Any]) -> None:
        if str(node.get("type") or "").upper() == "COMPONENT_SET":
            children = [
                child
                for child in node.get("children", [])
                if isinstance(child, Mapping)
                and str(child.get("type") or "").upper() == "COMPONENT"
            ]
            component_ids = [_figma_component_stable_id(child) for child in children]
            family_id = (
                _tigerstudio_plugin_text(node, "component_family_id")
                or (component_ids[0] if component_ids else "")
            )
            set_row = {
                "figma_node_id": str(node.get("id") or ""),
                "name": str(node.get("name") or "Component Set"),
                "family_id": family_id,
                "component_ids": component_ids,
                "property_definitions": _figma_component_property_definitions(
                    node.get("componentPropertyDefinitions")
                ),
            }
            for child in children:
                index[str(child.get("id") or "")] = set_row
        for child in node.get("children", []):
            if isinstance(child, Mapping):
                visit(child)

    visit(root)
    return index


def _walk_figma_nodes(
    root: Mapping[str, Any],
):
    yield root
    for child in root.get("children", []):
        if isinstance(child, Mapping):
            yield from _walk_figma_nodes(child)


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _color(value: object, default: str = "#00000000") -> str:
    if not isinstance(value, Mapping):
        return default
    channels = [
        max(0, min(255, round(_number(value.get(key)) * 255)))
        for key in ("r", "g", "b", "a")
    ]
    if "a" not in value:
        channels[3] = 255
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def _solid_paint(paints: object) -> Mapping[str, Any] | None:
    if not isinstance(paints, list):
        return None
    return next(
        (
            row
            for row in paints
            if isinstance(row, Mapping)
            and row.get("visible", True)
            and str(row.get("type") or "").upper() == "SOLID"
        ),
        None,
    )


def _gradient_paint(paints: object) -> Mapping[str, Any] | None:
    if not isinstance(paints, list):
        return None
    return next(
        (
            row
            for row in paints
            if isinstance(row, Mapping)
            and row.get("visible", True)
            and str(row.get("type") or "").upper()
            in {"GRADIENT_LINEAR", "GRADIENT_RADIAL"}
        ),
        None,
    )


def _figma_paint_is_opaque_alpha_cover(paint: Mapping[str, Any]) -> bool:
    """Return whether one visible Figma fill is opaque over the whole shape."""

    if not bool(paint.get("visible", True)):
        return False
    paint_opacity = max(
        0.0,
        min(1.0, _number(paint.get("opacity"), 1.0)),
    )
    paint_type = str(paint.get("type") or "").upper()
    if paint_type == "SOLID":
        color = paint.get("color")
        color = color if isinstance(color, Mapping) else {}
        return paint_opacity * _number(color.get("a"), 1.0) >= 0.999
    if paint_type.startswith("GRADIENT_"):
        stops = paint.get("gradientStops")
        if not isinstance(stops, list) or not stops:
            return False
        return all(
            isinstance(stop, Mapping)
            and paint_opacity
            * _number(
                (
                    stop.get("color")
                    if isinstance(stop.get("color"), Mapping)
                    else {}
                ).get("a"),
                1.0,
            )
            >= 0.999
            for stop in stops
        )
    # Image alpha and plugin paint extensions require raster evaluation even
    # when their current thumbnail happens to look opaque.
    return False


def _figma_mask_requires_raster_alpha(node: Mapping[str, Any]) -> bool:
    """Detect masks that cannot be represented by a hard geometry clip.

    Painter's current live canvas can safely inherit a vector/shape clip down
    a target subtree.  It cannot yet composite per-pixel alpha or luminance for
    the complete sibling group, so preserve that distinction instead of
    claiming a gradient alpha mask was converted exactly.
    """

    mask_type = str(node.get("maskType") or "ALPHA").upper()
    if mask_type == "VECTOR":
        return False
    if mask_type == "LUMINANCE":
        return True
    if _number(node.get("opacity"), 1.0) < 0.999:
        return True
    effects = node.get("effects")
    if isinstance(effects, list) and any(
        isinstance(effect, Mapping) and bool(effect.get("visible", True))
        for effect in effects
    ):
        return True
    strokes = node.get("strokes")
    if (
        isinstance(strokes, list)
        and _number(node.get("strokeWeight"), 1.0) > 0.0
        and any(
            isinstance(stroke, Mapping) and bool(stroke.get("visible", True))
            for stroke in strokes
        )
    ):
        return True
    fills = node.get("fills")
    visible_fills = [
        paint
        for paint in fills
        if isinstance(paint, Mapping) and bool(paint.get("visible", True))
    ] if isinstance(fills, list) else []
    return not any(
        _figma_paint_is_opaque_alpha_cover(paint)
        for paint in visible_fills
    )


def _color_with_opacity(value: object, opacity: object = 1.0) -> str:
    color = _color(value)
    alpha = int(color[7:9], 16)
    alpha = round(alpha * max(0.0, min(1.0, _number(opacity, 1.0))))
    return f"{color[:7]}{max(0, min(255, alpha)):02X}"


def _map_gradient(paint: Mapping[str, Any]) -> dict[str, Any]:
    handles = (
        paint.get("gradientHandlePositions")
        if isinstance(paint.get("gradientHandlePositions"), list)
        else []
    )

    def point(index: int, fallback: tuple[float, float]) -> dict[str, float]:
        value = handles[index] if index < len(handles) else {}
        value = value if isinstance(value, Mapping) else {}
        return {
            "x": _number(value.get("x"), fallback[0]),
            "y": _number(value.get("y"), fallback[1]),
        }

    raw_stops = (
        paint.get("gradientStops")
        if isinstance(paint.get("gradientStops"), list)
        else []
    )
    stops = sorted(
        (
            {
                "position": max(
                    0.0,
                    min(1.0, _number(stop.get("position"))),
                ),
                # Figma paint opacity is independent from each stop's alpha.
                # Preserve the stop color verbatim and keep paint opacity on
                # the canonical paint row so render/export applies it once.
                "color": _color(stop.get("color")),
            }
            for stop in raw_stops
            if isinstance(stop, Mapping)
        ),
        key=lambda row: row["position"],
    )
    if not stops:
        stops = [
            {"position": 0.0, "color": "#000000FF"},
            {"position": 1.0, "color": "#00000000"},
        ]
    return {
        "type": (
            "radial"
            if str(paint.get("type") or "").upper() == "GRADIENT_RADIAL"
            else "linear"
        ),
        "start": point(0, (0.0, 0.5)),
        "end": point(1, (1.0, 0.5)),
        "width": point(2, (0.0, 1.0)),
        "stops": stops,
    }


def _image_paint(paints: object) -> Mapping[str, Any] | None:
    if not isinstance(paints, list):
        return None
    return next(
        (
            row
            for row in paints
            if isinstance(row, Mapping)
            and row.get("visible", True)
            and str(row.get("type") or "").upper() == "IMAGE"
        ),
        None,
    )


def _map_paints(
    paints: object,
    *,
    stroke: bool = False,
    width: float = 1.0,
    align: str = "center",
) -> list[dict[str, Any]]:
    if not isinstance(paints, list):
        return []
    rows: list[dict[str, Any]] = []
    for raw in paints:
        if not isinstance(raw, Mapping):
            continue
        paint_type = str(raw.get("type") or "").upper()
        if paint_type == "SOLID":
            row: dict[str, Any] = {
                "type": "solid",
                "visible": bool(raw.get("visible", True)),
                "opacity": max(
                    0.0, min(1.0, _number(raw.get("opacity"), 1.0))
                ),
                # Keep color alpha and paint opacity as separate factors.
                "color": _color(raw.get("color")),
            }
        elif paint_type in {"GRADIENT_LINEAR", "GRADIENT_RADIAL"}:
            gradient = _map_gradient(raw)
            row = {
                "type": gradient["type"],
                "visible": bool(raw.get("visible", True)),
                "opacity": max(
                    0.0, min(1.0, _number(raw.get("opacity"), 1.0))
                ),
                "color": "#FFFFFFFF",
                "gradient": gradient,
            }
        elif paint_type == "IMAGE":
            scale_mode = str(raw.get("scaleMode") or "FILL").upper()
            filters = (
                raw.get("filters")
                if isinstance(raw.get("filters"), Mapping)
                else {}
            )

            def adjustment(name: str) -> float:
                value = _number(filters.get(name), 0.0)
                # Figma's REST/plugin image filters use normalized -1..1
                # values; Painter stores the same controls as -100..100.
                if abs(value) <= 1.0:
                    value *= 100.0
                return max(-100.0, min(100.0, value))

            row = {
                "type": "image",
                "visible": bool(raw.get("visible", True)),
                "opacity": max(
                    0.0, min(1.0, _number(raw.get("opacity"), 1.0))
                ),
                "color": "#FFFFFFFF",
                "blend_mode": str(
                    raw.get("blendMode") or "NORMAL"
                ).casefold(),
                # The resolved local asset lives in object content. Keeping
                # this field empty lets the provider-neutral adapter merge
                # paint opacity/filters with content.source_path.
                "source_path": "",
                "fit": {
                    "FIT": "fit",
                    "FILL": "fill",
                    "STRETCH": "stretch",
                    "TILE": "tile",
                    "CROP": "crop",
                }.get(scale_mode, "fill"),
                "rotation": _number(raw.get("rotation"), 0.0),
                "tile_scale": max(
                    0.05,
                    min(16.0, _number(raw.get("scalingFactor"), 1.0)),
                ),
                "adjustments": {
                    key: adjustment(key)
                    for key in (
                        "exposure",
                        "contrast",
                        "saturation",
                        "temperature",
                        "tint",
                        "highlights",
                        "shadows",
                    )
                },
            }
            image_transform = raw.get("imageTransform")
            if isinstance(image_transform, list):
                # A Figma crop transform is not equivalent to a normalized UV
                # rectangle in all cases (it may rotate/skew). Preserve it for
                # inspection; CROP remains explicitly blocked until a safe
                # rectangular crop can be supplied.
                row["figma_image_transform"] = copy.deepcopy(image_transform)
        else:
            continue
        if stroke:
            row["width"] = max(0.0, float(width))
            row["align"] = str(align).casefold()
        rows.append(row)
    return rows


def map_figma_plugin_paints(
    paints: object,
    *,
    stroke: bool = False,
    width: float = 1.0,
    align: str = "center",
) -> list[dict[str, Any]]:
    """Map public Plugin API Paint rows through the canonical Figma importer."""
    return _map_paints(paints, stroke=stroke, width=width, align=align)


def _map_text_ranges(node: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = str(node.get("characters") or "")
    overrides = node.get("characterStyleOverrides")
    table = node.get("styleOverrideTable")
    if not text or not isinstance(overrides, list) or not isinstance(table, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    start = 0
    while start < min(len(text), len(overrides)):
        style_id = str(overrides[start])
        end = start + 1
        while end < min(len(text), len(overrides)) and str(
            overrides[end]
        ) == style_id:
            end += 1
        raw = table.get(style_id)
        if style_id not in {"0", ""} and isinstance(raw, Mapping):
            style: dict[str, Any] = {}
            field_map = {
                "fontFamily": "font_family",
                "fontSize": "font_size",
                "fontWeight": "font_weight",
                "italic": "italic",
                "textDecoration": "underline",
                "letterSpacing": "letter_spacing",
                "lineHeightPx": "line_height",
            }
            for figma_key, target_key in field_map.items():
                if figma_key not in raw:
                    continue
                value = raw[figma_key]
                if figma_key == "textDecoration":
                    value = str(value).upper() == "UNDERLINE"
                style[target_key] = copy.deepcopy(value)
            if "lineHeightPx" in raw:
                style["line_height_unit"] = "px"
            fill = _solid_paint(raw.get("fills"))
            if fill is not None:
                style["color"] = _color_with_opacity(
                    fill.get("color"),
                    fill.get("opacity", 1.0),
                )
            if style:
                rows.append({"start": start, "end": end, "style": style})
        start = end
    return rows


def _box(node: Mapping[str, Any]) -> dict[str, float]:
    value = node.get("absoluteBoundingBox")
    value = value if isinstance(value, Mapping) else {}
    return {
        "x": _number(value.get("x")),
        "y": _number(value.get("y")),
        "width": max(1.0, _number(value.get("width"), 160.0)),
        "height": max(1.0, _number(value.get("height"), 64.0)),
    }


def _figma_missing_auto_layout_cross_box(
    node: Mapping[str, Any],
) -> tuple[dict[str, float], dict[str, Any]]:
    """Conservatively infer one missing Auto Layout cross-axis bound.

    Some component/node snapshots omit a container ``absoluteBoundingBox``
    while retaining resolved bounds for one or more direct flow children.
    For center-aligned children with a common center (or start/end aligned
    children with a common edge), the smallest content box plus authored
    padding is a deterministic inverse of Figma's layout result.  The main
    axis remains untouched because fill/space distribution is ambiguous.
    """

    fallback = _box(node)
    if isinstance(node.get("absoluteBoundingBox"), Mapping):
        return fallback, {}
    mode = str(node.get("layoutMode") or "").upper()
    if mode not in {"HORIZONTAL", "VERTICAL"}:
        return fallback, {}
    cross_position = "y" if mode == "HORIZONTAL" else "x"
    cross_size = "height" if mode == "HORIZONTAL" else "width"
    leading_key = "paddingTop" if mode == "HORIZONTAL" else "paddingLeft"
    trailing_key = (
        "paddingBottom" if mode == "HORIZONTAL" else "paddingRight"
    )
    children = [
        child
        for child in node.get("children", [])
        if isinstance(child, Mapping)
        and bool(child.get("visible", True))
        and str(child.get("layoutPositioning") or "").upper() != "ABSOLUTE"
        and isinstance(child.get("absoluteBoundingBox"), Mapping)
    ]
    if not children:
        return fallback, {}
    child_boxes = [_box(child) for child in children]
    starts = [box[cross_position] for box in child_boxes]
    sizes = [box[cross_size] for box in child_boxes]
    ends = [start + size for start, size in zip(starts, sizes)]
    leading = max(0.0, _number(node.get(leading_key)))
    trailing = max(0.0, _number(node.get(trailing_key)))
    alignment = str(node.get("counterAxisAlignItems") or "MIN").upper()
    tolerance = 0.5
    inferred_start: float | None = None
    if alignment == "CENTER":
        centers = [start + size * 0.5 for start, size in zip(starts, sizes)]
        if max(centers) - min(centers) > tolerance:
            return fallback, {}
        content_size = max(sizes)
        inferred_start = (
            sum(centers) / len(centers) - content_size * 0.5 - leading
        )
    elif alignment == "MAX":
        if max(ends) - min(ends) > tolerance:
            return fallback, {}
        content_size = max(sizes)
        inferred_start = max(ends) + trailing - (
            leading + content_size + trailing
        )
    elif alignment == "MIN":
        if max(starts) - min(starts) > tolerance:
            return fallback, {}
        content_size = max(sizes)
        inferred_start = min(starts) - leading
    else:
        # BASELINE needs font ascent data (or the sibling recovery stored by
        # the baseline importer) and is intentionally not guessed here.
        return fallback, {}
    inferred_size = leading + content_size + trailing
    if inferred_size <= 0.0 or inferred_start is None:
        return fallback, {}
    fallback[cross_position] = float(inferred_start)
    fallback[cross_size] = float(inferred_size)
    return fallback, {
        "status": "cross_axis_inferred",
        "reason": "missing_absolute_bounding_box",
        "axis": cross_size,
        "alignment": alignment.casefold(),
        "evidence_child_ids": [
            str(child.get("id") or "") for child in children
        ],
        "inferred_position": float(inferred_start),
        "inferred_size": float(inferred_size),
    }


def _map_kind(node: Mapping[str, Any]) -> str:
    node_type = str(node.get("type") or "").upper()
    if node_type in {
        "FRAME",
        "SECTION",
        "COMPONENT",
        "COMPONENT_SET",
        "SLOT",
        # An instance is frame-like in Figma: it paints its own fills, clips,
        # and carries auto layout.  Treating it as a group dropped the fill -
        # invisible while instances imported empty, obvious once their children
        # arrived and the button behind them had no background.
        "INSTANCE",
    }:
        return "frame"
    if node_type == "GROUP":
        return "group"
    if node_type == "ELLIPSE":
        return "ellipse"
    if node_type == "LINE":
        return "line"
    if node_type == "TEXT":
        return "text"
    if node_type in {
        "VECTOR",
        "BOOLEAN_OPERATION",
        "STAR",
        "POLYGON",
        "REGULAR_POLYGON",
    }:
        return "path"
    if _image_paint(node.get("fills")) is not None:
        return "image"
    return "rectangle"


def _figma_axis_sizing(
    node: Mapping[str, Any],
    *,
    axis: str,
    own_layout_mode: str,
    parent_layout_mode: str,
) -> str:
    modern_key = (
        "layoutSizingHorizontal"
        if axis == "width"
        else "layoutSizingVertical"
    )
    modern = str(node.get(modern_key) or "").upper()
    if modern in {"FIXED", "HUG", "FILL"}:
        return modern.casefold()

    if own_layout_mode in {"horizontal", "vertical"}:
        primary_axis = (
            axis == "width" and own_layout_mode == "horizontal"
        ) or (
            axis == "height" and own_layout_mode == "vertical"
        )
        legacy_key = (
            "primaryAxisSizingMode"
            if primary_axis
            else "counterAxisSizingMode"
        )
        legacy = str(node.get(legacy_key) or "").upper()
        if legacy == "AUTO":
            return "hug"
        if legacy == "FIXED":
            return "fixed"

    main_axis = (
        "width" if parent_layout_mode == "horizontal" else "height"
    )
    cross_axis = (
        "height" if parent_layout_mode == "horizontal" else "width"
    )
    if (
        parent_layout_mode in {"horizontal", "vertical"}
        and axis == main_axis
        and _number(node.get("layoutGrow")) > 0.0
    ):
        return "fill"
    if (
        parent_layout_mode in {"horizontal", "vertical"}
        and axis == cross_axis
        and str(node.get("layoutAlign") or "").upper() == "STRETCH"
    ):
        return "fill"
    return "fixed"


def _figma_layout_stroke_edges(
    node: Mapping[str, Any],
) -> dict[str, float]:
    """Return visible per-edge stroke widths used by Figma Auto Layout."""

    paints = node.get("strokes")
    if not isinstance(paints, list) or not any(
        isinstance(paint, Mapping)
        and bool(paint.get("visible", True))
        and _number(paint.get("opacity"), 1.0) > 0.0
        for paint in paints
    ):
        return {edge: 0.0 for edge in ("left", "top", "right", "bottom")}
    width = max(0.0, _number(node.get("strokeWeight")))
    individual = node.get("individualStrokeWeights")
    individual = individual if isinstance(individual, Mapping) else {}
    return {
        edge: max(0.0, _number(individual.get(edge), width))
        for edge in ("left", "top", "right", "bottom")
    }


def _figma_layout_stroke_insets(
    node: Mapping[str, Any],
) -> dict[str, float]:
    align = str(node.get("strokeAlign") or "CENTER").upper()
    factor = {"INSIDE": 1.0, "CENTER": 0.5}.get(align, 0.0)
    return {
        edge: width * factor
        for edge, width in _figma_layout_stroke_edges(node).items()
    }


def _figma_layout_stroke_outsets(
    node: Mapping[str, Any],
) -> dict[str, float]:
    align = str(node.get("strokeAlign") or "CENTER").upper()
    factor = {"OUTSIDE": 1.0, "CENTER": 0.5}.get(align, 0.0)
    return {
        edge: width * factor
        for edge, width in _figma_layout_stroke_edges(node).items()
    }


def _map_layout(
    node: Mapping[str, Any],
    *,
    parent_layout_mode: str = "none",
) -> dict[str, Any]:
    mode = str(node.get("layoutMode") or "NONE").casefold()
    mode = mode if mode in {"horizontal", "vertical"} else "none"
    main = {
        "min": "start",
        "center": "center",
        "max": "end",
        "space_between": "space_between",
    }.get(str(node.get("primaryAxisAlignItems") or "MIN").casefold(), "start")
    cross = {
        "min": "start",
        "center": "center",
        "max": "end",
        "baseline": "baseline",
    }.get(str(node.get("counterAxisAlignItems") or "MIN").casefold(), "start")
    layout = {
        "mode": mode,
        "padding": {
            "left": _number(node.get("paddingLeft")),
            "top": _number(node.get("paddingTop")),
            "right": _number(node.get("paddingRight")),
            "bottom": _number(node.get("paddingBottom")),
        },
        # Figma explicitly permits negative itemSpacing for overlapping
        # Auto Layout children. Do not clamp it to a conventional CSS gap.
        "gap": _number(node.get("itemSpacing")),
        "cross_gap": max(
            0.0,
            _number(
                node.get("counterAxisSpacing"),
                _number(node.get("itemSpacing")),
            ),
        ),
        "main_alignment": main,
        "cross_alignment": cross,
        "wrap": str(node.get("layoutWrap") or "").upper() == "WRAP",
        "width_sizing": _figma_axis_sizing(
            node,
            axis="width",
            own_layout_mode=mode,
            parent_layout_mode=parent_layout_mode,
        ),
        "height_sizing": _figma_axis_sizing(
            node,
            axis="height",
            own_layout_mode=mode,
            parent_layout_mode=parent_layout_mode,
        ),
        "positioning": (
            "absolute"
            if str(node.get("layoutPositioning") or "").upper() == "ABSOLUTE"
            else "auto"
        ),
    }
    if bool(node.get("itemReverseZIndex", False)):
        # Figma defines this as paint stacking only; flow order remains the
        # REST children order and is intentionally handled independently.
        layout["reverse_z_index"] = True
    if bool(node.get("strokesIncludedInLayout", False)):
        # Keep this authored semantic explicit.  Figma counts the container's
        # inward stroke and each child's outward stroke footprint when it
        # measures and places Auto Layout content.
        layout["include_strokes"] = True
        stroke_insets = _figma_layout_stroke_insets(node)
        if any(stroke_insets.values()):
            layout["stroke_insets"] = stroke_insets
    stroke_outsets = _figma_layout_stroke_outsets(node)
    if any(stroke_outsets.values()):
        layout["stroke_outsets"] = stroke_outsets
    return layout


def _figma_resolved_child_baseline_offsets(
    node: Mapping[str, Any],
) -> dict[str, float]:
    """Recover direct-child baseline metrics from resolved Figma geometry.

    Figma REST/archive nodes expose ``counterAxisAlignItems=BASELINE`` and the
    final child bounds, but not each font's ascent.  All participating boxes
    nevertheless share one baseline.  Choosing any line in the intersection
    of their cross-axis bounds yields the exact relative offsets; the nearest
    common trailing edge keeps every stored offset inside its child box.
    """

    if (
        str(node.get("layoutMode") or "").upper() != "HORIZONTAL"
        or str(node.get("counterAxisAlignItems") or "").upper()
        != "BASELINE"
    ):
        return {}
    children = [
        child
        for child in node.get("children", [])
        if isinstance(child, Mapping)
        and bool(child.get("visible", True))
        and str(child.get("layoutPositioning") or "").upper() != "ABSOLUTE"
        and isinstance(child.get("absoluteBoundingBox"), Mapping)
    ]
    if not children:
        return {}
    starts = [_box(child)["y"] for child in children]
    ends = [_box(child)["y"] + _box(child)["height"] for child in children]
    common_start = max(starts)
    common_end = min(ends)
    baseline = common_end if common_end >= common_start else common_start
    return {
        str(child.get("id") or ""): max(0.0, baseline - _box(child)["y"])
        for child in children
        if str(child.get("id") or "")
    }


_FIGMA_LAYOUT_GEOMETRY_EPSILON = 0.5
_FIGMA_AFFINE_EPSILON = 0.0001
# A rotation dragged/edited by hand in Figma can serialize with a==d and
# b==-c off by ~1e-3 even though it is a pure rotation - the tight epsilon
# above rejected those as sheared and fell back to the (larger) unrotated
# bounding box with no rotation applied, which is what visibly shifted a
# rotated Boolean operand (a hexagon rotated ~30 degrees) off to one side
# instead of leaving it, at worst, a fraction of a percent off-shape.
_FIGMA_AFFINE_ORTHOGONALITY_EPSILON = 0.01
_FIGMA_AUTO_LAYOUT_RECOVERY_FIELDS = (
    "layoutMode",
    "layoutWrap",
    "layoutSizingHorizontal",
    "layoutSizingVertical",
    "primaryAxisSizingMode",
    "counterAxisSizingMode",
    "primaryAxisAlignItems",
    "counterAxisAlignItems",
    "itemSpacing",
    "counterAxisSpacing",
    "paddingLeft",
    "paddingTop",
    "paddingRight",
    "paddingBottom",
    "layoutPositioning",
    "layoutGrow",
    "layoutAlign",
    "minWidth",
    "minHeight",
    "maxWidth",
    "maxHeight",
)


def _figma_size_aabb_diverges(node: Mapping[str, Any]) -> bool:
    """Return whether local layout size and transformed canvas AABB disagree."""

    size = node.get("size")
    bounds = node.get("absoluteBoundingBox")
    if not isinstance(size, Mapping) or not isinstance(bounds, Mapping):
        return False
    local_width = _number(size.get("x"))
    local_height = _number(size.get("y"))
    bounds_width = _number(bounds.get("width"))
    bounds_height = _number(bounds.get("height"))
    if min(local_width, local_height, bounds_width, bounds_height) < 0.0:
        return False
    return max(
        abs(local_width - bounds_width),
        abs(local_height - bounds_height),
    ) > _FIGMA_LAYOUT_GEOMETRY_EPSILON


def _figma_has_non_translation_transform(node: Mapping[str, Any]) -> bool:
    """Detect rotation, scale, reflection, or shear in a Figma affine matrix."""

    transform = node.get("relativeTransform")
    if (
        isinstance(transform, list)
        and len(transform) >= 2
        and isinstance(transform[0], list)
        and isinstance(transform[1], list)
        and len(transform[0]) >= 2
        and len(transform[1]) >= 2
    ):
        a = _number(transform[0][0], 1.0)
        c = _number(transform[0][1])
        b = _number(transform[1][0])
        d = _number(transform[1][1], 1.0)
        if max(
            abs(a - 1.0),
            abs(b),
            abs(c),
            abs(d - 1.0),
        ) > _FIGMA_AFFINE_EPSILON:
            return True
    return abs(_number(node.get("rotation"))) > _FIGMA_AFFINE_EPSILON


_FIGMA_IDENTITY_LINEAR_TRANSFORM = (1.0, 0.0, 0.0, 1.0)


def _figma_legacy_text_rotation_is_radian_quarter_turn(
    node: Mapping[str, Any],
) -> bool:
    """Recognize a narrow legacy REST text-rotation convention.

    A few old ``/nodes`` snapshots serialize an intrinsic auto-width text
    node's quarter turn in radians while omitting both ``size`` and
    ``relativeTransform``.  Require the exact quarter-turn marker and the
    independent line-height/AABB evidence so an ordinary authored 1.57-degree
    rotation is never guessed to be 90 degrees.
    """

    if (
        str(node.get("type") or "").upper() != "TEXT"
        or isinstance(node.get("relativeTransform"), list)
    ):
        return False
    rotation = _number(node.get("rotation"))
    if abs(abs(rotation) - math.pi / 2.0) > _FIGMA_AFFINE_EPSILON:
        return False
    style = node.get("style")
    style = style if isinstance(style, Mapping) else {}
    if str(style.get("textAutoResize") or "").upper() != "WIDTH_AND_HEIGHT":
        return False
    line_height = _number(style.get("lineHeightPx"))
    bounds = node.get("absoluteBoundingBox")
    bounds = bounds if isinstance(bounds, Mapping) else {}
    rotated_height = _number(bounds.get("width"))
    tolerance = max(1.0, line_height * 0.01)
    return line_height > 0.0 and abs(rotated_height - line_height) <= tolerance


def _figma_rotation_degrees(node: Mapping[str, Any]) -> float:
    rotation = _number(node.get("rotation"))
    if _figma_legacy_text_rotation_is_radian_quarter_turn(node):
        return math.degrees(rotation)
    return rotation


def _figma_node_linear_transform(
    node: Mapping[str, Any],
) -> tuple[float, float, float, float]:
    """Return Figma's 2x2 linear transform as ``a, c, b, d``."""

    transform = node.get("relativeTransform")
    if (
        isinstance(transform, list)
        and len(transform) >= 2
        and isinstance(transform[0], list)
        and isinstance(transform[1], list)
        and len(transform[0]) >= 2
        and len(transform[1]) >= 2
    ):
        return (
            _number(transform[0][0], 1.0),
            _number(transform[0][1]),
            _number(transform[1][0]),
            _number(transform[1][1], 1.0),
        )
    # Standard REST snapshots express this fallback rotation in degrees. A
    # tightly identified legacy intrinsic-text quarter turn is converted by
    # the helper above.
    angle = math.radians(_figma_rotation_degrees(node))
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return (cosine, -sine, sine, cosine)


def _multiply_figma_linear_transforms(
    parent: tuple[float, float, float, float],
    child: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    pa, pc, pb, pd = parent
    ca, cc, cb, cd = child
    return (
        pa * ca + pc * cb,
        pa * cc + pc * cd,
        pb * ca + pd * cb,
        pb * cc + pd * cd,
    )


def _figma_outer_affine_issue(
    transform: tuple[float, float, float, float],
) -> str:
    a, c, b, d = transform
    if max(abs(a - 1.0), abs(b), abs(c), abs(d - 1.0)) <= _FIGMA_AFFINE_EPSILON:
        return ""
    scale_x = math.hypot(a, b)
    scale_y = math.hypot(c, d)
    determinant = a * d - b * c
    orthogonality = (
        abs(a * c + b * d) / max(_FIGMA_AFFINE_EPSILON, scale_x * scale_y)
    )
    if determinant < 0.0:
        return "outer_affine_snapshot_requires_reflection_support"
    if orthogonality > _FIGMA_AFFINE_EPSILON:
        return "outer_affine_snapshot_requires_shear_support"
    return "outer_affine_snapshot_requires_hierarchical_transform_support"


def _figma_linear_transform_is_identity(
    transform: tuple[float, float, float, float],
) -> bool:
    a, c, b, d = transform
    return max(
        abs(a - 1.0),
        abs(b),
        abs(c),
        abs(d - 1.0),
    ) <= _FIGMA_AFFINE_EPSILON


def _figma_affine_snapshot_geometry(
    node: Mapping[str, Any],
    effective_linear: tuple[float, float, float, float],
) -> tuple[dict[str, float], float, dict[str, Any]]:
    """Map a cumulative orthogonal affine transform to Painter geometry.

    Painter stores a center-pivot rectangle plus one rotation, while Figma
    stores local size and a hierarchical affine matrix. Rotation with positive
    scales is representable. Reflection, shear, and missing local dimensions
    remain an explicit blocker with the exact matrix retained for recovery.
    """

    bounds = _box(node)
    size = node.get("size")
    a, c, b, d = effective_linear
    scale_x = math.hypot(a, b)
    scale_y = math.hypot(c, d)
    determinant = a * d - b * c
    orthogonality = (
        abs(a * c + b * d) / max(_FIGMA_AFFINE_EPSILON, scale_x * scale_y)
    )
    metadata: dict[str, Any] = {
        "effective_linear_transform": [[a, c], [b, d]],
        "relative_transform": copy.deepcopy(node.get("relativeTransform")),
        "source_size": copy.deepcopy(size),
        "source_absolute_bounding_box": copy.deepcopy(
            node.get("absoluteBoundingBox")
        ),
    }
    source_bounds = node.get("absoluteBoundingBox")
    source_bounds = (
        source_bounds if isinstance(source_bounds, Mapping) else {}
    )
    source_x = _number(source_bounds.get("x"), bounds["x"])
    source_y = _number(source_bounds.get("y"), bounds["y"])
    source_width = max(
        0.0,
        _number(source_bounds.get("width"), bounds["width"]),
    )
    source_height = max(
        0.0,
        _number(source_bounds.get("height"), bounds["height"]),
    )
    center_x = source_x + source_width * 0.5
    center_y = source_y + source_height * 0.5
    rotation = math.degrees(math.atan2(b, a))
    cosine = abs(math.cos(math.radians(rotation)))
    sine = abs(math.sin(math.radians(rotation)))
    if not isinstance(size, Mapping):
        quarter_turn = min(cosine, sine) <= _FIGMA_AFFINE_EPSILON
        if (
            quarter_turn
            and source_width > _FIGMA_AFFINE_EPSILON
            and source_height > _FIGMA_AFFINE_EPSILON
            and scale_x > _FIGMA_AFFINE_EPSILON
            and scale_y > _FIGMA_AFFINE_EPSILON
            and determinant > _FIGMA_AFFINE_EPSILON
            and orthogonality <= _FIGMA_AFFINE_EPSILON
        ):
            width = source_height if sine > cosine else source_width
            height = source_width if sine > cosine else source_height
            metadata.update(
                {
                    "status": "rotation_scale_mapped",
                    "scale_x": scale_x,
                    "scale_y": scale_y,
                    "rotation": rotation,
                    "missing_local_size_recovery": (
                        "quarter_turn_aabb_inverse"
                    ),
                }
            )
            if _figma_legacy_text_rotation_is_radian_quarter_turn(node):
                metadata["source_rotation_unit_recovery"] = (
                    "legacy_radians_inferred_from_text_line_height"
                )
            return (
                {
                    "x": center_x - width * 0.5,
                    "y": center_y - height * 0.5,
                    "width": width,
                    "height": height,
                },
                rotation,
                metadata,
            )
        metadata.update(
            {
                "status": "blocked_missing_local_size",
                "reason": "figma_affine_snapshot_requires_local_size",
            }
        )
        return bounds, 0.0, metadata
    local_width = _number(size.get("x"))
    local_height = _number(size.get("y"))
    near_zero_negative_axes: dict[str, float] = {}
    if -_FIGMA_AFFINE_EPSILON <= local_width < 0.0:
        near_zero_negative_axes["width"] = local_width
        local_width = 0.0
    if -_FIGMA_AFFINE_EPSILON <= local_height < 0.0:
        near_zero_negative_axes["height"] = local_height
        local_height = 0.0
    if (
        local_width < 0.0
        or local_height < 0.0
        or scale_x <= _FIGMA_AFFINE_EPSILON
        or scale_y <= _FIGMA_AFFINE_EPSILON
        or determinant <= _FIGMA_AFFINE_EPSILON
        or orthogonality > _FIGMA_AFFINE_ORTHOGONALITY_EPSILON
    ):
        metadata.update(
            {
                "status": "blocked_non_orthogonal_affine",
                "reason": (
                    "figma_affine_snapshot_requires_shear_or_reflection_support"
                ),
                "determinant": determinant,
                "orthogonality_error": orthogonality,
            }
        )
        return bounds, 0.0, metadata
    scaled_width = local_width * scale_x
    scaled_height = local_height * scale_y
    width = max(1.0, scaled_width)
    height = max(1.0, scaled_height)
    # Keep the effective first basis-vector angle in Painter's stored Figma
    # convention. The workspace owns the Qt paint-transform sign conversion.
    # Painter's object contract intentionally keeps every editable extent at
    # least one pixel, while Figma commonly serializes a stroked line with a
    # zero local width or height.  Promoting that zero axis without adjusting
    # the orthogonal axis makes a rotated line's AABB larger than the source.
    # Fit the remaining extent by least squares against both source AABB axes;
    # this retains the authored transform and the 1 px edit handle without
    # moving the snapshot or inflating its other dimension.
    minimum_extent_adjustment: dict[str, Any] = {}
    if scaled_width <= _FIGMA_AFFINE_EPSILON < scaled_height:
        width = 1.0
        height = max(
            1.0,
            sine * (source_width - cosine * width)
            + cosine * (source_height - sine * width),
        )
        minimum_extent_adjustment = {
            "axis": "width",
            "source_scaled_extent": scaled_width,
            "mapped_extent": width,
            "orthogonal_mapped_extent": height,
            "strategy": "least_squares_source_aabb",
        }
    elif scaled_height <= _FIGMA_AFFINE_EPSILON < scaled_width:
        height = 1.0
        width = max(
            1.0,
            cosine * (source_width - sine * height)
            + sine * (source_height - cosine * height),
        )
        minimum_extent_adjustment = {
            "axis": "height",
            "source_scaled_extent": scaled_height,
            "mapped_extent": height,
            "orthogonal_mapped_extent": width,
            "strategy": "least_squares_source_aabb",
        }
    metadata.update(
        {
            "status": "rotation_scale_mapped",
            "scale_x": scale_x,
            "scale_y": scale_y,
            "rotation": rotation,
        }
    )
    if minimum_extent_adjustment:
        metadata["minimum_extent_adjustment"] = minimum_extent_adjustment
    if near_zero_negative_axes:
        metadata["near_zero_negative_local_size_clamped"] = (
            near_zero_negative_axes
        )
    return (
        {
            "x": center_x - width * 0.5,
            "y": center_y - height * 0.5,
            "width": width,
            "height": height,
        },
        rotation,
        metadata,
    )


def _figma_transformed_auto_layout_recovery(
    node: Mapping[str, Any],
    mapped_layout: Mapping[str, Any],
    *,
    parent_linear: tuple[float, float, float, float] = (
        _FIGMA_IDENTITY_LINEAR_TRANSFORM
    ),
) -> dict[str, Any]:
    """Preserve transformed Auto Layout as resolved snapshot geometry.

    Figma lays out transformed children using their local ``size`` while its
    REST ``absoluteBoundingBox`` is an axis-aligned canvas bound. Painter's
    current object contract has one width/height pair, so reflowing those AABB
    dimensions can move a resolved snapshot by tens of thousands of pixels.
    Until the document contract carries hierarchical affine layout geometry,
    keep the imported AABBs untouched and retain the source layout/transform
    data for a future editable relink.
    """

    if str(mapped_layout.get("mode") or "") not in {
        "horizontal",
        "vertical",
    }:
        return {}
    reasons: list[str] = []
    if _figma_outer_affine_issue(parent_linear):
        # A locally axis-aligned Auto Layout can still be reflected, rotated,
        # scaled, or sheared by an ancestor. Reflowing its absolute AABBs as
        # though that outer basis were identity reverses or distorts children.
        reasons.append("outer_affine_transform")
    if _figma_has_non_translation_transform(node):
        reasons.append("container_affine_transform")
    if _figma_size_aabb_diverges(node):
        reasons.append("container_local_size_differs_from_aabb")
    affected_children: list[str] = []
    for child in node.get("children", []):
        if not isinstance(child, Mapping):
            continue
        if not bool(child.get("visible", True)):
            continue
        if str(child.get("layoutPositioning") or "").upper() == "ABSOLUTE":
            continue
        child_reasons = (
            _figma_has_non_translation_transform(child)
            or _figma_size_aabb_diverges(child)
        )
        if not child_reasons:
            continue
        affected_children.append(str(child.get("id") or ""))
    if affected_children:
        reasons.append("flow_child_local_size_or_transform_differs_from_aabb")
    if not reasons:
        return {}
    return {
        "status": "snapshot_absolute_geometry",
        "reason": "transformed_auto_layout_requires_affine_layout",
        "reason_codes": reasons,
        "mapped_layout": copy.deepcopy(dict(mapped_layout)),
        "source_layout": {
            key: copy.deepcopy(node[key])
            for key in _FIGMA_AUTO_LAYOUT_RECOVERY_FIELDS
            if key in node
        },
        "relative_transform": copy.deepcopy(node.get("relativeTransform")),
        "size": copy.deepcopy(node.get("size")),
        "absolute_bounding_box": copy.deepcopy(
            node.get("absoluteBoundingBox")
        ),
        "affected_child_ids": affected_children,
    }


def _convert_figma_hug_fill_cycles(
    objects: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    """Resolve impossible Figma sizing pairs without moving any geometry.

    REST snapshots can contain a Hug auto-layout parent with an in-flow Fill
    child on the same axis. Tiger cannot solve that circular dependency. The
    snapshot already supplies a resolved absoluteBoundingBox for the parent,
    so make that parent axis Fixed and retain the child's Fill behavior. This
    changes only responsive sizing semantics; imported x/y/width/height stay
    exactly as resolved by Figma.
    """

    children: dict[str, list[dict[str, Any]]] = {}
    for row in objects:
        children.setdefault(str(row.get("parent_id") or ""), []).append(row)

    for parent in objects:
        layout = parent.get("layout")
        if not isinstance(layout, dict) or layout.get("mode") not in {
            "horizontal",
            "vertical",
        }:
            continue
        parent_id = str(parent.get("id") or "")
        direct_children = children.get(parent_id, [])
        for axis in ("width", "height"):
            sizing_key = f"{axis}_sizing"
            if layout.get(sizing_key) != "hug":
                continue
            conflicting_children = sorted(
                str(child.get("id") or "")
                for child in direct_children
                if isinstance(child.get("layout"), Mapping)
                and child["layout"].get("positioning") != "absolute"
                and child["layout"].get(sizing_key) == "fill"
            )
            if not conflicting_children:
                continue
            layout[sizing_key] = "fixed"
            warnings.append(
                f"converted:{parent_id}:layout.{sizing_key}:hug_to_fixed:"
                "figma_hug_fill_cycle_preserve_absolute_geometry:"
                + ",".join(conflicting_children)
            )


def _map_constraints(node: Mapping[str, Any]) -> dict[str, Any]:
    source = node.get("constraints")
    source = source if isinstance(source, Mapping) else {}
    horizontal = {
        "MIN": "left",
        "MAX": "right",
        "CENTER": "center",
        "STRETCH": "stretch",
        "SCALE": "scale",
    }.get(str(source.get("horizontal") or "MIN").upper(), "left")
    vertical = {
        "MIN": "top",
        "MAX": "bottom",
        "CENTER": "center",
        "STRETCH": "stretch",
        "SCALE": "scale",
    }.get(str(source.get("vertical") or "MIN").upper(), "top")
    box = _box(node)
    return {
        "horizontal": horizontal,
        "vertical": vertical,
        "min_width": max(1.0, _number(node.get("minWidth"), 1.0)),
        "min_height": max(1.0, _number(node.get("minHeight"), 1.0)),
        "preferred_width": box["width"],
        "preferred_height": box["height"],
        "max_width": max(0.0, _number(node.get("maxWidth"))),
        "max_height": max(0.0, _number(node.get("maxHeight"))),
    }


def _capture_figma_center_constraint_offsets(
    objects: list[dict[str, Any]],
    artboards: list[dict[str, Any]],
) -> None:
    """Preserve Figma CENTER constraints at their authored position.

    Figma's CENTER constraint keeps the child's offset from the parent center;
    the REST payload only names the constraint mode. Painter's resolver needs
    that offset serialized explicitly, otherwise every centered import snaps
    to the exact parent center on its first constraint pass.

    Imported object coordinates are artboard-local, including nested rows, so
    parent rows and the synthetic 0,0 artboard rect share one coordinate space.
    """

    objects_by_id = {str(row["id"]): row for row in objects}
    artboards_by_id = {str(row["id"]): row for row in artboards}
    for row in objects:
        constraints = row.get("constraints")
        if not isinstance(constraints, dict):
            continue
        horizontal_center = constraints.get("horizontal") == "center"
        vertical_center = constraints.get("vertical") == "center"
        if not horizontal_center and not vertical_center:
            continue
        parent_id = str(row.get("parent_id") or "")
        if parent_id:
            parent = objects_by_id.get(parent_id)
            if parent is None:
                continue
            parent_x = _number(parent.get("x"))
            parent_y = _number(parent.get("y"))
        else:
            parent = artboards_by_id.get(str(row.get("artboard_id") or ""))
            if parent is None:
                continue
            parent_x = 0.0
            parent_y = 0.0
        parent_width = _number(parent.get("width"))
        parent_height = _number(parent.get("height"))
        if horizontal_center:
            constraints["center_offset_x"] = (
                _number(row.get("x"))
                + _number(row.get("width")) * 0.5
                - parent_x
                - parent_width * 0.5
            )
        if vertical_center:
            constraints["center_offset_y"] = (
                _number(row.get("y"))
                + _number(row.get("height")) * 0.5
                - parent_y
                - parent_height * 0.5
            )


_FIGMA_VARIABLE_FIELD_PATHS = {
    "fills": "style.fill",
    "strokes": "style.stroke",
    "opacity": "opacity",
    "cornerRadius": "style.radius",
    "strokeWeight": "style.stroke_width",
    "itemSpacing": "layout.gap",
    "counterAxisSpacing": "layout.cross_gap",
    "paddingLeft": "layout.padding.left",
    "paddingTop": "layout.padding.top",
    "paddingRight": "layout.padding.right",
    "paddingBottom": "layout.padding.bottom",
}


def _figma_variable_target_path(
    node: Mapping[str, Any],
    field: object,
) -> str:
    field_name = str(field or "")
    if (
        field_name == "fills"
        and str(node.get("type") or "").upper() == "TEXT"
    ):
        return "style.text_color"
    return _FIGMA_VARIABLE_FIELD_PATHS.get(field_name, "")


def _figma_variable_bindings(node: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return lossless, alias-level recovery records for boundVariables.

    Painter's active ``token_bindings`` contract stores one token per property
    path. Figma can bind a list of individual paints and also exposes fields
    that Painter cannot edit yet. Keep every original alias independently so
    unresolved variables can be relinked later without inventing a value.
    """

    source = node.get("boundVariables")
    source = source if isinstance(source, Mapping) else {}
    result: list[dict[str, Any]] = []
    for raw_field, raw_value in source.items():
        field = str(raw_field or "")
        source_was_list = isinstance(raw_value, list)
        aliases = raw_value if source_was_list else [raw_value]
        for alias_index, raw_alias in enumerate(aliases):
            alias = raw_alias if isinstance(raw_alias, Mapping) else {}
            variable_id = str(alias.get("id") or "")
            result.append(
                {
                    "field": field,
                    "alias_index": alias_index,
                    "source_was_list": source_was_list,
                    "id": variable_id,
                    "type": str(alias.get("type") or ""),
                    "target_path": _figma_variable_target_path(node, field),
                    "token_id": (
                        _stable_id("token", variable_id)
                        if variable_id
                        else ""
                    ),
                    "status": "pending",
                    "reason": "",
                    "raw_alias": copy.deepcopy(
                        dict(raw_alias)
                        if isinstance(raw_alias, Mapping)
                        else raw_alias
                    ),
                }
            )
    return result


def _map_token_bindings(node: Mapping[str, Any]) -> dict[str, str]:
    source = node.get("boundVariables")
    source = source if isinstance(source, Mapping) else {}
    result: dict[str, str] = {}
    for field in _FIGMA_VARIABLE_FIELD_PATHS:
        path = _figma_variable_target_path(node, field)
        raw = source.get(field)
        aliases = raw if isinstance(raw, list) else [raw]
        alias = next(
            (
                row
                for row in aliases
                if isinstance(row, Mapping) and str(row.get("id") or "")
            ),
            None,
        )
        if alias is not None:
            result[path] = _stable_id("token", alias["id"])
    return result


def _resolve_figma_variable_bindings(
    row: dict[str, Any],
    token_ids: set[str],
    warnings: list[str],
) -> None:
    """Activate resolvable aliases and mark every fallback explicitly."""

    requested = dict(row.get("token_bindings") or {})
    active = {
        path: str(token_id)
        for path, token_id in requested.items()
        if str(token_id) in token_ids
    }
    row["token_bindings"] = active
    content = row.get("content")
    content = dict(content) if isinstance(content, Mapping) else {}
    records = content.get("figma_variable_bindings")
    if not isinstance(records, list):
        return

    activated_paths: set[str] = set()
    resolved_records: list[dict[str, Any]] = []
    for raw_record in records:
        if not isinstance(raw_record, Mapping):
            continue
        record = copy.deepcopy(dict(raw_record))
        field = str(record.get("field") or "")
        alias_index = max(0, int(_number(record.get("alias_index"))))
        variable_id = str(record.get("id") or "")
        target_path = str(record.get("target_path") or "")
        token_id = str(record.get("token_id") or "")
        source_suffix = f"[{alias_index}]" if record.get("source_was_list") else ""
        source_path = f"boundVariables.{field}{source_suffix}"

        if not variable_id:
            record["status"] = "blocked"
            record["reason"] = "missing_variable_alias_id"
            warnings.append(
                f"blocked:{row['id']}:{source_path}:"
                "figma_variable_binding_requires_token_relink:"
                "missing_variable_alias_id"
            )
        elif not target_path:
            record["status"] = "blocked"
            record["reason"] = "unsupported_bound_variable_field"
            warnings.append(
                f"blocked:{row['id']}:{source_path}:"
                "figma_variable_binding_requires_token_relink:"
                f"unsupported_field:{variable_id}"
            )
        elif (
            target_path not in activated_paths
            and active.get(target_path) == token_id
        ):
            record["status"] = "native"
            record["reason"] = "mapped_to_token_binding"
            activated_paths.add(target_path)
        elif token_id not in token_ids:
            record["status"] = "unresolved"
            record["reason"] = "missing_variable_definition"
            warnings.append(
                f"converted:{row['id']}:{source_path}:"
                "figma_variable_binding_requires_token_relink:"
                f"missing_variable_definition:{variable_id}"
            )
        else:
            record["status"] = "recovered"
            record["reason"] = "multiple_aliases_require_per_paint_binding"
            warnings.append(
                f"converted:{row['id']}:{source_path}:"
                "figma_variable_binding_requires_token_relink:"
                f"multiple_aliases:{variable_id}"
            )
        resolved_records.append(record)

    content["figma_variable_bindings"] = resolved_records
    row["content"] = content


def _resolve_figma_artboard_variable_bindings(
    records: list[dict[str, Any]],
    token_ids: set[str],
    warnings: list[str],
) -> None:
    """Resolve recovery records for frames promoted to Painter artboards."""

    for record in records:
        artboard_id = str(record.get("artboard_id") or "")
        field = str(record.get("field") or "")
        alias_index = max(0, int(_number(record.get("alias_index"))))
        variable_id = str(record.get("id") or "")
        token_id = str(record.get("token_id") or "")
        source_suffix = f"[{alias_index}]" if record.get("source_was_list") else ""
        source_path = f"boundVariables.{field}{source_suffix}"
        if not variable_id:
            record["status"] = "blocked"
            record["reason"] = "missing_variable_alias_id"
            detail = "missing_variable_alias_id"
        elif token_id not in token_ids:
            record["status"] = "unresolved"
            record["reason"] = "missing_variable_definition"
            detail = f"missing_variable_definition:{variable_id}"
        else:
            # Painter artboards do not expose token_bindings. Preserve the
            # authored static background/geometry and require an explicit
            # relink instead of pretending this alias is active.
            record["status"] = "blocked"
            record["reason"] = "artboard_variable_binding_unsupported"
            detail = f"artboard_binding_unsupported:{variable_id}"
        warnings.append(
            f"blocked:{artboard_id}:{source_path}:"
            f"figma_variable_binding_requires_token_relink:{detail}"
        )


def _figma_text_resize_mode(value: object) -> str:
    return {
        "WIDTH_AND_HEIGHT": "auto_width",
        "HEIGHT": "auto_height",
        "NONE": "fixed_size",
        "TRUNCATE": "fixed_size",
    }.get(str(value or "").strip().upper(), "")


def _figma_progressive_blur_effect(effect: Mapping[str, Any]) -> bool:
    effect_type = str(effect.get("type") or "").strip().upper()
    if effect_type not in {"LAYER_BLUR", "BACKGROUND_BLUR"}:
        return False
    progressive_fields_present = any(
        key in effect for key in ("startRadius", "startOffset", "endOffset")
    )
    raw_blur_type = effect.get("blurType")
    if raw_blur_type is None and not progressive_fields_present:
        return False
    return str(raw_blur_type or "PROGRESSIVE").strip().upper() == (
        "PROGRESSIVE"
    )


def _figma_exact_effect_types(node: Mapping[str, Any]) -> list[str]:
    """Return visible modern effects that require an exact node render."""

    effects = node.get("effects")
    if not isinstance(effects, list):
        return []
    result: list[str] = []
    for effect in effects:
        if not isinstance(effect, Mapping) or not bool(
            effect.get("visible", True)
        ):
            continue
        effect_type = str(effect.get("type") or "").strip().upper()
        if effect_type in {"NOISE", "TEXTURE"}:
            label = effect_type.casefold()
        elif _figma_progressive_blur_effect(effect):
            label = f"progressive_{effect_type.casefold()}"
        else:
            continue
        if label not in result:
            result.append(label)
    return result


def _figma_bounds_record(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "x": _number(value.get("x")),
        "y": _number(value.get("y")),
        "width": max(0.0, _number(value.get("width"))),
        "height": max(0.0, _number(value.get("height"))),
    }


def _map_style(node: Mapping[str, Any]) -> dict[str, Any]:
    fill = _solid_paint(node.get("fills"))
    gradient = _gradient_paint(node.get("fills"))
    stroke = _solid_paint(node.get("strokes"))
    raw_effects = (
        node.get("effects") if isinstance(node.get("effects"), list) else []
    )
    appearance_effects: list[dict[str, Any]] = []
    for effect in raw_effects:
        if not isinstance(effect, Mapping):
            continue
        effect_type = str(effect.get("type") or "").upper()
        effect_visible = bool(effect.get("visible", True))
        preserve_hidden = effect_type in {"NOISE", "TEXTURE"} or (
            _figma_progressive_blur_effect(effect)
        )
        if not effect_visible and not preserve_hidden:
            continue
        if effect_type in {"LAYER_BLUR", "BACKGROUND_BLUR"}:
            blur: dict[str, Any] = {
                "type": (
                    "background_blur"
                    if effect_type == "BACKGROUND_BLUR"
                    else "layer_blur"
                ),
                "radius": max(
                    0.0,
                    _number(effect.get("radius"), 8.0),
                ),
            }
            raw_blur_type = effect.get("blurType")
            progressive_fields_present = any(
                key in effect
                for key in ("startRadius", "startOffset", "endOffset")
            )
            if raw_blur_type is not None or progressive_fields_present:
                blur_type = str(
                    raw_blur_type or "PROGRESSIVE"
                ).strip().casefold()
                blur["blur_type"] = (
                    blur_type
                    if blur_type in {"normal", "progressive"}
                    else "normal"
                )
                if blur["blur_type"] == "progressive":
                    start_offset = effect.get("startOffset")
                    start_offset = (
                        start_offset
                        if isinstance(start_offset, Mapping)
                        else {}
                    )
                    end_offset = effect.get("endOffset")
                    end_offset = (
                        end_offset
                        if isinstance(end_offset, Mapping)
                        else {}
                    )
                    blur.update(
                        {
                            "start_radius": max(
                                0.0,
                                _number(effect.get("startRadius")),
                            ),
                            "start_offset": {
                                "x": _number(start_offset.get("x")),
                                "y": _number(start_offset.get("y")),
                            },
                            "end_offset": {
                                "x": _number(end_offset.get("x")),
                                "y": _number(end_offset.get("y"), 1.0),
                            },
                        }
                    )
            if not effect_visible:
                blur["visible"] = False
            appearance_effects.append(blur)
            continue
        if effect_type == "NOISE":
            noise_type = str(
                effect.get("noiseType") or "MONOTONE"
            ).strip().casefold()
            if noise_type not in {"monotone", "duotone", "multitone"}:
                noise_type = "monotone"
            noise: dict[str, Any] = {
                "type": "noise",
                "color": _color(effect.get("color"), "#000000FF"),
                "blend_mode": str(
                    effect.get("blendMode") or "NORMAL"
                ).casefold(),
                "noise_size": max(0.0, _number(effect.get("noiseSize"))),
                "noise_type": noise_type,
                "density": max(0.0, _number(effect.get("density"))),
            }
            noise_size_vector = effect.get("noiseSizeVector")
            if isinstance(noise_size_vector, Mapping):
                noise["noise_size_vector"] = {
                    "x": _number(
                        noise_size_vector.get("x"),
                        noise["noise_size"],
                    ),
                    "y": _number(
                        noise_size_vector.get("y"),
                        noise["noise_size"],
                    ),
                }
            if effect.get("secondaryColor") is not None:
                noise["secondary_color"] = _color(
                    effect.get("secondaryColor"),
                    "#FFFFFFFF",
                )
            if effect.get("opacity") is not None:
                noise["opacity"] = max(
                    0.0,
                    min(1.0, _number(effect.get("opacity"), 1.0)),
                )
            if not effect_visible:
                noise["visible"] = False
            appearance_effects.append(noise)
            continue
        if effect_type == "TEXTURE":
            texture: dict[str, Any] = {
                "type": "texture",
                "radius": max(0.0, _number(effect.get("radius"))),
                "noise_size": max(0.0, _number(effect.get("noiseSize"))),
                "clip_to_shape": bool(effect.get("clipToShape", False)),
            }
            noise_size_vector = effect.get("noiseSizeVector")
            if isinstance(noise_size_vector, Mapping):
                texture["noise_size_vector"] = {
                    "x": _number(
                        noise_size_vector.get("x"),
                        texture["noise_size"],
                    ),
                    "y": _number(
                        noise_size_vector.get("y"),
                        texture["noise_size"],
                    ),
                }
            if not effect_visible:
                texture["visible"] = False
            appearance_effects.append(texture)
            continue
        if effect_type not in {"DROP_SHADOW", "INNER_SHADOW"}:
            continue
        offset = effect.get("offset")
        offset = offset if isinstance(offset, Mapping) else {}
        shadow_effect: dict[str, Any] = {
                "type": (
                    "inner_shadow"
                    if effect_type == "INNER_SHADOW"
                    else "drop_shadow"
                ),
                "color": _color(effect.get("color"), "#00000040"),
                "x": _number(offset.get("x")),
                "y": _number(offset.get("y"), 4.0),
                "blur": max(0.0, _number(effect.get("radius"), 8.0)),
                "spread": _number(effect.get("spread")),
                "blend_mode": str(
                    effect.get("blendMode") or "NORMAL"
                ).casefold(),
            }
        if (
            effect_type == "DROP_SHADOW"
            and effect.get("showShadowBehindNode") is not None
        ):
            shadow_effect["show_shadow_behind_node"] = bool(
                effect.get("showShadowBehindNode")
            )
        appearance_effects.append(shadow_effect)
    corner_values = node.get("rectangleCornerRadii")
    corner_values = (
        list(corner_values)
        if isinstance(corner_values, list) and len(corner_values) >= 4
        else []
    )
    fallback_radius = max(
        0.0,
        _number(
            node.get("cornerRadius"),
            corner_values[0] if corner_values else 0.0,
        ),
    )
    stroke_align = str(node.get("strokeAlign") or "CENTER").casefold()
    result: dict[str, Any] = {
        "fill": _color(fill.get("color"), "#00000000") if fill else "#00000000",
        "stroke": _color(stroke.get("color"), "#00000000") if stroke else "#00000000",
        "stroke_width": max(0.0, _number(node.get("strokeWeight"))),
        "stroke_cap": str(node.get("strokeCap") or "NONE").casefold(),
        "stroke_join": str(node.get("strokeJoin") or "MITER").casefold(),
        "stroke_miter_limit": max(
            0.0,
            _number(node.get("strokeMiterAngle"), 4.0),
        ),
        "stroke_dash": [
            max(0.0, _number(value))
            for value in (
                node.get("strokeDashes")
                if isinstance(node.get("strokeDashes"), list)
                else []
            )
        ],
        "radius": fallback_radius,
        "corner_smoothing": max(
            0.0,
            min(1.0, _number(node.get("cornerSmoothing"))),
        ),
        "blend_mode": str(
            node.get("blendMode") or "NORMAL"
        ).casefold(),
        "stroke_align": stroke_align,
        "fills": _map_paints(node.get("fills")),
        "strokes": _map_paints(
            node.get("strokes"),
            stroke=True,
            width=max(0.0, _number(node.get("strokeWeight"))),
            align=stroke_align,
        ),
        "corner_radii": {
            "top_left": max(
                0.0,
                _number(corner_values[0], fallback_radius),
            ) if corner_values else fallback_radius,
            "top_right": max(
                0.0,
                _number(corner_values[1], fallback_radius),
            ) if corner_values else fallback_radius,
            "bottom_right": max(
                0.0,
                _number(corner_values[2], fallback_radius),
            ) if corner_values else fallback_radius,
            "bottom_left": max(
                0.0,
                _number(corner_values[3], fallback_radius),
            ) if corner_values else fallback_radius,
        },
    }
    individual_stroke_weights = node.get("individualStrokeWeights")
    if isinstance(individual_stroke_weights, Mapping):
        result["individual_stroke_weights"] = {
            side: max(0.0, _number(individual_stroke_weights.get(side)))
            for side in ("top", "right", "bottom", "left")
        }
    if gradient is not None:
        result["fill_gradient"] = _map_gradient(gradient)
    if appearance_effects:
        result["effects"] = appearance_effects
    if str(node.get("type") or "").upper() == "TEXT":
        text_style = node.get("style")
        text_style = text_style if isinstance(text_style, Mapping) else {}
        line_height = max(
            0.0,
            _number(text_style.get("lineHeightPx")),
        )
        result.update(
            {
                "text_color": result["fill"],
                "font_family": str(text_style.get("fontFamily") or "Inter"),
                "font_size": max(
                    1.0,
                    _number(text_style.get("fontSize"), 16.0),
                ),
                "font_weight": int(
                    _number(text_style.get("fontWeight"), 400)
                ),
                "text_align": str(
                    text_style.get("textAlignHorizontal") or "LEFT"
                ).casefold(),
                "text_vertical_align": str(
                    text_style.get("textAlignVertical") or "TOP"
                ).casefold(),
                "line_height": line_height,
            }
        )
        if line_height > 0.0:
            result["line_height_unit"] = "px"
        from app.painter_ui_typography import normalize_ui_font_axes

        axes = normalize_ui_font_axes(
            _tigerstudio_plugin_json(node, "font_axes")
        )
        if axes:
            result["font_axes"] = axes
    shadow = next(
        (
            effect
            for effect in appearance_effects
            if effect["type"] == "drop_shadow"
            and bool(effect.get("visible", True))
        ),
        None,
    )
    if shadow is not None:
        result["shadow"] = {
            key: copy.deepcopy(value)
            for key, value in shadow.items()
            if key not in {"type", "blend_mode"}
        }
    return result


def _svg_number(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".") or "0"


def _visible_figma_paints(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        row
        for row in value
        if isinstance(row, Mapping) and bool(row.get("visible", True))
    ]


def _recover_figma_semantic_vector_geometry(
    node: Mapping[str, Any],
) -> dict[str, Any]:
    """Recover only primitives whose stored semantics determine the path.

    Old REST fixtures were often fetched without ``geometry=paths``.  An
    arbitrary VECTOR cannot be reconstructed from its bounding box, so this
    helper intentionally supports only two tightly constrained cases present
    in the compatibility corpus: an unrotated vector explicitly named as a
    rectangle, and the 2:1 solid tooltip triangle exported as ``Arrow``.
    Everything else remains an explicit compatibility blocker.
    """

    if str(node.get("type") or "").upper() != "VECTOR":
        return {}
    bounds = node.get("absoluteBoundingBox")
    bounds = bounds if isinstance(bounds, Mapping) else {}
    width = _number(bounds.get("width"))
    height = _number(bounds.get("height"))
    if width <= 0.0 or height <= 0.0:
        return {}
    fills = _visible_figma_paints(node.get("fills"))
    strokes = _visible_figma_paints(node.get("strokes"))
    if (
        len(fills) != 1
        or str(fills[0].get("type") or "").upper() != "SOLID"
        or strokes
    ):
        return {}

    name = str(node.get("name") or "").strip()
    rotation = _number(node.get("rotation"))
    width_text = _svg_number(width)
    height_text = _svg_number(height)
    if (
        re.fullmatch(r"Rectangle(?:\s+\d+)?", name, re.IGNORECASE)
        and abs(rotation) <= 0.0001
    ):
        path = f"M 0 0 H {width_text} V {height_text} H 0 Z"
        return {
            "kind": "rectangle",
            "geometry": [{"path": path, "winding_rule": "nonzero"}],
            "consumed_rotation": False,
        }

    ratio = max(width, height) / min(width, height)
    if name.casefold() != "arrow" or abs(ratio - 2.0) > 0.01:
        return {}
    half_turn = (
        abs(abs(rotation) - math.pi) <= 0.001
        or abs(abs(rotation) - 180.0) <= 0.001
    )
    if abs(rotation) > 0.0001 and not half_turn:
        return {}
    half_width = _svg_number(width / 2.0)
    half_height = _svg_number(height / 2.0)
    if width >= height:
        path = (
            f"M 0 {height_text} L {width_text} {height_text} "
            f"L {half_width} 0 Z"
            if half_turn
            else f"M 0 0 L {width_text} 0 L {half_width} {height_text} Z"
        )
    else:
        path = (
            f"M {width_text} 0 L {width_text} {height_text} "
            f"L 0 {half_height} Z"
            if half_turn
            else f"M 0 0 L 0 {height_text} L {width_text} {half_height} Z"
        )
    return {
        "kind": "triangle",
        "geometry": [{"path": path, "winding_rule": "nonzero"}],
        "consumed_rotation": half_turn,
    }


def _map_content(
    node: Mapping[str, Any],
    image_urls: Mapping[str, str],
    image_paths: Mapping[str, str],
    vector_render_paths: Mapping[str, str],
    effect_render_paths: Mapping[str, str],
    *,
    file_key: str = "",
) -> dict[str, Any]:
    node_type = str(node.get("type") or "").upper()
    node_id = str(node.get("id") or "")
    result: dict[str, Any] = {
        "figma_node_id": node_id,
        "figma_type": node_type,
    }
    exact_effect_types = _figma_exact_effect_types(node)
    exact_render_path = str(effect_render_paths.get(node_id) or "").strip()
    exact_render_file = (
        Path(exact_render_path).expanduser().resolve()
        if exact_render_path
        else None
    )
    if (
        exact_effect_types
        and exact_render_file is not None
        and exact_render_file.is_file()
    ):
        result["figma_exact_render"] = {
            "png_path": str(exact_render_file),
            "source_bounds": _figma_bounds_record(
                node.get("absoluteBoundingBox")
            ),
            "render_bounds": _figma_bounds_record(
                node.get("absoluteRenderBounds")
            ),
            "source": "figma_render_api",
            "node_id": node_id,
            "format": "png",
            "scale": 1.0,
            "effect_types": exact_effect_types,
            "provenance": {
                "file_key": str(file_key or ""),
                "endpoint": "GET /v1/images/:key",
                "authenticated_import": True,
            },
        }
    variable_bindings = _figma_variable_bindings(node)
    if variable_bindings:
        result["figma_variable_bindings"] = variable_bindings
    unsupported_paints: list[dict[str, Any]] = []
    for paint_target in ("fills", "strokes"):
        paints = node.get(paint_target)
        if not isinstance(paints, list):
            continue
        for paint in paints:
            if not isinstance(paint, Mapping):
                continue
            paint_type = str(paint.get("type") or "").upper()
            if paint_type not in {"GRADIENT_ANGULAR", "GRADIENT_DIAMOND"}:
                continue
            unsupported_paints.append(
                {
                    "target": paint_target,
                    "type": paint_type,
                    "paint": copy.deepcopy(dict(paint)),
                    "reason": "requires_conic_or_diamond_gradient_material",
                }
            )
    if unsupported_paints:
        result["figma_unsupported_paints"] = unsupported_paints
    if node_type == "TEXT":
        style = node.get("style")
        style = style if isinstance(style, Mapping) else {}
        line_height = max(0.0, _number(style.get("lineHeightPx")))
        text_resize = _figma_text_resize_mode(style.get("textAutoResize"))
        result.update(
            {
                "text": str(node.get("characters") or ""),
                "font_family": str(style.get("fontFamily") or "Inter"),
                "font_size": max(1.0, _number(style.get("fontSize"), 16.0)),
                "font_weight": int(_number(style.get("fontWeight"), 400)),
                "text_align": str(style.get("textAlignHorizontal") or "LEFT").casefold(),
                "line_height": line_height,
                "text_ranges": _map_text_ranges(node),
            }
        )
        if line_height > 0.0:
            result["line_height_unit"] = "px"
        if text_resize:
            result["text_resize"] = text_resize
    if node_type == "INSTANCE":
        component_key = str(
            node.get("componentId")
            or node.get("mainComponent")
            or node.get("key")
            or ""
        )
        if component_key:
            result["remote_component"] = {
                "component_key": component_key,
                "component_name": str(node.get("name") or "Remote Component"),
                "source_file_key": str(node.get("sourceFileKey") or ""),
                "source_node_id": str(node.get("id") or ""),
                "status": "linked",
            }
    if node_type == "BOOLEAN_OPERATION":
        result["boolean"] = {
            "enabled": True,
            "group": True,
            "operation": {
                "UNION": "union",
                "SUBTRACT": "subtract",
                "INTERSECT": "intersect",
                "EXCLUDE": "exclude",
            }.get(
                str(node.get("booleanOperation") or "UNION").upper(),
                "union",
            ),
            "operand_ids": [
                _figma_node_stable_id(child)
                for child in node.get("children", [])
                if isinstance(child, Mapping)
            ],
        }
    image = _image_paint(node.get("fills"))
    if image is not None:
        mapped_image = _map_paints([image])[0]
        image_ref = str(image.get("imageRef") or "")
        local_path = str(image_paths.get(image_ref) or "")
        scale_mode = str(image.get("scaleMode") or "FILL").upper()
        image_fit = str(mapped_image.get("fit") or "fill")
        image_transform = copy.deepcopy(
            image.get("imageTransform")
            if isinstance(image.get("imageTransform"), list)
            else []
        )
        image_render_blockers: list[str] = []
        visible_fills = _visible_figma_paints(node.get("fills"))
        if len(visible_fills) > 1:
            image_render_blockers.append(
                "figma_multiple_image_or_mixed_fills_require_composited_render"
            )
        adjustments = dict(mapped_image.get("adjustments") or {})
        if any(abs(_number(value)) > 0.0001 for value in adjustments.values()):
            image_render_blockers.append(
                "figma_image_filters_require_verified_color_pipeline"
            )
        if str(mapped_image.get("blend_mode") or "normal") != "normal":
            image_render_blockers.append(
                "figma_image_paint_blend_mode_requires_composited_render"
            )
        if image_transform:
            valid_shape = (
                len(image_transform) == 2
                and all(
                    isinstance(axis, list) and len(axis) >= 3
                    for axis in image_transform
                )
            )
            try:
                a, c, _offset_x = (
                    float(value) for value in image_transform[0][:3]
                )
                b, d, _offset_y = (
                    float(value) for value in image_transform[1][:3]
                )
                transform_valid = valid_shape and all(
                    math.isfinite(float(value))
                    for axis in image_transform
                    for value in axis[:3]
                ) and abs(a * d - b * c) > 1.0e-9
            except (IndexError, TypeError, ValueError):
                transform_valid = False
            if not transform_valid:
                image_render_blockers.append(
                    "figma_image_transform_invalid_or_singular"
                )
        result.update(
            {
                "image_ref": image_ref,
                "image_url": str(image_urls.get(image_ref) or ""),
                "image_path": local_path,
                "source_path": local_path,
                "image_mode": scale_mode.casefold(),
                "image_fit": image_fit,
                "tile_scale": float(mapped_image.get("tile_scale", 1.0)),
                "image_rotation": float(mapped_image.get("rotation", 0.0)),
                "image_opacity": float(mapped_image.get("opacity", 1.0)),
                "image_adjustments": adjustments,
                "image_blend_mode": str(
                    mapped_image.get("blend_mode") or "normal"
                ),
                "image_status": "ready" if local_path else "missing",
                "figma_image_transform": image_transform,
                "figma_image_transform_semantics": (
                    "target_normalized_to_source_normalized"
                    if image_transform
                    else "none"
                ),
            }
        )
        if image_render_blockers:
            result["figma_image_render_blockers"] = sorted(
                set(image_render_blockers)
            )
    fill_geometry = node.get("fillGeometry")
    if isinstance(fill_geometry, list):
        result["vector_fill_geometry"] = [
            {
                "path": str(row.get("path") or ""),
                "winding_rule": str(row.get("windingRule") or "NONZERO").casefold(),
            }
            for row in fill_geometry
            if isinstance(row, Mapping) and str(row.get("path") or "")
        ]
        result["vector_paths"] = [
            row["path"] for row in result["vector_fill_geometry"]
        ]
    stroke_geometry = node.get("strokeGeometry")
    if isinstance(stroke_geometry, list):
        result["vector_stroke_geometry"] = [
            {
                "path": str(row.get("path") or ""),
                "winding_rule": str(row.get("windingRule") or "NONZERO").casefold(),
            }
            for row in stroke_geometry
            if isinstance(row, Mapping) and str(row.get("path") or "")
        ]
        if result["vector_stroke_geometry"]:
            # REST strokeGeometry is the expanded outline around the shape's
            # center regardless of strokeAlign. Preserve it together with the
            # alignment so Painter can clip the centered geometry inside or
            # outside instead of re-stroking with the stale uniform
            # strokeWeight fallback used by mixed-edge rectangles.
            local_size = node.get("size")
            local_size = local_size if isinstance(local_size, Mapping) else {}
            source_box = _box(node)
            result["figma_stroke_geometry"] = {
                "representation": "expanded_outline",
                "source": "strokeGeometry",
                "viewport": {
                    "width": max(
                        0.0001,
                        _number(local_size.get("x"), source_box["width"]),
                    ),
                    "height": max(
                        0.0001,
                        _number(local_size.get("y"), source_box["height"]),
                    ),
                },
            }
    has_editable_geometry = bool(
        result.get("vector_fill_geometry")
        or result.get("vector_stroke_geometry")
        or result.get("vector_paths")
    )
    if node_type == "VECTOR" and not has_editable_geometry:
        render_path = str(
            vector_render_paths.get(str(node.get("id") or "")) or ""
        ).strip()
        if render_path and Path(render_path).expanduser().is_file():
            result["vector_render_path"] = render_path
            result["figma_vector_geometry_recovery"] = {
                "kind": "svg_render",
                "source": "figma_render_api",
                "editability": "render_only",
            }
        else:
            recovery = _recover_figma_semantic_vector_geometry(node)
            if recovery:
                result["vector_fill_geometry"] = copy.deepcopy(
                    recovery["geometry"]
                )
                result["vector_paths"] = [
                    str(row["path"]) for row in recovery["geometry"]
                ]
                result["figma_vector_geometry_recovery"] = {
                    "kind": str(recovery["kind"]),
                    "source": "semantic_primitive",
                    "editability": "editable_path",
                    "consumed_rotation": bool(
                        recovery.get("consumed_rotation", False)
                    ),
                }
    return result


def _top_level_frames(page: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    children = [
        row for row in page.get("children", []) if isinstance(row, Mapping)
    ]
    frames = [
        row
        for row in children
        if str(row.get("type") or "").upper()
        in {"FRAME", "COMPONENT", "COMPONENT_SET", "INSTANCE", "SECTION"}
    ]
    return frames or [page]


_FIGMA_ARTBOARD_GAP = 160.0
_FIGMA_PAGE_GAP = 1600.0


def _figma_page_frame_placement(
    frames: Sequence[Mapping[str, Any]],
    *,
    origin_y: float,
) -> tuple[list[tuple[float, float]], float]:
    """Return canvas positions for one page's top-level frames.

    Figma keeps every top-level frame's board position in
    ``absoluteBoundingBox``, and that grid is what makes an imported file
    recognisable.  Each page owns an independent coordinate space, so a page
    is shifted to its own local origin and stacked below the previous one
    instead of being interleaved.  Frames without a bounding box (and pages
    that report none at all) fall back to the historical left-to-right strip
    appended after the positioned content.
    """
    boxes = [_box(frame) for frame in frames]
    positioned = [
        isinstance(frame.get("absoluteBoundingBox"), Mapping)
        for frame in frames
    ]
    if any(positioned):
        base_x = min(
            box["x"] for box, ok in zip(boxes, positioned) if ok
        )
        base_y = min(
            box["y"] for box, ok in zip(boxes, positioned) if ok
        )
        strip_x = max(
            box["x"] + box["width"] - base_x
            for box, ok in zip(boxes, positioned)
            if ok
        ) + _FIGMA_ARTBOARD_GAP
    else:
        base_x = 0.0
        base_y = 0.0
        strip_x = 0.0

    placements: list[tuple[float, float]] = []
    for box, ok in zip(boxes, positioned):
        if ok:
            placements.append((box["x"] - base_x, box["y"] - base_y + origin_y))
            continue
        placements.append((strip_x, origin_y))
        strip_x += box["width"] + _FIGMA_ARTBOARD_GAP

    page_height = max(
        (y - origin_y) + box["height"]
        for box, (_x, y) in zip(boxes, placements)
    )
    return placements, origin_y + page_height + _FIGMA_PAGE_GAP


def _preferred_artboard_id(
    artboards: list[Mapping[str, Any]],
    objects: list[Mapping[str, Any]],
) -> str:
    if not artboards:
        return ""
    visible_counts = {
        str(artboard["id"]): sum(
            1
            for row in objects
            if str(row.get("artboard_id") or "") == str(artboard["id"])
            and bool(row.get("visible", True))
        )
        for artboard in artboards
    }
    preferred = max(
        artboards,
        key=lambda row: (
            visible_counts[str(row["id"])],
            float(row.get("width") or 0.0) * float(row.get("height") or 0.0),
        ),
    )
    return str(preferred["id"])


def _figma_document_root(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    root = payload.get("document")
    if isinstance(root, Mapping):
        return root
    # Public compatibility fixtures and JSON_REST_V1 exports often contain a
    # single REST node rather than the outer /files or /nodes response. Treat
    # that node exactly like a one-entry /nodes response so the same wrapping,
    # deduplication, and validation path applies.
    payload_type = str(payload.get("type") or "").upper()
    if payload_type:
        if payload_type == "DOCUMENT":
            return payload
        nodes: Mapping[str, Any] = {
            "fragment": {"document": payload},
        }
    else:
        raw_nodes = payload.get("nodes")
        nodes = raw_nodes if isinstance(raw_nodes, Mapping) else {}
    selected = [
        row["document"]
        for row in nodes.values()
        if isinstance(row, Mapping) and isinstance(row.get("document"), Mapping)
    ]
    if not selected:
        return None

    # A /files/:key/nodes response may mix frame-like targets and leaf targets.
    # Feeding every target into one CANVAS makes _top_level_frames select only
    # the frame-like rows and silently drops sibling leaves. Remove targets
    # already expanded beneath another selected node, then give each remaining
    # leaf a synthetic frame so it remains an editable object on its own
    # artboard. Selected CANVAS nodes remain real document pages.
    descendant_ids: set[str] = set()
    for node in selected:
        root_id = str(node.get("id") or "")
        for descendant in _walk_figma_nodes(node):
            descendant_id = str(descendant.get("id") or "")
            if descendant_id and descendant_id != root_id:
                descendant_ids.add(descendant_id)
    selected = [
        node
        for node in selected
        if not str(node.get("id") or "")
        or str(node.get("id") or "") not in descendant_ids
    ]

    pages: list[Mapping[str, Any]] = []
    loose_nodes: list[Mapping[str, Any]] = []
    for node in selected:
        if str(node.get("type") or "").upper() == "CANVAS":
            pages.append(node)
        else:
            loose_nodes.append(node)
    if loose_nodes:
        frame_types = {"FRAME", "COMPONENT", "COMPONENT_SET", "SECTION"}
        artboards: list[Mapping[str, Any]] = []
        for node in loose_nodes:
            if str(node.get("type") or "").upper() in frame_types:
                artboards.append(node)
                continue
            node_box = _box(node)
            artboards.append(
                {
                    "id": f"figma:nodes-artboard:{node.get('id') or len(artboards)}",
                    "name": str(node.get("name") or "Imported Node"),
                    "type": "FRAME",
                    "absoluteBoundingBox": node_box,
                    "clipsContent": False,
                    "children": [node],
                }
            )
        pages.append(
            {
                "id": "figma:nodes-canvas",
                "name": "Imported Nodes",
                "type": "CANVAS",
                "children": artboards,
            }
        )
    return {
        "id": "figma:nodes-document",
        "name": str(payload.get("name") or "Figma Nodes"),
        "type": "DOCUMENT",
        "children": pages,
    }


def import_figma_payload(
    payload: Mapping[str, Any],
    *,
    source: str = "",
    image_urls: Mapping[str, str] | None = None,
    image_paths: Mapping[str, str] | None = None,
    vector_render_paths: Mapping[str, str] | None = None,
    effect_render_paths: Mapping[str, str] | None = None,
    variables_payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _figma_document_root(payload)
    if root is None:
        raise PainterUIFigmaError(
            "Figma JSON does not contain a file document or nodes response"
        )
    pages = [
        row
        for row in root.get("children", [])
        if isinstance(row, Mapping)
        and str(row.get("type") or "").upper() == "CANVAS"
    ]
    if not pages:
        raise PainterUIFigmaError("Figma document does not contain any pages")
    images = dict(image_urls or {})
    local_images = dict(image_paths or {})
    local_vector_renders = dict(vector_render_paths or {})
    local_effect_renders = dict(effect_render_paths or {})
    file_key = ""
    try:
        file_key = figma_file_key(source)
    except PainterUIFigmaError:
        file_key = str(payload.get("key") or "snapshot")

    artboards: list[dict[str, Any]] = []
    imported_pages: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    interactions: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    artboard_variable_bindings: list[dict[str, Any]] = []
    pending_reactions: list[dict[str, Any]] = []
    figma_targets: dict[str, tuple[str, str]] = {}
    warnings: list[str] = []
    supported = 0
    skipped = 0
    component_set_index = _figma_component_set_index(root)
    page_origin_y = 0.0

    for page in pages:
        page_id = _figma_node_stable_id(page, "page")
        imported_pages.append(
            {
                "id": page_id,
                "name": str(page.get("name") or "Page"),
            }
        )
        page_frames = _top_level_frames(page)
        frame_placements, page_origin_y = _figma_page_frame_placement(
            page_frames,
            origin_y=page_origin_y,
        )
        for frame, (artboard_x, artboard_y) in zip(
            page_frames,
            frame_placements,
        ):
            frame_object_start = len(objects)
            frame_box = _box(frame)
            frame_id = _figma_node_stable_id(frame, "artboard")
            background = _solid_paint(frame.get("backgrounds") or frame.get("fills"))
            artboards.append(
                {
                    "id": frame_id,
                    "page_id": page_id,
                    "name": str(frame.get("name") or page.get("name") or "Figma"),
                    "width": int(round(frame_box["width"])),
                    "height": int(round(frame_box["height"])),
                    "x": artboard_x,
                    "y": artboard_y,
                    "background": (
                        _color(background.get("color"), "#FFFFFF")
                        if background
                        else "#FFFFFF"
                    ),
                    "breakpoint": "figma",
                    "orientation": (
                        "landscape"
                        if frame_box["width"] >= frame_box["height"]
                        else "portrait"
                    ),
                }
            )
            # A top-level COMPONENT is both the artboard source and an
            # editable Painter object (visit(frame) below). Its alias records
            # therefore belong to that object only; copying them into the
            # artboard recovery list would duplicate one Figma source slot.
            if str(frame.get("type") or "").upper() != "COMPONENT":
                for binding in _figma_variable_bindings(frame):
                    binding["artboard_id"] = frame_id
                    binding["figma_node_id"] = str(frame.get("id") or "")
                    artboard_variable_bindings.append(binding)
            frame_layout_mode = str(frame.get("layoutMode") or "").upper()
            if frame_layout_mode in {"HORIZONTAL", "VERTICAL"}:
                warnings.append(
                    f"converted:{frame.get('id')}:"
                    "artboard_auto_layout_flattened_to_absolute_geometry"
                )
            frame_reactions = frame.get("reactions")
            if not isinstance(frame_reactions, list):
                frame_reactions = frame.get("interactions")
            if isinstance(frame_reactions, list) and frame_reactions:
                pending_reactions.append(
                    {
                        "source_kind": "artboard",
                        "source_id": frame_id,
                        "source_figma_node_id": str(frame.get("id") or ""),
                        "artboard_id": frame_id,
                        "reactions": copy.deepcopy(frame_reactions),
                    }
                )
            figma_targets[str(frame.get("id") or "")] = ("artboard", frame_id)

            def visit(
                node: Mapping[str, Any],
                parent_id: str = "",
                *,
                include_self: bool = True,
                parent_layout_mode: str = "none",
                definition_component_id: str = "",
                instance_component_id: str = "",
                parent_figma_linear: tuple[float, float, float, float] = (
                    _FIGMA_IDENTITY_LINEAR_TRANSFORM
                ),
                parent_affine_snapshot: bool = False,
                parent_baseline_offsets: Mapping[str, float] | None = None,
            ) -> None:
                nonlocal supported, skipped
                node_type = str(node.get("type") or "").upper()
                unsupported = {"SLICE", "CONNECTOR", "WIDGET", "EMBED", "LINK_UNFURL"}
                if node_type in unsupported:
                    skipped += 1
                    warnings.append(f"blocked:{node.get('id')}:{node_type}")
                    return
                effective_figma_linear = _multiply_figma_linear_transforms(
                    parent_figma_linear,
                    _figma_node_linear_transform(node),
                )
                affine_snapshot_active = bool(parent_affine_snapshot)
                current_parent = parent_id
                if include_self:
                    (
                        node_box,
                        missing_bounds_recovery,
                    ) = _figma_missing_auto_layout_cross_box(node)
                    object_id = _figma_node_stable_id(node)
                    kind = _map_kind(node)
                    content = _map_content(
                        node,
                        images,
                        local_images,
                        local_vector_renders,
                        local_effect_renders,
                        file_key=file_key,
                    )
                    raw_component_property_references = node.get(
                        "componentPropertyReferences"
                    )
                    raw_component_property_references = (
                        raw_component_property_references
                        if isinstance(raw_component_property_references, Mapping)
                        else {}
                    )
                    component_property_bindings = (
                        _figma_component_property_bindings(
                            raw_component_property_references
                        )
                    )
                    component_property_binding_recovery = (
                        _figma_unmapped_component_property_bindings(
                            raw_component_property_references
                        )
                    )
                    if raw_component_property_references:
                        content["figma_component_property_references"] = (
                            copy.deepcopy(
                                dict(raw_component_property_references)
                            )
                        )
                    if component_property_binding_recovery:
                        content["figma_component_property_bindings"] = (
                            component_property_binding_recovery
                        )
                    if missing_bounds_recovery:
                        content["figma_missing_bounds_recovery"] = (
                            missing_bounds_recovery
                        )
                        warnings.append(
                            f"converted:{node.get('id')}:GEOMETRY:"
                            "missing_auto_layout_cross_bounds_inferred"
                        )
                    mapped_layout = _map_layout(
                        node,
                        parent_layout_mode=parent_layout_mode,
                    )
                    baseline_offset = (
                        parent_baseline_offsets.get(str(node.get("id") or ""))
                        if isinstance(parent_baseline_offsets, Mapping)
                        else None
                    )
                    if baseline_offset is not None:
                        mapped_layout["baseline_offset"] = max(
                            0.0,
                            float(baseline_offset),
                        )
                        mapped_layout["baseline_source"] = (
                            "figma_resolved_geometry"
                        )
                    auto_layout_recovery = (
                        _figma_transformed_auto_layout_recovery(
                            node,
                            mapped_layout,
                            parent_linear=parent_figma_linear,
                        )
                    )
                    if auto_layout_recovery:
                        if not affine_snapshot_active:
                            outer_affine_reason = _figma_outer_affine_issue(
                                parent_figma_linear
                            )
                            if outer_affine_reason:
                                pa, pc, pb, pd = parent_figma_linear
                                auto_layout_recovery.update(
                                    {
                                        "outer_affine_ignored": True,
                                        "outer_affine_reason": (
                                            outer_affine_reason
                                        ),
                                        "outer_affine_linear_transform": [
                                            [pa, pc],
                                            [pb, pd],
                                        ],
                                    }
                                )
                                warnings.append(
                                    f"blocked:{node.get('id')}:AFFINE:"
                                    f"{outer_affine_reason}"
                                )
                            # The imported AABB is already in artboard space.
                            # Start the recoverable affine basis at the
                            # flattened subtree root so unrelated outer groups
                            # are not applied to that absolute geometry twice.
                            effective_figma_linear = (
                                _figma_node_linear_transform(node)
                            )
                        affine_snapshot_active = True
                        content["figma_auto_layout_recovery"] = (
                            auto_layout_recovery
                        )
                        mapped_layout = copy.deepcopy(mapped_layout)
                        mapped_layout.update(
                            {
                                "mode": "none",
                                "width_sizing": "fixed",
                                "height_sizing": "fixed",
                            }
                        )
                        warnings.append(
                            f"converted:{object_id}:"
                            "transformed_auto_layout_flattened_to_"
                            "snapshot_absolute_geometry"
                        )
                    affine_rotation: float | None = None
                    if affine_snapshot_active:
                        (
                            node_box,
                            affine_rotation,
                            affine_recovery,
                        ) = _figma_affine_snapshot_geometry(
                            node,
                            effective_figma_linear,
                        )
                        content["figma_affine_snapshot_geometry"] = (
                            affine_recovery
                        )
                        if auto_layout_recovery.get("outer_affine_ignored"):
                            affine_recovery["outer_affine_ignored"] = True
                            affine_recovery["outer_affine_reason"] = (
                                auto_layout_recovery.get(
                                    "outer_affine_reason"
                                )
                            )
                            affine_recovery["outer_affine_linear_transform"] = (
                                copy.deepcopy(
                                    auto_layout_recovery.get(
                                        "outer_affine_linear_transform"
                                    )
                                )
                            )
                        if str(affine_recovery.get("status") or "").startswith(
                            "blocked_"
                        ):
                            warnings.append(
                                f"blocked:{node.get('id')}:AFFINE:"
                                f"{affine_recovery.get('reason')}"
                            )
                    elif not _figma_linear_transform_is_identity(
                        effective_figma_linear
                    ):
                        # Ordinary transformed nodes do not need their parent
                        # flow flattened, but they still need the same
                        # cumulative affine-to-center-pivot conversion. Using
                        # the already transformed Figma AABB as Painter's local
                        # width/height and then applying the archive's auxiliary
                        # rotation field rotates the AABB a second time.
                        (
                            candidate_box,
                            candidate_rotation,
                            candidate_recovery,
                        ) = _figma_affine_snapshot_geometry(
                            node,
                            effective_figma_linear,
                        )
                        if (
                            candidate_recovery.get("status")
                            == "rotation_scale_mapped"
                        ):
                            node_box = candidate_box
                            affine_rotation = candidate_rotation
                            candidate_recovery["scope"] = (
                                "ordinary_node_cumulative_transform"
                            )
                            content["figma_affine_snapshot_geometry"] = (
                                candidate_recovery
                            )
                            warnings.append(
                                f"converted:{node.get('id')}:AFFINE:"
                                "orthogonal_transform_mapped"
                            )
                    elif (
                        not _figma_linear_transform_is_identity(
                            parent_figma_linear
                        )
                        or not _figma_linear_transform_is_identity(
                            _figma_node_linear_transform(node)
                        )
                    ):
                        # A parent and child transform can cancel exactly in
                        # canvas space (the Grida archive contains paired
                        # reflections whose cumulative matrix is identity).
                        # The auxiliary ``rotation`` field has already been
                        # consumed by that hierarchy. Falling back to it here
                        # rotates the resolved Figma AABB a second time.
                        affine_rotation = 0.0
                        a, c, b, d = effective_figma_linear
                        content["figma_affine_snapshot_geometry"] = {
                            "status": "cumulative_identity_consumed",
                            "scope": "ordinary_node_cumulative_transform",
                            "effective_linear_transform": [[a, c], [b, d]],
                            "relative_transform": copy.deepcopy(
                                node.get("relativeTransform")
                            ),
                            "source_size": copy.deepcopy(node.get("size")),
                            "source_absolute_bounding_box": copy.deepcopy(
                                node.get("absoluteBoundingBox")
                            ),
                            "source_rotation": copy.deepcopy(
                                node.get("rotation")
                            ),
                            "rotation": 0.0,
                        }
                        warnings.append(
                            f"converted:{node.get('id')}:AFFINE:"
                            "cumulative_identity_transform_consumed"
                        )
                    for unsupported_paint in content.get(
                        "figma_unsupported_paints", []
                    ):
                        warnings.append(
                            f"blocked:{node.get('id')}:PAINT:"
                            f"{unsupported_paint.get('type')}:"
                            f"{unsupported_paint.get('reason')}"
                        )
                    has_vector_geometry = bool(
                        content.get("vector_fill_geometry")
                        or content.get("vector_stroke_geometry")
                        or content.get("vector_paths")
                    )
                    vector_recovery = content.get(
                        "figma_vector_geometry_recovery"
                    )
                    vector_recovery = (
                        vector_recovery
                        if isinstance(vector_recovery, Mapping)
                        else {}
                    )
                    if kind == "path" and vector_recovery:
                        if vector_recovery.get("source") == "figma_render_api":
                            warnings.append(
                                f"converted:{node.get('id')}:VECTOR:"
                                "figma_svg_render_fallback_noneditable"
                            )
                        else:
                            warnings.append(
                                f"converted:{node.get('id')}:VECTOR:"
                                "semantic_primitive_geometry_recovered:"
                                f"{vector_recovery.get('kind')}"
                            )
                    elif kind == "path" and not has_vector_geometry:
                        warnings.append(
                            f"blocked:{node.get('id')}:VECTOR:"
                            "missing_geometry_paths"
                        )
                    if (
                        kind == "image"
                        and content.get("image_ref")
                        and not content.get("source_path")
                    ):
                        warnings.append(
                            f"blocked:{node.get('id')}:IMAGE:missing_asset:"
                            f"{content.get('image_ref')}"
                        )
                    for image_reason in content.get(
                        "figma_image_render_blockers", []
                    ):
                        warnings.append(
                            f"blocked:{node.get('id')}:IMAGE:"
                            f"{image_reason}"
                        )
                    individual_stroke_weights = node.get(
                        "individualStrokeWeights"
                    )
                    if isinstance(individual_stroke_weights, Mapping):
                        if content.get("vector_stroke_geometry"):
                            warnings.append(
                                f"converted:{node.get('id')}:STROKE:"
                                "individual_stroke_weights_rendered_from_"
                                "expanded_geometry"
                            )
                        else:
                            warnings.append(
                                f"blocked:{node.get('id')}:STROKE:"
                                "individual_stroke_weights_require_"
                                "expanded_geometry_or_bake"
                            )
                    role = "none"
                    component_id = ""
                    source_object_id = ""
                    component_scope_id = ""
                    component_scope_source_object_id = ""
                    if node_type == "COMPONENT":
                        component_id = _figma_component_stable_id(node)
                        role = "definition"
                        source_object_id = object_id
                        component_set = component_set_index.get(
                            str(node.get("id") or "")
                        )
                        family_id = (
                            str(component_set.get("family_id") or "")
                            if component_set
                            else ""
                        )
                        base_component_id = (
                            family_id
                            if family_id and family_id != component_id
                            else ""
                        )
                        family_variants = (
                            [
                                str(value)
                                for value in component_set.get(
                                    "component_ids", []
                                )
                                if str(value) and str(value) != component_id
                            ]
                            if component_set and not base_component_id
                            else []
                        )
                        property_definitions = (
                            dict(component_set.get("property_definitions") or {})
                            if component_set
                            else {}
                        )
                        property_definitions.update(
                            _figma_component_property_definitions(
                                node.get("componentPropertyDefinitions")
                            )
                        )
                        variant_properties = _figma_component_properties(
                            node.get("variantProperties")
                        )
                        components.append(
                            {
                                "id": component_id,
                                "name": str(node.get("name") or "Component"),
                                "root_object_id": object_id,
                                "base_component_id": base_component_id,
                                "property_definitions": property_definitions,
                                "variant_ids": family_variants,
                                "metadata": {
                                    "figma_node_id": str(node.get("id") or ""),
                                    "figma_key": str(node.get("key") or ""),
                                    "figma_component_set_id": (
                                        str(
                                            component_set.get("figma_node_id")
                                            or ""
                                        )
                                        if component_set
                                        else ""
                                    ),
                                    "variant_key": _figma_variant_key(node),
                                    "variant_properties": variant_properties,
                                    "variant_source_map": (
                                        _figma_variant_source_map(node)
                                    ),
                                },
                            }
                        )
                    elif node_type == "INSTANCE":
                        component_id = (
                            _tigerstudio_plugin_text(node, "component_id")
                            or _stable_id(
                                "component",
                                node.get("componentId")
                                or node.get("mainComponent", ""),
                            )
                        )
                        role = "instance"
                        if definition_component_id:
                            component_scope_id = definition_component_id
                            component_scope_source_object_id = object_id
                    elif definition_component_id:
                        component_id = definition_component_id
                        role = "definition"
                        source_object_id = object_id
                    elif instance_component_id:
                        component_id = (
                            _tigerstudio_plugin_text(node, "component_id")
                            or instance_component_id
                        )
                        source_object_id = _tigerstudio_plugin_text(
                            node, "component_source_object_id"
                        )
                        role = "instance" if source_object_id else "none"
                    objects.append(
                        {
                            "id": object_id,
                            "kind": kind,
                            "name": str(node.get("name") or kind.title()),
                            "artboard_id": frame_id,
                            "parent_id": parent_id,
                            "x": node_box["x"] - frame_box["x"],
                            "y": node_box["y"] - frame_box["y"],
                            "width": node_box["width"],
                            "height": node_box["height"],
                            "rotation": (
                                affine_rotation
                                if affine_rotation is not None
                                else (
                                    0.0
                                    if bool(
                                        vector_recovery.get(
                                            "consumed_rotation", False
                                        )
                                    )
                                    else _figma_rotation_degrees(node)
                                )
                            ),
                            "opacity": max(
                                0.0, min(1.0, _number(node.get("opacity"), 1.0))
                            ),
                            "visible": bool(node.get("visible", True)),
                            "locked": bool(node.get("locked", False)),
                            "clip_content": bool(
                                node.get("clipsContent", False)
                            ),
                            "z_index": len(objects),
                            "style": _map_style(node),
                            "content": content,
                            "constraints": _map_constraints(node),
                            "layout": mapped_layout,
                            "component_id": component_id,
                            "component_role": role,
                            "component_source_object_id": source_object_id,
                            "component_scope_id": component_scope_id,
                            "component_scope_source_object_id": (
                                component_scope_source_object_id
                            ),
                            "component_properties": _figma_component_properties(
                                node.get("componentProperties")
                            ),
                            "component_property_bindings": (
                                component_property_bindings
                            ),
                            "token_bindings": _map_token_bindings(node),
                        }
                    )
                    figma_targets[str(node.get("id") or "")] = (
                        "object",
                        object_id,
                    )
                    raw_reactions = node.get("reactions")
                    if not isinstance(raw_reactions, list):
                        raw_reactions = node.get("interactions")
                    if isinstance(raw_reactions, list) and raw_reactions:
                        pending_reactions.append(
                            {
                                "source_kind": "object",
                                "source_id": object_id,
                                "source_figma_node_id": str(
                                    node.get("id") or ""
                                ),
                                "artboard_id": frame_id,
                                "reactions": copy.deepcopy(raw_reactions),
                            }
                        )
                    supported += 1
                    current_parent = object_id
                child_baseline_offsets = (
                    _figma_resolved_child_baseline_offsets(node)
                )
                if child_baseline_offsets:
                    warnings.append(
                        f"converted:{node.get('id')}:AUTO_LAYOUT:"
                        "baseline_alignment_preserved_from_resolved_geometry"
                    )
                child_parent_layout_mode = str(
                    node.get("layoutMode") or "NONE"
                ).casefold()
                if child_parent_layout_mode not in {"horizontal", "vertical"}:
                    child_parent_layout_mode = "none"
                for child in node.get("children", []):
                    if isinstance(child, Mapping):
                        visit(
                            child,
                            current_parent,
                            parent_layout_mode=child_parent_layout_mode,
                            definition_component_id=(
                                component_id
                                if role == "definition"
                                else definition_component_id
                            ),
                            instance_component_id=(
                                component_id
                                if node_type == "INSTANCE"
                                else instance_component_id
                            ),
                            parent_figma_linear=effective_figma_linear,
                            parent_affine_snapshot=affine_snapshot_active,
                            parent_baseline_offsets=child_baseline_offsets,
                        )
            if str(frame.get("type") or "").upper() == "SECTION":
                section_objects = objects[frame_object_start:]
                sections.append(
                    {
                        "id": _figma_node_stable_id(frame, "section"),
                        "name": str(frame.get("name") or "Section"),
                        "page_name": str(page.get("name") or ""),
                        # Sections share the canvas with the artboard imported
                        # from the same frame, so they must use the same
                        # page-local placement rather than raw Figma coords.
                        "x": float(artboard_x),
                        "y": float(artboard_y),
                        "width": float(frame_box["width"]),
                        "height": float(frame_box["height"]),
                        "object_ids": [
                            str(row["id"]) for row in section_objects
                        ],
                        "collapsed": bool(frame.get("devStatus") == "READY_FOR_DEV"),
                        "figma_node_id": str(frame.get("id") or ""),
                    }
                )

            if str(frame.get("type") or "").upper() == "COMPONENT":
                visit(frame)
            else:
                frame_linear = _figma_node_linear_transform(frame)
                for child in frame.get("children", []):
                    if isinstance(child, Mapping):
                        frame_layout_mode = str(
                            frame.get("layoutMode") or "NONE"
                        ).casefold()
                        visit(
                            child,
                            parent_layout_mode=(
                                frame_layout_mode
                                if frame_layout_mode in {"horizontal", "vertical"}
                                else "none"
                            ),
                            parent_figma_linear=frame_linear,
                            # The top-level artboard already owns absolute
                            # snapshot geometry and is not a Painter object.
                            # Let a nested transformed layout establish its
                            # own recoverable affine subtree root.
                            parent_affine_snapshot=False,
                        )
                if str(frame.get("type") or "").upper() == "INSTANCE":
                    # A top-level Figma instance is a screen/artboard, so its
                    # expanded descendants remain editable snapshot objects.
                    # Their component property references still point into
                    # the absent instance root and cannot be active Painter
                    # definition bindings.
                    for snapshot_row in objects[frame_object_start:]:
                        if snapshot_row.get("component_property_bindings"):
                            _detach_figma_component_property_bindings(
                                snapshot_row,
                                warnings,
                            )

    component_ids_by_figma_node = {
        str((row.get("metadata") or {}).get("figma_node_id") or ""): str(
            row["id"]
        )
        for row in components
    }
    component_ids_by_figma_key = {
        str((row.get("metadata") or {}).get("figma_key") or ""): str(row["id"])
        for row in components
        if str((row.get("metadata") or {}).get("figma_key") or "")
    }
    object_ids_by_figma_node = {
        str(node.get("id") or ""): _figma_node_stable_id(node)
        for node in _walk_figma_nodes(root)
        if str(node.get("id") or "")
    }
    objects_by_id = {str(row["id"]): row for row in objects}
    for component in components:
        for property_name, definition in component.get(
            "property_definitions", {}
        ).items():
            property_type = str(definition.get("type") or "")
            if property_type == "slot":
                source_id = object_ids_by_figma_node.get(
                    str(definition.get("default") or ""),
                    str(definition.get("default") or ""),
                )
                definition["default"] = source_id
                source = objects_by_id.get(source_id)
                if source is not None:
                    source["component_slot_property"] = str(property_name)
                definition["preferred_values"] = [
                    component_ids_by_figma_key.get(str(item), str(item))
                    for item in definition.get("preferred_values", [])
                ]
                continue
            if property_type != "instance_swap":
                continue
            default_value = str(definition.get("default") or "")
            if default_value in component_ids_by_figma_node:
                definition["default"] = component_ids_by_figma_node[
                    default_value
                ]
            definition["preferred_values"] = [
                component_ids_by_figma_key.get(str(item), str(item))
                for item in definition.get("preferred_values", [])
            ]
    component_roots = {
        str(row["id"]): str(row["root_object_id"]) for row in components
    }
    component_by_id = {str(row["id"]): row for row in components}
    missing_remote_component_ids: set[str] = set()
    for row in objects:
        if row.get("component_role") != "instance":
            continue
        component_id = str(row.get("component_id") or "")
        source_object_id = component_roots.get(component_id, "")
        if source_object_id:
            row["component_source_object_id"] = source_object_id
            component = component_by_id[component_id]
            for property_name, value in list(
                row.get("component_properties", {}).items()
            ):
                definition = component.get("property_definitions", {}).get(
                    property_name
                )
                if (
                    definition
                    and definition.get("type") == "instance_swap"
                    and str(value) in component_ids_by_figma_node
                ):
                    row["component_properties"][property_name] = (
                        component_ids_by_figma_node[str(value)]
                    )
            row["variant"] = str(
                (component.get("metadata") or {}).get("variant_key") or ""
            )
            continue
        missing_remote_component_ids.add(component_id)
        row["content"]["figma_component_id"] = component_id
        remote = dict(row["content"].get("remote_component") or {})
        remote["status"] = "missing"
        row["content"]["remote_component"] = remote
        row["component_id"] = ""
        row["component_role"] = "none"
        _detach_figma_component_property_bindings(row, warnings)
        warnings.append(
            f"converted:{row['id']}:remote_component_instance_to_group"
        )
    # REST snapshots expand an INSTANCE into editable descendant nodes. Those
    # rows inherit the instance component id during traversal, but a remote
    # component has no local definition that can own that id. Once its root is
    # downgraded to a group, detach the inherited descendants as well so the
    # resulting plain hierarchy has no dangling component references.
    if missing_remote_component_ids:
        for row in objects:
            if (
                row.get("component_role") == "none"
                and str(row.get("component_id") or "")
                in missing_remote_component_ids
            ):
                row["component_id"] = ""
                row["component_source_object_id"] = ""
                _detach_figma_component_property_bindings(row, warnings)

    # Expanded instance descendants inherit the component id but not the
    # definition node they were cloned from, so nothing downstream can tell an
    # authored override from a default. The UMG adapter then replays the
    # definition and a button labelled "Start" exports as "Get started". Pair
    # the two subtrees and record the link. Pairing is positional and fails
    # closed: an instance whose content was swapped or grafted stays unlinked
    # rather than mislabelled.
    _link_expanded_instance_descendants(objects, objects_by_id, warnings)

    # REST /nodes responses include the resolved descendants of local
    # instances. Their componentPropertyReferences describe the source
    # definition and must not become active bindings on the expanded instance
    # copy, which lives outside that definition. Preserve the source metadata
    # for recovery/inspection, but detach it from Tiger's editable binding
    # contract.
    for row in objects:
        if not row.get("component_property_bindings"):
            continue
        parent = objects_by_id.get(str(row.get("parent_id") or ""))
        while parent is not None:
            parent_content = parent.get("content")
            parent_content = (
                parent_content if isinstance(parent_content, Mapping) else {}
            )
            if str(parent_content.get("figma_type") or "").upper() == "INSTANCE":
                _detach_figma_component_property_bindings(
                    row,
                    warnings,
                    reason="expanded_instance_property_bindings_resolved",
                )
                break
            parent = objects_by_id.get(str(parent.get("parent_id") or ""))

    figma_node_index = {
        str(node.get("id") or ""): node
        for node in _walk_figma_nodes(root)
        if str(node.get("id") or "")
    }
    siblings: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in objects:
        siblings.setdefault(
            (str(row["artboard_id"]), str(row["parent_id"])),
            [],
        ).append(row)
    for rows in siblings.values():
        rows.sort(key=lambda item: int(item.get("z_index") or 0))
        for index, row in enumerate(rows):
            figma_type = str((row.get("content") or {}).get("figma_type") or "")
            source_id = str((row.get("content") or {}).get("figma_node_id") or "")
            source_node = figma_node_index.get(source_id, {})
            raw_mask = bool(source_node.get("isMask", False))
            if not raw_mask and figma_type != "MASK":
                continue
            targets: list[str] = []
            for candidate in rows[index + 1 :]:
                candidate_source = figma_node_index.get(
                    str(
                        (candidate.get("content") or {}).get(
                            "figma_node_id"
                        )
                        or ""
                    ),
                    {},
                )
                if bool(candidate_source.get("isMask", False)):
                    break
                targets.append(str(candidate["id"]))
            row["mask"] = {
                "enabled": True,
                "inverted": False,
                "outline": bool(source_node.get("isMaskOutline", False)),
                "target_ids": targets,
            }
            mask_type = str(source_node.get("maskType") or "ALPHA").upper()
            requires_raster_alpha = _figma_mask_requires_raster_alpha(
                source_node
            )
            content = row.get("content")
            content = dict(content) if isinstance(content, Mapping) else {}
            content["figma_mask"] = {
                "type": mask_type.casefold(),
                "requires_raster_alpha": requires_raster_alpha,
                "workspace_rendering": {
                    "ALPHA": "pixel_alpha",
                    "LUMINANCE": "pixel_luminance",
                    "VECTOR": "geometry_clip",
                }.get(mask_type, "geometry_clip"),
            }
            row["content"] = content

    object_component_ids = {
        str(row["id"]): str(row.get("component_id") or "")
        for row in objects
    }
    trigger_map = {
        "ON_CLICK": "click",
        "ON_HOVER": "hover",
        "MOUSE_ENTER": "mouse_enter",
        "MOUSE_LEAVE": "mouse_leave",
        "MOUSE_DOWN": "press",
        "ON_PRESS": "press",
        "ON_DRAG": "drag",
        "ON_KEY_DOWN": "keyboard",
        "AFTER_TIMEOUT": "delay",
        "ON_GAMEPAD": "gamepad",
    }
    navigation_map = {
        "NAVIGATE": "navigate",
        "OVERLAY": "open_overlay",
        "SWAP": "swap_overlay",
        "CHANGE_TO": "change_variant",
        "SCROLL_TO": "scroll_to",
    }
    reaction_recovery: list[dict[str, Any]] = []
    source_reaction_count = 0
    source_reaction_action_count = 0
    native_reaction_count = 0
    native_reaction_action_count = 0

    def append_unique(values: list[str], reason: str) -> None:
        if reason and reason not in values:
            values.append(reason)

    for pending in pending_reactions:
        source_kind = str(pending.get("source_kind") or "object")
        source_id = str(pending.get("source_id") or "")
        source_figma_node_id = str(
            pending.get("source_figma_node_id") or ""
        )
        source_artboard_id = str(pending.get("artboard_id") or "")
        reactions = pending.get("reactions")
        reactions = reactions if isinstance(reactions, list) else []
        for reaction_index, raw_reaction in enumerate(reactions):
            source_reaction_count += 1
            reaction = (
                raw_reaction if isinstance(raw_reaction, Mapping) else {}
            )
            recovery_reasons: list[str] = []
            blocked_actions: list[dict[str, Any]] = []
            native_action_indices: list[int] = []
            if source_kind != "object":
                append_unique(
                    recovery_reasons,
                    "figma_reaction_artboard_source_unsupported",
                )
            if not isinstance(raw_reaction, Mapping):
                append_unique(
                    recovery_reasons,
                    "figma_reaction_record_malformed",
                )

            raw_trigger = reaction.get("trigger")
            trigger_row = (
                raw_trigger if isinstance(raw_trigger, Mapping) else {}
            )
            trigger_type = str(trigger_row.get("type") or "").upper()
            trigger = trigger_map.get(trigger_type, "")
            if not isinstance(raw_trigger, Mapping):
                append_unique(
                    recovery_reasons,
                    (
                        "figma_reaction_trigger_missing"
                        if raw_trigger is None
                        else "figma_reaction_trigger_malformed"
                    ),
                )
            elif not trigger_type:
                append_unique(
                    recovery_reasons,
                    "figma_reaction_trigger_missing",
                )
            elif not trigger:
                append_unique(
                    recovery_reasons,
                    "figma_reaction_trigger_unsupported",
                )

            raw_actions_value = reaction.get("actions")
            if isinstance(raw_actions_value, list):
                raw_actions = list(raw_actions_value)
            elif "action" in reaction:
                raw_actions = [reaction.get("action")]
            elif "actions" in reaction:
                raw_actions = [raw_actions_value]
                append_unique(
                    recovery_reasons,
                    "figma_reaction_actions_container_malformed",
                )
            else:
                raw_actions = []
            source_reaction_action_count += len(raw_actions)
            if not raw_actions:
                append_unique(
                    recovery_reasons,
                    "figma_reaction_has_no_actions",
                )
            source_blocking_reasons = list(recovery_reasons)

            for action_index, raw_action in enumerate(raw_actions):
                action_reasons: list[str] = []
                mapped_action = ""
                destination = ""
                target_kind = ""
                target_id = ""
                action_type = ""
                navigation = ""
                if not isinstance(raw_action, Mapping):
                    append_unique(
                        action_reasons,
                        "figma_reaction_action_malformed",
                    )
                else:
                    action_type = str(raw_action.get("type") or "").upper()
                    navigation = str(
                        raw_action.get("navigation") or ""
                    ).upper()
                    destination = str(raw_action.get("destinationId") or "")
                    if action_type == "BACK":
                        mapped_action = "back"
                    elif action_type in {"CLOSE", "CLOSE_OVERLAY"}:
                        mapped_action = "close_overlay"
                    elif action_type == "URL":
                        append_unique(
                            action_reasons,
                            "figma_prototype_url_action_requires_runtime_policy",
                        )
                    elif action_type == "NODE":
                        if not navigation:
                            append_unique(
                                action_reasons,
                                "figma_reaction_navigation_missing",
                            )
                        else:
                            mapped_action = navigation_map.get(navigation, "")
                            if not mapped_action:
                                append_unique(
                                    action_reasons,
                                    "figma_reaction_navigation_unsupported",
                                )
                        if not destination:
                            append_unique(
                                action_reasons,
                                (
                                    "figma_scroll_to_missing_destination"
                                    if navigation == "SCROLL_TO"
                                    else "figma_reaction_destination_missing"
                                ),
                            )
                        else:
                            target_kind, target_id = figma_targets.get(
                                destination,
                                ("", ""),
                            )
                            if not target_kind:
                                append_unique(
                                    action_reasons,
                                    "figma_reaction_destination_unresolved",
                                )
                        if (
                            mapped_action == "scroll_to"
                            and target_kind
                            and target_kind != "object"
                        ):
                            append_unique(
                                action_reasons,
                                "figma_scroll_to_requires_object_destination",
                            )
                        if mapped_action == "change_variant" and (
                            target_kind != "object"
                            or not object_component_ids.get(target_id, "")
                        ):
                            append_unique(
                                action_reasons,
                                (
                                    "figma_change_to_destination_requires_"
                                    "local_component"
                                ),
                            )
                    elif not action_type:
                        append_unique(
                            action_reasons,
                            "figma_reaction_action_type_missing",
                        )
                    else:
                        append_unique(
                            action_reasons,
                            "figma_reaction_action_type_unsupported",
                        )

                for reason in source_blocking_reasons:
                    append_unique(action_reasons, reason)
                if action_reasons:
                    for reason in action_reasons:
                        append_unique(recovery_reasons, reason)
                    blocked_actions.append(
                        {
                            "action_index": action_index,
                            "action_type": action_type,
                            "navigation": navigation,
                            "destination_id": destination,
                            "reasons": action_reasons,
                            "raw_action": copy.deepcopy(raw_action),
                        }
                    )
                    warnings.append(
                        "blocked_reaction:"
                        f"{source_figma_node_id or source_id}:"
                        f"{reaction_index}:{action_index}:"
                        f"{action_reasons[0]}"
                    )
                    continue

                native_action_indices.append(action_index)
                native_reaction_action_count += 1
                assert isinstance(raw_action, Mapping)
                interactions.append(
                    {
                        "id": _stable_id(
                            "interaction",
                            f"{source_id}-{reaction_index}-{action_index}",
                        ),
                        "name": f"Figma {trigger} {mapped_action}",
                        "source_object_id": source_id,
                        "trigger": trigger,
                        "action": mapped_action,
                        "target_artboard_id": (
                            target_id if target_kind == "artboard" else ""
                        ),
                        "target_object_id": (
                            (
                                source_id
                                if mapped_action == "change_variant"
                                else target_id
                            )
                            if target_kind == "object"
                            else ""
                        ),
                        "component_id": (
                            object_component_ids.get(target_id, "")
                            if mapped_action == "change_variant"
                            else ""
                        ),
                        "parameters": {
                            "figma_transition": copy.deepcopy(
                                raw_action.get("transition")
                            ),
                            "preserve_scroll_position": bool(
                                raw_action.get("preserveScrollPosition", False)
                            ),
                            "figma_reaction": {
                                "source_kind": source_kind,
                                "source_object_id": source_id,
                                "source_figma_node_id": source_figma_node_id,
                                "artboard_id": source_artboard_id,
                                "reaction_index": reaction_index,
                                "action_index": action_index,
                                "raw_reaction": copy.deepcopy(raw_reaction),
                                "raw_trigger": copy.deepcopy(raw_trigger),
                                "raw_action": copy.deepcopy(raw_action),
                            },
                        },
                    }
                )

            if recovery_reasons:
                reaction_recovery.append(
                    {
                        "id": _stable_id(
                            "figma-reaction-recovery",
                            f"{source_kind}-{source_id}-{reaction_index}",
                        ),
                        "status": (
                            "partial" if native_action_indices else "blocked"
                        ),
                        "source_kind": source_kind,
                        "source_object_id": (
                            source_id if source_kind == "object" else ""
                        ),
                        "source_artboard_id": (
                            source_id if source_kind == "artboard" else ""
                        ),
                        "source_figma_node_id": source_figma_node_id,
                        "artboard_id": source_artboard_id,
                        "reaction_index": reaction_index,
                        "trigger_type": trigger_type,
                        "reasons": recovery_reasons,
                        "native_action_indices": native_action_indices,
                        "blocked_actions": blocked_actions,
                        "raw_reaction": copy.deepcopy(raw_reaction),
                    }
                )
                if not blocked_actions:
                    warnings.append(
                        "blocked_reaction:"
                        f"{source_figma_node_id or source_id}:"
                        f"{reaction_index}:{recovery_reasons[0]}"
                    )
            else:
                native_reaction_count += 1

    tokens: list[dict[str, Any]] = []
    variable_root = (
        variables_payload.get("meta")
        if isinstance(variables_payload, Mapping)
        else {}
    )
    variable_root = variable_root if isinstance(variable_root, Mapping) else {}
    variables = variable_root.get("variables")
    variables = variables if isinstance(variables, Mapping) else {}
    for variable_id, row in variables.items():
        if not isinstance(row, Mapping):
            continue
        resolved_type = str(row.get("resolvedType") or "").upper()
        kind = {
            "COLOR": "color",
            "FLOAT": "spacing",
            "STRING": "typography",
        }.get(resolved_type)
        if not kind:
            continue
        values = row.get("valuesByMode")
        values = values if isinstance(values, Mapping) else {}
        first = next(iter(values.values()), None)
        value = _color(first, "#000000") if resolved_type == "COLOR" else first
        tokens.append(
            {
                "id": _stable_id("token", variable_id),
                "name": str(row.get("name") or variable_id),
                "kind": kind,
                "value": value,
                "description": str(row.get("description") or ""),
            }
        )

    token_ids = {str(row["id"]) for row in tokens}
    for row in objects:
        _resolve_figma_variable_bindings(row, token_ids, warnings)
    _resolve_figma_artboard_variable_bindings(
        artboard_variable_bindings,
        token_ids,
        warnings,
    )

    _capture_figma_center_constraint_offsets(objects, artboards)
    _convert_figma_hug_fill_cycles(objects, warnings)

    source_component_property_binding_count = sum(
        len(references)
        for node in _walk_figma_nodes(root)
        for references in [node.get("componentPropertyReferences")]
        if isinstance(references, Mapping)
    )
    native_component_property_binding_count = sum(
        len(row.get("component_property_bindings", {}))
        for row in objects
    )
    recovered_component_property_binding_count = sum(
        len((row.get("content") or {}).get(
            "figma_component_property_bindings",
            {},
        ))
        for row in objects
        if isinstance(
            (row.get("content") or {}).get(
                "figma_component_property_bindings"
            ),
            Mapping,
        )
    )

    preferred_artboard_id = _preferred_artboard_id(artboards, objects)
    preferred_page_id = next(
        (
            str(row["page_id"])
            for row in artboards
            if str(row["id"]) == preferred_artboard_id
        ),
        str(imported_pages[0]["id"]),
    )
    document = normalize_ui_document(
        {
            "document_id": _stable_id("document", file_key),
            "active_page_id": preferred_page_id,
            "active_artboard_id": preferred_artboard_id,
            "pages": imported_pages,
            "artboards": artboards,
            "objects": objects,
            "sections": sections,
            "components": components,
            "tokens": tokens,
            "interactions": interactions,
            "linked_targets": {
                "figma": {
                    "file_key": file_key,
                    "source": source,
                    "name": str(payload.get("name") or ""),
                    "version": str(payload.get("version") or ""),
                    "last_modified": str(payload.get("lastModified") or ""),
                    "mode": "imported",
                    "artboard_variable_bindings": artboard_variable_bindings,
                    "reaction_recovery": reaction_recovery,
                }
            },
        }
    )
    raw_comments = payload.get("comments")
    raw_comments = raw_comments if isinstance(raw_comments, list) else []
    if raw_comments:
        from app.painter_ui_review import add_ui_review_comment

        for raw_comment in raw_comments:
            if not isinstance(raw_comment, Mapping):
                continue
            message = str(raw_comment.get("message") or "").strip()
            if not message:
                continue
            client_meta = raw_comment.get("client_meta")
            client_meta = (
                client_meta if isinstance(client_meta, Mapping) else {}
            )
            node_id = str(
                client_meta.get("node_id")
                or client_meta.get("nodeId")
                or ""
            )
            target_kind, target_id = figma_targets.get(node_id, ("", ""))
            try:
                document, _comment = add_ui_review_comment(
                    document,
                    text=message,
                    object_id=target_id if target_kind == "object" else "",
                    artboard_id=(
                        target_id
                        if target_kind == "artboard"
                        else ""
                    ),
                    author=str(
                        (raw_comment.get("user") or {}).get("handle")
                        if isinstance(raw_comment.get("user"), Mapping)
                        else ""
                    ),
                    x=_number(client_meta.get("x"), 0.5),
                    y=_number(client_meta.get("y"), 0.5),
                )
            except ValueError as exc:
                warnings.append(f"converted:comment:{exc}")
    validation = validate_ui_document(document)
    report = {
        "schema": FIGMA_IMPORT_SCHEMA,
        "ok": not validation["errors"],
        "file_key": file_key,
        "name": str(payload.get("name") or ""),
        "page_count": len(document["pages"]),
        "artboard_count": len(document["artboards"]),
        "object_count": len(document["objects"]),
        "component_count": len(document["components"]),
        "token_count": len(document["tokens"]),
        "variable_binding_count": sum(
            len((row.get("content") or {}).get("figma_variable_bindings", []))
            for row in document["objects"]
        )
        + len(artboard_variable_bindings),
        "unresolved_variable_binding_count": sum(
            1
            for row in document["objects"]
            for binding in (
                (row.get("content") or {}).get("figma_variable_bindings", [])
            )
            if isinstance(binding, Mapping)
            and str(binding.get("status") or "") == "unresolved"
        )
        + sum(
            1
            for binding in artboard_variable_bindings
            if str(binding.get("status") or "") == "unresolved"
        ),
        "variable_binding_relink_count": sum(
            1
            for row in document["objects"]
            for binding in (
                (row.get("content") or {}).get("figma_variable_bindings", [])
            )
            if isinstance(binding, Mapping)
            and str(binding.get("status") or "") != "native"
        )
        + sum(
            1
            for binding in artboard_variable_bindings
            if str(binding.get("status") or "") != "native"
        ),
        "source_component_property_binding_count": (
            source_component_property_binding_count
        ),
        "native_component_property_binding_count": (
            native_component_property_binding_count
        ),
        "recovered_component_property_binding_count": (
            recovered_component_property_binding_count
        ),
        "component_property_binding_count_conserved": (
            source_component_property_binding_count
            == native_component_property_binding_count
            + recovered_component_property_binding_count
        ),
        "interaction_count": len(document["interactions"]),
        "source_reaction_count": source_reaction_count,
        "source_reaction_action_count": source_reaction_action_count,
        "native_reaction_count": native_reaction_count,
        "native_reaction_action_count": native_reaction_action_count,
        "blocked_recovery_reaction_count": len(reaction_recovery),
        "blocked_recovery_action_count": sum(
            len(row.get("blocked_actions", []))
            for row in reaction_recovery
        ),
        "reaction_count_conserved": (
            source_reaction_count
            == native_reaction_count + len(reaction_recovery)
        ),
        "reaction_action_count_conserved": (
            source_reaction_action_count
            == native_reaction_action_count
            + sum(
                len(row.get("blocked_actions", []))
                for row in reaction_recovery
            )
        ),
        "section_count": len(document.get("sections", [])),
        "comment_count": len(
            (
                document.get("linked_targets", {})
                .get("review", {})
                .get("comments", [])
            )
        ),
        "active_artboard_id": document["active_artboard_id"],
        "active_page_id": document["active_page_id"],
        "supported_node_count": supported,
        "blocked_node_count": skipped,
        "warnings": warnings + list(validation["warnings"]),
        "errors": list(validation["errors"]),
    }
    report["resources"] = inspect_figma_resources(document)
    if report["errors"]:
        raise PainterUIFigmaError(
            "Figma conversion produced an invalid document: "
            + ", ".join(report["errors"][:5])
        )
    return document, report


def inspect_figma_resources(
    document: Mapping[str, Any],
    *,
    available_font_families: object = None,
    normalize: bool = True,
) -> dict[str, Any]:
    # Read-only inspection: callers holding a canonical document skip the
    # defensive copy, which dominates click latency on large files.
    normalized = normalize_ui_document(document) if normalize else document
    available = (
        {
            str(name).strip().casefold()
            for name in available_font_families
            if str(name).strip()
        }
        if isinstance(available_font_families, (list, tuple, set, frozenset))
        else None
    )
    missing_images: list[dict[str, str]] = []
    image_count = 0
    requested_fonts: set[str] = set()
    for row in normalized.get("objects", []):
        kind = str(row.get("kind") or "")
        content = row.get("content")
        content = content if isinstance(content, Mapping) else {}
        if kind == "image":
            image_count += 1
            path_text = str(
                content.get("source_path")
                or content.get("image_path")
                or content.get("path")
                or ""
            ).strip()
            if not path_text or not Path(path_text).expanduser().is_file():
                missing_images.append(
                    {
                        "object_id": str(row.get("id") or ""),
                        "name": str(row.get("name") or "Image"),
                        "image_ref": str(content.get("image_ref") or ""),
                        "path": path_text,
                    }
                )
        if kind == "text":
            style = row.get("style")
            style = style if isinstance(style, Mapping) else {}
            family = str(
                style.get("font_family")
                or content.get("font_family")
                or ""
            ).strip()
            if family:
                requested_fonts.add(family)
    missing_fonts = sorted(
        family
        for family in requested_fonts
        if available is not None and family.casefold() not in available
    )
    return {
        "schema": "tigerstudio.painter.ui.figma_resources.v1",
        "image_count": image_count,
        "missing_image_count": len(missing_images),
        "missing_images": missing_images,
        "requested_fonts": sorted(requested_fonts),
        "missing_font_count": len(missing_fonts),
        "missing_fonts": missing_fonts,
    }


def _request_json(
    url: str,
    *,
    token: str,
    timeout: float,
    opener: Callable[..., Any] | None = None,
    optional: bool = False,
) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "TigerStudio-PainterUI/1.0",
    }
    if str(token).startswith("Bearer "):
        headers["Authorization"] = str(token)
    else:
        headers["X-Figma-Token"] = str(token)
    request = urllib.request.Request(url, headers=headers)
    open_request = opener or urllib.request.urlopen
    try:
        response = open_request(request, timeout=timeout)
        with response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if optional and exc.code in {403, 404}:
            return {}
        message = exc.read().decode("utf-8", errors="replace")
        raise PainterUIFigmaError(
            f"Figma API returned HTTP {exc.code}: {message[:240]}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PainterUIFigmaError(f"Could not connect to Figma: {exc}") from exc
    if not isinstance(payload, dict):
        raise PainterUIFigmaError("Figma API returned an invalid response")
    return payload


def _download_figma_images(
    image_urls: Mapping[str, str],
    *,
    root: Path,
    timeout: float,
    opener: Callable[..., Any] | None = None,
) -> tuple[dict[str, str], list[str]]:
    root.mkdir(parents=True, exist_ok=True)
    open_request = opener or urllib.request.urlopen
    paths: dict[str, str] = {}
    warnings: list[str] = []
    for image_ref, url in image_urls.items():
        ref = str(image_ref or "")
        address = str(url or "")
        if not ref or not address:
            continue
        request = urllib.request.Request(
            address,
            headers={"User-Agent": "TigerStudio-PainterUI/1.0"},
        )
        try:
            response = open_request(request, timeout=timeout)
            with response:
                data = response.read()
                content_type = str(response.headers.get("Content-Type") or "")
        except Exception as exc:
            warnings.append(f"image_download_failed:{ref}:{exc}")
            continue
        extension = mimetypes.guess_extension(content_type.split(";")[0]) or ".png"
        target = root / f"{_stable_id('image', ref)}{extension}"
        target.write_bytes(data)
        paths[ref] = str(target)
    return paths, warnings


def _figma_missing_vector_node_ids(payload: Mapping[str, Any]) -> list[str]:
    """Find scene VECTOR nodes for which the REST snapshot omitted paths."""

    result: list[str] = []
    seen: set[str] = set()
    stack: list[object] = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            node_id = str(value.get("id") or "")
            if (
                node_id
                and node_id not in seen
                and str(value.get("type") or "").upper() == "VECTOR"
                and not any(
                    isinstance(value.get(field), list)
                    and any(
                        isinstance(row, Mapping)
                        and str(row.get("path") or "").strip()
                        for row in value[field]
                    )
                    for field in ("fillGeometry", "strokeGeometry")
                )
            ):
                seen.add(node_id)
                result.append(node_id)
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return sorted(result)


def _figma_exact_effect_node_ids(payload: Mapping[str, Any]) -> list[str]:
    """Find nodes whose visible modern effects need exact PNG evidence."""

    result: list[str] = []
    seen: set[str] = set()
    stack: list[object] = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            node_id = str(value.get("id") or "")
            if (
                node_id
                and node_id not in seen
                and _figma_exact_effect_types(value)
            ):
                seen.add(node_id)
                result.append(node_id)
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return sorted(result)


def _figma_vector_render_urls(
    file_key: str,
    node_ids: list[str],
    *,
    token: str,
    timeout: float,
    opener: Callable[..., Any] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Request exact SVG renders when editable geometry is unavailable."""

    urls: dict[str, str] = {}
    warnings: list[str] = []
    encoded_key = urllib.parse.quote(file_key, safe="")
    for start in range(0, len(node_ids), 100):
        chunk = node_ids[start : start + 100]
        query = urllib.parse.urlencode(
            {
                "ids": ",".join(chunk),
                "format": "svg",
                "svg_include_id": "true",
            }
        )
        try:
            payload = _request_json(
                f"{FIGMA_API_ROOT}/images/{encoded_key}?{query}",
                token=token,
                timeout=timeout,
                opener=opener,
                optional=True,
            )
        except PainterUIFigmaError as exc:
            warnings.append(
                "vector_render_request_failed:"
                f"{','.join(chunk)}:{exc}"
            )
            continue
        images = payload.get("images")
        images = images if isinstance(images, Mapping) else {}
        for node_id in chunk:
            address = str(images.get(node_id) or "").strip()
            if address:
                urls[node_id] = address
    return urls, warnings


def _figma_effect_render_urls(
    file_key: str,
    node_ids: list[str],
    *,
    token: str,
    timeout: float,
    opener: Callable[..., Any] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Request exact 1x PNGs for visible modern Figma effects."""

    urls: dict[str, str] = {}
    warnings: list[str] = []
    encoded_key = urllib.parse.quote(file_key, safe="")
    for start in range(0, len(node_ids), 100):
        chunk = node_ids[start : start + 100]
        query = urllib.parse.urlencode(
            {
                "ids": ",".join(chunk),
                "format": "png",
                "scale": 1,
            }
        )
        try:
            payload = _request_json(
                f"{FIGMA_API_ROOT}/images/{encoded_key}?{query}",
                token=token,
                timeout=timeout,
                opener=opener,
                optional=True,
            )
        except PainterUIFigmaError as exc:
            warnings.append(
                "effect_render_request_failed:"
                f"{','.join(chunk)}:{exc}"
            )
            continue
        images = payload.get("images")
        images = images if isinstance(images, Mapping) else {}
        for node_id in chunk:
            address = str(images.get(node_id) or "").strip()
            if address:
                urls[node_id] = address
            else:
                warnings.append(f"effect_render_missing:{node_id}")
    return urls, warnings


def import_figma_file(
    source: str,
    *,
    token: str = "",
    timeout: float = 30.0,
    opener: Callable[..., Any] | None = None,
    asset_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    access_token = str(token or os.environ.get("FIGMA_ACCESS_TOKEN") or "").strip()
    if not access_token:
        raise PainterUIFigmaError(
            "A Figma token with file_content:read scope is required"
        )
    key = figma_file_key(source)
    encoded = urllib.parse.quote(key, safe="")
    payload = _request_json(
        f"{FIGMA_API_ROOT}/files/{encoded}?geometry=paths&plugin_data=shared",
        token=access_token,
        timeout=timeout,
        opener=opener,
    )
    image_payload = _request_json(
        f"{FIGMA_API_ROOT}/files/{encoded}/images",
        token=access_token,
        timeout=timeout,
        opener=opener,
        optional=True,
    )
    variable_payload = _request_json(
        f"{FIGMA_API_ROOT}/files/{encoded}/variables/local",
        token=access_token,
        timeout=timeout,
        opener=opener,
        optional=True,
    )
    resolved_asset_root = (
        Path(asset_root).expanduser().resolve()
        if asset_root
        else default_figma_asset_root(key)
    )
    image_urls = image_payload.get("meta", {}).get("images")
    if not isinstance(image_urls, Mapping):
        image_urls = image_payload.get("images")
    image_urls = image_urls if isinstance(image_urls, Mapping) else {}
    local_images, image_warnings = _download_figma_images(
        image_urls,
        root=resolved_asset_root,
        timeout=timeout,
        opener=opener,
    )
    missing_vector_ids = _figma_missing_vector_node_ids(payload)
    vector_render_urls, vector_request_warnings = _figma_vector_render_urls(
        key,
        missing_vector_ids,
        token=access_token,
        timeout=timeout,
        opener=opener,
    )
    local_vector_renders, vector_download_warnings = _download_figma_images(
        vector_render_urls,
        root=resolved_asset_root / "vector-renders",
        timeout=timeout,
        opener=opener,
    )
    vector_download_warnings = [
        warning.replace(
            "image_download_failed:",
            "vector_render_download_failed:",
            1,
        )
        for warning in vector_download_warnings
    ]
    effect_render_ids = _figma_exact_effect_node_ids(payload)
    effect_render_urls, effect_request_warnings = _figma_effect_render_urls(
        key,
        effect_render_ids,
        token=access_token,
        timeout=timeout,
        opener=opener,
    )
    local_effect_renders, effect_download_warnings = _download_figma_images(
        effect_render_urls,
        root=resolved_asset_root / "effect-renders",
        timeout=timeout,
        opener=opener,
    )
    effect_download_warnings = [
        warning.replace(
            "image_download_failed:",
            "effect_render_download_failed:",
            1,
        )
        for warning in effect_download_warnings
    ]
    document, report = import_figma_payload(
        payload,
        source=source,
        image_urls=image_urls,
        image_paths=local_images,
        vector_render_paths=local_vector_renders,
        effect_render_paths=local_effect_renders,
        variables_payload=variable_payload,
    )
    report["asset_root"] = str(resolved_asset_root)
    report["downloaded_image_count"] = len(local_images)
    report["downloaded_vector_render_count"] = len(local_vector_renders)
    report["requested_effect_render_count"] = len(effect_render_ids)
    report["downloaded_effect_render_count"] = len(local_effect_renders)
    report["warnings"].extend(
        [
            *image_warnings,
            *vector_request_warnings,
            *vector_download_warnings,
            *effect_request_warnings,
            *effect_download_warnings,
        ]
    )
    return document, report


def figma_image_paths_from_dir(image_dir: str | Path) -> dict[str, str]:
    """Map ``imageRef`` values onto files in a bundled archive image folder.

    Archive exports name each blob after the ``imageRef`` it satisfies, so the
    file stem is the lookup key.
    """

    root = Path(image_dir).expanduser()
    if not root.is_dir():
        raise PainterUIFigmaError(f"Figma image directory not found: {root}")
    paths: dict[str, str] = {}
    for entry in sorted(root.iterdir()):
        if entry.is_file() and entry.stem:
            paths.setdefault(entry.stem, str(entry))
    return paths


def import_figma_json(
    path: str | Path,
    *,
    image_dir: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = Path(path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise PainterUIFigmaError("Figma JSON snapshot must contain an object")
    image_paths = figma_image_paths_from_dir(image_dir) if image_dir else None
    return import_figma_payload(
        payload,
        source=str(source),
        image_paths=image_paths,
    )


def _write_fig_images(
    images: Mapping[str, bytes],
    *,
    root: Path,
) -> tuple[dict[str, str], list[str]]:
    """Persist ``.fig`` image blobs so imported fills can reference real files."""

    if not images:
        return {}, []
    warnings: list[str] = []
    written: dict[str, str] = {}
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {}, [f"fig_image_root_unavailable:{exc}"]
    for name, blob in images.items():
        if not isinstance(blob, (bytes, bytearray)) or not blob:
            continue
        # Archive entries are named by the same hash the paints reference, so
        # the entry name is already the imageRef the importer looks up.
        suffix = _fig_image_suffix(bytes(blob))
        target = root / f"{name}{suffix}"
        try:
            target.write_bytes(bytes(blob))
        except OSError as exc:
            warnings.append(f"fig_image_write_failed:{name}:{exc}")
            continue
        written[name] = str(target)
    return written, warnings


def _fig_image_suffix(blob: bytes) -> str:
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if blob[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if blob[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return ".webp"
    return ".bin"


def import_fig_file(
    path: str | Path,
    *,
    asset_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Import a local Figma ``.fig`` archive without contacting the REST API.

    The ``.fig`` container is reverse engineered rather than a published Figma
    contract, so coverage is narrower than the REST path and the resulting
    report always carries ``fig_native_import`` plus any translation warnings.
    Callers must not present this as native Figma compatibility.
    """

    from app.painter_ui_figma_fig import PainterUIFigError, read_fig_archive
    from app.painter_ui_figma_fig_rest import fig_archive_to_rest_payload

    source = Path(path).expanduser()
    try:
        archive = read_fig_archive(source)
    except PainterUIFigError as exc:
        raise PainterUIFigmaError(f"Could not read {source.name}: {exc}") from exc

    try:
        payload, fig_report = fig_archive_to_rest_payload(archive)
    except ValueError as exc:
        raise PainterUIFigmaError(f"Could not translate {source.name}: {exc}") from exc

    resolved_asset_root = (
        Path(asset_root).expanduser().resolve()
        if asset_root
        else default_figma_asset_root(f"fig:{source.name}")
    )
    image_paths, image_warnings = _write_fig_images(
        archive.images,
        root=resolved_asset_root / "fig-images",
    )

    document, report = import_figma_payload(
        payload,
        source=str(source),
        image_paths=image_paths,
        variables_payload=None,
    )
    report["fig_native_import"] = True
    report["fig_version"] = fig_report["fig_version"]
    report["fig_node_count"] = fig_report["node_count"]
    report["fig_unmapped_node_types"] = fig_report["unmapped_node_types"]
    report["asset_root"] = str(resolved_asset_root)
    report["downloaded_image_count"] = len(image_paths)
    report["warnings"].extend(
        [
            *(f"fig_translation:{warning}" for warning in fig_report["warnings"]),
            *image_warnings,
        ]
    )
    return document, report


def merge_figma_document(
    current: Mapping[str, Any],
    imported: Mapping[str, Any],
    *,
    mode: str = "replace",
) -> dict[str, Any]:
    normalized = normalize_ui_document(imported)
    if str(mode).strip().casefold() == "replace":
        return normalized
    if str(mode).strip().casefold() != "append":
        raise PainterUIFigmaError("Import mode must be replace or append")
    result = normalize_ui_document(current)
    used = {
        str(row.get("id") or "")
        for key in (
            "artboards",
            "objects",
            "sections",
            "components",
            "tokens",
            "interactions",
        )
        for row in result[key]
    }
    mapping: dict[str, str] = {}
    for key in (
        "artboards",
        "objects",
        "sections",
        "components",
        "tokens",
        "interactions",
    ):
        for row in normalized[key]:
            source_id = str(row["id"])
            candidate = source_id
            serial = 2
            while candidate in used:
                candidate = f"{source_id}-{serial}"
                serial += 1
            mapping[source_id] = candidate
            used.add(candidate)

    def remap_row(key: str, row: Mapping[str, Any]) -> dict[str, Any]:
        value = copy.deepcopy(dict(row))
        value["id"] = mapping[str(row["id"])]
        reference_fields = {
            "objects": (
                "artboard_id",
                "parent_id",
                "component_id",
                "component_source_object_id",
                "component_scope_id",
                "component_scope_source_object_id",
            ),
            "components": ("root_object_id", "base_component_id"),
            "sections": (),
            "tokens": ("alias_token_id",),
            "interactions": (
                "source_object_id",
                "target_artboard_id",
                "target_object_id",
                "component_id",
            ),
        }.get(key, ())
        for field in reference_fields:
            reference = str(value.get(field) or "")
            if reference in mapping:
                value[field] = mapping[reference]
        if key == "objects":
            value["token_bindings"] = {
                path: mapping.get(str(token_id), str(token_id))
                for path, token_id in value.get("token_bindings", {}).items()
            }
            mask = dict(value.get("mask") or {})
            mask["target_ids"] = [
                mapping.get(str(item), str(item))
                for item in mask.get("target_ids", [])
            ]
            value["mask"] = mask
            content = dict(value.get("content") or {})
            boolean = dict(content.get("boolean") or {})
            boolean["operand_ids"] = [
                mapping.get(str(item), str(item))
                for item in boolean.get("operand_ids", [])
            ]
            if boolean:
                content["boolean"] = boolean
            value["content"] = content
        if key == "sections":
            value["object_ids"] = [
                mapping.get(str(item), str(item))
                for item in value.get("object_ids", [])
            ]
        return value

    for key in (
        "artboards",
        "objects",
        "sections",
        "components",
        "tokens",
        "interactions",
    ):
        result[key].extend(remap_row(key, row) for row in normalized[key])
    result["active_artboard_id"] = mapping[normalized["active_artboard_id"]]
    result["linked_targets"]["figma"] = copy.deepcopy(
        normalized.get("linked_targets", {}).get("figma", {})
    )
    result["revision"] = int(result.get("revision", 0)) + 1
    return normalize_ui_document(result)


def inspect_figma_compatibility(
    document: Mapping[str, Any],
    *,
    normalize: bool = True,
) -> dict[str, Any]:
    # Read-only inspection: callers holding a canonical document skip the
    # defensive copy, which dominates click latency on large files.
    normalized = normalize_ui_document(document) if normalize else document
    rows: list[dict[str, str]] = []
    render_blockers: list[dict[str, Any]] = []
    component_ids = {str(row["id"]) for row in normalized["components"]}
    object_ids = {str(row["id"]) for row in normalized["objects"]}
    artboard_ids = {str(row["id"]) for row in normalized["artboards"]}
    for row in normalized["objects"]:
        kind = str(row["kind"])
        content = dict(row.get("content") or {})
        vector_recovery = content.get("figma_vector_geometry_recovery")
        vector_recovery = (
            vector_recovery
            if isinstance(vector_recovery, Mapping)
            else {}
        )
        status = "native"
        reason = "Maps to an editable Figma node"
        if kind == "motion_actor":
            status = "baked"
            reason = "Motion actors require a poster-frame image in Figma"
        elif (
            kind == "path"
            and vector_recovery.get("source") == "figma_render_api"
        ):
            status = "converted"
            reason = (
                "Exact Figma SVG render is preserved, but editable vector "
                "path geometry is unavailable"
            )
        elif kind not in {
            "frame",
            "group",
            "rectangle",
            "ellipse",
            "line",
            "path",
            "text",
            "image",
            "button",
            "progress",
        }:
            status = "blocked"
            reason = f"Unsupported Painter UI kind: {kind}"
        rows.append({"id": row["id"], "status": status, "reason": reason})
        auto_layout_recovery = content.get("figma_auto_layout_recovery")
        if isinstance(auto_layout_recovery, Mapping):
            rows.append(
                {
                    "id": f"{row['id']}:transformed-auto-layout",
                    "status": "converted",
                    "reason": (
                        "Transformed Figma Auto Layout is preserved as "
                        "snapshot absolute geometry with recovery metadata"
                    ),
                }
            )
            if auto_layout_recovery.get("outer_affine_ignored"):
                rows.append(
                    {
                        "id": f"{row['id']}:outer-affine-transform",
                        "status": "blocked",
                        "reason": str(
                            auto_layout_recovery.get("outer_affine_reason")
                            or "outer_affine_snapshot_requires_transform_support"
                        ),
                    }
                )
        affine_recovery = content.get("figma_affine_snapshot_geometry")
        if (
            isinstance(affine_recovery, Mapping)
            and str(affine_recovery.get("status") or "").startswith("blocked_")
        ):
            rows.append(
                {
                    "id": f"{row['id']}:affine-transform",
                    "status": "blocked",
                    "reason": str(
                        affine_recovery.get("reason")
                        or "figma_affine_snapshot_requires_transform_support"
                    ),
                }
            )
        mask = dict(row.get("mask") or {})
        if mask.get("enabled"):
            rows.append(
                {
                    "id": f"{row['id']}:mask",
                    "status": "native",
                    "reason": "Maps to an editable Figma mask node",
                }
            )
        if (content.get("boolean") or {}).get("enabled"):
            rows.append(
                {
                    "id": f"{row['id']}:boolean",
                    "status": "native",
                    "reason": "Maps to an editable Figma Boolean operation",
                }
            )
        if content.get("text_ranges"):
            rows.append(
                {
                    "id": f"{row['id']}:text-ranges",
                    "status": "native",
                    "reason": "Maps to Figma character-range text styles",
                }
            )
        for paint in content.get("figma_unsupported_paints", []):
            rows.append(
                {
                    "id": f"{row['id']}:figma-paint:{paint.get('type')}",
                    "status": "blocked",
                    "reason": (
                        f"Figma {paint.get('type')} on {paint.get('target')} "
                        "requires a conic/diamond UI material or deterministic bake"
                    ),
                }
            )
        for index, image_reason in enumerate(
            content.get("figma_image_render_blockers", [])
        ):
            rows.append(
                {
                    "id": f"{row['id']}:figma-image:{index}",
                    "status": "blocked",
                    "reason": str(image_reason),
                }
            )
        image_rotation = _number(content.get("image_rotation"), 0.0)
        if abs(image_rotation / 90.0 - round(image_rotation / 90.0)) > 0.0001:
            rows.append(
                {
                    "id": f"{row['id']}:figma-image-rotation",
                    "status": "blocked",
                    "reason": (
                        "Figma image rotation must use 90-degree increments"
                    ),
                }
            )
        for binding in content.get("figma_variable_bindings", []):
            if not isinstance(binding, Mapping):
                continue
            binding_status = str(binding.get("status") or "")
            if binding_status == "native":
                continue
            rows.append(
                {
                    "id": (
                        f"{row['id']}:figma-variable:"
                        f"{binding.get('field')}:"
                        f"{binding.get('alias_index', 0)}"
                    ),
                    "status": "blocked",
                    "reason": (
                        "figma_variable_binding_requires_token_relink: "
                        f"{binding.get('reason') or 'unresolved_binding'} "
                        f"({binding.get('id') or 'missing id'})"
                    ),
                }
            )
        for target_path, property_name in row.get(
            "component_property_bindings",
            {},
        ).items():
            rows.append(
                {
                    "id": (
                        f"{row['id']}:figma-component-property-binding:"
                        f"{target_path}"
                    ),
                    "status": "native",
                    "reason": (
                        "Maps to an editable Figma component property "
                        f"reference: {property_name}"
                    ),
                }
            )
        recovered_property_bindings = content.get(
            "figma_component_property_bindings"
        )
        recovered_property_bindings = (
            recovered_property_bindings
            if isinstance(recovered_property_bindings, Mapping)
            else {}
        )
        raw_property_references = content.get(
            "figma_component_property_references"
        )
        raw_property_references = (
            raw_property_references
            if isinstance(raw_property_references, Mapping)
            else {}
        )
        for target_path, property_name in recovered_property_bindings.items():
            reason = "figma_component_property_binding_requires_component_relink"
            if str(target_path).startswith("figma_field:"):
                raw_field = str(target_path).split(":", 1)[1]
                reason = (
                    "figma_component_property_reference_field_unsupported"
                    if raw_field
                    not in {"characters", "visible", "mainComponent"}
                    else "figma_component_property_reference_value_missing"
                )
                property_name = raw_property_references.get(
                    raw_field,
                    property_name,
                )
            rows.append(
                {
                    "id": (
                        f"{row['id']}:figma-component-property-recovery:"
                        f"{target_path}"
                    ),
                    "status": "blocked",
                    "reason": f"{reason}: {property_name}",
                }
            )
        style = dict(row.get("style") or {})
        effects = style.get("effects")
        if isinstance(effects, list):
            for effect_index, effect in enumerate(effects):
                if not isinstance(effect, Mapping):
                    continue
                if not bool(effect.get("visible", True)):
                    continue
                exact_render = content.get("figma_exact_render")
                block_reasons = ui_effect_render_block_reasons(
                    effect,
                    exact_render=exact_render,
                )
                if not block_reasons:
                    continue
                render_blockers.append(
                    {
                        "id": f"{row['id']}:effect:{effect_index}",
                        "object_id": row["id"],
                        "effect_index": effect_index,
                        "effect_type": str(effect.get("type") or ""),
                        "status": "blocked",
                        # Keep the established primary reason stable for
                        # report consumers. Exact-render safety details are
                        # additive and do not turn a PNG into an implicit bake.
                        "reason": block_reasons[0],
                        "diagnostics": block_reasons[1:],
                        "exact_render_available": isinstance(
                            exact_render,
                            Mapping,
                        ),
                        "fallback": "ui_material_or_deterministic_bake",
                    }
                )
        if style.get("font_axes"):
            rows.append(
                {
                    "id": f"{row['id']}:font-axes",
                    "status": "converted",
                    "reason": (
                        "Variable-font axes are preserved as Tiger Studio "
                        "shared plugin data"
                    ),
                }
            )
        remote = dict(content.get("remote_component") or {})
        if remote.get("status") == "missing":
            rows.append(
                {
                    "id": f"{row['id']}:remote-component",
                    "status": "converted",
                    "reason": (
                        "Missing remote component is exported as an editable "
                        "frame with recovery metadata"
                    ),
                }
            )
    figma_link = (
        normalized.get("linked_targets", {}).get("figma", {})
    )
    figma_link = figma_link if isinstance(figma_link, Mapping) else {}
    for binding in figma_link.get("artboard_variable_bindings", []):
        if not isinstance(binding, Mapping):
            continue
        rows.append(
            {
                "id": (
                    f"{binding.get('artboard_id')}:figma-variable:"
                    f"{binding.get('field')}:"
                    f"{binding.get('alias_index', 0)}"
                ),
                "status": "blocked",
                "reason": (
                    "figma_variable_binding_requires_token_relink: "
                    f"{binding.get('reason') or 'artboard_binding'} "
                    f"({binding.get('id') or 'missing id'})"
                ),
            }
        )
    for recovery_index, recovery in enumerate(
        figma_link.get("reaction_recovery", [])
    ):
        if not isinstance(recovery, Mapping):
            continue
        recovery_reasons = [
            str(reason)
            for reason in recovery.get("reasons", [])
            if str(reason or "")
        ]
        rows.append(
            {
                "id": str(
                    recovery.get("id")
                    or f"figma-reaction-recovery-{recovery_index}"
                ),
                "status": "blocked",
                "reason": "; ".join(recovery_reasons)
                or "figma_reaction_recovery_requires_manual_resolution",
            }
        )
    figma_plugin_triggers = {
        "click",
        "double_click",
        "hover",
        "press",
        "focus",
        "keyboard",
        "delay",
        "mouse_enter",
        "mouse_leave",
        "drag",
        "gamepad",
    }
    figma_plugin_actions = {
        "navigate",
        "back",
        "open_overlay",
        "close_overlay",
        "swap_overlay",
        "scroll_to",
        "change_variant",
    }
    for interaction in normalized["interactions"]:
        parameters = interaction.get("parameters")
        parameters = parameters if isinstance(parameters, Mapping) else {}
        figma_reaction = parameters.get("figma_reaction")
        figma_reaction = (
            figma_reaction if isinstance(figma_reaction, Mapping) else {}
        )
        status = "native"
        reason = (
            "Maps to an editable Figma prototype reaction"
            if figma_reaction
            else "Maps to a supported Figma plugin prototype reaction"
        )
        if str(interaction.get("trigger") or "") not in figma_plugin_triggers:
            status = "blocked"
            reason = (
                "figma_plugin_trigger_unsupported:"
                f"{interaction.get('trigger') or 'missing'}"
            )
        elif str(interaction.get("action") or "") not in figma_plugin_actions:
            status = "blocked"
            reason = (
                "figma_plugin_action_unsupported:"
                f"{interaction.get('action') or 'missing'}"
            )
        elif str(interaction.get("source_object_id") or "") not in object_ids:
            status = "blocked"
            reason = "figma_plugin_reaction_source_missing"
        else:
            action = str(interaction.get("action") or "")
            target_object_id = str(
                interaction.get("target_object_id") or ""
            )
            target_artboard_id = str(
                interaction.get("target_artboard_id") or ""
            )
            component_id = str(interaction.get("component_id") or "")
            if action in {"navigate", "open_overlay", "swap_overlay"} and not (
                target_object_id in object_ids
                or target_artboard_id in artboard_ids
            ):
                status = "blocked"
                reason = "figma_plugin_reaction_destination_missing"
            elif action == "scroll_to" and target_object_id not in object_ids:
                status = "blocked"
                reason = "figma_plugin_scroll_to_object_destination_missing"
            elif action == "change_variant" and component_id not in component_ids:
                status = "blocked"
                reason = "figma_plugin_change_to_component_destination_missing"
        rows.append(
            {
                "id": f"{interaction['id']}:figma-reaction",
                "status": status,
                "reason": reason,
            }
        )
    supported_property_types = {"enum", "boolean", "text", "instance_swap", "slot"}
    for component in normalized["components"]:
        for property_name, definition in component[
            "property_definitions"
        ].items():
            property_type = str(definition.get("type") or "")
            status = "native"
            reason = "Maps to a Figma component property"
            if property_type not in supported_property_types:
                status = "blocked"
                reason = (
                    "Unsupported Figma component property type: "
                    f"{property_type or 'missing'}"
                )
            elif (
                property_type == "instance_swap"
                and str(definition.get("default") or "") not in component_ids
            ):
                status = "blocked"
                reason = "Instance-swap default does not reference a local component"
            elif property_type == "slot":
                source = next(
                    (
                        row
                        for row in normalized["objects"]
                        if row["id"] == str(definition.get("default") or "")
                    ),
                    None,
                )
                if source is None or source["component_slot_property"] != property_name:
                    status = "blocked"
                    reason = "Slot property does not reference its component Slot frame"
            rows.append(
                {
                    "id": f"{component['id']}:{property_name}",
                    "status": status,
                    "reason": reason,
                }
            )
    counts = {
        status: sum(1 for row in rows if row["status"] == status)
        for status in ("native", "converted", "baked", "blocked")
    }
    review_comments = (
        normalized.get("linked_targets", {})
        .get("review", {})
        .get("comments", [])
    )
    for section in normalized.get("sections", []):
        rows.append(
            {
                "id": section["id"],
                "status": "native",
                "reason": "Maps to a Figma Section node",
            }
        )
    for comment in review_comments:
        rows.append(
            {
                "id": str(comment.get("id") or "comment"),
                "status": "converted",
                "reason": (
                    "Figma plugins cannot create file comments; review data "
                    "is preserved in plugin metadata"
                ),
            }
        )
    counts = {
        status: sum(1 for row in rows if row["status"] == status)
        for status in ("native", "converted", "baked", "blocked")
    }
    return {
        "schema": FIGMA_EXCHANGE_SCHEMA,
        "ok": counts["blocked"] == 0,
        "counts": counts,
        "objects": rows,
        "artboard_count": len(normalized["artboards"]),
        "component_count": len(normalized["components"]),
        "token_count": len(normalized["tokens"]),
        "interaction_count": len(normalized["interactions"]),
        "section_count": len(normalized.get("sections", [])),
        "comment_count": len(review_comments),
        # These rows do not block a lossless Figma plugin export: Figma can
        # recreate its own native effects.  They do block a claim of exact
        # Painter raster preview and are mirrored by the UMG preflight.
        "render_blocker_count": len(render_blockers),
        "render_blockers": render_blockers,
    }


def _asset_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    assets: dict[str, Any] = {}
    for row in document["objects"]:
        content = row.get("content")
        content = content if isinstance(content, Mapping) else {}
        source = str(
            content.get("path")
            or content.get("source_path")
            or content.get("image_path")
            or ""
        )
        if not source:
            continue
        path = Path(source).expanduser()
        if not path.is_file():
            continue
        mime, _ = mimetypes.guess_type(path.name)
        assets[row["id"]] = {
            "name": path.name,
            "mime": mime or "application/octet-stream",
            "base64": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
    return assets


def _plugin_code(exchange: Mapping[str, Any]) -> str:
    payload = json.dumps(exchange, ensure_ascii=False, separators=(",", ":"))
    return f"""const exchange = {payload};
const doc = exchange.document;
const created = new Map();
const components = new Map();
const componentRecords = new Map(doc.components.map(row => [row.id,row]));
const componentRootByObject = new Map(doc.components.map(row => [row.root_object_id,row]));
const componentPropertyNames = new Map();
const tokenVars = new Map();
const objectById = new Map(doc.objects.map(row => [row.id, row]));
function insideInstance(row) {{
  let parent=objectById.get(row.parent_id);
  while(parent) {{
    if(parent.component_role==='instance') return true;
    parent=objectById.get(parent.parent_id);
  }}
  return false;
}}
function isComponentRoot(row) {{ return componentRootByObject.has(row.id); }}
function isInstanceRoot(row) {{
  if(row.component_role!=='instance') return false;
  const parent=objectById.get(row.parent_id);
  return !parent || parent.component_role!=='instance';
}}
function containingInstanceRoot(row) {{
  let current=row, result=null;
  while(current) {{
    if(isInstanceRoot(current)) result=current;
    current=objectById.get(current.parent_id);
  }}
  return result;
}}
function componentFamilyId(componentId) {{
  const row=componentRecords.get(componentId);
  return row ? (row.base_component_id || row.id) : componentId;
}}
function containingDefinitionComponentId(row) {{
  let current=row;
  while(current) {{
    if(current.component_role==='definition') return current.component_id;
    current=objectById.get(current.parent_id);
  }}
  return '';
}}
function cleanPropertyName(value) {{
  return String(value||'').replace(/#\\d+:\\d+$/,'').trim();
}}
function defaultVariantKey(record) {{
  return Object.entries(record.property_definitions||{{}})
    .filter(([,definition])=>definition.type==='enum')
    .map(([name,definition])=>`${{name}}=${{String(definition.default??'')}}`)
    .join(', ');
}}

function color(value) {{
  const text = String(value || '#00000000').replace('#', '');
  const full = text.length === 3 ? text.split('').map(x => x + x).join('') + 'FF'
    : text.length === 6 ? text + 'FF' : text.padEnd(8, 'F').slice(0, 8);
  return {{ r: parseInt(full.slice(0,2),16)/255, g: parseInt(full.slice(2,4),16)/255,
    b: parseInt(full.slice(4,6),16)/255, a: parseInt(full.slice(6,8),16)/255 }};
}}
function paint(value) {{ const c=color(value); return {{type:'SOLID',color:{{r:c.r,g:c.g,b:c.b}},opacity:c.a}}; }}
function stackPaint(row) {{
  if(String(row?.type||'solid')==='solid') {{
    const p=paint(row.color||'#FFFFFFFF');
    p.visible=row.visible!==false; p.opacity=Math.max(0,Math.min(1,Number(row.opacity??p.opacity)));
    return p;
  }}
  const g=row.gradient||{{}}, point=(value,fallback)=>({{x:Number(value?.x??fallback.x),y:Number(value?.y??fallback.y)}});
  return {{
    type:String(row.type||'linear')==='radial'?'GRADIENT_RADIAL':'GRADIENT_LINEAR',
    visible:row.visible!==false,
    opacity:Math.max(0,Math.min(1,Number(row.opacity??1))),
    gradientHandlePositions:[point(g.start,{{x:0,y:.5}}),point(g.end,{{x:1,y:.5}}),point(g.width,{{x:0,y:1}})],
    gradientStops:(g.stops||[]).map(stop=>{{const c=color(stop.color);return {{position:Number(stop.position)||0,color:c}};}})
  }};
}}
function fillPaint(style) {{
  const g=style.fill_gradient;
  if(!g || !Array.isArray(g.stops) || !g.stops.length) return paint(style.fill||'#00000000');
  const point=(value,fallback)=>({{x:Number(value?.x ?? fallback.x),y:Number(value?.y ?? fallback.y)}});
  const start=point(g.start,{{x:0,y:0.5}}), end=point(g.end,{{x:1,y:0.5}});
  const width=point(g.width,{{x:0,y:1}});
  return {{
    type:String(g.type||'linear').toLowerCase()==='radial'?'GRADIENT_RADIAL':'GRADIENT_LINEAR',
    gradientHandlePositions:[start,end,width],
    gradientStops:g.stops.map(stop=>{{
      const c=color(stop.color);
      return {{position:Math.max(0,Math.min(1,Number(stop.position)||0)),color:{{r:c.r,g:c.g,b:c.b,a:c.a}}}};
    }})
  }};
}}
  function effectRows(style) {{
    let rows=Array.isArray(style.effects)?style.effects:[];
    if(!rows.length && style.shadow) rows=[{{type:'drop_shadow',...style.shadow}}];
    return rows
      .filter(row=>['drop_shadow','inner_shadow','layer_blur','background_blur','noise','texture'].includes(String(row.type||'').toLowerCase()))
      .map(row=>{{
        const type=String(row.type||'').toLowerCase();
        if(type==='layer_blur'||type==='background_blur') {{
          const effect={{
            type:type==='background_blur'?'BACKGROUND_BLUR':'LAYER_BLUR',
            radius:Math.max(0,Number(row.radius)||0),
            visible:row.visible!==false
          }};
          const blurType=String(row.blur_type||'').toUpperCase();
          if(blurType==='NORMAL'||blurType==='PROGRESSIVE') effect.blurType=blurType;
          if(blurType==='PROGRESSIVE') {{
            effect.startRadius=Math.max(0,Number(row.start_radius)||0);
            effect.startOffset={{x:Number(row.start_offset?.x)||0,y:Number(row.start_offset?.y)||0}};
            effect.endOffset={{x:Number(row.end_offset?.x)||0,y:Number(row.end_offset?.y)||0}};
          }}
          return effect;
        }}
        if(type==='noise') {{
          const c=color(row.color||'#000000FF');
          const effect={{
            type:'NOISE', color:{{r:c.r,g:c.g,b:c.b,a:c.a}},
            blendMode:String(row.blend_mode||'NORMAL').toUpperCase(),
            noiseSize:Math.max(0,Number(row.noise_size)||0),
            noiseType:String(row.noise_type||'MONOTONE').toUpperCase(),
            density:Math.max(0,Number(row.density)||0), visible:row.visible!==false
          }};
          if(row.noise_size_vector) effect.noiseSizeVector={{x:Number(row.noise_size_vector.x)||0,y:Number(row.noise_size_vector.y)||0}};
          if(row.secondary_color) {{const s=color(row.secondary_color);effect.secondaryColor={{r:s.r,g:s.g,b:s.b,a:s.a}};}}
          if(row.opacity!==undefined) effect.opacity=Math.max(0,Math.min(1,Number(row.opacity)||0));
          return effect;
        }}
        if(type==='texture') {{
          const effect={{
            type:'TEXTURE', radius:Math.max(0,Number(row.radius)||0),
            noiseSize:Math.max(0,Number(row.noise_size)||0),
            clipToShape:!!row.clip_to_shape, visible:row.visible!==false
          }};
          if(row.noise_size_vector) effect.noiseSizeVector={{x:Number(row.noise_size_vector.x)||0,y:Number(row.noise_size_vector.y)||0}};
          return effect;
        }}
        const c=color(row.color||'#00000040');
        const effect={{
          type:type==='inner_shadow'?'INNER_SHADOW':'DROP_SHADOW',
          color:{{r:c.r,g:c.g,b:c.b,a:c.a}},
          offset:{{x:Number(row.x)||0,y:Number(row.y)||0}},
          radius:Math.max(0,Number(row.blur)||0),
          spread:Number(row.spread)||0,
          blendMode:String(row.blend_mode||'NORMAL').toUpperCase(),
          visible:row.visible!==false
        }};
        if(type==='drop_shadow'&&row.show_shadow_behind_node!==undefined)
          effect.showShadowBehindNode=!!row.show_shadow_behind_node;
        return effect;
      }});
}}
function decode64(text) {{
  const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let buffer=0,bits=0,out=[];
  for (const ch of text.replace(/=+$/,'')) {{
    const value=alphabet.indexOf(ch); if(value<0) continue;
    buffer=(buffer<<6)|value; bits+=6;
    if(bits>=8) {{ bits-=8; out.push((buffer>>bits)&255); }}
  }}
  return new Uint8Array(out);
}}
function validImageTransform(value) {{
  return Array.isArray(value) && value.length===2
    && value.every(axis=>Array.isArray(axis) && axis.length>=3
      && axis.slice(0,3).every(item=>Number.isFinite(Number(item))))
    && Math.abs(Number(value[0][0])*Number(value[1][1])
      - Number(value[1][0])*Number(value[0][1]))>1e-9;
}}
function imageCropTransform(content) {{
  const crop=content.image_crop||content.crop||{{}};
  if(!(crop.enabled??crop.Enabled)) return null;
  let x=Number(crop.x??crop.X??0), y=Number(crop.y??crop.Y??0);
  let width=Number(crop.width??crop.Width??0), height=Number(crop.height??crop.Height??0);
  const units=String(crop.units??crop.Units??'normalized').toLowerCase();
  if(['pixel','pixels','px'].includes(units)) {{
    const sourceWidth=Number(content.original_width||content.source_width||0);
    const sourceHeight=Number(content.original_height||content.source_height||0);
    if(sourceWidth<=0||sourceHeight<=0) return null;
    x/=sourceWidth; width/=sourceWidth; y/=sourceHeight; height/=sourceHeight;
  }}
  if(![x,y,width,height].every(Number.isFinite)||width<=0||height<=0) return null;
  return [[width,0,x],[0,height,y]];
}}
function imagePaint(row,imageHash) {{
  const content=row.content||{{}};
  let mode=String(content.image_mode||content.image_fit||'FILL').toUpperCase();
  if(mode==='STRETCH') mode='CROP';
  if(!['FILL','FIT','CROP','TILE'].includes(mode)) mode='FILL';
  const result={{type:'IMAGE',scaleMode:mode,imageHash}};
  if(mode==='CROP') {{
    const transform=validImageTransform(content.figma_image_transform)
      ? content.figma_image_transform : imageCropTransform(content);
    result.imageTransform=transform||[[1,0,0],[0,1,0]];
  }}
  const rotation=Number(content.image_rotation??content.rotation??0);
  if(mode!=='CROP' && Number.isFinite(rotation)
    && Math.abs(rotation/90-Math.round(rotation/90))<=1e-4)
    result.rotation=rotation;
  if(mode==='TILE') result.scalingFactor=Math.max(.0001,Number(content.tile_scale)||1);
  result.opacity=Math.max(0,Math.min(1,Number(content.image_opacity??1)));
  result.blendMode=String(content.image_blend_mode||'NORMAL').toUpperCase();
  const adjustments=content.image_adjustments||content.adjustments||{{}};
  result.filters={{}};
  for(const key of ['exposure','contrast','saturation','temperature','tint','highlights','shadows']) {{
    const value=Number(adjustments[key]||0);
    if(Number.isFinite(value)&&Math.abs(value)>1e-9)
      result.filters[key]=Math.max(-1,Math.min(1,value/100));
  }}
  return result;
}}
function applyFrame(node,row) {{
  const parentRow=objectById.get(row.parent_id);
  node.name=row.name || row.id;
  node.x=(Number(row.x)||0)-(parentRow?(Number(parentRow.x)||0):0);
  node.y=(Number(row.y)||0)-(parentRow?(Number(parentRow.y)||0):0);
  node.resize(Math.max(1,Number(row.width)||1),Math.max(1,Number(row.height)||1));
  node.rotation=Number(row.rotation)||0; node.opacity=Math.max(0,Math.min(1,Number(row.opacity ?? 1)));
  node.visible=row.visible !== false; node.locked=!!row.locked;
  if('clipsContent' in node) node.clipsContent=!!row.clip_content;
  node.setSharedPluginData('tigerstudio','stable_id',row.id);
  if(row.component_id) node.setSharedPluginData('tigerstudio','component_id',row.component_id);
  if(row.component_source_object_id) node.setSharedPluginData('tigerstudio','component_source_object_id',row.component_source_object_id);
  const s=row.style||{{}};
  node.setSharedPluginData('tigerstudio','font_axes',JSON.stringify(s.font_axes||{{}}));
  if('fills' in node) node.fills=Array.isArray(s.fills)&&s.fills.length?s.fills.map(stackPaint):[fillPaint(s)];
  if('strokes' in node) node.strokes=Array.isArray(s.strokes)&&s.strokes.length?s.strokes.map(stackPaint):(s.stroke&&!String(s.stroke).endsWith('00')?[paint(s.stroke)]:[]);
  if('effects' in node) node.effects=effectRows(s);
  if('strokeWeight' in node) node.strokeWeight=Math.max(0,Number(s.stroke_width)||0);
  if('strokeAlign' in node) node.strokeAlign=String(s.stroke_align||'CENTER').toUpperCase();
  const individualStrokeWeights=s.individual_stroke_weights||{{}};
  if(Object.keys(individualStrokeWeights).length) {{
    const sideProperties={{top:'strokeTopWeight',right:'strokeRightWeight',bottom:'strokeBottomWeight',left:'strokeLeftWeight'}};
    for(const [side,property] of Object.entries(sideProperties)) {{
      if(property in node) node[property]=Math.max(0,Number(individualStrokeWeights[side])||0);
    }}
  }}
  node.setSharedPluginData('tigerstudio','individual_stroke_weights',JSON.stringify(individualStrokeWeights));
  if('dashPattern' in node && Array.isArray(s.stroke_dash)) node.dashPattern=s.stroke_dash.map(value=>Math.max(0,Number(value)||0));
  if('strokeCap' in node && s.stroke_cap) node.strokeCap=String(s.stroke_cap).toUpperCase();
  if('strokeJoin' in node && s.stroke_join) node.strokeJoin=String(s.stroke_join).toUpperCase();
  if('strokeMiterLimit' in node && s.stroke_miter_limit!==undefined) node.strokeMiterLimit=Math.max(0,Number(s.stroke_miter_limit)||0);
  if('blendMode' in node) node.blendMode=String(s.blend_mode||'NORMAL').toUpperCase();
  if('cornerRadius' in node && typeof node.cornerRadius==='number') node.cornerRadius=Math.max(0,Number(s.radius)||0);
  if('cornerSmoothing' in node) node.cornerSmoothing=Math.max(0,Math.min(1,Number(s.corner_smoothing)||0));
  const radii=s.corner_radii||{{}};
  if('topLeftRadius' in node) {{
    node.topLeftRadius=Math.max(0,Number(radii.top_left??s.radius)||0);
    node.topRightRadius=Math.max(0,Number(radii.top_right??s.radius)||0);
    node.bottomRightRadius=Math.max(0,Number(radii.bottom_right??s.radius)||0);
    node.bottomLeftRadius=Math.max(0,Number(radii.bottom_left??s.radius)||0);
  }}
  if('isMask' in node) node.isMask=!!row.mask?.enabled;
  node.setSharedPluginData('tigerstudio','mask',JSON.stringify(row.mask||{{}}));
  node.setSharedPluginData('tigerstudio','remote_component',JSON.stringify((row.content||{{}}).remote_component||{{}}));
  if(row.layout && 'layoutMode' in node) {{
    node.layoutMode=String(row.layout.mode||'NONE').toUpperCase();
    if(node.layoutMode!=='NONE') {{
      const p=row.layout.padding||{{}}; node.paddingLeft=Number(p.left)||0; node.paddingTop=Number(p.top)||0;
      node.paddingRight=Number(p.right)||0; node.paddingBottom=Number(p.bottom)||0;
      node.itemSpacing=Number(row.layout.gap)||0;
      node.primaryAxisAlignItems={{start:'MIN',center:'CENTER',end:'MAX',space_between:'SPACE_BETWEEN'}}[row.layout.main_alignment]||'MIN';
      node.counterAxisAlignItems={{start:'MIN',center:'CENTER',end:'MAX',stretch:'MIN',baseline:'BASELINE'}}[row.layout.cross_alignment]||'MIN';
    }}
  }}
}}
async function createAuthoredNode(row,parent) {{
  let node;
  if(isComponentRoot(row)) node=figma.createComponent();
  else if(row.component_slot_property && parent.type==='COMPONENT' && parent.createSlot) node=parent.createSlot();
  else if(row.kind==='ellipse') node=figma.createEllipse();
  else if(row.kind==='line') node=figma.createLine();
  else if(row.kind==='text') node=figma.createText();
  else if(['frame','group','button','progress'].includes(row.kind)) node=figma.createFrame();
  else node=figma.createRectangle();
  parent.appendChild(node); applyFrame(node,row); created.set(row.id,node);
  if(isComponentRoot(row)) components.set(row.component_id,node);
  if(row.kind==='text') {{
    const c=row.content||{{}}, s=row.style||{{}}; const font={{family:s.font_family||'Inter',style:'Regular'}};
    try {{ await figma.loadFontAsync(font); node.fontName=font; }} catch (_) {{ await figma.loadFontAsync({{family:'Inter',style:'Regular'}}); }}
    node.characters=String(c.text||''); node.fontSize=Math.max(1,Number(s.font_size)||16);
    node.textAlignHorizontal=String(s.text_align||'LEFT').toUpperCase();
    for(const range of c.text_ranges||[]) {{
      const start=Math.max(0,Math.min(node.characters.length,Number(range.start)||0));
      const end=Math.max(start,Math.min(node.characters.length,Number(range.end)||start));
      const rs=range.style||{{}};
      if(end<=start) continue;
      if(rs.font_size) node.setRangeFontSize(start,end,Math.max(1,Number(rs.font_size)));
      if(rs.color) node.setRangeFills(start,end,[paint(rs.color)]);
      if(rs.underline) node.setRangeTextDecoration(start,end,'UNDERLINE');
    }}
  }}
  const asset=exchange.assets[row.id];
  if(asset && 'fills' in node) {{
    const image=figma.createImage(decode64(asset.base64));
    node.fills=[imagePaint(row,image.hash)];
  }}
  for(const [path,tokenId] of Object.entries(row.token_bindings||{{}})) {{
    const variable=tokenVars.get(tokenId); if(!variable) continue;
    try {{
      if(path==='style.fill' && 'fills' in node && node.fills.length)
        node.fills=[figma.variables.setBoundVariableForPaint(node.fills[0],'color',variable)];
      else if(path==='style.stroke' && 'strokes' in node && node.strokes.length)
        node.strokes=[figma.variables.setBoundVariableForPaint(node.strokes[0],'color',variable)];
      else if(path==='opacity' && node.setBoundVariable) node.setBoundVariable('opacity',variable);
      else if(path==='style.radius' && node.setBoundVariable) node.setBoundVariable('cornerRadius',variable);
    }} catch (_) {{}}
  }}
  return node;
}}
async function main() {{
  const page=figma.currentPage;
  let variableCollection=null;
  if(doc.tokens.length && figma.variables) {{
    variableCollection=figma.variables.createVariableCollection('Tiger Studio Tokens');
    variableCollection.renameMode(variableCollection.modes[0].modeId,'Default');
    for(const row of doc.tokens) {{
      const type=row.kind==='color'?'COLOR':row.kind==='opacity'||row.kind==='spacing'||row.kind==='radius'?'FLOAT':'STRING';
      try {{
        const v=figma.variables.createVariable(row.name,variableCollection,type);
        v.setValueForMode(variableCollection.defaultModeId,type==='COLOR'?color(row.value):row.value);
        tokenVars.set(row.id,v);
      }} catch (_) {{}}
    }}
  }}
  for(const board of doc.artboards) {{
    const node=figma.createFrame(); node.name=board.name; node.x=board.x; node.y=board.y;
    node.resize(board.width,board.height); node.fills=[paint(board.background||'#FFFFFF')];
    node.clipsContent=false; node.setSharedPluginData('tigerstudio','stable_id',board.id);
    page.appendChild(node); created.set(board.id,node);
  }}
  const ordered=[...doc.objects].sort((a,b)=>(a.z_index||0)-(b.z_index||0));
  for(const row of ordered.filter(x => x.component_role !== 'instance' && !insideInstance(x))) {{
    const parent=created.get(row.parent_id)||created.get(row.artboard_id)||page;
    await createAuthoredNode(row,parent);
  }}
  const booleanRows=ordered.filter(row => (row.content||{{}}).boolean?.enabled);
  const booleanById=new Map(booleanRows.map(row=>[row.id,row]));
  const booleanDepth=(row,stack=new Set())=>{{
    if(stack.has(row.id)) throw new Error(`Boolean cycle includes ${{row.id}}`);
    const next=new Set(stack); next.add(row.id);
    let depth=0;
    for(const operandId of ((row.content||{{}}).boolean?.operand_ids||[])) {{
      const operand=booleanById.get(operandId);
      if(operand) depth=Math.max(depth,1+booleanDepth(operand,next));
    }}
    return depth;
  }};
  booleanRows.sort((a,b)=>booleanDepth(a)-booleanDepth(b)||(a.z_index||0)-(b.z_index||0));
  for(const row of booleanRows) {{
    const spec=row.content.boolean, nodes=(spec.operand_ids||[]).map(id=>created.get(id)).filter(Boolean);
    const placeholder=created.get(row.id), parent=placeholder?.parent||created.get(row.parent_id)||created.get(row.artboard_id)||page;
    if(nodes.length<2) throw new Error(`Boolean operands are missing for ${{row.id}}`);
    let result;
    if(spec.operation==='subtract') result=figma.subtract(nodes,parent);
    else if(spec.operation==='intersect') result=figma.intersect(nodes,parent);
    else if(spec.operation==='exclude') result=figma.exclude(nodes,parent);
    else result=figma.union(nodes,parent);
    if(placeholder && placeholder!==result) placeholder.remove();
    applyFrame(result,row);
    result.setSharedPluginData('tigerstudio','stable_id',row.id);
    created.set(row.id,result);
  }}
  for(const section of doc.sections||[]) {{
    if(!figma.createSection) continue;
    const node=figma.createSection();
    node.name=section.name||section.id; node.x=Number(section.x)||0; node.y=Number(section.y)||0;
    node.resizeWithoutConstraints(Math.max(1,Number(section.width)||1),Math.max(1,Number(section.height)||1));
    node.setSharedPluginData('tigerstudio','stable_id',section.id);
    node.setSharedPluginData('tigerstudio','object_ids',JSON.stringify(section.object_ids||[]));
    page.appendChild(node); created.set(section.id,node);
  }}
  page.setSharedPluginData('tigerstudio','review',JSON.stringify(doc.linked_targets?.review||{{}}));
  for(const family of doc.components.filter(row => !row.base_component_id)) {{
    const memberIds=[family.id,...(family.variant_ids||[])];
    const memberNodes=memberIds.map(id=>components.get(id)).filter(node=>node && node.type==='COMPONENT');
    if(!memberNodes.length) continue;
    for(const componentId of memberIds) {{
      const record=componentRecords.get(componentId), node=components.get(componentId);
      if(!record || !node) continue;
      const variantKey=String((record.metadata||{{}}).variant_key||defaultVariantKey(record)).trim();
      if(variantKey) node.name=variantKey;
    }}
    let propertyOwner=memberNodes[0];
    if(memberNodes.length>1) {{
      const parent=memberNodes[0].parent;
      if(parent && 'appendChild' in parent) {{
        try {{
          propertyOwner=figma.combineAsVariants(memberNodes,parent);
          propertyOwner.name=family.name||'Component Set';
          propertyOwner.setSharedPluginData('tigerstudio','component_family_id',family.id);
        }} catch (error) {{
          throw new Error(`Variant combine failed for ${{family.id}}: ${{error.message}}`);
        }}
      }}
    }}
    const names=new Map();
    for(const propertyName of Object.keys(propertyOwner.componentPropertyDefinitions||{{}}))
      names.set(cleanPropertyName(propertyName),propertyName);
    for(const [propertyName,definition] of Object.entries(family.property_definitions||{{}})) {{
      if(names.has(propertyName)) {{
        if(definition.type==='slot') {{
          const actual=names.get(propertyName);
          const preferredValues=(definition.preferred_values||[]).map(value=>components.get(String(value||''))).filter(Boolean).map(node=>({{type:'COMPONENT',key:node.key}}));
          const settings=definition.slot_settings||{{}};
          try {{ propertyOwner.editComponentProperty(actual,{{description:String(definition.description||''),preferredValues,slotSettings:{{stretchChildOnInsert:!!settings.stretch_child_on_insert,displayEmptyByDefault:!!settings.display_empty_by_default,minChildren:settings.min_children??null,maxChildren:settings.max_children??null,allowPreferredValuesOnly:!!settings.allow_preferred_values_only}}}}); }}
          catch (error) {{ throw new Error(`Slot property failed for ${{family.id}}:${{propertyName}}: ${{error.message}}`); }}
        }}
        continue;
      }}
      const type={{enum:'VARIANT',boolean:'BOOLEAN',text:'TEXT',instance_swap:'INSTANCE_SWAP',slot:'SLOT'}}[definition.type];
      if(!type) continue;
      if(type==='SLOT') throw new Error(`Slot node is missing for ${{family.id}}:${{propertyName}}`);
      let defaultValue=definition.default;
      if(type==='BOOLEAN') defaultValue=!!defaultValue;
      else if(type==='INSTANCE_SWAP') {{
        const target=components.get(String(defaultValue||''));
        if(!target) throw new Error(`Instance-swap default is missing for ${{family.id}}:${{propertyName}}`);
        defaultValue=target.id;
      }} else defaultValue=String(defaultValue??'');
      try {{
        const options=type==='INSTANCE_SWAP'?{{preferredValues:(definition.preferred_values||[]).map(value=>components.get(String(value||''))).filter(Boolean).map(node=>({{type:'COMPONENT',key:node.key}}))}}:undefined;
        const actual=propertyOwner.addComponentProperty(propertyName,type,defaultValue,options);
        names.set(propertyName,actual);
      }} catch (error) {{
        throw new Error(`Component property failed for ${{family.id}}:${{propertyName}}: ${{error.message}}`);
      }}
    }}
    componentPropertyNames.set(family.id,names);
  }}
  for(const row of ordered.filter(isInstanceRoot)) {{
    const definition=components.get(row.component_id); let node=definition?definition.createInstance():figma.createFrame();
    const parent=created.get(row.parent_id)||created.get(row.artboard_id)||page;
    parent.appendChild(node); applyFrame(node,row); created.set(row.id,node);
    if(definition && node.type==='INSTANCE') {{
      const familyId=componentFamilyId(row.component_id);
      const names=componentPropertyNames.get(familyId)||new Map();
      const values={{}};
      for(const [propertyName,value] of Object.entries(row.component_properties||{{}})) {{
        const propertyDefinition=(componentRecords.get(familyId)?.property_definitions||{{}})[propertyName];
        if(propertyDefinition?.type==='slot') continue;
        const actual=names.get(propertyName)||propertyName;
        const component=components.get(String(value||''));
        values[actual]=component ? component.id : value;
      }}
      if(Object.keys(values).length) {{
        try {{ node.setProperties(values); }}
        catch (error) {{ throw new Error(`Instance properties failed for ${{row.id}}: ${{error.message}}`); }}
      }}
    }}
  }}
  const usedInstanceClones=new Set();
  for(const row of ordered.filter(row => row.component_role==='instance' && !isInstanceRoot(row))) {{
    const rootRow=containingInstanceRoot(row), rootNode=rootRow?created.get(rootRow.id):null;
    if(!rootNode || !rootNode.findAll) throw new Error(`Instance root is missing for ${{row.id}}`);
    const sourceId=String(row.component_source_object_id||'');
    const candidates=rootNode.findAll(node =>
      !usedInstanceClones.has(node.id)
      && node.getSharedPluginData
      && node.getSharedPluginData('tigerstudio','stable_id')===sourceId
    );
    const node=candidates[0];
    if(!node) throw new Error(`Instance sublayer is missing for ${{row.id}} from ${{sourceId}}`);
    usedInstanceClones.add(node.id);
    node.setSharedPluginData('tigerstudio','stable_id',row.id);
    if(row.component_id) node.setSharedPluginData('tigerstudio','component_id',row.component_id);
    if(sourceId) node.setSharedPluginData('tigerstudio','component_source_object_id',sourceId);
    created.set(row.id,node);
  }}
  let pendingSlotRows=ordered.filter(row => insideInstance(row) && !created.has(row.id));
  while(pendingSlotRows.length) {{
    let progress=false; const deferred=[];
    for(const row of pendingSlotRows) {{
      const parent=created.get(row.parent_id);
      if(!parent) {{ deferred.push(row); continue; }}
      if(!('appendChild' in parent)) throw new Error(`Slot content parent cannot contain children: ${{row.id}}`);
      await createAuthoredNode(row,parent); progress=true;
    }}
    if(!progress) throw new Error(`Slot-local hierarchy is unresolved: ${{deferred.map(row=>row.id).join(',')}}`);
    pendingSlotRows=deferred;
  }}
  for(const row of ordered.filter(row => Object.keys(row.component_property_bindings||{{}}).length)) {{
    const node=created.get(row.id);
    const ownerId=containingDefinitionComponentId(row);
    const names=componentPropertyNames.get(componentFamilyId(ownerId))||new Map();
    if(!node) throw new Error(`Component property target node is missing: ${{row.id}}`);
    const references={{...(node.componentPropertyReferences||{{}})}};
    for(const [targetPath,propertyName] of Object.entries(row.component_property_bindings||{{}})) {{
      const field={{'content.text':'characters','visible':'visible','component_id':'mainComponent'}}[targetPath];
      const actual=names.get(propertyName);
      if(!field || !actual)
        throw new Error(`Component property binding is unresolved: ${{row.id}}:${{targetPath}}:${{propertyName}}`);
      references[field]=actual;
    }}
    try {{ node.componentPropertyReferences=references; }}
    catch (error) {{ throw new Error(`Component property binding failed for ${{row.id}}: ${{error.message}}`); }}
  }}
  const reactionsBySource=new Map();
  const triggerTypes={{
    click:'ON_CLICK',double_click:'ON_CLICK',hover:'ON_HOVER',
    press:'MOUSE_DOWN',focus:'ON_KEY_DOWN',keyboard:'ON_KEY_DOWN',
    delay:'AFTER_TIMEOUT',mouse_enter:'MOUSE_ENTER',
    mouse_leave:'MOUSE_LEAVE',drag:'ON_DRAG',gamepad:'ON_GAMEPAD'
  }};
  const navigationTypes={{
    navigate:'NAVIGATE',open_overlay:'OVERLAY',swap_overlay:'SWAP',
    scroll_to:'SCROLL_TO',change_variant:'CHANGE_TO'
  }};
  for(const link of doc.interactions) {{
    const source=created.get(link.source_object_id);
    if(!source)
      throw new Error(`Reaction source is missing for ${{link.id}}: ${{link.source_object_id}}`);
    if(!source.setReactionsAsync)
      throw new Error(`Reaction source cannot author reactions for ${{link.id}}: ${{link.source_object_id}}`);
    const parameters=link.parameters||{{}};
    const metadata=parameters.figma_reaction||{{}};
    const target=link.action==='change_variant'
      ? components.get(link.component_id)
      : created.get(link.target_artboard_id||link.target_object_id);
    const needsTarget=Object.prototype.hasOwnProperty.call(navigationTypes,link.action);
    if(needsTarget && !target)
      throw new Error(`Reaction target is missing for ${{link.id}}`);
    const rawTrigger=metadata.raw_trigger;
    const trigger=rawTrigger && typeof rawTrigger==='object'
      ? {{...rawTrigger}}
      : {{type:triggerTypes[link.trigger]}};
    if(!trigger.type)
      throw new Error(`Reaction trigger is unsupported for ${{link.id}}: ${{link.trigger}}`);
    const rawAction=metadata.raw_action;
    let action;
    if(rawAction && typeof rawAction==='object') {{
      action={{...rawAction}};
      if(needsTarget) action.destinationId=target.id;
    }} else if(link.action==='back') action={{type:'BACK'}};
    else if(link.action==='close_overlay') action={{type:'CLOSE'}};
    else if(needsTarget) action={{
      type:'NODE',destinationId:target.id,
      navigation:navigationTypes[link.action],
      transition:parameters.figma_transition??null,
      preserveScrollPosition:!!parameters.preserve_scroll_position
    }};
    else throw new Error(`Reaction action is unsupported for ${{link.id}}: ${{link.action}}`);
    const sourceGroups=reactionsBySource.get(link.source_object_id)||new Map();
    const reactionIndex=Number(metadata.reaction_index);
    const groupKey=Number.isFinite(reactionIndex)
      ? `figma:${{reactionIndex}}` : `interaction:${{link.id}}`;
    const group=sourceGroups.get(groupKey)||{{
      order:Number.isFinite(reactionIndex)?reactionIndex:Number.MAX_SAFE_INTEGER,
      trigger,actions:[]
    }};
    const actionIndex=Number(metadata.action_index);
    group.actions.push({{
      order:Number.isFinite(actionIndex)?actionIndex:group.actions.length,
      action
    }});
    sourceGroups.set(groupKey,group);
    reactionsBySource.set(link.source_object_id,sourceGroups);
  }}
  for(const [sourceId,sourceGroups] of reactionsBySource) {{
    const source=created.get(sourceId);
    if(!source || !source.setReactionsAsync)
      throw new Error(`Reaction source became unavailable: ${{sourceId}}`);
    const reactions=[...sourceGroups.values()]
      .sort((a,b)=>a.order-b.order)
      .map(group=>({{
        trigger:group.trigger,
        actions:group.actions.sort((a,b)=>a.order-b.order).map(row=>row.action)
      }}));
    try {{ await source.setReactionsAsync(reactions); }}
    catch (error) {{
      throw new Error(`Reaction export failed for ${{sourceId}}: ${{error.message}}`);
    }}
  }}
  figma.currentPage.selection=doc.artboards.map(x=>created.get(x.id)).filter(Boolean);
  figma.viewport.scrollAndZoomIntoView(figma.currentPage.selection);
  figma.closePlugin(`Imported ${{doc.artboards.length}} artboards and ${{doc.objects.length}} objects from Tiger Studio`);
}}
main().catch(error => figma.closePlugin('Tiger Studio import failed: '+error.message));
"""


def export_figma_plugin_package(
    document: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    normalized = normalize_ui_document(document)
    compatibility = inspect_figma_compatibility(normalized)
    if compatibility["counts"]["blocked"]:
        raise PainterUIFigmaError(
            "Figma export is blocked by unsupported objects; inspect compatibility"
        )
    target = Path(output_dir).expanduser().resolve() / "TigerStudioFigmaExport"
    target.mkdir(parents=True, exist_ok=True)
    exchange = {
        "schema": FIGMA_EXCHANGE_SCHEMA,
        "document": normalized,
        "assets": _asset_payload(normalized),
        "compatibility": compatibility,
    }
    manifest = {
        "name": "Tiger Studio Painter UI Import",
        "id": "tigerstudio-painter-ui-local-export",
        "api": "1.0.0",
        "main": "code.js",
        "editorType": ["figma"],
        "documentAccess": "dynamic-page",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "figma_exchange.json").write_text(
        json.dumps(exchange, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "compatibility_report.json").write_text(
        json.dumps(compatibility, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "code.js").write_text(_plugin_code(exchange), encoding="utf-8")
    (target / "README.txt").write_text(
        "Figma Desktop > Plugins > Development > Import plugin from manifest...\n"
        "Choose manifest.json, open a Figma Design file, then run the plugin.\n"
        "The bundle creates editable nodes; it is not a native .fig file.\n",
        encoding="utf-8",
    )
    return {
        "schema": FIGMA_EXCHANGE_SCHEMA,
        "ok": True,
        "output_dir": str(target),
        "manifest_path": str(target / "manifest.json"),
        "exchange_path": str(target / "figma_exchange.json"),
        "compatibility": compatibility,
    }


__all__ = [
    "FIGMA_EXCHANGE_SCHEMA",
    "FIGMA_IMPORT_SCHEMA",
    "PainterUIFigmaError",
    "default_figma_asset_root",
    "export_figma_plugin_package",
    "figma_file_key",
    "figma_image_paths_from_dir",
    "import_fig_file",
    "import_figma_file",
    "import_figma_json",
    "import_figma_payload",
    "inspect_figma_resources",
    "inspect_figma_compatibility",
    "map_figma_plugin_paints",
    "merge_figma_document",
]

"""Provider-neutral deterministic static-vector baking for Tiger Studio UMG.

The shared UMG schema already knows how to import a Texture2D and display it
through ``Layer.ImageFill``.  This module therefore stops at a package-time
PNG plus layout adjustment; it does not add a provider-specific Unreal path.

The first supported subset is deliberately small: a fixed-size leaf containing
complete, closed Figma fill geometry with one normal solid paint.  Anything
with children, strokes, masks, booleans, effects, dynamic sizing, or render-API
fallback geometry remains an explicit preflight blocker.
"""
from __future__ import annotations

import binascii
import copy
import hashlib
import html
import json
import math
from pathlib import Path
import re
import struct
from typing import Any, Mapping
import zlib

from PySide6.QtCore import QByteArray, QRectF, Qt, qVersion
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


STATIC_VECTOR_BAKE_SCHEMA = "tigerstudio.umg.static_vector_bake.v2"
STATIC_VECTOR_BAKE_PADDING = 2
STATIC_VECTOR_BAKE_MAX_DIMENSION = 4096
STATIC_VECTOR_BAKE_MAX_PIXELS = 16 * 1024 * 1024
STATIC_VECTOR_BAKE_MAX_GEOMETRY_ROWS = 256
STATIC_VECTOR_BAKE_MAX_SUBPATHS = 256
STATIC_VECTOR_BAKE_MAX_PATH_BYTES = 1024 * 1024
STATIC_VECTOR_BAKE_MAX_PATH_TOKENS = 100_000
STATIC_VECTOR_BAKE_PROBE_DIMENSION = 256
STATIC_VECTOR_BAKE_BOUNDS_EPSILON = 0.0001
# The logical size gets snapped to the nearest integer for hash determinism
# (see its round() calls), which can leave the actual geometry extending up
# to half a pixel past that rounded box - not a real error, just where the
# snap landed. Half a pixel is not visually distinguishable in a baked UI
# decoration, so the *outside-bounds* check tolerates it. This is
# deliberately a separate, looser constant from
# STATIC_VECTOR_BAKE_BOUNDS_EPSILON: that one also gates degenerate-subpath
# detection, where a genuinely thin but real subpath must not be misread as
# zero-area.
STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK = 0.5001
STATIC_VECTOR_BAKE_RENDERER = "qt_svg_fill_geometry_v3"
STATIC_VECTOR_BAKE_COLOR_CONTRACT = {
    "color_space": "sRGB",
    "alpha_mode": "straight",
    "channel_depth_bits": 8,
    "png_srgb_rendering_intent": 0,
}
_FIGMA_VECTOR_TYPES = frozenset(
    {"BOOLEAN_OPERATION", "LINE", "POLYGON", "REGULAR_POLYGON", "STAR", "VECTOR"}
)
_SVG_COMMAND_ARITY = {
    "M": 2,
    "L": 2,
    "H": 1,
    "V": 1,
    "C": 6,
    "S": 4,
    "Q": 4,
    "T": 2,
    "A": 7,
}
_SVG_NUMBER_PATTERN = (
    r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?"
)
_SVG_TOKEN_RE = re.compile(
    rf"(?:{_SVG_NUMBER_PATTERN})|[MmLlHhVvCcSsQqTtAaZz]|[ \t\r\n,]+"
)


def _visible_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        row
        for row in value
        if isinstance(row, Mapping) and bool(row.get("visible", True))
    ]


def _geometry_rows(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    if len(value) > STATIC_VECTOR_BAKE_MAX_GEOMETRY_ROWS:
        return []
    result: list[dict[str, str]] = []
    for row in value:
        if not isinstance(row, Mapping):
            return []
        path = str(row.get("path") or "").strip()
        if not path:
            return []
        winding_rule = str(row.get("winding_rule") or "nonzero").casefold()
        if winding_rule not in {"evenodd", "nonzero"}:
            return []
        result.append(
            {
                "path": path,
                "winding_rule": winding_rule,
            }
        )
    return result


def _path_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    if len(value) > STATIC_VECTOR_BAKE_MAX_GEOMETRY_ROWS:
        return []
    result: list[str] = []
    for row in value:
        path = str(row.get("path") or "").strip() if isinstance(row, Mapping) else str(row).strip()
        if not path:
            return []
        result.append(path)
    return result


def _rgba(value: object, fallback: str = "#00000000") -> tuple[int, int, int, int]:
    text = str(value or "").strip()
    if text.startswith("#") and len(text) == 9:
        try:
            return tuple(int(text[index : index + 2], 16) for index in (1, 3, 5, 7))  # type: ignore[return-value]
        except ValueError:
            pass
    color = QColor(text)
    if not color.isValid():
        return _rgba(fallback, "#00000000")
    return color.red(), color.green(), color.blue(), color.alpha()


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _svg_path_tokens(value: str) -> list[str] | None:
    # The broad scanner below intentionally accepts compact SVG numbers such
    # as ``0-1`` and ``.6.5``.  Commas have stricter grammar, though: they are
    # numeric separators, never command separators, and cannot be repeated.
    # Qt's SVG parser has historically recovered some malformed comma forms;
    # accepting that recovery would make the bake contract renderer-version
    # dependent, so reject those forms before tokenization.
    stripped = value.strip()
    if (
        not stripped
        or len(value.encode("utf-8")) > STATIC_VECTOR_BAKE_MAX_PATH_BYTES
        or stripped.startswith(",")
        or stripped.endswith(",")
        or re.search(r"[A-Za-z]\s*,", stripped)
        or re.search(r",\s*(?:,|[A-Za-z])", stripped)
    ):
        return None
    tokens: list[str] = []
    position = 0
    for match in _SVG_TOKEN_RE.finditer(value):
        if match.start() != position:
            return None
        token = match.group(0)
        position = match.end()
        if token.strip(" \t\r\n,"):
            tokens.append(token)
            if len(tokens) > STATIC_VECTOR_BAKE_MAX_PATH_TOKENS:
                return None
    if position != len(value):
        return None
    return tokens


def _split_closed_svg_subpaths(value: str) -> list[str] | None:
    """Validate and split one SVG path into independently closed subpaths.

    A later relative ``m`` depends on the preceding subpath's current point.
    Splitting that command into an independent renderer would change its
    meaning, so schema v2 rejects that form conservatively.  A later absolute
    ``M`` is self-contained and can be inspected independently.
    """
    tokens = _svg_path_tokens(value)
    if not tokens:
        return None
    index = 0
    current_command = ""
    open_subpath = False
    saw_move = False
    subpath_start = -1
    subpaths: list[str] = []
    command_count = 0
    while index < len(tokens):
        token = tokens[index]
        if len(token) == 1 and token.isalpha():
            current_command = token
            command_count += 1
            if command_count > STATIC_VECTOR_BAKE_MAX_PATH_TOKENS:
                return None
            index += 1
            upper = current_command.upper()
            if upper == "Z":
                if not open_subpath:
                    return None
                open_subpath = False
                subpaths.append(" ".join(tokens[subpath_start:index]))
                current_command = ""
                continue
            if upper not in _SVG_COMMAND_ARITY:
                return None
            if upper == "M":
                if open_subpath:
                    return None
                if saw_move and current_command == "m":
                    return None
                open_subpath = True
                saw_move = True
                subpath_start = index - 1
            elif not open_subpath:
                return None
        elif not current_command:
            return None

        upper = current_command.upper()
        arity = _SVG_COMMAND_ARITY.get(upper)
        if arity is None:
            return None
        end = index
        while end < len(tokens) and not (
            len(tokens[end]) == 1 and tokens[end].isalpha()
        ):
            end += 1
        parameter_count = end - index
        if parameter_count <= 0 or parameter_count % arity:
            return None
        for group_start in range(index, end, arity):
            raw_group = tokens[group_start : group_start + arity]
            group: list[float] = []
            for numeric_token in raw_group:
                try:
                    numeric = float(numeric_token)
                except (TypeError, ValueError):
                    return None
                if not math.isfinite(numeric):
                    return None
                group.append(numeric)
            if upper == "A":
                if group[0] < 0.0 or group[1] < 0.0:
                    return None
                # SVG arc flags are the literal one-character tokens 0/1;
                # accepting numeric equivalents such as 1.0 or +1 delegates
                # malformed-input recovery to Qt and is not deterministic.
                if raw_group[3] not in {"0", "1"} or raw_group[4] not in {
                    "0",
                    "1",
                }:
                    return None
        index = end
    if not saw_move or open_subpath or not subpaths:
        return None
    return subpaths


def _valid_closed_svg_path(value: str) -> bool:
    """Validate the bounded SVG path subset accepted by the bake contract."""

    return _split_closed_svg_subpaths(value) is not None


def _geometry_complexity_supported(rows: list[dict[str, str]]) -> bool:
    if not rows or len(rows) > STATIC_VECTOR_BAKE_MAX_GEOMETRY_ROWS:
        return False
    total_bytes = sum(len(row["path"].encode("utf-8")) for row in rows)
    if total_bytes > STATIC_VECTOR_BAKE_MAX_PATH_BYTES:
        return False
    subpath_count = 0
    token_count = 0
    for row in rows:
        tokens = _svg_path_tokens(row["path"])
        if tokens is None:
            return False
        token_count += len(tokens)
        if token_count > STATIC_VECTOR_BAKE_MAX_PATH_TOKENS:
            return False
        subpaths = _split_closed_svg_subpaths(row["path"])
        if subpaths is None:
            return False
        subpath_count += len(subpaths)
        if subpath_count > STATIC_VECTOR_BAKE_MAX_SUBPATHS:
            return False
    return True


def plan_static_vector_bake(
    row: Mapping[str, Any],
    *,
    resolved_size: Mapping[str, Any],
    has_children: bool,
    runtime_size_dynamic: bool,
) -> dict[str, Any]:
    """Return a pure, filesystem-free plan for the safe static subset."""

    style = row.get("style")
    style = style if isinstance(style, Mapping) else {}
    content = row.get("content")
    content = content if isinstance(content, Mapping) else {}
    figma_type = str(content.get("figma_type") or "").upper()
    raw_fill_geometry = content.get("vector_fill_geometry")
    fill_geometry = _geometry_rows(content.get("vector_fill_geometry"))
    is_candidate = figma_type in _FIGMA_VECTOR_TYPES and bool(
        content.get("vector_fill_geometry")
    )
    if not is_candidate:
        return {"status": "not_applicable", "available": False, "reasons": []}

    reasons: list[str] = []
    if has_children:
        reasons.append("figma_vector_static_bake_requires_leaf")
    if runtime_size_dynamic:
        reasons.append("figma_vector_static_bake_requires_fixed_size")
    if not fill_geometry:
        reasons.append("figma_vector_static_bake_geometry_incomplete")
        if (
            isinstance(raw_fill_geometry, list)
            and len(raw_fill_geometry) > STATIC_VECTOR_BAKE_MAX_GEOMETRY_ROWS
        ):
            reasons.append("figma_vector_static_bake_geometry_row_limit_exceeded")
        if isinstance(raw_fill_geometry, list) and any(
            isinstance(item, Mapping)
            and str(item.get("winding_rule") or "nonzero").casefold()
            not in {"evenodd", "nonzero"}
            for item in raw_fill_geometry
        ):
            reasons.append("figma_vector_static_bake_winding_rule_unsupported")
    else:
        total_geometry_bytes = sum(
            len(item["path"].encode("utf-8")) for item in fill_geometry
        )
        if total_geometry_bytes > STATIC_VECTOR_BAKE_MAX_PATH_BYTES:
            reasons.append(
                "figma_vector_static_bake_path_syntax_or_complexity_unsupported"
            )
        else:
            geometry_token_rows = [
                _svg_path_tokens(item["path"]) for item in fill_geometry
            ]
            geometry_subpath_rows = [
                _split_closed_svg_subpaths(item["path"])
                for item in fill_geometry
            ]
            if any(tokens is None for tokens in geometry_token_rows):
                reasons.append(
                    "figma_vector_static_bake_path_syntax_or_complexity_unsupported"
                )
            elif sum(
                len(tokens or []) for tokens in geometry_token_rows
            ) > STATIC_VECTOR_BAKE_MAX_PATH_TOKENS:
                reasons.append(
                    "figma_vector_static_bake_path_syntax_or_complexity_unsupported"
                )
            elif not all(
                any(token.upper() == "Z" for token in tokens)
                for tokens in geometry_token_rows
                if tokens is not None
            ):
                reasons.append("figma_vector_static_bake_geometry_incomplete")
            elif any(subpaths is None for subpaths in geometry_subpath_rows):
                reasons.append(
                    "figma_vector_static_bake_path_syntax_or_complexity_unsupported"
                )
            elif sum(
                len(subpaths or []) for subpaths in geometry_subpath_rows
            ) > STATIC_VECTOR_BAKE_MAX_SUBPATHS:
                reasons.append("figma_vector_static_bake_subpath_limit_exceeded")
            elif not _geometry_complexity_supported(fill_geometry):
                reasons.append(
                    "figma_vector_static_bake_path_syntax_or_complexity_unsupported"
                )
    raw_vector_paths = content.get("vector_paths")
    vector_paths = _path_values(raw_vector_paths)
    if raw_vector_paths and (
        not vector_paths
        or vector_paths != [item["path"] for item in fill_geometry]
    ):
        reasons.append("figma_vector_static_bake_geometry_sources_disagree")
    if content.get("vector_stroke_geometry"):
        reasons.append("figma_vector_static_bake_stroke_geometry_unsupported")
    if content.get("vector_render_path"):
        reasons.append("figma_vector_static_bake_render_fallback_unsupported")
    recovery = content.get("figma_vector_geometry_recovery")
    if isinstance(recovery, Mapping) and str(recovery.get("source") or "") == "figma_render_api":
        reasons.append("figma_vector_static_bake_render_fallback_unsupported")
    if isinstance(recovery, Mapping) and str(recovery.get("source") or "") == "semantic_primitive":
        reasons.append("figma_vector_static_bake_semantic_recovery_unsupported")
    if bool((row.get("mask") or {}).get("enabled")):
        reasons.append("figma_vector_static_bake_mask_unsupported")
    if bool((content.get("boolean") or {}).get("enabled")):
        reasons.append("figma_vector_static_bake_boolean_unsupported")
    if content.get("figma_unsupported_paints"):
        reasons.append("figma_vector_static_bake_paint_unsupported")
    if content.get("flip_x") or content.get("flip_y"):
        reasons.append("figma_vector_static_bake_object_flip_unsupported")

    fills = _visible_rows(style.get("fills"))
    if len(fills) != 1:
        reasons.append("figma_vector_static_bake_requires_one_fill")
    if fills:
        paint = fills[0]
        if str(paint.get("type") or "solid").casefold() != "solid":
            reasons.append("figma_vector_static_bake_requires_solid_fill")
        if str(paint.get("blend_mode") or "normal").casefold() != "normal":
            reasons.append("figma_vector_static_bake_fill_blend_unsupported")
    if isinstance(style.get("fill_gradient"), Mapping):
        reasons.append("figma_vector_static_bake_requires_solid_fill")
    legacy_stroke_active = (
        float(style.get("stroke_width") or 0.0) > 0.0001
        and _rgba(style.get("stroke"), "#00000000")[3] > 0
    )
    if _visible_rows(style.get("strokes")) or legacy_stroke_active:
        reasons.append("figma_vector_static_bake_stroke_unsupported")
    effects = _visible_rows(style.get("effects"))
    if effects or isinstance(style.get("shadow"), Mapping):
        reasons.append("figma_vector_static_bake_effect_unsupported")
    if str(style.get("blend_mode") or "normal").casefold() not in {"normal", "pass_through"}:
        reasons.append("figma_vector_static_bake_blend_unsupported")

    try:
        width = float(resolved_size.get("width", resolved_size.get("X")))
        height = float(resolved_size.get("height", resolved_size.get("Y")))
    except (TypeError, ValueError):
        width = height = math.nan
    if not all(math.isfinite(value) and value > 0.0 for value in (width, height)):
        reasons.append("figma_vector_static_bake_dimensions_invalid")
    else:
        # Auto-layout distribution routinely leaves genuinely fractional
        # sizes (e.g. a 1/3 split of 1160px), not just float32 noise. The
        # determinism this guards -- the hashed source and the plugin's
        # fixed-precision float formatting agreeing -- only requires that
        # both sides bake at the same *rounded* pixel size, which the
        # round() calls below already produce regardless of how fractional
        # the input was. A single shape's raster canvas being off by at most
        # half a pixel from its authored size is not visually distinguishable
        # in a baked UI decoration, so there is nothing left to block here.
        pixel_width = int(round(width)) + STATIC_VECTOR_BAKE_PADDING * 2
        pixel_height = int(round(height)) + STATIC_VECTOR_BAKE_PADDING * 2
        if (
            pixel_width > STATIC_VECTOR_BAKE_MAX_DIMENSION
            or pixel_height > STATIC_VECTOR_BAKE_MAX_DIMENSION
            or pixel_width * pixel_height > STATIC_VECTOR_BAKE_MAX_PIXELS
        ):
            reasons.append("figma_vector_static_bake_dimensions_exceed_limit")

    reasons = sorted(set(reasons))
    if reasons:
        return {"status": "unsafe", "available": False, "reasons": reasons}

    # Figma/Painter geometry resolution can leave sub-ULP float32 noise on an
    # otherwise-integer size (e.g. 11.999999046325684 instead of 12.0), which
    # the check above already treats as integer. Snap it here so the hashed
    # source and the plugin's fixed-precision canonical float formatting
    # agree; leaving the noisy value in only the two of them disagree and the
    # plugin reports baked_static_vector_source_hash_mismatch.
    width = float(round(width))
    height = float(round(height))

    # Painter preview/export selects the visible paint record before the
    # legacy style.fill shortcut.  Preserve that exact color and paint opacity
    # so a package bake cannot silently become more opaque than the Figma node.
    selected_paint = fills[0] if fills else {}
    fill_rgba = _rgba(selected_paint.get("color", style.get("fill")), "#506884FF")
    paint_opacity = max(
        0.0,
        min(1.0, float(selected_paint.get("opacity", 1.0) or 0.0)),
    )
    fill_rgba = (*fill_rgba[:3], int(round(fill_rgba[3] * paint_opacity)))
    if fill_rgba[3] <= 0:
        return {
            "status": "unsafe",
            "available": False,
            "reasons": ["figma_vector_static_bake_transparent_fill_unsupported"],
        }
    source: dict[str, Any] = {
        "schema": STATIC_VECTOR_BAKE_SCHEMA,
        "geometry": fill_geometry,
        "fill_rgba": list(fill_rgba),
        "color_contract": copy.deepcopy(STATIC_VECTOR_BAKE_COLOR_CONTRACT),
        "logical_size": {"width": width, "height": height},
        "padding": STATIC_VECTOR_BAKE_PADDING,
        "renderer": {
            "id": STATIC_VECTOR_BAKE_RENDERER,
            "qt_version": str(qVersion()),
            "antialiasing": True,
        },
        "geometry_complexity": {
            "row_count": len(fill_geometry),
            "path_bytes": sum(
                len(item["path"].encode("utf-8")) for item in fill_geometry
            ),
            "token_count": sum(
                len(_svg_path_tokens(item["path"]) or [])
                for item in fill_geometry
            ),
        },
    }
    subpath_contract, subpath_reason = _derive_subpath_contract(source)
    if subpath_reason:
        subpath_reasons = [subpath_reason]
        if subpath_reason in {
            "figma_vector_static_bake_subpath_degenerate",
            "figma_vector_static_bake_subpath_outside_logical_bounds",
            "figma_vector_static_bake_subpath_visible_geometry_missing",
        }:
            subpath_reasons.append(
                "figma_vector_static_bake_visible_geometry_missing"
            )
        return {
            "status": "unsafe",
            "available": False,
            "reasons": sorted(set(subpath_reasons)),
        }
    source["subpath_contract"] = subpath_contract
    source_hash = hashlib.sha256(_canonical_bytes(source)).hexdigest()
    plan = {
        "status": "available",
        "available": True,
        "reasons": [],
        "source_hash": source_hash,
        "source": source,
        "logical_size": dict(source["logical_size"]),
        "pixel_size": {
            "width": int(round(width)) + STATIC_VECTOR_BAKE_PADDING * 2,
            "height": int(round(height)) + STATIC_VECTOR_BAKE_PADDING * 2,
        },
        "padding": {
            "left": STATIC_VECTOR_BAKE_PADDING,
            "top": STATIC_VECTOR_BAKE_PADDING,
            "right": STATIC_VECTOR_BAKE_PADDING,
            "bottom": STATIC_VECTOR_BAKE_PADDING,
        },
        "layout_policy": "expand_about_preserved_render_pivot",
    }
    try:
        if not _probe_plan_has_visible_pixels(plan):
            return {
                "status": "unsafe",
                "available": False,
                "reasons": ["figma_vector_static_bake_visible_geometry_missing"],
            }
    except (TypeError, ValueError):
        return {
            "status": "unsafe",
            "available": False,
            "reasons": ["figma_vector_static_bake_svg_render_invalid"],
        }
    return plan


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(
        ">I", binascii.crc32(kind + data) & 0xFFFFFFFF
    )


def _image_rgba_bytes(image: QImage) -> tuple[QImage, bytes]:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    stride = rgba.bytesPerLine()
    raw = bytes(rgba.bits())
    row_bytes = rgba.width() * 4
    packed = bytearray()
    for y in range(rgba.height()):
        start = y * stride
        packed.extend(raw[start : start + row_bytes])
    return rgba, bytes(packed)


def _deterministic_png(image: QImage) -> bytes:
    rgba, packed = _image_rgba_bytes(image)
    scanlines = bytearray()
    row_bytes = rgba.width() * 4
    for y in range(rgba.height()):
        scanlines.append(0)
        start = y * row_bytes
        scanlines.extend(packed[start : start + row_bytes])
    header = struct.pack(">IIBBBBB", rgba.width(), rgba.height(), 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"sRGB", b"\x00")
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), level=9))
        + _png_chunk(b"IEND", b"")
    )


def _svg_renderer(
    source: Mapping[str, Any],
    *,
    geometry: list[Mapping[str, Any]] | None = None,
    element_ids: bool = False,
) -> QSvgRenderer:
    logical = source["logical_size"]
    width = float(logical["width"])
    height = float(logical["height"])
    red, green, blue, alpha = source["fill_rgba"]
    fill = QColor(int(red), int(green), int(blue), int(alpha))
    rows = geometry if geometry is not None else source["geometry"]
    markup = "".join(
        f'<path {f"id=\"subpath_{index}\" " if element_ids else ""}'
        f'd="{html.escape(str(item["path"]), quote=True)}" '
        f'fill="{fill.name()}" fill-opacity="{fill.alphaF():.8f}" '
        f'fill-rule="{item["winding_rule"]}" stroke="none"/>'
        for index, item in enumerate(rows)
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" overflow="visible" '
        f'width="{width:.8f}" height="{height:.8f}" '
        f'viewBox="0 0 {width:.8f} {height:.8f}">{markup}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("Static vector bake SVG geometry is invalid")
    return renderer


def _canonical_bound(value: float) -> float:
    rounded = round(float(value), 9)
    return 0.0 if abs(rounded) < 0.0000000005 else rounded


def _derive_subpath_contract(
    source: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    """Derive the hashed per-subpath draw and logical-bounds contract."""

    logical = source.get("logical_size")
    if not isinstance(logical, Mapping):
        return {}, "figma_vector_static_bake_dimensions_invalid"
    try:
        logical_width = float(logical.get("width"))
        logical_height = float(logical.get("height"))
    except (TypeError, ValueError):
        return {}, "figma_vector_static_bake_dimensions_invalid"
    geometry = _geometry_rows(source.get("geometry"))
    subpath_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(geometry):
        subpaths = _split_closed_svg_subpaths(row["path"])
        if subpaths is None:
            return {}, (
                "figma_vector_static_bake_path_syntax_or_complexity_unsupported"
            )
        for subpath_index, subpath in enumerate(subpaths):
            subpath_rows.append(
                {
                    "row_index": row_index,
                    "subpath_index": subpath_index,
                    "path": subpath,
                    "winding_rule": row["winding_rule"],
                }
            )
            if len(subpath_rows) > STATIC_VECTOR_BAKE_MAX_SUBPATHS:
                return {}, "figma_vector_static_bake_subpath_limit_exceeded"
    if not subpath_rows:
        return {}, "figma_vector_static_bake_visible_geometry_missing"

    items: list[dict[str, Any]] = []
    for flat_index, subpath in enumerate(subpath_rows):
        isolated_geometry = [
            {
                "path": subpath["path"],
                "winding_rule": subpath["winding_rule"],
            }
        ]
        try:
            renderer = _svg_renderer(
                source,
                geometry=isolated_geometry,
                element_ids=True,
            )
            bounds = renderer.boundsOnElement("subpath_0")
        except (TypeError, ValueError):
            return {}, "figma_vector_static_bake_svg_render_invalid"
        if (
            not renderer.isValid()
            or not bounds.isValid()
            or bounds.isEmpty()
            or not all(
                math.isfinite(value)
                for value in (
                    bounds.x(),
                    bounds.y(),
                    bounds.width(),
                    bounds.height(),
                )
            )
            or bounds.width() <= STATIC_VECTOR_BAKE_BOUNDS_EPSILON
            or bounds.height() <= STATIC_VECTOR_BAKE_BOUNDS_EPSILON
        ):
            return {}, "figma_vector_static_bake_subpath_degenerate"
        if (
            bounds.left() < -STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK
            or bounds.top() < -STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK
            or bounds.right()
            > logical_width + STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK
            or bounds.bottom()
            > logical_height + STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK
        ):
            return {}, "figma_vector_static_bake_subpath_outside_logical_bounds"
        isolated_source = dict(source)
        isolated_source["geometry"] = isolated_geometry
        probe_plan = {
            "source": isolated_source,
        }
        if not _probe_plan_has_visible_pixels(probe_plan):
            return {}, "figma_vector_static_bake_subpath_visible_geometry_missing"
        items.append(
            {
                "index": flat_index,
                "row_index": int(subpath["row_index"]),
                "subpath_index": int(subpath["subpath_index"]),
                "bounds": {
                    "x": _canonical_bound(bounds.x()),
                    "y": _canonical_bound(bounds.y()),
                    "width": _canonical_bound(bounds.width()),
                    "height": _canonical_bound(bounds.height()),
                },
            }
        )
    return {
        "count": len(items),
        "max_count": STATIC_VECTOR_BAKE_MAX_SUBPATHS,
        "logical_bounds_epsilon": STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK,
        "items": items,
    }, ""


def _render_source_image(
    source: Mapping[str, Any],
    *,
    pixel_width: int,
    pixel_height: int,
    render_rect: QRectF,
) -> QImage:
    renderer = _svg_renderer(source)
    image = QImage(
        int(pixel_width),
        int(pixel_height),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, render_rect)
    painter.end()
    return image


def _image_has_visible_alpha(image: QImage) -> bool:
    _rgba, packed = _image_rgba_bytes(image)
    return any(packed[index] for index in range(3, len(packed), 4))


def _probe_plan_has_visible_pixels(plan: Mapping[str, Any]) -> bool:
    source = plan["source"]
    logical = source["logical_size"]
    width = float(logical["width"])
    height = float(logical["height"])
    scale = min(
        1.0,
        STATIC_VECTOR_BAKE_PROBE_DIMENSION / max(width, height),
    )
    render_width = max(1, int(math.ceil(width * scale)))
    render_height = max(1, int(math.ceil(height * scale)))
    image = _render_source_image(
        source,
        pixel_width=render_width + STATIC_VECTOR_BAKE_PADDING * 2,
        pixel_height=render_height + STATIC_VECTOR_BAKE_PADDING * 2,
        render_rect=QRectF(
            float(STATIC_VECTOR_BAKE_PADDING),
            float(STATIC_VECTOR_BAKE_PADDING),
            float(render_width),
            float(render_height),
        ),
    )
    return _image_has_visible_alpha(image)


def _validated_materialization_plan(
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild every trusted field from the hashed source and recheck limits."""

    if not bool(plan.get("available")) or str(plan.get("status") or "") != "available":
        raise ValueError("Static vector bake plan is unavailable")
    source_value = plan.get("source")
    if not isinstance(source_value, Mapping):
        raise ValueError("Static vector bake source is missing")
    source = copy.deepcopy(dict(source_value))
    if str(source.get("schema") or "") != STATIC_VECTOR_BAKE_SCHEMA:
        raise ValueError("Static vector bake source schema is unsupported")
    renderer = source.get("renderer")
    if not isinstance(renderer, Mapping) or renderer != {
        "id": STATIC_VECTOR_BAKE_RENDERER,
        "qt_version": str(qVersion()),
        "antialiasing": True,
    }:
        raise ValueError("Static vector bake renderer contract is not reproducible")
    if source.get("color_contract") != STATIC_VECTOR_BAKE_COLOR_CONTRACT:
        raise ValueError("Static vector bake color contract is not reproducible")
    geometry = _geometry_rows(source.get("geometry"))
    if geometry != source.get("geometry") or not _geometry_complexity_supported(
        geometry
    ):
        raise ValueError("Static vector bake geometry is invalid or too complex")
    rgba = source.get("fill_rgba")
    if (
        not isinstance(rgba, list)
        or len(rgba) != 4
        or any(isinstance(value, bool) or not isinstance(value, int) for value in rgba)
        or any(value < 0 or value > 255 for value in rgba)
        or rgba[3] <= 0
    ):
        raise ValueError("Static vector bake fill color is invalid")
    logical = source.get("logical_size")
    if not isinstance(logical, Mapping):
        raise ValueError("Static vector bake logical size is missing")
    try:
        width = float(logical.get("width"))
        height = float(logical.get("height"))
    except (TypeError, ValueError):
        raise ValueError("Static vector bake logical size is invalid") from None
    if (
        not math.isfinite(width)
        or not math.isfinite(height)
        or width <= 0.0
        or height <= 0.0
        or abs(width - round(width)) > 0.000001
        or abs(height - round(height)) > 0.000001
    ):
        raise ValueError("Static vector bake logical size is invalid")
    if source.get("padding") != STATIC_VECTOR_BAKE_PADDING:
        raise ValueError("Static vector bake padding contract is invalid")
    expected_complexity = {
        "row_count": len(geometry),
        "path_bytes": sum(
            len(item["path"].encode("utf-8")) for item in geometry
        ),
        "token_count": sum(
            len(_svg_path_tokens(item["path"]) or []) for item in geometry
        ),
    }
    if source.get("geometry_complexity") != expected_complexity:
        raise ValueError("Static vector bake geometry complexity was mutated")
    expected_subpaths, subpath_reason = _derive_subpath_contract(source)
    if subpath_reason:
        raise ValueError(
            "Static vector bake subpath contract is invalid: " + subpath_reason
        )
    if source.get("subpath_contract") != expected_subpaths:
        raise ValueError("Static vector bake subpath contract was mutated")
    pixel_width = int(round(width)) + STATIC_VECTOR_BAKE_PADDING * 2
    pixel_height = int(round(height)) + STATIC_VECTOR_BAKE_PADDING * 2
    if (
        pixel_width > STATIC_VECTOR_BAKE_MAX_DIMENSION
        or pixel_height > STATIC_VECTOR_BAKE_MAX_DIMENSION
        or pixel_width * pixel_height > STATIC_VECTOR_BAKE_MAX_PIXELS
    ):
        raise ValueError("Static vector bake dimensions exceed the safety limit")
    expected_hash = hashlib.sha256(_canonical_bytes(source)).hexdigest()
    if expected_hash != str(plan.get("source_hash") or ""):
        raise ValueError("Static vector bake plan mutated after preflight")
    derived = {
        "status": "available",
        "available": True,
        "reasons": [],
        "source_hash": expected_hash,
        "source": source,
        "logical_size": {"width": width, "height": height},
        "pixel_size": {"width": pixel_width, "height": pixel_height},
        "padding": {
            "left": STATIC_VECTOR_BAKE_PADDING,
            "top": STATIC_VECTOR_BAKE_PADDING,
            "right": STATIC_VECTOR_BAKE_PADDING,
            "bottom": STATIC_VECTOR_BAKE_PADDING,
        },
        "layout_policy": "expand_about_preserved_render_pivot",
    }
    for key in ("logical_size", "pixel_size", "padding", "layout_policy"):
        if plan.get(key) != derived[key]:
            raise ValueError(f"Static vector bake {key} was mutated after preflight")
    if not _probe_plan_has_visible_pixels(derived):
        raise ValueError("Static vector bake geometry has no visible pixels")
    return derived


def _render_plan_image(plan: Mapping[str, Any]) -> tuple[dict[str, Any], QImage]:
    derived = _validated_materialization_plan(plan)
    source = derived["source"]
    logical = derived["logical_size"]
    padding = STATIC_VECTOR_BAKE_PADDING
    image = _render_source_image(
        source,
        pixel_width=int(derived["pixel_size"]["width"]),
        pixel_height=int(derived["pixel_size"]["height"]),
        render_rect=QRectF(
            float(padding),
            float(padding),
            float(logical["width"]),
            float(logical["height"]),
        ),
    )
    if not _image_has_visible_alpha(image):
        raise ValueError("Static vector bake rendered no visible pixels")
    return derived, image


def _write_identical_or_create(path: Path, payload: bytes) -> bool:
    """Create one content-addressed file, or reuse an identical existing file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
        return False
    except FileExistsError:
        if path.read_bytes() != payload:
            raise FileExistsError(
                f"Refusing to overwrite non-identical static bake artifact: {path}"
            )
        return True


def write_static_vector_bake(plan: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Materialize an available plan as deterministic PNG and JSON manifest."""

    derived, image = _render_plan_image(plan)
    expected_hash = str(derived["source_hash"])
    root = Path(output_dir).expanduser().resolve()
    stem = f"TS_Vector_{expected_hash[:24]}"
    _rgba, rgba_bytes = _image_rgba_bytes(image)
    pixel_rgba_hash = hashlib.sha256(rgba_bytes).hexdigest()
    png_bytes = _deterministic_png(image)
    content_hash = hashlib.sha256(png_bytes).hexdigest()
    png_path = root / f"{stem}.png"
    manifest_path = root / f"{stem}.json"
    manifest = {
        "schema": STATIC_VECTOR_BAKE_SCHEMA,
        "source_hash": expected_hash,
        "content_hash": content_hash,
        "pixel_rgba_sha256": pixel_rgba_hash,
        "png": png_path.name,
        "logical_size": dict(derived["logical_size"]),
        "pixel_size": dict(derived["pixel_size"]),
        "padding": dict(derived["padding"]),
        "layout_policy": str(derived["layout_policy"]),
        "color_contract": copy.deepcopy(STATIC_VECTOR_BAKE_COLOR_CONTRACT),
        "source": copy.deepcopy(derived["source"]),
        "satisfied_gate": "figma_vector_geometry_requires_deterministic_bake",
        "origin_disposition": "Baked",
    }
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8") + b"\n"
    reused_png = _write_identical_or_create(png_path, png_bytes)
    reused_manifest = _write_identical_or_create(manifest_path, manifest_bytes)
    return {
        **manifest,
        "png_path": str(png_path),
        "manifest_path": str(manifest_path),
        "reused": reused_png and reused_manifest,
    }


def expand_umg_layer_for_static_bake(
    layer: dict[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Expand a fixed Canvas layer while preserving its world render pivot."""

    derived = _validated_materialization_plan(plan)
    padding = derived["padding"]
    left = float(padding["left"])
    top = float(padding["top"])
    right = float(padding["right"])
    bottom = float(padding["bottom"])
    size = layer["Size"]
    old_width = float(size["X"])
    old_height = float(size["Y"])
    logical = derived["logical_size"]
    if (
        abs(old_width - float(logical["width"])) > 0.000001
        or abs(old_height - float(logical["height"])) > 0.000001
    ):
        raise ValueError("Static vector bake layer size no longer matches its plan")
    old_pivot = layer["RenderTransformPivot"]
    new_width = old_width + left + right
    new_height = old_height + top + bottom
    new_pivot = {
        "X": (float(old_pivot["X"]) * old_width + left) / new_width,
        "Y": (float(old_pivot["Y"]) * old_height + top) / new_height,
    }
    slot = layer["CanvasSlot"]
    minimum = slot["AnchorMinimum"]
    maximum = slot["AnchorMaximum"]
    if (
        abs(float(minimum["X"]) - float(maximum["X"])) > 0.000001
        or abs(float(minimum["Y"]) - float(maximum["Y"])) > 0.000001
    ):
        raise ValueError("Static vector bake cannot expand a stretched Canvas slot")
    # Position and leading offsets are pivot coordinates in the shared layout
    # contract.  Keeping them unchanged preserves anchors and rotation exactly.
    layer["Size"] = {"X": new_width, "Y": new_height}
    layer["Anchor"] = dict(new_pivot)
    layer["RenderTransformPivot"] = dict(new_pivot)
    slot["Alignment"] = dict(new_pivot)
    slot["Offsets"]["Right"] = new_width
    slot["Offsets"]["Bottom"] = new_height
    return {
        "original_size": {"X": old_width, "Y": old_height},
        "expanded_size": {"X": new_width, "Y": new_height},
        "original_pivot": dict(old_pivot),
        "expanded_pivot": dict(new_pivot),
        "position_preserved": dict(layer["Position"]),
        "rotation_degrees_preserved": float(layer["RotationDegrees"]),
    }


__all__ = [
    "STATIC_VECTOR_BAKE_BOUNDS_EPSILON",
    "STATIC_VECTOR_BAKE_COLOR_CONTRACT",
    "STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK",
    "STATIC_VECTOR_BAKE_MAX_DIMENSION",
    "STATIC_VECTOR_BAKE_MAX_PIXELS",
    "STATIC_VECTOR_BAKE_MAX_SUBPATHS",
    "STATIC_VECTOR_BAKE_PADDING",
    "STATIC_VECTOR_BAKE_RENDERER",
    "STATIC_VECTOR_BAKE_SCHEMA",
    "expand_umg_layer_for_static_bake",
    "plan_static_vector_bake",
    "write_static_vector_bake",
]

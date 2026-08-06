"""Conservative package-time baking for exact Figma appearance renders.

The Painter-to-UMG package path and TigerStudioUMG schema 14 consume these
artifacts as a strictly validated typed ImageFill.  A very small, static Figma
``NOISE`` or ``TEXTURE`` subset can therefore be planned and materialized
without inventing pixels: the input pixels must come from an exact Figma
render PNG recorded on the Painter object.  Noise retains the schema-14 v1
contract; Texture uses a distinct schema-15 v1 contract so the serialized
meaning is never widened silently.

The accepted subset is a fixed-size, unrotated, leaf rectangle with exactly
one visible normalized supported effect, one normal solid fill, and no stroke,
image, mask, boolean, or dynamic sizing.  Every other candidate fails closed
with explicit reasons.  Synthetic contract tests do not claim a real Figma
visual golden.
"""
from __future__ import annotations

import binascii
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from typing import Any, Mapping
import zlib

from app.painter_ui_appearance import normalize_ui_effect


STATIC_APPEARANCE_BAKE_SCHEMA = "tigerstudio.umg.static_appearance_bake.v1"
STATIC_APPEARANCE_BAKE_KIND = "static_figma_appearance_png"
STATIC_TEXTURE_BAKE_SCHEMA = "tigerstudio.umg.static_texture_bake.v1"
STATIC_TEXTURE_BAKE_KIND = "static_figma_texture_png"
STATIC_APPEARANCE_BAKE_MAX_DIMENSION = 4096
STATIC_APPEARANCE_BAKE_MAX_PIXELS = 16 * 1024 * 1024
STATIC_APPEARANCE_BAKE_MAX_FILE_BYTES = 128 * 1024 * 1024
STATIC_APPEARANCE_BAKE_BOUNDS_EPSILON = 0.000001
STATIC_APPEARANCE_BAKE_INTENDED_GATE = (
    "figma_noise_effect_requires_ui_material_or_deterministic_bake"
)
STATIC_TEXTURE_BAKE_INTENDED_GATE = (
    "figma_texture_effect_requires_ui_material_or_deterministic_bake"
)
STATIC_APPEARANCE_BAKE_COLOR_CONTRACT = {
    "color_space": "sRGB",
    "alpha_mode": "straight",
    "channel_depth_bits": 8,
    "png_srgb_rendering_intent": 0,
}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_RGBA_RE = re.compile(r"^#[0-9A-Fa-f]{8}$")


class _PngContractError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_json(value: object) -> Any:
    """Return a detached, finite JSON value or raise ``ValueError``."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("value is not finite canonical JSON") from exc


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _canonical_number(value: float) -> float:
    rounded = round(float(value), 9)
    return 0.0 if abs(rounded) < 0.0000000005 else rounded


def _bounds(value: object) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    result: dict[str, float] = {}
    for key in ("x", "y", "width", "height"):
        number = _finite_number(value.get(key))
        if number is None:
            return None
        result[key] = _canonical_number(number)
    if result["width"] <= 0.0 or result["height"] <= 0.0:
        return None
    return result


def _bounds_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return all(
        abs(float(left[key]) - float(right[key]))
        <= STATIC_APPEARANCE_BAKE_BOUNDS_EPSILON
        for key in ("x", "y", "width", "height")
    )


def _visible_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        row
        for row in value
        if isinstance(row, Mapping) and bool(row.get("visible", True))
    ]


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    )


def _paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def _inflate_exact(compressed: bytes, expected_size: int) -> bytes:
    try:
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(compressed, expected_size + 1)
        if len(decoded) > expected_size or inflater.unconsumed_tail:
            raise _PngContractError(
                "figma_appearance_static_bake_png_structure_invalid"
            )
        decoded += inflater.flush(expected_size + 1 - len(decoded))
    except _PngContractError:
        raise
    except zlib.error as exc:
        raise _PngContractError(
            "figma_appearance_static_bake_png_structure_invalid"
        ) from exc
    if (
        len(decoded) != expected_size
        or not inflater.eof
        or inflater.unused_data
        or inflater.unconsumed_tail
    ):
        raise _PngContractError(
            "figma_appearance_static_bake_png_structure_invalid"
        )
    return decoded


def _decode_png_rgba8_srgb(payload: bytes) -> dict[str, Any]:
    """Decode a bounded non-interlaced RGBA8 PNG with explicit sRGB intent 0."""

    invalid = "figma_appearance_static_bake_png_structure_invalid"
    if (
        len(payload) < len(_PNG_SIGNATURE) + 12
        or len(payload) > STATIC_APPEARANCE_BAKE_MAX_FILE_BYTES
        or not payload.startswith(_PNG_SIGNATURE)
    ):
        raise _PngContractError(invalid)

    offset = len(_PNG_SIGNATURE)
    chunks: list[tuple[bytes, bytes]] = []
    saw_iend = False
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise _PngContractError(invalid)
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        kind = payload[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(payload):
            raise _PngContractError(invalid)
        data = payload[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", payload[end - 4 : end])[0]
        if (binascii.crc32(kind + data) & 0xFFFFFFFF) != expected_crc:
            raise _PngContractError(invalid)
        chunks.append((kind, data))
        offset = end
        if kind == b"IEND":
            saw_iend = True
            if offset != len(payload):
                raise _PngContractError(invalid)
            break
    if not saw_iend or not chunks or chunks[0][0] != b"IHDR":
        raise _PngContractError(invalid)
    if sum(kind == b"IHDR" for kind, _data in chunks) != 1:
        raise _PngContractError(invalid)
    if sum(kind == b"IEND" for kind, _data in chunks) != 1:
        raise _PngContractError(invalid)

    header = chunks[0][1]
    if len(header) != 13:
        raise _PngContractError(invalid)
    width, height, depth, color_type, compression, filter_method, interlace = (
        struct.unpack(">IIBBBBB", header)
    )
    if depth != 8 or color_type != 6:
        raise _PngContractError(
            "figma_appearance_static_bake_png_not_rgba8"
        )
    if compression != 0 or filter_method != 0:
        raise _PngContractError(invalid)
    if interlace != 0:
        raise _PngContractError(
            "figma_appearance_static_bake_png_interlace_unsupported"
        )
    if (
        width <= 0
        or height <= 0
        or width > STATIC_APPEARANCE_BAKE_MAX_DIMENSION
        or height > STATIC_APPEARANCE_BAKE_MAX_DIMENSION
        or width * height > STATIC_APPEARANCE_BAKE_MAX_PIXELS
    ):
        raise _PngContractError(
            "figma_appearance_static_bake_png_dimensions_exceed_limit"
        )

    srgb_rows = [data for kind, data in chunks if kind == b"sRGB"]
    first_idat = next(
        (index for index, (kind, _data) in enumerate(chunks) if kind == b"IDAT"),
        -1,
    )
    srgb_index = next(
        (index for index, (kind, _data) in enumerate(chunks) if kind == b"sRGB"),
        -1,
    )
    if (
        len(srgb_rows) != 1
        or srgb_rows[0] != b"\x00"
        or first_idat < 0
        or srgb_index < 1
        or srgb_index > first_idat
        or any(kind in {b"iCCP", b"gAMA", b"cHRM"} for kind, _data in chunks)
    ):
        raise _PngContractError(
            "figma_appearance_static_bake_png_srgb_intent_invalid"
        )

    idat_indices = [
        index for index, (kind, _data) in enumerate(chunks) if kind == b"IDAT"
    ]
    if not idat_indices or idat_indices != list(
        range(idat_indices[0], idat_indices[-1] + 1)
    ):
        raise _PngContractError(invalid)
    known_critical = {b"IHDR", b"IDAT", b"IEND", b"PLTE"}
    if any(
        kind[:1].isupper() and kind not in known_critical
        for kind, _data in chunks
    ):
        raise _PngContractError(invalid)

    compressed = b"".join(data for kind, data in chunks if kind == b"IDAT")
    scanline_width = width * 4
    raw = _inflate_exact(compressed, height * (scanline_width + 1))
    rgba = bytearray(width * height * 4)
    previous = bytearray(scanline_width)
    for y in range(height):
        source_start = y * (scanline_width + 1)
        filter_type = raw[source_start]
        if filter_type > 4:
            raise _PngContractError(invalid)
        filtered = raw[source_start + 1 : source_start + 1 + scanline_width]
        current = bytearray(scanline_width)
        for index, value in enumerate(filtered):
            left = current[index - 4] if index >= 4 else 0
            up = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            else:
                predictor = _paeth(left, up, upper_left)
            current[index] = (value + predictor) & 0xFF
        target_start = y * scanline_width
        rgba[target_start : target_start + scanline_width] = current
        previous = current
    return {
        "width": int(width),
        "height": int(height),
        "rgba": bytes(rgba),
    }


def _deterministic_png(width: int, height: int, rgba: bytes) -> bytes:
    if len(rgba) != width * height * 4:
        raise ValueError("RGBA byte count does not match appearance bake size")
    row_bytes = width * 4
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)
        start = y * row_bytes
        scanlines.extend(rgba[start : start + row_bytes])
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        _PNG_SIGNATURE
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"sRGB", b"\x00")
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), level=9))
        + _png_chunk(b"IEND", b"")
    )


def _read_exact_png(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise _PngContractError(
            "figma_appearance_static_bake_png_unreadable"
        ) from exc
    return payload, _decode_png_rgba8_srgb(payload)


def _solid_fill(style: Mapping[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    fills = _visible_rows(style.get("fills"))
    if len(fills) != 1:
        return None, ["figma_appearance_static_bake_requires_one_solid_fill"]
    fill = fills[0]
    if str(fill.get("type") or "").strip().casefold() != "solid":
        reasons.append("figma_appearance_static_bake_requires_one_solid_fill")
    color = str(fill.get("color") or "")
    if not _RGBA_RE.fullmatch(color):
        reasons.append("figma_appearance_static_bake_solid_fill_invalid")
    opacity = _finite_number(fill.get("opacity", 1.0))
    if opacity is None or not 0.0 <= opacity <= 1.0:
        reasons.append("figma_appearance_static_bake_solid_fill_invalid")
    blend_mode = str(fill.get("blend_mode") or "normal").strip().casefold()
    if blend_mode != "normal":
        reasons.append("figma_appearance_static_bake_fill_blend_unsupported")
    if isinstance(style.get("fill_gradient"), Mapping):
        reasons.append("figma_appearance_static_bake_requires_one_solid_fill")
    if reasons:
        return None, sorted(set(reasons))
    return {
        "type": "solid",
        "color": color.upper(),
        "opacity": float(opacity),
        "blend_mode": "normal",
    }, []


def _noise_effect(style: Mapping[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    raw_effects = style.get("effects")
    if not isinstance(raw_effects, list) or any(
        not isinstance(row, Mapping) for row in raw_effects
    ):
        return None, [
            "figma_appearance_static_bake_requires_one_visible_noise_effect"
        ]
    effects = _visible_rows(raw_effects)
    if len(effects) != 1 or str(effects[0].get("type") or "").casefold() != "noise":
        return None, [
            "figma_appearance_static_bake_requires_one_visible_noise_effect"
        ]
    raw = dict(effects[0])
    raw.pop("visible", None)
    for key in ("noise_size", "density"):
        number = raw.get(key)
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(float(number))
        ):
            return None, [
                "figma_appearance_static_bake_noise_effect_not_normalized"
            ]
    raw_vector = raw.get("noise_size_vector")
    if raw_vector is not None and (
        not isinstance(raw_vector, Mapping)
        or set(raw_vector) != {"x", "y"}
        or any(
            isinstance(raw_vector.get(key), bool)
            or not isinstance(raw_vector.get(key), (int, float))
            or not math.isfinite(float(raw_vector.get(key)))
            for key in ("x", "y")
        )
    ):
        return None, [
            "figma_appearance_static_bake_noise_effect_not_normalized"
        ]
    raw_opacity = raw.get("opacity")
    if raw_opacity is not None and (
        isinstance(raw_opacity, bool)
        or not isinstance(raw_opacity, (int, float))
        or not math.isfinite(float(raw_opacity))
    ):
        return None, [
            "figma_appearance_static_bake_noise_effect_not_normalized"
        ]
    try:
        canonical_raw = _canonical_json(raw)
        normalized = _canonical_json(normalize_ui_effect(raw))
    except ValueError:
        return None, ["figma_appearance_static_bake_noise_effect_invalid"]
    if canonical_raw != normalized:
        return None, [
            "figma_appearance_static_bake_noise_effect_not_normalized"
        ]
    density = _finite_number(normalized.get("density"))
    if density is None or not 0.0 <= density <= 1.0:
        return None, [
            "figma_appearance_static_bake_noise_density_out_of_range"
        ]
    return dict(normalized), []


def _texture_effect(
    style: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    raw_effects = style.get("effects")
    if not isinstance(raw_effects, list) or any(
        not isinstance(row, Mapping) for row in raw_effects
    ):
        return None, [
            "figma_appearance_static_bake_requires_one_visible_texture_effect"
        ]
    effects = _visible_rows(raw_effects)
    if (
        len(effects) != 1
        or str(effects[0].get("type") or "").strip().casefold()
        != "texture"
    ):
        return None, [
            "figma_appearance_static_bake_requires_one_visible_texture_effect"
        ]
    raw = dict(effects[0])
    raw.pop("visible", None)
    # JSON booleans must stay booleans across the Python/C++ contract.  Plain
    # dict equality considers ``1 == True``, so the normalized-value equality
    # check below is not sufficient to reject integer stand-ins.
    if type(raw.get("clip_to_shape")) is not bool:
        return None, [
            "figma_appearance_static_bake_texture_effect_not_normalized"
        ]
    for key in ("radius", "noise_size"):
        number = raw.get(key)
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(float(number))
            or float(number) < 0.0
        ):
            return None, [
                "figma_appearance_static_bake_texture_effect_not_normalized"
            ]
    raw_vector = raw.get("noise_size_vector")
    if raw_vector is not None and (
        not isinstance(raw_vector, Mapping)
        or set(raw_vector) != {"x", "y"}
        or any(
            isinstance(raw_vector.get(key), bool)
            or not isinstance(raw_vector.get(key), (int, float))
            or not math.isfinite(float(raw_vector.get(key)))
            or float(raw_vector.get(key)) < 0.0
            for key in ("x", "y")
        )
    ):
        return None, [
            "figma_appearance_static_bake_texture_effect_not_normalized"
        ]
    try:
        canonical_raw = _canonical_json(raw)
        normalized = _canonical_json(normalize_ui_effect(raw))
    except ValueError:
        return None, ["figma_appearance_static_bake_texture_effect_invalid"]
    if canonical_raw != normalized:
        return None, [
            "figma_appearance_static_bake_texture_effect_not_normalized"
        ]
    return dict(normalized), []


def _rectangle_shape(
    style: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    raw_radii = style.get("corner_radii")
    raw_radii = raw_radii if isinstance(raw_radii, Mapping) else {}
    fallback = _finite_number(style.get("radius", 0.0))
    if fallback is None or fallback < 0.0:
        return None, ["figma_appearance_static_bake_rectangle_shape_invalid"]
    radii: dict[str, float] = {}
    for key in ("top_left", "top_right", "bottom_right", "bottom_left"):
        number = _finite_number(raw_radii.get(key, fallback))
        if number is None or number < 0.0:
            return None, [
                "figma_appearance_static_bake_rectangle_shape_invalid"
            ]
        radii[key] = _canonical_number(number)
    smoothing = _finite_number(style.get("corner_smoothing", 0.0))
    if smoothing is None or not 0.0 <= smoothing <= 1.0:
        return None, ["figma_appearance_static_bake_rectangle_shape_invalid"]
    return {
        "kind": "rectangle",
        "corner_radii": radii,
        "corner_smoothing": _canonical_number(smoothing),
    }, []


def _candidate_effect_types(style: Mapping[str, Any]) -> list[str]:
    effects = style.get("effects")
    if not isinstance(effects, list):
        return []
    return [
        effect_type
        for row in effects
        if isinstance(row, Mapping) and bool(row.get("visible", True))
        for effect_type in [
            str(row.get("type") or "").strip().casefold()
        ]
        if effect_type in {"noise", "texture"}
    ]


def _appearance_contract(effect_type: str) -> dict[str, str]:
    if effect_type == "texture":
        return {
            "schema": STATIC_TEXTURE_BAKE_SCHEMA,
            "kind": STATIC_TEXTURE_BAKE_KIND,
            "intended_gate": STATIC_TEXTURE_BAKE_INTENDED_GATE,
            "candidate_status": "tigerstudio_umg_schema15_candidate",
            "artifact_status": "tigerstudio_umg_schema15_artifact",
            "materialized_status": "tigerstudio_umg_schema15_materialized",
        }
    return {
        "schema": STATIC_APPEARANCE_BAKE_SCHEMA,
        "kind": STATIC_APPEARANCE_BAKE_KIND,
        "intended_gate": STATIC_APPEARANCE_BAKE_INTENDED_GATE,
        "candidate_status": "tigerstudio_umg_schema14_candidate",
        "artifact_status": "tigerstudio_umg_schema14_artifact",
        "materialized_status": "tigerstudio_umg_schema14_materialized",
    }


def plan_static_appearance_bake(
    row: Mapping[str, Any],
    *,
    resolved_size: Mapping[str, Any],
    has_children: bool,
    runtime_size_dynamic: bool,
) -> dict[str, Any]:
    """Validate and hash an exact-render-only static appearance subset."""

    style_value = row.get("style")
    style = style_value if isinstance(style_value, Mapping) else {}
    content_value = row.get("content")
    content = content_value if isinstance(content_value, Mapping) else {}
    candidate_effect_types = _candidate_effect_types(style)
    if not candidate_effect_types:
        return {
            "kind": STATIC_APPEARANCE_BAKE_KIND,
            "status": "not_applicable",
            "available": False,
            "reasons": [],
        }

    unique_effect_types = sorted(set(candidate_effect_types))
    if len(unique_effect_types) != 1:
        return {
            "kind": STATIC_APPEARANCE_BAKE_KIND,
            "status": "unsafe",
            "available": False,
            "reasons": [
                "figma_appearance_static_bake_effect_kind_ambiguous"
            ],
        }
    effect_type = unique_effect_types[0]
    contract = _appearance_contract(effect_type)

    reasons: list[str] = []
    if str(row.get("kind") or "").strip().casefold() != "rectangle":
        reasons.append("figma_appearance_static_bake_requires_rectangle")
    if str(content.get("figma_type") or "").strip().upper() != "RECTANGLE":
        reasons.append("figma_appearance_static_bake_requires_figma_rectangle")
    if has_children:
        reasons.append("figma_appearance_static_bake_requires_leaf")
    if runtime_size_dynamic:
        reasons.append("figma_appearance_static_bake_requires_fixed_size")
    rotation = _finite_number(row.get("rotation", 0.0))
    if rotation is None or abs(rotation) > STATIC_APPEARANCE_BAKE_BOUNDS_EPSILON:
        reasons.append("figma_appearance_static_bake_requires_unrotated")
    if bool(content.get("flip_x")) or bool(content.get("flip_y")):
        reasons.append("figma_appearance_static_bake_object_flip_unsupported")
    opacity = _finite_number(row.get("opacity", 1.0))
    if opacity is None or abs(opacity - 1.0) > STATIC_APPEARANCE_BAKE_BOUNDS_EPSILON:
        reasons.append("figma_appearance_static_bake_object_opacity_unsupported")
    if str(style.get("blend_mode") or "normal").strip().casefold() != "normal":
        reasons.append("figma_appearance_static_bake_object_blend_unsupported")

    fill, fill_reasons = _solid_fill(style)
    reasons.extend(fill_reasons)
    effect, effect_reasons = (
        _texture_effect(style)
        if effect_type == "texture"
        else _noise_effect(style)
    )
    reasons.extend(effect_reasons)
    shape, shape_reasons = _rectangle_shape(style)
    reasons.extend(shape_reasons)

    legacy_stroke = str(style.get("stroke") or "#00000000")
    legacy_stroke_visible = bool(
        _RGBA_RE.fullmatch(legacy_stroke)
        and int(legacy_stroke[-2:], 16) > 0
        and (_finite_number(style.get("stroke_width")) or 0.0) > 0.0
    )
    individual_weights = style.get("individual_stroke_weights")
    individual_visible = isinstance(individual_weights, Mapping) and any(
        (_finite_number(value) or 0.0) > 0.0
        for value in individual_weights.values()
    )
    if (
        _visible_rows(style.get("strokes"))
        or legacy_stroke_visible
        or individual_visible
        or bool(content.get("vector_stroke_geometry"))
    ):
        reasons.append("figma_appearance_static_bake_stroke_unsupported")
    if any(
        bool(content.get(key))
        for key in (
            "image_ref",
            "image_url",
            "image_path",
            "source_path",
            "vector_render_path",
        )
    ):
        reasons.append("figma_appearance_static_bake_image_unsupported")
    mask = row.get("mask")
    if isinstance(mask, Mapping) and bool(mask.get("enabled")):
        reasons.append("figma_appearance_static_bake_mask_unsupported")
    boolean = content.get("boolean")
    if isinstance(boolean, Mapping) and bool(boolean.get("enabled")):
        reasons.append("figma_appearance_static_bake_boolean_unsupported")

    width = _finite_number(
        resolved_size.get("width", resolved_size.get("X"))
    )
    height = _finite_number(
        resolved_size.get("height", resolved_size.get("Y"))
    )
    pixel_width = pixel_height = 0
    if width is None or height is None or width <= 0.0 or height <= 0.0:
        reasons.append("figma_appearance_static_bake_dimensions_invalid")
    elif (
        abs(width - round(width)) > STATIC_APPEARANCE_BAKE_BOUNDS_EPSILON
        or abs(height - round(height)) > STATIC_APPEARANCE_BAKE_BOUNDS_EPSILON
    ):
        reasons.append(
            "figma_appearance_static_bake_fractional_dimensions_unsupported"
        )
    else:
        pixel_width = int(round(width))
        pixel_height = int(round(height))
        if (
            pixel_width > STATIC_APPEARANCE_BAKE_MAX_DIMENSION
            or pixel_height > STATIC_APPEARANCE_BAKE_MAX_DIMENSION
            or pixel_width * pixel_height > STATIC_APPEARANCE_BAKE_MAX_PIXELS
        ):
            reasons.append(
                "figma_appearance_static_bake_dimensions_exceed_limit"
            )

    exact_value = content.get("figma_exact_render")
    exact = exact_value if isinstance(exact_value, Mapping) else None
    source_bounds = render_bounds = None
    input_path: Path | None = None
    source_name = node_id = ""
    scale = 1.0
    if exact is None:
        reasons.append("figma_appearance_static_bake_exact_render_record_missing")
    else:
        source_name = str(exact.get("source") or "").strip()
        if source_name != "figma_render_api":
            reasons.append(
                "figma_appearance_static_bake_exact_render_source_unsupported"
            )
        format_name = str(exact.get("format") or "png").strip().casefold()
        if format_name != "png":
            reasons.append(
                "figma_appearance_static_bake_exact_render_format_unsupported"
            )
        scale_value = _finite_number(exact.get("scale", 1.0))
        if scale_value is None or abs(scale_value - 1.0) > (
            STATIC_APPEARANCE_BAKE_BOUNDS_EPSILON
        ):
            reasons.append(
                "figma_appearance_static_bake_exact_render_scale_unsupported"
            )
        else:
            scale = float(scale_value)
        content_node_id = str(content.get("figma_node_id") or "").strip()
        record_node_id = str(exact.get("node_id") or "").strip()
        node_id = record_node_id or content_node_id
        if not node_id:
            reasons.append(
                "figma_appearance_static_bake_exact_render_node_id_missing"
            )
        if content_node_id and record_node_id and content_node_id != record_node_id:
            reasons.append(
                "figma_appearance_static_bake_exact_render_node_id_mismatch"
            )
        source_bounds = _bounds(exact.get("source_bounds"))
        render_bounds = _bounds(exact.get("render_bounds"))
        if source_bounds is None or render_bounds is None:
            reasons.append(
                "figma_appearance_static_bake_exact_render_bounds_invalid"
            )
        elif not _bounds_match(source_bounds, render_bounds):
            reasons.append(
                "figma_appearance_static_bake_exact_render_bounds_mismatch"
            )
        elif width is not None and height is not None and (
            abs(source_bounds["width"] - width)
            > STATIC_APPEARANCE_BAKE_BOUNDS_EPSILON
            or abs(source_bounds["height"] - height)
            > STATIC_APPEARANCE_BAKE_BOUNDS_EPSILON
        ):
            reasons.append(
                "figma_appearance_static_bake_exact_render_bounds_size_mismatch"
            )
        path_text = str(exact.get("png_path") or "").strip()
        if not path_text:
            reasons.append("figma_appearance_static_bake_png_path_missing")
        else:
            try:
                input_path = Path(path_text).expanduser().resolve()
            except (OSError, ValueError):
                reasons.append("figma_appearance_static_bake_png_path_invalid")
            else:
                if not input_path.is_file():
                    reasons.append("figma_appearance_static_bake_png_missing")

    input_payload = b""
    decoded: dict[str, Any] | None = None
    if input_path is not None and input_path.is_file():
        try:
            input_payload, decoded = _read_exact_png(input_path)
        except _PngContractError as exc:
            reasons.append(exc.reason)
    if decoded is not None and (
        decoded["width"] != pixel_width or decoded["height"] != pixel_height
    ):
        reasons.append("figma_appearance_static_bake_png_dimensions_mismatch")

    reasons = sorted(set(reasons))
    if reasons:
        return {
            "kind": contract["kind"],
            "status": "unsafe",
            "available": False,
            "reasons": reasons,
            "intended_gate": contract["intended_gate"],
        }

    assert effect is not None
    assert fill is not None
    assert shape is not None
    assert source_bounds is not None
    assert render_bounds is not None
    assert input_path is not None
    assert decoded is not None
    effect_hash = hashlib.sha256(_canonical_bytes(effect)).hexdigest()
    input_png_sha256 = hashlib.sha256(input_payload).hexdigest()
    pixel_rgba_sha256 = hashlib.sha256(decoded["rgba"]).hexdigest()
    logical_size = {
        "width": float(width),
        "height": float(height),
    }
    pixel_size = {"width": pixel_width, "height": pixel_height}
    source = {
        "schema": contract["schema"],
        "figma_node_id": node_id,
        "logical_size": logical_size,
        "pixel_size": pixel_size,
        "source_bounds": source_bounds,
        "render_bounds": render_bounds,
        "render_contract": {
            "source": source_name,
            "format": "png",
            "scale": scale,
        },
        "effect": effect,
        "effect_hash": effect_hash,
        "fill": fill,
        "shape": shape,
        "input_png_sha256": input_png_sha256,
        "pixel_rgba_sha256": pixel_rgba_sha256,
        "color_contract": copy.deepcopy(
            STATIC_APPEARANCE_BAKE_COLOR_CONTRACT
        ),
    }
    if effect_type == "texture":
        source["intended_gate"] = contract["intended_gate"]
    source_hash = hashlib.sha256(_canonical_bytes(source)).hexdigest()
    return {
        "kind": contract["kind"],
        "status": "available",
        "available": True,
        "reasons": [],
        "intended_gate": contract["intended_gate"],
        "integration_status": contract["candidate_status"],
        "source": source,
        "effect_hash": effect_hash,
        "source_hash": source_hash,
        "input_png": {
            "path": str(input_path),
            "png_sha256": input_png_sha256,
            "pixel_rgba_sha256": pixel_rgba_sha256,
            **pixel_size,
        },
        "logical_size": logical_size,
        "pixel_size": pixel_size,
    }


def _validated_materialization_plan(
    plan: Mapping[str, Any],
) -> tuple[dict[str, Any], Path, bytes, dict[str, Any]]:
    kind = str(plan.get("kind") or "")
    if kind == STATIC_TEXTURE_BAKE_KIND:
        effect_type = "texture"
    elif kind == STATIC_APPEARANCE_BAKE_KIND:
        effect_type = "noise"
    else:
        raise ValueError("Static appearance bake kind is unsupported")
    contract = _appearance_contract(effect_type)
    if (
        plan.get("status") != "available"
        or plan.get("available") is not True
        or plan.get("integration_status")
        != contract["candidate_status"]
        or plan.get("intended_gate") != contract["intended_gate"]
    ):
        raise ValueError("Static appearance bake plan is not available")
    source_value = plan.get("source")
    input_value = plan.get("input_png")
    if not isinstance(source_value, Mapping) or not isinstance(input_value, Mapping):
        raise ValueError("Static appearance bake plan contract is invalid")
    source = _canonical_json(source_value)
    if not isinstance(source, dict):
        raise ValueError("Static appearance bake source is invalid")
    effect = source.get("effect")
    if (
        not isinstance(effect, Mapping)
        or str(effect.get("type") or "").strip().casefold()
        != effect_type
    ):
        raise ValueError("Static appearance bake effect is invalid")
    effect_hash = hashlib.sha256(_canonical_bytes(effect)).hexdigest()
    if source.get("effect_hash") != effect_hash or plan.get("effect_hash") != effect_hash:
        raise ValueError("Static appearance bake effect hash mismatch")
    source_hash = hashlib.sha256(_canonical_bytes(source)).hexdigest()
    if plan.get("source_hash") != source_hash:
        raise ValueError("Static appearance bake source hash mismatch")
    if source.get("schema") != contract["schema"]:
        raise ValueError("Static appearance bake schema mismatch")
    if effect_type == "texture" and (
        source.get("intended_gate") != contract["intended_gate"]
    ):
        raise ValueError("Static appearance bake intended gate mismatch")
    if effect_type == "noise" and "intended_gate" in source:
        raise ValueError("Static appearance bake source contract changed")
    if source.get("color_contract") != STATIC_APPEARANCE_BAKE_COLOR_CONTRACT:
        raise ValueError("Static appearance bake color contract mismatch")

    path = Path(str(input_value.get("path") or "")).expanduser().resolve()
    payload, decoded = _read_exact_png(path)
    png_hash = hashlib.sha256(payload).hexdigest()
    rgba_hash = hashlib.sha256(decoded["rgba"]).hexdigest()
    pixel_size = source.get("pixel_size")
    if not isinstance(pixel_size, Mapping):
        raise ValueError("Static appearance bake pixel size is invalid")
    expected_width = int(pixel_size.get("width") or 0)
    expected_height = int(pixel_size.get("height") or 0)
    if (
        decoded["width"] != expected_width
        or decoded["height"] != expected_height
        or input_value.get("width") != expected_width
        or input_value.get("height") != expected_height
    ):
        raise ValueError("Static appearance bake PNG dimensions changed")
    if (
        png_hash != input_value.get("png_sha256")
        or png_hash != source.get("input_png_sha256")
        or rgba_hash != input_value.get("pixel_rgba_sha256")
        or rgba_hash != source.get("pixel_rgba_sha256")
    ):
        raise ValueError("Static appearance bake input PNG changed after planning")
    return source, path, payload, decoded


def _write_identical_or_create(path: Path, payload: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
        return False
    except FileExistsError:
        if path.read_bytes() != payload:
            raise FileExistsError(
                "Refusing to overwrite non-identical static appearance bake "
                f"artifact: {path}"
            )
        return True


def write_static_appearance_bake(
    plan: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Re-encode an available exact Figma render into a deterministic package."""

    source, input_path, input_payload, decoded = _validated_materialization_plan(
        plan
    )
    source_effect = source.get("effect")
    source_effect = source_effect if isinstance(source_effect, Mapping) else {}
    effect_type = str(source_effect.get("type") or "")
    contract = _appearance_contract(effect_type)
    source_hash = str(plan["source_hash"])
    effect_hash = str(plan["effect_hash"])
    root = Path(output_dir).expanduser().resolve()
    stem_prefix = "TS_Texture" if effect_type == "texture" else "TS_Appearance"
    stem = f"{stem_prefix}_{source_hash[:24]}"
    png_bytes = _deterministic_png(
        int(decoded["width"]),
        int(decoded["height"]),
        decoded["rgba"],
    )
    content_hash = hashlib.sha256(png_bytes).hexdigest()
    pixel_rgba_sha256 = hashlib.sha256(decoded["rgba"]).hexdigest()
    source_canonical_json = _canonical_bytes(source).decode("utf-8")
    effect_canonical_json = _canonical_bytes(source["effect"]).decode(
        "utf-8"
    )
    png_path = root / f"{stem}.png"
    manifest_path = root / f"{stem}.json"
    provenance = {
        "source": "figma_render_api",
        "figma_node_id": source["figma_node_id"],
        "format": "png",
        "scale": 1.0,
        "source_bounds": copy.deepcopy(source["source_bounds"]),
        "render_bounds": copy.deepcopy(source["render_bounds"]),
        "input_png_sha256": hashlib.sha256(input_payload).hexdigest(),
        "input_pixel_rgba_sha256": pixel_rgba_sha256,
    }
    manifest = {
        "schema": contract["schema"],
        "kind": contract["kind"],
        "source_hash": source_hash,
        "effect_hash": effect_hash,
        "source_canonical_json": source_canonical_json,
        "effect_canonical_json": effect_canonical_json,
        "content_hash": content_hash,
        "pixel_rgba_sha256": pixel_rgba_sha256,
        "png": png_path.name,
        "logical_size": copy.deepcopy(source["logical_size"]),
        "pixel_size": copy.deepcopy(source["pixel_size"]),
        "color_contract": copy.deepcopy(
            STATIC_APPEARANCE_BAKE_COLOR_CONTRACT
        ),
        "source": source,
        "provenance": provenance,
        "intended_gate": contract["intended_gate"],
        "integration_status": contract["artifact_status"],
        "umg_support_claimed": True,
    }
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    reused_png = _write_identical_or_create(png_path, png_bytes)
    reused_manifest = _write_identical_or_create(manifest_path, manifest_bytes)
    return {
        **manifest,
        "png_path": str(png_path),
        "manifest_path": str(manifest_path),
        "input_png_path": str(input_path),
        "reused": reused_png and reused_manifest,
    }


__all__ = [
    "STATIC_APPEARANCE_BAKE_BOUNDS_EPSILON",
    "STATIC_APPEARANCE_BAKE_COLOR_CONTRACT",
    "STATIC_APPEARANCE_BAKE_INTENDED_GATE",
    "STATIC_APPEARANCE_BAKE_KIND",
    "STATIC_APPEARANCE_BAKE_MAX_DIMENSION",
    "STATIC_APPEARANCE_BAKE_MAX_PIXELS",
    "STATIC_APPEARANCE_BAKE_SCHEMA",
    "STATIC_TEXTURE_BAKE_INTENDED_GATE",
    "STATIC_TEXTURE_BAKE_KIND",
    "STATIC_TEXTURE_BAKE_SCHEMA",
    "plan_static_appearance_bake",
    "write_static_appearance_bake",
]

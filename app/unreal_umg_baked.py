"""Validation for materialized Baked layers in Tiger UMG schemas 13-15.

``Baked`` is a provenance classification, not a request for Unreal to run an
unspecified rasterizer.  Schema 13 adds static-vector PNGs, schema 14 adds the
exact Figma Noise subset, and schema 15 adds the separately versioned exact
Figma Texture subset.  Each is represented by the existing typed ``ImageFill``
record.  Authoring-time source plans are validated separately and are never
accepted by the generic Unreal document preflight.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from pathlib import PurePosixPath
import re
from typing import Any, Iterable, Mapping

from app.painter_ui_appearance import normalize_ui_effect
from app.unreal_umg_image_fill import (
    IMAGE_ADJUSTMENT_KEYS,
    validate_umg_image_fill_record,
)
from app.unreal_umg_static_vector_bake import (
    STATIC_VECTOR_BAKE_BOUNDS_EPSILON,
    STATIC_VECTOR_BAKE_COLOR_CONTRACT,
    STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK,
    STATIC_VECTOR_BAKE_MAX_SUBPATHS,
    STATIC_VECTOR_BAKE_PADDING,
    STATIC_VECTOR_BAKE_RENDERER,
    STATIC_VECTOR_BAKE_SCHEMA,
    _deterministic_png,
    _image_rgba_bytes,
    _render_plan_image,
    _validated_materialization_plan,
)
from app.unreal_umg_static_appearance_bake import (
    STATIC_APPEARANCE_BAKE_COLOR_CONTRACT,
    STATIC_APPEARANCE_BAKE_INTENDED_GATE,
    STATIC_APPEARANCE_BAKE_KIND,
    STATIC_APPEARANCE_BAKE_MAX_DIMENSION,
    STATIC_APPEARANCE_BAKE_MAX_PIXELS,
    STATIC_APPEARANCE_BAKE_SCHEMA,
    STATIC_TEXTURE_BAKE_INTENDED_GATE,
    STATIC_TEXTURE_BAKE_KIND,
    STATIC_TEXTURE_BAKE_SCHEMA,
    _canonical_bytes as _appearance_canonical_bytes,
    _decode_png_rgba8_srgb as _decode_appearance_png,
    _deterministic_png as _deterministic_appearance_png,
    _validated_materialization_plan as _validated_appearance_plan,
)


MATERIALIZED_BAKED_SCHEMA_VERSION = 13
STATIC_APPEARANCE_BAKE_SCHEMA_VERSION = 14
STATIC_TEXTURE_BAKE_SCHEMA_VERSION = 15
SUPPORTED_TIGER_UMG_SCHEMA_VERSION = 20
STATIC_VECTOR_BAKE_GATE = (
    "figma_vector_geometry_requires_deterministic_bake"
)
STATIC_APPEARANCE_BAKE_GATE = STATIC_APPEARANCE_BAKE_INTENDED_GATE
STATIC_TEXTURE_BAKE_GATE = STATIC_TEXTURE_BAKE_INTENDED_GATE


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _sha256(value: object) -> str:
    text = str(value or "")
    return (
        text.casefold()
        if len(text) == 64
        and all(character in "0123456789abcdefABCDEF" for character in text)
        else ""
    )


def _safe_relative_path(value: object, suffix: str) -> bool:
    text = str(value or "")
    if (
        not text
        or "\\" in text
        or text.startswith("/")
        or text.startswith("//")
        or re.match(r"^[A-Za-z]:", text)
        or "\x00" in text
        or "//" in text
    ):
        return False
    path = PurePosixPath(text)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and "." not in path.parts
        and path.suffix.casefold() == suffix
    )


def _safe_object_name(value: object) -> str:
    """Mirror TigerStudioUMGGeneration.cpp's object-name normalizer."""

    normalized = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in str(value or "")
    )
    return normalized or "Document"


def _resource_folder(value: object) -> str:
    kind = str(value or "").casefold()
    return "Audio" if kind == "sound" else "Fonts" if kind == "font" else "Textures"


def _resource_rows(
    resources: Mapping[str, Mapping[str, Any]]
    | Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(resources, Mapping):
        return [row for row in resources.values() if isinstance(row, Mapping)]
    return [row for row in resources if isinstance(row, Mapping)]


def validate_umg_resource_identity_contract(
    resources: Mapping[str, Mapping[str, Any]]
    | Iterable[Mapping[str, Any]],
) -> list[str]:
    """Reject identities that would alias after Unreal normalizes asset paths."""

    reasons: list[str] = []
    seen_ids: set[str] = set()
    seen_destinations: set[tuple[str, str]] = set()
    for resource in _resource_rows(resources):
        resource_id = str(resource.get("Id") or "")
        if not resource_id or resource_id in seen_ids:
            reasons.append("umg_resource_id_duplicate_or_empty")
        else:
            seen_ids.add(resource_id)
        destination_key = (
            _resource_folder(resource.get("Kind")).casefold(),
            _safe_object_name(resource.get("DestinationName")).casefold(),
        )
        if destination_key in seen_destinations:
            reasons.append("umg_resource_destination_collision")
        else:
            seen_destinations.add(destination_key)
    return sorted(set(reasons))


def _resource_source_path(
    resource: Mapping[str, Any],
    *,
    resource_base_path: str | Path | None,
) -> tuple[Path | None, str]:
    text = str(resource.get("SourcePath") or "")
    if not text or "\x00" in text:
        return None, "baked_resource_source_path_invalid"
    source = Path(text).expanduser()
    if source.is_absolute():
        return source, ""
    if not _safe_relative_path(text, ".png"):
        return None, "baked_resource_source_path_invalid"
    if resource_base_path is None:
        return None, "baked_resource_file_unverified"
    return Path(resource_base_path).expanduser().resolve() / PurePosixPath(text), ""


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_and_bake(
    layer: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    try:
        payload = json.loads(str(layer.get("PayloadJson") or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}, {}, ["baked_payload_json_invalid"]
    if not isinstance(payload, Mapping):
        return {}, {}, ["baked_payload_json_invalid"]
    bake = payload.get("static_vector_bake")
    if not isinstance(bake, Mapping):
        return dict(payload), {}, ["baked_static_vector_record_missing"]
    return dict(payload), dict(bake), []


def _payload_and_appearance_bake(
    layer: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    try:
        payload = json.loads(str(layer.get("PayloadJson") or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}, {}, ["baked_payload_json_invalid"]
    if not isinstance(payload, Mapping):
        return {}, {}, ["baked_payload_json_invalid"]
    bake = payload.get("static_appearance_bake")
    if not isinstance(bake, Mapping):
        return dict(payload), {}, [
            "baked_static_appearance_record_missing"
        ]
    vector = payload.get("static_vector_bake")
    if isinstance(vector, Mapping) and str(vector.get("status") or "") in {
        "available",
        "materialized",
    }:
        return dict(payload), dict(bake), ["baked_plan_kind_conflict"]
    return dict(payload), dict(bake), []


def _static_appearance_contract(
    bake: Mapping[str, Any],
) -> dict[str, Any]:
    kind = str(bake.get("kind") or "")
    if kind == STATIC_TEXTURE_BAKE_KIND:
        return {
            "kind": STATIC_TEXTURE_BAKE_KIND,
            "source_schema": STATIC_TEXTURE_BAKE_SCHEMA,
            "effect_type": "texture",
            "intended_gate": STATIC_TEXTURE_BAKE_GATE,
            "schema_version": STATIC_TEXTURE_BAKE_SCHEMA_VERSION,
            "candidate_status": "tigerstudio_umg_schema15_candidate",
            "artifact_status": "tigerstudio_umg_schema15_artifact",
            "materialized_status": "tigerstudio_umg_schema15_materialized",
            "painter_conversion": "static_texture_png_bake",
            "materialized_mapping": (
                "texture2d_image_fill_from_static_texture_bake"
            ),
        }
    if kind == STATIC_APPEARANCE_BAKE_KIND:
        return {
            "kind": STATIC_APPEARANCE_BAKE_KIND,
            "source_schema": STATIC_APPEARANCE_BAKE_SCHEMA,
            "effect_type": "noise",
            "intended_gate": STATIC_APPEARANCE_BAKE_GATE,
            "schema_version": STATIC_APPEARANCE_BAKE_SCHEMA_VERSION,
            "candidate_status": "tigerstudio_umg_schema14_candidate",
            "artifact_status": "tigerstudio_umg_schema14_artifact",
            "materialized_status": "tigerstudio_umg_schema14_materialized",
            "painter_conversion": "static_appearance_png_bake",
            "materialized_mapping": (
                "texture2d_image_fill_from_static_appearance_bake"
            ),
        }
    return {}


def _appearance_schema_reason(
    bake: Mapping[str, Any],
    document_schema_version: int,
) -> str:
    contract = _static_appearance_contract(bake)
    if not contract:
        return "baked_static_appearance_contract_mismatch"
    required = int(contract["schema_version"])
    if int(document_schema_version) >= required:
        return ""
    return (
        "baked_static_texture_requires_schema_15"
        if required == STATIC_TEXTURE_BAKE_SCHEMA_VERSION
        else "baked_static_appearance_requires_schema_14"
    )


def _validate_appearance_bounds(
    value: object,
) -> tuple[dict[str, float], bool]:
    row = _mapping(value)
    if set(row) != {"x", "y", "width", "height"}:
        return {}, False
    result: dict[str, float] = {}
    for key in ("x", "y", "width", "height"):
        number = _finite_number(row.get(key))
        if number is None:
            return {}, False
        result[key] = number
    return result, result["width"] > 0.0 and result["height"] > 0.0


def _validate_static_appearance_source(
    bake: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    contract = _static_appearance_contract(bake)
    if not contract:
        return ["baked_static_appearance_contract_mismatch"]
    source = bake.get("source")
    if not isinstance(source, Mapping):
        return ["baked_static_appearance_source_missing"]
    source = dict(source)
    expected_keys = {
        "schema",
        "figma_node_id",
        "logical_size",
        "pixel_size",
        "source_bounds",
        "render_bounds",
        "render_contract",
        "effect",
        "effect_hash",
        "fill",
        "shape",
        "input_png_sha256",
        "pixel_rgba_sha256",
        "color_contract",
    }
    if contract["effect_type"] == "texture":
        expected_keys.add("intended_gate")
    if set(source) != expected_keys:
        reasons.append("baked_static_appearance_source_contract_invalid")
    if str(source.get("schema") or "") != contract["source_schema"]:
        reasons.append("baked_static_appearance_schema_unsupported")
    if contract["effect_type"] == "texture" and (
        source.get("intended_gate") != contract["intended_gate"]
    ):
        reasons.append("baked_static_appearance_intended_gate_invalid")
    if not str(source.get("figma_node_id") or ""):
        reasons.append("baked_static_appearance_node_id_invalid")
    if source.get("color_contract") != STATIC_APPEARANCE_BAKE_COLOR_CONTRACT:
        reasons.append("baked_static_appearance_color_contract_invalid")

    logical = _mapping(source.get("logical_size"))
    width = _finite_number(logical.get("width"))
    height = _finite_number(logical.get("height"))
    if (
        set(logical) != {"width", "height"}
        or width is None
        or height is None
        or width <= 0.0
        or height <= 0.0
        or abs(width - round(width)) > 0.000001
        or abs(height - round(height)) > 0.000001
        or width > STATIC_APPEARANCE_BAKE_MAX_DIMENSION
        or height > STATIC_APPEARANCE_BAKE_MAX_DIMENSION
        or width * height > STATIC_APPEARANCE_BAKE_MAX_PIXELS
    ):
        reasons.append("baked_static_appearance_logical_size_invalid")
        width = height = None
    pixel = _mapping(source.get("pixel_size"))
    if (
        width is None
        or height is None
        or pixel
        != {"width": int(round(width)), "height": int(round(height))}
    ):
        reasons.append("baked_static_appearance_pixel_size_invalid")

    source_bounds, source_bounds_valid = _validate_appearance_bounds(
        source.get("source_bounds")
    )
    render_bounds, render_bounds_valid = _validate_appearance_bounds(
        source.get("render_bounds")
    )
    if not source_bounds_valid or not render_bounds_valid:
        reasons.append("baked_static_appearance_bounds_invalid")
    elif (
        any(
            not _numbers_match(source_bounds[key], render_bounds[key])
            for key in ("x", "y", "width", "height")
        )
        or width is None
        or height is None
        or not _numbers_match(source_bounds["width"], width)
        or not _numbers_match(source_bounds["height"], height)
    ):
        reasons.append("baked_static_appearance_bounds_mismatch")
    if source.get("render_contract") != {
        "source": "figma_render_api",
        "format": "png",
        "scale": 1.0,
    }:
        reasons.append("baked_static_appearance_render_contract_invalid")

    effect = source.get("effect")
    if not isinstance(effect, Mapping):
        reasons.append("baked_static_appearance_effect_invalid")
        effect_hash = ""
    else:
        effect = dict(effect)
        if contract["effect_type"] == "texture":
            required_effect_keys = {
                "type",
                "radius",
                "noise_size",
                "clip_to_shape",
            }
            allowed_effect_keys = required_effect_keys | {
                "noise_size_vector",
            }
        else:
            required_effect_keys = {
                "type",
                "color",
                "blend_mode",
                "noise_size",
                "noise_type",
                "density",
            }
            allowed_effect_keys = required_effect_keys | {
                "noise_size_vector",
                "secondary_color",
                "opacity",
            }
        try:
            effect_hash = hashlib.sha256(
                _appearance_canonical_bytes(effect)
            ).hexdigest()
        except (TypeError, ValueError):
            effect_hash = ""
        effect_invalid = (
            not effect_hash
            or not required_effect_keys.issubset(effect)
            or not set(effect).issubset(allowed_effect_keys)
            or effect != normalize_ui_effect(effect)
            or str(effect.get("type") or "") != contract["effect_type"]
        )
        if contract["effect_type"] == "texture":
            vector = effect.get("noise_size_vector")
            effect_invalid = effect_invalid or (
                _finite_number(effect.get("radius")) is None
                or float(effect.get("radius")) < 0.0
                or _finite_number(effect.get("noise_size")) is None
                or float(effect.get("noise_size")) < 0.0
                or not isinstance(effect.get("clip_to_shape"), bool)
                or (
                    vector is not None
                    and (
                        not isinstance(vector, Mapping)
                        or set(vector) != {"x", "y"}
                        or any(
                            _finite_number(vector.get(axis)) is None
                            or float(vector.get(axis)) < 0.0
                            for axis in ("x", "y")
                        )
                    )
                )
            )
        else:
            vector = effect.get("noise_size_vector")
            opacity = effect.get("opacity")
            effect_invalid = effect_invalid or (
                _finite_number(effect.get("noise_size")) is None
                or float(effect.get("noise_size")) < 0.0
                or _finite_number(effect.get("density")) is None
                or not 0.0 <= float(effect.get("density")) <= 1.0
                or (
                    vector is not None
                    and (
                        not isinstance(vector, Mapping)
                        or set(vector) != {"x", "y"}
                        or any(
                            _finite_number(vector.get(axis)) is None
                            or float(vector.get(axis)) < 0.0
                            for axis in ("x", "y")
                        )
                    )
                )
                or (
                    opacity is not None
                    and (
                        _finite_number(opacity) is None
                        or not 0.0 <= float(opacity) <= 1.0
                    )
                )
            )
        if effect_invalid:
            reasons.append("baked_static_appearance_effect_invalid")
    if (
        not effect_hash
        or source.get("effect_hash") != effect_hash
        or bake.get("effect_hash") != effect_hash
    ):
        reasons.append("baked_static_appearance_effect_hash_mismatch")

    fill = _mapping(source.get("fill"))
    if (
        set(fill) != {"type", "color", "opacity", "blend_mode"}
        or fill.get("type") != "solid"
        or fill.get("blend_mode") != "normal"
        or not re.fullmatch(r"#[0-9A-F]{8}", str(fill.get("color") or ""))
        or _finite_number(fill.get("opacity")) is None
        or not 0.0 <= float(fill.get("opacity")) <= 1.0
    ):
        reasons.append("baked_static_appearance_fill_invalid")
    shape = _mapping(source.get("shape"))
    radii = _mapping(shape.get("corner_radii"))
    smoothing = _finite_number(shape.get("corner_smoothing"))
    if (
        set(shape) != {"kind", "corner_radii", "corner_smoothing"}
        or shape.get("kind") != "rectangle"
        or set(radii)
        != {"top_left", "top_right", "bottom_right", "bottom_left"}
        or any(
            _finite_number(radii.get(key)) is None
            or float(radii.get(key)) < 0.0
            for key in radii
        )
        or smoothing is None
        or not 0.0 <= smoothing <= 1.0
    ):
        reasons.append("baked_static_appearance_shape_invalid")

    for key in ("input_png_sha256", "pixel_rgba_sha256"):
        if not _sha256(source.get(key)):
            reasons.append(f"baked_static_appearance_{key}_invalid")
    if _sha256(bake.get("pixel_rgba_sha256")) and (
        _sha256(bake.get("pixel_rgba_sha256"))
        != _sha256(source.get("pixel_rgba_sha256"))
    ):
        reasons.append("baked_static_appearance_pixel_hash_mismatch")
    try:
        source_hash = hashlib.sha256(
            _appearance_canonical_bytes(source)
        ).hexdigest()
    except (TypeError, ValueError):
        source_hash = ""
    if not source_hash or _sha256(bake.get("source_hash")) != source_hash:
        reasons.append("baked_static_appearance_source_hash_mismatch")
    return sorted(set(reasons))


def _validate_static_appearance_gate_transition(
    bake: Mapping[str, Any],
) -> list[str]:
    contract = _static_appearance_contract(bake)
    if not contract:
        return ["baked_static_appearance_gate_transition_invalid"]
    intended_gate = str(contract["intended_gate"])
    outer_gate = bake.get("intended_gate")
    if (
        (str(bake.get("status") or "") == "available" or outer_gate is not None)
        and outer_gate != intended_gate
    ):
        return ["baked_static_appearance_intended_gate_invalid"]
    transition = bake.get("gate_transition")
    if not isinstance(transition, Mapping):
        return ["baked_static_appearance_gate_transition_invalid"]
    before = [str(reason) for reason in transition.get("before", [])]
    after = [str(reason) for reason in transition.get("after", [])]
    satisfied = [str(reason) for reason in transition.get("satisfied", [])]
    if (
        any(not reason for reason in [*before, *after, *satisfied])
        or before != sorted(set(before))
        or after != sorted(set(after))
        or satisfied != [intended_gate]
        or intended_gate not in before
        or after
        != [
            reason
            for reason in before
            if reason != intended_gate
        ]
    ):
        return ["baked_static_appearance_gate_transition_invalid"]
    return []


def _validate_static_vector_source(
    bake: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    source = bake.get("source")
    if not isinstance(source, Mapping):
        return ["baked_static_vector_source_missing"]
    source = dict(source)
    if set(source) != {
        "schema",
        "geometry",
        "fill_rgba",
        "stroke_rgba",
        "stroke_width",
        "stroke_inset",
        "color_contract",
        "logical_size",
        "padding",
        "renderer",
        "geometry_complexity",
        "subpath_contract",
    }:
        reasons.append("baked_static_vector_source_contract_invalid")
    if str(source.get("schema") or "") != STATIC_VECTOR_BAKE_SCHEMA:
        reasons.append("baked_static_vector_schema_unsupported")
    renderer = _mapping(source.get("renderer"))
    if (
        str(renderer.get("id") or "") != STATIC_VECTOR_BAKE_RENDERER
        or renderer.get("antialiasing") is not True
        or not str(renderer.get("qt_version") or "")
    ):
        reasons.append("baked_static_vector_renderer_invalid")
    if source.get("color_contract") != STATIC_VECTOR_BAKE_COLOR_CONTRACT:
        reasons.append("baked_static_vector_color_contract_invalid")
    geometry = source.get("geometry")
    if (
        not isinstance(geometry, list)
        or not geometry
        or any(
            not isinstance(row, Mapping)
            or not str(row.get("path") or "").strip()
            or str(row.get("winding_rule") or "")
            not in {"evenodd", "nonzero"}
            for row in geometry
        )
    ):
        reasons.append("baked_static_vector_geometry_invalid")
    rgba = source.get("fill_rgba")
    fill_channels_valid = (
        isinstance(rgba, list)
        and len(rgba) == 4
        and not any(
            isinstance(channel, bool)
            or not isinstance(channel, int)
            or channel < 0
            or channel > 255
            for channel in rgba
        )
    )
    if not fill_channels_valid:
        reasons.append("baked_static_vector_fill_invalid")
    stroke_rgba = source.get("stroke_rgba")
    stroke_channels_valid = (
        isinstance(stroke_rgba, list)
        and len(stroke_rgba) == 4
        and not any(
            isinstance(channel, bool)
            or not isinstance(channel, int)
            or channel < 0
            or channel > 255
            for channel in stroke_rgba
        )
    )
    if not stroke_channels_valid:
        reasons.append("baked_static_vector_stroke_invalid")
    stroke_width = source.get("stroke_width")
    stroke_width_number = _finite_number(stroke_width)
    if (
        isinstance(stroke_width, bool)
        or stroke_width_number is None
        or stroke_width_number < 0.0
        or not stroke_channels_valid
        or (stroke_width_number > 0.0) != (int(stroke_rgba[3]) > 0)
    ):
        reasons.append("baked_static_vector_stroke_invalid")
    if not isinstance(source.get("stroke_inset"), bool):
        reasons.append("baked_static_vector_stroke_invalid")
    # A stroke-only decoration has no fill; only reject when neither paints.
    if (
        fill_channels_valid
        and rgba[3] <= 0
        and (not stroke_channels_valid or int(stroke_rgba[3]) <= 0)
    ):
        reasons.append("baked_static_vector_fill_invalid")
    logical = _mapping(source.get("logical_size"))
    width = _finite_number(logical.get("width"))
    height = _finite_number(logical.get("height"))
    if (
        width is None
        or height is None
        or width <= 0.0
        or height <= 0.0
        or abs(width - round(width)) > 0.000001
        or abs(height - round(height)) > 0.000001
    ):
        reasons.append("baked_static_vector_logical_size_invalid")
    if source.get("padding") != STATIC_VECTOR_BAKE_PADDING:
        reasons.append("baked_static_vector_padding_invalid")
    subpath_contract = _mapping(source.get("subpath_contract"))
    subpath_count = _finite_number(subpath_contract.get("count"))
    subpath_max = _finite_number(subpath_contract.get("max_count"))
    subpath_epsilon = _finite_number(
        subpath_contract.get("logical_bounds_epsilon")
    )
    subpath_items = subpath_contract.get("items")
    subpaths_valid = (
        subpath_count is not None
        and subpath_count == round(subpath_count)
        and 1 <= subpath_count <= STATIC_VECTOR_BAKE_MAX_SUBPATHS
        and subpath_max == STATIC_VECTOR_BAKE_MAX_SUBPATHS
        and subpath_epsilon == STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK
        and isinstance(subpath_items, list)
        and len(subpath_items) == int(subpath_count)
    )
    if subpaths_valid:
        assert isinstance(subpath_items, list)
        seen_indices: set[int] = set()
        for item in subpath_items:
            if not isinstance(item, Mapping):
                subpaths_valid = False
                break
            index = _finite_number(item.get("index"))
            row_index = _finite_number(item.get("row_index"))
            local_index = _finite_number(item.get("subpath_index"))
            bounds = _mapping(item.get("bounds"))
            x = _finite_number(bounds.get("x"))
            y = _finite_number(bounds.get("y"))
            bounds_width = _finite_number(bounds.get("width"))
            bounds_height = _finite_number(bounds.get("height"))
            if (
                index is None
                or index != round(index)
                or int(index) in seen_indices
                or row_index is None
                or row_index != round(row_index)
                or row_index < 0
                or local_index is None
                or local_index != round(local_index)
                or local_index < 0
                or x is None
                or y is None
                or bounds_width is None
                or bounds_height is None
                or bounds_width <= STATIC_VECTOR_BAKE_BOUNDS_EPSILON
                or bounds_height <= STATIC_VECTOR_BAKE_BOUNDS_EPSILON
                or width is None
                or height is None
                or x < -STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK
                or y < -STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK
                or x + bounds_width
                > width + STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK
                or y + bounds_height
                > height + STATIC_VECTOR_BAKE_LOGICAL_BOUNDS_SLACK
            ):
                subpaths_valid = False
                break
            seen_indices.add(int(index))
        subpaths_valid = subpaths_valid and seen_indices == set(
            range(int(subpath_count))
        )
    if not subpaths_valid:
        reasons.append("baked_static_vector_subpath_contract_invalid")
    source_hash = _sha256(bake.get("source_hash"))
    try:
        expected_source_hash = hashlib.sha256(
            _canonical_bytes(source)
        ).hexdigest()
    except (TypeError, ValueError):
        expected_source_hash = ""
    if not source_hash or source_hash != expected_source_hash:
        reasons.append("baked_static_vector_source_hash_mismatch")
    if width is not None and height is not None and source_hash:
        reproducible_plan = {
            "status": "available",
            "available": True,
            "reasons": [],
            "source_hash": source_hash,
            "source": source,
            "logical_size": {"width": width, "height": height},
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
            _validated_materialization_plan(reproducible_plan)
        except (TypeError, ValueError):
            reasons.append("baked_static_vector_source_not_reproducible")
    return sorted(set(reasons))


def _validate_static_vector_gate_transition(
    bake: Mapping[str, Any],
) -> list[str]:
    transition = bake.get("gate_transition")
    if not isinstance(transition, Mapping):
        return ["baked_static_vector_gate_transition_invalid"]
    before = transition.get("before")
    after = transition.get("after")
    satisfied = transition.get("satisfied")
    if (
        not isinstance(before, list)
        or not isinstance(after, list)
        or not isinstance(satisfied, list)
        or any(not isinstance(reason, str) or not reason for reason in before)
        or any(not isinstance(reason, str) or not reason for reason in after)
        or any(
            not isinstance(reason, str) or not reason for reason in satisfied
        )
        or before != sorted(set(before))
        or after != sorted(set(after))
        or satisfied != [STATIC_VECTOR_BAKE_GATE]
        or STATIC_VECTOR_BAKE_GATE not in before
        or after
        != [reason for reason in before if reason != STATIC_VECTOR_BAKE_GATE]
    ):
        return ["baked_static_vector_gate_transition_invalid"]
    return []


def validate_umg_static_vector_source_plan(
    layer: Mapping[str, Any],
) -> list[str]:
    """Validate the unmaterialized Painter package-time bake plan."""

    _payload, bake, reasons = _payload_and_bake(layer)
    if reasons:
        return reasons
    if (
        str(bake.get("status") or "") != "available"
        or bake.get("available") is not True
        or list(bake.get("reasons") or [])
    ):
        reasons.append("baked_source_plan_unavailable")
    reasons.extend(_validate_static_vector_source(bake))
    reasons.extend(_validate_static_vector_gate_transition(bake))
    source = _mapping(bake.get("source"))
    logical = _mapping(source.get("logical_size"))
    width = _finite_number(logical.get("width"))
    height = _finite_number(logical.get("height"))
    layer_size = _mapping(layer.get("Size"))
    layer_width = _finite_number(layer_size.get("X"))
    layer_height = _finite_number(layer_size.get("Y"))
    if (
        width is None
        or height is None
        or layer_width is None
        or layer_height is None
        # plan_static_vector_bake snaps a genuinely fractional authored size
        # (e.g. an auto-layout 1/3 split) to the nearest integer with the
        # same round() so its hashed source and the plugin's fixed-precision
        # formatting agree; the layer's own authored Size is never re-snapped,
        # so this must compare against that same rounding, not exact equality.
        or round(layer_width) != width
        or round(layer_height) != height
    ):
        reasons.append("baked_source_plan_layer_size_mismatch")
    expected_pixel = {
        "width": int(round(width)) + STATIC_VECTOR_BAKE_PADDING * 2,
        "height": int(round(height)) + STATIC_VECTOR_BAKE_PADDING * 2,
    } if width is not None and height is not None else {}
    if bake.get("logical_size") != dict(logical):
        reasons.append("baked_source_plan_logical_size_mismatch")
    if bake.get("pixel_size") != expected_pixel:
        reasons.append("baked_source_plan_pixel_size_mismatch")
    if bake.get("padding") != {
        "left": STATIC_VECTOR_BAKE_PADDING,
        "top": STATIC_VECTOR_BAKE_PADDING,
        "right": STATIC_VECTOR_BAKE_PADDING,
        "bottom": STATIC_VECTOR_BAKE_PADDING,
    }:
        reasons.append("baked_source_plan_padding_mismatch")
    if bake.get("layout_policy") != "expand_about_preserved_render_pivot":
        reasons.append("baked_source_plan_layout_policy_unsupported")
    if str(layer.get("Kind") or "") != "Image":
        reasons.append("baked_static_vector_layer_kind_unsupported")
    if str(layer.get("AssetId") or "") or bool(layer.get("ImageFill")):
        reasons.append("baked_source_plan_already_materialized")
    if bool(layer.get("Material")) or bool(layer.get("Flipbook")):
        reasons.append("baked_conflicting_visual_record")
    if list(layer.get("BlockReasons") or []):
        reasons.append("baked_block_reasons_must_be_empty")
    return sorted(set(reasons))


def validate_umg_static_appearance_source_plan(
    layer: Mapping[str, Any],
    *,
    document_schema_version: int,
) -> list[str]:
    """Validate an unmaterialized exact-Figma appearance plan."""

    if int(document_schema_version) > SUPPORTED_TIGER_UMG_SCHEMA_VERSION:
        return ["baked_schema_version_unsupported"]
    payload, bake, reasons = _payload_and_appearance_bake(layer)
    if reasons:
        return sorted(set(reasons))
    schema_reason = _appearance_schema_reason(
        bake,
        document_schema_version,
    )
    if schema_reason:
        return [schema_reason]
    contract = _static_appearance_contract(bake)
    if (
        str(bake.get("status") or "") != "available"
        or bake.get("available") is not True
        or list(bake.get("reasons") or [])
        or bake.get("integration_status")
        != contract["candidate_status"]
    ):
        reasons.append("baked_static_appearance_source_plan_unavailable")
    reasons.extend(_validate_static_appearance_source(bake))
    reasons.extend(_validate_static_appearance_gate_transition(bake))
    try:
        _validated_appearance_plan(bake)
    except (OSError, TypeError, ValueError):
        reasons.append("baked_static_appearance_source_not_reproducible")

    source = _mapping(bake.get("source"))
    logical = _mapping(source.get("logical_size"))
    width = _finite_number(logical.get("width"))
    height = _finite_number(logical.get("height"))
    layer_size = _mapping(layer.get("Size"))
    if (
        width is None
        or height is None
        or not _numbers_match(layer_size.get("X"), width)
        or not _numbers_match(layer_size.get("Y"), height)
    ):
        reasons.append("baked_static_appearance_layer_size_mismatch")
    if bake.get("logical_size") != dict(logical):
        reasons.append("baked_static_appearance_plan_logical_size_mismatch")
    if bake.get("pixel_size") != source.get("pixel_size"):
        reasons.append("baked_static_appearance_plan_pixel_size_mismatch")
    input_png = _mapping(bake.get("input_png"))
    if (
        _sha256(input_png.get("png_sha256"))
        != _sha256(source.get("input_png_sha256"))
        or _sha256(input_png.get("pixel_rgba_sha256"))
        != _sha256(source.get("pixel_rgba_sha256"))
    ):
        reasons.append("baked_static_appearance_input_hash_mismatch")
    if str(layer.get("Kind") or "") != "Image":
        reasons.append("baked_static_appearance_layer_kind_unsupported")
    if str(layer.get("AssetId") or "") or bool(layer.get("ImageFill")):
        reasons.append("baked_source_plan_already_materialized")
    if bool(layer.get("Material")) or bool(layer.get("Flipbook")):
        reasons.append("baked_conflicting_visual_record")
    if list(layer.get("BlockReasons") or []):
        reasons.append("baked_block_reasons_must_be_empty")
    if payload.get("painter_conversion") != contract["painter_conversion"]:
        reasons.append("baked_static_appearance_payload_conversion_invalid")
    if payload.get("umg_mapping") != "package_time_texture2d_image_fill":
        reasons.append("baked_static_appearance_payload_mapping_invalid")
    return sorted(set(reasons))


def _resource_map(
    resources: Mapping[str, Mapping[str, Any]]
    | Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    if isinstance(resources, Mapping):
        return {
            str(key): value
            for key, value in resources.items()
            if isinstance(value, Mapping)
        }
    return {
        str(row.get("Id") or ""): row
        for row in resources
        if isinstance(row, Mapping) and str(row.get("Id") or "")
    }


def _numbers_match(left: object, right: object) -> bool:
    left_number = _finite_number(left)
    right_number = _finite_number(right)
    return (
        left_number is not None
        and right_number is not None
        and abs(left_number - right_number) <= 0.000001
    )


def _vector_matches(value: object, *, x: float, y: float) -> bool:
    row = _mapping(value)
    return (
        set(row) == {"X", "Y"}
        and _numbers_match(row.get("X"), x)
        and _numbers_match(row.get("Y"), y)
    )


def _validate_materialized_layout(
    layer: Mapping[str, Any],
    bake: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    source = _mapping(bake.get("source"))
    logical = _mapping(source.get("logical_size"))
    logical_width = _finite_number(logical.get("width"))
    logical_height = _finite_number(logical.get("height"))
    if logical_width is None or logical_height is None:
        return ["baked_layout_source_size_invalid"]
    padding = _finite_number(source.get("padding"))
    if padding != STATIC_VECTOR_BAKE_PADDING:
        reasons.append("baked_layout_padding_invalid")
        padding = float(STATIC_VECTOR_BAKE_PADDING)
    expanded_width = logical_width + padding * 2.0
    expanded_height = logical_height + padding * 2.0
    layer_size = _mapping(layer.get("Size"))
    if not _vector_matches(
        layer_size,
        x=expanded_width,
        y=expanded_height,
    ):
        reasons.append("baked_layer_size_mismatch")

    adjustment = bake.get("layout_adjustment")
    if not isinstance(adjustment, Mapping) or set(adjustment) != {
        "original_size",
        "expanded_size",
        "original_pivot",
        "expanded_pivot",
        "position_preserved",
        "rotation_degrees_preserved",
    }:
        return sorted(set([*reasons, "baked_layout_adjustment_invalid"]))
    if not _vector_matches(
        adjustment.get("original_size"),
        x=logical_width,
        y=logical_height,
    ):
        reasons.append("baked_layout_original_size_mismatch")
    if not _vector_matches(
        adjustment.get("expanded_size"),
        x=expanded_width,
        y=expanded_height,
    ):
        reasons.append("baked_layout_expanded_size_mismatch")

    original_pivot = _mapping(adjustment.get("original_pivot"))
    original_pivot_x = _finite_number(original_pivot.get("X"))
    original_pivot_y = _finite_number(original_pivot.get("Y"))
    if (
        set(original_pivot) != {"X", "Y"}
        or original_pivot_x is None
        or original_pivot_y is None
        or not 0.0 <= original_pivot_x <= 1.0
        or not 0.0 <= original_pivot_y <= 1.0
    ):
        reasons.append("baked_layout_original_pivot_invalid")
        original_pivot_x = 0.5
        original_pivot_y = 0.5
    expected_pivot_x = (
        original_pivot_x * logical_width + padding
    ) / expanded_width
    expected_pivot_y = (
        original_pivot_y * logical_height + padding
    ) / expanded_height
    if not _vector_matches(
        adjustment.get("expanded_pivot"),
        x=expected_pivot_x,
        y=expected_pivot_y,
    ):
        reasons.append("baked_layout_expanded_pivot_mismatch")
    for field in ("Anchor", "RenderTransformPivot"):
        if not _vector_matches(
            layer.get(field),
            x=expected_pivot_x,
            y=expected_pivot_y,
        ):
            reasons.append("baked_layout_layer_pivot_mismatch")
            break

    position = _mapping(layer.get("Position"))
    position_x = _finite_number(position.get("X"))
    position_y = _finite_number(position.get("Y"))
    if (
        position_x is None
        or position_y is None
        or not _vector_matches(
            adjustment.get("position_preserved"),
            x=position_x,
            y=position_y,
        )
    ):
        reasons.append("baked_layout_position_mismatch")
    rotation = _finite_number(layer.get("RotationDegrees"))
    if rotation is None or not _numbers_match(
        adjustment.get("rotation_degrees_preserved"), rotation
    ):
        reasons.append("baked_layout_rotation_mismatch")

    canvas_slot = _mapping(layer.get("CanvasSlot"))
    minimum = _mapping(canvas_slot.get("AnchorMinimum"))
    maximum = _mapping(canvas_slot.get("AnchorMaximum"))
    offsets = _mapping(canvas_slot.get("Offsets"))
    if (
        not _numbers_match(minimum.get("X"), maximum.get("X"))
        or not _numbers_match(minimum.get("Y"), maximum.get("Y"))
        or not _vector_matches(
            canvas_slot.get("Alignment"),
            x=expected_pivot_x,
            y=expected_pivot_y,
        )
        or _finite_number(offsets.get("Left")) is None
        or _finite_number(offsets.get("Top")) is None
        or not _numbers_match(offsets.get("Right"), expanded_width)
        or not _numbers_match(offsets.get("Bottom"), expanded_height)
    ):
        reasons.append("baked_layout_canvas_slot_mismatch")
    return sorted(set(reasons))


def _validate_static_appearance_layout_preservation(
    layer: Mapping[str, Any],
    bake: Mapping[str, Any],
) -> list[str]:
    preservation = bake.get("layout_preservation")
    expected_keys = {
        "policy",
        "Size",
        "Anchor",
        "RenderTransformPivot",
        "Position",
        "RotationDegrees",
        "CanvasSlot",
    }
    if not isinstance(preservation, Mapping) or set(preservation) != expected_keys:
        return ["baked_static_appearance_layout_preservation_invalid"]
    reasons: list[str] = []
    if preservation.get("policy") != "preserve_exact_layer_layout":
        reasons.append("baked_static_appearance_layout_policy_invalid")
    for key in (
        "Size",
        "Anchor",
        "RenderTransformPivot",
        "Position",
        "RotationDegrees",
        "CanvasSlot",
    ):
        if preservation.get(key) != layer.get(key):
            reasons.append("baked_static_appearance_layout_changed")
            break
    source = _mapping(bake.get("source"))
    logical = _mapping(source.get("logical_size"))
    layer_size = _mapping(layer.get("Size"))
    if (
        not _numbers_match(layer_size.get("X"), logical.get("width"))
        or not _numbers_match(layer_size.get("Y"), logical.get("height"))
    ):
        reasons.append("baked_static_appearance_layer_size_mismatch")
    if not _numbers_match(layer.get("RotationDegrees"), 0.0):
        reasons.append("baked_static_appearance_rotation_invalid")
    return sorted(set(reasons))


def _validate_static_appearance_canonical_strings(
    bake: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    source_text = bake.get("source_canonical_json")
    effect_text = bake.get("effect_canonical_json")
    if not isinstance(source_text, str) or not source_text:
        reasons.append("baked_static_appearance_source_canonical_json_invalid")
        source_text = ""
    if not isinstance(effect_text, str) or not effect_text:
        reasons.append("baked_static_appearance_effect_canonical_json_invalid")
        effect_text = ""
    try:
        parsed_source = json.loads(source_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed_source = None
        reasons.append("baked_static_appearance_source_canonical_json_invalid")
    try:
        parsed_effect = json.loads(effect_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed_effect = None
        reasons.append("baked_static_appearance_effect_canonical_json_invalid")
    source = bake.get("source")
    source = dict(source) if isinstance(source, Mapping) else {}
    effect = source.get("effect")
    effect = dict(effect) if isinstance(effect, Mapping) else {}
    if parsed_source != source:
        reasons.append("baked_static_appearance_source_canonical_json_mismatch")
    if parsed_effect != effect:
        reasons.append("baked_static_appearance_effect_canonical_json_mismatch")
    if isinstance(parsed_source, Mapping):
        try:
            canonical = _appearance_canonical_bytes(parsed_source).decode(
                "utf-8"
            )
        except (TypeError, ValueError):
            canonical = ""
        if canonical != source_text:
            reasons.append("baked_static_appearance_source_json_not_canonical")
    if isinstance(parsed_effect, Mapping):
        try:
            canonical = _appearance_canonical_bytes(parsed_effect).decode(
                "utf-8"
            )
        except (TypeError, ValueError):
            canonical = ""
        if canonical != effect_text:
            reasons.append("baked_static_appearance_effect_json_not_canonical")
    if source_text and hashlib.sha256(source_text.encode("utf-8")).hexdigest() != _sha256(
        bake.get("source_hash")
    ):
        reasons.append("baked_static_appearance_source_hash_mismatch")
    if effect_text and hashlib.sha256(effect_text.encode("utf-8")).hexdigest() != _sha256(
        bake.get("effect_hash")
    ):
        reasons.append("baked_static_appearance_effect_hash_mismatch")
    return sorted(set(reasons))


def _validate_materialized_static_appearance_layer(
    layer: Mapping[str, Any],
    *,
    document_schema_version: int,
    resources: Mapping[str, Mapping[str, Any]]
    | Iterable[Mapping[str, Any]],
    resource_base_path: str | Path | None,
) -> list[str]:
    if int(document_schema_version) > SUPPORTED_TIGER_UMG_SCHEMA_VERSION:
        return ["baked_schema_version_unsupported"]
    payload, bake, payload_reasons = _payload_and_appearance_bake(layer)
    if not payload_reasons:
        schema_reason = _appearance_schema_reason(
            bake,
            document_schema_version,
        )
        if schema_reason:
            return [schema_reason]
    contract = _static_appearance_contract(bake)
    reasons: list[str] = []
    reasons.extend(validate_umg_resource_identity_contract(resources))
    if str(layer.get("Disposition") or "") != "Baked":
        reasons.append("baked_disposition_required")
    if str(layer.get("Kind") or "") != "Image":
        reasons.append("baked_static_appearance_layer_kind_unsupported")
    if list(layer.get("BlockReasons") or []):
        reasons.append("baked_block_reasons_must_be_empty")
    if bool(layer.get("Material")) or bool(layer.get("Flipbook")):
        reasons.append("baked_conflicting_visual_record")

    reasons.extend(payload_reasons)
    if not payload_reasons:
        if (
            str(bake.get("status") or "") != "materialized"
            or bake.get("available") is not True
            or list(bake.get("reasons") or [])
            or bake.get("integration_status")
            != contract["materialized_status"]
            or bake.get("umg_support_claimed") is not True
        ):
            reasons.append(
                "baked_static_appearance_materialization_record_invalid"
            )
        reasons.extend(_validate_static_appearance_source(bake))
        reasons.extend(_validate_static_appearance_gate_transition(bake))
        reasons.extend(_validate_static_appearance_canonical_strings(bake))
        reasons.extend(
            _validate_static_appearance_layout_preservation(layer, bake)
        )
        if str(bake.get("origin_disposition") or "") != "Baked":
            reasons.append("baked_origin_disposition_invalid")
        if str(bake.get("satisfied_gate") or "") != contract[
            "intended_gate"
        ]:
            reasons.append("baked_satisfied_gate_invalid")
        if not _safe_relative_path(bake.get("manifest_path"), ".json"):
            reasons.append("baked_manifest_path_invalid")
        if not _safe_relative_path(bake.get("png_path"), ".png"):
            reasons.append("baked_png_path_invalid")
        if not _sha256(bake.get("manifest_sha256")):
            reasons.append("baked_manifest_hash_invalid")

    content_hash = _sha256(bake.get("content_hash"))
    pixel_hash = _sha256(bake.get("pixel_rgba_sha256"))
    if not content_hash:
        reasons.append("baked_content_hash_invalid")
    if not pixel_hash:
        reasons.append("baked_pixel_hash_invalid")
    expected_asset_id = f"texture_{content_hash}" if content_hash else ""
    layer_asset_id = str(layer.get("AssetId") or "")
    image_fill = layer.get("ImageFill")
    image_fill = dict(image_fill) if isinstance(image_fill, Mapping) else {}
    if (
        not layer_asset_id
        or str(image_fill.get("AssetId") or "") != layer_asset_id
        or layer_asset_id != expected_asset_id
    ):
        reasons.append("baked_asset_id_mismatch")
    layer_size = _mapping(layer.get("Size"))
    source_size = {
        "X": _finite_number(layer_size.get("X")),
        "Y": _finite_number(layer_size.get("Y")),
    }
    expected_image_fill = {
        "AssetId": layer_asset_id,
        "Mode": "Stretch",
        "FocalPoint": {"X": 0.5, "Y": 0.5},
        "TileScale": 1.0,
        "SourceSize": source_size,
        "Crop": {
            "Enabled": False,
            "Units": "Normalized",
            "X": 0.0,
            "Y": 0.0,
            "Width": 1.0,
            "Height": 1.0,
        },
        "NineSlice": {
            "Enabled": False,
            "Units": "Pixels",
            "Left": 0.0,
            "Top": 0.0,
            "Right": 0.0,
            "Bottom": 0.0,
        },
        "CornerRadii": {"X": 0.0, "Y": 0.0, "Z": 0.0, "W": 0.0},
        "Opacity": 1.0,
        "Tint": "#FFFFFFFF",
        "Adjustments": {key: 0.0 for key in IMAGE_ADJUSTMENT_KEYS},
    }
    if image_fill != expected_image_fill:
        reasons.append("baked_image_fill_contract_invalid")
    reasons.extend(
        validate_umg_image_fill_record(
            image_fill,
            layer_asset_id=layer_asset_id,
        )
    )
    if payload.get("image_fill") != image_fill:
        reasons.append("baked_payload_image_fill_mismatch")
    if payload.get("umg_mapping") != contract.get("materialized_mapping"):
        reasons.append("baked_payload_mapping_invalid")
    if payload.get("painter_conversion") != contract.get(
        "painter_conversion"
    ):
        reasons.append("baked_payload_conversion_invalid")

    matching_resources = [
        row
        for row in _resource_rows(resources)
        if str(row.get("Id") or "") == layer_asset_id
    ]
    resource = matching_resources[0] if len(matching_resources) == 1 else None
    if resource is None:
        reasons.append("baked_resource_missing")
    else:
        if str(resource.get("Kind") or "").casefold() != "texture":
            reasons.append("baked_resource_kind_unsupported")
        if str(resource.get("ContentHash") or "").casefold() != content_hash:
            reasons.append("baked_resource_content_hash_mismatch")
        if str(resource.get("DestinationName") or "") != f"TS_{expected_asset_id}":
            reasons.append("baked_resource_destination_name_invalid")
        try:
            settings = json.loads(str(resource.get("SettingsJson") or ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            settings = {}
        if settings != {"Usage": "ImageFill", "SRGB": True}:
            reasons.append("baked_resource_settings_invalid")
        source_path, path_reason = _resource_source_path(
            resource,
            resource_base_path=resource_base_path,
        )
        if path_reason:
            reasons.append(path_reason)
        elif source_path is not None:
            if not source_path.is_file():
                reasons.append("baked_resource_file_missing")
            else:
                try:
                    png_bytes = source_path.read_bytes()
                    decoded = _decode_appearance_png(png_bytes)
                except (OSError, TypeError, ValueError):
                    reasons.append("baked_static_appearance_png_invalid")
                else:
                    if hashlib.sha256(png_bytes).hexdigest() != content_hash:
                        reasons.append("baked_resource_file_hash_mismatch")
                    actual_pixel_hash = hashlib.sha256(
                        decoded["rgba"]
                    ).hexdigest()
                    source = _mapping(bake.get("source"))
                    pixel_size = _mapping(source.get("pixel_size"))
                    if (
                        decoded["width"] != pixel_size.get("width")
                        or decoded["height"] != pixel_size.get("height")
                    ):
                        reasons.append(
                            "baked_static_appearance_png_dimensions_mismatch"
                        )
                    if actual_pixel_hash != pixel_hash or actual_pixel_hash != _sha256(
                        source.get("pixel_rgba_sha256")
                    ):
                        reasons.append("baked_pixel_hash_mismatch")
                    expected_png = _deterministic_appearance_png(
                        int(decoded["width"]),
                        int(decoded["height"]),
                        decoded["rgba"],
                    )
                    if expected_png != png_bytes:
                        reasons.append(
                            "baked_static_appearance_png_not_deterministic"
                        )

    provenance = _mapping(bake.get("provenance"))
    source = _mapping(bake.get("source"))
    expected_provenance = {
        "source": "figma_render_api",
        "figma_node_id": source.get("figma_node_id"),
        "format": "png",
        "scale": 1.0,
        "source_bounds": source.get("source_bounds"),
        "render_bounds": source.get("render_bounds"),
        "input_png_sha256": source.get("input_png_sha256"),
        "input_pixel_rgba_sha256": source.get("pixel_rgba_sha256"),
    }
    if dict(provenance) != expected_provenance:
        reasons.append("baked_static_appearance_provenance_invalid")

    if resource_base_path is not None and _safe_relative_path(
        bake.get("manifest_path"), ".json"
    ):
        manifest_path = Path(resource_base_path).expanduser().resolve() / PurePosixPath(
            str(bake.get("manifest_path"))
        )
        if not manifest_path.is_file():
            reasons.append("baked_manifest_file_missing")
        else:
            try:
                manifest_bytes = manifest_path.read_bytes()
                manifest = json.loads(manifest_bytes.decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                reasons.append("baked_manifest_file_invalid")
            else:
                if hashlib.sha256(manifest_bytes).hexdigest() != _sha256(
                    bake.get("manifest_sha256")
                ):
                    reasons.append("baked_manifest_file_hash_mismatch")
                expected_manifest = {
                    "schema": contract.get("source_schema"),
                    "kind": contract.get("kind"),
                    "source_hash": bake.get("source_hash"),
                    "effect_hash": bake.get("effect_hash"),
                    "source_canonical_json": bake.get(
                        "source_canonical_json"
                    ),
                    "effect_canonical_json": bake.get(
                        "effect_canonical_json"
                    ),
                    "content_hash": bake.get("content_hash"),
                    "pixel_rgba_sha256": bake.get("pixel_rgba_sha256"),
                    "png": PurePosixPath(str(bake.get("png_path"))).name,
                    "logical_size": source.get("logical_size"),
                    "pixel_size": source.get("pixel_size"),
                    "color_contract": STATIC_APPEARANCE_BAKE_COLOR_CONTRACT,
                    "source": dict(source),
                    "provenance": dict(provenance),
                    "intended_gate": contract.get("intended_gate"),
                    "integration_status": contract.get("artifact_status"),
                    "umg_support_claimed": True,
                }
                if manifest != expected_manifest:
                    reasons.append("baked_manifest_contract_mismatch")
    return sorted(set(reasons))


def validate_umg_materialized_baked_layer(
    layer: Mapping[str, Any],
    *,
    document_schema_version: int,
    resources: Mapping[str, Mapping[str, Any]]
    | Iterable[Mapping[str, Any]],
    resource_base_path: str | Path | None = None,
) -> list[str]:
    """Validate schema-13 vector, schema-14 Noise, or schema-15 Texture."""

    if int(document_schema_version) < MATERIALIZED_BAKED_SCHEMA_VERSION:
        return ["baked_generation_unavailable"]
    if int(document_schema_version) > SUPPORTED_TIGER_UMG_SCHEMA_VERSION:
        return ["baked_schema_version_unsupported"]
    try:
        dispatch_payload = json.loads(str(layer.get("PayloadJson") or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        dispatch_payload = {}
    appearance_dispatch = (
        dispatch_payload.get("static_appearance_bake")
        if isinstance(dispatch_payload, Mapping)
        else None
    )
    if isinstance(appearance_dispatch, Mapping) and str(
        appearance_dispatch.get("status") or ""
    ) in {"available", "materialized"}:
        return _validate_materialized_static_appearance_layer(
            layer,
            document_schema_version=document_schema_version,
            resources=resources,
            resource_base_path=resource_base_path,
        )
    reasons: list[str] = []
    reasons.extend(validate_umg_resource_identity_contract(resources))
    if str(layer.get("Disposition") or "") != "Baked":
        reasons.append("baked_disposition_required")
    if str(layer.get("Kind") or "") != "Image":
        reasons.append("baked_static_vector_layer_kind_unsupported")
    if list(layer.get("BlockReasons") or []):
        reasons.append("baked_block_reasons_must_be_empty")
    if bool(layer.get("Material")) or bool(layer.get("Flipbook")):
        reasons.append("baked_conflicting_visual_record")

    payload, bake, payload_reasons = _payload_and_bake(layer)
    reasons.extend(payload_reasons)
    if not payload_reasons:
        if (
            str(bake.get("status") or "") != "materialized"
            or bake.get("available") is not True
            or list(bake.get("reasons") or [])
        ):
            reasons.append("baked_materialization_record_invalid")
        reasons.extend(_validate_static_vector_source(bake))
        reasons.extend(_validate_static_vector_gate_transition(bake))
        if str(bake.get("origin_disposition") or "") != "Baked":
            reasons.append("baked_origin_disposition_invalid")
        if str(bake.get("satisfied_gate") or "") != STATIC_VECTOR_BAKE_GATE:
            reasons.append("baked_satisfied_gate_invalid")
        if not _safe_relative_path(bake.get("manifest_path"), ".json"):
            reasons.append("baked_manifest_path_invalid")
        if not _safe_relative_path(bake.get("png_path"), ".png"):
            reasons.append("baked_png_path_invalid")
        reasons.extend(_validate_materialized_layout(layer, bake))

    content_hash = _sha256(bake.get("content_hash"))
    if not content_hash:
        reasons.append("baked_content_hash_invalid")
    if not _sha256(bake.get("pixel_rgba_sha256")):
        reasons.append("baked_pixel_hash_invalid")
    expected_asset_id = f"texture_{content_hash}" if content_hash else ""
    layer_asset_id = str(layer.get("AssetId") or "")
    image_fill = layer.get("ImageFill")
    image_fill = dict(image_fill) if isinstance(image_fill, Mapping) else {}
    image_asset_id = str(image_fill.get("AssetId") or "")
    if (
        not layer_asset_id
        or layer_asset_id != image_asset_id
        or layer_asset_id != expected_asset_id
    ):
        reasons.append("baked_asset_id_mismatch")

    layer_size = _mapping(layer.get("Size"))
    source_size = {
        "X": _finite_number(layer_size.get("X")),
        "Y": _finite_number(layer_size.get("Y")),
    }
    expected_image_fill = {
        "AssetId": layer_asset_id,
        "Mode": "Stretch",
        "FocalPoint": {"X": 0.5, "Y": 0.5},
        "TileScale": 1.0,
        "SourceSize": source_size,
        "Crop": {
            "Enabled": False,
            "Units": "Normalized",
            "X": 0.0,
            "Y": 0.0,
            "Width": 1.0,
            "Height": 1.0,
        },
        "NineSlice": {
            "Enabled": False,
            "Units": "Pixels",
            "Left": 0.0,
            "Top": 0.0,
            "Right": 0.0,
            "Bottom": 0.0,
        },
        "CornerRadii": {"X": 0.0, "Y": 0.0, "Z": 0.0, "W": 0.0},
        "Opacity": 1.0,
        "Tint": "#FFFFFFFF",
        "Adjustments": {key: 0.0 for key in IMAGE_ADJUSTMENT_KEYS},
    }
    if image_fill != expected_image_fill:
        reasons.append("baked_image_fill_contract_invalid")
    reasons.extend(
        validate_umg_image_fill_record(
            image_fill,
            layer_asset_id=layer_asset_id,
        )
    )
    if payload.get("image_fill") != image_fill:
        reasons.append("baked_payload_image_fill_mismatch")
    if payload.get("umg_mapping") != (
        "texture2d_image_fill_from_static_vector_bake"
    ):
        reasons.append("baked_payload_mapping_invalid")
    if payload.get("painter_conversion") != "static_vector_png_bake":
        reasons.append("baked_payload_conversion_invalid")

    matching_resources = [
        row
        for row in _resource_rows(resources)
        if str(row.get("Id") or "") == layer_asset_id
    ]
    resource = matching_resources[0] if len(matching_resources) == 1 else None
    if resource is None:
        reasons.append("baked_resource_missing")
    else:
        if str(resource.get("Kind") or "").casefold() != "texture":
            reasons.append("baked_resource_kind_unsupported")
        if str(resource.get("ContentHash") or "").casefold() != content_hash:
            reasons.append("baked_resource_content_hash_mismatch")
        expected_destination = f"TS_{expected_asset_id}"
        if str(resource.get("DestinationName") or "") != expected_destination:
            reasons.append("baked_resource_destination_name_invalid")
        try:
            settings = json.loads(str(resource.get("SettingsJson") or ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            settings = {}
        if settings != {"Usage": "ImageFill", "SRGB": True}:
            reasons.append("baked_resource_settings_invalid")
        source_path, path_reason = _resource_source_path(
            resource,
            resource_base_path=resource_base_path,
        )
        if path_reason:
            reasons.append(path_reason)
        elif source_path is not None:
            if source_path.suffix.casefold() != ".png":
                reasons.append("baked_resource_source_path_invalid")
            elif not source_path.is_file():
                reasons.append("baked_resource_file_missing")
            else:
                try:
                    actual_hash = _hash_file(source_path)
                except OSError:
                    reasons.append("baked_resource_file_unreadable")
                else:
                    if actual_hash != content_hash:
                        reasons.append("baked_resource_file_hash_mismatch")
                    source = _mapping(bake.get("source"))
                    logical = _mapping(source.get("logical_size"))
                    width = _finite_number(logical.get("width"))
                    height = _finite_number(logical.get("height"))
                    source_hash = _sha256(bake.get("source_hash"))
                    if width is not None and height is not None and source_hash:
                        plan = {
                            "status": "available",
                            "available": True,
                            "reasons": [],
                            "source_hash": source_hash,
                            "source": dict(source),
                            "logical_size": {"width": width, "height": height},
                            "pixel_size": {
                                "width": int(round(width))
                                + STATIC_VECTOR_BAKE_PADDING * 2,
                                "height": int(round(height))
                                + STATIC_VECTOR_BAKE_PADDING * 2,
                            },
                            "padding": {
                                "left": STATIC_VECTOR_BAKE_PADDING,
                                "top": STATIC_VECTOR_BAKE_PADDING,
                                "right": STATIC_VECTOR_BAKE_PADDING,
                                "bottom": STATIC_VECTOR_BAKE_PADDING,
                            },
                            "layout_policy": (
                                "expand_about_preserved_render_pivot"
                            ),
                        }
                        try:
                            _derived, expected_image = _render_plan_image(plan)
                            _rgba_image, expected_rgba = _image_rgba_bytes(
                                expected_image
                            )
                            expected_png = _deterministic_png(expected_image)
                        except (TypeError, ValueError):
                            reasons.append(
                                "baked_static_vector_source_not_reproducible"
                            )
                        else:
                            if hashlib.sha256(expected_png).hexdigest() != content_hash:
                                reasons.append(
                                    "baked_resource_source_render_mismatch"
                                )
                            if hashlib.sha256(expected_rgba).hexdigest() != _sha256(
                                bake.get("pixel_rgba_sha256")
                            ):
                                reasons.append("baked_pixel_hash_mismatch")
    return sorted(set(reasons))


__all__ = [
    "MATERIALIZED_BAKED_SCHEMA_VERSION",
    "STATIC_APPEARANCE_BAKE_GATE",
    "STATIC_APPEARANCE_BAKE_SCHEMA",
    "STATIC_APPEARANCE_BAKE_SCHEMA_VERSION",
    "STATIC_TEXTURE_BAKE_GATE",
    "STATIC_TEXTURE_BAKE_SCHEMA",
    "STATIC_TEXTURE_BAKE_SCHEMA_VERSION",
    "SUPPORTED_TIGER_UMG_SCHEMA_VERSION",
    "STATIC_VECTOR_BAKE_GATE",
    "STATIC_VECTOR_BAKE_RENDERER",
    "STATIC_VECTOR_BAKE_SCHEMA",
    "validate_umg_materialized_baked_layer",
    "validate_umg_resource_identity_contract",
    "validate_umg_static_appearance_source_plan",
    "validate_umg_static_vector_source_plan",
]

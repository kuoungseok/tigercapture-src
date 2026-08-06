"""Prove schema-14 Noise and schema-15 Texture with synthetic PNG fixtures.

This is a pipeline contract test, not a Figma visual golden.  The input is a
locally generated RGBA8+sRGB PNG and is always identified as
``synthetic_contract_fixture`` in both the fixture and the final report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_ui_document import create_ui_document
from app.painter_ui_umg_adapter import generate_painter_umg
from app.unreal_umg_static_appearance_bake import (
    STATIC_APPEARANCE_BAKE_INTENDED_GATE,
    STATIC_APPEARANCE_BAKE_KIND,
    STATIC_APPEARANCE_BAKE_SCHEMA,
    STATIC_TEXTURE_BAKE_INTENDED_GATE,
    STATIC_TEXTURE_BAKE_KIND,
    STATIC_TEXTURE_BAKE_SCHEMA,
    _deterministic_png,
)
from app.unreal_umg_workflow import DEFAULT_UNREAL_ENGINE_ROOT
from tools.qa_painter_ui_unreal_umg import (
    _ensure_project,
    _render_generated_asset,
    _reopen_generated_asset,
)


QA_SCHEMA = "tigercapture.painter.ui.unreal_umg_static_appearance_bake_qa.v1"
SOURCE_PROVENANCE = "synthetic_contract_fixture"
CANVAS_WIDTH = 96
CANVAS_HEIGHT = 64
LAYER_X = 23
LAYER_Y = 17
LAYER_WIDTH = 32
LAYER_HEIGHT = 24
LAYER_ID = "synthetic-noise-appearance"
LAYER_NAME = "Synthetic Noise Appearance"
PACKAGE_DIRECTORY = "packet_supported"
DEFAULT_EXPECTED_PLUGIN_VERSION = "1.6.0"
SUPPORTED_PLUGIN_VERSIONS = frozenset({"1.4.0", "1.5.0", "1.6.0"})
REQUIRED_PLUGIN_DLLS = (
    "UnrealEditor-TigerStudioUMG.dll",
    "UnrealEditor-TigerStudioUMGEditor.dll",
)


def _effect_contract(effect: str) -> dict[str, Any]:
    normalized = str(effect or "").strip().casefold()
    if normalized == "noise":
        return {
            "effect": "noise",
            "schema_version": 14,
            "kind": STATIC_APPEARANCE_BAKE_KIND,
            "source_schema": STATIC_APPEARANCE_BAKE_SCHEMA,
            "gate": STATIC_APPEARANCE_BAKE_INTENDED_GATE,
            "conversion": "static_appearance_png_bake",
            "mapping": "texture2d_image_fill_from_static_appearance_bake",
            "artifact_status": "tigerstudio_umg_schema14_artifact",
            "materialized_status": "tigerstudio_umg_schema14_materialized",
            "layer_id": LAYER_ID,
            "layer_name": LAYER_NAME,
            "node_id": "synthetic:appearance:1",
            "package_directory": PACKAGE_DIRECTORY,
            "fixture_filename": "synthetic_static_appearance.png",
            "capture_filename": "static_appearance_fwidget_renderer.png",
        }
    if normalized == "texture":
        return {
            "effect": "texture",
            "schema_version": 15,
            "kind": STATIC_TEXTURE_BAKE_KIND,
            "source_schema": STATIC_TEXTURE_BAKE_SCHEMA,
            "gate": STATIC_TEXTURE_BAKE_INTENDED_GATE,
            "conversion": "static_texture_png_bake",
            "mapping": "texture2d_image_fill_from_static_texture_bake",
            "artifact_status": "tigerstudio_umg_schema15_artifact",
            "materialized_status": "tigerstudio_umg_schema15_materialized",
            "layer_id": "synthetic-texture-appearance",
            "layer_name": "Synthetic Texture Appearance",
            "node_id": "synthetic:texture:1",
            "package_directory": "packet_texture_supported",
            "fixture_filename": "synthetic_static_texture.png",
            "capture_filename": "static_texture_fwidget_renderer.png",
        }
    raise ValueError(f"unsupported_effect:{effect}")


def _effect_row(effect: str) -> dict[str, Any]:
    if effect == "texture":
        return {
            "type": "texture",
            "visible": True,
            "radius": 4.0,
            "noise_size": 8.0,
            "clip_to_shape": True,
            "noise_size_vector": {"x": 8.0, "y": 12.0},
        }
    return {
        "type": "noise",
        "visible": True,
        "color": "#18304CBF",
        "blend_mode": "soft_light",
        "noise_size": 6.0,
        "noise_type": "duotone",
        "density": 0.42,
        "secondary_color": "#E8C8A480",
    }


def _synthetic_rgba(width: int, height: int) -> bytes:
    """Return an opaque, blocky color field that exposes pixel corruption."""

    palette = (
        (22, 42, 76, 255),
        (206, 78, 92, 255),
        (43, 184, 132, 255),
        (236, 183, 65, 255),
        (105, 78, 196, 255),
        (37, 154, 210, 255),
    )
    return bytes(
        channel
        for y in range(height)
        for x in range(width)
        for channel in palette[
            ((x // 4) * 3 + (y // 3) * 5 + (x // 11)) % len(palette)
        ]
    )


def _write_synthetic_exact_render(path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba = _synthetic_rgba(LAYER_WIDTH, LAYER_HEIGHT)
    payload = _deterministic_png(LAYER_WIDTH, LAYER_HEIGHT, rgba)
    path.write_bytes(payload)
    return {
        "path": str(path),
        "width": LAYER_WIDTH,
        "height": LAYER_HEIGHT,
        "png_sha256": hashlib.sha256(payload).hexdigest(),
        "pixel_rgba_sha256": hashlib.sha256(rgba).hexdigest(),
        "provenance": SOURCE_PROVENANCE,
    }


def _fixture(png_path: Path, *, effect: str = "noise") -> dict[str, Any]:
    """Build one fixed, unrotated leaf rectangle for one exact effect."""

    contract = _effect_contract(effect)

    document = create_ui_document(
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        name="Synthetic Static Appearance UE QA",
    )
    document["document_id"] = "ui-static-appearance-synthetic-ue-qa"
    document["artboards"][0]["background"] = "#00000000"
    bounds = {
        "x": float(LAYER_X),
        "y": float(LAYER_Y),
        "width": float(LAYER_WIDTH),
        "height": float(LAYER_HEIGHT),
    }
    document["objects"] = [
        {
            "id": contract["layer_id"],
            "kind": "rectangle",
            "name": contract["layer_name"],
            "artboard_id": document["active_artboard_id"],
            "parent_id": "",
            "x": float(LAYER_X),
            "y": float(LAYER_Y),
            "width": float(LAYER_WIDTH),
            "height": float(LAYER_HEIGHT),
            "rotation": 0.0,
            "opacity": 1.0,
            "visible": True,
            "locked": False,
            "clip_content": False,
            "z_index": 0,
            "style": {
                "fill": "#243A5EFF",
                "fills": [
                    {
                        "type": "solid",
                        "visible": True,
                        "color": "#243A5EFF",
                        "opacity": 1.0,
                        "blend_mode": "normal",
                    }
                ],
                "stroke": "#00000000",
                "stroke_width": 0.0,
                "strokes": [],
                "blend_mode": "normal",
                "radius": 0.0,
                "corner_radii": {
                    "top_left": 0.0,
                    "top_right": 0.0,
                    "bottom_right": 0.0,
                    "bottom_left": 0.0,
                },
                "corner_smoothing": 0.0,
                "effects": [_effect_row(contract["effect"])],
            },
            "content": {
                "figma_node_id": contract["node_id"],
                "figma_type": "RECTANGLE",
                "boolean": {"enabled": False},
                "figma_exact_render": {
                    "png_path": str(png_path.expanduser().resolve()),
                    # This field is part of the accepted appearance contract;
                    # the provenance below makes clear that no Figma request ran.
                    "source": "figma_render_api",
                    "node_id": contract["node_id"],
                    "format": "png",
                    "scale": 1.0,
                    "source_bounds": dict(bounds),
                    "render_bounds": dict(bounds),
                    "provenance": {
                        "classification": SOURCE_PROVENANCE,
                        "actual_figma_request": False,
                    },
                },
            },
            "mask": {"enabled": False},
            "constraints": {
                "horizontal": "left",
                "vertical": "top",
                "pivot_x": 0.0,
                "pivot_y": 0.0,
            },
            "layout": {},
            "token_bindings": {},
            "accessibility": {},
        }
    ]
    return document


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _installed_plugin_binary_evidence(
    generation: Mapping[str, Any],
    *,
    expected_plugin_version: str | None = None,
) -> dict[str, Any]:
    """Prove that the QA project executed the just-built bundled DLLs."""

    plugin = generation.get("plugin")
    plugin = dict(plugin) if isinstance(plugin, Mapping) else {}
    bundled_root = Path(str(plugin.get("source_path") or ""))
    installed_root = Path(str(plugin.get("installed_path") or ""))
    rows: list[dict[str, Any]] = []
    for name in REQUIRED_PLUGIN_DLLS:
        bundled = bundled_root / "Binaries" / "Win64" / name
        installed = installed_root / "Binaries" / "Win64" / name
        bundled_hash = _sha256_file(bundled) if bundled.is_file() else ""
        installed_hash = _sha256_file(installed) if installed.is_file() else ""
        rows.append(
            {
                "name": name,
                "bundled_path": str(bundled),
                "installed_path": str(installed),
                "bundled_sha256": bundled_hash,
                "installed_sha256": installed_hash,
                "ok": bool(
                    bundled_hash
                    and installed_hash
                    and bundled_hash == installed_hash
                ),
            }
        )
    bundled_version = str(plugin.get("bundled_version") or "")
    installed_version = str(plugin.get("installed_version") or "")
    version_ok = bool(
        bundled_version == installed_version
        and (
            bundled_version == expected_plugin_version
            if expected_plugin_version
            else bundled_version in SUPPORTED_PLUGIN_VERSIONS
        )
    )
    return {
        "ok": bool(
            version_ok
            and len(rows) == len(REQUIRED_PLUGIN_DLLS)
            and all(row["ok"] for row in rows)
        ),
        "bundled_version": bundled_version,
        "installed_version": installed_version,
        "expected_plugin_version": str(expected_plugin_version or ""),
        "supported_plugin_versions": sorted(SUPPORTED_PLUGIN_VERSIONS),
        "version_ok": version_ok,
        "dlls": rows,
    }


def _payload(layer: Mapping[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(str(layer.get("PayloadJson") or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _package_root(package: Mapping[str, Any]) -> Path | None:
    document_path = Path(str(package.get("document_path") or ""))
    return document_path.expanduser().resolve().parent if document_path.is_file() else None


def _materialization_evidence(
    package: Mapping[str, Any],
    *,
    effect: str = "noise",
) -> dict[str, Any]:
    """Verify the package texture, hashes, bounds, and schema fail-closed."""

    contract = _effect_contract(effect)
    errors: list[str] = []
    document = package.get("document")
    document = dict(document) if isinstance(document, Mapping) else {}
    layers = [row for row in document.get("Layers", []) if isinstance(row, Mapping)]
    resources = [
        row for row in document.get("Resources", []) if isinstance(row, Mapping)
    ]
    artifacts = [
        row for row in package.get("static_bakes", []) if isinstance(row, Mapping)
    ]
    if package.get("ok") is not True:
        errors.append("package_failed")
    if document.get("SchemaVersion") != contract["schema_version"]:
        errors.append(f"schema_{contract['schema_version']}_required")
    if len(layers) != 1:
        errors.append("exactly_one_layer_required")
    if len(resources) != 1:
        errors.append("exactly_one_resource_required")
    if len(artifacts) != 1:
        errors.append("exactly_one_static_bake_required")

    layer = dict(layers[0]) if len(layers) == 1 else {}
    resource = dict(resources[0]) if len(resources) == 1 else {}
    artifact = dict(artifacts[0]) if len(artifacts) == 1 else {}
    payload = _payload(layer)
    bake = payload.get("static_appearance_bake")
    bake = dict(bake) if isinstance(bake, Mapping) else {}
    image_fill = layer.get("ImageFill")
    image_fill = dict(image_fill) if isinstance(image_fill, Mapping) else {}

    if (
        layer.get("Id") != contract["layer_id"]
        or layer.get("Disposition") != "Baked"
    ):
        errors.append("appearance_layer_not_materialized_baked")
    if layer.get("Kind") != "Image" or list(layer.get("BlockReasons") or []):
        errors.append("appearance_layer_typed_image_contract_invalid")
    if payload.get("painter_conversion") != contract["conversion"]:
        errors.append("appearance_conversion_invalid")
    if payload.get("umg_mapping") != contract["mapping"]:
        errors.append("appearance_mapping_invalid")
    if (
        bake.get("kind") != contract["kind"]
        or bake.get("status") != "materialized"
        or bake.get("available") is not True
    ):
        errors.append("appearance_materialization_record_invalid")
    if bake.get("integration_status") != contract["materialized_status"]:
        errors.append("appearance_materialization_status_invalid")
    if (
        artifact.get("schema") != contract["source_schema"]
        or artifact.get("kind") != contract["kind"]
        or artifact.get("intended_gate") != contract["gate"]
        or artifact.get("integration_status") != contract["artifact_status"]
        or artifact.get("umg_support_claimed") is not True
    ):
        errors.append("appearance_artifact_contract_invalid")
    source = bake.get("source")
    source = dict(source) if isinstance(source, Mapping) else {}
    source_effect = source.get("effect")
    source_effect = (
        dict(source_effect) if isinstance(source_effect, Mapping) else {}
    )
    if source.get("schema") != contract["source_schema"]:
        errors.append("appearance_source_schema_invalid")
    if source_effect.get("type") != contract["effect"]:
        errors.append("appearance_source_effect_invalid")
    if contract["effect"] == "texture" and (
        source.get("intended_gate") != contract["gate"]
        or bake.get("intended_gate") != contract["gate"]
    ):
        errors.append("texture_intended_gate_invalid")
    if bake.get("satisfied_gate") != contract["gate"]:
        errors.append("appearance_satisfied_gate_invalid")
    transition = bake.get("gate_transition")
    transition = dict(transition) if isinstance(transition, Mapping) else {}
    if transition.get("satisfied") != [contract["gate"]]:
        errors.append("appearance_gate_transition_invalid")
    source_canonical = json.dumps(
        source,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    effect_canonical = json.dumps(
        source_effect,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if (
        bake.get("source_canonical_json") != source_canonical
        or bake.get("source_hash")
        != hashlib.sha256(source_canonical.encode("utf-8")).hexdigest()
    ):
        errors.append("appearance_source_hash_invalid")
    if (
        bake.get("effect_canonical_json") != effect_canonical
        or bake.get("effect_hash")
        != hashlib.sha256(effect_canonical.encode("utf-8")).hexdigest()
    ):
        errors.append("appearance_effect_hash_invalid")

    expected_size = {"X": float(LAYER_WIDTH), "Y": float(LAYER_HEIGHT)}
    expected_position = {"X": float(LAYER_X), "Y": float(LAYER_Y)}
    if layer.get("Size") != expected_size or layer.get("Position") != expected_position:
        errors.append("appearance_layer_geometry_changed")
    canvas_slot = layer.get("CanvasSlot")
    canvas_slot = dict(canvas_slot) if isinstance(canvas_slot, Mapping) else {}
    offsets = canvas_slot.get("Offsets")
    offsets = dict(offsets) if isinstance(offsets, Mapping) else {}
    if (
        canvas_slot.get("AnchorMinimum") != {"X": 0.0, "Y": 0.0}
        or canvas_slot.get("AnchorMaximum") != {"X": 0.0, "Y": 0.0}
        or canvas_slot.get("Alignment") != {"X": 0.0, "Y": 0.0}
        or offsets
        != {
            "Left": float(LAYER_X),
            "Top": float(LAYER_Y),
            "Right": float(LAYER_WIDTH),
            "Bottom": float(LAYER_HEIGHT),
        }
    ):
        errors.append("appearance_canvas_slot_changed")

    asset_id = str(layer.get("AssetId") or "")
    content_hash = str(bake.get("content_hash") or "").casefold()
    pixel_hash = str(bake.get("pixel_rgba_sha256") or "").casefold()
    if (
        not asset_id
        or asset_id != f"texture_{content_hash}"
        or image_fill.get("AssetId") != asset_id
        or resource.get("Id") != asset_id
        or artifact.get("asset_id") != asset_id
    ):
        errors.append("appearance_asset_identity_mismatch")

    root = _package_root(package)
    source_text = str(resource.get("SourcePath") or "")
    texture_path = (root / source_text).resolve() if root and source_text else None
    texture_size: list[int] = []
    actual_content_hash = ""
    actual_pixel_hash = ""
    if texture_path is None or not texture_path.is_file():
        errors.append("packaged_texture_missing")
    else:
        actual_content_hash = _sha256_file(texture_path)
        try:
            with Image.open(texture_path) as source_image:
                texture = source_image.convert("RGBA")
                texture_size = [texture.width, texture.height]
                actual_pixel_hash = hashlib.sha256(texture.tobytes()).hexdigest()
        except (OSError, ValueError):
            errors.append("packaged_texture_invalid")
        if actual_content_hash != content_hash:
            errors.append("packaged_texture_content_hash_mismatch")
        if actual_pixel_hash != pixel_hash:
            errors.append("packaged_texture_pixel_hash_mismatch")
        if texture_size != [LAYER_WIDTH, LAYER_HEIGHT]:
            errors.append("packaged_texture_size_mismatch")
    if str(resource.get("ContentHash") or "").casefold() != content_hash:
        errors.append("resource_content_hash_mismatch")
    if source.get("logical_size") != {
        "width": float(LAYER_WIDTH),
        "height": float(LAYER_HEIGHT),
    } or source.get("pixel_size") != {
        "width": LAYER_WIDTH,
        "height": LAYER_HEIGHT,
    }:
        errors.append("appearance_source_size_mismatch")
    if source.get("pixel_rgba_sha256") != actual_pixel_hash:
        errors.append("appearance_source_pixel_hash_mismatch")
    if (package.get("preflight") or {}).get("counts") != {
        "Native": 0,
        "Material": 0,
        "Baked": 1,
        "Blocked": 0,
    }:
        errors.append("source_preflight_counts_invalid")
    if (package.get("packaged_preflight") or {}).get("counts") != {
        "Native": 0,
        "Material": 0,
        "Baked": 1,
        "Blocked": 0,
    }:
        errors.append("packaged_preflight_counts_invalid")

    return {
        "ok": not errors,
        "errors": sorted(set(errors)),
        "source_provenance": SOURCE_PROVENANCE,
        "not_a_figma_visual_golden": True,
        "effect": contract["effect"],
        "expected_contract": {
            "schema_version": contract["schema_version"],
            "kind": contract["kind"],
            "source_schema": contract["source_schema"],
            "gate": contract["gate"],
            "conversion": contract["conversion"],
            "mapping": contract["mapping"],
            "artifact_status": contract["artifact_status"],
            "materialized_status": contract["materialized_status"],
        },
        "schema_version": document.get("SchemaVersion"),
        "layer_id": str(layer.get("Id") or ""),
        "asset_id": asset_id,
        "content_hash": content_hash,
        "actual_content_hash": actual_content_hash,
        "pixel_rgba_sha256": pixel_hash,
        "actual_pixel_rgba_sha256": actual_pixel_hash,
        "texture_size": texture_size,
        "expected_texture_size": [LAYER_WIDTH, LAYER_HEIGHT],
        "texture_path": str(texture_path) if texture_path else "",
        "expected_capture_bounds": [
            LAYER_X,
            LAYER_Y,
            LAYER_X + LAYER_WIDTH - 1,
            LAYER_Y + LAYER_HEIGHT - 1,
        ],
    }


def _alpha_bounds(image: Image.Image, *, threshold: int = 127) -> list[int]:
    alpha = image.getchannel("A")
    points = [
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if alpha.getpixel((x, y)) > threshold
    ]
    if not points:
        return []
    return [
        min(x for x, _y in points),
        min(y for _x, y in points),
        max(x for x, _y in points),
        max(y for _x, y in points),
    ]


def _capture_evidence(
    capture_path: Path,
    package: Mapping[str, Any],
    *,
    effect: str = "noise",
) -> dict[str, Any]:
    """Compare UE output to the packaged texture at the authored coordinates."""

    contract = _effect_contract(effect)
    errors: list[str] = []
    materialization = _materialization_evidence(
        package,
        effect=contract["effect"],
    )
    texture_path = Path(str(materialization.get("texture_path") or ""))
    try:
        with Image.open(capture_path) as source:
            capture = source.convert("RGBA")
        with Image.open(texture_path) as source:
            texture = source.convert("RGBA")
    except (OSError, ValueError):
        return {
            "ok": False,
            "errors": ["capture_or_texture_unreadable"],
            "source_provenance": SOURCE_PROVENANCE,
            "not_a_figma_visual_golden": True,
            "effect": contract["effect"],
        }

    if capture.size != (CANVAS_WIDTH, CANVAS_HEIGHT):
        errors.append("capture_size_mismatch")
    expected_bounds = [
        LAYER_X,
        LAYER_Y,
        LAYER_X + LAYER_WIDTH - 1,
        LAYER_Y + LAYER_HEIGHT - 1,
    ]
    alpha_bounds = _alpha_bounds(capture)
    if alpha_bounds != expected_bounds:
        errors.append("capture_appearance_bounds_mismatch")

    crop = capture.crop(
        (
            LAYER_X,
            LAYER_Y,
            LAYER_X + LAYER_WIDTH,
            LAYER_Y + LAYER_HEIGHT,
        )
    )
    expected_bytes = texture.tobytes()
    actual_bytes = crop.tobytes()
    expected_pixel_hash = hashlib.sha256(expected_bytes).hexdigest()
    actual_pixel_hash = hashlib.sha256(actual_bytes).hexdigest()
    exact_pixel_hash = actual_pixel_hash == expected_pixel_hash
    differences = [
        abs(actual - expected)
        for actual, expected in zip(actual_bytes, expected_bytes, strict=True)
    ]
    rgb_differences = [
        value for index, value in enumerate(differences) if index % 4 != 3
    ]
    alpha_differences = [
        value for index, value in enumerate(differences) if index % 4 == 3
    ]
    mean_rgb_error = (
        sum(rgb_differences) / len(rgb_differences) if rgb_differences else 255.0
    )
    rgb_within_four_fraction = (
        sum(value <= 4 for value in rgb_differences) / len(rgb_differences)
        if rgb_differences
        else 0.0
    )
    alpha_exact_fraction = (
        sum(value == 0 for value in alpha_differences) / len(alpha_differences)
        if alpha_differences
        else 0.0
    )
    if mean_rgb_error > 2.0 or rgb_within_four_fraction < 0.98:
        errors.append("capture_texture_rgb_mismatch")
    if alpha_exact_fraction < 0.995:
        errors.append("capture_texture_alpha_mismatch")
    if contract["effect"] == "texture" and not exact_pixel_hash:
        errors.append("capture_texture_pixel_hash_mismatch")

    sample_points = (
        (2, 2),
        (LAYER_WIDTH // 2, LAYER_HEIGHT // 2),
        (LAYER_WIDTH - 3, LAYER_HEIGHT - 3),
    )
    samples: list[dict[str, Any]] = []
    for local_x, local_y in sample_points:
        expected = list(texture.getpixel((local_x, local_y)))
        actual = list(capture.getpixel((LAYER_X + local_x, LAYER_Y + local_y)))
        maximum_error = max(
            abs(actual[index] - expected[index]) for index in range(4)
        )
        samples.append(
            {
                "local": [local_x, local_y],
                "capture": [LAYER_X + local_x, LAYER_Y + local_y],
                "expected_rgba": expected,
                "actual_rgba": actual,
                "maximum_channel_error": maximum_error,
            }
        )
    if any(row["maximum_channel_error"] > 4 for row in samples):
        errors.append("capture_sample_pixel_mismatch")

    outside_alpha_max = max(
        (
            capture.getpixel((x, y))[3]
            for y in range(capture.height)
            for x in range(capture.width)
            if not (
                LAYER_X <= x < LAYER_X + LAYER_WIDTH
                and LAYER_Y <= y < LAYER_Y + LAYER_HEIGHT
            )
        ),
        default=0,
    )
    if outside_alpha_max > 4:
        errors.append("capture_outside_alpha_nonzero")

    return {
        "ok": not errors and bool(materialization.get("ok")),
        "errors": sorted(set([*errors, *materialization.get("errors", [])])),
        "source_provenance": SOURCE_PROVENANCE,
        "not_a_figma_visual_golden": True,
        "effect": contract["effect"],
        "capture_size": list(capture.size),
        "required_capture_size": [CANVAS_WIDTH, CANVAS_HEIGHT],
        "alpha_bounds": alpha_bounds,
        "expected_alpha_bounds": expected_bounds,
        "mean_rgb_error": mean_rgb_error,
        "rgb_within_four_fraction": rgb_within_four_fraction,
        "alpha_exact_fraction": alpha_exact_fraction,
        "expected_crop_pixel_rgba_sha256": expected_pixel_hash,
        "actual_crop_pixel_rgba_sha256": actual_pixel_hash,
        "exact_crop_pixel_hash": exact_pixel_hash,
        "outside_alpha_max": outside_alpha_max,
        "samples": samples,
    }


def _reference_capture(
    package: Mapping[str, Any],
    *,
    effect: str = "noise",
) -> Image.Image:
    """Create a Python reference used only to unit-test the fail-closed gate."""

    evidence = _materialization_evidence(package, effect=effect)
    texture_path = Path(str(evidence.get("texture_path") or ""))
    with Image.open(texture_path) as source:
        texture = source.convert("RGBA")
    result = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    result.alpha_composite(texture, (LAYER_X, LAYER_Y))
    return result


def run_qa(
    workspace: Path,
    *,
    timeout_seconds: int,
    effect: str = "noise",
    expected_plugin_version: str = DEFAULT_EXPECTED_PLUGIN_VERSION,
) -> dict[str, Any]:
    contract = _effect_contract(effect)
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    source = _write_synthetic_exact_render(
        workspace / "fixture" / contract["fixture_filename"]
    )
    project = _ensure_project(workspace)
    generation = generate_painter_umg(
        _fixture(Path(source["path"]), effect=contract["effect"]),
        project_path=project,
        # Keep the final supported-contract artifacts separate from the
        # intentionally fail-closed pre-support proof that may share a
        # workspace. Identical supported reruns still exercise writer reuse.
        output_dir=workspace / contract["package_directory"],
        timeout_seconds=timeout_seconds,
    )
    package = generation.get("package")
    package = package if isinstance(package, Mapping) else {}
    materialization = _materialization_evidence(
        package,
        effect=contract["effect"],
    )
    asset_path = str(generation.get("generated_asset_path") or "")
    texture_paths = [
        str(value)
        for value in generation.get("imported_asset_paths", [])
        if str(value)
    ]
    expected_widget_classes = {contract["layer_id"]: "Image"}
    reopen = (
        _reopen_generated_asset(
            project,
            asset_path,
            texture_paths=texture_paths,
            texture_widget_names=[contract["layer_id"]],
            expected_widget_classes=expected_widget_classes,
            timeout_seconds=timeout_seconds,
        )
        if generation.get("ok") and asset_path and len(texture_paths) == 1
        else {"ok": False, "errors": ["generation_failed_before_reopen"]}
    )
    capture_path = workspace / contract["capture_filename"]
    render = (
        _render_generated_asset(
            project,
            asset_path,
            capture_path,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            timeout_seconds=timeout_seconds,
        )
        if reopen.get("ok")
        else {"ok": False, "message": "reopen_failed_before_render"}
    )
    pixels = (
        _capture_evidence(capture_path, package, effect=contract["effect"])
        if render.get("ok") and capture_path.is_file()
        else {"ok": False, "errors": ["render_failed_before_pixel_gate"]}
    )
    installed_plugin_binaries = _installed_plugin_binary_evidence(
        generation,
        expected_plugin_version=expected_plugin_version,
    )
    generated_classes = generation.get("generated_widget_classes") or {}
    generated_class_ok = (
        str(generated_classes.get(contract["layer_id"]) or "") == "Image"
    )
    reopened_textures = list(reopen.get("textures") or [])
    reopen_texture_ok = bool(
        len(reopened_textures) == 1
        and reopened_textures[0].get("ok")
        and reopened_textures[0].get("class") == "Texture2D"
        and reopened_textures[0].get("widget_name") == contract["layer_id"]
    )
    return {
        "schema": QA_SCHEMA,
        "ok": bool(
            generation.get("ok")
            and materialization.get("ok")
            and reopen.get("ok")
            and reopen_texture_ok
            and render.get("ok")
            and pixels.get("ok")
            and installed_plugin_binaries.get("ok")
            and generated_class_ok
            and int(generation.get("generated_widget_count") or 0) == 1
            and len(texture_paths) == 1
        ),
        "source_provenance": SOURCE_PROVENANCE,
        "not_a_figma_visual_golden": True,
        "effect": contract["effect"],
        "expected_contract": {
            "schema_version": contract["schema_version"],
            "kind": contract["kind"],
            "source_schema": contract["source_schema"],
            "gate": contract["gate"],
            "conversion": contract["conversion"],
            "mapping": contract["mapping"],
            "artifact_status": contract["artifact_status"],
            "materialized_status": contract["materialized_status"],
            "plugin_version": expected_plugin_version,
        },
        "source_fixture": source,
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "project_path": str(project),
        "generation": generation,
        "materialization_evidence": materialization,
        "reopen": reopen,
        "render": render,
        "pixel_evidence": pixels,
        "installed_plugin_binary_evidence": installed_plugin_binaries,
        "widget_class_evidence": {
            "expected": expected_widget_classes,
            "generated": generated_classes,
            "generated_exact": generated_class_ok,
            "reopened_texture_reference_exact": reopen_texture_ok,
            "compile_proof": "generation_success_then_generated_class_reopen",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--effect", choices=("noise", "texture"), default="noise")
    parser.add_argument(
        "--expected-plugin-version",
        default=DEFAULT_EXPECTED_PLUGIN_VERSION,
    )
    args = parser.parse_args()
    report = run_qa(
        args.workspace,
        timeout_seconds=args.timeout,
        effect=args.effect,
        expected_plugin_version=args.expected_plugin_version,
    )
    report_path = args.workspace.expanduser().resolve() / "qa_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

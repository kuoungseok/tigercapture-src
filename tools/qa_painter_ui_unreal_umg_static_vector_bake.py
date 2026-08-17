"""Generate, reopen, and FWidgetRenderer-capture one package-baked vector."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_ui_document import add_ui_object, create_ui_document
from app.painter_ui_constraints import capture_ui_constraints
from app.painter_ui_umg_adapter import generate_painter_umg
from app.unreal_umg_workflow import DEFAULT_UNREAL_ENGINE_ROOT
from tools.qa_painter_ui_unreal_umg import (
    _ensure_project,
    _render_generated_asset,
    _reopen_generated_asset,
)


def _fixture() -> dict[str, Any]:
    document = create_ui_document(192, 128, name="Static Vector Bake UE QA")
    document["document_id"] = "ui-static-vector-bake-ue-qa"
    document["artboards"][0]["background"] = "#101820FF"
    document, primary = add_ui_object(
        document,
        kind="path",
        name="Exact Triangle",
        x=30,
        y=20,
        width=40,
        height=30,
        content={
            "figma_type": "VECTOR",
            "vector_fill_geometry": [
                {"path": "M 0 30 L 20 0 L 40 30 Z", "winding_rule": "nonzero"}
            ],
            "vector_paths": ["M 0 30 L 20 0 L 40 30 Z"],
        },
        style={
            "fill": "#20D878FF",
            "fills": [
                {
                    "type": "solid",
                    "visible": True,
                    "color": "#20D878FF",
                    "opacity": 0.5,
                    "blend_mode": "normal",
                }
            ],
            "stroke": "#00000000",
            "stroke_width": 0.0,
            "strokes": [],
            "blend_mode": "normal",
        },
    )
    primary_row = next(
        row for row in document["objects"] if row["id"] == primary["id"]
    )
    primary_row["constraints"] = capture_ui_constraints(
        primary_row,
        {"x": 0.0, "y": 0.0, "width": 192.0, "height": 128.0},
        {
            "horizontal": "center",
            "vertical": "center",
            "pivot_x": 0.2,
            "pivot_y": 0.8,
        },
    )
    document, rotated = add_ui_object(
        document,
        kind="path",
        name="Rotated EvenOdd Ring",
        x=122,
        y=54,
        width=32,
        height=32,
        content={
            "figma_type": "VECTOR",
            "vector_fill_geometry": [
                {
                    "path": (
                        "M 0 0 H 32 V 32 H 0 Z "
                        "M 8 8 H 24 V 24 H 8 Z"
                    ),
                    "winding_rule": "evenodd",
                }
            ],
            "vector_paths": [
                "M 0 0 H 32 V 32 H 0 Z M 8 8 H 24 V 24 H 8 Z"
            ],
        },
        style={
            "fill": "#F97316FF",
            "fills": [
                {
                    "type": "solid",
                    "visible": True,
                    "color": "#F97316FF",
                    "opacity": 1.0,
                    "blend_mode": "normal",
                }
            ],
            "stroke": "#00000000",
            "stroke_width": 0.0,
            "strokes": [],
            "blend_mode": "normal",
        },
    )
    rotated_row = next(
        row for row in document["objects"] if row["id"] == rotated["id"]
    )
    rotated_row["rotation"] = 25.0
    rotated_row["constraints"] = capture_ui_constraints(
        rotated_row,
        {"x": 0.0, "y": 0.0, "width": 192.0, "height": 128.0},
        {
            "horizontal": "right",
            "vertical": "bottom",
            "pivot_x": 0.3,
            "pivot_y": 0.7,
        },
    )
    return document


COLOR_CONTRACT = {
    "color_space": "sRGB",
    "alpha_mode": "straight",
    "channel_depth_bits": 8,
    "png_srgb_rendering_intent": 0,
}


def _srgb_to_linear(value: float) -> float:
    value = max(0.0, min(1.0, float(value)))
    return value / 12.92 if value <= 0.04045 else pow(
        (value + 0.055) / 1.055,
        2.4,
    )


def _linear_to_srgb(value: float) -> float:
    value = max(0.0, min(1.0, float(value)))
    return 12.92 * value if value <= 0.0031308 else (
        1.055 * pow(value, 1.0 / 2.4) - 0.055
    )


def _linear_premultiplied_srgb_byte(value: int, alpha: int) -> int:
    """Encode an sRGB source channel after linear-light alpha multiply."""

    linear = _srgb_to_linear(float(value) / 255.0) * (
        max(0, min(255, int(alpha))) / 255.0
    )
    return max(0, min(255, int(round(_linear_to_srgb(linear) * 255.0))))


def _world_sample(layer: dict[str, Any], local_x: float, local_y: float) -> tuple[int, int]:
    size = layer["Size"]
    pivot = layer["RenderTransformPivot"]
    position = layer["Position"]
    pivot_x = float(pivot["X"]) * float(size["X"])
    pivot_y = float(pivot["Y"]) * float(size["Y"])
    radians = math.radians(float(layer["RotationDegrees"]))
    delta_x = float(local_x) - pivot_x
    delta_y = float(local_y) - pivot_y
    return (
        int(round(float(position["X"]) + math.cos(radians) * delta_x - math.sin(radians) * delta_y)),
        int(round(float(position["Y"]) + math.sin(radians) * delta_x + math.cos(radians) * delta_y)),
    )


def _world_to_local(
    layer: dict[str, Any],
    world_x: float,
    world_y: float,
) -> tuple[float, float]:
    size = layer["Size"]
    pivot = layer["RenderTransformPivot"]
    position = layer["Position"]
    pivot_x = float(pivot["X"]) * float(size["X"])
    pivot_y = float(pivot["Y"]) * float(size["Y"])
    radians = math.radians(float(layer["RotationDegrees"]))
    delta_x = float(world_x) - float(position["X"])
    delta_y = float(world_y) - float(position["Y"])
    return (
        pivot_x + math.cos(radians) * delta_x + math.sin(radians) * delta_y,
        pivot_y - math.sin(radians) * delta_x + math.cos(radians) * delta_y,
    )


def _local_to_world(
    layer: dict[str, Any],
    local_x: float,
    local_y: float,
) -> tuple[float, float]:
    size = layer["Size"]
    pivot = layer["RenderTransformPivot"]
    position = layer["Position"]
    pivot_x = float(pivot["X"]) * float(size["X"])
    pivot_y = float(pivot["Y"]) * float(size["Y"])
    radians = math.radians(float(layer["RotationDegrees"]))
    delta_x = float(local_x) - pivot_x
    delta_y = float(local_y) - pivot_y
    return (
        float(position["X"])
        + math.cos(radians) * delta_x
        - math.sin(radians) * delta_y,
        float(position["Y"])
        + math.sin(radians) * delta_x
        + math.cos(radians) * delta_y,
    )


def _ue_round_to_float(value: float) -> float:
    """Mirror FMath::RoundToFloat, including its half-up behavior."""

    return float(math.floor(float(value) + 0.5))


def _slate_pixel_snapped_box_projection(
    layer: dict[str, Any],
) -> dict[str, Any]:
    """Describe the default SImage/MakeBox vertex and UV projection.

    SImage paints a box without NoPixelSnapping.  Slate therefore transforms
    and independently rounds all four box vertices before submitting the two
    indexed triangles.  A rotated quad can stop being a perfect parallelogram
    after that rounding, so one inverse rotation is not an equivalent alpha
    reference; UVs must be interpolated per submitted triangle.
    """

    width = float(layer["Size"]["X"])
    height = float(layer["Size"]["Y"])
    local_vertices = [
        [0.0, 0.0],
        [width, 0.0],
        [0.0, height],
        [width, height],
    ]
    exact_world_vertices = [
        list(_local_to_world(layer, local_x, local_y))
        for local_x, local_y in local_vertices
    ]
    snapped_world_vertices = [
        [_ue_round_to_float(x), _ue_round_to_float(y)]
        for x, y in exact_world_vertices
    ]
    return {
        "enabled": True,
        "source_contract": (
            "SImage MakeBox default pixel snapping; each transformed vertex "
            "uses FMath::RoundToFloat"
        ),
        "rounding": "floor(value + 0.5)",
        "local_vertices": local_vertices,
        "exact_world_vertices": exact_world_vertices,
        "snapped_world_vertices": snapped_world_vertices,
        "uv_vertices": [
            [0.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
        ],
        "triangle_indices": [[0, 1, 2], [2, 1, 3]],
    }


def _barycentric_coordinates(
    point: tuple[float, float],
    vertex_a: tuple[float, float] | list[float],
    vertex_b: tuple[float, float] | list[float],
    vertex_c: tuple[float, float] | list[float],
) -> tuple[float, float, float] | None:
    point_x, point_y = point
    a_x, a_y = vertex_a
    b_x, b_y = vertex_b
    c_x, c_y = vertex_c
    determinant = (
        (b_y - c_y) * (a_x - c_x)
        + (c_x - b_x) * (a_y - c_y)
    )
    if abs(determinant) <= 1e-12:
        return None
    weight_a = (
        (b_y - c_y) * (point_x - c_x)
        + (c_x - b_x) * (point_y - c_y)
    ) / determinant
    weight_b = (
        (c_y - a_y) * (point_x - c_x)
        + (a_x - c_x) * (point_y - c_y)
    ) / determinant
    weight_c = 1.0 - weight_a - weight_b
    epsilon = 1e-9
    if (
        weight_a < -epsilon
        or weight_b < -epsilon
        or weight_c < -epsilon
    ):
        return None
    return weight_a, weight_b, weight_c


def _slate_texture_uv_at_point(
    projection: dict[str, Any],
    point: tuple[float, float],
) -> tuple[float, float] | None:
    vertices = projection["snapped_world_vertices"]
    uv_vertices = projection["uv_vertices"]
    for index_a, index_b, index_c in projection["triangle_indices"]:
        weights = _barycentric_coordinates(
            point,
            vertices[index_a],
            vertices[index_b],
            vertices[index_c],
        )
        if weights is None:
            continue
        weight_a, weight_b, weight_c = weights
        return (
            weight_a * uv_vertices[index_a][0]
            + weight_b * uv_vertices[index_b][0]
            + weight_c * uv_vertices[index_c][0],
            weight_a * uv_vertices[index_a][1]
            + weight_b * uv_vertices[index_b][1]
            + weight_c * uv_vertices[index_c][1],
        )
    return None


def _bilinear_alpha(alpha: Image.Image, local_x: float, local_y: float) -> int:
    # Local coordinates use pixel edges (0..width/height), while Pillow pixel
    # samples live at half-integer centers.
    sample_x = local_x - 0.5
    sample_y = local_y - 0.5
    left = math.floor(sample_x)
    top = math.floor(sample_y)
    fraction_x = sample_x - left
    fraction_y = sample_y - top
    pixels = alpha.load()

    def read(x: int, y: int) -> int:
        if 0 <= x < alpha.width and 0 <= y < alpha.height:
            return int(pixels[x, y])
        return 0

    value = (
        read(left, top) * (1.0 - fraction_x) * (1.0 - fraction_y)
        + read(left + 1, top) * fraction_x * (1.0 - fraction_y)
        + read(left, top + 1) * (1.0 - fraction_x) * fraction_y
        + read(left + 1, top + 1) * fraction_x * fraction_y
    )
    return max(0, min(255, int(round(value))))


def _transformed_alpha_frame(
    layer: dict[str, Any],
    bake: Image.Image,
    frame_size: tuple[int, int],
) -> Image.Image:
    alpha = bake.getchannel("A")
    projection = _slate_pixel_snapped_box_projection(layer)
    frame = Image.new("L", frame_size, 0)
    values: list[int] = []
    for y in range(frame_size[1]):
        for x in range(frame_size[0]):
            value = 0
            texture_uv = _slate_texture_uv_at_point(
                projection,
                (x + 0.5, y + 0.5),
            )
            if texture_uv is not None:
                texture_u, texture_v = texture_uv
                value = _bilinear_alpha(
                    alpha,
                    texture_u * alpha.width,
                    texture_v * alpha.height,
                )
            values.append(value)
    frame.putdata(values)
    return frame


def _bilinear_srgb_texture_sample(
    source: Image.Image,
    texture_u: float,
    texture_v: float,
) -> tuple[float, float, float, float]:
    """Mirror a bilinear sample from an sRGB RGBA texture.

    Hardware sRGB sampling decodes each RGB texel to linear before filtering.
    Alpha stays linear and is filtered independently.  This distinction is
    visible where a colored texel is filtered with transparent black padding.
    """

    sample_x = float(texture_u) * source.width - 0.5
    sample_y = float(texture_v) * source.height - 0.5
    left = math.floor(sample_x)
    top = math.floor(sample_y)
    fraction_x = sample_x - left
    fraction_y = sample_y - top
    pixels = source.load()
    taps = (
        (left, top, (1.0 - fraction_x) * (1.0 - fraction_y)),
        (left + 1, top, fraction_x * (1.0 - fraction_y)),
        (left, top + 1, (1.0 - fraction_x) * fraction_y),
        (left + 1, top + 1, fraction_x * fraction_y),
    )
    sampled = [0.0, 0.0, 0.0, 0.0]
    for x, y, weight in taps:
        clamped_x = max(0, min(source.width - 1, x))
        clamped_y = max(0, min(source.height - 1, y))
        rgba = pixels[clamped_x, clamped_y]
        for channel in range(3):
            sampled[channel] += weight * _srgb_to_linear(
                float(rgba[channel]) / 255.0
            )
        sampled[3] += weight * float(rgba[3]) / 255.0
    return sampled[0], sampled[1], sampled[2], sampled[3]


def _slate_sample_over_transparent_rgba(
    sampled_linear_rgba: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    """Apply Slate's straight-alpha blend into a clear sRGB target."""

    red, green, blue, alpha = sampled_linear_rgba
    encoded_rgb = [
        max(
            0,
            min(
                255,
                int(round(_linear_to_srgb(channel * alpha) * 255.0)),
            ),
        )
        for channel in (red, green, blue)
    ]
    alpha_byte = max(0, min(255, int(round(alpha * 255.0))))
    return encoded_rgb[0], encoded_rgb[1], encoded_rgb[2], alpha_byte


def _slate_sampled_rgba_frame(
    layer: dict[str, Any],
    bake: Image.Image,
    frame_size: tuple[int, int],
) -> Image.Image:
    """Build the per-layer GPU color result over a transparent sRGB target."""

    source = bake.convert("RGBA")
    projection = _slate_pixel_snapped_box_projection(layer)
    values: list[tuple[int, int, int, int]] = []
    for y in range(frame_size[1]):
        for x in range(frame_size[0]):
            texture_uv = _slate_texture_uv_at_point(
                projection,
                (x + 0.5, y + 0.5),
            )
            if texture_uv is None:
                values.append((0, 0, 0, 0))
                continue
            values.append(
                _slate_sample_over_transparent_rgba(
                    _bilinear_srgb_texture_sample(source, *texture_uv)
                )
            )
    frame = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    frame.putdata(values)
    return frame


def _mask_stats(mask: list[bool], size: tuple[int, int]) -> dict[str, Any]:
    points = [
        (index % size[0], index // size[0])
        for index, occupied in enumerate(mask)
        if occupied
    ]
    if not points:
        return {"occupancy": 0, "bbox": [], "centroid": []}
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    count = len(points)
    return {
        "occupancy": count,
        "bbox": [min(xs), min(ys), max(xs) + 1, max(ys) + 1],
        "centroid": [
            sum(value + 0.5 for value in xs) / count,
            sum(value + 0.5 for value in ys) / count,
        ],
    }


def _mask_comparison(
    expected_alpha: Image.Image,
    actual_alpha: Image.Image,
    *,
    threshold: int = 128,
) -> dict[str, Any]:
    expected_values = expected_alpha.tobytes()
    actual_values = actual_alpha.tobytes()
    expected_mask = [value >= threshold for value in expected_values]
    actual_mask = [value >= threshold for value in actual_values]
    expected_stats = _mask_stats(expected_mask, expected_alpha.size)
    actual_stats = _mask_stats(actual_mask, actual_alpha.size)
    intersection = sum(
        expected and actual
        for expected, actual in zip(expected_mask, actual_mask, strict=True)
    )
    union = sum(
        expected or actual
        for expected, actual in zip(expected_mask, actual_mask, strict=True)
    )
    expected_count = int(expected_stats["occupancy"])
    actual_count = int(actual_stats["occupancy"])
    area_error = (
        abs(actual_count - expected_count) / expected_count
        if expected_count
        else 1.0
    )
    if expected_stats["centroid"] and actual_stats["centroid"]:
        centroid_distance = math.hypot(
            float(actual_stats["centroid"][0])
            - float(expected_stats["centroid"][0]),
            float(actual_stats["centroid"][1])
            - float(expected_stats["centroid"][1]),
        )
    else:
        centroid_distance = float("inf")
    if expected_stats["bbox"] and actual_stats["bbox"]:
        bbox_delta = [
            abs(int(actual) - int(expected))
            for actual, expected in zip(
                actual_stats["bbox"],
                expected_stats["bbox"],
                strict=True,
            )
        ]
    else:
        bbox_delta = [999, 999, 999, 999]
    iou = intersection / union if union else 0.0
    return {
        "ok": bool(
            expected_count > 0
            and iou >= 0.98
            and area_error <= 0.02
            and centroid_distance <= 0.5
            and max(bbox_delta) <= 1
        ),
        "threshold": threshold,
        "expected": expected_stats,
        "actual": actual_stats,
        "intersection": intersection,
        "union": union,
        "iou": iou,
        "required_iou": 0.98,
        "area_relative_error": area_error,
        "maximum_area_relative_error": 0.02,
        "centroid_distance_pixels": centroid_distance,
        "maximum_centroid_distance_pixels": 0.5,
        "bbox_edge_abs_delta": bbox_delta,
        "maximum_bbox_edge_abs_delta": 1,
    }


def _png_chunk_evidence(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    chunks: list[str] = []
    srgb_intents: list[int] = []
    offset = 8
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        while offset + 12 <= len(data):
            length = int.from_bytes(data[offset : offset + 4], "big")
            name = data[offset + 4 : offset + 8]
            payload_start = offset + 8
            payload_end = payload_start + length
            if payload_end + 4 > len(data):
                break
            decoded = name.decode("ascii", errors="replace")
            chunks.append(decoded)
            if name == b"sRGB" and length == 1:
                srgb_intents.append(int(data[payload_start]))
            offset = payload_end + 4
            if name == b"IEND":
                break
    return {
        "ok": chunks.count("sRGB") == 1 and srgb_intents == [0],
        "chunks": chunks,
        "srgb_chunk_count": chunks.count("sRGB"),
        "srgb_rendering_intents": srgb_intents,
        "required_srgb_rendering_intent": 0,
    }


def _artifact_color_contract(
    artifact: dict[str, Any],
    bake: Image.Image,
) -> dict[str, Any]:
    manifest_path = Path(str(artifact["manifest_path"]))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_contract = (manifest.get("source") or {}).get("color_contract")
    manifest_contract = manifest.get("color_contract")
    png_chunks = _png_chunk_evidence(Path(str(artifact["png_path"])))
    rgba = bake.tobytes()
    maximum_alpha = max(rgba[3::4], default=0)
    plateau = Counter(
        tuple(rgba[offset : offset + 3])
        for offset in range(0, len(rgba), 4)
        if rgba[offset + 3] == maximum_alpha
    )
    source_rgb = list(plateau.most_common(1)[0][0]) if plateau else []
    return {
        "ok": bool(
            source_contract == COLOR_CONTRACT
            and manifest_contract == COLOR_CONTRACT
            and png_chunks["ok"]
            and len(source_rgb) == 3
            and maximum_alpha > 0
        ),
        "required": dict(COLOR_CONTRACT),
        "source": source_contract,
        "manifest": manifest_contract,
        "png": png_chunks,
        "source_plateau_rgb": source_rgb,
        "source_maximum_alpha": maximum_alpha,
        "source_plateau_pixel_count": sum(plateau.values()),
    }


def _rgb_contract_metrics(
    actual: Image.Image,
    expected_alpha: Image.Image,
    *,
    source_rgb: list[int],
    source_maximum_alpha: int,
    gpu_color_reference: Image.Image | None = None,
) -> dict[str, Any]:
    actual_rgba = actual.tobytes()
    expected_values = expected_alpha.tobytes()
    gpu_reference_rgba = (
        gpu_color_reference.convert("RGBA").tobytes()
        if gpu_color_reference is not None
        else None
    )
    if gpu_color_reference is not None and gpu_color_reference.size != actual.size:
        raise ValueError("GPU color reference must match the actual image size")
    plateau_floor = max(1, int(source_maximum_alpha) - 1)
    plateau_pixel_count = 0
    plateau_alpha_error_count = 0
    plateau_rgb_error_count = 0
    visible_rgb_error_count = 0
    compared_visible_pixel_count = 0
    channel_max_error = [0, 0, 0]
    for index, expected_alpha_byte in enumerate(expected_values):
        offset = index * 4
        actual_alpha = int(actual_rgba[offset + 3])
        if expected_alpha_byte >= plateau_floor:
            plateau_pixel_count += 1
            if abs(actual_alpha - expected_alpha_byte) > 2:
                plateau_alpha_error_count += 1
            expected_rgb = (
                source_rgb
                if expected_alpha_byte >= 254
                else [
                    _linear_premultiplied_srgb_byte(value, actual_alpha)
                    for value in source_rgb
                ]
            )
            errors = [
                abs(int(actual_rgba[offset + channel]) - expected_rgb[channel])
                for channel in range(3)
            ]
            if any(error > 2 for error in errors):
                plateau_rgb_error_count += 1
        # Every pixel that is visibly covered in both the deterministic
        # inverse-transform reference and the Unreal capture participates in
        # the RGB contract.  Keeping the cutoff at one (instead of hiding the
        # antialiased fringe behind a larger threshold) catches texture or
        # render-target gamma regressions at the vector boundary as well as on
        # the solid plateau.
        if expected_alpha_byte > 0 and actual_alpha > 0:
            compared_visible_pixel_count += 1
            if gpu_reference_rgba is not None:
                expected_rgb = list(gpu_reference_rgba[offset : offset + 3])
            else:
                expected_rgb = (
                    source_rgb
                    if actual_alpha >= 254
                    else [
                        _linear_premultiplied_srgb_byte(value, actual_alpha)
                        for value in source_rgb
                    ]
                )
            errors = [
                abs(int(actual_rgba[offset + channel]) - expected_rgb[channel])
                for channel in range(3)
            ]
            for channel, error in enumerate(errors):
                channel_max_error[channel] = max(channel_max_error[channel], error)
            if any(error > 2 for error in errors):
                visible_rgb_error_count += 1
    return {
        "ok": bool(
            plateau_pixel_count > 100
            and plateau_alpha_error_count == 0
            and plateau_rgb_error_count == 0
            and compared_visible_pixel_count > 100
            and visible_rgb_error_count == 0
        ),
        "source_straight_alpha_srgb": source_rgb,
        "source_maximum_alpha": source_maximum_alpha,
        "plateau_pixel_count": plateau_pixel_count,
        "plateau_alpha_error_pixel_count": plateau_alpha_error_count,
        "plateau_rgb_error_pixel_count": plateau_rgb_error_count,
        "compared_visible_pixel_count": compared_visible_pixel_count,
        "visible_rgb_error_pixel_count": visible_rgb_error_count,
        "rgb_channel_abs_error_max": channel_max_error,
        "rgb_abs_error_threshold": 2,
        "opaque_expected_transform": "PNG straight-alpha sRGB source bytes",
        "translucent_expected_transform": (
            "linear_to_srgb(bilinear(srgb_to_linear(PNG RGB))*"
            "bilinear(PNG alpha))"
        ),
        "texture_filter_color_space": "decode each sRGB texel before bilinear",
        "blend_contract": (
            "Slate straight-alpha SourceAlpha/InverseSourceAlpha over "
            "transparent sRGB target"
        ),
    }


def _reference_capture(package: dict[str, Any]) -> Image.Image:
    """Build a deterministic contract reference used by adversarial tests."""

    frame_size = (192, 128)
    frame = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    layers = {str(row["Id"]): row for row in package["document"]["Layers"]}
    for artifact in package["static_bakes"]:
        layer = layers[str(artifact["object_id"])]
        with Image.open(Path(str(artifact["png_path"]))) as source:
            bake = source.convert("RGBA")
        layer_frame = _slate_sampled_rgba_frame(layer, bake, frame_size)
        frame = Image.alpha_composite(frame, layer_frame)
    return frame


def _image_evidence(
    capture_path: Path,
    package: dict[str, Any],
) -> dict[str, Any]:
    with Image.open(capture_path) as source:
        image = source.convert("RGBA")
    layers = {
        str(row["Name"]): row for row in package["document"]["Layers"]
    }
    artifacts = {
        str(row["object_id"]): row for row in package["static_bakes"]
    }
    primary = layers["Exact Triangle"]
    rotated = layers["Rotated EvenOdd Ring"]
    primary_artifact = artifacts[str(primary["Id"])]
    rotated_artifact = artifacts[str(rotated["Id"])]
    with Image.open(Path(str(primary_artifact["png_path"]))) as source:
        primary_bake = source.convert("RGBA")
    with Image.open(Path(str(rotated_artifact["png_path"]))) as source:
        rotated_bake = source.convert("RGBA")
    primary_contract = _artifact_color_contract(primary_artifact, primary_bake)
    rotated_contract = _artifact_color_contract(rotated_artifact, rotated_bake)
    primary_left = int(
        round(
            float(primary["Position"]["X"])
            - float(primary["RenderTransformPivot"]["X"])
            * float(primary["Size"]["X"])
        )
    )
    primary_top = int(
        round(
            float(primary["Position"]["Y"])
            - float(primary["RenderTransformPivot"]["Y"])
            * float(primary["Size"]["Y"])
        )
    )
    primary_box = (
        primary_left,
        primary_top,
        primary_left + primary_bake.width,
        primary_top + primary_bake.height,
    )
    actual_primary = image.crop(primary_box)
    primary_expected_frame = _transformed_alpha_frame(
        primary,
        primary_bake,
        image.size,
    )
    primary_gpu_color_reference = _slate_sampled_rgba_frame(
        primary,
        primary_bake,
        image.size,
    )
    primary_expected_crop = primary_expected_frame.crop(primary_box)
    expected_alpha = primary_expected_crop.tobytes()
    actual_alpha = actual_primary.getchannel("A").tobytes()
    alpha_error_count = sum(
        actual != expected
        for actual, expected in zip(actual_alpha, expected_alpha, strict=True)
    )
    maximum_bake_alpha = max(expected_alpha, default=0)
    primary_rgb = _rgb_contract_metrics(
        actual_primary,
        primary_expected_crop,
        source_rgb=primary_contract["source_plateau_rgb"],
        source_maximum_alpha=int(primary_contract["source_maximum_alpha"]),
        gpu_color_reference=primary_gpu_color_reference.crop(primary_box),
    )

    rotated_expected_alpha = _transformed_alpha_frame(
        rotated,
        rotated_bake,
        image.size,
    )
    rotated_gpu_color_reference = _slate_sampled_rgba_frame(
        rotated,
        rotated_bake,
        image.size,
    )
    rotated_slate_projection = _slate_pixel_snapped_box_projection(rotated)
    expected_support = rotated_expected_alpha.getbbox() or (0, 0, 0, 0)
    ring_roi = (
        max(0, int(expected_support[0]) - 3),
        max(0, int(expected_support[1]) - 3),
        min(image.width, int(expected_support[2]) + 3),
        min(image.height, int(expected_support[3]) + 3),
    )
    actual_ring_alpha = Image.new("L", image.size, 0)
    actual_ring_alpha.paste(image.getchannel("A").crop(ring_roi), ring_roi)
    ring_mask = _mask_comparison(
        rotated_expected_alpha,
        actual_ring_alpha,
    )
    ring_rgb = _rgb_contract_metrics(
        image,
        rotated_expected_alpha,
        source_rgb=rotated_contract["source_plateau_rgb"],
        source_maximum_alpha=int(rotated_contract["source_maximum_alpha"]),
        gpu_color_reference=rotated_gpu_color_reference,
    )

    padding = rotated_artifact.get("padding") or {}
    hole_left = float(padding.get("left", 2)) + 10.0
    hole_top = float(padding.get("top", 2)) + 10.0
    hole_right = float(padding.get("left", 2)) + 22.0
    hole_bottom = float(padding.get("top", 2)) + 22.0
    captured_alpha = image.getchannel("A").tobytes()
    hole_alpha_values: list[int] = []
    for y in range(image.height):
        for x in range(image.width):
            local_x, local_y = _world_to_local(rotated, x + 0.5, y + 0.5)
            if (
                hole_left <= local_x <= hole_right
                and hole_top <= local_y <= hole_bottom
            ):
                hole_alpha_values.append(captured_alpha[y * image.width + x])
    hole_alpha_max = max(hole_alpha_values, default=255)
    pixels = image.load()
    hole_x, hole_y = _world_sample(rotated, 18.0, 18.0)
    solid_x, solid_y = _world_sample(rotated, 6.0, 18.0)
    solid_alpha_max = max(
        pixels[x, y][3]
        for y in range(max(0, solid_y - 1), min(image.height, solid_y + 2))
        for x in range(max(0, solid_x - 1), min(image.width, solid_x + 2))
    )
    primary_alpha_bbox = list(actual_primary.getchannel("A").getbbox() or ())
    expected_primary_alpha_bbox = list(primary_expected_crop.getbbox() or ())
    return {
        "ok": bool(
            image.size == (192, 128)
            and alpha_error_count == 0
            and primary_alpha_bbox == expected_primary_alpha_bbox
            and expected_primary_alpha_bbox == [2, 2, 42, 32]
            and maximum_bake_alpha in {127, 128}
            and primary_contract["ok"]
            and rotated_contract["ok"]
            and primary_rgb["ok"]
            and ring_mask["ok"]
            and ring_rgb["ok"]
            and hole_alpha_max == 0
            and len(hole_alpha_values) > 50
            and solid_alpha_max >= 250
            and abs(float(rotated["RotationDegrees"]) - 25.0) <= 0.000001
            and rotated["RenderTransformPivot"] != {"X": 0.5, "Y": 0.5}
        ),
        "capture_size": list(image.size),
        "required_capture_size": [192, 128],
        "primary_box": list(primary_box),
        "primary_bake_size": list(primary_bake.size),
        "primary_alpha_bbox": primary_alpha_bbox,
        "expected_primary_alpha_bbox": expected_primary_alpha_bbox,
        "alpha_mask_exact": alpha_error_count == 0,
        "alpha_error_pixel_count": alpha_error_count,
        "maximum_bake_alpha": maximum_bake_alpha,
        "expected_fill_opacity": 0.5,
        "primary_color_contract": primary_contract,
        "primary_rgb": primary_rgb,
        "rotated_evenodd_ring": {
            "rotation_degrees": float(rotated["RotationDegrees"]),
            "render_transform_pivot": dict(rotated["RenderTransformPivot"]),
            "canvas_anchor_minimum": dict(
                rotated["CanvasSlot"]["AnchorMinimum"]
            ),
            "canvas_anchor_maximum": dict(
                rotated["CanvasSlot"]["AnchorMaximum"]
            ),
            "full_frame_expected_alpha_size": list(rotated_expected_alpha.size),
            "reference_projection": (
                "slate_pixel_snapped_box_two_triangle_piecewise_affine_uv_"
                "then_bilinear_png_alpha"
            ),
            "pixel_center_convention": (
                "target samples at n+0.5; normalized UV maps PNG texel "
                "centers at (n+0.5)/size"
            ),
            "slate_pixel_snapping": rotated_slate_projection,
            "comparison_roi": list(ring_roi),
            "mask": ring_mask,
            "color_contract": rotated_contract,
            "rgb": ring_rgb,
            "hole_sample": [hole_x, hole_y],
            "hole_core_local_bounds": [
                hole_left,
                hole_top,
                hole_right,
                hole_bottom,
            ],
            "hole_core_pixel_count": len(hole_alpha_values),
            "hole_alpha_max": hole_alpha_max,
            "solid_sample": [solid_x, solid_y],
            "solid_alpha_max_3x3": solid_alpha_max,
        },
    }


def _texture_property_script(
    texture_paths: list[str],
    report_path: Path,
) -> str:
    return f"""
import json
from pathlib import Path
import unreal

def read(value, name):
    try:
        return value.get_editor_property(name)
    except Exception as exc:
        return "unavailable:" + str(exc)

rows = []
for texture_path in {texture_paths!r}:
    texture = unreal.load_asset(texture_path)
    row = {{"path": texture_path, "loaded": texture is not None}}
    if texture is not None:
        row.update({{
            "class": texture.get_class().get_name(),
            "srgb": bool(read(texture, "srgb")),
            "compression_settings": str(read(texture, "compression_settings")),
            "mip_gen_settings": str(read(texture, "mip_gen_settings")),
            "lod_group": str(read(texture, "lod_group")),
            "never_stream": bool(read(texture, "never_stream")),
            "compression_no_alpha": bool(read(texture, "compression_no_alpha")),
            "address_x": str(read(texture, "address_x")),
            "address_y": str(read(texture, "address_y")),
        }})
    rows.append(row)
Path({str(report_path)!r}).write_text(
    json.dumps({{"textures": rows}}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
""".strip()


def _enum_has(value: Any, *tokens: str) -> bool:
    normalized = "".join(character for character in str(value).upper() if character.isalnum())
    return any(
        "".join(character for character in token.upper() if character.isalnum())
        in normalized
        for token in tokens
    )


def _inspect_texture_properties(
    project: Path,
    texture_paths: list[str],
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    editor = (
        DEFAULT_UNREAL_ENGINE_ROOT
        / "Binaries"
        / "Win64"
        / "UnrealEditor-Cmd.exe"
    )
    with tempfile.TemporaryDirectory(
        prefix="tigerstudio_static_vector_texture_properties_"
    ) as temporary:
        temporary_root = Path(temporary)
        report_path = temporary_root / "texture_properties.json"
        script_path = temporary_root / "inspect_texture_properties.py"
        script_path.write_text(
            _texture_property_script(texture_paths, report_path),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                str(editor),
                str(project),
                f"-ExecutePythonScript={script_path.as_posix()}",
                "-ScriptErrorsAreFatal",
                "-unattended",
                "-nop4",
                "-nosplash",
                "-RenderOffscreen",
                "-AllowCommandletRendering",
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=max(30, int(timeout_seconds)),
            check=False,
        )
        if not report_path.is_file():
            return {
                "ok": False,
                "errors": ["texture_property_report_missing"],
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            }
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        rows = list(payload.get("textures") or [])
        for row in rows:
            row["ok"] = bool(
                row.get("loaded")
                and row.get("class") == "Texture2D"
                and row.get("srgb") is True
                and _enum_has(
                    row.get("compression_settings"),
                    "TC_EditorIcon",
                    "TC_Editor_Icon",
                )
                and _enum_has(
                    row.get("mip_gen_settings"),
                    "TMGS_NoMipmaps",
                    "TMGS_No_Mipmaps",
                )
                and _enum_has(row.get("lod_group"), "TEXTUREGROUP_UI")
                and row.get("never_stream") is True
                and row.get("compression_no_alpha") is False
                and _enum_has(row.get("address_x"), "TA_Clamp")
                and _enum_has(row.get("address_y"), "TA_Clamp")
            )
        return {
            "ok": bool(
                completed.returncode == 0
                and len(rows) == len(texture_paths)
                and len(rows) == 2
                and all(row.get("ok") for row in rows)
            ),
            "inspection_phase": "after_widget_blueprint_reopen",
            "required": {
                "class": "Texture2D",
                "srgb": True,
                "compression_settings": "TC_EditorIcon",
                "mip_gen_settings": "TMGS_NoMipmaps",
                "lod_group": "TEXTUREGROUP_UI",
                "never_stream": True,
                "compression_no_alpha": False,
                "address_x": "TA_Clamp",
                "address_y": "TA_Clamp",
            },
            "textures": rows,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }


def _materialization_evidence(package: dict[str, Any]) -> dict[str, Any]:
    document = package.get("document") or {}
    layers = list(document.get("Layers") or [])
    resources = list(document.get("Resources") or [])
    static_bakes = list(package.get("static_bakes") or [])
    source_preflight = package.get("preflight") or {}
    packaged_preflight = package.get("packaged_preflight") or {}
    background_layers = [
        row
        for row in layers
        if row.get("Id") == "__tiger_artboard_background"
    ]
    background_layer = background_layers[0] if len(background_layers) == 1 else {}
    baked_layers = [row for row in layers if row.get("Disposition") == "Baked"]
    asset_ids = [
        str((row.get("ImageFill") or {}).get("AssetId") or "")
        for row in baked_layers
    ]
    resource_ids = [str(row.get("Id") or "") for row in resources]
    layer_object_ids = [str(row.get("Id") or "") for row in baked_layers]
    artifact_object_ids = [str(row.get("object_id") or "") for row in static_bakes]
    payload_rows: list[dict[str, Any]] = []
    for layer in baked_layers:
        try:
            payload = json.loads(str(layer.get("PayloadJson") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        bake = payload.get("static_vector_bake") or {}
        payload_rows.append(
            {
                "object_id": str(layer.get("Id") or ""),
                "status": str(bake.get("status") or ""),
                "content_hash": str(bake.get("content_hash") or ""),
                "renderer_id": str(
                    ((bake.get("source") or {}).get("renderer") or {}).get("id")
                    or ""
                ),
            }
        )
    resources_by_id = {
        str(row.get("Id") or ""): row for row in resources if row.get("Id")
    }
    resource_contracts: list[dict[str, Any]] = []
    for asset_id in asset_ids:
        resource = resources_by_id.get(asset_id) or {}
        try:
            settings = json.loads(str(resource.get("SettingsJson") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            settings = {}
        resource_contracts.append(
            {
                "asset_id": asset_id,
                "kind": str(resource.get("Kind") or ""),
                "source_path": str(resource.get("SourcePath") or ""),
                "destination_name": str(resource.get("DestinationName") or ""),
                "content_hash": str(resource.get("ContentHash") or ""),
                "settings": settings,
            }
        )
    source_plans = list(source_preflight.get("bake_plans") or [])
    materialized_plans = list(packaged_preflight.get("bake_plans") or [])
    expected_counts = {
        "Native": 1,
        "Material": 0,
        "Baked": 2,
        "Blocked": 0,
    }
    return {
        "ok": bool(
            package.get("ok")
            and document.get("SchemaVersion") == 16
            and source_preflight.get("counts") == expected_counts
            and packaged_preflight.get("counts") == expected_counts
            and len(layers) == 3
            and len(background_layers) == 1
            and background_layer.get("Kind") == "Image"
            and background_layer.get("Disposition") == "Native"
            and background_layer.get("Visibility") == "HitTestInvisible"
            and len(baked_layers) == 2
            and all(row.get("Kind") == "Image" for row in baked_layers)
            and all(asset_ids)
            and len(set(asset_ids)) == 2
            and resource_ids == asset_ids
            and layer_object_ids == artifact_object_ids
            and len(source_plans) == 2
            and all(row.get("status") == "available" for row in source_plans)
            and len(materialized_plans) == 2
            and all(
                row.get("status") == "materialized"
                for row in materialized_plans
            )
            and all(row["status"] == "materialized" for row in payload_rows)
            and all(row["renderer_id"] == "qt_svg_fill_stroke_geometry_v4" for row in payload_rows)
            and all(
                row["kind"] == "texture"
                and row["source_path"].startswith("assets/")
                and row["destination_name"] == f"TS_{row['asset_id']}"
                and len(row["content_hash"]) == 64
                and row["settings"] == {"Usage": "ImageFill", "SRGB": True}
                for row in resource_contracts
            )
            and all(
                payload["content_hash"] == resource["content_hash"]
                for payload, resource in zip(
                    payload_rows,
                    resource_contracts,
                    strict=True,
                )
            )
        ),
        "schema_version": document.get("SchemaVersion"),
        "required_schema_version": 16,
        "source_preflight_counts": source_preflight.get("counts"),
        "packaged_preflight_counts": packaged_preflight.get("counts"),
        "required_counts": expected_counts,
        "artboard_background": {
            "id": str(background_layer.get("Id") or ""),
            "kind": str(background_layer.get("Kind") or ""),
            "disposition": str(background_layer.get("Disposition") or ""),
            "visibility": str(background_layer.get("Visibility") or ""),
        },
        "source_bake_plans": source_plans,
        "packaged_bake_plans": materialized_plans,
        "baked_layer_ids": layer_object_ids,
        "baked_asset_ids": asset_ids,
        "artifact_object_ids": artifact_object_ids,
        "payloads": payload_rows,
        "resources": resource_contracts,
    }


def run_qa(workspace: Path, *, timeout_seconds: int) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    project = _ensure_project(workspace)
    generation = generate_painter_umg(
        _fixture(),
        project_path=project,
        output_dir=workspace / "packet",
        timeout_seconds=timeout_seconds,
    )
    asset_path = str(generation.get("generated_asset_path") or "")
    texture_paths = [
        str(value)
        for value in generation.get("imported_asset_paths", [])
        if str(value)
    ]
    package = generation.get("package") or {}
    static_bakes = list(package.get("static_bakes") or [])
    materialization = _materialization_evidence(package)
    object_ids = [str(row.get("object_id") or "") for row in static_bakes]
    expected_widget_classes = {
        object_id: "Image" for object_id in object_ids if object_id
    }
    reopen = (
        _reopen_generated_asset(
            project,
            asset_path,
            texture_paths=texture_paths,
            texture_widget_names=object_ids,
            expected_widget_classes=expected_widget_classes,
            timeout_seconds=timeout_seconds,
        )
        if generation.get("ok") and asset_path and len(object_ids) == 2
        else {"ok": False, "errors": ["generation_failed_before_reopen"]}
    )
    texture_properties = (
        _inspect_texture_properties(
            project,
            texture_paths,
            timeout_seconds=timeout_seconds,
        )
        if reopen.get("ok") and len(texture_paths) == 2
        else {
            "ok": False,
            "errors": ["reopen_failed_before_texture_property_inspection"],
        }
    )
    capture_path = workspace / "static_vector_bake_fwidget_renderer.png"
    render = (
        _render_generated_asset(
            project,
            asset_path,
            capture_path,
            width=192,
            height=128,
            timeout_seconds=timeout_seconds,
        )
        if reopen.get("ok")
        else {"ok": False, "message": "reopen_failed_before_render"}
    )
    evidence = (
        _image_evidence(capture_path, package)
        if render.get("ok") and static_bakes and capture_path.is_file()
        else {"ok": False, "reason": "render_or_bake_missing"}
    )
    generated_widget_classes = generation.get("generated_widget_classes") or {}
    generation_widget_classes_ok = all(
        str(generated_widget_classes.get(name) or "") == class_name
        for name, class_name in expected_widget_classes.items()
    )
    reopen_widget_classes = reopen.get("widget_classes") or {}
    reopen_widget_tree_class_verified = bool(reopen_widget_classes) and all(
        str(reopen_widget_classes.get(name) or "") == class_name
        for name, class_name in expected_widget_classes.items()
    )
    reopen_texture_rows = list(reopen.get("textures") or [])
    reopen_texture_references_ok = bool(
        len(reopen_texture_rows) == 2
        and all(
            row.get("ok")
            and row.get("class") == "Texture2D"
            and row.get("widget_name") in expected_widget_classes
            for row in reopen_texture_rows
        )
    )
    return {
        "schema": "tigercapture.painter.ui.unreal_umg_static_vector_bake_qa.v3",
        "ok": bool(generation.get("ok"))
        and bool(materialization.get("ok"))
        and bool(reopen.get("ok"))
        and reopen_texture_references_ok
        and bool(texture_properties.get("ok"))
        and bool(render.get("ok"))
        and bool(evidence.get("ok"))
        and generation_widget_classes_ok
        and int(generation.get("generated_widget_count") or 0) == 2
        and len(texture_paths) == 2
        and len(static_bakes) == 2,
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "project_path": str(project),
        "generation": generation,
        "materialization_evidence": materialization,
        "reopen": reopen,
        "texture_property_evidence": texture_properties,
        "render": render,
        "pixel_evidence": evidence,
        "widget_class_evidence": {
            "generation_session_exact": generation_widget_classes_ok,
            "generation_widget_count": int(
                generation.get("generated_widget_count") or 0
            ),
            "required_generation_widget_count": 2,
            "expected": expected_widget_classes,
            "expected_uobject_class": "UImage (reported by Unreal as Image)",
            "generated": generated_widget_classes,
            "reopen_widget_tree_exposed": bool(reopen_widget_classes),
            "reopen_widget_tree_exact": reopen_widget_tree_class_verified,
            "reopen_texture_references_exact": reopen_texture_references_ok,
            "reopen_verification": (
                "widget_tree_exact"
                if reopen_widget_tree_class_verified
                else "generated_class_plus_serialized_texture_references"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    report = run_qa(args.workspace, timeout_seconds=args.timeout)
    report_path = args.workspace.expanduser().resolve() / "qa_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

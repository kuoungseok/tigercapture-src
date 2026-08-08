"""Shared 2.5D camera and generic layer-replicator evaluation."""
from __future__ import annotations

import math
from typing import Any, Mapping

from .keyframes import evaluate_property
from .schema import AnimatedProperty, MotionComposition, MotionLayer


def _evaluate(value: Any, time_ms: float, default: Any, value_type: str = "scalar") -> Any:
    if isinstance(value, Mapping) and ({"default", "keyframes"} & set(value)):
        prop = AnimatedProperty.from_dict(value, value_type=value_type)
        if prop.default is None:
            prop.default = default
        return evaluate_property(prop, time_ms)
    return default if value is None else value


def _vector(value: Any, size: int, default: list[float]) -> list[float]:
    source = list(value) if isinstance(value, (list, tuple)) else list(default)
    source.extend(default[len(source):size])
    output = []
    for index in range(size):
        try:
            output.append(float(source[index]))
        except (TypeError, ValueError, IndexError):
            output.append(float(default[index]))
    return output


def active_2_5d_camera(composition: MotionComposition, time_ms: float) -> dict[str, Any] | None:
    """Return evaluated camera values only when 2D projection is explicitly enabled."""
    camera = next((
        layer for layer in reversed(composition.layers)
        if layer.layer_type == "camera"
        and layer.visible
        and layer.in_ms <= time_ms < layer.out_ms
        and bool(layer.source.params.get("apply_to_2d", False))
    ), None)
    if camera is None:
        return None
    params = camera.source.params
    position = _vector(_evaluate(params.get("position"), time_ms, [0.0, 0.0, 3.25], "vector3"), 3, [0.0, 0.0, 3.25])
    rotation = _vector(_evaluate(params.get("rotation"), time_ms, [0.0, 0.0, 0.0], "vector3"), 3, [0.0, 0.0, 0.0])
    fov = max(10.0, min(120.0, float(_evaluate(params.get("fov"), time_ms, 45.0))))
    projection = str(_evaluate(params.get("projection"), time_ms, "perspective", "string") or "perspective").lower()
    if projection not in {"perspective", "orthographic"}:
        projection = "perspective"
    return {
        "x": position[0],
        "y": position[1],
        "z": max(0.2, position[2]),
        "roll": rotation[2],
        "fov": fov,
        "projection": projection,
        "orthographic_size": max(
            0.05,
            min(100.0, float(_evaluate(params.get("orthographic_size"), time_ms, 3.25))),
        ),
        "parallax_strength": max(0.0, min(4.0, float(params.get("parallax_strength", 1.0) or 0.0))),
        "pixels_per_unit": max(1.0, min(1000.0, float(params.get("pixels_per_unit", 120.0) or 120.0))),
    }


def active_2_5d_light(
    composition: MotionComposition,
    time_ms: float,
) -> dict[str, float] | None:
    """Return the active directional light used by 2.5D card shadows."""
    layer = next((
        row for row in reversed(composition.layers)
        if row.layer_type == "light"
        and row.visible
        and row.in_ms <= time_ms < row.out_ms
        and str(row.source.params.get("light_type") or "directional").lower()
        == "directional"
    ), None)
    if layer is None:
        return None
    params = layer.source.params
    if not bool(_evaluate(params.get("enabled"), time_ms, True, "bool")):
        return None
    return {
        "azimuth": max(
            -180.0,
            min(180.0, float(_evaluate(params.get("azimuth"), time_ms, 45.0))),
        ),
        "elevation": max(
            5.0,
            min(89.0, float(_evaluate(params.get("elevation"), time_ms, 45.0))),
        ),
        "intensity": max(
            0.0,
            min(4.0, float(_evaluate(params.get("intensity"), time_ms, 0.42))),
        ),
    }


def project_layer_matrix(
    matrix: tuple[float, float, float, float, float, float],
    *,
    composition: MotionComposition,
    layer: MotionLayer,
    time_ms: float,
) -> tuple[float, float, float, float, float, float]:
    """Project one authored 2D world matrix through the active 2.5D camera."""
    camera = active_2_5d_camera(composition, time_ms)
    if camera is None or layer.layer_type in {"camera", "light", "ar_pbr"}:
        return matrix
    if bool(layer.metadata.get("camera_2_5d_excluded", False)):
        return matrix
    three_d = layer.metadata.get("three_d")
    if isinstance(three_d, Mapping) and not bool(three_d.get("enabled", True)):
        return matrix
    depth = max(-8.0, min(8.0, float(layer.metadata.get("depth_z", 0.0) or 0.0)))
    if camera["projection"] == "orthographic":
        projection_scale = max(0.08, min(12.0, camera["z"] / camera["orthographic_size"]))
        parallax = camera["parallax_strength"]
    else:
        distance = max(0.2, camera["z"] - depth)
        fov_zoom = math.tan(math.radians(45.0 * 0.5)) / math.tan(math.radians(camera["fov"] * 0.5))
        projection_scale = max(0.08, min(12.0, camera["z"] / distance * fov_zoom))
        parallax = camera["parallax_strength"] * (1.0 + depth / max(camera["z"], 0.2))
    pan_x = -camera["x"] * camera["pixels_per_unit"] * parallax
    pan_y = camera["y"] * camera["pixels_per_unit"] * parallax

    a, b, c, d, tx, ty = matrix
    if isinstance(three_d, Mapping) and bool(three_d.get("enabled", False)):
        rotation_x = max(
            -180.0,
            min(180.0, float(_evaluate(three_d.get("rotation_x"), time_ms, 0.0))),
        )
        rotation_y = max(
            -180.0,
            min(180.0, float(_evaluate(three_d.get("rotation_y"), time_ms, 0.0))),
        )
        horizontal = math.cos(math.radians(rotation_y))
        vertical = math.cos(math.radians(rotation_x))
        a, b = a * horizontal, b * horizontal
        c, d = c * vertical, d * vertical
    center_x = composition.width * 0.5
    center_y = composition.height * 0.5
    tx = center_x + (tx - center_x + pan_x) * projection_scale
    ty = center_y + (ty - center_y + pan_y) * projection_scale
    angle = math.radians(-camera["roll"])
    cosine, sine = math.cos(angle), math.sin(angle)
    projected = (
        (cosine * a - sine * b) * projection_scale,
        (sine * a + cosine * b) * projection_scale,
        (cosine * c - sine * d) * projection_scale,
        (sine * c + cosine * d) * projection_scale,
        tx,
        ty,
    )
    return projected


def _path_position(points: Any, progress: float) -> tuple[float, float]:
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        return 0.0, 0.0
    clean = [_vector(point, 2, [0.0, 0.0]) for point in points]
    lengths = [math.hypot(clean[index + 1][0] - clean[index][0], clean[index + 1][1] - clean[index][1])
               for index in range(len(clean) - 1)]
    total = sum(lengths)
    if total <= 1e-9:
        return float(clean[0][0]), float(clean[0][1])
    target = max(0.0, min(1.0, progress)) * total
    walked = 0.0
    for index, length in enumerate(lengths):
        if target <= walked + length or index == len(lengths) - 1:
            local = 0.0 if length <= 1e-9 else (target - walked) / length
            return (
                float(clean[index][0] + (clean[index + 1][0] - clean[index][0]) * local),
                float(clean[index][1] + (clean[index + 1][1] - clean[index][1]) * local),
            )
        walked += length
    return float(clean[-1][0]), float(clean[-1][1])


def _ordered_copy_indices(count: int, order: str, seed: float) -> list[int]:
    indices = list(range(count))
    if order == "reverse":
        indices.reverse()
    elif order == "random":
        indices.sort(key=lambda index: math.sin((index + 1) * 91.733 + seed * 17.171))
    return indices


def evaluate_replicator(config: Any, time_ms: float) -> list[dict[str, float]]:
    """Evaluate a renderer-neutral replicator for any renderable layer type."""
    if not isinstance(config, Mapping) or not bool(config.get("enabled", True)):
        return [{"x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0, "opacity": 1.0}]
    count = max(1, min(256, int(_evaluate(config.get("count"), time_ms, 1) or 1)))
    offset = _vector(_evaluate(config.get("offset"), time_ms, [0.0, 0.0], "vector2"), 2, [0.0, 0.0])
    arrangement = str(config.get("arrangement") or "line").lower()
    columns = max(1, min(count, int(config.get("columns", max(1, round(math.sqrt(count)))) or 1)))
    scale = _vector(_evaluate(config.get("scale"), time_ms, [1.0, 1.0], "vector2"), 2, [1.0, 1.0])
    rotation = float(_evaluate(config.get("rotation"), time_ms, 0.0))
    opacity_start = max(0.0, min(1.0, float(_evaluate(config.get("opacity_start"), time_ms, 1.0))))
    opacity_end = max(0.0, min(1.0, float(_evaluate(config.get("opacity_end"), time_ms, opacity_start))))
    seed = float(config.get("seed", 0.0) or 0.0)
    jitter = _vector(config.get("jitter"), 2, [0.0, 0.0])
    order = str(config.get("order") or "normal").lower()
    ordered_indices = _ordered_copy_indices(count, order, seed)
    sequence_offset_ms = max(0.0, float(config.get("sequence_offset_ms", 0.0) or 0.0))
    sequence_fade_ms = max(0.0, float(config.get("sequence_fade_ms", 0.0) or 0.0))
    sequence_start_ms = float(config.get("sequence_start_ms", 0.0) or 0.0)
    phase = float(time_ms) / 1000.0
    rows = []
    for sequence_index, index in enumerate(ordered_indices):
        mix = index / max(1, count - 1)
        noise_x = math.sin((index * 12.9898 + seed * 17.31) * 1.731 + phase * 0.7)
        noise_y = math.sin((index * 78.233 + seed * 9.17) * 1.137 - phase * 0.53)
        if arrangement == "grid":
            base_x = offset[0] * (index % columns)
            base_y = offset[1] * (index // columns)
            base_rotation = rotation * index
        elif arrangement == "radial":
            angle = rotation + 360.0 * index / max(1, count)
            radians = math.radians(angle)
            base_x = abs(offset[0]) * math.cos(radians)
            base_y = abs(offset[0]) * math.sin(radians)
            base_rotation = angle if bool(config.get("face_outward", False)) else rotation * index
        elif arrangement == "spiral":
            turns = float(config.get("turns", 2.0) or 2.0)
            angle = rotation + 360.0 * turns * mix
            radius = abs(offset[0]) * mix
            radians = math.radians(angle)
            base_x = radius * math.cos(radians)
            base_y = radius * math.sin(radians)
            base_rotation = angle if bool(config.get("face_outward", False)) else rotation * index
        elif arrangement == "path":
            base_x, base_y = _path_position(config.get("path_points"), mix)
            base_rotation = rotation * index
        else:
            base_x = offset[0] * index
            base_y = offset[1] * index
            base_rotation = rotation * index
        reveal_time = sequence_start_ms + sequence_index * sequence_offset_ms
        if sequence_fade_ms > 0.0:
            sequence_opacity = max(0.0, min(1.0, (float(time_ms) - reveal_time) / sequence_fade_ms))
        elif sequence_offset_ms > 0.0:
            sequence_opacity = 1.0 if float(time_ms) >= reveal_time else 0.0
        else:
            sequence_opacity = 1.0
        rows.append({
            "x": base_x + noise_x * jitter[0],
            "y": base_y + noise_y * jitter[1],
            "rotation": base_rotation,
            "scale_x": scale[0] ** index,
            "scale_y": scale[1] ** index,
            "opacity": (opacity_start + (opacity_end - opacity_start) * mix) * sequence_opacity,
            "copy_index": float(index),
            "sequence_index": float(sequence_index),
            "source_time_ms": float(time_ms) - sequence_index * sequence_offset_ms,
        })
    return rows


__all__ = [
    "active_2_5d_camera",
    "active_2_5d_light",
    "evaluate_replicator",
    "project_layer_matrix",
]

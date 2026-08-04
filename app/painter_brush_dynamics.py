"""Deterministic brush dynamics shared by Painter preview/export."""
from __future__ import annotations

import base64
import colorsys
import json
import math
from pathlib import Path
from typing import Any, Iterable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter


BRUSH_DYNAMICS_DEFAULTS: dict[str, object] = {
    "enabled": False,
    "flow": 100,
    "buildup": 0,
    "stabilization": 0,
    "pressure_curve": [[0.0, 0.0], [0.25, 0.18], [0.5, 0.5], [0.75, 0.82], [1.0, 1.0]],
    "pressure_min": 0,
    "pressure_max": 100,
    "scatter": 0,
    "scatter_count": 1,
    "size_jitter": 0,
    "texture_strength": 0,
    "texture_scale": 100,
    "transfer_opacity": 100,
    "transfer_flow": 100,
    "hue_jitter": 0,
    "saturation_jitter": 0,
    "value_jitter": 0,
    "tilt_size": 0,
    "tilt_angle": 0,
    "rotation_angle": 0,
    "barrel_flow": 0,
    "mode": "paint",
    "mix": 50,
    "pickup": 50,
    "smudge_length": 50,
    "smudge_radius": 20,
    "color_rate": 0,
    "overlay": False,
    "smudge_type": "dulling",
    "dab_image_path": "",
    "dab_png_base64": "",
    "dual_brush_enabled": False,
    "dual_brush_seed": 0,
    "dual_brush_strength": 100,
    "noise_enabled": False,
    "noise_seed": 0,
    "noise_scale": 100,
    "wet_edges_enabled": False,
    "wet_edge_pooling": 50,
    "wet_edge_pigment": 100,
    "wet_edge_water": 100,
    "protect_texture": False,
    "texture": {},
    "document_texture": {},
}

BRUSH_DYNAMICS_MODEL_CONTRACT: dict[str, object] = {
    "model": "tiger_authored_deterministic_dab_dynamics_v1",
    "coefficient_source": "authored_brush_response_not_physical_stylus_model",
    "deterministic_replay_claim": True,
    "physical_media_claim": False,
    "driver_latency_claim": False,
    "external_brush_engine_parity_claim": False,
    "smudge_sample_radius_px_domain": [0, 32],
    "max_scatter_copies_per_path_sample": 16,
    "max_materialized_dabs_per_stroke": 8192,
    "dab_budget_behavior": "uniform_full_path_resampling_with_explicit_workload_diagnostic",
    "capacity_source": "tiger_authored_brush_workload_policy",
    "live_commit_rgba_tolerance_contract": {
        "model": "8bit_one_lsb_per_distinct_alpha_over_stage",
        "distinct_stage_budget": 2,
        "max_delta_lsb": 2,
        "byte_identical_claim": False,
    },
}

PAINTER_DYNAMIC_DAB_BUDGET = 8192

_PERCENT_KEYS = {
    "flow", "buildup", "stabilization", "pressure_min", "pressure_max",
    "scatter", "size_jitter", "texture_strength", "texture_scale",
    "transfer_opacity", "transfer_flow", "hue_jitter", "saturation_jitter",
    "value_jitter", "tilt_size", "tilt_angle", "rotation_angle",
    "barrel_flow", "mix", "pickup", "smudge_length", "smudge_radius",
    "color_rate",
    "dual_brush_strength", "noise_scale", "wet_edge_pooling",
    "wet_edge_pigment", "wet_edge_water",
}
_MODES = {"paint", "smudge", "mixer", "pickup"}


def _normalize_texture_mapping(
    value: object, *, name: str
) -> tuple[dict[str, object], list[str]]:
    if not isinstance(value, dict):
        return {}, ([f"{name} must be an object"] if value not in (None, {}) else [])
    result: dict[str, object] = {}
    errors: list[str] = []
    pattern_id = str(value.get("pattern_id") or "").strip()
    if pattern_id:
        result["pattern_id"] = pattern_id
    if "strength" in value:
        try:
            strength = float(value["strength"])
            if math.isfinite(strength):
                result["strength"] = max(0.0, min(100.0, strength))
            else:
                errors.append(f"{name}.strength must be finite numeric percent")
        except (TypeError, ValueError, OverflowError):
            errors.append(f"{name}.strength must be finite numeric percent")
    if "scale" in value:
        try:
            scale = float(value["scale"])
            if math.isfinite(scale) and scale > 0.0:
                result["scale"] = scale
            else:
                errors.append(f"{name}.scale must be finite and positive")
        except (TypeError, ValueError, OverflowError):
            errors.append(f"{name}.scale must be finite and positive")
    offset = value.get("offset")
    if isinstance(offset, (list, tuple)) and len(offset) >= 2:
        try:
            normalized_offset = [float(offset[0]), float(offset[1])]
            if all(math.isfinite(item) for item in normalized_offset):
                result["offset"] = normalized_offset
            else:
                errors.append(f"{name}.offset must contain two finite numbers")
        except (TypeError, ValueError, OverflowError):
            errors.append(f"{name}.offset must contain two finite numbers")
    elif offset is not None:
        errors.append(f"{name}.offset must contain two finite numbers")
    return result, errors


def normalize_brush_dynamics(values: dict[str, object] | None = None) -> dict[str, object]:
    result = dict(BRUSH_DYNAMICS_DEFAULTS)
    result.update(dict(values or {}))
    normalization_errors: list[str] = []
    result["enabled"] = bool(result.get("enabled", False))
    for key in _PERCENT_KEYS:
        default = float(BRUSH_DYNAMICS_DEFAULTS[key])
        try:
            result[key] = max(0, min(100, int(round(float(result.get(key, default))))))
        except (TypeError, ValueError, OverflowError):
            result[key] = int(default)
            normalization_errors.append(f"{key} must be finite numeric percent")
    result["pressure_max"] = max(int(result["pressure_min"]) + 1, int(result["pressure_max"]))
    try:
        result["scatter_count"] = max(
            1, min(8, int(result.get("scatter_count", 1) or 1))
        )
    except (TypeError, ValueError, OverflowError):
        result["scatter_count"] = 1
        normalization_errors.append("scatter_count must be an integer from 1 to 8")
    mode = str(result.get("mode") or "paint").strip().casefold()
    result["mode"] = mode if mode in _MODES else "paint"
    result["overlay"] = bool(result.get("overlay", False))
    for key in (
        "dual_brush_enabled",
        "noise_enabled",
        "wet_edges_enabled",
        "protect_texture",
    ):
        result[key] = bool(result.get(key, False))
    for key in ("dual_brush_seed", "noise_seed"):
        try:
            result[key] = int(result.get(key, 0) or 0) & ((1 << 64) - 1)
        except (TypeError, ValueError, OverflowError):
            result[key] = 0
            normalization_errors.append(f"{key} must be an integer")
    for key in ("texture", "document_texture"):
        mapping, mapping_errors = _normalize_texture_mapping(
            result.get(key), name=key
        )
        result[key] = mapping
        normalization_errors.extend(mapping_errors)
    if normalization_errors:
        result["normalization_errors"] = normalization_errors
    else:
        result.pop("normalization_errors", None)
    smudge_type = str(result.get("smudge_type") or "dulling").strip().casefold()
    result["smudge_type"] = smudge_type if smudge_type in {"smear", "dulling"} else "dulling"
    sampled = result.get("sampled_rgba")
    normalized_samples: list[list[int]] = []
    invalid_sample_count = 0
    for row in list(sampled or []):
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            invalid_sample_count += 1
            continue
        try:
            normalized_samples.append([
                max(0, min(255, int(channel))) for channel in list(row)[:4]
            ])
        except (TypeError, ValueError, OverflowError):
            invalid_sample_count += 1
    result["sampled_rgba"] = normalized_samples
    if invalid_sample_count:
        normalization_errors.append(
            f"sampled_rgba rejected {invalid_sample_count} invalid rows"
        )
    if normalization_errors:
        result["normalization_errors"] = normalization_errors
    else:
        result.pop("normalization_errors", None)
    result["pressure_curve"] = normalize_pressure_curve(result.get("pressure_curve"))
    result["dab_image_path"] = str(result.get("dab_image_path") or "")
    result["dab_png_base64"] = str(result.get("dab_png_base64") or "")
    return result


def normalize_pressure_curve(points: object) -> list[list[float]]:
    clean: list[list[float]] = []
    for row in list(points or []):
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        try:
            x = max(0.0, min(1.0, float(row[0])))
            y = max(0.0, min(1.0, float(row[1])))
        except (TypeError, ValueError):
            continue
        clean.append([x, y])
    clean.sort(key=lambda item: item[0])
    if not clean or clean[0][0] > 0.0:
        clean.insert(0, [0.0, 0.0])
    if clean[-1][0] < 1.0:
        clean.append([1.0, 1.0])
    deduped: list[list[float]] = []
    for row in clean:
        if deduped and abs(deduped[-1][0] - row[0]) < 1e-9:
            deduped[-1] = row
        else:
            deduped.append(row)
    return deduped


def map_pressure(value: float, settings: dict[str, object]) -> float:
    cfg = normalize_brush_dynamics(settings)
    return _map_pressure_normalized(value, cfg)


def _map_pressure_normalized(value: float, cfg: dict[str, object]) -> float:
    low = float(cfg["pressure_min"]) / 100.0
    high = max(low + 0.01, float(cfg["pressure_max"]) / 100.0)
    x = max(0.0, min(1.0, (float(value) - low) / (high - low)))
    curve = cfg["pressure_curve"]
    for left, right in zip(curve, curve[1:]):
        if x <= right[0]:
            amount = (x - left[0]) / max(1e-9, right[0] - left[0])
            return max(0.0, min(1.0, left[1] * (1.0 - amount) + right[1] * amount))
    return float(curve[-1][1])


def stabilize_points(
    points: Iterable[tuple[float, float]], strength: float
) -> list[tuple[float, float]]:
    rows = [(float(x), float(y)) for x, y in points]
    if len(rows) < 2:
        return rows
    amount = max(0.0, min(1.0, float(strength)))
    if amount <= 0.0:
        return rows
    alpha = max(0.08, 1.0 - amount * 0.9)
    out = [rows[0]]
    for (px, py), (x, y) in zip(rows, rows[1:]):
        # Use the previous authored sample rather than the previous filtered
        # output. This makes every two-point live segment prefix-stable and
        # therefore identical to the final committed render.
        out.append((px + (x - px) * alpha, py + (y - py) * alpha))
    return out


def _curve(values: object, count: int, default: float) -> list[float]:
    rows = list(values or [])
    if not rows:
        return [default] * count
    clean = [max(-1.0, min(1.0, float(value))) for value in rows]
    if len(clean) == count:
        return clean
    if count <= 1:
        return [clean[0]]
    result = []
    for index in range(count):
        pos = index * (len(clean) - 1) / max(1, count - 1)
        left = int(math.floor(pos)); right = min(len(clean) - 1, left + 1)
        mix = pos - left
        result.append(clean[left] * (1.0 - mix) + clean[right] * mix)
    return result


def _noise(seed: int, index: int, channel: int) -> float:
    return math.sin(seed * 0.173 + index * 12.9898 + channel * 78.233) * 0.5 + 0.5


def _dynamic_dab_plan(stroke: Any, width: int, height: int) -> dict[str, object]:
    cfg = normalize_brush_dynamics(getattr(stroke, "brush_dynamics", {}) or {})
    if not bool(cfg["enabled"]):
        return {"enabled": False, "cfg": cfg}
    source = list(getattr(stroke, "points", []) or [])
    points = stabilize_points(source, float(cfg["stabilization"]) / 100.0)
    if not points:
        return {"enabled": False, "cfg": cfg}
    pressure = _curve(getattr(stroke, "point_pressure", []), len(points), 1.0)
    tilt_x = _curve(getattr(stroke, "point_tilt_x", []), len(points), 0.0)
    tilt_y = _curve(getattr(stroke, "point_tilt_y", []), len(points), 0.0)
    rotation = _curve(getattr(stroke, "point_rotation", []), len(points), 0.5)
    barrel = _curve(getattr(stroke, "point_tangential_pressure", []), len(points), 0.0)
    base_width = max(0.5, float(getattr(stroke, "width_px", 4.0) or 4.0))
    spacing = max(0.7, base_width * max(0.01, float(getattr(stroke, "brush_spacing", 25))) / 100.0)
    count = min(
        16,
        int(cfg["scatter_count"])
        * (1 + int(round(float(cfg["buildup"]) / 34.0))),
    )
    segment_distances = [
        math.hypot(
            (second[0] - first[0]) * width,
            (second[1] - first[1]) * height,
        )
        for first, second in zip(points, points[1:])
    ]
    total_distance = sum(segment_distances)
    raw_path_sample_count = (
        1
        if len(points) == 1 or total_distance <= 0.0
        else int(math.ceil(total_distance / spacing)) + 1
    )
    max_path_samples = max(1, PAINTER_DYNAMIC_DAB_BUDGET // max(1, count))
    effective_spacing = spacing
    workload_degraded = raw_path_sample_count > max_path_samples
    if workload_degraded and total_distance > 0.0 and max_path_samples > 1:
        effective_spacing = max(
            spacing,
            total_distance / float(max_path_samples - 1),
        )
    workload = {
        "policy": "uniform_full_path_resampling_v1",
        "estimated_dabs": int(raw_path_sample_count * count),
        "rendered_dabs": int(min(raw_path_sample_count, max_path_samples) * count),
        "dab_budget": PAINTER_DYNAMIC_DAB_BUDGET,
        "degraded": bool(workload_degraded),
        "requested_spacing_px": float(spacing),
        "effective_spacing_px": float(effective_spacing),
    }
    return {
        "enabled": True,
        "cfg": cfg,
        "points": points,
        "pressure": pressure,
        "tilt_x": tilt_x,
        "tilt_y": tilt_y,
        "rotation": rotation,
        "barrel": barrel,
        "base_width": base_width,
        "count": count,
        "segment_distances": segment_distances,
        "max_path_samples": max_path_samples,
        "effective_spacing": effective_spacing,
        "workload": workload,
    }


def dynamic_dab_workload(stroke: Any, width: int, height: int) -> dict[str, object]:
    """Return bounded-render diagnostics without mutating authored stroke state."""

    plan = _dynamic_dab_plan(stroke, width, height)
    return dict(plan.get("workload") or {})


def dynamic_dabs(stroke: Any, width: int, height: int) -> list[dict[str, float | tuple[int, int, int]]]:
    plan = _dynamic_dab_plan(stroke, width, height)
    if not bool(plan.get("enabled", False)):
        return []
    cfg = dict(plan["cfg"])
    points = list(plan["points"])
    pressure = list(plan["pressure"])
    tilt_x = list(plan["tilt_x"])
    tilt_y = list(plan["tilt_y"])
    rotation = list(plan["rotation"])
    barrel = list(plan["barrel"])
    base_width = float(plan["base_width"])
    count = int(plan["count"])
    segment_distances = list(plan["segment_distances"])
    max_path_samples = int(plan["max_path_samples"])
    effective_spacing = float(plan["effective_spacing"])
    workload_degraded = bool(dict(plan["workload"])["degraded"])
    samples: list[tuple[float, float, float, float, float, float]] = []
    if len(points) == 1:
        samples.append((*points[0], pressure[0], tilt_x[0], tilt_y[0], rotation[0], barrel[0]))
    else:
        distance_to_next = 0.0
        for segment, (first, second) in enumerate(zip(points, points[1:])):
            x1, y1 = first[0] * width, first[1] * height
            x2, y2 = second[0] * width, second[1] * height
            distance = math.hypot(x2 - x1, y2 - y1)
            if distance <= 0.0:
                continue
            while distance_to_next < distance:
                t = distance_to_next / distance
                samples.append((
                    (x1 + (x2 - x1) * t) / width,
                    (y1 + (y2 - y1) * t) / height,
                    pressure[segment] * (1.0 - t) + pressure[segment + 1] * t,
                    tilt_x[segment] * (1.0 - t) + tilt_x[segment + 1] * t,
                    tilt_y[segment] * (1.0 - t) + tilt_y[segment + 1] * t,
                    rotation[segment] * (1.0 - t) + rotation[segment + 1] * t,
                    barrel[segment] * (1.0 - t) + barrel[segment + 1] * t,
                ))
                distance_to_next += effective_spacing
            distance_to_next -= distance
        samples.append((*points[-1], pressure[-1], tilt_x[-1], tilt_y[-1], rotation[-1], barrel[-1]))
    if len(samples) > max_path_samples:
        if max_path_samples == 1:
            samples = [samples[-1]]
        else:
            last_index = len(samples) - 1
            sample_indices = [
                int(round(index * last_index / float(max_path_samples - 1)))
                for index in range(max_path_samples)
            ]
            samples = [samples[index] for index in sample_indices]
        workload_degraded = True
    try:
        seed = int(getattr(stroke, "brush_seed", 0) or 0) & ((1 << 64) - 1)
    except (TypeError, ValueError, OverflowError):
        seed = 0
    base_rgb = tuple(int(v) for v in getattr(stroke, "color", (255, 50, 50)))
    h, s, v = colorsys.rgb_to_hsv(*(channel / 255.0 for channel in base_rgb))
    result = []
    for sample_index, sample in enumerate(samples):
        x, y, raw_pressure, tx, ty, rot, tangential = sample
        local_pressure = _map_pressure_normalized(max(0.0, raw_pressure), cfg)
        for copy_index in range(count):
            index = sample_index * count + copy_index
            a = _noise(seed, index, 1) * math.tau
            radius = (_noise(seed, index, 2) ** 0.55) * base_width * float(cfg["scatter"]) / 100.0
            size_jitter = (2.0 * _noise(seed, index, 3) - 1.0) * float(cfg["size_jitter"]) / 100.0
            tilt_amount = math.hypot(tx, ty) * float(cfg["tilt_size"]) / 100.0
            dab_size = base_width * max(0.08, (0.18 + local_pressure * 0.82) * (1.0 + size_jitter + tilt_amount))
            texture = 1.0 - float(cfg["texture_strength"]) / 100.0 * _noise(
                seed, int(index * max(0.1, float(cfg["texture_scale"]) / 100.0)), 4
            )
            flow = float(cfg["flow"]) / 100.0 * float(cfg["transfer_flow"]) / 100.0
            flow *= float(cfg["transfer_opacity"]) / 100.0
            flow *= 1.0 + max(0.0, tangential) * float(cfg["barrel_flow"]) / 100.0
            alpha = max(0.0, min(1.0, flow * texture * (0.25 + local_pressure * 0.75)))
            hue = (h + (2.0 * _noise(seed, index, 5) - 1.0) * float(cfg["hue_jitter"]) / 360.0) % 1.0
            sat = max(0.0, min(1.0, s + (2.0 * _noise(seed, index, 6) - 1.0) * float(cfg["saturation_jitter"]) / 100.0))
            val = max(0.0, min(1.0, v + (2.0 * _noise(seed, index, 7) - 1.0) * float(cfg["value_jitter"]) / 100.0))
            rgb = tuple(int(round(channel * 255.0)) for channel in colorsys.hsv_to_rgb(hue, sat, val))
            angle = float(getattr(stroke, "brush_angle", 0.0))
            angle += math.degrees(math.atan2(ty, tx)) * float(cfg["tilt_angle"]) / 100.0 if abs(tx) + abs(ty) > 1e-6 else 0.0
            angle += (rot - 0.5) * 360.0 * float(cfg["rotation_angle"]) / 100.0
            result.append({
                "x": x * width + math.cos(a) * radius,
                "y": y * height + math.sin(a) * radius,
                "size": dab_size,
                "roundness": max(0.1, float(getattr(stroke, "brush_roundness", 100)) / 100.0),
                "angle": angle,
                "alpha": alpha,
                "pressure": local_pressure,
                "rgb": rgb,
            })
    if result:
        from app.painter_advanced_brush import advanced_dab_alphas

        advanced_alpha = advanced_dab_alphas(
            [float(dab["alpha"]) for dab in result],
            cfg,
            stroke_seed=seed,
        )
        for dab, alpha in zip(result, advanced_alpha):
            dab["alpha"] = float(alpha)
    return result


def _sample_color(device: object, x: float, y: float, fallback: QColor) -> QColor:
    if isinstance(device, QImage) and not device.isNull():
        px = max(0, min(device.width() - 1, int(round(x))))
        py = max(0, min(device.height() - 1, int(round(y))))
        sampled = device.pixelColor(px, py)
        if sampled.alpha() > 0:
            return sampled
    return QColor(fallback)


def _sample_radius_color(
    image: QImage | None,
    x: float,
    y: float,
    radius_px: float,
    fallback: QColor,
) -> QColor:
    if not isinstance(image, QImage) or image.isNull():
        return QColor(fallback)
    radius = max(0, min(32, int(round(float(radius_px)))))
    center_x = max(0, min(image.width() - 1, int(round(x))))
    center_y = max(0, min(image.height() - 1, int(round(y))))
    if radius <= 0:
        return _sample_color(image, center_x, center_y, fallback)
    red = green = blue = alpha = count = 0
    radius_squared = radius * radius
    for py in range(max(0, center_y - radius), min(image.height(), center_y + radius + 1)):
        for px in range(max(0, center_x - radius), min(image.width(), center_x + radius + 1)):
            if (px - center_x) ** 2 + (py - center_y) ** 2 > radius_squared:
                continue
            color = image.pixelColor(px, py)
            if color.alpha() <= 0:
                continue
            red += color.red(); green += color.green(); blue += color.blue(); alpha += color.alpha()
            count += 1
    if not count:
        return QColor(fallback)
    return QColor(
        int(round(red / count)),
        int(round(green / count)),
        int(round(blue / count)),
        int(round(alpha / count)),
    )


def _mix_color(first: QColor, second: QColor, second_amount: float) -> QColor:
    amount = max(0.0, min(1.0, float(second_amount)))
    return QColor(
        int(round(first.red() * (1.0 - amount) + second.red() * amount)),
        int(round(first.green() * (1.0 - amount) + second.green() * amount)),
        int(round(first.blue() * (1.0 - amount) + second.blue() * amount)),
        int(round(first.alpha() * (1.0 - amount) + second.alpha() * amount)),
    )


def _captured_dab_image(settings: dict[str, object]) -> QImage | None:
    encoded = str(settings.get("dab_png_base64") or "")
    image = QImage()
    if encoded:
        try:
            decoded = base64.b64decode(encoded, validate=True)
            if not image.loadFromData(decoded, "PNG"):
                raise ValueError("embedded brush dab is not a valid PNG")
        except (TypeError, ValueError):
            image = QImage()
    if image.isNull():
        path = str(settings.get("dab_image_path") or "")
        if path:
            image = QImage(path)
    return image if not image.isNull() else None


def paint_dynamic_stroke(
    painter: QPainter,
    stroke: Any,
    width: int,
    height: int,
    color: QColor,
    *,
    sampling_image: QImage | None = None,
) -> bool:
    cfg = normalize_brush_dynamics(getattr(stroke, "brush_dynamics", {}) or {})
    dabs = dynamic_dabs(stroke, width, height)
    if not dabs:
        return False
    mode = str(cfg["mode"])
    base_opacity = color.alphaF()
    if sampling_image is None:
        device = painter.device()
        sampling_image = QImage(device) if isinstance(device, QImage) else None
    elif not sampling_image.isNull():
        sampling_image = sampling_image.copy()
    carried_color: QColor | None = None
    previous_position: tuple[float, float] | None = None
    captured_dab = _captured_dab_image(cfg)
    frozen_samples = list(cfg.get("sampled_rgba") or [])
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        for dab_index, dab in enumerate(dabs):
            rgb = dab["rgb"]
            dab_color = QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))
            if mode in {"smudge", "pickup", "mixer"}:
                x, y = float(dab["x"]), float(dab["y"])
                sample_x, sample_y = x, y
                if (
                    mode == "smudge"
                    and str(cfg["smudge_type"]) == "smear"
                    and previous_position is not None
                ):
                    sample_x, sample_y = previous_position
                sample_radius = (
                    float(dab["size"]) * 0.5 * float(cfg["smudge_radius"]) / 100.0
                    if str(cfg["smudge_type"]) == "dulling"
                    else 0.0
                )
                if dab_index < len(frozen_samples):
                    row = list(frozen_samples[dab_index])
                    sampled = QColor(*row[:4]) if len(row) >= 4 else QColor(*row[:3])
                else:
                    sampled = _sample_radius_color(
                        sampling_image,
                        sample_x,
                        sample_y,
                        sample_radius,
                        dab_color,
                    )
                if mode == "mixer":
                    mix = float(cfg["mix"]) / 100.0
                    dab_color = _mix_color(dab_color, sampled, mix)
                elif mode == "smudge":
                    retention = float(cfg["smudge_length"]) / 100.0
                    carried_color = (
                        sampled
                        if carried_color is None
                        else _mix_color(sampled, carried_color, retention)
                    )
                    dab_color = _mix_color(
                        carried_color,
                        dab_color,
                        float(cfg["color_rate"]) / 100.0,
                    )
                else:
                    dab_color = sampled
                previous_position = (x, y)
            opacity = base_opacity * float(dab["alpha"])
            if mode in {"smudge", "pickup"}:
                opacity *= max(0.08, float(cfg["pickup"]) / 100.0)
            dab_color.setAlphaF(max(0.0, min(1.0, opacity)))
            painter.save()
            painter.translate(QPointF(float(dab["x"]), float(dab["y"])))
            painter.rotate(float(dab["angle"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dab_color)
            size = float(dab["size"])
            target = QRectF(
                -size * 0.5,
                -size * float(dab["roundness"]) * 0.5,
                size,
                size * float(dab["roundness"]),
            )
            if captured_dab is not None:
                painter.setOpacity(dab_color.alphaF())
                painter.drawImage(target, captured_dab)
                painter.setOpacity(1.0)
            else:
                painter.drawEllipse(target)
            painter.restore()
    finally:
        painter.restore()
    return True


def capture_dynamic_sample_colors(
    stroke: Any,
    width: int,
    height: int,
    sampling_image: QImage,
) -> list[list[int]]:
    """Freeze per-dab sampled RGBA for stable Overlay/current-layer replay."""

    cfg = normalize_brush_dynamics(getattr(stroke, "brush_dynamics", {}) or {})
    if str(cfg["mode"]) not in {"smudge", "mixer", "pickup"}:
        return []
    dabs = dynamic_dabs(stroke, width, height)
    colors: list[list[int]] = []
    previous_position: tuple[float, float] | None = None
    fallback = QColor(*tuple(int(v) for v in getattr(stroke, "color", (255, 50, 50))))
    for dab in dabs:
        x, y = float(dab["x"]), float(dab["y"])
        sample_x, sample_y = x, y
        if (
            str(cfg["mode"]) == "smudge"
            and str(cfg["smudge_type"]) == "smear"
            and previous_position is not None
        ):
            sample_x, sample_y = previous_position
        radius = (
            float(dab["size"]) * 0.5 * float(cfg["smudge_radius"]) / 100.0
            if str(cfg["smudge_type"]) == "dulling"
            else 0.0
        )
        sampled = _sample_radius_color(
            sampling_image, sample_x, sample_y, radius, fallback
        )
        colors.append(list(sampled.getRgb()))
        previous_position = (x, y)
    return colors


def brush_resource_diagnostics(preset: dict[str, object], *, base_dir: str | Path | None = None) -> dict[str, object]:
    dynamics = normalize_brush_dynamics(dict(preset.get("dynamics") or {}))
    path_value = str(dynamics.get("dab_image_path") or "")
    resolved = None
    missing: list[str] = []
    if path_value:
        candidate = Path(path_value)
        if not candidate.is_absolute() and base_dir is not None:
            candidate = Path(base_dir) / candidate
        resolved = candidate.resolve()
        if not resolved.is_file():
            missing.append(str(resolved))
    encoded = str(dynamics.get("dab_png_base64") or "")
    embedded = bool(encoded)
    embedded_valid = False
    if embedded:
        try:
            decoded = base64.b64decode(encoded, validate=True)
            embedded_image = QImage()
            embedded_valid = bool(embedded_image.loadFromData(decoded, "PNG"))
        except (TypeError, ValueError):
            embedded_valid = False
        if not embedded_valid and (resolved is None or not resolved.is_file()):
            missing.append("embedded:dab_png_base64:invalid")
    return {
        "ok": not missing,
        "missing_resources": missing,
        "captured_dab": bool(path_value or embedded),
        "embedded": embedded,
        "embedded_valid": embedded_valid,
        "resolved_dab_path": str(resolved or ""),
    }


def export_brush_bundle(path: str | Path, presets: list[dict[str, object]]) -> dict[str, object]:
    destination = Path(path)
    rows = []
    for preset in presets:
        row = json.loads(json.dumps(preset))
        dynamics = normalize_brush_dynamics(dict(row.get("dynamics") or {}))
        source = str(dynamics.get("dab_image_path") or "")
        if source and Path(source).is_file() and not dynamics.get("dab_png_base64"):
            dynamics["dab_png_base64"] = base64.b64encode(Path(source).read_bytes()).decode("ascii")
            dynamics["dab_image_path"] = ""
        row["dynamics"] = dynamics
        rows.append(row)
    payload = {"schema": "tigerstudio.painter.brush-bundle.v2", "presets": rows}
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(destination), "preset_count": len(rows), "schema": payload["schema"]}


def import_brush_bundle(path: str | Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    source = Path(path)
    if source.suffix.casefold() == ".abr":
        data = source.read_bytes()[:4]
        version = int.from_bytes(data[:2], "big") if len(data) >= 2 else 0
        return [], {
            "ok": False,
            "format": "abr",
            "version": version,
            "scope": "metadata-only",
            "reason": "Proprietary ABR dab decoding is not bundled; export brushes as Tiger JSON with licensed dab PNGs.",
        }
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema") not in {"tigerstudio.painter.brush-bundle.v1", "tigerstudio.painter.brush-bundle.v2"}:
        raise ValueError("Unsupported brush bundle schema")
    rows = [dict(row) for row in payload.get("presets", []) if isinstance(row, dict)]
    for row in rows:
        row["dynamics"] = normalize_brush_dynamics(dict(row.get("dynamics") or {}))
    missing = [item for row in rows for item in brush_resource_diagnostics(row, base_dir=source.parent)["missing_resources"]]
    return rows, {"ok": not missing, "format": "tiger", "preset_count": len(rows), "missing_resources": missing}


__all__ = [
    "BRUSH_DYNAMICS_DEFAULTS", "BRUSH_DYNAMICS_MODEL_CONTRACT",
    "PAINTER_DYNAMIC_DAB_BUDGET",
    "normalize_brush_dynamics", "normalize_pressure_curve",
    "map_pressure", "stabilize_points", "dynamic_dab_workload", "dynamic_dabs", "paint_dynamic_stroke",
    "capture_dynamic_sample_colors",
    "brush_resource_diagnostics", "export_brush_bundle", "import_brush_bundle",
]

"""Deterministic brush dynamics shared by Painter preview/export."""
from __future__ import annotations

import base64
import colorsys
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from app.painter_brush_domains import (
    BRUSH_DETAIL_DEFAULTS,
    BRUSH_WIDTH_DEFAULT_PX,
    normalize_brush_detail_integer,
    normalize_brush_width_px,
)


BRUSH_DYNAMICS_DEFAULTS: dict[str, object] = {
    "enabled": False,
    "flow": 100,
    "buildup": 0,
    "stabilization": 0,
    "pressure_curve": [[0.0, 0.0], [1.0, 1.0]],
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
    "smudge_radius_behavior": "authored_percentage_without_hidden_pixel_cap",
    "smudge_exact_enumeration_radius_max_px": 32,
    "smudge_large_radius_axis_samples": 17,
    "smudge_large_radius_sample_capacity": 289,
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
SMUDGE_EXACT_RADIUS_MAX_PX = 32
SMUDGE_LARGE_RADIUS_AXIS_SAMPLES = 17
UINT64_MAX = (1 << 64) - 1

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
    result["pressure_min"] = min(99, int(result["pressure_min"]))
    result["pressure_max"] = max(
        int(result["pressure_min"]) + 1,
        min(100, int(result["pressure_max"])),
    )
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
            result[key] = int(result.get(key, 0) or 0) & UINT64_MAX
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
        if deduped and deduped[-1][0] == row[0]:
            deduped[-1] = row
        else:
            deduped.append(row)
    return deduped


def map_pressure(value: float, settings: dict[str, object]) -> float:
    cfg = normalize_brush_dynamics(settings)
    return _map_pressure_normalized(value, cfg)


def _map_pressure_normalized(value: float, cfg: dict[str, object]) -> float:
    low = float(cfg["pressure_min"]) / 100.0
    high = float(cfg["pressure_max"]) / 100.0
    x = max(0.0, min(1.0, (float(value) - low) / (high - low)))
    curve = cfg["pressure_curve"]
    for left, right in zip(curve, curve[1:]):
        if x <= right[0]:
            amount = (x - left[0]) / (right[0] - left[0])
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
    alpha = 1.0 - amount
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


@lru_cache(maxsize=1 << 17)
def _noise(seed: int, index: int, channel: int) -> float:
    """Deterministic per-dab randomness.

    The live preview repaints the whole authored prefix on every input sample,
    so the same (seed, index, channel) triples are hashed again several thousand
    times per sample - about half the cost of a dynamic brush stroke.  The
    result only depends on the arguments, so memoising it is byte-identical and
    turns the repeats into dictionary hits.
    """
    payload = b"".join(
        int(value & UINT64_MAX).to_bytes(8, "little", signed=False)
        for value in (seed, index, channel)
    )
    digest = hashlib.blake2b(
        payload,
        digest_size=8,
        person=b"TigerDab",
    ).digest()
    return int.from_bytes(digest, "little", signed=False) / UINT64_MAX


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
    try:
        base_width = normalize_brush_width_px(
            getattr(stroke, "width_px", BRUSH_WIDTH_DEFAULT_PX)
        )
    except (TypeError, ValueError):
        base_width = BRUSH_WIDTH_DEFAULT_PX
    try:
        spacing_percent = normalize_brush_detail_integer(
            getattr(stroke, "brush_spacing", BRUSH_DETAIL_DEFAULTS["spacing"]),
            field="spacing",
        )
    except (TypeError, ValueError):
        spacing_percent = int(BRUSH_DETAIL_DEFAULTS["spacing"])
    try:
        roundness_percent = normalize_brush_detail_integer(
            getattr(stroke, "brush_roundness", BRUSH_DETAIL_DEFAULTS["roundness"]),
            field="roundness",
        )
    except (TypeError, ValueError):
        roundness_percent = int(BRUSH_DETAIL_DEFAULTS["roundness"])
    spacing = base_width * spacing_percent / 100.0
    scatter_count = int(cfg["scatter_count"])
    count = scatter_count + int(
        round(scatter_count * float(cfg["buildup"]) / 100.0)
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
        "roundness": roundness_percent / 100.0,
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


def _walk_dab_samples(
    plan: dict[str, object],
    width: int,
    height: int,
    *,
    first_segment: int = 0,
    carry: float = 0.0,
) -> tuple[list[tuple[float, float, float, float, float, float]], float]:
    """Spacing walk over the segments, resumable from a segment and a carry.

    Returns the samples emitted for those segments and the distance still owed
    to the next dab, so a live stroke can continue the walk when the next input
    sample arrives instead of redoing the whole path.
    """
    points = list(plan["points"])
    pressure = list(plan["pressure"])
    tilt_x = list(plan["tilt_x"])
    tilt_y = list(plan["tilt_y"])
    rotation = list(plan["rotation"])
    barrel = list(plan["barrel"])
    effective_spacing = float(plan["effective_spacing"])
    samples: list[tuple[float, float, float, float, float, float]] = []
    distance_to_next = float(carry)
    for segment in range(first_segment, len(points) - 1):
        first = points[segment]
        second = points[segment + 1]
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
    return samples, distance_to_next


def _final_dab_sample(
    plan: dict[str, object],
) -> tuple[float, float, float, float, float, float]:
    """The cap the walk always appends for the stroke's last authored point."""
    points = list(plan["points"])
    return (
        *points[-1],
        plan["pressure"][-1],
        plan["tilt_x"][-1],
        plan["tilt_y"][-1],
        plan["rotation"][-1],
        plan["barrel"][-1],
    )


def _dab_build_context(stroke: Any, plan: dict[str, object]) -> dict[str, Any]:
    try:
        seed = int(getattr(stroke, "brush_seed", 0) or 0) & UINT64_MAX
    except (TypeError, ValueError, OverflowError):
        seed = 0
    base_rgb = tuple(int(v) for v in getattr(stroke, "color", (255, 50, 50)))
    h, s, v = colorsys.rgb_to_hsv(*(channel / 255.0 for channel in base_rgb))
    return {
        "cfg": dict(plan["cfg"]),
        "base_width": float(plan["base_width"]),
        "roundness": float(plan["roundness"]),
        "count": int(plan["count"]),
        "seed": seed,
        "hsv": (h, s, v),
        "angle": float(getattr(stroke, "brush_angle", 0.0)),
    }


def _dabs_for_samples(
    context: dict[str, Any],
    samples: list[tuple[float, float, float, float, float, float]],
    width: int,
    height: int,
    *,
    first_sample_index: int = 0,
) -> list[dict[str, float | tuple[int, int, int]]]:
    cfg = context["cfg"]
    base_width = float(context["base_width"])
    roundness = float(context["roundness"])
    count = int(context["count"])
    seed = int(context["seed"])
    h, s, v = context["hsv"]
    result = []
    for offset, sample in enumerate(samples):
        sample_index = first_sample_index + offset
        x, y, raw_pressure, tx, ty, rot, tangential = sample
        local_pressure = _map_pressure_normalized(max(0.0, raw_pressure), cfg)
        for copy_index in range(count):
            index = sample_index * count + copy_index
            a = _noise(seed, index, 1) * math.tau
            radius = math.sqrt(_noise(seed, index, 2)) * base_width * float(cfg["scatter"]) / 100.0
            size_jitter = (2.0 * _noise(seed, index, 3) - 1.0) * float(cfg["size_jitter"]) / 100.0
            tilt_amount = math.hypot(tx, ty) * float(cfg["tilt_size"]) / 100.0
            dab_size = base_width * max(
                0.0,
                local_pressure * (1.0 + size_jitter + tilt_amount),
            )
            texture = 1.0 - float(cfg["texture_strength"]) / 100.0 * _noise(
                seed, int(index * float(cfg["texture_scale"]) / 100.0), 4
            )
            flow = float(cfg["flow"]) / 100.0 * float(cfg["transfer_flow"]) / 100.0
            flow *= float(cfg["transfer_opacity"]) / 100.0
            flow *= 1.0 + max(0.0, tangential) * float(cfg["barrel_flow"]) / 100.0
            alpha = max(0.0, min(1.0, flow * texture * local_pressure))
            hue = (h + (2.0 * _noise(seed, index, 5) - 1.0) * float(cfg["hue_jitter"]) / 360.0) % 1.0
            sat = max(0.0, min(1.0, s + (2.0 * _noise(seed, index, 6) - 1.0) * float(cfg["saturation_jitter"]) / 100.0))
            val = max(0.0, min(1.0, v + (2.0 * _noise(seed, index, 7) - 1.0) * float(cfg["value_jitter"]) / 100.0))
            rgb = tuple(int(round(channel * 255.0)) for channel in colorsys.hsv_to_rgb(hue, sat, val))
            angle = float(context["angle"])
            angle += math.degrees(math.atan2(ty, tx)) * float(cfg["tilt_angle"]) / 100.0 if tx != 0.0 or ty != 0.0 else 0.0
            angle += (rot - 0.5) * 360.0 * float(cfg["rotation_angle"]) / 100.0
            result.append({
                "x": x * width + math.cos(a) * radius,
                "y": y * height + math.sin(a) * radius,
                "size": dab_size,
                "roundness": roundness,
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


def dynamic_dabs(
    stroke: Any,
    width: int,
    height: int,
) -> list[dict[str, float | tuple[int, int, int]]]:
    plan = _dynamic_dab_plan(stroke, width, height)
    if not bool(plan.get("enabled", False)):
        return []
    points = list(plan["points"])
    max_path_samples = int(plan["max_path_samples"])
    if len(points) == 1:
        samples = [_final_dab_sample(plan)]
    else:
        samples, _carry = _walk_dab_samples(plan, width, height)
        samples.append(_final_dab_sample(plan))
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
    return _dabs_for_samples(
        _dab_build_context(stroke, plan),
        samples,
        width,
        height,
    )


class DynamicDabStream:
    """Resumable dab generation for the stroke currently being drawn.

    The live preview used to clear its image and repaint every dab of the stroke
    on every input sample, which is quadratic in stroke length.  The dab
    sequence is prefix-stable - ``stabilize_points`` is deliberately causal and
    the spacing walk only carries a distance forward - so everything except the
    cap dabs at the stroke's last authored point can be painted once and left
    alone.

    ``update`` returns ``(new_stable_dabs, cap_dabs)``: the first are appended to
    the live image, the second are drawn on top of it each frame because they
    move with the pointer.  It returns ``None`` when the stroke cannot be
    extended this way, and the caller must fall back to a full repaint.
    """

    def __init__(self) -> None:
        self._signature: tuple[Any, ...] | None = None
        self._segment = 0
        self._carry = 0.0
        self._stable_samples = 0
        self._context: dict[str, Any] | None = None

    def reset(self) -> None:
        self._signature = None
        self._segment = 0
        self._carry = 0.0
        self._stable_samples = 0
        self._context = None

    @property
    def stable_dab_count(self) -> int:
        if self._context is None:
            return 0
        return self._stable_samples * int(self._context["count"])

    def update(
        self,
        stroke: Any,
        width: int,
        height: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
        from app.painter_advanced_brush import advanced_dab_alphas_prefix_stable

        plan = _dynamic_dab_plan(stroke, width, height)
        if not bool(plan.get("enabled", False)):
            return None
        cfg = dict(plan["cfg"])
        if str(cfg["mode"]) != "paint":
            # Smudge, mixer and pickup carry colour between dabs and sample the
            # canvas underneath, so a dab cannot be replayed out of context.
            return None
        if not advanced_dab_alphas_prefix_stable(cfg):
            return None
        if bool(dict(plan["workload"])["degraded"]):
            # Over budget the walk is resampled against the whole path, so
            # earlier dabs move as the stroke grows.
            return None
        points = list(plan["points"])
        if len(points) < 2:
            return None
        for key in ("pressure", "tilt_x", "tilt_y", "rotation", "barrel"):
            if len(plan[key]) != len(points):
                # ``_curve`` resampled a per-point channel, so every value
                # shifts when the point count changes.
                return None
        signature = (
            id(stroke),
            int(width),
            int(height),
            tuple(sorted((str(key), repr(value)) for key, value in cfg.items())),
            float(plan["base_width"]),
            float(plan["roundness"]),
            int(plan["count"]),
            float(plan["effective_spacing"]),
            int(plan["max_path_samples"]),
            int(getattr(stroke, "brush_seed", 0) or 0),
            tuple(int(v) for v in getattr(stroke, "color", (255, 50, 50))),
            float(getattr(stroke, "brush_angle", 0.0)),
        )
        if signature != self._signature:
            self.reset()
            self._signature = signature
            self._context = _dab_build_context(stroke, plan)
        context = self._context
        if context is None:
            return None
        if self._segment > len(points) - 1:
            return None
        fresh_samples, carry = _walk_dab_samples(
            plan,
            width,
            height,
            first_segment=self._segment,
            carry=self._carry,
        )
        self._segment = len(points) - 1
        self._carry = carry
        first_sample_index = self._stable_samples
        stable = _dabs_for_samples(
            context,
            fresh_samples,
            width,
            height,
            first_sample_index=first_sample_index,
        )
        self._stable_samples += len(fresh_samples)
        cap = _dabs_for_samples(
            context,
            [_final_dab_sample(plan)],
            width,
            height,
            first_sample_index=self._stable_samples,
        )
        if (self._stable_samples + 1) > int(plan["max_path_samples"]):
            return None
        return stable, cap


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
    radius = max(0, int(round(float(radius_px))))
    center_x = max(0, min(image.width() - 1, int(round(x))))
    center_y = max(0, min(image.height() - 1, int(round(y))))
    if radius <= 0:
        return _sample_color(image, center_x, center_y, fallback)
    red = green = blue = alpha = count = 0
    for px, py in _smudge_sample_pixels(
        image.width(), image.height(), center_x, center_y, radius
    ):
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


def _smudge_sample_pixels(
    width: int,
    height: int,
    center_x: int,
    center_y: int,
    radius: int,
) -> list[tuple[int, int]]:
    """Cover the authored radius with exact or bounded deterministic samples."""

    radius = max(0, int(radius))
    radius_squared = radius * radius
    if radius <= SMUDGE_EXACT_RADIUS_MAX_PX:
        return [
            (px, py)
            for py in range(max(0, center_y - radius), min(height, center_y + radius + 1))
            for px in range(max(0, center_x - radius), min(width, center_x + radius + 1))
            if (px - center_x) ** 2 + (py - center_y) ** 2 <= radius_squared
        ]
    axis_last = SMUDGE_LARGE_RADIUS_AXIS_SAMPLES - 1
    pixels: set[tuple[int, int]] = set()
    for row in range(SMUDGE_LARGE_RADIUS_AXIS_SAMPLES):
        py = center_y - radius + int(round(2 * radius * row / axis_last))
        if py < 0 or py >= height:
            continue
        for column in range(SMUDGE_LARGE_RADIUS_AXIS_SAMPLES):
            px = center_x - radius + int(round(2 * radius * column / axis_last))
            if px < 0 or px >= width:
                continue
            if (px - center_x) ** 2 + (py - center_y) ** 2 <= radius_squared:
                pixels.add((px, py))
    return sorted(pixels, key=lambda point: (point[1], point[0]))


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
    return paint_dynamic_dabs(
        painter,
        dabs,
        cfg,
        color,
        sampling_image=sampling_image,
    )


def paint_dynamic_dabs(
    painter: QPainter,
    dabs: list[dict[str, Any]],
    cfg: dict[str, Any],
    color: QColor,
    *,
    sampling_image: QImage | None = None,
) -> bool:
    """Paint an already-generated dab sequence.

    Split out of ``paint_dynamic_stroke`` so a live stroke can paint only the
    dabs it has not painted yet through exactly the same code.
    """
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
                opacity *= float(cfg["pickup"]) / 100.0
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

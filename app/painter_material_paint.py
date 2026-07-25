"""Stroke-native material channels for Tiger Studio Painter."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

import numpy as np


STANDARD_LAYER_TYPE = "standard"
MATERIAL_LAYER_TYPE = "material"
MATERIAL_PAINT_SCHEMA = "tigerstudio.painter.material_paint.v1"

MATERIAL_PAINT_DEFAULTS: dict[str, float] = {
    "load": 0.78,
    "thickness": 0.62,
    "wetness": 0.34,
    "gloss": 0.28,
    "roughness": 0.56,
}

MATERIAL_COMPATIBLE_STYLES = frozenset(
    {
        "loaded_oil",
        "impasto_oil",
        "oil_smear",
        "soft_oil_glaze",
        "real_wet_oil",
        "bristle_oil",
        "dry_oil",
        "palette_knife",
        "filbert_oil",
        "flat_hog_oil",
        "fan_bristle_oil",
        "rigger_oil",
        "scumble_oil",
        "stipple_oil",
        "knife_scrape_oil",
        "acrylic_bristle",
        "gouache_flat",
    }
)

_STYLE_THICKNESS = {
    "impasto_oil": 1.35,
    "loaded_oil": 1.18,
    "palette_knife": 1.30,
    "knife_scrape_oil": 1.12,
    "bristle_oil": 1.08,
    "flat_hog_oil": 1.08,
    "filbert_oil": 1.02,
    "fan_bristle_oil": 0.92,
    "rigger_oil": 0.78,
    "real_wet_oil": 0.82,
    "soft_oil_glaze": 0.42,
    "oil_smear": 0.56,
    "dry_oil": 0.72,
    "scumble_oil": 0.68,
    "stipple_oil": 0.76,
}


def normalize_layer_type(value: Any) -> str:
    key = str(value or STANDARD_LAYER_TYPE).strip().casefold().replace("-", "_")
    if key in {"material", "material_paint", "thick", "thick_paint", "pbr"}:
        return MATERIAL_LAYER_TYPE
    return STANDARD_LAYER_TYPE


def normalize_material_settings(
    value: Mapping[str, Any] | None,
) -> dict[str, float]:
    source = dict(value or {})
    out: dict[str, float] = {}
    for key, default in MATERIAL_PAINT_DEFAULTS.items():
        try:
            number = float(source.get(key, default))
        except (TypeError, ValueError):
            number = default
        out[key] = max(0.0, min(1.0, number))
    return out


def brush_material_capability(style: Any) -> dict[str, Any]:
    brush_style = str(style or "round").strip().casefold()
    compatible = brush_style in MATERIAL_COMPATIBLE_STYLES
    profile = normalize_material_settings(None)
    factor = float(_STYLE_THICKNESS.get(brush_style, 0.62 if compatible else 0.38))
    profile["thickness"] = max(0.0, min(1.0, profile["thickness"] * factor))
    if brush_style in {"real_wet_oil", "oil_smear", "soft_oil_glaze"}:
        profile["wetness"] = max(profile["wetness"], 0.68)
        profile["roughness"] = min(profile["roughness"], 0.38)
    if brush_style in {"dry_oil", "scumble_oil", "stipple_oil"}:
        profile["wetness"] = min(profile["wetness"], 0.14)
        profile["roughness"] = max(profile["roughness"], 0.72)
    return {
        "schema": MATERIAL_PAINT_SCHEMA,
        "style": brush_style,
        "compatible": bool(compatible),
        "profile": profile,
        "fallback": "simple_relief" if not compatible else "",
    }


def _value(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


def material_layer_specs(layers: Sequence[Any]) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for layer in layers:
        layer_id = str(_value(layer, "layer_id", "") or "")
        if not layer_id:
            continue
        specs[layer_id] = {
            "layer_type": normalize_layer_type(_value(layer, "layer_type", "standard")),
            "visible": bool(_value(layer, "visible", True)),
            "opacity": max(0.0, min(1.0, float(_value(layer, "opacity", 100) or 0) / 100.0)),
            "settings": normalize_material_settings(_value(layer, "material_settings", {})),
        }
    return specs


def has_material_strokes(strokes: Sequence[Any], layers: Sequence[Any]) -> bool:
    specs = material_layer_specs(layers)
    for stroke in strokes:
        layer_id = str(_value(stroke, "layer_id", "") or "paint-layer-1")
        layer = specs.get(layer_id)
        if (
            layer
            and layer["layer_type"] == MATERIAL_LAYER_TYPE
            and layer["visible"]
            and bool(_value(stroke, "material_enabled", False))
        ):
            return True
    return False


def material_paint_signature(
    strokes: Sequence[Any],
    layers: Sequence[Any],
    *,
    width: int,
    height: int,
    time_ms: int = 0,
    light_azimuth_deg: float = -38.0,
    light_elevation_deg: float = 48.0,
) -> str:
    specs = material_layer_specs(layers)
    rows = []
    for stroke in strokes:
        layer_id = str(_value(stroke, "layer_id", "") or "paint-layer-1")
        layer = specs.get(layer_id)
        if not layer or layer["layer_type"] != MATERIAL_LAYER_TYPE:
            continue
        rows.append(
            {
                "layer": layer_id,
                "points": list(_value(stroke, "points", []) or []),
                "width": float(_value(stroke, "width_px", 1.0) or 1.0),
                "style": str(_value(stroke, "brush_style", "round") or "round"),
                "enabled": bool(_value(stroke, "material_enabled", False)),
                "engine": int(_value(stroke, "brush_engine_version", 1) or 1),
                "pressure": list(_value(stroke, "point_pressure", []) or []),
                "tilt": list(_value(stroke, "point_tilt", []) or []),
                "tilt_x": list(_value(stroke, "point_tilt_x", []) or []),
                "tilt_y": list(_value(stroke, "point_tilt_y", []) or []),
                "rotation": list(_value(stroke, "point_rotation", []) or []),
                "tangential_pressure": list(
                    _value(stroke, "point_tangential_pressure", []) or []
                ),
                "point_load": list(_value(stroke, "point_load", []) or []),
                "bristles": int(_value(stroke, "bristle_count", 0) or 0),
                "seed": int(_value(stroke, "brush_seed", 0) or 0),
                "depletion": float(_value(stroke, "load_depletion", 0.28) or 0.0),
                "load": float(_value(stroke, "material_load", layer["settings"]["load"])),
                "thickness": float(
                    _value(stroke, "material_thickness", layer["settings"]["thickness"])
                ),
                "wetness": float(_value(stroke, "material_wetness", layer["settings"]["wetness"])),
                "gloss": float(_value(stroke, "material_gloss", layer["settings"]["gloss"])),
                "roughness": float(
                    _value(stroke, "material_roughness", layer["settings"]["roughness"])
                ),
            }
        )
    payload = {
        "size": [int(width), int(height)],
        "time_ms": int(time_ms),
        "light": [float(light_azimuth_deg), float(light_elevation_deg)],
        "layers": specs,
        "strokes": rows,
    }
    return hashlib.blake2b(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        digest_size=16,
    ).hexdigest()


def _draw_polyline(mask: np.ndarray, points: list[tuple[int, int]], width: int) -> None:
    if not points:
        return
    try:
        import cv2

        if len(points) == 1:
            cv2.circle(mask, points[0], max(1, width // 2), 1.0, -1, lineType=cv2.LINE_AA)
        else:
            cv2.polylines(
                mask,
                [np.asarray(points, dtype=np.int32)],
                False,
                1.0,
                max(1, int(width)),
                lineType=cv2.LINE_AA,
            )
        return
    except Exception:
        pass
    from PIL import Image, ImageDraw

    image = Image.fromarray(np.uint8(np.clip(mask, 0.0, 1.0) * 255), mode="L")
    draw = ImageDraw.Draw(image)
    if len(points) == 1:
        x, y = points[0]
        radius = max(1, width // 2)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    else:
        draw.line(points, fill=255, width=max(1, int(width)), joint="curve")
    mask[:] = np.asarray(image, dtype=np.float32) / 255.0


def _draw_weighted_segment(
    mask: np.ndarray,
    first: tuple[int, int],
    second: tuple[int, int],
    width: int,
    value: float,
) -> None:
    value = max(0.0, min(1.0, float(value)))
    try:
        import cv2

        cv2.line(
            mask,
            first,
            second,
            value,
            max(1, int(width)),
            lineType=cv2.LINE_AA,
        )
        return
    except Exception:
        pass
    segment = np.zeros_like(mask)
    _draw_polyline(segment, [first, second], width)
    np.maximum(mask, segment * value, out=mask)


def _blur(values: np.ndarray, radius: float) -> np.ndarray:
    try:
        import cv2

        sigma = max(0.1, float(radius))
        return cv2.GaussianBlur(values, (0, 0), sigmaX=sigma, sigmaY=sigma)
    except Exception:
        return values


def _shift_clamped(values: np.ndarray, dx: int, dy: int) -> np.ndarray:
    height, width = values.shape[:2]
    pad_x = abs(int(dx))
    pad_y = abs(int(dy))
    padded = np.pad(values, ((pad_y, pad_y), (pad_x, pad_x)), mode="edge")
    start_x = pad_x - int(dx)
    start_y = pad_y - int(dy)
    return padded[start_y : start_y + height, start_x : start_x + width]


def rasterize_material_channels(
    strokes: Sequence[Any],
    layers: Sequence[Any],
    *,
    width: int,
    height: int,
    time_ms: int = 0,
    light_azimuth_deg: float = -38.0,
    light_elevation_deg: float = 48.0,
) -> dict[str, Any]:
    width = max(8, int(width))
    height = max(8, int(height))
    specs = material_layer_specs(layers)
    relief = np.zeros((height, width), dtype=np.float32)
    coverage = np.zeros_like(relief)
    roughness_sum = np.zeros_like(relief)
    roughness_weight = np.zeros_like(relief)
    direction_x = np.zeros_like(relief)
    direction_y = np.zeros_like(relief)
    stroke_count = 0
    profile_counts: dict[str, int] = {}

    for stroke in strokes:
        layer_id = str(_value(stroke, "layer_id", "") or "paint-layer-1")
        layer = specs.get(layer_id)
        if not layer or layer["layer_type"] != MATERIAL_LAYER_TYPE or not layer["visible"]:
            continue
        if not bool(_value(stroke, "material_enabled", False)):
            continue
        start_ms = int(_value(stroke, "start_ms", 0) or 0)
        end_ms = _value(stroke, "end_ms", None)
        if int(time_ms) < start_ms or (end_ms is not None and int(time_ms) >= int(end_ms)):
            continue
        normalized_points = list(_value(stroke, "points", []) or [])
        points = [
            (
                max(0, min(width - 1, int(round(float(point[0]) * (width - 1))))),
                max(0, min(height - 1, int(round(float(point[1]) * (height - 1))))),
            )
            for point in normalized_points
            if isinstance(point, (list, tuple)) and len(point) >= 2
        ]
        if not points:
            continue
        settings = layer["settings"]
        load = max(0.0, min(1.0, float(_value(stroke, "material_load", settings["load"]))))
        thickness = max(
            0.0,
            min(1.0, float(_value(stroke, "material_thickness", settings["thickness"]))),
        )
        wetness = max(
            0.0,
            min(1.0, float(_value(stroke, "material_wetness", settings["wetness"]))),
        )
        gloss = max(0.0, min(1.0, float(_value(stroke, "material_gloss", settings["gloss"]))))
        authored_roughness = max(
            0.04,
            min(1.0, float(_value(stroke, "material_roughness", settings["roughness"]))),
        )
        style = str(_value(stroke, "brush_style", "round") or "round").casefold()
        profile_counts[style] = int(profile_counts.get(style, 0)) + 1
        width_px = max(1, int(round(float(_value(stroke, "width_px", 1.0) or 1.0))))
        opacity = max(0.0, min(1.0, float(_value(stroke, "opacity", 255) or 0) / 255.0))
        deposition = (
            thickness
            * load
            * opacity
            * layer["opacity"]
            * float(_STYLE_THICKNESS.get(style, 0.72))
        )
        if deposition <= 0.0001:
            continue

        mask = np.zeros_like(relief)
        burial_mask: np.ndarray | None = None
        direction_written = False
        from app.painter_brush_engine_v2 import (
            bristle_lane_paths,
            normalize_curve,
            normalize_signed_curve,
            stipple_dabs,
            stroke_uses_bristle_v2,
        )
        point_count = len(points)
        pressure_curve = normalize_curve(
            _value(stroke, "point_pressure", []) or [],
            point_count,
            1.0,
        )
        tilt_x_curve = normalize_signed_curve(
            _value(stroke, "point_tilt_x", []) or [],
            point_count,
        )
        tilt_y_curve = normalize_signed_curve(
            _value(stroke, "point_tilt_y", []) or [],
            point_count,
        )
        dynamic_points = [
            (
                max(0, min(width - 1, int(round(point[0] + tilt_x_curve[index] * width_px * 0.10)))),
                max(0, min(height - 1, int(round(point[1] + tilt_y_curve[index] * width_px * 0.10)))),
            )
            for index, point in enumerate(points)
        ]
        dynamic_widths = [
            max(
                1,
                int(
                    round(
                        width_px
                        * (0.18 + pressure_curve[index] * 0.82)
                        * (
                            1.0
                            + min(
                                1.0,
                                math.hypot(tilt_x_curve[index], tilt_y_curve[index]),
                            )
                            * 0.24
                        )
                    )
                ),
            )
            for index in range(point_count)
        ]

        if style == "stipple_oil":
            brush_seed = int(_value(stroke, "brush_seed", 0) or 0)
            for x, y, radius_x, radius_y, angle in stipple_dabs(
                stroke,
                width=width - 1,
                height=height - 1,
            ):
                half_length = max(0.5, radius_x * 0.46)
                first = (
                    max(0, min(width - 1, int(round(x - math.cos(angle) * half_length)))),
                    max(0, min(height - 1, int(round(y - math.sin(angle) * half_length)))),
                )
                second = (
                    max(0, min(width - 1, int(round(x + math.cos(angle) * half_length)))),
                    max(0, min(height - 1, int(round(y + math.sin(angle) * half_length)))),
                )
                _draw_weighted_segment(
                    mask,
                    first,
                    second,
                    max(1, int(round(radius_y * 2.0))),
                    0.72 + 0.18 * math.sin(brush_seed * 0.11 + x * 0.07 + y * 0.05),
                )
            direction_written = True
        elif style in {"palette_knife", "knife_scrape_oil"}:
            _draw_polyline(mask, points, max(2, int(round(width_px * 0.94))))
        elif stroke_uses_bristle_v2(stroke):
            lanes = bristle_lane_paths(stroke, width=width - 1, height=height - 1)
            lane_width = max(1, int(round(width_px / max(5, len(lanes)) * 0.92)))
            if style not in {"dry_oil", "scumble_oil", "fan_bristle_oil"}:
                for first, second in zip(points, points[1:]):
                    _draw_weighted_segment(
                        mask,
                        first,
                        second,
                        max(1, int(round(width_px * 0.70))),
                        0.34,
                    )
            for lane in lanes:
                for first, second in zip(lane, lane[1:]):
                    x1, y1, pressure_a, load_a = first
                    x2, y2, pressure_b, load_b = second
                    lane_deposit = max(
                        0.04,
                        min(1.0, (pressure_a + pressure_b) * 0.25 + (load_a + load_b) * 0.25),
                    )
                    segment_points = [
                        (
                            max(0, min(width - 1, int(round(x1)))),
                            max(0, min(height - 1, int(round(y1)))),
                        ),
                        (
                            max(0, min(width - 1, int(round(x2)))),
                            max(0, min(height - 1, int(round(y2)))),
                        ),
                    ]
                    _draw_weighted_segment(
                        mask,
                        segment_points[0],
                        segment_points[1],
                        lane_width,
                        lane_deposit,
                    )
            if lanes and lanes[0]:
                dx = float(lanes[0][-1][0] - lanes[0][0][0])
                dy = float(lanes[0][-1][1] - lanes[0][0][1])
                length = max(1.0, math.hypot(dx, dy))
                direction_x += mask * (dx / length)
                direction_y += mask * (dy / length)
            direction_written = True
        else:
            if len(dynamic_points) == 1:
                _draw_polyline(mask, dynamic_points, dynamic_widths[0])
            else:
                for index, (first, second) in enumerate(
                    zip(dynamic_points, dynamic_points[1:])
                ):
                    _draw_weighted_segment(
                        mask,
                        first,
                        second,
                        max(1, int(round((dynamic_widths[index] + dynamic_widths[index + 1]) * 0.5))),
                        1.0,
                    )

        if style in {"loaded_oil", "impasto_oil"}:
            body = np.zeros_like(relief)
            _draw_polyline(body, points, max(2, int(round(width_px * 0.82))))
            burial_mask = body
            rounded_body = _blur(body, max(0.9, width_px * 0.085))
            bristle_deposit = np.clip(mask, 0.0, 1.0)
            mask = np.clip(
                rounded_body * (0.38 if style == "impasto_oil" else 0.48)
                + bristle_deposit * (0.82 if style == "impasto_oil" else 0.64),
                0.0,
                1.0,
            )
        elif style in {"palette_knife", "knife_scrape_oil"}:
            body = np.zeros_like(relief)
            _draw_polyline(body, points, max(2, int(round(width_px * 0.94))))
            plateau = _blur(body, max(0.55, width_px * 0.028))
            plateau = np.clip((plateau - 0.12) * 1.28, 0.0, 1.0)
            burial_mask = plateau
            mask = np.clip(plateau + mask * 0.12, 0.0, 1.0)
        elif (
            not stroke_uses_bristle_v2(stroke)
            and style in {"bristle_oil", "flat_hog_oil", "filbert_oil", "fan_bristle_oil"}
        ):
            ridge = np.zeros_like(relief)
            for offset_ratio in (-0.30, -0.10, 0.12, 0.31):
                shifted = [
                    (x, max(0, min(height - 1, int(round(y + width_px * offset_ratio)))))
                    for x, y in points
                ]
                _draw_polyline(ridge, shifted, max(1, width_px // 9))
            mask = np.clip(mask * 0.62 + ridge * 0.62, 0.0, 1.0)
        elif style in {"dry_oil", "scumble_oil"}:
            yy, xx = np.indices(mask.shape)
            grain = (
                np.sin(xx * 0.47 + yy * 0.19 + stroke_count * 1.7) * 0.5 + 0.5
            ).astype(np.float32)
            mask *= np.clip((grain - 0.22) * 1.35, 0.0, 1.0)
        elif style == "stipple_oil":
            mask = np.clip(mask, 0.0, 1.0)

        # Fresh opaque paint buries the older surface instead of adding its
        # normals forever. Without this, underpaint ridges visibly continue
        # through a thick later stroke as if the top color were transparent.
        burial_strength = min(
            0.97,
            opacity
            * layer["opacity"]
            * max(0.0, min(1.0, deposition))
            * (
                0.96
                if style in {"impasto_oil", "loaded_oil"}
                else 0.88
                if style in {"palette_knife", "knife_scrape_oil"}
                else 0.72
            ),
        )
        burial = np.clip(
            (burial_mask if burial_mask is not None else mask) * burial_strength,
            0.0,
            0.97,
        )
        relief *= 1.0 - burial
        relief += mask * deposition * 0.24
        coverage = np.maximum(coverage, mask * opacity * layer["opacity"])
        style_roughness = {
            "impasto_oil": 0.04,
            "loaded_oil": 0.02,
            "palette_knife": 0.07,
            "knife_scrape_oil": 0.12,
            "stipple_oil": 0.16,
            "dry_oil": 0.18,
            "scumble_oil": 0.20,
        }.get(style, 0.08)
        surface_roughness = np.clip(
            authored_roughness + (1.0 - load) * 0.12 - wetness * 0.22 - gloss * 0.30,
            0.04,
            1.0,
        )
        local_roughness = np.clip(
            float(surface_roughness)
            + style_roughness
            + (1.0 - mask) * 0.10
            - mask * wetness * 0.09,
            0.04,
            1.0,
        )
        roughness_sum += mask * local_roughness
        roughness_weight += mask

        if not direction_written:
            for index, (first, second) in enumerate(
                zip(dynamic_points, dynamic_points[1:])
            ):
                dx = float(second[0] - first[0])
                dy = float(second[1] - first[1])
                length = max(1.0, math.hypot(dx, dy))
                segment = np.zeros_like(relief)
                _draw_polyline(
                    segment,
                    [first, second],
                    max(
                        1,
                        int(
                            round(
                                (dynamic_widths[index] + dynamic_widths[index + 1])
                                * 0.5
                            )
                        ),
                    ),
                )
                direction_x += segment * (dx / length)
                direction_y += segment * (dy / length)
        stroke_count += 1

    relief = np.clip(1.0 - np.exp(-np.maximum(relief, 0.0) * 1.16), 0.0, 1.0)
    coverage = np.clip(coverage, 0.0, 1.0)
    roughness = np.where(
        roughness_weight > 1e-5,
        roughness_sum / np.maximum(roughness_weight, 1e-5),
        0.72,
    ).astype(np.float32)
    grad_y, grad_x = np.gradient(relief)
    normal_strength = 9.2
    nx = -grad_x * normal_strength
    ny = grad_y * normal_strength
    nz = np.ones_like(relief)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack((nx / norm, ny / norm, nz / norm), axis=2)
    normal = np.clip(normal * 0.5 + 0.5, 0.0, 1.0).astype(np.float32)

    local = _blur(relief, max(1.0, min(width, height) / 180.0))
    concavity = np.clip(local - relief, 0.0, 1.0)
    ao = np.clip(1.0 - concavity * 5.5, 0.0, 1.0).astype(np.float32)

    azimuth = math.radians(float(light_azimuth_deg))
    elevation = math.radians(max(5.0, min(85.0, float(light_elevation_deg))))
    light = np.asarray(
        [
            math.cos(elevation) * math.cos(azimuth),
            math.cos(elevation) * math.sin(azimuth),
            math.sin(elevation),
        ],
        dtype=np.float32,
    )
    signed_normal = normal * 2.0 - 1.0
    diffuse = np.clip(np.sum(signed_normal * light[None, None, :], axis=2), 0.0, 1.0)
    half_vector = light + np.asarray([0.0, 0.0, 1.0], dtype=np.float32)
    half_vector /= max(0.0001, float(np.linalg.norm(half_vector)))
    normal_dot_half = np.clip(
        np.sum(signed_normal * half_vector[None, None, :], axis=2),
        0.0,
        1.0,
    )
    specular_power = 7.0 + np.square(1.0 - roughness) * 72.0
    specular = (
        np.power(normal_dot_half, specular_power)
        * (1.0 - roughness)
        * 0.72
    )
    soft_shadow = np.zeros_like(relief)
    for distance in (2, 4, 7, 11):
        dx = int(round(-float(light[0]) * distance))
        dy = int(round(-float(light[1]) * distance))
        blocker = _shift_clamped(relief, dx, dy)
        clearance = float(distance) * 0.006 / max(0.18, float(light[2]))
        soft_shadow = np.maximum(soft_shadow, blocker - relief - clearance)
    soft_shadow = np.clip(
        _blur(soft_shadow, max(0.8, min(width, height) / 360.0)) * 4.6,
        0.0,
        1.0,
    )
    shading = np.clip(
        0.72
        + diffuse * 0.34
        + specular
        - soft_shadow * 0.43
        - (1.0 - ao) * 0.18,
        0.38,
        1.34,
    )

    return {
        "schema": MATERIAL_PAINT_SCHEMA,
        "size": [width, height],
        "stroke_count": int(stroke_count),
        "style_profiles": profile_counts,
        "active": bool(stroke_count),
        "height": relief,
        "coverage": coverage,
        "normal": normal,
        "roughness": roughness,
        "ao": ao,
        "direction": np.stack((direction_x, direction_y), axis=2),
        "shading": shading.astype(np.float32),
        "soft_shadow": soft_shadow.astype(np.float32),
        "light": {
            "azimuth_deg": float(light_azimuth_deg),
            "elevation_deg": float(light_elevation_deg),
        },
    }


def material_preview_rgba(channels: Mapping[str, Any]) -> np.ndarray:
    shading = np.asarray(channels.get("shading"), dtype=np.float32)
    coverage = np.asarray(channels.get("coverage"), dtype=np.float32)
    if shading.ndim != 2 or coverage.shape != shading.shape:
        return np.zeros((8, 8, 4), dtype=np.uint8)
    delta = np.where(np.abs(shading - 1.0) < 0.025, 0.0, shading - 1.0)
    light = np.clip(delta, 0.0, 1.0)
    shadow = np.clip(-delta, 0.0, 1.0)
    rgba = np.zeros((shading.shape[0], shading.shape[1], 4), dtype=np.uint8)
    white = light >= shadow
    rgba[..., :3] = np.where(white[..., None], 255, 0).astype(np.uint8)
    alpha = np.maximum(light * 0.84, shadow * 0.82) * coverage
    rgba[..., 3] = np.uint8(np.clip(alpha * 255.0, 0.0, 255.0))
    return rgba


def merge_material_channels_into_generated(
    generated: Mapping[str, Any],
    channels: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(generated)
    maps = dict(result.get("maps") or {})
    material_height = np.asarray(channels.get("height"), dtype=np.float32)
    coverage = np.asarray(channels.get("coverage"), dtype=np.float32)
    if material_height.ndim != 2 or coverage.shape != material_height.shape:
        return result
    mask = np.clip(coverage, 0.0, 1.0)

    existing_height = np.asarray(maps.get("height", np.zeros_like(material_height)), dtype=np.float32)
    if existing_height.shape == material_height.shape:
        maps["height"] = np.clip(
            existing_height * (1.0 - mask * 0.72) + material_height * mask,
            0.0,
            1.0,
        )
    maps["normal"] = _blend_map(maps.get("normal"), channels.get("normal"), mask, channels=3)
    maps["roughness"] = _blend_map(
        maps.get("roughness"), channels.get("roughness"), mask, channels=1
    )
    material_ao = np.asarray(channels.get("ao"), dtype=np.float32)
    existing_ao = np.asarray(maps.get("ao", np.ones_like(material_ao)), dtype=np.float32)
    if existing_ao.shape == material_ao.shape:
        maps["ao"] = np.clip(existing_ao * (1.0 - mask + material_ao * mask), 0.0, 1.0)
    result["maps"] = maps
    result["material_paint"] = {
        "schema": MATERIAL_PAINT_SCHEMA,
        "native_channels": True,
        "stroke_count": int(channels.get("stroke_count", 0) or 0),
        "channels": ["height", "normal", "roughness", "ao", "direction"],
        "fallback_rgb_inference_preserved_outside_material_coverage": True,
    }
    return result


def _blend_map(existing: Any, authored: Any, mask: np.ndarray, *, channels: int) -> np.ndarray:
    authored_array = np.asarray(authored, dtype=np.float32)
    if channels == 3:
        blend = mask[..., None]
    else:
        blend = mask
    if existing is None:
        return authored_array
    existing_array = np.asarray(existing, dtype=np.float32)
    if existing_array.shape != authored_array.shape:
        return authored_array
    return np.clip(existing_array * (1.0 - blend) + authored_array * blend, 0.0, 1.0)

"""Stroke-native material channels for Tiger Studio Painter."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

import numpy as np

from app.painter_legacy_brush import deterministic_unit
from app.painter_dimensions import positive_integer, positive_real


STANDARD_LAYER_TYPE = "standard"
MATERIAL_LAYER_TYPE = "material"
MATERIAL_PAINT_SCHEMA = "tigerstudio.painter.material_paint.v1"
MATERIAL_PAINT_MODEL_CONTRACT = {
    "schema": "tigerstudio.painter.material_model.v1",
    "model": "tiger_authored_deterministic_stylized_relief_v1",
    "coefficient_source": "authored_product_policy_not_measured_physical_media",
    "deterministic_replay_claim": True,
    "physical_media_claim": False,
    "paint_rheology_claim": False,
    "external_product_pixel_parity_claim": False,
    "normalized_material_channel_domain": [0.0, 1.0],
    "signed_height_domain": [-1.0, 1.0],
    "fallback_blur": "deterministic_float32_separable_gaussian",
}
MATERIAL_PREVIEW_AZIMUTH_MIN_DEGREES = -180.0
MATERIAL_PREVIEW_AZIMUTH_MAX_DEGREES = 180.0
MATERIAL_PREVIEW_ELEVATION_MIN_DEGREES = 5.0
MATERIAL_PREVIEW_ELEVATION_MAX_DEGREES = 85.0
MATERIAL_PREVIEW_AZIMUTH_DEFAULT_DEGREES = -38.0
MATERIAL_PREVIEW_ELEVATION_DEFAULT_DEGREES = 48.0
_MATERIAL_RASTER_BACKEND_STATUS: dict[str, Any] = {
    "backend": "uninitialized",
    "fallback_count": 0,
    "last_fallback_error": "",
}

MATERIAL_PAINT_DEFAULTS: dict[str, Any] = {
    "load": 0.78,
    "thickness": 0.62,
    "wetness": 0.34,
    "gloss": 0.28,
    "roughness": 0.56,
    "plow": 0.0,
    "resaturation": 0.0,
    "negative_depth": False,
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


def normalize_material_preview_light_angles(
    azimuth_deg: object,
    elevation_deg: object,
) -> tuple[float, float]:
    def normalized(
        value: object,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        if isinstance(value, bool):
            return default
        try:
            result = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(result):
            return default
        return max(minimum, min(maximum, result))

    return (
        normalized(
            azimuth_deg,
            default=MATERIAL_PREVIEW_AZIMUTH_DEFAULT_DEGREES,
            minimum=MATERIAL_PREVIEW_AZIMUTH_MIN_DEGREES,
            maximum=MATERIAL_PREVIEW_AZIMUTH_MAX_DEGREES,
        ),
        normalized(
            elevation_deg,
            default=MATERIAL_PREVIEW_ELEVATION_DEFAULT_DEGREES,
            minimum=MATERIAL_PREVIEW_ELEVATION_MIN_DEGREES,
            maximum=MATERIAL_PREVIEW_ELEVATION_MAX_DEGREES,
        ),
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
) -> dict[str, Any]:
    source = dict(value or {})
    out: dict[str, Any] = {}
    for key, default in MATERIAL_PAINT_DEFAULTS.items():
        if key == "negative_depth":
            out[key] = bool(source.get(key, default))
            continue
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
        "relief_model": "tiger_authored_stylized_relief_v1",
        "coefficient_source": "authored_style_preset_not_measured_physical_media",
        "physical_media_claim": False,
        "external_brush_parity_claim": False,
        "fallback": "stylized_reduced_relief" if not compatible else "",
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
    resolved_width = positive_integer(width, field="material signature width")
    resolved_height = positive_integer(height, field="material signature height")
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
                "width": positive_real(
                    _value(stroke, "width_px", 1.0),
                    field="material stroke width_px",
                ),
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
                "plow": float(_value(stroke, "material_plow", layer["settings"]["plow"])),
                "resaturation": float(
                    _value(stroke, "material_resaturation", layer["settings"]["resaturation"])
                ),
                "negative_depth": bool(
                    _value(stroke, "material_negative_depth", layer["settings"]["negative_depth"])
                ),
            }
        )
    payload = {
        "size": [resolved_width, resolved_height],
        "time_ms": int(time_ms),
        "light": [float(light_azimuth_deg), float(light_elevation_deg)],
        "layers": specs,
        "strokes": rows,
    }
    return hashlib.blake2b(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        digest_size=16,
    ).hexdigest()


def _record_material_raster_backend(
    backend: str, error: BaseException | None = None
) -> None:
    _MATERIAL_RASTER_BACKEND_STATUS["backend"] = str(backend)
    if error is None:
        _MATERIAL_RASTER_BACKEND_STATUS["last_fallback_error"] = ""
        return
    _MATERIAL_RASTER_BACKEND_STATUS["fallback_count"] = int(
        _MATERIAL_RASTER_BACKEND_STATUS.get("fallback_count", 0)
    ) + 1
    _MATERIAL_RASTER_BACKEND_STATUS["last_fallback_error"] = (
        f"{type(error).__name__}: {error}"
    )


def material_raster_backend_status() -> dict[str, Any]:
    return dict(_MATERIAL_RASTER_BACKEND_STATUS)


def _draw_polyline_pillow(
    mask: np.ndarray, points: list[tuple[int, int]], width: int
) -> None:
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


def _draw_polyline(mask: np.ndarray, points: list[tuple[int, int]], width: int) -> None:
    if not points or int(width) <= 0:
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
        _record_material_raster_backend("opencv")
        return
    except Exception as exc:
        _record_material_raster_backend("pillow", exc)
    _draw_polyline_pillow(mask, points, width)


def _draw_weighted_segment(
    mask: np.ndarray,
    first: tuple[int, int],
    second: tuple[int, int],
    width: int,
    value: float,
) -> None:
    value = max(0.0, min(1.0, float(value)))
    if int(width) <= 0 or value <= 0.0:
        return
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
        _record_material_raster_backend("opencv")
        return
    except Exception as exc:
        _record_material_raster_backend("pillow", exc)
    segment = np.zeros_like(mask)
    _draw_polyline_pillow(segment, [first, second], width)
    np.maximum(mask, segment * value, out=mask)


def _blur(values: np.ndarray, radius: float) -> np.ndarray:
    source = np.asarray(values, dtype=np.float32)
    if source.ndim != 2:
        raise ValueError("Painter material blur expects a two-dimensional channel")
    if not bool(np.isfinite(source).all()):
        raise ValueError("Painter material blur input must be finite")
    sigma = float(radius)
    if not math.isfinite(sigma):
        raise ValueError("Painter material blur radius must be finite")
    if sigma <= 0.0:
        return source.copy()
    try:
        import cv2

        blurred = cv2.GaussianBlur(source, (0, 0), sigmaX=sigma, sigmaY=sigma)
        _record_material_raster_backend("opencv")
        return blurred
    except Exception as exc:
        _record_material_raster_backend("numpy_gaussian", exc)
        kernel_radius = max(1, int(math.ceil(sigma * 3.0)))
        offsets = np.arange(-kernel_radius, kernel_radius + 1, dtype=np.float64)
        kernel = np.exp(-(offsets * offsets) / (2.0 * sigma * sigma))
        kernel /= np.sum(kernel)
        horizontal_source = np.pad(source, ((0, 0), (kernel_radius, kernel_radius)), mode="edge")
        horizontal = np.zeros_like(source, dtype=np.float64)
        for offset, weight in enumerate(kernel):
            horizontal += horizontal_source[:, offset : offset + source.shape[1]] * weight
        vertical_source = np.pad(horizontal, ((kernel_radius, kernel_radius), (0, 0)), mode="edge")
        blurred = np.zeros_like(horizontal, dtype=np.float64)
        for offset, weight in enumerate(kernel):
            blurred += vertical_source[offset : offset + source.shape[0], :] * weight
        return blurred.astype(np.float32)


def _deterministic_noise_field(
    shape: tuple[int, int], seed: int, channel: int
) -> np.ndarray:
    """Return a stable Tiger-authored [0, 1] field without libm sine noise."""

    yy, xx = np.indices(shape, dtype=np.uint64)
    mask = np.uint64(0xFFFFFFFFFFFFFFFF)
    value = (
        xx * np.uint64(0x9E3779B185EBCA87)
        ^ yy * np.uint64(0xC2B2AE3D27D4EB4F)
        ^ np.uint64(int(seed) & int(mask))
        ^ np.uint64(int(channel) & int(mask))
    )
    value ^= value >> np.uint64(30)
    value *= np.uint64(0xBF58476D1CE4E5B9)
    value ^= value >> np.uint64(27)
    value *= np.uint64(0x94D049BB133111EB)
    value ^= value >> np.uint64(31)
    return ((value >> np.uint64(40)).astype(np.float32) / float(0xFFFFFF)).astype(
        np.float32
    )


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
    surface_settings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    width = positive_integer(width, field="material raster width")
    height = positive_integer(height, field="material raster height")
    specs = material_layer_specs(layers)
    relief = np.zeros((height, width), dtype=np.float32)
    excavation = np.zeros((height, width), dtype=np.float32)
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
            0.0,
            min(1.0, float(_value(stroke, "material_roughness", settings["roughness"]))),
        )
        plow = max(
            0.0,
            min(1.0, float(_value(stroke, "material_plow", settings["plow"]))),
        )
        resaturation = max(
            0.0,
            min(
                1.0,
                float(
                    _value(
                        stroke,
                        "material_resaturation",
                        settings["resaturation"],
                    )
                ),
            ),
        )
        negative_depth = bool(
            _value(stroke, "material_negative_depth", settings["negative_depth"])
        )
        style = str(_value(stroke, "brush_style", "round") or "round").casefold()
        profile_counts[style] = int(profile_counts.get(style, 0)) + 1
        authored_width_px = positive_real(
            _value(stroke, "width_px", 1.0),
            field="material stroke width_px",
        )
        width_px = max(1, int(round(authored_width_px)))
        opacity = max(0.0, min(1.0, float(_value(stroke, "opacity", 255) or 0) / 255.0))
        deposition = (
            thickness
            * load
            * opacity
            * layer["opacity"]
            * float(_STYLE_THICKNESS.get(style, 0.72))
        )
        if deposition <= 0.0:
            continue

        mask = np.zeros_like(relief)
        burial_mask: np.ndarray | None = None
        direction_written = False
        from app.painter_brush_engine_v2 import (
            bristle_lane_paths,
            depleted_load_curve,
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
        load_curve = depleted_load_curve(
            stroke,
            width=width - 1,
            height=height - 1,
        )
        point_response = [
            pressure_curve[index] * load_curve[index]
            for index in range(point_count)
        ]
        if not any(value > 0.0 for value in point_response):
            continue
        rotation_curve = normalize_curve(
            _value(stroke, "point_rotation", []) or [],
            point_count,
            0.5,
        )
        tangential_curve = normalize_signed_curve(
            _value(stroke, "point_tangential_pressure", []) or [],
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
            int(
                round(
                    width_px
                    * pressure_curve[index]
                    * load_curve[index]
                    * (
                        1.0
                        + min(
                            1.0,
                            math.hypot(tilt_x_curve[index], tilt_y_curve[index]),
                        )
                        * 0.24
                    )
                )
            )
            for index in range(point_count)
        ]

        if style == "stipple_oil":
            brush_seed = int(_value(stroke, "brush_seed", 0) or 0)
            stipple_response = sum(point_response) / len(point_response)
            for dab_index, (x, y, radius_x, radius_y, angle) in enumerate(
                stipple_dabs(
                    stroke,
                    width=width - 1,
                    height=height - 1,
                )
            ):
                half_length = radius_x * 0.46
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
                    int(round(radius_y * 2.0)),
                    stipple_response
                    * (
                        0.72
                        + 0.18
                        * (
                            deterministic_unit(
                                brush_seed, dab_index, 0x4D41544C
                            )
                            * 2.0
                            - 1.0
                        )
                    ),
                )
            direction_written = True
        elif style in {"palette_knife", "knife_scrape_oil"}:
            if len(dynamic_points) == 1:
                _draw_weighted_segment(
                    mask,
                    dynamic_points[0],
                    dynamic_points[0],
                    dynamic_widths[0],
                    pressure_curve[0] * load_curve[0],
                )
            else:
                for index, (first, second) in enumerate(
                    zip(dynamic_points, dynamic_points[1:])
                ):
                    local_pressure = (pressure_curve[index] + pressure_curve[index + 1]) * 0.5
                    local_load = (load_curve[index] + load_curve[index + 1]) * 0.5
                    _draw_weighted_segment(
                        mask,
                        first,
                        second,
                        int(
                            round(
                                (dynamic_widths[index] + dynamic_widths[index + 1])
                                * 0.47
                            )
                        ),
                        local_pressure * local_load,
                    )
        elif stroke_uses_bristle_v2(stroke):
            lanes = bristle_lane_paths(stroke, width=width - 1, height=height - 1)
            lane_width = int(round(width_px / len(lanes) * 0.92)) if lanes else 0
            if style not in {"dry_oil", "scumble_oil", "fan_bristle_oil"}:
                for index, (first, second) in enumerate(zip(points, points[1:])):
                    body_deposit = (
                        min(pressure_curve[index], pressure_curve[index + 1])
                        * min(load_curve[index], load_curve[index + 1])
                    )
                    _draw_weighted_segment(
                        mask,
                        first,
                        second,
                        int(
                            round(
                                width_px
                                * 0.70
                                * min(pressure_curve[index], pressure_curve[index + 1])
                            )
                        ),
                        body_deposit,
                    )
            for lane in lanes:
                for first, second in zip(lane, lane[1:]):
                    x1, y1, pressure_a, load_a = first
                    x2, y2, pressure_b, load_b = second
                    lane_deposit = (
                        min(pressure_a, pressure_b) * min(load_a, load_b)
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
                        int(round((dynamic_widths[index] + dynamic_widths[index + 1]) * 0.5)),
                        1.0,
                    )

        if style in {"loaded_oil", "impasto_oil"}:
            body = np.zeros_like(relief)
            for index, (first, second) in enumerate(zip(points, points[1:])):
                local_pressure = min(pressure_curve[index], pressure_curve[index + 1])
                local_load = min(load_curve[index], load_curve[index + 1])
                _draw_weighted_segment(
                    body,
                    first,
                    second,
                    int(round(width_px * 0.82 * local_pressure)),
                    local_pressure * local_load,
                )
            if len(points) == 1:
                _draw_weighted_segment(
                    body,
                    points[0],
                    points[0],
                    int(round(width_px * 0.82 * pressure_curve[0])),
                    pressure_curve[0] * load_curve[0],
                )
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
            ridge = np.zeros_like(relief)
            for index, (first, second) in enumerate(
                zip(dynamic_points, dynamic_points[1:])
            ):
                local_pressure = (pressure_curve[index] + pressure_curve[index + 1]) * 0.5
                local_load = (load_curve[index] + load_curve[index + 1]) * 0.5
                segment_width = int(
                    round(
                        (dynamic_widths[index] + dynamic_widths[index + 1])
                        * 0.47
                    )
                )
                _draw_weighted_segment(
                    body,
                    first,
                    second,
                    segment_width,
                    local_pressure * local_load,
                )
                dx = float(second[0] - first[0])
                dy = float(second[1] - first[1])
                length = max(1.0, math.hypot(dx, dy))
                nx = -dy / length
                ny = dx / length
                rotation = (rotation_curve[index] + rotation_curve[index + 1]) * 0.5
                tangential = (tangential_curve[index] + tangential_curve[index + 1]) * 0.5
                blade_side = 0.20 + (rotation - 0.5) * 0.26 + tangential * 0.10
                offset = float(segment_width) * blade_side
                ridge_first = (
                    max(0, min(width - 1, int(round(first[0] + nx * offset)))),
                    max(0, min(height - 1, int(round(first[1] + ny * offset)))),
                )
                ridge_second = (
                    max(0, min(width - 1, int(round(second[0] + nx * offset)))),
                    max(0, min(height - 1, int(round(second[1] + ny * offset)))),
                )
                _draw_weighted_segment(
                    ridge,
                    ridge_first,
                    ridge_second,
                    int(round(segment_width * 0.13)),
                    local_pressure * local_load,
                )
            if len(dynamic_points) == 1:
                _draw_polyline(body, dynamic_points, dynamic_widths[0])
            plateau = _blur(body, width_px * 0.028)
            plateau = np.clip((plateau - 0.12) * 1.28, 0.0, 1.0)
            burial_mask = plateau
            mask = np.clip(plateau * 0.88 + mask * 0.12 + ridge * 0.62, 0.0, 1.0)
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
            grain = _deterministic_noise_field(
                mask.shape,
                int(_value(stroke, "brush_seed", 0) or 0),
                stroke_count,
            )
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
        if plow > 0.0 and len(dynamic_points) >= 2:
            dx = float(dynamic_points[-1][0] - dynamic_points[0][0])
            dy = float(dynamic_points[-1][1] - dynamic_points[0][1])
            travel = max(1.0, math.hypot(dx, dy))
            nx, ny = -dy / travel, dx / travel
            shift = max(1, int(round(width_px * (0.08 + plow * 0.22))))
            displaced = relief * np.clip(mask * plow, 0.0, 1.0)
            relief -= displaced
            relief += _shift_clamped(
                displaced,
                int(round(nx * shift)),
                int(round(ny * shift)),
            )
        relief *= 1.0 - burial
        deposit = mask * deposition * 0.24
        if negative_depth:
            excavation += deposit
        else:
            relief += deposit
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
            0.0,
            1.0,
        )
        local_roughness = np.clip(
            float(surface_roughness)
            + style_roughness
            + (1.0 - mask) * 0.10
            - mask * wetness * 0.09,
            0.0,
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
    excavation = np.clip(
        1.0 - np.exp(-np.maximum(excavation, 0.0) * 1.16), 0.0, 1.0
    )
    signed_height = np.clip(relief - excavation, -1.0, 1.0).astype(np.float32)
    coverage = np.clip(coverage, 0.0, 1.0)
    roughness = np.where(
        roughness_weight > 1e-5,
        roughness_sum / np.maximum(roughness_weight, 1e-5),
        0.72,
    ).astype(np.float32)
    from app.ar_pbr.texture_map_lab import ao_map_from_height, normal_map_from_height

    shared_settings = {
        "normal_strength": 9.2,
        "normal_radius_px": 1.0,
        "normal_format": "unreal_directx",
        "normal_filter": "sobel",
        "ao_strength": 1.0,
        "ao_radius_px": max(1.0, min(width, height) / 180.0),
        "edge_aware_smoothing": True,
        "edge_aware_sensitivity": 9.0,
    }
    if surface_settings:
        shared_settings.update(dict(surface_settings))
    normal = normal_map_from_height(signed_height, shared_settings)
    ao = ao_map_from_height(signed_height, shared_settings, realtime=True)

    resolved_azimuth, resolved_elevation = normalize_material_preview_light_angles(
        light_azimuth_deg,
        light_elevation_deg,
    )
    azimuth = math.radians(resolved_azimuth)
    elevation = math.radians(resolved_elevation)
    light = np.asarray(
        [
            math.cos(elevation) * math.cos(azimuth),
            math.cos(elevation) * math.sin(azimuth),
            math.sin(elevation),
        ],
        dtype=np.float32,
    )
    signed_normal = normal * 2.0 - 1.0
    # The exported map follows the requested convention. Painter's 2D canvas
    # lighting uses a y-down screen tangent basis, equivalent to DirectX.
    # Convert OpenGL maps back to that canonical basis before N dot L.
    if str(shared_settings.get("normal_format", "unreal_directx")).casefold() not in {
        "unreal_directx",
        "directx",
    }:
        signed_normal[..., 1] *= -1.0
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
    # Painter needs relief to remain readable while the artist works, even
    # when the movable key light approaches a front-facing direction. This
    # fixed, low-energy rake light does not replace PBR lighting; it contributes
    # only the signed normal delta from a flat surface.
    studio_rake = np.asarray([-0.68, 0.36, 0.64], dtype=np.float32)
    studio_rake /= max(0.0001, float(np.linalg.norm(studio_rake)))
    studio_normal_delta = (
        np.sum(signed_normal * studio_rake[None, None, :], axis=2)
        - float(studio_rake[2])
    )
    local_height = _blur(signed_height, max(0.8, min(width, height) / 260.0))
    height_detail = signed_height - local_height
    normal_slope = np.sqrt(
        np.square(signed_normal[..., 0]) + np.square(signed_normal[..., 1])
    )
    soft_shadow = np.zeros_like(relief)
    for distance in (2, 4, 7, 11):
        dx = int(round(-float(light[0]) * distance))
        dy = int(round(-float(light[1]) * distance))
        blocker = _shift_clamped(signed_height, dx, dy)
        clearance = float(distance) * 0.006 / max(0.18, float(light[2]))
        soft_shadow = np.maximum(soft_shadow, blocker - signed_height - clearance)
    soft_shadow = np.clip(
        _blur(soft_shadow, max(0.8, min(width, height) / 360.0)) * 4.6,
        0.0,
        1.0,
    )
    shading = np.clip(
        0.72
        + diffuse * 0.34
        + specular
        + studio_normal_delta * 0.30
        + height_detail * 0.90
        + normal_slope * 0.025
        - soft_shadow * 0.43
        - (1.0 - ao) * 0.18,
        0.38,
        1.34,
    )

    return {
        "schema": MATERIAL_PAINT_SCHEMA,
        "model": "deterministic_stylized_relief_v1",
        "physical_media_claim": False,
        "negative_depth_supported": True,
        "plow_supported": True,
        "size": [width, height],
        "stroke_count": int(stroke_count),
        "style_profiles": profile_counts,
        "active": bool(stroke_count),
        "height": relief,
        "signed_height": signed_height,
        "excavation": excavation,
        "coverage": coverage,
        "normal": normal,
        "roughness": roughness,
        "ao": ao,
        "direction": np.stack((direction_x, direction_y), axis=2),
        "shading": shading.astype(np.float32),
        "shading_profile": "painter_artist_relief_readability_v1",
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
    # Differences below one output-code unit cannot survive the final 8-bit
    # alpha conversion. Use that quantization boundary instead of an authored
    # visual deadband.
    delta = np.where(np.abs(shading - 1.0) < (1.0 / 255.0), 0.0, shading - 1.0)
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
    *,
    surface_settings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(generated)
    maps = dict(result.get("maps") or {})
    material_height = np.asarray(channels.get("height"), dtype=np.float32)
    coverage = np.asarray(channels.get("coverage"), dtype=np.float32)
    if material_height.ndim != 2 or coverage.shape != material_height.shape:
        return result
    mask = np.clip(coverage, 0.0, 1.0)
    signed_height = np.asarray(channels.get("signed_height"), dtype=np.float32)
    has_excavation = (
        signed_height.shape == material_height.shape
            and float(np.min(signed_height)) < 0.0
    )
    authored_height = (
        np.clip(0.5 + signed_height * 0.5, 0.0, 1.0)
        if has_excavation
        else material_height
    )

    existing_height = np.asarray(maps.get("height", np.zeros_like(material_height)), dtype=np.float32)
    if existing_height.shape == material_height.shape:
        maps["height"] = np.clip(
            existing_height * (1.0 - mask * (1.0 if has_excavation else 0.72))
            + authored_height * mask,
            0.0,
            1.0,
        )
    maps["normal"] = _blend_map(maps.get("normal"), channels.get("normal"), mask, channels=3)
    merged_height = np.asarray(maps.get("height"), dtype=np.float32)
    if merged_height.shape == material_height.shape and not has_excavation:
        from app.ar_pbr.texture_map_lab import normal_map_from_height

        normal_settings = dict(result.get("settings") or {})
        if surface_settings:
            normal_settings.update(dict(surface_settings))
        maps["normal"] = normal_map_from_height(merged_height, normal_settings)
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
        "height_encoding": (
            "signed_neutral_0_5" if has_excavation else "positive_relief_zero_baseline"
        ),
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

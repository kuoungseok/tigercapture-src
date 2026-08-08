"""Reproducible parameter-response measurements for Painter media engines.

The measurements below are metamorphic checks over a fixed synthetic corpus.
They establish that named controls independently affect rendered pixels or
material channels.  They are not perceptual quality scores or physical-media
validation.
"""
from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter


MEDIA_RESPONSE_SCHEMA = "tigerstudio.painter.media-response.v1"


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return np.frombuffer(bytes(converted.constBits()), dtype=np.uint8).reshape(
        converted.height(), converted.width(), 4
    )


def _digest(image: QImage) -> str:
    return hashlib.sha256(bytes(image.constBits())).hexdigest()


def _smudge_image(*, length: int, radius: int, color_rate: int) -> QImage:
    from app.drawing import DrawingCanvas, Stroke

    image = QImage(200, 64, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#E4C52E"))
    painter = QPainter(image)
    painter.fillRect(QRect(0, 0, 100, 64), QColor("#2468D8"))
    painter.end()
    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        color=(220, 45, 35),
        opacity=255,
        width_px=22,
        brush_style="round",
        brush_spacing=18,
        brush_seed=17,
        brush_dynamics={
            "enabled": True,
            "mode": "smudge",
            "flow": 100,
            "pickup": 100,
            "smudge_length": length,
            "smudge_radius": radius,
            "color_rate": color_rate,
        },
        point_pressure=[1.0, 1.0],
    )
    painter = QPainter(image)
    DrawingCanvas._paint_stroke(painter, stroke, image.width(), image.height())
    painter.end()
    return image


def _overlay_smudge_replay_response() -> bool:
    from app.drawing import DrawingCanvas, Stroke
    from app.painter_brush_dynamics import capture_dynamic_sample_colors

    source = QImage(160, 64, QImage.Format.Format_ARGB32_Premultiplied)
    source.fill(QColor("#2468D8"))
    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        color=(220, 45, 35),
        opacity=255,
        width_px=20,
        brush_spacing=18,
        brush_dynamics={
            "enabled": True,
            "mode": "smudge",
            "smudge_type": "dulling",
            "overlay": True,
            "flow": 100,
            "pickup": 100,
            "smudge_length": 100,
            "smudge_radius": 0,
            "color_rate": 0,
        },
        point_pressure=[1.0, 1.0],
    )
    dynamics = dict(stroke.brush_dynamics)
    dynamics["sampled_rgba"] = capture_dynamic_sample_colors(
        stroke, 160, 64, source
    )
    stroke.brush_dynamics = dynamics
    replay = QImage(160, 64, QImage.Format.Format_ARGB32_Premultiplied)
    replay.fill(QColor("#28B86A"))
    painter = QPainter(replay)
    DrawingCanvas._paint_stroke(painter, stroke, 160, 64)
    painter.end()
    center = replay.pixelColor(80, 32)
    return bool(center.blue() > center.green())


def _wet_image(*, mixing: float, diffusion: float, pickup: float, dry: bool = False):
    from app.drawing import DrawingCanvas, Stroke
    from app.painter_wet_canvas import render_wet_layer_qimage

    strokes = [
        Stroke(
            points=[(0.12, 0.5), (0.88, 0.5)],
            color=(230, 24, 20),
            width_px=34,
            material_wetness=1.0,
        ),
        Stroke(
            points=[(0.5, 0.12), (0.5, 0.88)],
            color=(20, 40, 230),
            width_px=34,
            material_wetness=1.0,
        ),
    ]
    return render_wet_layer_qimage(
        strokes,
        settings={
            "enabled": True,
            "mixing": mixing,
            "diffusion": diffusion,
            "pickup": pickup,
            "drying_seconds": 100,
            "elapsed_seconds": 100 if dry else 0,
        },
        width=160,
        height=120,
        time_ms=0,
        render_stroke=lambda painter, stroke, width, height, opacity: DrawingCanvas._paint_stroke(
            painter, stroke, width, height, opacity_scale=opacity
        ),
    )


def _material_channels(
    *,
    style: str = "impasto_oil",
    tilt_x: float = 0.0,
    load_depletion: float = 0.28,
    point_load_end: float = 0.75,
    point_count: int = 2,
    **overrides: float,
) -> dict[str, Any]:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import rasterize_material_channels

    values = {
        "material_load": 0.8,
        "material_thickness": 0.8,
        "material_wetness": 0.3,
        "material_gloss": 0.3,
        "material_roughness": 0.6,
    }
    values.update(overrides)
    layer = PaintLayer("response-material", "Response", layer_type="material")
    count = max(2, int(point_count))
    points = [
        (0.12 + 0.76 * index / (count - 1), 0.5)
        for index in range(count)
    ]
    loads = [
        1.0 + (float(point_load_end) - 1.0) * index / (count - 1)
        for index in range(count)
    ]
    stroke = Stroke(
        points=points,
        width_px=30,
        brush_style=style,
        layer_id=layer.layer_id,
        material_enabled=True,
        brush_engine_version=2,
        bristle_count=14,
        brush_seed=117,
        point_pressure=[0.9] * count,
        point_tilt_x=[float(tilt_x)] * count,
        point_tilt_y=[0.0] * count,
        point_rotation=[0.5] * count,
        point_load=loads,
        load_depletion=float(load_depletion),
        **values,
    )
    return rasterize_material_channels([stroke], [layer], width=180, height=96)


def _plow_channels(plow: float) -> dict[str, Any]:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import rasterize_material_channels

    layer = PaintLayer("plow-material", "Plow", layer_type="material")
    common = {
        "width_px": 28,
        "brush_style": "palette_knife",
        "layer_id": layer.layer_id,
        "material_enabled": True,
        "material_load": 1.0,
        "material_thickness": 1.0,
        "brush_engine_version": 2,
        "point_pressure": [1.0, 1.0],
        "point_load": [1.0, 1.0],
    }
    under = Stroke(points=[(0.12, 0.5), (0.88, 0.5)], **common)
    over = Stroke(
        points=[(0.5, 0.12), (0.5, 0.88)],
        material_plow=float(plow),
        **common,
    )
    return rasterize_material_channels([under, over], [layer], width=180, height=120)


def measure_painter_media_response() -> dict[str, Any]:
    """Measure named-control response without inventing quality thresholds."""

    smudge_short = _smudge_image(length=0, radius=0, color_rate=0)
    smudge_carried = _smudge_image(length=100, radius=0, color_rate=0)
    smudge_wide = _smudge_image(length=0, radius=100, color_rate=0)
    smudge_colored = _smudge_image(length=100, radius=0, color_rate=100)
    short_end = _rgba(smudge_short)[32, 165, :3]
    carried_end = _rgba(smudge_carried)[32, 165, :3]
    colored_end = _rgba(smudge_colored)[32, 165, :3]

    wet_mix_zero, wet_mix_zero_report = _wet_image(
        mixing=0.0, diffusion=0.0, pickup=0.0
    )
    wet_mix_full, wet_mix_full_report = _wet_image(
        mixing=1.0, diffusion=0.0, pickup=0.0
    )
    wet_pickup_full, _ = _wet_image(mixing=1.0, diffusion=0.0, pickup=1.0)
    wet_diffuse, wet_diffuse_report = _wet_image(
        mixing=1.0, diffusion=1.0, pickup=0.0
    )
    wet_dry, wet_dry_report = _wet_image(
        mixing=1.0, diffusion=1.0, pickup=1.0, dry=True
    )

    material_load_low = _material_channels(material_load=0.2)
    material_load_high = _material_channels(material_load=1.0)
    material_thin = _material_channels(material_thickness=0.2)
    material_thick = _material_channels(material_thickness=1.0)
    material_dry = _material_channels(material_wetness=0.0)
    material_wet = _material_channels(material_wetness=1.0)
    material_matte = _material_channels(material_gloss=0.0)
    material_gloss = _material_channels(material_gloss=1.0)
    material_rough_low = _material_channels(material_roughness=0.1)
    material_rough_high = _material_channels(material_roughness=0.9)
    material_depletion_low = _material_channels(
        load_depletion=0.0, point_load_end=1.0, point_count=65
    )
    material_depletion_high = _material_channels(
        load_depletion=1.0, point_load_end=1.0, point_count=65
    )
    material_resaturated = _material_channels(
        load_depletion=0.0, point_load_end=1.0, point_count=65
    )
    material_depleted_input = _material_channels(
        load_depletion=0.0, point_load_end=0.05, point_count=65
    )
    material_auto_resat_off = _material_channels(
        load_depletion=1.0,
        point_load_end=0.05,
        point_count=65,
        material_resaturation=0.0,
    )
    material_auto_resat_on = _material_channels(
        load_depletion=1.0,
        point_load_end=0.05,
        point_count=65,
        material_resaturation=1.0,
    )
    knife_untilted = _material_channels(style="palette_knife", tilt_x=0.0)
    knife_tilted = _material_channels(style="palette_knife", tilt_x=0.8)
    positive_depth = _material_channels(material_negative_depth=False)
    negative_depth = _material_channels(material_negative_depth=True)
    plow_zero = _plow_channels(0.0)
    plow_full = _plow_channels(1.0)

    def occupied_mean(channels: dict[str, Any], name: str) -> float:
        weights = np.clip(np.asarray(channels["coverage"], dtype=np.float64), 0.0, 1.0)
        values = np.asarray(channels[name], dtype=np.float64)
        total = float(np.sum(weights))
        return float(np.sum(values * weights) / total) if total > 0.0 else 0.0

    wet_arrays = {
        "mix_0": _rgba(wet_mix_zero),
        "mix_1": _rgba(wet_mix_full),
        "pickup_1": _rgba(wet_pickup_full),
        "diffusion_1": _rgba(wet_diffuse),
        "dry": _rgba(wet_dry),
    }
    wet_hashes = {key: hashlib.sha256(value.tobytes()).hexdigest() for key, value in wet_arrays.items()}

    return {
        "schema": MEDIA_RESPONSE_SCHEMA,
        "evidence_kind": "automated_measurement",
        "scope": "fixed_synthetic_corpus",
        "quality_threshold_claim": False,
        "physical_media_validation": False,
        "smudge": {
            "model": "deterministic_carried_color_stylized_v1",
            "end_rgb": {
                "length_0": short_end.astype(int).tolist(),
                "length_100": carried_end.astype(int).tolist(),
                "color_rate_100": colored_end.astype(int).tolist(),
            },
            "length_response": bool(carried_end[2] > short_end[2]),
            "radius_response": _digest(smudge_wide) != _digest(smudge_short),
            "color_rate_response": bool(colored_end[0] > carried_end[0]),
            "overlay_frozen_replay_response": _overlay_smudge_replay_response(),
            "all_layer_sampling_supported": True,
            "explicit_overlay_mode_supported": True,
        },
        "wet_canvas": {
            "model": wet_mix_full_report["model"],
            "mixing_response": wet_hashes["mix_0"] != wet_hashes["mix_1"],
            "pickup_response": wet_hashes["mix_1"] != wet_hashes["pickup_1"],
            "diffusion_response": wet_hashes["mix_1"] != wet_hashes["diffusion_1"],
            "drying_response": wet_hashes["diffusion_1"] != wet_hashes["dry"],
            "diffusion_applied": bool(wet_diffuse_report["diffusion_applied"]),
            "dry_remaining": float(wet_dry_report["remaining"]),
            "physical_pigment_claim": bool(wet_mix_zero_report["physical_pigment_claim"]),
        },
        "material_paint": {
            "model": "deterministic_stylized_relief_v1",
            "load_height_sum": [
                float(np.sum(material_load_low["height"])),
                float(np.sum(material_load_high["height"])),
            ],
            "thickness_height_sum": [
                float(np.sum(material_thin["height"])),
                float(np.sum(material_thick["height"])),
            ],
            "wetness_roughness_mean": [
                occupied_mean(material_dry, "roughness"),
                occupied_mean(material_wet, "roughness"),
            ],
            "gloss_roughness_mean": [
                occupied_mean(material_matte, "roughness"),
                occupied_mean(material_gloss, "roughness"),
            ],
            "roughness_mean": [
                occupied_mean(material_rough_low, "roughness"),
                occupied_mean(material_rough_high, "roughness"),
            ],
            "load_response": bool(
                np.sum(material_load_high["height"]) > np.sum(material_load_low["height"])
            ),
            "thickness_response": bool(
                np.sum(material_thick["height"]) > np.sum(material_thin["height"])
            ),
            "wetness_response": bool(
                occupied_mean(material_wet, "roughness") < occupied_mean(material_dry, "roughness")
            ),
            "gloss_response": bool(
                occupied_mean(material_gloss, "roughness") < occupied_mean(material_matte, "roughness")
            ),
            "roughness_response": bool(
                occupied_mean(material_rough_high, "roughness")
                > occupied_mean(material_rough_low, "roughness")
            ),
            "load_depletion_height_sum": [
                float(np.sum(material_depletion_low["height"])),
                float(np.sum(material_depletion_high["height"])),
            ],
            "load_depletion_response": bool(
                np.sum(material_depletion_high["height"])
                < np.sum(material_depletion_low["height"])
            ),
            "authored_load_recovery_response": bool(
                np.sum(material_resaturated["height"])
                > np.sum(material_depleted_input["height"])
            ),
            "automatic_resaturation_height_sum": [
                float(np.sum(material_auto_resat_off["height"])),
                float(np.sum(material_auto_resat_on["height"])),
            ],
            "automatic_resaturation_response": bool(
                np.sum(material_auto_resat_on["height"])
                > np.sum(material_auto_resat_off["height"])
            ),
            "automatic_resaturation_supported": True,
            "tilt_knife_response": bool(
                not np.array_equal(knife_untilted["height"], knife_tilted["height"])
            ),
            "plow_response": bool(
                not np.array_equal(plow_zero["signed_height"], plow_full["signed_height"])
            ),
            "negative_depth_response": bool(
                float(np.min(negative_depth["signed_height"])) < 0.0
                and float(np.max(negative_depth["excavation"])) > 0.0
                and float(np.min(positive_depth["signed_height"])) >= 0.0
            ),
            "plow_supported": True,
            "negative_depth_supported": True,
        },
    }


__all__ = ["MEDIA_RESPONSE_SCHEMA", "measure_painter_media_response"]

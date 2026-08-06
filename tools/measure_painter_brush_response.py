"""Measure Painter Painting brush-response invariants on deterministic fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


OFFICIAL_SOURCES = {
    "rfc7693_blake2": "https://www.rfc-editor.org/rfc/rfc7693",
    "qt_tablet_event_pressure": (
        "https://doc.qt.io/qtforpython-6/PySide6/QtGui/QTabletEvent.html"
    ),
    "qt_qimage_bounds": "https://doc.qt.io/qt-6/qimage.html",
    "krita_pixel_brush_engine": (
        "https://docs.krita.org/en/reference_manual/brushes/brush_engines/"
        "pixel_brush_engine.html"
    ),
    "krita_color_smudge_engine": (
        "https://docs.krita.org/en/reference_manual/brushes/brush_engines/"
        "color_smudge_engine.html"
    ),
    "krita_brush_texture": (
        "https://docs.krita.org/en/reference_manual/brushes/brush_settings/"
        "texture.html"
    ),
    "corel_thick_paint_controls": (
        "https://product.corel.com/help/Painter/540219480/Main/EN/"
        "Win-Documentation/Corel-Painter-Thick-Paint-Brush-controls.html"
    ),
    "khronos_gltf_materials": (
        "https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html"
    ),
}


def _max_delta(first: list[float], second: list[float]) -> float:
    return max((abs(a - b) for a, b in zip(first, second)), default=0.0)


def measure_brush_response() -> dict[str, Any]:
    import numpy as np

    from PySide6.QtGui import QColor, QImage, QPainter

    from app.drawing import DrawingCanvas, PaintLayer, Stroke
    from app.painter_brush_dynamics import (
        SMUDGE_LARGE_RADIUS_AXIS_SAMPLES,
        _sample_radius_color,
        _smudge_sample_pixels,
        dynamic_dab_workload,
        dynamic_dabs,
        map_pressure,
        normalize_brush_dynamics,
        stabilize_points,
    )
    from app.painter_brush_engine_v2 import (
        depleted_load_curve,
        incremental_stroke_segments,
    )
    from app.painter_material_paint import rasterize_material_channels

    load_common = {
        "point_load": [1.0, 1.0],
        "load_depletion": 0.75,
        "load_dryout_px": 256.0,
        "material_resaturation": 0.0,
    }
    coarse = Stroke(points=[(0.125, 0.50), (0.875, 0.50)], **load_common)
    dense = Stroke(
        points=[(0.125 + index / 32.0, 0.50) for index in range(25)],
        point_load=[1.0] * 25,
        load_depletion=0.75,
        load_dryout_px=256.0,
        material_resaturation=0.0,
    )
    coarse_load = depleted_load_curve(coarse, width=256, height=128)
    dense_load = depleted_load_curve(dense, width=256, height=128)

    segmented_source = Stroke(
        points=[(0.10, 0.50), (0.40, 0.50), (0.90, 0.50)],
        brush_style="bristle_oil",
        brush_engine_version=2,
        point_load=[1.0, 1.0, 1.0],
        load_depletion=0.8,
        load_dryout_px=200.0,
    )
    full_load = depleted_load_curve(segmented_source, width=200, height=100)
    segments = incremental_stroke_segments(
        segmented_source,
        width=200,
        height=100,
    )
    segmented_load = [
        depleted_load_curve(segment, width=200, height=100)
        for segment in segments
    ]
    segment_delta = max(
        _max_delta(segmented_load[0], full_load[:2]),
        _max_delta(segmented_load[1], full_load[1:]),
    )

    sparse_curve_source = Stroke(
        points=[(0.125, 0.50), (0.375, 0.50), (0.625, 0.50), (0.875, 0.50)],
        brush_style="bristle_oil",
        brush_engine_version=2,
        point_pressure=[0.25, 1.0],
        point_tilt_x=[-0.5, 0.5],
        point_rotation=[0.25, 0.75],
        point_load=[1.0, 0.25],
        load_depletion=0.75,
        load_dryout_px=256.0,
    )
    sparse_full_load = depleted_load_curve(
        sparse_curve_source,
        width=256,
        height=128,
    )
    sparse_segments = incremental_stroke_segments(
        sparse_curve_source,
        width=256,
        height=128,
    )
    sparse_segment_delta = max(
        (
            _max_delta(
                depleted_load_curve(segment, width=256, height=128),
                sparse_full_load[index : index + 2],
            )
            for index, segment in enumerate(sparse_segments)
        ),
        default=0.0,
    )

    resaturated = Stroke(
        points=list(coarse.points),
        point_load=[1.0, 1.0],
        load_depletion=0.75,
        load_dryout_px=256.0,
        material_resaturation=0.5,
    )
    resaturated_load = depleted_load_curve(resaturated, width=256, height=128)

    dynamics = {
        "enabled": True,
        "flow": 100,
        "transfer_flow": 100,
        "transfer_opacity": 100,
        "pressure_curve": [[0.0, 0.0], [1.0, 1.0]],
    }
    low_pressure = Stroke(
        points=[(0.10, 0.50), (0.90, 0.50)],
        width_px=20,
        brush_spacing=25,
        point_pressure=[0.2, 0.2],
        brush_dynamics=dynamics,
    )
    high_pressure = Stroke(
        **{
            **low_pressure.__dict__,
            "point_pressure": [0.9, 0.9],
        }
    )
    low_dabs = dynamic_dabs(low_pressure, 200, 100)
    high_dabs = dynamic_dabs(high_pressure, 200, 100)
    sparse = Stroke(**{**high_pressure.__dict__, "brush_spacing": 100})
    sparse_dabs = dynamic_dabs(sparse, 200, 100)
    zero_pressure = Stroke(
        **{
            **high_pressure.__dict__,
            "point_pressure": [0.0, 0.0],
        }
    )
    zero_pressure_dabs = dynamic_dabs(zero_pressure, 200, 100)
    buildup_zero = Stroke(
        points=[(0.5, 0.5)],
        width_px=10,
        brush_dynamics={"enabled": True, "scatter_count": 8, "buildup": 0},
    )
    buildup_full = Stroke(
        **{
            **buildup_zero.__dict__,
            "brush_dynamics": {
                "enabled": True,
                "scatter_count": 8,
                "buildup": 100,
            },
        }
    )
    buildup_zero_dabs = dynamic_dabs(buildup_zero, 64, 64)
    buildup_full_dabs = dynamic_dabs(buildup_full, 64, 64)
    full_stabilization = stabilize_points(
        [(0.0, 0.0), (0.4, 0.8), (0.9, 0.3)], 1.0
    )

    layer = PaintLayer(
        "material-evidence",
        "Material evidence",
        layer_type="material",
        material_settings={"thickness": 0.8, "roughness": 0.5},
    )
    material_common = {
        "points": [(0.15, 0.50), (0.85, 0.50)],
        "width_px": 24,
        "brush_style": "palette_knife",
        "brush_engine_version": 2,
        "material_enabled": True,
        "material_load": 1.0,
        "material_thickness": 0.8,
        "layer_id": layer.layer_id,
    }
    light = Stroke(
        **material_common,
        point_pressure=[0.2, 0.2],
        point_load=[0.3, 0.3],
    )
    loaded = Stroke(
        **material_common,
        point_pressure=[0.9, 0.9],
        point_load=[1.0, 1.0],
    )
    light_channels = rasterize_material_channels(
        [light], [layer], width=160, height=96
    )
    loaded_channels = rasterize_material_channels(
        [loaded], [layer], width=160, height=96
    )
    light_height = float(np.sum(light_channels["height"]))
    loaded_height = float(np.sum(loaded_channels["height"]))

    replay_payload = json.dumps(high_dabs, sort_keys=True, separators=(",", ":"))
    replay_hash = hashlib.sha256(replay_payload.encode("utf-8")).hexdigest()
    repeat_hash = hashlib.sha256(
        json.dumps(
            dynamic_dabs(high_pressure, 200, 100),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    collapsed_pressure_window = normalize_brush_dynamics(
        {"pressure_min": 100, "pressure_max": 100}
    )
    reversed_pressure_window = normalize_brush_dynamics(
        {"pressure_min": 80, "pressure_max": 20}
    )

    def render_neutral_endpoint(mode: str, amount: int) -> bytes:
        image = QImage(96, 64, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("#2877C8"))
        neutral_stroke = Stroke(
            points=[(0.10, 0.50), (0.90, 0.50)],
            color=(220, 62, 45),
            opacity=255,
            width_px=16,
            brush_spacing=25,
            brush_dynamics={
                "enabled": True,
                "mode": mode,
                "pickup": amount,
                "flow": amount if mode == "paint" else 100,
            },
            point_pressure=[1.0, 1.0],
        )
        painter = QPainter(image)
        try:
            DrawingCanvas._paint_stroke(
                painter,
                neutral_stroke,
                image.width(),
                image.height(),
            )
        finally:
            painter.end()
        return bytes(image.constBits())

    transparent_deposit_reference = render_neutral_endpoint("paint", 0)
    zero_pickup = render_neutral_endpoint("pickup", 0)
    zero_smudge = render_neutral_endpoint("smudge", 0)

    minimum_domain = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        width_px=0,
        brush_spacing=0,
        brush_dynamics={"enabled": True},
    )
    minimum_domain_workload = dynamic_dab_workload(minimum_domain, 100, 32)
    zero_texture_scale = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        width_px=10,
        brush_spacing=100,
        brush_seed=73,
        brush_dynamics={
            "enabled": True,
            "texture_strength": 100,
            "texture_scale": 0,
        },
        point_pressure=[1.0, 1.0],
    )
    zero_texture_alphas = {
        round(float(dab["alpha"]), 12)
        for dab in dynamic_dabs(zero_texture_scale, 400, 32)
    }
    full_size_jitter = Stroke(
        points=[(0.0, 0.5), (1.0, 0.5)],
        width_px=10,
        brush_spacing=1,
        brush_seed=17,
        brush_dynamics={"enabled": True, "size_jitter": 100},
        point_pressure=[1.0, 1.0],
    )
    minimum_jitter_dab_size = min(
        float(dab["size"])
        for dab in dynamic_dabs(full_size_jitter, 800, 32)
    )

    smudge_extent = 241
    smudge_center = smudge_extent // 2
    smudge_source = QImage(
        smudge_extent,
        smudge_extent,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    smudge_source.fill(QColor("#2468D8"))
    for pixel_y in range(smudge_extent):
        for pixel_x in range(smudge_extent):
            if (
                (pixel_x - smudge_center) ** 2
                + (pixel_y - smudge_center) ** 2
                <= 32**2
            ):
                smudge_source.setPixelColor(pixel_x, pixel_y, QColor("#D83224"))
    near_smudge_color = _sample_radius_color(
        smudge_source, smudge_center, smudge_center, 32, QColor("black")
    )
    wide_smudge_color = _sample_radius_color(
        smudge_source, smudge_center, smudge_center, 100, QColor("black")
    )
    wide_smudge_samples = _smudge_sample_pixels(
        smudge_extent, smudge_extent, smudge_center, smudge_center, 100
    )

    measurements = {
        "coarse_end_load": coarse_load[-1],
        "dense_end_load": dense_load[-1],
        "event_density_end_load_delta": abs(coarse_load[-1] - dense_load[-1]),
        "segmented_full_load_max_delta": segment_delta,
        "sparse_curve_segmented_full_load_max_delta": sparse_segment_delta,
        "resaturated_end_load": resaturated_load[-1],
        "low_pressure_mean_size": sum(float(row["size"]) for row in low_dabs) / len(low_dabs),
        "high_pressure_mean_size": sum(float(row["size"]) for row in high_dabs) / len(high_dabs),
        "low_pressure_mean_alpha": sum(float(row["alpha"]) for row in low_dabs) / len(low_dabs),
        "high_pressure_mean_alpha": sum(float(row["alpha"]) for row in high_dabs) / len(high_dabs),
        "dense_spacing_dab_count": len(high_dabs),
        "sparse_spacing_dab_count": len(sparse_dabs),
        "light_material_height_sum": light_height,
        "loaded_material_height_sum": loaded_height,
        "deterministic_replay_sha256": replay_hash,
        "repeat_replay_sha256": repeat_hash,
        "collapsed_pressure_window": [
            collapsed_pressure_window["pressure_min"],
            collapsed_pressure_window["pressure_max"],
        ],
        "reversed_pressure_window": [
            reversed_pressure_window["pressure_min"],
            reversed_pressure_window["pressure_max"],
        ],
        "zero_pickup_sha256": hashlib.sha256(zero_pickup).hexdigest(),
        "zero_smudge_sha256": hashlib.sha256(zero_smudge).hexdigest(),
        "zero_deposit_reference_sha256": hashlib.sha256(
            transparent_deposit_reference
        ).hexdigest(),
        "minimum_domain_requested_spacing_px": minimum_domain_workload[
            "requested_spacing_px"
        ],
        "zero_texture_scale_unique_alpha_count": len(zero_texture_alphas),
        "minimum_full_jitter_dab_size_px": minimum_jitter_dab_size,
        "near_smudge_blue": near_smudge_color.blue(),
        "wide_smudge_blue": wide_smudge_color.blue(),
        "wide_smudge_sample_count": len(wide_smudge_samples),
        "wide_smudge_sample_capacity": SMUDGE_LARGE_RADIUS_AXIS_SAMPLES**2,
        "zero_pressure_max_size": max(
            (float(dab["size"]) for dab in zero_pressure_dabs), default=0.0
        ),
        "zero_pressure_max_alpha": max(
            (float(dab["alpha"]) for dab in zero_pressure_dabs), default=0.0
        ),
        "buildup_zero_dab_count": len(buildup_zero_dabs),
        "buildup_full_dab_count": len(buildup_full_dabs),
        "full_stabilization_points": full_stabilization,
    }
    checks = {
        "load_matches_192px_over_256px_formula": coarse_load[-1] == 0.4375,
        "load_independent_of_tablet_event_density": measurements[
            "event_density_end_load_delta"
        ] == 0.0,
        "live_segments_match_full_stroke": segment_delta == 0.0,
        "sparse_sensor_curves_match_full_stroke": sparse_segment_delta == 0.0,
        "resaturation_replenishes_load": resaturated_load[-1] > coarse_load[-1],
        "pressure_increases_dab_size": measurements["high_pressure_mean_size"]
        > measurements["low_pressure_mean_size"],
        "pressure_increases_dab_alpha": measurements["high_pressure_mean_alpha"]
        > measurements["low_pressure_mean_alpha"],
        "spacing_controls_dab_density": len(high_dabs) > len(sparse_dabs),
        "pressure_and_load_increase_material_deposit": loaded_height > light_height,
        "deterministic_replay": replay_hash == repeat_hash,
        "pressure_window_stays_in_percent_domain": (
            collapsed_pressure_window["pressure_min"] == 99
            and collapsed_pressure_window["pressure_max"] == 100
            and reversed_pressure_window["pressure_min"] == 80
            and reversed_pressure_window["pressure_max"] == 81
        ),
        "pressure_window_endpoints_map_exactly": (
            map_pressure(0.99, collapsed_pressure_window) == 0.0
            and map_pressure(1.0, collapsed_pressure_window) == 1.0
        ),
        "zero_pickup_is_exact_no_deposit": (
            zero_pickup == transparent_deposit_reference
            and zero_smudge == transparent_deposit_reference
        ),
        "declared_minimum_spacing_reaches_dab_plan": (
            minimum_domain_workload["requested_spacing_px"] == 0.01
        ),
        "zero_texture_scale_has_no_hidden_floor": len(zero_texture_alphas) == 1,
        "full_size_jitter_has_no_hidden_eight_percent_floor": (
            minimum_jitter_dab_size < 0.08 * 10
        ),
        "large_smudge_radius_samples_beyond_32px": (
            wide_smudge_color.blue() > near_smudge_color.blue()
            and any(
                (pixel_x - smudge_center) ** 2
                + (pixel_y - smudge_center) ** 2
                > 32**2
                for pixel_x, pixel_y in wide_smudge_samples
            )
        ),
        "large_smudge_sampling_is_bounded": (
            len(wide_smudge_samples) <= SMUDGE_LARGE_RADIUS_AXIS_SAMPLES**2
        ),
        "default_pressure_has_exact_linear_endpoints": (
            map_pressure(0.0, {}) == 0.0
            and map_pressure(0.25, {}) == 0.25
            and map_pressure(1.0, {}) == 1.0
            and all(float(dab["size"]) == 0.0 for dab in zero_pressure_dabs)
            and all(float(dab["alpha"]) == 0.0 for dab in zero_pressure_dabs)
        ),
        "full_stabilization_has_exact_endpoint": full_stabilization
        == [(0.0, 0.0), (0.0, 0.0), (0.4, 0.8)],
        "full_buildup_doubles_scatter_count": (
            len(buildup_zero_dabs) == 8 and len(buildup_full_dabs) == 16
        ),
    }
    return {
        "schema": "tigerstudio.painter.brush_response_measurement.v1",
        "scope": "painting_only_ui_design_excluded",
        "official_sources": OFFICIAL_SOURCES,
        "claim_boundary": {
            "physical_media_parity": False,
            "external_brush_engine_pixel_parity": False,
            "validated_claim": "deterministic_authored_response_invariants",
        },
        "measurements": measurements,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = measure_brush_response()
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

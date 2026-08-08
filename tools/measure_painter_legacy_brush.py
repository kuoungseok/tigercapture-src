"""Measure the retained Tiger Painter brush contract (M51)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _rgba_bytes(image) -> bytes:
    data = bytearray()
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            data.extend((color.red(), color.green(), color.blue(), color.alpha()))
    return bytes(data)


def _sha256(image) -> str:
    return hashlib.sha256(_rgba_bytes(image)).hexdigest()


def _max_rgba_delta(first: bytes, second: bytes) -> int:
    if len(first) != len(second):
        raise ValueError("RGBA buffers must have equal length")
    return max((abs(left - right) for left, right in zip(first, second)), default=0)


def _render(stroke, *, width: int = 192, height: int = 96):
    from PySide6.QtGui import QImage, QPainter

    from app.drawing import DrawingCanvas

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    try:
        DrawingCanvas._paint_stroke(painter, stroke, width, height)
    finally:
        painter.end()
    return image


def _alpha_metrics(image) -> dict[str, object]:
    coordinates = [
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 0
    ]
    if not coordinates:
        return {"count": 0, "bounds": None, "max_alpha": 0}
    xs = [point[0] for point in coordinates]
    ys = [point[1] for point in coordinates]
    return {
        "count": len(coordinates),
        "bounds": [min(xs), min(ys), max(xs), max(ys)],
        "max_alpha": max(image.pixelColor(x, y).alpha() for x, y in coordinates),
    }


def _stroke_from_preset(preset: dict[str, object]):
    from app.drawing import Stroke

    return Stroke(
        points=[(0.08, 0.72), (0.29, 0.27), (0.55, 0.64), (0.88, 0.31)],
        color=(48, 132, 224),
        opacity=round(int(preset["opacity"]) * 255 / 100),
        width_px=float(preset["width"]),
        brush_style=str(preset["style"]),
        brush_hardness=int(preset.get("hardness", 100)),
        brush_spacing=int(preset.get("spacing", 25)),
        brush_angle=int(preset.get("angle", 0)),
        brush_roundness=int(preset.get("roundness", 100)),
    )


def main() -> int:
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from app.drawing import (
        BRUSH_LIBRARY_PRESETS,
        PAINT_TEXTURED_BRUSH_STYLES,
        Stroke,
        compose_pil_paint_overlays,
        render_strokes_to_png,
    )
    from app.painter_brush_catalog import (
        DESIGNER_BRUSH_PRESETS,
        DESIGNER_BRUSH_RENDER_PROFILES,
        DESIGNER_PROFILE_PUBLIC_CONTROL_KEYS,
    )
    from app.painter_legacy_brush import (
        LEGACY_BRUSH_GEOMETRY_CONTRACT,
        deterministic_unit,
        sample_polyline_uniform,
        stable_style_seed,
    )

    app = QApplication.instance() or QApplication([])

    preset_by_style = {
        str(preset["style"]): preset
        for preset in DESIGNER_BRUSH_PRESETS
        if str(preset["style"]) in DESIGNER_BRUSH_RENDER_PROFILES
    }
    retained_preset_by_style = {
        str(preset["style"]): preset
        for preset in BRUSH_LIBRARY_PRESETS
        if str(preset["style"]) in PAINT_TEXTURED_BRUSH_STYLES
    }
    profile_hashes: dict[str, str] = {}
    profile_metrics: dict[str, dict[str, object]] = {}
    repeat_equal = True
    for style in sorted(DESIGNER_BRUSH_RENDER_PROFILES):
        stroke = _stroke_from_preset(preset_by_style[style])
        first = _render(stroke)
        second = _render(stroke)
        profile_hashes[style] = _sha256(first)
        profile_metrics[style] = _alpha_metrics(first)
        repeat_equal = repeat_equal and _rgba_bytes(first) == _rgba_bytes(second)

    retained_hashes: dict[str, str] = {}
    retained_metrics: dict[str, dict[str, object]] = {}
    retained_repeat_equal = True
    for style in sorted(PAINT_TEXTURED_BRUSH_STYLES):
        stroke = _stroke_from_preset(retained_preset_by_style[style])
        first = _render(stroke)
        second = _render(stroke)
        retained_hashes[style] = _sha256(first)
        retained_metrics[style] = _alpha_metrics(first)
        retained_repeat_equal = (
            retained_repeat_equal and _rgba_bytes(first) == _rgba_bytes(second)
        )

    shadowed = {
        style: sorted(DESIGNER_PROFILE_PUBLIC_CONTROL_KEYS.intersection(profile))
        for style, profile in DESIGNER_BRUSH_RENDER_PROFILES.items()
        if DESIGNER_PROFILE_PUBLIC_CONTROL_KEYS.intersection(profile)
    }

    width_small = Stroke(
        points=[(0.15, 0.5), (0.85, 0.5)], color=(20, 90, 220), opacity=255,
        width_px=4.0, brush_style="pixel_square", brush_spacing=100,
    )
    width_large = Stroke(**{**width_small.__dict__, "width_px": 12.0})
    opacity_low = Stroke(**{**width_small.__dict__, "opacity": 64})
    spacing_sparse_stroke = Stroke(
        **{**width_small.__dict__, "opacity": 64, "brush_spacing": 100}
    )
    spacing_dense = Stroke(
        **{**spacing_sparse_stroke.__dict__, "brush_spacing": 25}
    )
    small_metrics = _alpha_metrics(_render(width_small))
    large_metrics = _alpha_metrics(_render(width_large))
    low_metrics = _alpha_metrics(_render(opacity_low))
    high_metrics = _alpha_metrics(_render(width_small))
    dense_metrics = _alpha_metrics(_render(spacing_dense))
    sparse_metrics = _alpha_metrics(_render(spacing_sparse_stroke))

    public_control_base = _stroke_from_preset(preset_by_style["graphite_pencil"])
    hardness_hard = _render(
        Stroke(**{**public_control_base.__dict__, "brush_hardness": 100})
    )
    hardness_soft = _render(
        Stroke(**{**public_control_base.__dict__, "brush_hardness": 10})
    )
    roundness_round = _render(
        Stroke(**{**public_control_base.__dict__, "brush_roundness": 100})
    )
    roundness_flat = _render(
        Stroke(**{**public_control_base.__dict__, "brush_roundness": 25})
    )
    angle_zero = _render(
        Stroke(**{**public_control_base.__dict__, "brush_angle": 0})
    )
    angle_rotated = _render(
        Stroke(**{**public_control_base.__dict__, "brush_angle": 45})
    )
    oil_control_base = _stroke_from_preset(retained_preset_by_style["loaded_oil"])
    oil_control_variants = {
        "hardness": _render(
            Stroke(**{**oil_control_base.__dict__, "brush_hardness": 10})
        ),
        "roundness": _render(
            Stroke(**{**oil_control_base.__dict__, "brush_roundness": 25})
        ),
        "angle": _render(
            Stroke(**{**oil_control_base.__dict__, "brush_angle": 45})
        ),
        "spacing": _render(
            Stroke(**{**oil_control_base.__dict__, "brush_spacing": 100})
        ),
    }
    oil_control_base_rgba = _rgba_bytes(_render(oil_control_base))

    sparse_samples, sparse_workload = sample_polyline_uniform(
        [(0.0, 0.0), (10.0, 0.0)], 3.0
    )
    tessellated_samples, tessellated_workload = sample_polyline_uniform(
        [(0.0, 0.0), (2.0, 0.0), (7.0, 0.0), (10.0, 0.0)], 3.0
    )
    bounded_samples, bounded_workload = sample_polyline_uniform(
        [(0.0, 0.0), (10.0, 0.0)], 0.01, sample_budget=4
    )

    parity_stroke = _stroke_from_preset(preset_by_style["graphite_pencil"])
    direct = _render(parity_stroke)
    output_dir = ROOT / "debugCapture" / "painter" / "evidence_audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    export_path = output_dir / "m51_legacy_brush_export.png"
    export_ok = render_strokes_to_png(
        [parity_stroke], direct.width(), direct.height(), str(export_path)
    )
    exported = QImage(str(export_path))
    pil = compose_pil_paint_overlays(
        strokes=[parity_stroke], frame_size=(direct.width(), direct.height())
    )
    direct_rgba = _rgba_bytes(direct)
    export_rgba = _rgba_bytes(exported)
    pil_rgba = pil.convert("RGBA").tobytes()
    direct_export_max_delta = _max_rgba_delta(direct_rgba, export_rgba)

    noise_a = deterministic_unit(stable_style_seed("graphite_pencil"), 17)
    noise_b = deterministic_unit(stable_style_seed("graphite_pencil"), 17)
    noise_other = deterministic_unit(stable_style_seed("charcoal_vine"), 17)

    small_bounds = small_metrics["bounds"]
    large_bounds = large_metrics["bounds"]
    checks = {
        "all_profiles_have_presets": len(preset_by_style) == len(DESIGNER_BRUSH_RENDER_PROFILES),
        "all_retained_styles_have_presets": len(retained_preset_by_style)
        == len(PAINT_TEXTURED_BRUSH_STYLES),
        "no_profile_shadows_public_controls": not shadowed,
        "all_profiles_render_nonempty": all(
            int(metrics["count"]) > 0 for metrics in profile_metrics.values()
        ),
        "all_profile_renders_repeat_exactly": repeat_equal,
        "all_retained_style_renders_repeat_exactly": retained_repeat_equal,
        "profile_fixture_hashes_are_distinct": len(set(profile_hashes.values()))
        == len(profile_hashes),
        "retained_style_fixture_hashes_are_distinct": len(set(retained_hashes.values()))
        == len(retained_hashes),
        "all_retained_styles_render_nonempty": all(
            int(metrics["count"]) > 0 for metrics in retained_metrics.values()
        ),
        "public_width_increases_pixel_tip_extent": bool(
            small_bounds and large_bounds
            and (large_bounds[3] - large_bounds[1]) > (small_bounds[3] - small_bounds[1])
        ),
        "public_opacity_increases_measured_alpha": int(low_metrics["max_alpha"])
        < int(high_metrics["max_alpha"]),
        "public_spacing_changes_dab_accumulation": int(dense_metrics["max_alpha"])
        > int(sparse_metrics["max_alpha"]),
        "public_hardness_changes_designer_profile_pixels": _rgba_bytes(hardness_hard)
        != _rgba_bytes(hardness_soft),
        "public_roundness_changes_designer_profile_pixels": _rgba_bytes(roundness_round)
        != _rgba_bytes(roundness_flat),
        "public_angle_changes_designer_profile_pixels": _rgba_bytes(angle_zero)
        != _rgba_bytes(angle_rotated),
        "all_public_tip_controls_change_loaded_oil_pixels": all(
            oil_control_base_rgba != _rgba_bytes(image)
            for image in oil_control_variants.values()
        ),
        "cumulative_sampling_is_tessellation_invariant": sparse_samples
        == tessellated_samples and sparse_workload == tessellated_workload,
        "bounded_sampling_keeps_both_path_endpoints": len(bounded_samples) == 4
        and bounded_samples[0][:2] == (0.0, 0.0)
        and bounded_samples[-1][:2] == (10.0, 0.0),
        "bounded_sampling_emits_degradation_diagnostic": bounded_workload["degraded"] is True
        and bounded_workload["estimated_samples"] == 1001
        and bounded_workload["rendered_samples"] == 4,
        "blake2b_noise_repeats_and_separates_styles": noise_a == noise_b
        and noise_a != noise_other,
        "preview_export_rgba_within_measured_one_lsb": export_ok
        and direct_export_max_delta <= 1,
        "export_pil_overlay_rgba_exact": export_rgba == pil_rgba,
    }
    report = {
        "schema": "tigerstudio.painter.legacy-brush-measurement.v1",
        "scope": "painting_only_ui_design_excluded",
        "claim_boundary": {
            "tiger_authored_model": True,
            "physical_media_claim": False,
            "external_brush_engine_pixel_parity_claim": False,
            "visual_quality_acceptance_claim": False,
        },
        "official_sources": [
            "https://doc.qt.io/qt-6/qpen.html",
            "https://doc.qt.io/qt-6/qpainter.html",
            "https://docs.krita.org/en/reference_manual/brushes/brush_settings/options.html",
            "https://helpx.adobe.com/photoshop/desktop/apply-painting-techniques/brushes-presets/create-brush-set-painting-options.html",
            "https://product.corel.com/help/Painter/540219480/Main/EN/Win-Documentation/Corel-Painter-Spacing-controls.html",
            "https://www.rfc-editor.org/rfc/rfc7693",
        ],
        "geometry_contract": LEGACY_BRUSH_GEOMETRY_CONTRACT,
        "profile_count": len(profile_hashes),
        "profile_hashes": profile_hashes,
        "profile_metrics": profile_metrics,
        "retained_style_count": len(retained_hashes),
        "retained_style_hashes": retained_hashes,
        "retained_style_metrics": retained_metrics,
        "shadowed_public_controls": shadowed,
        "control_metrics": {
            "width_small": small_metrics,
            "width_large": large_metrics,
            "opacity_low": low_metrics,
            "opacity_high": high_metrics,
            "spacing_dense": dense_metrics,
            "spacing_sparse": sparse_metrics,
        },
        "sampling": {
            "normal": sparse_workload,
            "bounded": bounded_workload,
            "bounded_x": [sample[0] for sample in bounded_samples],
        },
        "parity_hashes": {
            "direct": hashlib.sha256(direct_rgba).hexdigest(),
            "export": hashlib.sha256(export_rgba).hexdigest(),
            "pil_overlay": hashlib.sha256(pil_rgba).hexdigest(),
            "preview_export_max_delta_lsb": direct_export_max_delta,
        },
        "checks": checks,
        "checks_passed": sum(bool(value) for value in checks.values()),
        "checks_total": len(checks),
        "passed": all(checks.values()),
    }
    report_path = output_dir / "m51_legacy_brush.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "path": str(report_path),
        "passed": report["passed"],
        "checks_passed": report["checks_passed"],
        "checks_total": report["checks_total"],
        "profile_count": report["profile_count"],
        "parity_hashes": report["parity_hashes"],
    }, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

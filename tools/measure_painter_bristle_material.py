"""Measure M52 bristle-v2 and stylized material invariants on fixed fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


OFFICIAL_SOURCES = {
    "qt_tablet_event": "https://doc.qt.io/qtforpython-6/PySide6/QtGui/QTabletEvent.html",
    "qt_qimage": "https://doc.qt.io/qt-6/qimage.html",
    "corel_bristle_controls": "https://product.corel.com/help/Painter/540219480/Main/EN/Win-Documentation/Corel-Painter-Bristle-controls.html",
    "corel_thick_paint_controls": "https://product.corel.com/help/Painter/540219480/Main/EN/Win-Documentation/Corel-Painter-Thick-Paint-Brush-controls.html",
    "adobe_mixer_brush": "https://helpx.adobe.com/photoshop/using/painting-mixer-brush.html",
    "khronos_gltf_materials": "https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html",
    "rfc7693_blake2": "https://www.rfc-editor.org/rfc/rfc7693",
}


def _qimage_bytes(image: Any) -> bytes:
    return bytes(image.constBits())


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _render(stroke: Any, width: int = 224, height: int = 128) -> Any:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter

    from app.drawing import DrawingCanvas

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        DrawingCanvas._paint_stroke(painter, stroke, width, height)
    finally:
        painter.end()
    return image


def measure() -> dict[str, Any]:
    import numpy as np
    from PIL import Image
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from app.drawing import PaintLayer, Stroke, render_strokes_to_png
    from app.painter_brush_engine_v2 import (
        AUTO_BRISTLE_DENSITY_PER_PIXEL,
        BRISTLE_ENGINE_MODEL_CONTRACT,
        BRISTLE_V2_STYLES,
        MAX_EXPLICIT_BRISTLE_COUNT,
        bristle_lane_paths,
        incremental_stroke_segments,
        resolved_bristle_count,
    )
    from app.painter_material_paint import (
        MATERIAL_PAINT_MODEL_CONTRACT,
        _blur,
        brush_material_capability,
        material_preview_rgba,
        rasterize_material_channels,
    )

    base = Stroke(
        points=[(0.08, 0.68), (0.34, 0.24), (0.62, 0.72), (0.92, 0.30)],
        color=(202, 86, 31),
        opacity=231,
        width_px=31,
        brush_style="bristle_oil",
        brush_spacing=25,
        brush_engine_version=2,
        bristle_count=16,
        brush_seed=0x52425253,
        point_pressure=[0.36, 0.94, 0.71, 0.48],
        point_tilt=[0.5, 0.5, 0.5, 0.5],
        point_tilt_x=[0.0, 0.42, -0.28, 0.16],
        point_tilt_y=[0.0, -0.24, 0.31, -0.18],
        point_rotation=[0.18, 0.72, 0.46, 0.83],
        point_load=[1.0, 0.86, 0.67, 0.49],
        load_depletion=0.32,
        load_dryout_px=512.0,
    )
    replay = _render(base)
    repeated = _render(base)
    replay_hash = _hash_bytes(_qimage_bytes(replay))
    repeat_hash = _hash_bytes(_qimage_bytes(repeated))

    zero_pressure = Stroke(
        **{
            **base.__dict__,
            "point_pressure": [0.0] * len(base.points),
            "point_load": [1.0] * len(base.points),
        }
    )
    zero_load = Stroke(
        **{
            **base.__dict__,
            "point_pressure": [1.0] * len(base.points),
            "point_load": [0.0] * len(base.points),
        }
    )
    transparent = bytes(len(_qimage_bytes(replay)))

    low_pressure = Stroke(**{**base.__dict__, "point_pressure": [0.2] * len(base.points)})
    high_pressure = Stroke(**{**base.__dict__, "point_pressure": [0.9] * len(base.points)})
    tilted = Stroke(**{**base.__dict__, "point_tilt_x": [0.8] * len(base.points)})
    low_count = Stroke(**{**base.__dict__, "bristle_count": 1})
    high_count = Stroke(**{**base.__dict__, "bristle_count": MAX_EXPLICIT_BRISTLE_COUNT})
    soft_tip = Stroke(**{**base.__dict__, "brush_hardness": 0})
    round_tip = Stroke(**{**base.__dict__, "brush_roundness": 100})
    flat_tip = Stroke(**{**base.__dict__, "brush_roundness": 25})
    angled_tip = Stroke(**{**base.__dict__, "brush_roundness": 25, "brush_angle": 67})
    sparse_tip = Stroke(**{**base.__dict__, "brush_spacing": 100})
    response_hashes = {
        "low_pressure": _hash_bytes(_qimage_bytes(_render(low_pressure))),
        "high_pressure": _hash_bytes(_qimage_bytes(_render(high_pressure))),
        "tilted": _hash_bytes(_qimage_bytes(_render(tilted))),
        "one_bristle": _hash_bytes(_qimage_bytes(_render(low_count))),
        "sixty_four_bristles": _hash_bytes(_qimage_bytes(_render(high_count))),
        "soft_tip": _hash_bytes(_qimage_bytes(_render(soft_tip))),
        "round_tip": _hash_bytes(_qimage_bytes(_render(round_tip))),
        "flat_tip": _hash_bytes(_qimage_bytes(_render(flat_tip))),
        "angled_tip": _hash_bytes(_qimage_bytes(_render(angled_tip))),
        "sparse_tip": _hash_bytes(_qimage_bytes(_render(sparse_tip))),
    }

    style_hashes: dict[str, str] = {}
    style_nonempty: dict[str, bool] = {}
    style_zero_pressure_identity: dict[str, bool] = {}
    style_zero_load_identity: dict[str, bool] = {}
    for style in sorted(BRISTLE_V2_STYLES):
        image = _render(Stroke(**{**base.__dict__, "brush_style": style}))
        raw = _qimage_bytes(image)
        style_hashes[style] = _hash_bytes(raw)
        style_nonempty[style] = raw != bytes(len(raw))
        style_zero_pressure_identity[style] = _qimage_bytes(
            _render(Stroke(**{**zero_pressure.__dict__, "brush_style": style}))
        ) == transparent
        style_zero_load_identity[style] = _qimage_bytes(
            _render(Stroke(**{**zero_load.__dict__, "brush_style": style}))
        ) == transparent

    segmented_image = None
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from app.drawing import DrawingCanvas

    segmented_image = QImage(224, 128, QImage.Format.Format_ARGB32_Premultiplied)
    segmented_image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(segmented_image)
    try:
        for segment in incremental_stroke_segments(base, width=224, height=128):
            DrawingCanvas._paint_stroke(painter, segment, 224, 128)
    finally:
        painter.end()
    segmented_hash = _hash_bytes(_qimage_bytes(segmented_image))

    output_dir = ROOT / "debugCapture" / "painter" / "evidence_audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "m52_bristle_export.png"
    if not render_strokes_to_png([base], 224, 128, str(png_path)):
        raise RuntimeError("M52 bristle PNG export failed")
    exported_rgba = np.asarray(Image.open(png_path).convert("RGBA"), dtype=np.int16)
    direct_rgba = np.empty_like(exported_rgba)
    for y in range(replay.height()):
        for x in range(replay.width()):
            color = replay.pixelColor(x, y)
            direct_rgba[y, x] = (color.red(), color.green(), color.blue(), color.alpha())
    preview_export_delta = int(np.max(np.abs(direct_rgba - exported_rgba)))

    layer = PaintLayer("m52-material", "M52 material", layer_type="material")
    material_base = Stroke(
        **{
            **base.__dict__,
            "layer_id": layer.layer_id,
            "material_enabled": True,
            "material_load": 1.0,
            "material_thickness": 0.88,
            "material_wetness": 0.25,
            "material_gloss": 0.20,
            "material_roughness": 0.55,
            "material_plow": 0.0,
        }
    )

    def channels(**changes: Any) -> dict[str, Any]:
        stroke = Stroke(**{**material_base.__dict__, **changes})
        return rasterize_material_channels([stroke], [layer], width=224, height=128)

    material = channels()
    material_repeat = channels()
    material_zero_pressure = channels(point_pressure=[0.0] * len(base.points))
    material_zero_load = channels(point_load=[0.0] * len(base.points))
    material_low_load = channels(point_load=[0.2] * len(base.points))
    material_high_load = channels(point_load=[1.0] * len(base.points))
    material_rough_zero = channels(material_roughness=0.0, material_wetness=0.0, material_gloss=0.0)
    material_rough_full = channels(material_roughness=1.0, material_wetness=0.0, material_gloss=0.0)

    material_style_hashes: dict[str, str] = {}
    material_style_zero_endpoint_identity: dict[str, bool] = {}
    for style in sorted(BRISTLE_V2_STYLES):
        style_channels = channels(brush_style=style)
        material_style_hashes[style] = _hash_bytes(
            np.asarray(style_channels["signed_height"]).tobytes()
            + np.asarray(style_channels["roughness"]).tobytes()
        )
        zero_pressure_channels = channels(
            brush_style=style,
            point_pressure=[0.0] * len(base.points),
            point_load=[1.0] * len(base.points),
        )
        zero_load_channels = channels(
            brush_style=style,
            point_pressure=[1.0] * len(base.points),
            point_load=[0.0] * len(base.points),
        )
        material_style_zero_endpoint_identity[style] = all(
            float(np.max(candidate[name])) == 0.0
            for candidate in (zero_pressure_channels, zero_load_channels)
            for name in ("coverage", "height", "excavation")
        )

    channel_names = ("signed_height", "coverage", "roughness", "normal", "ao", "shading")
    material_hash = _hash_bytes(b"".join(np.asarray(material[name]).tobytes() for name in channel_names))
    material_repeat_hash = _hash_bytes(
        b"".join(np.asarray(material_repeat[name]).tobytes() for name in channel_names)
    )
    material_preview_hash = _hash_bytes(material_preview_rgba(material).tobytes())
    material_preview_repeat_hash = _hash_bytes(material_preview_rgba(material_repeat).tobytes())

    original_cv2 = sys.modules.get("cv2", ...)
    sys.modules["cv2"] = None
    try:
        impulse = np.zeros((21, 21), dtype=np.float32)
        impulse[10, 10] = 1.0
        impulse[3, 3] = 1.0 / 1024.0
        blur_a = _blur(impulse, 2.0)
        blur_b = _blur(impulse, 2.0)
    finally:
        if original_cv2 is ...:
            sys.modules.pop("cv2", None)
        else:
            sys.modules["cv2"] = original_cv2

    auto_widths = (0.25, 10.0, 100.0, 200.0)
    auto_counts = {
        str(width): resolved_bristle_count(Stroke(bristle_count=0), width)
        for width in auto_widths
    }
    checks = {
        "model_claims_are_bounded": (
            BRISTLE_ENGINE_MODEL_CONTRACT["deterministic_replay_claim"] is True
            and BRISTLE_ENGINE_MODEL_CONTRACT["physical_bristle_claim"] is False
            and BRISTLE_ENGINE_MODEL_CONTRACT["paint_rheology_claim"] is False
            and brush_material_capability("bristle_oil")["physical_media_claim"] is False
            and MATERIAL_PAINT_MODEL_CONTRACT["deterministic_replay_claim"] is True
            and MATERIAL_PAINT_MODEL_CONTRACT["physical_media_claim"] is False
            and MATERIAL_PAINT_MODEL_CONTRACT["paint_rheology_claim"] is False
            and MATERIAL_PAINT_MODEL_CONTRACT["external_product_pixel_parity_claim"] is False
        ),
        "all_bristle_styles_nonempty": all(style_nonempty.values()),
        "all_bristle_styles_have_distinct_rgba": len(set(style_hashes.values()))
        == len(style_hashes),
        "bristle_replay_exact": replay_hash == repeat_hash,
        "whole_stroke_matches_incremental_segments": replay_hash == segmented_hash,
        "zero_pressure_color_is_exact_identity_for_all_styles": all(
            style_zero_pressure_identity.values()
        ),
        "zero_load_color_is_exact_identity_for_all_styles": all(
            style_zero_load_identity.values()
        ),
        "pressure_changes_color_pixels": response_hashes["low_pressure"] != response_hashes["high_pressure"],
        "tilt_changes_color_pixels": response_hashes["tilted"] != replay_hash,
        "bristle_count_changes_color_pixels": response_hashes["one_bristle"] != response_hashes["sixty_four_bristles"],
        "public_hardness_changes_bristle_pixels": response_hashes["soft_tip"] != replay_hash,
        "public_roundness_changes_bristle_pixels": response_hashes["round_tip"] != response_hashes["flat_tip"],
        "public_angle_changes_bristle_pixels": response_hashes["flat_tip"] != response_hashes["angled_tip"],
        "public_spacing_changes_bristle_pixels": response_hashes["sparse_tip"] != replay_hash,
        "explicit_sixty_four_bristles_are_materialized": len(bristle_lane_paths(high_count, width=224, height=128)) == MAX_EXPLICIT_BRISTLE_COUNT,
        "auto_density_uses_public_width_and_published_capacity": (
            auto_counts["0.25"] == 1
            and auto_counts["10.0"] == round(10.0 * AUTO_BRISTLE_DENSITY_PER_PIXEL)
            and auto_counts["100.0"] == round(100.0 * AUTO_BRISTLE_DENSITY_PER_PIXEL)
            and auto_counts["200.0"] == MAX_EXPLICIT_BRISTLE_COUNT
        ),
        "preview_export_within_one_lsb": preview_export_delta <= 1,
        "material_channels_replay_exact": material_hash == material_repeat_hash,
        "all_material_styles_have_distinct_height_roughness": len(
            set(material_style_hashes.values())
        )
        == len(material_style_hashes),
        "material_preview_replay_exact": material_preview_hash == material_preview_repeat_hash,
        "zero_pressure_material_is_exact_identity": float(np.max(material_zero_pressure["coverage"])) == 0.0 and float(np.max(material_zero_pressure["height"])) == 0.0,
        "zero_load_material_is_exact_identity": float(np.max(material_zero_load["coverage"])) == 0.0 and float(np.max(material_zero_load["height"])) == 0.0,
        "all_material_styles_have_exact_zero_endpoints": all(
            material_style_zero_endpoint_identity.values()
        ),
        "load_increases_material_deposit": float(np.sum(material_high_load["height"])) > float(np.sum(material_low_load["height"])),
        "roughness_endpoints_change_material_channel": not np.array_equal(material_rough_zero["roughness"], material_rough_full["roughness"]),
        "numpy_blur_fallback_replays_exactly": np.array_equal(blur_a, blur_b),
        "numpy_blur_preserves_sub_8bit_signal": float(blur_a[3, 3]) > 0.0,
    }
    return {
        "schema": "tigerstudio.painter.bristle_material_measurement.v1",
        "scope": "painting_only_ui_design_excluded",
        "official_sources": OFFICIAL_SOURCES,
        "claim_boundary": {
            "physical_bristle_or_rheology": False,
            "external_product_pixel_parity": False,
            "visual_quality_certification": False,
            "validated_claim": "deterministic_tiger_authored_control_response_and_pipeline_parity",
        },
        "measurements": {
            "style_count": len(style_hashes),
            "style_hashes": style_hashes,
            "style_zero_pressure_identity": style_zero_pressure_identity,
            "style_zero_load_identity": style_zero_load_identity,
            "replay_sha256": replay_hash,
            "segmented_sha256": segmented_hash,
            "export_sha256": _hash_bytes(exported_rgba.tobytes()),
            "preview_export_max_delta_lsb": preview_export_delta,
            "response_hashes": response_hashes,
            "auto_bristle_counts": auto_counts,
            "material_channel_sha256": material_hash,
            "material_preview_sha256": material_preview_hash,
            "material_style_hashes": material_style_hashes,
            "material_style_zero_endpoint_identity": (
                material_style_zero_endpoint_identity
            ),
            "low_load_height_sum": float(np.sum(material_low_load["height"])),
            "high_load_height_sum": float(np.sum(material_high_load["height"])),
            "fallback_blur_sha256": _hash_bytes(blur_a.tobytes()),
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(
            ROOT
            / "debugCapture"
            / "painter"
            / "evidence_audit"
            / "m52_bristle_material.json"
        ),
    )
    args = parser.parse_args(argv)
    report = measure()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "path": str(output),
                "passed": report["passed"],
                "checks_passed": sum(bool(value) for value in report["checks"].values()),
                "checks_total": len(report["checks"]),
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

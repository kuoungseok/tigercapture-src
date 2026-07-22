"""Render a durable GLTF through Motion Designer's real AR/PBR GPU adapter."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_ASSET = (
    ROOT / "sample_assets" / "pbr_blender_scenes" / "polyhaven" / "models"
    / "Camera_01" / "Camera_01_1k.gltf"
)
DEFAULT_OUTPUT = ROOT / "debugCapture" / "motion_designer" / "ar_pbr"


def _rgba_array(image) -> Any:
    import numpy as np
    from PySide6.QtGui import QImage

    straight = image.convertToFormat(QImage.Format_RGBA8888)
    rows = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(
        straight.height(), straight.bytesPerLine(),
    )
    return rows[:, : straight.width() * 4].reshape(straight.height(), straight.width(), 4).copy()


def _summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    rows = diagnostics.get("rows") if isinstance(diagnostics.get("rows"), list) else []
    row = rows[0] if rows and isinstance(rows[0], dict) else {}
    textures = row.get("textures") if isinstance(row.get("textures"), dict) else {}
    mesh = row.get("mesh") if isinstance(row.get("mesh"), dict) else {}
    model_view = row.get("model_view") if isinstance(row.get("model_view"), dict) else {}
    shadow_filter = row.get("shadow_filter") if isinstance(row.get("shadow_filter"), dict) else {}
    return {
        "ok": bool(diagnostics.get("ok")),
        "mode": str(diagnostics.get("mode") or ""),
        "renderer_quality": str(diagnostics.get("renderer_quality") or ""),
        "fallback": bool(diagnostics.get("fallback", True)),
        "full_gpu_export_available": bool(diagnostics.get("full_gpu_export_available")),
        "rendered_track_count": int(diagnostics.get("rendered_track_count", 0) or 0),
        "quality": str(diagnostics.get("quality") or ""),
        "pbr_depth_occlusion_applied": bool(diagnostics.get("pbr_depth_occlusion_applied")),
        "pbr_depth_occluded_pixels": int(diagnostics.get("pbr_depth_occluded_pixels", 0) or 0),
        "texture_map_count": int(textures.get("map_count", 0) or 0),
        "texture_missing_count": int(textures.get("missing_count", 0) or 0),
        "mesh_vertex_count": int(mesh.get("vertex_count", 0) or 0),
        "mesh_triangle_count": int(mesh.get("triangle_count", 0) or 0),
        "auto_fit": bool(model_view.get("auto_fit")),
        "fit_zoom": float(model_view.get("zoom", 0.0) or 0.0),
        "fov_deg": float(model_view.get("fov_deg", 0.0) or 0.0),
        "shadow_map_enabled": bool(row.get("shadow_map_enabled")),
        "shadow_filter": str(shadow_filter.get("filter") or ""),
        "warnings": list(diagnostics.get("warnings") or []),
        "errors": list(diagnostics.get("errors") or []),
    }


def _image_metrics(rgba) -> dict[str, Any]:
    import numpy as np

    alpha = rgba[..., 3]
    ys, xs = np.nonzero(alpha)
    if len(xs):
        bounds = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    else:
        bounds = [0, 0, 0, 0]
    width = max(0, bounds[2] - bounds[0])
    height = max(0, bounds[3] - bounds[1])
    return {
        "alpha_pixel_count": int(np.count_nonzero(alpha)),
        "alpha_coverage": float(np.count_nonzero(alpha) / alpha.size),
        "visible_bounds": bounds,
        "visible_width_ratio": float(width / rgba.shape[1]),
        "visible_height_ratio": float(height / rgba.shape[0]),
        "rgb_sum": int(rgba[..., :3].sum()),
    }


def _save_evidence(output: Path, images: list[tuple[str, Any]]) -> Path:
    from PIL import Image, ImageDraw

    panels = []
    for title, rgba in images:
        source = Image.fromarray(rgba, "RGBA")
        panel = Image.new("RGBA", (source.width, source.height + 34), (28, 31, 37, 255))
        checker = Image.new("RGBA", source.size, (47, 51, 59, 255))
        panel.alpha_composite(checker, (0, 34))
        panel.alpha_composite(source, (0, 34))
        ImageDraw.Draw(panel).text((12, 10), title, fill=(235, 239, 245, 255))
        panels.append(panel)
    evidence = Image.new(
        "RGBA", (sum(panel.width for panel in panels), max(panel.height for panel in panels)),
        (18, 20, 24, 255),
    )
    x = 0
    for panel in panels:
        evidence.alpha_composite(panel, (x, 0))
        x += panel.width
    path = output / "evidence.png"
    evidence.convert("RGB").save(path, quality=95)
    return path


def run_qa(asset: Path = DEFAULT_ASSET, output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    import numpy as np
    from PySide6.QtGui import QGuiApplication

    from app.motion_designer.adapters.ar_pbr import ar_pbr_diagnostics, clear_ar_pbr_cache
    from app.motion_designer.ar_pbr_source import (
        create_ar_pbr_layer,
        create_camera_layer,
        create_light_layer,
        evaluate_ar_pbr_frame,
        set_depth_group,
    )
    from app.motion_designer.export_renderer import MotionExportRenderer
    from app.motion_designer.render_graph import build_render_graph, render_graph_image
    from app.motion_designer.schema import AnimatedProperty, Keyframe, MotionComposition

    app = QGuiApplication.instance() or QGuiApplication(["qa_motion_ar_pbr"])
    asset = asset.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not asset.is_file():
        return {"schema": "tiger.motion_designer.ar_pbr_qa.v1", "ok": False, "error": "asset_missing", "asset": str(asset)}

    composition = MotionComposition(
        name="M8 AR PBR GPU QA", width=640, height=360, fps=30.0, duration_ms=2000,
    )
    model = create_ar_pbr_layer(asset, width=composition.width, height=composition.height, duration_ms=composition.duration_ms)
    camera = create_camera_layer(duration_ms=composition.duration_ms)
    light = create_light_layer(duration_ms=composition.duration_ms)
    camera.source.params["rotation"] = AnimatedProperty(
        value_type="vector3", default=[0.0, 0.0, 0.0],
        keyframes=[Keyframe(time_ms=0, value=[0.0, -12.0, 0.0]), Keyframe(time_ms=1000, value=[0.0, 18.0, 0.0])],
    ).to_dict()
    camera.source.params["fov"] = AnimatedProperty(
        default=45.0, keyframes=[Keyframe(time_ms=0, value=40.0), Keyframe(time_ms=1000, value=52.0)],
    ).to_dict()
    light.source.params["color"] = AnimatedProperty(value_type="color3", default=[1.0, .91, .78]).to_dict()
    light.source.params["intensity"] = AnimatedProperty(default=.72).to_dict()
    model.source.params["material"]["clearcoat"] = AnimatedProperty(default=.18).to_dict()
    model.source.params["material"]["clearcoat_roughness"] = AnimatedProperty(default=.12).to_dict()
    composition.layers = [model, camera, light]

    sample_time_ms = 500.0
    start_state = evaluate_ar_pbr_frame(model, 0, composition=composition, composition_time_ms=0)
    end_state = evaluate_ar_pbr_frame(model, 1000, composition=composition, composition_time_ms=1000)

    started = time.perf_counter()
    clear_ar_pbr_cache()
    preview = render_graph_image(build_render_graph(
        composition, sample_time_ms, render_quality="preview",
        output_size=(composition.width, composition.height),
    ))
    preview_ms = (time.perf_counter() - started) * 1000.0
    preview_diag = _summary(ar_pbr_diagnostics(model.id))

    started = time.perf_counter()
    clear_ar_pbr_cache()
    exported = MotionExportRenderer().render_frame(composition, sample_time_ms, use_cache=False)
    export_ms = (time.perf_counter() - started) * 1000.0
    export_diag = _summary(ar_pbr_diagnostics(model.id))
    preview_rgba = _rgba_array(preview)
    export_rgba = _rgba_array(exported)
    preview.save(str(output / "preview.png"), "PNG")
    exported.save(str(output / "export.png"), "PNG")

    difference = np.abs(preview_rgba.astype(np.int16) - export_rgba.astype(np.int16))
    parity = {
        "max_abs_channel_error": int(difference.max()),
        "mean_abs_channel_error": float(difference.mean()),
        "different_pixel_count": int(np.count_nonzero(np.any(difference != 0, axis=2))),
        "tolerance": 2,
    }
    preview_metrics = _image_metrics(preview_rgba)
    export_metrics = _image_metrics(export_rgba)

    depth_path = output / "depth_half_plane.npy"
    depth = np.ones((composition.height, composition.width), dtype=np.float32)
    depth[:, : composition.width // 2] = .2
    np.save(depth_path, depth)
    depth_group = set_depth_group(
        composition, member_layer_ids=[model.id], depth_source_id="qa_half_plane",
        depth_frame_path=str(depth_path), occlusion=True,
    )
    composition.revision += 1
    clear_ar_pbr_cache()
    depth_image = MotionExportRenderer().render_frame(composition, sample_time_ms, use_cache=False)
    depth_rgba = _rgba_array(depth_image)
    depth_image.save(str(output / "depth_occlusion.png"), "PNG")
    depth_diag = _summary(ar_pbr_diagnostics(model.id))
    evidence_path = _save_evidence(output, [
        ("MOTION PREVIEW / FULL GPU", preview_rgba),
        ("MOTION EXPORT / FULL GPU", export_rgba),
        ("DEPTH GROUP OCCLUSION", depth_rgba),
    ])

    keyframes_ok = (
        start_state.settings["model_view"]["fov_deg"] != end_state.settings["model_view"]["fov_deg"]
        and start_state.track["transform"]["rotation"] != end_state.track["transform"]["rotation"]
    )
    diagnostics_ok = all(
        row["ok"]
        and row["mode"] == "full_model_view_gpu_export_service"
        and row["renderer_quality"] == "full_model_view_gpu_pbr"
        and not row["fallback"]
        and row["full_gpu_export_available"]
        and row["rendered_track_count"] == 1
        and row["texture_map_count"] > 0
        and row["texture_missing_count"] == 0
        and row["auto_fit"]
        and row["shadow_map_enabled"]
        for row in (preview_diag, export_diag)
    )
    framing_ok = (
        export_metrics["visible_width_ratio"] >= .15
        and export_metrics["visible_height_ratio"] >= .10
        and export_metrics["alpha_coverage"] >= .01
    )
    parity_ok = parity["max_abs_channel_error"] <= parity["tolerance"]
    depth_metrics = _image_metrics(depth_rgba)
    depth_ok = (
        depth_diag["pbr_depth_occlusion_applied"]
        and depth_diag["pbr_depth_occluded_pixels"] > 0
    )
    depth_ok = bool(depth_ok and depth_metrics["alpha_pixel_count"] < export_metrics["alpha_pixel_count"])
    ok = bool(diagnostics_ok and framing_ok and parity_ok and depth_ok and keyframes_ok)
    return {
        "schema": "tiger.motion_designer.ar_pbr_qa.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "milestone": "M8",
        "ok": ok,
        "asset": str(asset),
        "asset_is_durable": asset.is_relative_to(ROOT / "sample_assets"),
        "composition": {"width": composition.width, "height": composition.height, "sample_time_ms": sample_time_ms},
        "preview": {"path": str(output / "preview.png"), "render_ms": round(preview_ms, 3), "metrics": preview_metrics, "diagnostics": preview_diag},
        "export": {"path": str(output / "export.png"), "render_ms": round(export_ms, 3), "metrics": export_metrics, "diagnostics": export_diag},
        "parity": {**parity, "ok": parity_ok},
        "framing": {"ok": framing_ok, "minimum_width_ratio": .15, "minimum_height_ratio": .10, "minimum_alpha_coverage": .01},
        "keyframe_evaluation": {
            "ok": keyframes_ok,
            "start_fov": start_state.settings["model_view"]["fov_deg"],
            "end_fov": end_state.settings["model_view"]["fov_deg"],
            "start_rotation": start_state.track["transform"]["rotation"],
            "end_rotation": end_state.track["transform"]["rotation"],
        },
        "depth_group": {"ok": depth_ok, "group": depth_group, "metrics": depth_metrics, "diagnostics": depth_diag},
        "evidence": str(evidence_path),
        "limitations": [
            "The current Motion AR/PBR adapter exposes one key light plus HDRI.",
            "Camera rotation is represented as inverse model orbit in the existing model-view renderer.",
            "Standalone depth groups require an explicit depth-frame path; editor video depth is supplied by the main composite bridge.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    report = run_qa(args.asset, args.output)
    report_path = args.output.resolve() / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": report.get("ok"), "report": str(report_path), "evidence": report.get("evidence"),
        "parity": report.get("parity"), "framing": report.get("framing"),
        "depth_ok": (report.get("depth_group") or {}).get("ok"),
    }, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

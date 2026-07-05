from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT_DIR = ROOT / "debugCapture" / "ar_pbr_export_bake_qa"
DEFAULT_REPORT = ROOT / "debugCapture" / "ar_pbr_export_bake_qa.json"


def _run_export(exporter) -> dict[str, Any]:
    events: dict[str, Any] = {"success": None, "error": ""}

    def _success(path, size):
        events["success"] = {"path": str(path), "size": int(size)}

    def _error(message):
        events["error"] = str(message)

    exporter.finished_success.connect(_success)
    exporter.finished_error.connect(_error)
    exporter.run()
    ok = bool(events.get("success")) and not bool(events.get("error"))
    events["ok"] = ok
    return events


def _read_rgb(path: Path, *, frame_index: int = 2):
    import cv2  # type: ignore

    cap = cv2.VideoCapture(str(path))
    if frame_index > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
    ok, bgr = cap.read()
    cap.release()
    if not ok or bgr is None:
        raise RuntimeError(f"Could not read frame from {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _solid_video(path: Path, *, color: str = "black", size: str = "128x128") -> None:
    import subprocess
    from imageio_ffmpeg import get_ffmpeg_exe

    ffmpeg = get_ffmpeg_exe()
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={size}:d=1:r=6",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace")[-1000:])


def _write_texture(path: Path, color: tuple[int, int, int] = (245, 86, 24)) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color).save(path)


def _ar_descriptor(
    *,
    base_texture: Path | None = None,
    roughness_texture: Path | None = None,
    metallic_texture: Path | None = None,
    specular_texture: Path | None = None,
    normal_texture: Path | None = None,
    occlusion_texture: Path | None = None,
) -> dict[str, Any]:
    material: dict[str, Any] = {
        "name": "BodyPaint",
        "base_color": [1.0, 0.28, 0.08, 1.0],
        "roughness": 0.32,
        "metallic": 0.0,
        "reflectance": 0.45,
    }
    if base_texture is not None:
        material["base_texture"] = str(base_texture)
    if roughness_texture is not None:
        material["roughness_texture"] = str(roughness_texture)
    if metallic_texture is not None:
        material["metallic_texture"] = str(metallic_texture)
    if specular_texture is not None:
        material["specular_texture"] = str(specular_texture)
    if normal_texture is not None:
        material["normal_texture"] = str(normal_texture)
    if occlusion_texture is not None:
        material["occlusion_texture"] = str(occlusion_texture)
    return {
        "id": "qa_ar_triangle",
        "geometries": [
            {
                "name": "triangle",
                "vertices": [[-1.0, -0.8, 0.0], [1.0, -0.8, 0.0], [0.0, 1.0, 0.0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0.0, 0.0, 0.0], "size": [2.0, 1.8, 1.0]},
            }
        ],
        "materials": [material],
    }


def _ar_track(*, asset_path: str = "qa_ar_model.glb", hdri_path: str = "") -> dict[str, Any]:
    from app.ar_pbr.schema import normalize_ar_track
    lighting = {
        "direct_strength": 1.35,
        "ibl_exposure": 1.2,
        "shadow_strength": 0.5,
        "light_azimuth": 35.0,
        "light_elevation": 50.0,
    }
    if hdri_path:
        lighting["hdri_path"] = hdri_path

    return normalize_ar_track(
        {
            "id": "ar_pbr_export_001",
            "type": "ar_pbr_object",
            "asset_path": asset_path,
            "start_ms": 0,
            "end_ms": 1000,
            "transform": {
                "position": [0.0, 0.0, 0.0],
                "rotation": [0.0, 12.0, 0.0],
                "scale": [1.8, 1.8, 1.8],
            },
            "occlusion": False,
            "shadow_catcher": True,
            "reflection_catcher": True,
            "render": {"lighting": lighting},
        }
    )


def run_ar_pbr_export_bake_qa(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    from PySide6.QtCore import QCoreApplication

    from app.video_exporter import VideoExportThread

    QCoreApplication.instance() or QCoreApplication([])
    out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
    report_path = report_path if report_path.is_absolute() else ROOT / report_path
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    source = out_dir / "source.mp4"
    baseline = out_dir / "baseline.mp4"
    processed = out_dir / "processed_ar_pbr.mp4"
    _solid_video(source, color="gray")
    for path in (baseline, processed):
        try:
            path.unlink()
        except OSError:
            pass

    segments = [(0, 1000, 1.0)]
    common = {
        "segments": segments,
        "quality_id": "low",
        "format_id": "mp4",
        "target_fps": 6.0,
    }
    baseline_exporter = VideoExportThread(source, baseline, **common)
    baseline_result = _run_export(baseline_exporter)

    asset = out_dir / "qa_ar_model.glb"
    asset.write_bytes(b"qa placeholder glb")
    texture = out_dir / "body_bodyd.png"
    roughness = out_dir / "body_bodyr.png"
    metallic = out_dir / "body_bodym.png"
    specular = out_dir / "body_bodys.png"
    normal = out_dir / "body_bodyn.png"
    occlusion = out_dir / "body_bodyao.png"
    _write_texture(texture, (245, 86, 24))
    _write_texture(roughness, (84, 84, 84))
    _write_texture(metallic, (12, 12, 12))
    _write_texture(specular, (210, 210, 210))
    _write_texture(normal, (128, 128, 255))
    _write_texture(occlusion, (128, 128, 128))
    hdri = out_dir / "qa_directional_env.hdr"
    import numpy as np
    from app.ar_pbr import export_packet_renderer as export_renderer

    export_renderer._HDRI_ARRAY_CACHE[str(hdri)] = np.asarray(
        [
            [[0.95, 0.18, 0.12], [0.20, 0.90, 0.34], [0.14, 0.26, 0.96], [0.88, 0.82, 0.24]],
            [[0.22, 0.36, 0.92], [0.92, 0.60, 0.20], [0.25, 0.86, 0.72], [0.70, 0.22, 0.84]],
        ],
        dtype=np.float32,
    )
    export_renderer._HDRI_AVERAGE_CACHE.pop(str(hdri), None)
    export_renderer._HDRI_PREFILTER_CACHE.pop(str(hdri), None)
    descriptor = _ar_descriptor(
        base_texture=texture,
        roughness_texture=roughness,
        metallic_texture=metallic,
        specular_texture=specular,
        normal_texture=normal,
        occlusion_texture=occlusion,
    )
    track = _ar_track(asset_path=str(asset), hdri_path=str(hdri))
    processed_exporter = VideoExportThread(
        source,
        processed,
        **common,
        ar_pbr_tracks=[track],
        ar_pbr_asset_descriptors={
            "ar_pbr_export_001": descriptor,
            str(asset): descriptor,
            asset.name: descriptor,
        },
    )
    previous_renderer = os.environ.get("TIGERCAPTURE_AR_PBR_EXPORT_RENDERER")
    os.environ["TIGERCAPTURE_AR_PBR_EXPORT_RENDERER"] = "packet"
    try:
        processed_result = _run_export(processed_exporter)
    finally:
        if previous_renderer is None:
            os.environ.pop("TIGERCAPTURE_AR_PBR_EXPORT_RENDERER", None)
        else:
            os.environ["TIGERCAPTURE_AR_PBR_EXPORT_RENDERER"] = previous_renderer

    import numpy as np

    baseline_rgb = _read_rgb(baseline)
    processed_rgb = _read_rgb(processed)
    diff = np.abs(processed_rgb.astype(np.int16) - baseline_rgb.astype(np.int16))
    mean_abs_diff = float(diff.mean())
    changed_ratio = float((diff.sum(axis=2) > 24).mean())
    baseline_luma = (
        0.2126 * baseline_rgb[:, :, 0].astype(np.float32)
        + 0.7152 * baseline_rgb[:, :, 1].astype(np.float32)
        + 0.0722 * baseline_rgb[:, :, 2].astype(np.float32)
    )
    processed_luma = (
        0.2126 * processed_rgb[:, :, 0].astype(np.float32)
        + 0.7152 * processed_rgb[:, :, 1].astype(np.float32)
        + 0.0722 * processed_rgb[:, :, 2].astype(np.float32)
    )
    darkened_pixels = int((baseline_luma - processed_luma > 5.5).sum())
    orange_pixels = int(
        (
            (processed_rgb[:, :, 0] > 90)
            & (processed_rgb[:, :, 1] > 18)
            & (processed_rgb[:, :, 1] < 150)
            & (processed_rgb[:, :, 2] < 90)
        ).sum()
    )
    diagnostics = getattr(processed_exporter, "_ar_pbr_last_export_diagnostics", {}) or {}
    checks = {
        "baseline_export_ok": bool(baseline_result.get("ok")) and baseline.exists() and baseline.stat().st_size > 1024,
        "processed_export_ok": bool(processed_result.get("ok")) and processed.exists() and processed.stat().st_size > 1024,
        "processed_differs_from_baseline": mean_abs_diff > 2.0 and changed_ratio > 0.01,
        "processed_has_ar_pbr_pixels": orange_pixels > 80,
        "export_diagnostics_packet_renderer": diagnostics.get("mode") == "gpu_packet_export",
        "export_rendered_track": int(diagnostics.get("rendered_track_count", 0) or 0) >= 1,
        "export_uses_preview_packet_mesh": int(diagnostics.get("mesh_triangle_count", 0) or 0) >= 1,
        "export_uses_preview_packet_shadow": int(diagnostics.get("shadow_triangle_count", 0) or 0) >= 8,
        "export_uses_preview_packet_reflection": int(diagnostics.get("reflection_triangle_count", 0) or 0) >= 2,
        "processed_has_catcher_darkening": darkened_pixels > 40,
        "packet_export_ssaa_enabled": int(diagnostics.get("ssaa_scale", 1) or 1) >= 2,
        "export_texture_plan_ready": int(diagnostics.get("texture_map_count", 0) or 0) >= 1
        and int(diagnostics.get("texture_material_count", 0) or 0) >= 1,
        "export_texture_tint_applied": int(diagnostics.get("texture_tinted_triangle_count", 0) or 0) >= 1,
        "export_texture_uv_sampling": int(diagnostics.get("texture_sampled_triangle_count", 0) or 0) >= 1,
        "export_pbr_packet_ready": int(diagnostics.get("packet_pbr_triangle_count", 0) or 0) >= 1,
        "export_pbr_material_maps": int(diagnostics.get("pbr_texture_map_count", 0) or 0) >= 5,
        "export_pbr_material_map_sampling": int(diagnostics.get("pbr_sampled_triangle_count", 0) or 0) >= 1,
        "export_pbr_hdri_directional_sampling": bool(diagnostics.get("pbr_hdri_directional_sampling"))
        and int(diagnostics.get("pbr_hdri_sampled_pixels", 0) or 0) > 0,
        "export_pbr_prefiltered_ibl": bool(diagnostics.get("pbr_prefiltered_ibl"))
        and int(diagnostics.get("pbr_prefiltered_ibl_pixels", 0) or 0) > 0
        and int(diagnostics.get("pbr_prefiltered_ibl_level_count", 0) or 0) >= 2,
        "export_pbr_occlusion_map": bool(diagnostics.get("pbr_occlusion_map_applied"))
        and int(diagnostics.get("pbr_occlusion_map_pixels", 0) or 0) > 0,
        "export_pbr_renderer_quality": diagnostics.get("renderer_quality") == "preview_packet_pbr_material_maps",
    }
    failures = [
        {"check": name, "message": "check failed"}
        for name, passed in checks.items()
        if not passed
    ]
    report = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "ar_pbr_export_bake",
        "source": str(source),
        "outputs": {
            "baseline": str(baseline),
            "processed": str(processed),
        },
        "summary": {
            "checks": len(checks),
            "passing": sum(1 for passed in checks.values() if passed),
            "mean_abs_diff": round(mean_abs_diff, 4),
            "changed_pixel_ratio": round(changed_ratio, 5),
            "orange_pixels": orange_pixels,
            "darkened_pixels": darkened_pixels,
            "ssaa_scale": int(diagnostics.get("ssaa_scale", 1) or 1),
            "texture_map_count": int(diagnostics.get("texture_map_count", 0) or 0),
            "texture_tinted_triangle_count": int(diagnostics.get("texture_tinted_triangle_count", 0) or 0),
            "texture_sampled_triangle_count": int(diagnostics.get("texture_sampled_triangle_count", 0) or 0),
            "pbr_triangle_count": int(diagnostics.get("pbr_triangle_count", 0) or 0),
            "packet_pbr_triangle_count": int(diagnostics.get("packet_pbr_triangle_count", 0) or 0),
            "pbr_sampled_triangle_count": int(diagnostics.get("pbr_sampled_triangle_count", 0) or 0),
            "pbr_texture_map_count": int(diagnostics.get("pbr_texture_map_count", 0) or 0),
            "pbr_hdri_sampled_pixels": int(diagnostics.get("pbr_hdri_sampled_pixels", 0) or 0),
            "pbr_prefiltered_ibl_pixels": int(diagnostics.get("pbr_prefiltered_ibl_pixels", 0) or 0),
            "pbr_prefiltered_ibl_level_count": int(diagnostics.get("pbr_prefiltered_ibl_level_count", 0) or 0),
            "pbr_occlusion_map_pixels": int(diagnostics.get("pbr_occlusion_map_pixels", 0) or 0),
            "renderer_quality": diagnostics.get("renderer_quality"),
        },
        "checks": checks,
        "diagnostics": diagnostics,
        "failures": failures,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report["report"] = str(report_path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify AR/PBR tracks bake into final export.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    report = run_ar_pbr_export_bake_qa(out_dir=args.out_dir, report_path=args.out)
    print(json.dumps({
        "ok": report.get("ok"),
        "report": report.get("report"),
        "summary": report.get("summary"),
        "failures": report.get("failures", []),
    }, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

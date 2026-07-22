"""Real MToon GPU evidence for the Motion Designer VRM source."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_VRM = ROOT / "external/assets/vtuber/booth_milica/Milica1.3free/Milica_v1.3.vrm"
DEFAULT_OUTPUT = ROOT / "debugCapture/motion_designer/vrm"


def _qimage_array(image) -> np.ndarray:
    from PySide6.QtGui import QImage

    converted = image.convertToFormat(QImage.Format_RGBA8888)
    bits = converted.bits()
    return np.frombuffer(bits, dtype=np.uint8, count=converted.sizeInBytes()).reshape(
        converted.height(), converted.bytesPerLine(),
    )[:, : converted.width() * 4].reshape(converted.height(), converted.width(), 4).copy()


def _alpha_metrics(array: np.ndarray) -> dict[str, Any]:
    alpha = array[:, :, 3]
    ys, xs = np.where(alpha > 8)
    if not xs.size:
        return {"visible": False, "bbox": [], "height_ratio": 0.0, "bottom_gap_px": array.shape[0]}
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    return {
        "visible": True,
        "bbox": bbox,
        "height_ratio": round((bbox[3] - bbox[1]) / float(array.shape[0]), 4),
        "width_ratio": round((bbox[2] - bbox[0]) / float(array.shape[1]), 4),
        "bottom_gap_px": int(array.shape[0] - bbox[3]),
        "visible_pixels": int(np.count_nonzero(alpha > 8)),
    }


def _save_contact_sheet(rows: list[dict[str, Any]], output: Path) -> None:
    tile_w, tile_h = rows[0]["image"].size
    header = 64
    sheet = Image.new("RGB", (tile_w * len(rows), tile_h + header), (15, 17, 21))
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        x = index * tile_w
        checker = Image.new("RGBA", (tile_w, tile_h), (31, 35, 42, 255))
        checker.alpha_composite(row["image"])
        sheet.paste(checker.convert("RGB"), (x, header))
        pose = row["diagnostics"].get("selected_motion") or {}
        draw.text((x + 10, 8), row["label"], fill=(235, 239, 244))
        draw.text(
            (x + 10, 30),
            f"yaw {pose.get('yaw_deg', 0):.1f}  pitch {pose.get('pitch_deg', 0):.1f}  "
            f"blink {pose.get('blink_l', 0):.2f}  mouth {pose.get('mouth_open', 0):.2f}",
            fill=(126, 180, 203),
        )
    sheet.save(output)


def run(output_dir: Path, *, size: int = 320) -> dict[str, Any]:
    if os.environ.get("QT_QPA_PLATFORM", "").casefold() == "offscreen":
        raise RuntimeError("Real VRM GPU QA cannot run with QT_QPA_PLATFORM=offscreen")
    from PySide6.QtWidgets import QApplication

    from app.motion_designer.adapters import vrm as adapter
    from app.motion_designer.schema import MotionComposition
    from app.motion_designer.ui.vrm_panel import VRMPanel
    from app.motion_designer.ui.style import MOTION_DESIGNER_QSS
    from app.motion_designer.vrm_source import create_vrm_layer

    app = QApplication.instance() or QApplication([])
    output_dir.mkdir(parents=True, exist_ok=True)
    body_layer = create_vrm_layer(
        DEFAULT_VRM, width=size, height=size, duration_ms=1000,
        params={
            "pose": {
                "yaw_deg": {"default": -14.0, "keyframes": [
                    {"time_ms": 0, "value": -14.0, "interpolation": {"kind": "linear"}},
                    {"time_ms": 500, "value": 16.0, "interpolation": {"kind": "linear"}},
                ]},
                "pitch_deg": {"default": -5.0, "keyframes": [
                    {"time_ms": 0, "value": -5.0, "interpolation": {"kind": "linear"}},
                    {"time_ms": 500, "value": 10.0, "interpolation": {"kind": "linear"}},
                ]},
                "mouth_open": {"default": 0.1, "keyframes": [
                    {"time_ms": 0, "value": 0.1, "interpolation": {"kind": "linear"}},
                    {"time_ms": 500, "value": 0.72, "interpolation": {"kind": "linear"}},
                ]},
                "blink_l": {"default": 0.0, "keyframes": [
                    {"time_ms": 0, "value": 0.0, "interpolation": {"kind": "linear"}},
                    {"time_ms": 500, "value": 1.0, "interpolation": {"kind": "linear"}},
                ]},
                "blink_r": {"default": 0.0, "keyframes": [
                    {"time_ms": 0, "value": 0.0, "interpolation": {"kind": "linear"}},
                    {"time_ms": 500, "value": 1.0, "interpolation": {"kind": "linear"}},
                ]},
                "idle_strength": {"default": 0.0},
            },
            "playback": {"idle_motion": False, "preview_cache_fps": 30.0},
            "placement": {
                "source_exposure": "full_body", "framing_preset": "full_body",
                "target_width_ratio": {"default": 0.72}, "target_height_ratio": {"default": 0.94},
                "output_center_x": {"default": 0.5}, "output_bottom_y": {"default": 0.985},
            },
            "render": {"gpu_warmup_frames": 1, "texture_max_size": 512, "reuse_gpu_widget": True},
        },
    )
    body_composition = MotionComposition(width=size, height=size, duration_ms=1000, layers=[body_layer])
    face_layer = create_vrm_layer(
        DEFAULT_VRM, width=size, height=size, duration_ms=1000,
        params={
            "pose": {
                "yaw_deg": {"default": -4.0, "keyframes": [
                    {"time_ms": 0, "value": -4.0, "interpolation": {"kind": "linear"}},
                    {"time_ms": 500, "value": 4.0, "interpolation": {"kind": "linear"}},
                ]},
                "mouth_open": {"default": 0.1, "keyframes": [
                    {"time_ms": 0, "value": 0.1, "interpolation": {"kind": "linear"}},
                    {"time_ms": 500, "value": 0.72, "interpolation": {"kind": "linear"}},
                ]},
                "blink_l": {"default": 0.0, "keyframes": [
                    {"time_ms": 0, "value": 0.0, "interpolation": {"kind": "linear"}},
                    {"time_ms": 500, "value": 1.0, "interpolation": {"kind": "linear"}},
                ]},
                "blink_r": {"default": 0.0, "keyframes": [
                    {"time_ms": 0, "value": 0.0, "interpolation": {"kind": "linear"}},
                    {"time_ms": 500, "value": 1.0, "interpolation": {"kind": "linear"}},
                ]},
                "idle_strength": {"default": 0.0},
            },
            "playback": {"idle_motion": False, "preview_cache_fps": 30.0},
            "placement": {
                "source_exposure": "chest_up", "framing_preset": "bust_up",
                "target_width_ratio": {"default": 0.82}, "target_height_ratio": {"default": 0.94},
                "output_center_x": {"default": 0.5}, "output_bottom_y": {"default": 0.985},
            },
            "render": {"gpu_warmup_frames": 1, "texture_max_size": 512, "reuse_gpu_widget": True},
        },
    )
    face_composition = MotionComposition(width=size, height=size, duration_ms=1000, layers=[face_layer])
    adapter.clear_vrm_cache()
    rows: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    arrays: list[np.ndarray] = []
    requests = (
        (body_layer, body_composition, "body", "Full body / look left", 0),
        (body_layer, body_composition, "body", "Full body / look right", 500),
        (face_layer, face_composition, "face", "Bust / eyes open", 0),
        (face_layer, face_composition, "face", "Bust / blink and speak", 500),
    )
    for active_layer, active_composition, prefix, label, sample_time in requests:
        started = time.perf_counter()
        preview = adapter.render_vrm(
            active_layer, sample_time, composition=active_composition, quality="preview", viewport_size=(size, size),
        )
        preview_seconds = time.perf_counter() - started
        export_started = time.perf_counter()
        exported = adapter.render_vrm(
            active_layer, sample_time, composition=active_composition, quality="export", viewport_size=(size, size),
        )
        export_seconds = time.perf_counter() - export_started
        preview_array = _qimage_array(preview)
        export_array = _qimage_array(exported)
        diagnostics = adapter.vrm_diagnostics(active_layer.id)
        image = Image.fromarray(preview_array, "RGBA")
        image.save(output_dir / f"{prefix}_{sample_time:04d}.png")
        metrics = _alpha_metrics(preview_array)
        parity = bool(np.array_equal(preview_array, export_array))
        samples.append({
            "label": label,
            "time_ms": sample_time,
            "preview_seconds": round(preview_seconds, 4),
            "cached_export_seconds": round(export_seconds, 4),
            "preview_export_parity": parity,
            "alpha": metrics,
            "renderer": diagnostics.get("renderer"),
            "renderer_family": diagnostics.get("renderer_family"),
            "render_profile": diagnostics.get("render_profile"),
            "pose_source": diagnostics.get("pose_source"),
            "selected_motion": diagnostics.get("selected_motion"),
            "fit": diagnostics.get("fit"),
            "render_mode": (diagnostics.get("render") or {}).get("mode"),
        })
        arrays.append(preview_array)
        rows.append({"label": label, "image": image, "diagnostics": diagnostics})

    body_changed_pixels = int(np.count_nonzero(np.any(arrays[0] != arrays[1], axis=2)))
    face_changed_pixels = int(np.count_nonzero(np.any(arrays[2] != arrays[3], axis=2)))
    changed_pixels = body_changed_pixels + face_changed_pixels
    _save_contact_sheet(rows, output_dir / "evidence.png")
    panel = VRMPanel()
    panel.setStyleSheet(MOTION_DESIGNER_QSS)
    panel.resize(360, 680)
    panel.set_layer(body_layer)
    panel.show()
    app.processEvents()
    panel.grab().save(str(output_dir / "vrm_inspector.png"))
    panel.close()
    app.processEvents()

    ok = all(
        sample["preview_export_parity"]
        and sample["renderer"] == "vrm_mtoon_gpu"
        and sample["renderer_family"] == "vtuber_vrm"
        and sample["render_profile"] == "vrm_mtoon"
        and sample["pose_source"] == "explicit_motion_frame"
        and sample["alpha"]["visible"]
        and sample["alpha"]["height_ratio"] >= 0.84
        and sample["alpha"]["bottom_gap_px"] <= max(8, int(size * 0.04))
        for sample in samples
    ) and changed_pixels > 100
    report = {
        "ok": bool(ok),
        "schema": "tigerstudio.motion.vrm.qa.v1",
        "avatar": str(DEFAULT_VRM),
        "opengl_only": True,
        "software_renderer_used": False,
        "preview_export_parity": all(sample["preview_export_parity"] for sample in samples),
        "temporal_changed_pixels": changed_pixels,
        "body_changed_pixels": body_changed_pixels,
        "face_changed_pixels": face_changed_pixels,
        "samples": samples,
        "evidence": str(output_dir / "evidence.png"),
        "inspector": str(output_dir / "vrm_inspector.png"),
        "limits": [
            "First uncached frames are precomputed and cached; this QA does not claim realtime VRM rendering.",
            "The durable Milica VRM0 sample validates the current explicit pose and MToon GPU path, not every third-party VRM rig.",
        ],
    }
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--size", type=int, default=320)
    args = parser.parse_args()
    report = run(args.output, size=max(192, int(args.size)))
    print(json.dumps({
        "ok": report["ok"],
        "opengl_only": report["opengl_only"],
        "preview_export_parity": report["preview_export_parity"],
        "temporal_changed_pixels": report["temporal_changed_pixels"],
        "evidence": report["evidence"],
    }, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

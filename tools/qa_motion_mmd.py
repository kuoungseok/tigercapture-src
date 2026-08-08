"""Real Motion Designer MMD OpenGL compatibility and parity evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT = ROOT / "debugCapture" / "motion_designer" / "mmd"
SAMPLES = (
    {
        "id": "cantarella_cloth_ik",
        "model": ROOT / "local_resources/mmd/model_pool/playable/flashy_girls/wuthering_waves/Cantarella/Cantarella.pmx",
        "motion": ROOT / "local_resources/mmd/model_pool/motions/validated/wavefile_v2_arora_14.vmd",
        "targets": ["dance", "ik", "physics", "cutout", "self_shadow", "gpu_skinning"],
    },
    {
        "id": "alice_face_hair",
        "model": ROOT / "local_resources/mmd/model_pool/playable/flashy_girls/zzz/Alice_Skin/Alice - Sea of Thyme/Alice - Sea of Thyme.pmx",
        "motion": ROOT / "local_resources/mmd/model_pool/motions/validated/wavefile_v2_arora_14.vmd",
        "targets": ["transparent_hair", "face_order", "eye_bloom", "metal"],
    },
    {
        "id": "miku_vmd_camera",
        "model": ROOT / "local_resources/mmd/model_pool/playable/vmd_validated/vocaloid_default/miku_v2.pmd",
        "motion": ROOT / "local_resources/mmd/model_pool/motions/threejs_wavefile/wavefile_camera.vmd",
        "targets": ["pmd", "vmd_camera", "auto_frame_fallback", "toon"],
    },
)


def _rgba(image):
    import numpy as np
    from PySide6.QtGui import QImage

    straight = image.convertToFormat(QImage.Format_RGBA8888)
    data = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(straight.height(), straight.bytesPerLine())
    return data[:, : straight.width() * 4].reshape(straight.height(), straight.width(), 4).copy()


def _save(array, path: Path) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array, "RGBA").save(path)


def _visible_std(array) -> float:
    import numpy as np

    alpha = array[..., 3].astype(np.float32)[..., None] / 255.0
    matte = np.array([37.0, 42.0, 51.0], dtype=np.float32)
    visible = array[..., :3].astype(np.float32) * alpha + matte * (1.0 - alpha)
    return float(visible.std())


def _render_one(sample: dict[str, Any], output: Path, *, width: int, height: int) -> dict[str, Any]:
    import numpy as np

    from app.motion_designer.adapters.mmd import clear_mmd_cache, mmd_diagnostics, render_mmd
    from app.motion_designer.mmd_source import create_mmd_layer
    from app.motion_designer.schema import MotionComposition

    layer = create_mmd_layer(
        sample["model"], motion_path=sample["motion"], width=width, height=height,
        duration_ms=4000, name=sample["id"],
    )
    composition = MotionComposition(width=width, height=height, duration_ms=4000, layers=[layer])
    clear_mmd_cache()
    captures = []
    for pos_ms in (500, 1100):
        preview = render_mmd(
            layer, pos_ms, composition=composition, composition_time_ms=pos_ms,
            quality="preview", viewport_size=(width, height),
        )
        exported = render_mmd(
            layer, pos_ms, composition=composition, composition_time_ms=pos_ms,
            quality="export", viewport_size=(width, height),
        )
        preview_array = _rgba(preview)
        export_array = _rgba(exported)
        delta = np.abs(preview_array.astype(np.int16) - export_array.astype(np.int16))
        alpha = preview_array[..., 3]
        ys, xs = np.where(alpha > 0)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None
        preview_path = output / f"{sample['id']}_{pos_ms}_preview.png"
        export_path = output / f"{sample['id']}_{pos_ms}_export.png"
        _save(preview_array, preview_path)
        _save(export_array, export_path)
        captures.append({
            "time_ms": pos_ms,
            "preview_path": str(preview_path),
            "export_path": str(export_path),
            "array": preview_array,
            "bbox": bbox,
            "nonblank_pixels": int(np.count_nonzero(alpha)),
            "visible_rgb_stddev": round(_visible_std(preview_array), 3),
            "max_abs_channel_error": int(delta.max(initial=0)),
            "different_channel_count": int(np.count_nonzero(delta)),
        })
    first, second = captures
    temporal = np.abs(first.pop("array").astype(np.int16) - second.pop("array").astype(np.int16))
    diagnostics = mmd_diagnostics(layer.id)
    diag = {
        key: diagnostics.get(key) for key in (
            "ok", "renderer", "gpu_skinning", "gpu_skinning_available",
            "track_gpu_skinning_active", "active_ik_count", "physics_body_count",
            "track_physics_backend", "track_physics_backend_available",
            "transparent_group_count", "cutout_group_count", "outline_group_count",
            "self_shadow_receiver_group_count", "bloom_group_count", "missing_texture_count",
            "vmd_camera_available", "vmd_camera_enabled", "cache_hit", "canonical_frame_cache",
        )
    }
    temporal_pixels = int(np.count_nonzero(np.max(temporal, axis=2) > 8))
    parity = all(row["max_abs_channel_error"] == 0 for row in captures)
    nonblank = all(row["bbox"] is not None and row["visible_rgb_stddev"] >= 8.0 for row in captures)
    expected_camera = sample["id"] == "miku_vmd_camera"
    camera_ok = bool(diag.get("vmd_camera_available")) if expected_camera else True
    renderer_ok = diag.get("renderer") == "mmd_toon_opengl" and bool(diag.get("ok"))
    return {
        "ok": parity and nonblank and temporal_pixels > 100 and camera_ok and renderer_ok,
        "id": sample["id"],
        "model": str(sample["model"]),
        "motion": str(sample["motion"]),
        "targets": sample["targets"],
        "preview_export_parity": parity,
        "temporal_changed_pixels": temporal_pixels,
        "captures": captures,
        "diagnostics": diag,
    }


def _contact_sheet(rows: list[dict[str, Any]], output: Path, *, width: int, height: int) -> Path:
    from PIL import Image, ImageDraw

    margin, label_h = 14, 30
    sheet = Image.new("RGB", (margin * 4 + width * 3, margin * 2 + height + label_h), "#0f1217")
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        capture = row["captures"][1]
        frame = Image.open(capture["preview_path"]).convert("RGBA")
        x = margin + index * (width + margin)
        y = margin
        tile = Image.new("RGB", (width, height), "#252a33")
        tile.paste(frame, (0, 0), frame)
        sheet.paste(tile, (x, y))
        draw.text((x + 4, y + height + 7), row["id"], fill="#eef2f6")
    path = output / "evidence.png"
    sheet.save(path)
    return path


def _capture_ui(output: Path) -> dict[str, Any]:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from app.motion_designer.mmd_source import create_mmd_layer
    from app.motion_designer.schema import MotionComposition
    from app.motion_designer.ui.window import MotionDesignerWindow

    app = QApplication.instance() or QApplication([])
    sample = SAMPLES[0]
    actor = create_mmd_layer(
        sample["model"], motion_path=sample["motion"], width=1280, height=720,
        duration_ms=4000, name="Cantarella / Wavefile",
    )
    composition = MotionComposition(
        name="M9B MMD Inspector QA", width=1280, height=720, duration_ms=4000, layers=[actor],
    )
    window = MotionDesignerWindow(composition)
    window.resize(1280, 800)
    window.show()
    window._select_layer(actor.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.mmd)
    window.viewer_tabs.setCurrentWidget(window.preview)
    window.timeline.set_time_and_emit(1100)
    loop = QEventLoop()
    QTimer.singleShot(1200, loop.quit)
    loop.exec()
    app.processEvents()
    viewport = window.mmd.scroll.viewport().grab().toImage()
    dark_surface = not viewport.isNull() and viewport.pixelColor(2, 2).lightness() < 80
    path = output / "mmd_inspector.png"
    saved = window.grab().save(str(path), "PNG")
    size = [window.width(), window.height()]
    window.close()
    app.processEvents()
    return {"ok": bool(saved and dark_surface), "path": str(path), "size": size, "dark_surface": dark_surface}


def run(output: Path, *, width: int = 384, height: int = 216) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    rows = [_render_one(sample, output, width=width, height=height) for sample in SAMPLES]
    evidence = _contact_sheet(rows, output, width=width, height=height)
    ui_evidence = _capture_ui(output)
    report = {
        "ok": all(row["ok"] for row in rows) and ui_evidence["ok"],
        "sample_count": len(rows),
        "preview_export_parity": all(row["preview_export_parity"] for row in rows),
        "opengl_only": all(row["diagnostics"]["renderer"] == "mmd_toon_opengl" for row in rows),
        "evidence_path": str(evidence),
        "ui_evidence": ui_evidence,
        "output_dir": str(output),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "rows": rows,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--width", type=int, default=384)
    parser.add_argument("--height", type=int, default=216)
    args = parser.parse_args()
    report = run(args.output.resolve(), width=max(160, args.width), height=max(90, args.height))
    summary = {
        "ok": report["ok"], "sample_count": report["sample_count"],
        "preview_export_parity": report["preview_export_parity"],
        "opengl_only": report["opengl_only"], "evidence_path": report["evidence_path"],
        "ui_evidence": report["ui_evidence"], "elapsed_ms": report["elapsed_ms"],
        "rows": [{"id": row["id"], "ok": row["ok"], "temporal_changed_pixels": row["temporal_changed_pixels"], "diagnostics": row["diagnostics"]} for row in report["rows"]],
    }
    print("MOTION_MMD_QA " + json.dumps(summary, ensure_ascii=False, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

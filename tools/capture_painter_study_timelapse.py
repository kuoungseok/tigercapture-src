from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a visible Tiger Studio Painter AI-study stroke replay."
    )
    parser.add_argument("reference", type=Path)
    parser.add_argument("--output-video", type=Path, required=True)
    parser.add_argument("--output-image", type=Path, required=True)
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--seed", type=int, default=240725)
    parser.add_argument("--refinement-passes", type=int, default=2)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--phase-duration-ms", type=int, default=1500)
    parser.add_argument("--focus-region", action="append", default=[])
    return parser.parse_args()


def _focus_regions(values: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in values:
        parts = [part.strip() for part in str(value).split(",")]
        if len(parts) != 6:
            raise ValueError("--focus-region requires id,x0,y0,x1,y1,priority")
        rows.append(
            {
                "id": parts[0],
                "bbox_norm": [float(part) for part in parts[1:5]],
                "priority": float(parts[5]),
            }
        )
    return rows


def _execute(registry: Any, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    result = registry.execute_action(action, dict(params or {})).to_dict()
    if not result.get("ok"):
        raise RuntimeError(f"{action} failed: {result.get('error') or 'unknown error'}")
    return dict(result.get("result") or {})


def main() -> int:
    args = _args()
    reference = args.reference.resolve()
    source = Image.open(reference)
    width = max(256, min(1600, int(args.width)))
    height = max(256, round(width * source.height / max(1, source.width)))

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap, export_paint_png
    from app.window_capture import start_window_video_capture, stop_window_video_capture

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(width, height, "#111827"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1280, 900)
    dialog.setWindowTitle("Painter - Tiger Studio | Preparing AI study")
    dialog.show()
    app.processEvents()
    registry = ActionRegistry(owner=dialog)

    _execute(
        registry,
        "paint.study.analyze_reference",
        {
            "reference_path": str(reference),
            "target_width": width,
            "region_count": 14,
            "seed": int(args.seed),
            "focus_regions": _focus_regions(args.focus_region),
        },
    )
    _execute(registry, "paint.study.segment_regions")
    phases = [
        ("paint.study.build_underpaint", {"max_strokes": 16000}),
        ("paint.study.generate_strokes", {"phase": "forms", "max_strokes": 1500}),
        ("paint.study.generate_strokes", {"phase": "detail", "max_strokes": 1300}),
        ("paint.study.generate_strokes", {"phase": "accent", "max_strokes": 450}),
        ("paint.study.trace_contours", {"max_strokes": 800}),
    ]
    for action, params in phases:
        _execute(registry, action, params)
    _execute(registry, "paint.study.compare_render")
    for index in range(max(0, int(args.refinement_passes))):
        _execute(
            registry,
            "paint.study.refine_region",
            {
                "max_strokes": 5000,
                "layer_name": f"AI Study Refinement {index + 1}",
                "seed_offset": (index + 1) * 1000,
            },
        )
        _execute(registry, "paint.study.compare_render")
    quality = _execute(registry, "paint.study.quality_report")["study"]

    output_image = args.output_image.resolve()
    output_image.parent.mkdir(parents=True, exist_ok=True)
    _execute(
        registry,
        "paint.document.export_png",
        {"path": str(output_image), "include_background": True},
    )
    output_video = args.output_video.resolve()
    output_video.parent.mkdir(parents=True, exist_ok=True)

    final_layers = list(dialog._paint_layers)
    final_strokes = dialog.canvas.embedded_strokes()
    strokes_by_layer: dict[str, list[Any]] = defaultdict(list)
    for stroke in final_strokes:
        strokes_by_layer[str(getattr(stroke, "layer_id", "") or "")].append(stroke)
    replay_layers = [
        layer
        for layer in final_layers
        if strokes_by_layer.get(str(getattr(layer, "layer_id", "") or ""))
    ]

    # Rendering tens of thousands of strokes on every captured frame makes the
    # visible Qt window stall. Pre-render one truthful cumulative frame per
    # generated layer, then play those frames in the real Painter window.
    frame_dir = (
        ROOT
        / "debugCapture"
        / "painter_ai_timelapse_frames"
        / output_video.stem
    )
    frame_dir.mkdir(parents=True, exist_ok=True)
    cumulative: list[Any] = []
    replay_frames: list[tuple[Any, Path]] = []
    background = dialog._export_background_pixmap()
    for index, layer in enumerate(replay_layers, start=1):
        layer_id = str(layer.layer_id)
        cumulative.extend(strokes_by_layer[layer_id])
        frame_path = frame_dir / f"{index:02d}_{layer_id}.png"
        export_paint_png(
            frame_path,
            background_pixmap=background,
            strokes=cumulative,
            frame_size=(width, height),
            include_background=True,
        )
        replay_frames.append((layer, frame_path))

    dialog.canvas.set_strokes_snapshot([])
    dialog._paint_layers = final_layers[:1]
    dialog._active_paint_layer_id = str(dialog._paint_layers[0].layer_id)
    dialog._selected_layer_id = dialog._active_paint_layer_id
    dialog._sync_canvas_layer_view()
    dialog._update_inspector_counts()
    dialog.setWindowTitle("Painter - Tiger Studio | AI painting timelapse")
    app.processEvents()

    session_id = "painter-ai-study-timelapse"
    capture = start_window_video_capture(
        path=output_video,
        title_contains="Painter - Tiger Studio",
        fps=max(10, min(30, int(args.fps))),
        backend="auto",
        activate=True,
        session_id=session_id,
        max_duration_ms=120_000,
    )

    phase_duration = max(500, int(args.phase_duration_ms))
    frame_index = 0

    def finish() -> None:
        from PySide6.QtGui import QPixmap

        dialog.canvas.set_strokes_snapshot([])
        dialog._paint_layers = final_layers
        dialog._active_paint_layer_id = str(final_layers[-1].layer_id)
        dialog._selected_layer_id = dialog._active_paint_layer_id
        dialog._bg_pixmap_source = QPixmap(str(output_image))
        dialog._background_layer_present = True
        dialog._sync_canvas_layer_view()
        dialog._update_inspector_counts()
        dialog._update_canvas_geometry()
        dialog.setWindowTitle("Painter - Tiger Studio | Complete")
        app.processEvents()

        def stop() -> None:
            stopped = stop_window_video_capture(session_id=session_id, wait_ms=30_000)
            report_path = output_video.with_suffix(".capture.json")
            report_path.write_text(
                json.dumps(
                    {
                        "schema": "tigerstudio.painter.ai_study_capture.v1",
                        "reference": str(reference),
                        "output_image": str(output_image),
                        "output_video": str(output_video),
                        "stroke_count": len(final_strokes),
                        "quality": quality,
                        "capture_start": capture,
                        "capture_stop": stopped,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {
                        "ok": output_video.exists() and output_image.exists(),
                        "video": str(output_video),
                        "image": str(output_image),
                        "report": str(report_path),
                        "quality": quality,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            dialog.close()
            app.quit()

        QTimer.singleShot(1800, stop)

    def advance() -> None:
        nonlocal frame_index
        if frame_index >= len(replay_frames):
            finish()
            return
        from PySide6.QtGui import QPixmap

        layer, frame_path = replay_frames[frame_index]
        layer_id = str(layer.layer_id)
        dialog._paint_layers.append(layer)
        dialog._active_paint_layer_id = layer_id
        dialog._selected_layer_id = layer_id
        dialog._bg_pixmap_source = QPixmap(str(frame_path))
        dialog._background_layer_present = True
        dialog._sync_canvas_layer_view()
        dialog._update_inspector_counts()
        dialog._update_canvas_geometry()
        dialog.setWindowTitle(f"Painter - Tiger Studio | {layer.name}")
        frame_index += 1
        QTimer.singleShot(phase_duration, advance)

    QTimer.singleShot(800, advance)
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())

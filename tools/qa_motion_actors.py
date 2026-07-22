"""Real Motion Designer Live2D/Spine compatibility and parity evidence."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT = ROOT / "debugCapture" / "motion_designer" / "actors"
LIVE2D_SAMPLES = (
    ROOT / "resources/live2d_samples/CubismWebSamples/Samples/Resources/Hiyori/Hiyori.model3.json",
    ROOT / "resources/live2d_samples/CubismWebSamples/Samples/Resources/Haru/Haru.model3.json",
    ROOT / "resources/live2d_samples/CubismWebSamples/Samples/Resources/Mao/Mao.model3.json",
)
SPINE_SAMPLES = (
    ROOT / "resources/spine_samples/celestial-circus/export/celestial-circus-pro.skel",
    ROOT / "resources/spine_samples/chibi-stickers/export/chibi-stickers.skel",
    ROOT / "resources/spine_samples/mix-and-match/export/mix-and-match-pro.skel",
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


def _render_one(kind: str, path: Path, output: Path, *, size: int, pos_ms: int) -> dict[str, Any]:
    import numpy as np

    from app.actor_process_probe import run_isolated_actor_probe
    from app.motion_designer.actor_source import create_actor_layer
    from app.motion_designer.schema import MotionComposition

    probe = run_isolated_actor_probe(kind, str(path), width=size, height=size, pos_ms=pos_ms, timeout_ms=60_000)
    source_kind = f"{kind}_actor"
    layer = create_actor_layer(source_kind, path, width=size, height=size, duration_ms=2000)
    composition = MotionComposition(width=size, height=size, duration_ms=2000, layers=[layer])
    if kind == "live2d":
        from app.motion_designer.adapters.live2d import clear_live2d_cache, live2d_diagnostics, render_live2d

        clear_live2d_cache()
        preview = render_live2d(layer, pos_ms, composition=composition, quality="preview", viewport_size=(size, size))
        exported = render_live2d(layer, pos_ms, composition=composition, quality="export", viewport_size=(size, size))
        diagnostics = live2d_diagnostics(layer.id)
    else:
        from app.motion_designer.adapters.spine import clear_spine_cache, render_spine, spine_diagnostics

        clear_spine_cache()
        preview = render_spine(layer, pos_ms, composition=composition, quality="preview", viewport_size=(size, size))
        exported = render_spine(layer, pos_ms, composition=composition, quality="export", viewport_size=(size, size))
        diagnostics = spine_diagnostics(layer.id)
    preview_array = _rgba(preview)
    export_array = _rgba(exported)
    alpha = preview_array[..., 3]
    ys, xs = np.where(alpha > 0)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None
    matte = np.array([37.0, 42.0, 51.0], dtype=np.float32)
    alpha_float = alpha.astype(np.float32)[..., None] / 255.0
    visible = preview_array[..., :3].astype(np.float32) * alpha_float + matte * (1.0 - alpha_float)
    visible_stddev = float(visible.std())
    visually_distinct = visible_stddev >= 8.0
    stem = f"{kind}_{path.stem.replace('.', '_')}"
    preview_path = output / f"{stem}_preview.png"
    export_path = output / f"{stem}_export.png"
    _save(preview_array, preview_path)
    _save(export_array, export_path)
    delta = np.abs(preview_array.astype(np.int16) - export_array.astype(np.int16))
    return {
        "ok": (
            bool(probe.get("ok"))
            and bbox is not None
            and visually_distinct
            and int(delta.max(initial=0)) == 0
        ),
        "kind": kind,
        "source": str(path),
        "probe": probe,
        "preview_path": str(preview_path),
        "export_path": str(export_path),
        "bbox": bbox,
        "nonblank_pixels": int(np.count_nonzero(alpha)),
        "visible_rgb_stddev": round(visible_stddev, 3),
        "visually_distinct": visually_distinct,
        "max_abs_channel_error": int(delta.max(initial=0)),
        "different_channel_count": int(np.count_nonzero(delta)),
        "diagnostics": diagnostics,
    }


def _contact_sheet(rows: list[dict[str, Any]], output: Path, *, size: int) -> Path:
    from PIL import Image, ImageDraw

    margin, label_h = 14, 28
    sheet = Image.new("RGB", (margin * 4 + size * 3, margin * 3 + (size + label_h) * 2), "#0f1217")
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        image = Image.open(row["preview_path"]).convert("RGBA")
        x = margin + (index % 3) * (size + margin)
        y = margin + (index // 3) * (size + label_h + margin)
        tile = Image.new("RGB", (size, size), "#252a33")
        tile.paste(image, (0, 0), image)
        sheet.paste(tile, (x, y))
        draw.text((x + 4, y + size + 6), f"{row['kind'].upper()}  {Path(row['source']).stem}", fill="#eef2f6")
    path = output / "evidence.png"
    sheet.save(path)
    return path


def _capture_actor_ui(output: Path) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    from app.motion_designer.actor_source import create_actor_layer
    from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
    from app.motion_designer.ui.window import MotionDesignerWindow

    app = QApplication.instance() or QApplication([])
    background = MotionLayer(
        name="Actor Stage",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 1280,
            "height": 720,
            "fill": "#252a33",
            "stroke_width": 0,
        }),
        out_ms=2000,
    )
    background.transform.position.default = [640.0, 360.0]
    actor = create_actor_layer(
        "live2d_actor", LIVE2D_SAMPLES[0], width=1280, height=720, duration_ms=2000,
    )
    actor.name = "Hiyori / Idle"
    actor.source.params["actor"]["scale"] = 1.1
    composition = MotionComposition(
        name="M9A Actor Inspector QA",
        width=1280,
        height=720,
        duration_ms=2000,
        layers=[background, actor],
    )
    window = MotionDesignerWindow(composition)
    window.resize(1280, 800)
    window.show()
    app.processEvents()
    window._select_layer(actor.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.actor)
    window.timeline.set_time_and_emit(500)
    app.processEvents()
    viewport = window.actor.scroll.viewport().grab().toImage()
    dark_surface = (
        not viewport.isNull()
        and viewport.pixelColor(2, 2).lightness() < 80
    )
    path = output / "actor_inspector.png"
    saved = window.grab().save(str(path), "PNG")
    size = [window.width(), window.height()]
    window.close()
    app.processEvents()
    return {
        "ok": bool(saved and dark_surface),
        "path": str(path),
        "size": size,
        "dark_surface": dark_surface,
    }


def run(output: Path, *, size: int = 320, pos_ms: int = 500) -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    # Cubism probes are intentionally serial; concurrent GLFW contexts can contend on Windows.
    for path in LIVE2D_SAMPLES:
        rows.append(_render_one("live2d", path, output, size=size, pos_ms=pos_ms))
    for path in SPINE_SAMPLES:
        rows.append(_render_one("spine", path, output, size=size, pos_ms=pos_ms))
    evidence = _contact_sheet(rows, output, size=size)
    ui_evidence = _capture_actor_ui(output)
    report = {
        "ok": all(row["ok"] for row in rows) and ui_evidence["ok"],
        "sample_count": len(rows),
        "live2d_count": sum(row["kind"] == "live2d" for row in rows),
        "spine_count": sum(row["kind"] == "spine" for row in rows),
        "preview_export_parity": all(row["max_abs_channel_error"] == 0 for row in rows),
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
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--pos-ms", type=int, default=500)
    args = parser.parse_args()
    report = run(args.output.resolve(), size=max(128, args.size), pos_ms=max(0, args.pos_ms))
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

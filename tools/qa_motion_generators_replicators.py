from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.generators import create_generator_layer
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui.window import MotionDesignerWindow


def build_composition() -> MotionComposition:
    composition = MotionComposition(
        name="Generator and Replicator",
        width=1280,
        height=720,
        fps=30,
        duration_ms=5000,
    )
    background = create_generator_layer(
        "gradient",
        width=composition.width,
        height=composition.height,
        duration_ms=composition.duration_ms,
        name="Procedural Gradient",
    )
    background.source.params.update({
        "color_a": "#163c4a",
        "color_b": "#080b12",
        "angle": 28.0,
    })
    tile = MotionLayer(
        name="Radial Replicator",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "shape": "star",
            "width": 82,
            "height": 82,
            "sides": 5,
            "inner_ratio": 0.45,
            "fill": "#f2c14e",
            "stroke": "#fff2c5",
            "stroke_width": 3,
        }),
        out_ms=composition.duration_ms,
    )
    tile.transform.position.default = [composition.width * 0.5, composition.height * 0.5]
    tile.metadata["replicator"] = {
        "enabled": True,
        "arrangement": "radial",
        "count": 12,
        "columns": 4,
        "offset": [235.0, 0.0],
        "rotation": 15.0,
        "scale": [0.96, 0.96],
        "opacity_start": 1.0,
        "opacity_end": 0.55,
        "jitter": [0.0, 0.0],
        "seed": 0,
    }
    title = MotionLayer(
        name="Title",
        layer_type="text",
        source=SourceRef(kind="text", params={
            "text": "GENERATORS + REPLICATORS",
            "font_size": 62,
            "fill": "#f6f7f8",
        }),
        out_ms=composition.duration_ms,
    )
    title.transform.position.default = [composition.width * 0.5, composition.height * 0.5]
    composition.layers = [background, tile, title]
    return composition


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    output = ROOT / "debugCapture" / "motion_designer"
    output.mkdir(parents=True, exist_ok=True)
    composition = build_composition()
    render_path = output / "motion_generators_replicators_render.png"
    MotionExportRenderer().save_png(composition, 1200, render_path)

    window = MotionDesignerWindow(composition)
    window.resize(1600, 900)
    window.show()
    app.processEvents()
    tile = next(layer for layer in composition.layers if layer.name == "Radial Replicator")
    window._select_layer(tile.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.replicator)
    window.viewer_tabs.setCurrentWidget(window.canvas)
    window.timeline.set_time_and_emit(1200)
    app.processEvents()
    ui_path = output / "motion_generators_replicators_ui.png"
    if not window.grab().save(str(ui_path), "PNG"):
        raise RuntimeError(f"Could not save {ui_path}")
    print(render_path)
    print(ui_path)
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

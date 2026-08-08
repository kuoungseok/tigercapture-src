from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionBehaviorRef,
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    MotionMaskRef,
    SourceRef,
)
from app.motion_designer.mask_tracking import MotionTrackingCache
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.ui.window import MotionDesignerWindow
from app.motion_designer.vector_shapes import default_pen_path


def _assert_dark_inspector_surface(window: MotionDesignerWindow) -> None:
    image = window.vector.scroll.viewport().grab().toImage()
    if image.isNull():
        raise RuntimeError("Motion Designer inspector viewport could not be captured")
    samples = (
        image.pixelColor(1, 1),
        image.pixelColor(max(1, image.width() - 2), max(1, image.height() - 2)),
    )
    if any(color.lightness() >= 80 for color in samples):
        values = [color.name() for color in samples]
        raise RuntimeError(f"Motion Designer dark-chrome regression: inspector surface {values}")


def _position(default: list[float], *keys: tuple[int, list[float]]) -> AnimatedProperty:
    return AnimatedProperty(
        value_type="vector2",
        default=default,
        keyframes=[Keyframe(time_ms=time_ms, value=value, interpolation="bezier") for time_ms, value in keys],
    )


def build_demo_composition() -> MotionComposition:
    composition = MotionComposition(
        name="Motion Designer UI QA",
        width=1280,
        height=720,
        fps=30.0,
        duration_ms=5000,
    )
    background = MotionLayer(
        name="Background",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 1280, "height": 720, "fill": "#e8edf1", "stroke": "#e8edf1",
        }),
        out_ms=5000,
    )
    background.transform.position.default = [640.0, 360.0]
    band = MotionLayer(
        name="Accent Band",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 900, "height": 150, "fill": "#24677f", "stroke": "#24677f",
        }),
        out_ms=5000,
    )
    band.transform.position = _position(
        [640.0, 395.0],
        (0, [300.0, 395.0]),
        (1200, [640.0, 395.0]),
        (4200, [700.0, 395.0]),
    )
    band.behaviors.append(MotionBehaviorRef(
        kind="spring", start_ms=0, end_ms=1200,
        params={"amplitude": 18.0, "frequency": 3.0, "damping": 5.0},
    ))
    title = MotionLayer(
        name="Main Title",
        layer_type="text",
        source=SourceRef(kind="text", params={
            "text": "MOTION DESIGNER", "font_size": 76, "bold": True, "fill": "#11161b",
        }),
        out_ms=5000,
    )
    title.transform.position = _position(
        [640.0, 285.0],
        (0, [640.0, 190.0]),
        (900, [640.0, 285.0]),
        (4200, [640.0, 270.0]),
    )
    title.effects.append(MotionEffectRef(kind="unsharp_mask", params={
        "radius": AnimatedProperty(default=1.5),
        "amount": AnimatedProperty(default=0.65),
    }))
    subtitle = MotionLayer(
        name="Subtitle",
        layer_type="text",
        source=SourceRef(kind="text", params={
            "text": "TIGER STUDIO  /  TITLE SYSTEM", "font_size": 30,
            "fill": "#f4f7f8",
        }),
        out_ms=5000,
    )
    subtitle.transform.position.default = [640.0, 396.0]
    subtitle.behaviors.append(MotionBehaviorRef(
        kind="fade", start_ms=350, end_ms=1150, params={"direction": "in"},
    ))
    path = MotionLayer(
        name="Bezier Accent",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 520, "height": 180, "shape": "path",
            "path": default_pen_path(520, 180).to_dict(),
            "fill": "#00000000", "stroke": "#e76f51", "stroke_width": 7,
            "cap": "round", "trim": {"start": 0.0, "end": .86, "offset": 0.0},
            "repeater": {"count": 2, "offset": [0, 18], "opacity_end": .28},
        }),
        out_ms=5000,
    )
    path.transform.position.default = [640.0, 510.0]
    composition.layers = [background, band, title, subtitle, path]
    return composition


def capture(size: tuple[int, int], output_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"
    font_id = QFontDatabase.addApplicationFont(str(font_path)) if font_path.is_file() else -1
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    if families:
        app.setFont(QFont(families[0], 9))
    window = MotionDesignerWindow(build_demo_composition())
    window.resize(*size)
    window.show()
    app.processEvents()
    title = next(layer for layer in window.controller.composition.layers if layer.name == "Main Title")
    window._select_layer(title.id)
    window.timeline.set_time_and_emit(1200)
    app.processEvents()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output_path), "PNG"):
        raise RuntimeError(f"Could not write screenshot: {output_path}")
    window.close()
    app.processEvents()


def capture_vector(output_path: Path, *, preview: bool = False) -> None:
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(build_demo_composition())
    window.resize(1600, 900)
    window.show()
    app.processEvents()
    layer = next(row for row in window.controller.composition.layers if row.name == "Bezier Accent")
    window._select_layer(layer.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.vector)
    if preview:
        window.viewer_tabs.setCurrentWidget(window.preview)
    window.timeline.set_time_and_emit(1200)
    app.processEvents()
    _assert_dark_inspector_surface(window)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output_path), "PNG"):
        raise RuntimeError(f"Could not write screenshot: {output_path}")
    window.close()
    app.processEvents()


def capture_typography(output_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    composition = build_demo_composition()
    title = next(row for row in composition.layers if row.name == "Main Title")
    title.source.params["text_animation"] = {
        "in": "typewriter-in", "hold": "hold-wave", "out": "fade-out",
        "in_duration_ms": 900, "out_duration_ms": 550,
        "unit": "character", "stagger_ms": 55,
        "selector_start": 0.0, "selector_end": 1.0, "reverse": False,
    }
    window = MotionDesignerWindow(composition)
    window.resize(1600, 900)
    window.show()
    app.processEvents()
    window._select_layer(title.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.typography)
    window.timeline.set_time_and_emit(520)
    app.processEvents()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output_path), "PNG"):
        raise RuntimeError(f"Could not write screenshot: {output_path}")
    window.close()
    app.processEvents()


def capture_typography_path(output_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    composition = build_demo_composition()
    title = next(row for row in composition.layers if row.name == "Main Title")
    title.effects.clear()
    title.source.params.update({
        "text": "FOLLOW THE CURVE",
        "width": 760,
        "height": 300,
        "font_size": 64,
        "text_animation": {},
        "text_path": default_pen_path(760, 300).to_dict(),
        "text_path_offset": .5,
    })
    title.transform.position.default = [640, 330]
    window = MotionDesignerWindow(composition)
    window.resize(1600, 900)
    window.show()
    app.processEvents()
    window._select_layer(title.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.typography)
    window.typography.scroll.verticalScrollBar().setValue(
        window.typography.scroll.verticalScrollBar().maximum()
    )
    window.timeline.set_time_and_emit(1200)
    app.processEvents()
    handles = [
        item for item in window.canvas.scene().items()
        if item.data(1) == "typography_path_handle"
    ]
    if len(handles) < len(title.source.params["text_path"]["points"]):
        raise RuntimeError("Typography path handles are missing from the Canvas")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output_path), "PNG"):
        raise RuntimeError(f"Could not write screenshot: {output_path}")
    window.close()
    app.processEvents()


def capture_mask_tracking(output_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    composition = build_demo_composition()
    band = next(row for row in composition.layers if row.name == "Accent Band")
    band.masks.append(MotionMaskRef(
        kind="rectangle",
        mode="add",
        params={
            "x": AnimatedProperty(default=120.0),
            "y": AnimatedProperty(default=0.0),
            "width": AnimatedProperty(default=560.0),
            "height": AnimatedProperty(default=150.0),
            "radius": AnimatedProperty(default=16.0),
            "feather": AnimatedProperty(default=10.0),
            "expansion": AnimatedProperty(default=4.0),
            "opacity": AnimatedProperty(default=1.0),
        },
        metadata={"tracking_cache": MotionTrackingCache.from_dict({
            "mode": "planar",
            "origin": [450.0, 75.0],
            "samples": [
                {"time_ms": 0, "translate": [-80.0, 0.0], "scale": [1.0, 1.0], "rotation": -3.0},
                {"time_ms": 1200, "translate": [0.0, 0.0], "scale": [1.0, 1.0], "rotation": 0.0},
                {"time_ms": 4200, "translate": [90.0, 0.0], "scale": [1.04, .96], "rotation": 4.0},
            ],
        }).to_dict()},
    ))
    window = MotionDesignerWindow(composition)
    window.resize(1600, 900)
    window.show()
    app.processEvents()
    window._select_layer(band.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.masks)
    window.timeline.set_time_and_emit(1200)
    app.processEvents()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output_path), "PNG"):
        raise RuntimeError(f"Could not write screenshot: {output_path}")
    window.close()
    app.processEvents()


def build_boolean_composition() -> MotionComposition:
    composition = MotionComposition(
        name="Linked Boolean QA", width=1280, height=720, fps=30.0, duration_ms=5000,
    )
    background = MotionLayer(
        name="Background", layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 1280, "height": 720, "fill": "#edf1f4", "stroke_width": 0,
        }), out_ms=5000,
    )
    background.transform.position.default = [640, 360]
    target = MotionLayer(
        name="Boolean Plate", layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 700, "height": 360, "shape": "rectangle", "radius": 34,
            "fill": "#24677f", "stroke": "#163c4a", "stroke_width": 5,
        }), out_ms=5000,
    )
    target.transform.position.default = [640, 360]
    circle = MotionLayer(
        name="Circle Cutout", layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 210, "height": 210, "shape": "ellipse", "stroke_width": 0,
        }), out_ms=5000,
    )
    circle.transform.position = _position(
        [535, 360], (0, [455, 360]), (1200, [535, 360]), (4200, [580, 360]),
    )
    star = MotionLayer(
        name="Star Cutout", layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 230, "height": 230, "shape": "star", "sides": 5,
            "inner_ratio": .45, "stroke_width": 0,
        }), out_ms=5000,
    )
    star.transform.position.default = [760, 360]
    star.transform.rotation.default = 12
    target.source.params["boolean"] = {
        "operation": "subtract",
        "operand_layer_ids": [circle.id, star.id],
        "hide_operands": True,
    }
    composition.layers = [background, target, circle, star]
    return composition


def capture_boolean(output_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    composition = build_boolean_composition()
    target = next(row for row in composition.layers if row.name == "Boolean Plate")
    window = MotionDesignerWindow(composition)
    window.resize(1600, 900)
    window.show()
    app.processEvents()
    window._select_layer(target.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.vector)
    window.timeline.set_time_and_emit(1200)
    app.processEvents()
    _assert_dark_inspector_surface(window)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output_path), "PNG"):
        raise RuntimeError(f"Could not write screenshot: {output_path}")
    window.close()
    app.processEvents()


def capture_ai(reference_path: Path, output_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    composition = MotionComposition(
        name="Motion AI Workspace QA", width=1280, height=720, fps=30.0, duration_ms=5000,
    )
    window = MotionDesignerWindow(composition)
    window.resize(1920, 900)
    window.show()
    app.processEvents()
    window.ai.add_paths([str(reference_path)])
    window.ai.prompt.setPlainText(
        'Use the dropped frame as a full background, fade it in, and add "OMNI MOTION".'
    )
    window.ai.advanced_button.setChecked(True)
    window.ai.request_plan()
    deadline = time.monotonic() + 15.0
    while window.ai._proposal is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    if window.ai._proposal is None:
        raise RuntimeError("Motion AI UI QA timed out waiting for candidates")
    window.ai.apply_proposal()
    window.timeline.set_time_and_emit(1200)
    app.processEvents()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output_path), "PNG"):
        raise RuntimeError(f"Could not write screenshot: {output_path}")
    window.close()
    app.processEvents()


def main() -> int:
    output = ROOT / "debugCapture" / "motion_designer"
    for size, name in (((1600, 900), "motion_designer_1600x900.png"),
                       ((1280, 720), "motion_designer_1280x720.png")):
        capture(size, output / name)
        print(output / name)
    vector_path = output / "motion_designer_vector_1600x900.png"
    capture_vector(vector_path)
    print(vector_path)
    vector_render_path = output / "motion_designer_vector_render_1280x720.png"
    MotionExportRenderer().save_png(build_demo_composition(), 1200, vector_render_path)
    print(vector_render_path)
    typography_path = output / "motion_designer_typography_1600x900.png"
    capture_typography(typography_path)
    print(typography_path)
    typography_path_picker = output / "motion_designer_typography_path_1600x900.png"
    capture_typography_path(typography_path_picker)
    print(typography_path_picker)
    mask_path = output / "motion_designer_mask_tracking_1600x900.png"
    capture_mask_tracking(mask_path)
    print(mask_path)
    boolean_path = output / "motion_designer_boolean_1600x900.png"
    capture_boolean(boolean_path)
    print(boolean_path)
    boolean_render_path = output / "motion_designer_boolean_render_1280x720.png"
    MotionExportRenderer().save_png(build_boolean_composition(), 1200, boolean_render_path)
    print(boolean_render_path)
    ai_path = output / "motion_designer_ai_1920x900.png"
    capture_ai(vector_render_path, ai_path)
    print(ai_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

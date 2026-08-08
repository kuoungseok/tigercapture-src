"""Capture real OpenGL Craft and Painterly Motion preview evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from time import sleep

if os.name == "nt":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    os.environ.setdefault("QT_OPENGL", "desktop")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.craft_style import make_craft_style_effect
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.painterly_look import make_painterly_look_effect
from app.motion_designer.ar_pbr_source import create_light_layer
from app.motion_designer.schema import (
    Keyframe,
    MotionComposition,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.ui.window import MotionDesignerWindow


OUTPUT = ROOT / "debugCapture" / "motion_style_gpu"


def _composition(kind: str) -> MotionComposition:
    effect = (
        make_craft_style_effect(preset="archive_print")
        if kind == "craft"
        else make_painterly_look_effect(preset="ink")
    )
    background = MotionLayer(
        id=f"{kind}_background",
        name="Background",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={"width": 960, "height": 540, "fill": "#163c4a"},
        ),
        out_ms=4000,
    )
    background.transform.position.default = [480, 270]
    background.metadata["three_d"] = {
        "enabled": True,
        "receive_shadows": True,
        "projection_model": "affine_card_2_5d",
    }
    matte = MotionLayer(
        id=f"{kind}_matte",
        name=f"{kind.title()} Matte",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "width": 380,
                "height": 280,
                "fill": "#ffffff",
                "radius": 120,
            },
        ),
        out_ms=4000,
    )
    matte.transform.position.default = [480, 270]
    card = MotionLayer(
        id=f"{kind}_card",
        name=f"{kind.title()} GPU",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "width": 620,
                "height": 350,
                "fill": "#e76f51",
                "radius": 42,
            },
        ),
        effects=[effect],
        blend_mode="multiply" if kind == "craft" else "screen",
        metadata={
            "depth_z": 1.0,
            "matte_layer_id": matte.id,
            "matte_mode": "alpha",
            "three_d": {
                "enabled": True,
                "cast_shadows": True,
                "shadow_strength": 0.72,
                "shadow_softness": 5.0,
                "projection_model": "affine_card_2_5d",
            },
            "motion_blur": {
                "enabled": True,
                "samples": 8,
                "shutter": 0.65,
            },
        },
        out_ms=4000,
    )
    card.transform.position.keyframes = [
        Keyframe(time_ms=0, value=[360, 270]),
        Keyframe(time_ms=4000, value=[600, 270]),
    ]
    light = create_light_layer(
        duration_ms=4000,
        params={
            "azimuth": 145.0,
            "elevation": 42.0,
            "intensity": 0.42,
        },
    )
    return MotionComposition(
        id=f"style_gpu_{kind}",
        name=f"Style GPU {kind.title()}",
        width=960,
        height=540,
        duration_ms=4000,
        layers=[background, matte, card, light],
    )


def _capture(app: QApplication, kind: str) -> dict[str, object]:
    composition = _composition(kind)
    window = MotionDesignerWindow(composition)
    window.resize(1280, 760)
    window.show()
    window.viewer_tabs.setCurrentWidget(window.preview)
    window.timeline.set_time_and_emit(1250)
    for _index in range(40):
        app.processEvents()
        sleep(0.02)
    frame = window.preview.grabFramebuffer()
    path = OUTPUT / f"{kind}_gpu_preview.png"
    saved = not frame.isNull() and frame.save(str(path), "PNG")
    diagnostics = window.preview.diagnostics()
    export_renderer = MotionExportRenderer()
    export_frame = export_renderer.render_frame(
        composition,
        1250,
        use_cache=False,
    )
    export_path = OUTPUT / f"{kind}_gpu_export.png"
    export_saved = (
        not export_frame.isNull()
        and export_frame.save(str(export_path), "PNG")
    )
    export_diagnostics = export_renderer.last_render_report
    result = {
        "kind": kind,
        "ok": bool(
            saved
            and diagnostics.get("backend") == "motion_style_gpu"
            and diagnostics.get("context_valid")
            and int(diagnostics.get("gl_error", -1)) == 0
            and int(diagnostics.get(f"{kind}_pass_count", 0)) == 1
            and int(diagnostics.get("motion_blur_pass_count", 0)) == 1
            and int(diagnostics.get("blend_pass_count", 0)) == 1
            and int(diagnostics.get("matte_pass_count", 0)) == 1
            and int(diagnostics.get("shadow_pass_count", 0)) == 1
            and export_saved
            and export_diagnostics.get("backend") == "motion_style_gpu"
            and export_diagnostics.get("offscreen_export") is True
            and int(export_diagnostics.get("gl_error", -1)) == 0
        ),
        "diagnostics": diagnostics,
        "export_diagnostics": export_diagnostics,
        "screenshot": str(path),
        "export_screenshot": str(export_path),
    }
    window.close()
    app.processEvents()
    return result


def main() -> int:
    app = QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = [_capture(app, "craft"), _capture(app, "painterly")]
    report = {
        "schema": "tigerstudio.motion.style_gpu_qa.v1",
        "ok": all(bool(row["ok"]) for row in rows),
        "rows": rows,
    }
    report_path = OUTPUT / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

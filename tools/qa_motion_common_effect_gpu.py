"""Exercise common Motion effects through real offscreen OpenGL composition."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

if os.name == "nt":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    os.environ.setdefault("QT_OPENGL", "desktop")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.motion_designer.gpu_export_renderer import MotionGpuExportRenderer
from app.motion_designer.render_graph import build_render_graph, render_graph_image
from app.motion_designer.schema import (
    AnimatedProperty,
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    SourceRef,
)


OUTPUT = ROOT / "debugCapture" / "motion_common_effect_gpu"


def _shape(
    layer_id: str,
    *,
    fill: str,
    size: tuple[int, int],
    position: tuple[int, int],
    effect: MotionEffectRef | None = None,
    parent_id: str = "",
) -> MotionLayer:
    layer = MotionLayer(
        id=layer_id,
        name=layer_id.replace("_", " ").title(),
        parent_id=parent_id,
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "width": size[0],
                "height": size[1],
                "fill": fill,
                "radius": 26,
            },
        ),
        effects=[effect] if effect is not None else [],
        out_ms=2000,
    )
    layer.transform.position.default = list(position)
    return layer


def _composition() -> MotionComposition:
    group = MotionLayer(
        id="effect_group",
        name="Effect Group",
        layer_type="group",
        effects=[
            MotionEffectRef(
                kind="posterize",
                params={
                    "levels": AnimatedProperty(default=5),
                    "amount": AnimatedProperty(default=0.65),
                },
            ),
        ],
        out_ms=2000,
    )
    adjustment = MotionLayer(
        id="global_adjustment",
        name="Global Adjustment",
        layer_type="adjustment",
        effects=[
            MotionEffectRef(
                kind="vignette",
                params={
                    "amount": AnimatedProperty(default=0.32),
                    "softness": AnimatedProperty(default=0.55),
                },
            ),
        ],
        out_ms=2000,
    )
    return MotionComposition(
        id="common_effect_gpu_qa",
        name="Common Effect GPU QA",
        width=640,
        height=360,
        duration_ms=2000,
        layers=[
            _shape(
                "background",
                fill="#246777",
                size=(640, 360),
                position=(320, 180),
            ),
            group,
            _shape(
                "group_card",
                fill="#f0a43c",
                size=(230, 220),
                position=(190, 180),
                parent_id=group.id,
            ),
            _shape(
                "graded_card",
                fill="#d34d71",
                size=(230, 220),
                position=(450, 180),
                effect=MotionEffectRef(
                    kind="saturation",
                    params={"amount": AnimatedProperty(default=0.25)},
                ),
            ),
            adjustment,
        ],
    )


def _rgba(image: QImage) -> np.ndarray:
    straight = image.convertToFormat(QImage.Format_RGBA8888)
    return np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(
        straight.height(),
        straight.bytesPerLine(),
    )[:, : straight.width() * 4].reshape(
        straight.height(),
        straight.width(),
        4,
    ).copy()


def main() -> int:
    QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    composition = _composition()
    graph = build_render_graph(composition, 700, render_quality="export")
    cpu = render_graph_image(graph, output_size=(640, 360))
    gpu_renderer = MotionGpuExportRenderer()
    gpu = gpu_renderer.render(graph, width=640, height=360)
    if gpu is None:
        report = {
            "schema": "tigerstudio.motion.common_effect_gpu_qa.v1",
            "ok": False,
            "diagnostics": gpu_renderer.last_diagnostics,
        }
    else:
        cpu.save(str(OUTPUT / "cpu_reference.png"), "PNG")
        gpu.save(str(OUTPUT / "gpu_export.png"), "PNG")
        delta = np.abs(_rgba(cpu).astype(np.int16) - _rgba(gpu).astype(np.int16))
        mean_rgb = float(delta[..., :3].mean())
        mean_alpha = float(delta[..., 3].mean())
        diagnostics = gpu_renderer.last_diagnostics
        report = {
            "schema": "tigerstudio.motion.common_effect_gpu_qa.v1",
            "ok": bool(
                diagnostics.get("backend") == "motion_compositor_gpu"
                and int(diagnostics.get("gl_error", -1)) == 0
                and int(diagnostics.get("common_effect_pass_count", 0)) == 3
                and int(diagnostics.get("adjustment_pass_count", 0)) == 1
                and mean_rgb <= 18.0
                and mean_alpha <= 1.0
            ),
            "mean_rgb_abs_error": mean_rgb,
            "mean_alpha_abs_error": mean_alpha,
            "diagnostics": diagnostics,
            "cpu_reference": str(OUTPUT / "cpu_reference.png"),
            "gpu_export": str(OUTPUT / "gpu_export.png"),
        }
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

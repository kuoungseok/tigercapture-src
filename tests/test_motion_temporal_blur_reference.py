from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.motion_designer.render_graph import (
    build_render_graph,
    render_graph_image,
    shutter_sample_times,
)
from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    SourceRef,
)


def _alpha_columns(image: QImage) -> list[int]:
    rgba = image.convertToFormat(QImage.Format_RGBA8888)
    return [
        sum(rgba.pixelColor(x, y).alpha() for y in range(rgba.height()))
        for x in range(rgba.width())
    ]


def test_shutter_samples_follow_angle_and_phase() -> None:
    assert shutter_sample_times(1000.0, 25.0, 3, 180.0, -90.0) == [990.0, 1000.0, 1010.0]
    assert shutter_sample_times(1000.0, 25.0, 3, 360.0, 0.0) == [1000.0, 1020.0, 1040.0]


def test_temporal_shutter_renders_multiple_layer_times() -> None:
    QApplication.instance() or QApplication([])
    layer = MotionLayer(
        id="moving",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "primitive": "rectangle", "width": 12.0, "height": 20.0,
            "fill": "#ffffffff", "stroke": "#00000000", "stroke_width": 0.0,
        }),
        out_ms=1000,
    )
    layer.transform.position = AnimatedProperty(
        value_type="vector2",
        default=[10.0, 32.0],
        keyframes=[
            Keyframe(time_ms=0, value=[10.0, 32.0]),
            Keyframe(time_ms=1000, value=[118.0, 32.0]),
        ],
    )
    composition = MotionComposition(width=128, height=64, fps=10.0, duration_ms=1000, layers=[layer])
    sharp = render_graph_image(build_render_graph(composition, 500.0))
    layer.metadata["motion_blur"] = {
        "enabled": True,
        "contract": "temporal_shutter_samples_v1",
        "samples": 9,
        "shutter_angle": 360.0,
        "shutter_phase": -180.0,
    }
    blurred = render_graph_image(build_render_graph(composition, 500.0))
    sharp_columns = sum(value > 0 for value in _alpha_columns(sharp))
    blurred_columns = sum(value > 0 for value in _alpha_columns(blurred))
    assert blurred_columns > sharp_columns
    assert build_render_graph(composition, 500.0).diagnostics["motion_blur_node_count"] == 1

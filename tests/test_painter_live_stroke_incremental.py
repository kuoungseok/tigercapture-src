"""Guards for the incremental Painter stroke paths.

Each case pins a place where the canvas used to redo work proportional to the
whole document or the whole stroke on every input sample or pen-up.
"""
from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _mouse(kind, x, y):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    return QMouseEvent(
        kind,
        QPointF(x, y),
        QPointF(x, y),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_callback_backed_strokes_use_the_raster_cache() -> None:
    """The video and GIF overlays own no stroke list, and still must cache.

    Without this they re-rendered every committed stroke on every frame, which
    is what made drawing on the preview overlay unusable once a few hundred
    strokes existed.
    """

    _app()
    from PySide6.QtGui import QImage

    from app.drawing import DrawingCanvas, Stroke

    strokes = [
        Stroke(points=[(0.1, index / 60.0), (0.9, index / 60.0)])
        for index in range(1, 51)
    ]
    canvas = DrawingCanvas(lambda: 0, lambda: strokes)
    canvas.resize(240, 160)
    assert not hasattr(canvas, "_embedded_strokes")
    calls = {"count": 0}
    original = DrawingCanvas._paint_committed_strokes_qpainter

    def counted(self, *args, **kwargs):
        calls["count"] += 1
        return original(self, *args, **kwargs)

    DrawingCanvas._paint_committed_strokes_qpainter = counted
    try:
        frame = QImage(canvas.size(), QImage.Format.Format_ARGB32_Premultiplied)
        canvas.render(frame)
        canvas.render(frame)
        canvas.render(frame)
        assert calls["count"] == 1
        # A changed list has to be noticed even though nothing bumped a
        # revision counter.
        strokes.append(Stroke(points=[(0.2, 0.2), (0.8, 0.8)]))
        canvas.render(frame)
        assert calls["count"] == 2
    finally:
        DrawingCanvas._paint_committed_strokes_qpainter = original
        canvas.close()
        canvas.deleteLater()


def test_missing_gl_context_is_not_reprobed_per_commit() -> None:
    _app()
    from PySide6.QtGui import QImage

    from app.drawing import DrawingCanvas, Stroke

    canvas = DrawingCanvas(lambda: 0)
    canvas.resize(200, 140)
    canvas.set_strokes_snapshot(
        [Stroke(points=[(0.1, 0.1), (0.9, 0.9)], point_pressure=[1.0, 1.0])]
    )
    frame = QImage(canvas.size(), QImage.Format.Format_ARGB32_Premultiplied)
    canvas.render(frame)
    if not getattr(canvas, "_painter_canvas_gpu_context_unavailable", ""):
        pytest.skip("This environment has a usable Painter OpenGL context.")
    probes = {"count": 0}
    import app.painter_opengl as painter_opengl

    original = painter_opengl.canvas_stroke_gpu_signature

    def counted(*args, **kwargs):
        probes["count"] += 1
        return original(*args, **kwargs)

    painter_opengl.canvas_stroke_gpu_signature = counted
    try:
        for index in range(5):
            canvas.add_stroke_direct(
                Stroke(
                    points=[(0.2, 0.2 + index / 20.0), (0.8, 0.5)],
                    point_pressure=[1.0, 1.0],
                )
            )
            canvas.render(frame)
        assert probes["count"] == 0
        status = canvas._painter_canvas_renderer_status
        assert status["fallback"] is True
        assert status["size"] == [200, 140]
    finally:
        painter_opengl.canvas_stroke_gpu_signature = original
        canvas.close()
        canvas.deleteLater()


def test_layered_documents_append_instead_of_rebuilding() -> None:
    """A blend-mode document must not re-render itself on every pen-up."""

    _app()
    from PySide6.QtGui import QImage

    from app.drawing import DrawingCanvas, PaintLayer, Stroke

    def build(incremental: bool):
        canvas = DrawingCanvas(lambda: 0)
        canvas.resize(200, 140)
        canvas.set_strokes_snapshot(
            [
                Stroke(
                    points=[
                        (0.05 + index / 40.0, 0.1),
                        (0.05 + index / 40.0, 0.9),
                    ],
                    point_pressure=[1.0, 1.0],
                    width_px=5.0,
                )
                for index in range(20)
            ]
        )
        canvas.set_layer_view(
            visibility={"paint-layer-1": True},
            order=["paint-layer-1"],
            layers=[
                PaintLayer("paint-layer-1", "Multiply", blend_mode="multiply")
            ],
        )
        if not incremental:
            canvas._append_stroke_to_layer_cache = (
                lambda stroke, *, previous_revision: False
            )
        return canvas, QImage(
            canvas.size(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )

    fast, fast_frame = build(True)
    slow, slow_frame = build(False)
    fast.render(fast_frame)
    slow.render(slow_frame)
    calls = {"count": 0}
    original = DrawingCanvas._paint_committed_strokes_qpainter

    def counted(self, *args, **kwargs):
        calls["count"] += 1
        return original(self, *args, **kwargs)

    DrawingCanvas._paint_committed_strokes_qpainter = counted
    try:
        for canvas, frame in ((fast, fast_frame), (slow, slow_frame)):
            canvas.add_stroke_direct(
                Stroke(
                    points=[(0.25, 0.15), (0.75, 0.85)],
                    point_pressure=[1.0, 1.0],
                    width_px=9.0,
                    color=(20, 200, 120),
                )
            )
            frame.fill(0)
            canvas.render(frame)
        # Only the fallback canvas re-rendered the document.
        assert calls["count"] == 1
        assert bytes(fast_frame.constBits()) == bytes(slow_frame.constBits())
    finally:
        DrawingCanvas._paint_committed_strokes_qpainter = original
        fast.close()
        fast.deleteLater()
        slow.close()
        slow.deleteLater()


@pytest.mark.parametrize(
    "dynamics",
    [
        {"enabled": True, "mode": "paint", "scatter": 55, "scatter_count": 3},
        {"enabled": True, "mode": "paint", "stabilization": 65},
        {"enabled": True, "mode": "smudge", "smudge_length": 70},
        {"enabled": True, "mode": "mixer", "mix": 60},
    ],
)
def test_live_dynamic_stroke_extends_instead_of_repainting(dynamics) -> None:
    """The live preview appends dabs, and still matches the full repaint."""

    _app()
    from PySide6.QtGui import QImage, QMouseEvent

    from app.drawing import DrawingCanvas, Stroke

    def draw(incremental: bool):
        canvas = DrawingCanvas(lambda: 0)
        canvas.resize(220, 150)
        canvas.set_strokes_snapshot(
            [
                Stroke(
                    points=[
                        (0.1 + index / 12.0, 0.2),
                        (0.1 + index / 12.0, 0.8),
                    ],
                    point_pressure=[1.0, 1.0],
                    width_px=12.0,
                    color=(40 + 20 * index, 180, 90),
                )
                for index in range(6)
            ]
        )
        canvas.set_tool("pen")
        canvas.set_pen_width(18.0)
        canvas._brush_dynamics = dict(dynamics)
        if not incremental:
            canvas._paint_live_dynamic_increment = lambda w, h: False
        frame = QImage(canvas.size(), QImage.Format.Format_ARGB32_Premultiplied)
        canvas.mousePressEvent(
            _mouse(QMouseEvent.Type.MouseButtonPress, 20.0, 40.0)
        )
        for index in range(1, 26):
            canvas.mouseMoveEvent(
                _mouse(
                    QMouseEvent.Type.MouseMove,
                    20.0 + index * 7.0,
                    40.0 + (index % 5) * 9.0,
                )
            )
        frame.fill(0)
        canvas.render(frame)
        used_stream = bool(getattr(canvas, "_live_dynamic_cap_dabs", None))
        canvas.close()
        canvas.deleteLater()
        return frame, used_stream

    fast, used_stream = draw(True)
    slow, _ = draw(False)
    assert used_stream is True
    left = bytes(fast.constBits())
    right = bytes(slow.constBits())
    if left != right:
        # The live overlay composites in one more stage than the committed
        # render, which the brush model contract budgets at a couple of code
        # values.
        assert max(abs(a - b) for a, b in zip(left, right)) <= 2


def test_live_dynamic_stream_falls_back_for_length_coupled_features() -> None:
    """Features whose alpha field spans the stroke cannot be extended."""

    _app()
    from app.painter_advanced_brush import advanced_dab_alphas_prefix_stable
    from app.painter_brush_dynamics import (
        DynamicDabStream,
        normalize_brush_dynamics,
    )
    from app.drawing import Stroke

    for settings in (
        {"noise_enabled": True},
        {"dual_brush_enabled": True},
        {"wet_edges_enabled": True},
        {"protect_texture": True},
        {"texture": {"pattern_id": "canvas", "strength": 40}},
    ):
        cfg = normalize_brush_dynamics({"enabled": True, **settings})
        assert advanced_dab_alphas_prefix_stable(cfg) is False
        stroke = Stroke(
            points=[(0.1, 0.1), (0.4, 0.4), (0.8, 0.5)],
            point_pressure=[1.0, 1.0, 1.0],
            point_tilt_x=[0.0, 0.0, 0.0],
            point_tilt_y=[0.0, 0.0, 0.0],
            point_rotation=[0.5, 0.5, 0.5],
            point_tangential_pressure=[0.0, 0.0, 0.0],
            brush_dynamics=dict(cfg),
        )
        assert DynamicDabStream().update(stroke, 200, 120) is None

    plain = normalize_brush_dynamics({"enabled": True})
    assert advanced_dab_alphas_prefix_stable(plain) is True

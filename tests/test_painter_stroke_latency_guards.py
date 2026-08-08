from __future__ import annotations

import os
from types import SimpleNamespace

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_committed_strokes_are_not_repainted_on_cache_hit() -> None:
    _app()
    from PySide6.QtGui import QImage, QPainter

    from app.drawing import DrawingCanvas, Stroke

    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.resize(320, 180)
    strokes = [
        Stroke(points=[(0.1, index / 120.0), (0.9, index / 120.0)])
        for index in range(1, 101)
    ]
    canvas.set_strokes_snapshot(strokes)
    calls = {"count": 0}

    def count_stroke(*_args, **_kwargs):
        calls["count"] += 1

    canvas._paint_stroke = count_stroke
    target = QImage(320, 180, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(target)
    try:
        canvas._paint_strokes_with_cpu_cache(painter, strokes, 320, 180, 0)
        assert calls["count"] == 100
        canvas._paint_strokes_with_cpu_cache(painter, strokes, 320, 180, 0)
        assert calls["count"] == 100
        added = Stroke(points=[(0.1, 0.95), (0.9, 0.95)])
        canvas.add_stroke_direct(added)
        assert calls["count"] == 101
        canvas._paint_strokes_with_cpu_cache(
            painter,
            canvas.embedded_strokes(),
            320,
            180,
            0,
        )
        assert calls["count"] == 101
    finally:
        painter.end()


def test_live_brush_work_per_sample_is_bounded_to_latest_segment() -> None:
    _app()
    from PySide6.QtCore import QPointF

    from app.drawing import DrawingCanvas

    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.resize(640, 360)
    canvas.set_pen_style("bristle_oil")
    rendered_point_counts: list[int] = []

    def record_segment(_painter, stroke, *_args, **_kwargs):
        rendered_point_counts.append(len(stroke.points))

    canvas._paint_stroke = record_segment
    sample = SimpleNamespace(
        pressure=0.8,
        tilt=0.2,
        tilt_x=0.1,
        tilt_y=-0.1,
        rotation=0.25,
        tangential_pressure=0.0,
        load=0.9,
    )
    canvas._begin_current_stroke(QPointF(10, 100), sample)
    for index in range(1, 200):
        canvas._append_current_stroke_sample(
            QPointF(10 + index * 2.5, 100 + (index % 7)),
            sample,
        )

    assert len(rendered_point_counts) == 200
    assert max(rendered_point_counts) <= 2


def test_paint_stroke_history_uses_delta_commands() -> None:
    app = _app()
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(
            320,
            180,
            "transparent",
        ),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._on_stroke_added(
        Stroke(points=[(0.1, 0.5), (0.9, 0.5)], source_tool="pen")
    )

    assert dialog._undo_stack[-1]["kind"] == "stroke_add"
    assert len(dialog.canvas.embedded_strokes()) == 1
    dialog._undo()
    assert dialog.canvas.embedded_strokes() == []
    dialog._redo()
    assert len(dialog.canvas.embedded_strokes()) == 1

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_malformed_stroke_history_indices_are_rejected_without_mutation() -> None:
    app = _app()
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap
    from PySide6.QtWidgets import QListWidget

    stroke = Stroke(points=[(0.1, 0.5), (0.9, 0.5)], source_tool="pen")
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180, "transparent"),
        initial_strokes=[stroke],
        time_ms=0,
        standalone=True,
    )
    before = dialog.canvas.embedded_strokes()
    invalid_commands = [
        ({"kind": "stroke_add", "start": -1, "strokes": [stroke]}, True),
        ({"kind": "stroke_add", "start": 9, "strokes": [stroke]}, True),
        ({"kind": "stroke_add", "start": 0.5, "strokes": [stroke]}, True),
        ({"kind": "stroke_remove", "index": -1, "stroke": stroke}, False),
        ({"kind": "stroke_remove", "index": 9, "stroke": stroke}, False),
        ({"kind": "stroke_remove", "index": 0.5, "stroke": stroke}, False),
    ]

    for command, undo in invalid_commands:
        with pytest.raises(ValueError):
            dialog._apply_stroke_history_command(command, undo=undo)
        assert dialog.canvas.embedded_strokes() == before

    dialog.canvas.set_strokes_snapshot([])
    with pytest.raises(ValueError, match="outside the current stroke range"):
        dialog._apply_stroke_history_command(
            {"kind": "stroke_remove", "index": 0, "stroke": stroke},
            undo=False,
        )
    assert dialog.canvas.embedded_strokes() == []

    history = QListWidget()
    dialog._history_list = history
    dialog._undo_labels = []
    dialog._redo_labels = []
    dialog._update_history_list()
    assert history.count() == 1
    assert history.currentRow() == 0
    dialog._undo_labels = ["First", "Second"]
    dialog._redo_labels = ["Third"]
    dialog._update_history_list()
    assert history.count() == 4
    assert history.currentRow() == 2

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_atlas_accepts_precomputed_signature_without_rehash(monkeypatch) -> None:
    from PySide6.QtGui import QImage

    import app.painter_opengl as painter_opengl

    def fail_hash(*_args, **_kwargs):
        raise AssertionError("precomputed signature should bypass hashing")

    def fake_render(*_args, width: int, height: int, **_kwargs):
        image = QImage(width, height, QImage.Format.Format_RGBA8888)
        image.fill(0)
        return image, {"renderer": "test", "active": "opengl"}

    monkeypatch.setattr(painter_opengl, "canvas_stroke_gpu_signature", fail_hash)
    monkeypatch.setattr(
        painter_opengl,
        "render_canvas_strokes_opengl_qimage",
        fake_render,
    )
    atlas = painter_opengl.PainterCanvasStrokeAtlas()
    image, report = atlas.render(
        [],
        signature="known-signature",
        width=16,
        height=16,
        time_ms=0,
    )

    assert not image.isNull()
    assert report["signature"] == "known-signature"


def test_atlas_reuses_one_session_across_changed_signatures(monkeypatch) -> None:
    from PySide6.QtGui import QImage

    import app.painter_opengl as painter_opengl

    sessions = []

    def fake_render(*_args, width: int, height: int, _session=None, **_kwargs):
        sessions.append(_session)
        image = QImage(width, height, QImage.Format.Format_RGBA8888)
        image.fill(0)
        return image, {"renderer": "test", "active": "opengl"}

    monkeypatch.setattr(
        painter_opengl,
        "render_canvas_strokes_opengl_qimage",
        fake_render,
    )
    atlas = painter_opengl.PainterCanvasStrokeAtlas()
    for signature in ("first", "second", "third"):
        atlas.render([], signature=signature, width=32, height=24, time_ms=0)
    assert len(sessions) == 3
    assert all(session is not None for session in sessions)
    assert len({id(session) for session in sessions}) == 1
    atlas.close()
    assert atlas.telemetry()["closed"] is True


def test_canvas_destruction_closes_retained_opengl_atlas() -> None:
    app = _app()
    import shiboken6

    from app.drawing import DrawingCanvas

    class AtlasProbe:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    canvas = DrawingCanvas(lambda: 0, lambda: [])
    probe = AtlasProbe()
    canvas._painter_canvas_stroke_atlas = probe
    shiboken6.delete(canvas)
    app.processEvents()

    assert probe.closed == 1


def test_opengl_render_entry_points_reject_invalid_document_dimensions() -> None:
    import app.painter_opengl as painter_opengl

    with pytest.raises((TypeError, ValueError)):
        painter_opengl.render_canvas_strokes_opengl_qimage(
            [], width=0, height=24, time_ms=0
        )
    with pytest.raises((TypeError, ValueError)):
        painter_opengl.render_blockout_scene_opengl_qimage(
            {}, width=32, height=0
        )
    with pytest.raises(TypeError):
        painter_opengl.render_canvas_strokes_opengl_qimage(
            [], width=19.9, height=13, time_ms=0
        )
    with pytest.raises(TypeError):
        painter_opengl.render_blockout_scene_opengl_qimage(
            {}, width=True, height=13
        )

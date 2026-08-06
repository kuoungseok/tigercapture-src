from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _mask(values: list[int]):
    from PySide6.QtGui import QImage

    payload = bytes(values)
    return QImage(
        payload,
        len(values),
        1,
        len(values),
        QImage.Format.Format_Alpha8,
    ).copy()


def _values(mask) -> list[int]:
    from PySide6.QtGui import QImage

    converted = mask.convertToFormat(QImage.Format.Format_Alpha8)
    return list(bytes(converted.constBits())[: converted.width()])


def test_quick_mask_alpha8_white_black_gray_boundary_and_overlay() -> None:
    from PySide6.QtGui import QColor
    from app.painter_quick_mask import (
        apply_quick_mask_coverage,
        quick_mask_boundary_mask,
        quick_mask_entry_selection,
        quick_mask_grayscale_value,
        quick_mask_overlay_image,
    )

    source = _mask([0, 64, 128, 255])
    assert _values(quick_mask_entry_selection(None, 4, 1)) == [0, 0, 0, 0]
    assert _values(quick_mask_entry_selection(source, 4, 1)) == [0, 64, 128, 255]
    assert quick_mask_grayscale_value(QColor("#000000")) == 0
    assert quick_mask_grayscale_value(QColor("#808080")) == 128
    assert quick_mask_grayscale_value(QColor("#FFFFFF")) == 255

    coverage = _mask([255, 255, 128, 0])
    assert _values(apply_quick_mask_coverage(source, coverage, 255)) == [
        255, 255, 192, 255,
    ]
    assert _values(apply_quick_mask_coverage(source, coverage, 0)) == [
        0, 0, 64, 255,
    ]
    assert _values(apply_quick_mask_coverage(source, coverage, 128)) == [
        128, 128, 128, 255,
    ]
    assert _values(quick_mask_boundary_mask(_mask([0, 127, 128, 255]))) == [
        0, 0, 255, 255,
    ]
    overlay = quick_mask_overlay_image(_mask([0, 127, 128, 255]), 4, 1)
    assert [overlay.pixelColor(x, 0).alpha() for x in range(4)] == [128, 64, 63, 0]


def test_quick_mask_mouse_eraser_emits_mask_stroke_instead_of_deleting() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from app.drawing import DrawingCanvas

    canvas = DrawingCanvas(get_time_ms=lambda: 0, get_strokes=lambda: [])
    canvas.setFixedSize(64, 64)
    canvas.set_document_size(64, 64)
    canvas.set_quick_mask_enabled(True)
    canvas.set_tool("eraser")
    emitted = []
    erased = []
    canvas.stroke_added.connect(emitted.append)
    canvas.stroke_erased_at.connect(erased.append)
    canvas.show()
    app.processEvents()

    QTest.mousePress(
        canvas,
        Qt.MouseButton.LeftButton,
        pos=QPoint(20, 20),
    )
    QTest.mouseMove(canvas, QPoint(36, 36), delay=1)
    QTest.mouseRelease(
        canvas,
        Qt.MouseButton.LeftButton,
        pos=QPoint(36, 36),
    )
    app.processEvents()

    assert len(emitted) == 1
    assert emitted[0].source_tool == "eraser"
    assert len(emitted[0].points) >= 2
    assert erased == []
    canvas.close()


def test_quick_mask_real_tablet_eraser_emits_mask_stroke() -> None:
    _app()
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QInputDevice, QPointingDevice, QTabletEvent
    from app.drawing import DrawingCanvas

    device = QPointingDevice(
        "Tiger Quick Mask Eraser",
        704,
        QInputDevice.DeviceType.Stylus,
        QPointingDevice.PointerType.Eraser,
        QInputDevice.Capability.Position | QInputDevice.Capability.Pressure,
        1,
        3,
    )
    canvas = DrawingCanvas(get_time_ms=lambda: 0, get_strokes=lambda: [])
    canvas.setFixedSize(64, 64)
    canvas.set_document_size(64, 64)
    canvas.set_quick_mask_enabled(True)
    canvas.set_tool("pen")
    emitted = []
    erased = []
    canvas.stroke_added.connect(emitted.append)
    canvas.stroke_erased_at.connect(erased.append)

    def event(event_type, x, y, button, buttons):
        return QTabletEvent(
            event_type,
            device,
            QPointF(x, y),
            QPointF(x, y),
            0.7,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            Qt.KeyboardModifier.NoModifier,
            button,
            buttons,
        )

    canvas.tabletEvent(event(
        QEvent.Type.TabletPress,
        18.0,
        18.0,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    ))
    canvas.tabletEvent(event(
        QEvent.Type.TabletMove,
        34.0,
        34.0,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
    ))
    canvas.tabletEvent(event(
        QEvent.Type.TabletRelease,
        42.0,
        42.0,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
    ))

    assert len(emitted) == 1
    assert emitted[0].source_tool == "eraser"
    assert len(emitted[0].points) >= 3
    assert erased == []
    canvas.close()


def test_quick_mask_dialog_routes_strokes_to_selection_and_preserves_layer(
    tmp_path,
) -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    layer = dialog._active_paint_layer()
    raster = QImage(8, 8, QImage.Format.Format_ARGB32_Premultiplied)
    raster.fill(QColor("#FF0000"))
    dialog._set_paint_layer_raster(layer.layer_id, raster)
    dialog.canvas.select_rectangle(0.0, 0.0, 0.5, 1.0)
    initial_mask = dialog._sync_pixel_selection_from_canvas()
    assert initial_mask is not None
    initial_values = bytes(initial_mask.constBits())
    layer_before = dialog._paint_layer_raster(layer.layer_id, create=False)
    assert layer_before is not None
    layer_before = layer_before.copy()
    stroke_count_before = len(dialog.canvas.embedded_strokes())
    dialog._background_color = QColor("#ABCDEF")
    dialog._apply_pen_color(QColor("#123456"), remember=False)

    assert dialog._set_quick_mask_enabled(True)
    assert dialog._pen_color == QColor("#000000")
    assert dialog._background_color == QColor("#FFFFFF")
    assert dialog.canvas.selection_snapshot() == []
    assert bytes(dialog._selection_pixel_mask.constBits()) == initial_values
    undo_before = len(dialog._undo_stack)

    def edit(
        color: tuple[int, int, int],
        source_tool: str = "pen",
        opacity: int = 255,
    ) -> int:
        dialog._on_stroke_added(Stroke(
            points=[(0.75, 0.5)],
            color=color,
            opacity=opacity,
            width_px=3.0,
            source_tool=source_tool,
        ))
        return dialog._selection_pixel_mask.pixelColor(6, 4).alpha()

    assert edit((255, 255, 255)) == 255
    assert edit((0, 0, 0)) == 0
    no_op_undo = len(dialog._undo_stack)
    assert edit((0, 0, 0), opacity=0) == 0
    assert len(dialog._undo_stack) == no_op_undo
    assert edit((0, 0, 0), source_tool="eraser") == 255
    assert edit((128, 128, 128)) == 128
    assert len(dialog._undo_stack) == undo_before + 4
    assert len(dialog.canvas.embedded_strokes()) == stroke_count_before
    layer_after = dialog._paint_layer_raster(layer.layer_id, create=False)
    assert layer_after is not None and layer_after == layer_before

    edited = QImage(dialog._selection_pixel_mask)
    assert dialog._set_quick_mask_enabled(False)
    assert not dialog._quick_mask_enabled
    assert dialog._pen_color == QColor("#123456")
    assert dialog._background_color == QColor("#ABCDEF")
    assert dialog._selection_pixel_mask == edited
    assert dialog.canvas.has_active_selection()
    assert not dialog._set_quick_mask_enabled(False)

    dialog._undo()
    assert dialog._selection_pixel_mask.pixelColor(6, 4).alpha() == 255
    dialog._redo()
    assert dialog._selection_pixel_mask.pixelColor(6, 4).alpha() == 128
    assert len(dialog.canvas.embedded_strokes()) == stroke_count_before
    layer_redone = dialog._paint_layer_raster(layer.layer_id, create=False)
    assert layer_redone is not None and layer_redone == layer_before

    dialog._selection_pixel_mask = None
    dialog.canvas.select_rectangle(0.0, 0.0, 0.5, 1.0)
    dialog.canvas.set_selection_snapshot(
        dialog.canvas.selection_snapshot(),
        inverted=True,
    )
    assert dialog._set_quick_mask_enabled(True)
    assert dialog._selection_pixel_mask.pixelColor(1, 4).alpha() == 0
    assert dialog._selection_pixel_mask.pixelColor(7, 4).alpha() == 255
    saved_mask = QImage(dialog._selection_pixel_mask)
    document_path = tmp_path / "quick-mask-selection.tspaint"
    dialog.save_document_to_path(document_path)
    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(document_path)
    assert not restored._quick_mask_enabled
    assert not restored.canvas.quick_mask_enabled()
    assert restored._pen_color == QColor("#123456")
    assert restored._background_color == QColor("#ABCDEF")
    assert restored._selection_pixel_mask == saved_mask
    assert restored.canvas.has_active_selection()
    restored.close()
    assert dialog._set_quick_mask_enabled(False)
    dialog.close()
    app.processEvents()

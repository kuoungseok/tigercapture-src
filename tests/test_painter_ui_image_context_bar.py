from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _image(path, width: int = 320, height: int = 180) -> str:
    from PySide6.QtGui import QColor, QImage, QPainter

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#1E3552"))
    painter = QPainter(image)
    painter.fillRect(0, 0, width // 2, height, QColor("#E8A94D"))
    painter.end()
    assert image.save(str(path), "PNG")
    return str(path)


def test_image_context_bar_is_transient_localized_and_emits_commands() -> None:
    _app()
    from PySide6.QtWidgets import QWidget

    from app.painter_i18n import painter_text
    from app.painter_ui_image_context_bar import PainterUIImageContextBar

    parent = QWidget()
    toolbar = QWidget(parent)
    toolbar.setGeometry(200, 300, 360, 40)
    bar = PainterUIImageContextBar(parent)
    commands: list[str] = []
    bar.command_requested.connect(commands.append)
    bar.set_state(
        {
            "eligible": True,
            "object_id": "image-1",
            "image_fit": "fill",
            "original_width": 320,
            "original_height": 180,
        }
    )
    bar.place_above(toolbar)
    bar.mode_buttons["tile"].click()
    bar.focal_button.click()

    assert not bar.isHidden()
    assert bar.mode_buttons["fill"].isChecked()
    assert painter_text("Edit focal point", "ko") == "초점 위치 편집"
    assert commands == ["tile", "focal"]
    bar.set_state({})
    assert not bar.isVisible()
    bar.deleteLater()
    parent.deleteLater()


def test_canvas_image_context_reuses_fill_service_and_one_step_undo(
    tmp_path,
) -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import add_ui_object
    from app.painter_ui_image_assets import set_ui_image_fill

    source = _image(tmp_path / "wide.png")
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, row = add_ui_object(
        dialog._painter_ui_document,
        kind="image",
        name="Hero",
        x=100,
        y=80,
        width=200,
        height=200,
    )
    document, row, _report = set_ui_image_fill(
        document,
        row["id"],
        source,
        image_fit="fill",
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._refresh_painter_ui_overlay()
    bar = dialog._painter_ui_image_context_bar

    assert not bar.isHidden()
    assert bar.state()["object_id"] == row["id"]
    bar.mode_buttons["fit"].click()
    app.processEvents()
    updated = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )
    assert updated["content"]["image_fit"] == "fit"
    assert dialog._undo_labels[-1] == "Set UI image fill"
    dialog._undo()
    restored = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )
    assert restored["content"]["image_fit"] == "fill"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_replace_image_preserves_context_settings(monkeypatch, tmp_path) -> None:
    app = _app()
    from PySide6.QtWidgets import QFileDialog

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import add_ui_object
    from app.painter_ui_image_assets import set_ui_image_fill

    first = _image(tmp_path / "first.png", 400, 160)
    replacement = _image(tmp_path / "replacement.png", 240, 360)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, row = add_ui_object(
        dialog._painter_ui_document,
        kind="image",
        name="Hero",
        x=100,
        y=80,
        width=200,
        height=200,
    )
    document, row, _report = set_ui_image_fill(
        document,
        row["id"],
        first,
        image_fit="fill",
        focal_x=0.72,
        focal_y=0.31,
        tile_scale=1.75,
    )
    dialog._painter_ui_document = document
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (replacement, ""),
    )

    undo_count = len(dialog._undo_labels)
    dialog._prompt_set_painter_ui_image_fill()

    updated = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )
    content = updated["content"]
    assert content["source_path"] == replacement
    assert content["image_fit"] == "fill"
    assert content["focal_x"] == pytest.approx(0.72)
    assert content["focal_y"] == pytest.approx(0.31)
    assert content["tile_scale"] == pytest.approx(1.75)
    assert len(dialog._undo_labels) == undo_count + 1
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_canvas_focal_handle_updates_fill_and_persists(tmp_path) -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import add_ui_object
    from app.painter_ui_image_assets import set_ui_image_fill

    source = _image(tmp_path / "focal.png", 400, 160)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, row = add_ui_object(
        dialog._painter_ui_document,
        kind="image",
        name="Crop",
        x=120,
        y=90,
        width=220,
        height=220,
    )
    document, row, _report = set_ui_image_fill(
        document,
        row["id"],
        source,
        image_fit="fill",
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    overlay = dialog._painter_ui_overlay
    overlay.resize(1000, 760)
    overlay.set_document(document)
    overlay.show()
    dialog._sync_painter_ui_image_context()
    dialog._handle_painter_ui_image_context_command("focal")
    app.processEvents()

    control = overlay._image_focal_control()
    assert control is not None
    _selected, rect, focal = control
    target = QPoint(
        round(rect.left() + rect.width() * 0.8),
        round(rect.top() + rect.height() * 0.25),
    )
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=focal.toPoint(),
    )
    assert overlay._interaction == "image_focal"
    QTest.mouseMove(overlay, target)
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=target,
    )
    app.processEvents()

    updated = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )
    assert updated["content"]["focal_x"] == pytest.approx(0.8, abs=0.03)
    assert updated["content"]["focal_y"] == pytest.approx(0.25, abs=0.03)
    assert dialog._undo_labels[-1] == "Set UI image fill"
    document_path = tmp_path / "focal.tspaint"
    dialog.save_document_to_path(document_path)
    restored_dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored_dialog.open_document_from_path(document_path)
    saved = next(
        item
        for item in restored_dialog._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )
    assert saved["content"]["focal_x"] == pytest.approx(
        updated["content"]["focal_x"]
    )
    assert saved["content"]["focal_y"] == pytest.approx(
        updated["content"]["focal_y"]
    )
    restored_dialog.close()
    restored_dialog.deleteLater()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()

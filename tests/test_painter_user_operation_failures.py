from __future__ import annotations

import copy
import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_user_operations_expose_exact_failure_and_preserve_document(monkeypatch, tmp_path: Path) -> None:
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    import app.drawing as drawing
    import app.drawing_editor_object_import as editor_object_import
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.drawing_editor_object_import import PaintImportObject

    app = _app()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(96, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    initial_layers = copy.deepcopy(dialog._paint_layers)
    initial_strokes = list(dialog.canvas.embedded_strokes())
    initial_stickers = list(dialog._stickers)
    initial_brushes = copy.deepcopy(dialog._brush_user_presets)
    warnings: list[str] = []
    information: list[str] = []
    dialog_choice = {
        "open": (str(tmp_path / "input.bin"), ""),
        "save": (str(tmp_path / "output.bin"), "PNG 8-bit (*.png)"),
        "question": QMessageBox.StandardButton.No,
    }
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: dialog_choice["open"])
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_args: dialog_choice["save"])
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(str(_args[-1])))
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: information.append(str(_args[-1])))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: dialog_choice["question"])

    monkeypatch.setattr(
        drawing,
        "import_brush_bundle",
        lambda *_args: (_ for _ in ()).throw(ValueError("brush import failed exactly")),
    )
    dialog._import_custom_brush_bundle()
    assert dialog._painter_operational_errors["brush_bundle_import"] == (
        "ValueError: brush import failed exactly"
    )
    assert warnings[-1].endswith("ValueError: brush import failed exactly")
    assert dialog._brush_user_presets == initial_brushes

    monkeypatch.setattr(
        drawing,
        "export_brush_bundle",
        lambda *_args: (_ for _ in ()).throw(OSError("brush export failed exactly")),
    )
    dialog._export_custom_brush_bundle()
    assert dialog._painter_operational_errors["brush_bundle_export"] == (
        "OSError: brush export failed exactly"
    )
    assert warnings[-1].endswith("OSError: brush export failed exactly")

    png_target = tmp_path / "paint.png"
    png_target.write_bytes(b"old-png")

    def fail_png(staging_path, **_kwargs):
        Path(staging_path).write_bytes(b"partial-png")
        raise RuntimeError("PNG writer failed exactly")

    dialog_choice["save"] = (str(png_target), "PNG Image (*.png)")
    monkeypatch.setattr(drawing, "export_paint_png", fail_png)
    dialog._export_png_to_file(include_background=False)
    png_error = dialog._painter_operational_errors["png_export"]
    assert png_error.startswith("PainterExportTransactionError: file_commit failed: RuntimeError")
    assert "PNG writer failed exactly" in png_error
    assert png_target.read_bytes() == b"old-png"

    dialog_choice["open"] = (str(tmp_path / "layer.png"), "")
    monkeypatch.setattr(
        dialog,
        "import_image_as_paint_layer",
        lambda *_args: (_ for _ in ()).throw(OSError("layer import failed exactly")),
    )
    dialog._prompt_import_image_as_paint_layer()
    assert dialog._painter_operational_errors["paint_layer_image_import"] == (
        "OSError: layer import failed exactly"
    )

    dialog_choice["save"] = (str(tmp_path / "document.tspaint"), "")
    monkeypatch.setattr(
        dialog,
        "save_document_to_path",
        lambda *_args: (_ for _ in ()).throw(PermissionError("document save denied exactly")),
    )
    assert dialog._prompt_save_painter_document(save_as=True) is None
    assert dialog._painter_operational_errors["document_save"] == (
        "PermissionError: document save denied exactly"
    )

    dialog_choice["open"] = (str(tmp_path / "document.tspaint"), "")
    monkeypatch.setattr(
        dialog,
        "open_document_from_path",
        lambda *_args: (_ for _ in ()).throw(ValueError("document open invalid exactly")),
    )
    assert dialog._prompt_open_painter_document() is None
    assert dialog._painter_operational_errors["document_open"] == (
        "ValueError: document open invalid exactly"
    )

    dialog_choice["save"] = (str(tmp_path / "art.png"), "PNG 8-bit (*.png)")
    monkeypatch.setattr(
        dialog,
        "export_document_to_path",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("flat export failed exactly")),
    )
    info_before = len(information)
    dialog._prompt_export_painter_document(bit_depth=8)
    assert dialog._painter_operational_errors["document_export"] == (
        "RuntimeError: flat export failed exactly"
    )
    assert len(information) == info_before

    export_attempt = 0

    def fail_psd_exports(*_args, **kwargs):
        nonlocal export_attempt
        export_attempt += 1
        if kwargs.get("bake_unsupported"):
            raise OSError("baked PSD failed exactly")
        raise ValueError("PSD preflight blocked exactly")

    dialog_choice["save"] = (str(tmp_path / "art.psd"), "Layered PSD (*.psd)")
    dialog_choice["question"] = QMessageBox.StandardButton.Yes
    monkeypatch.setattr(dialog, "export_document_to_path", fail_psd_exports)
    dialog._prompt_export_painter_document(bit_depth=8)
    assert export_attempt == 2
    assert dialog._painter_operational_errors["document_export"] == (
        "OSError: baked PSD failed exactly"
    )
    assert warnings[-1].endswith("OSError: baked PSD failed exactly")
    assert len(information) == info_before

    dialog_choice["open"] = (str(tmp_path / "layers.psd"), "")
    monkeypatch.setattr(
        dialog,
        "import_psd_document_from_path",
        lambda *_args: (_ for _ in ()).throw(ValueError("PSD import failed exactly")),
    )
    dialog._prompt_import_layered_psd()
    assert dialog._painter_operational_errors["layered_psd_import"] == (
        "ValueError: PSD import failed exactly"
    )

    dialog._editor_object_provider = lambda: (_ for _ in ()).throw(
        RuntimeError("editor provider failed exactly")
    )
    dialog._import_editor_object()
    assert dialog._painter_operational_errors["editor_object_provider"] == (
        "RuntimeError: editor provider failed exactly"
    )
    assert warnings[-1].endswith("RuntimeError: editor provider failed exactly")

    monkeypatch.setattr(
        editor_object_import,
        "render_paint_import_object",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("poster render failed exactly")),
    )
    dialog._place_editor_object_sticker(
        PaintImportObject(id="object:1", kind="test", label="Object")
    )
    assert dialog._painter_operational_errors["editor_object_render"] == (
        "OSError: poster render failed exactly"
    )
    assert warnings[-1].endswith("OSError: poster render failed exactly")

    assert dialog._paint_layers == initial_layers
    assert dialog.canvas.embedded_strokes() == initial_strokes
    assert dialog._stickers == initial_stickers
    assert dialog._brush_user_presets == initial_brushes

    dialog.close()
    dialog.deleteLater()
    app.processEvents()

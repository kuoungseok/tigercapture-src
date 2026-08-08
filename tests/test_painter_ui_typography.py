from __future__ import annotations

import copy
import json
import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600, name="Desktop")
    document, text = add_ui_object(
        document,
        kind="text",
        name="Variable heading",
        style={
            "font_family": "Arial",
            "font_size": 32,
            "font_axes": {"wght": 625, "wdth": 88, "bad": 10, "opsz": "nan"},
        },
        content={"text": "Tiger Studio"},
    )
    return document, text


def test_font_axis_normalization_and_document_round_trip() -> None:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_typography import normalize_ui_font_axes

    assert normalize_ui_font_axes(
        {"wght": 625, "wdth": "88.5", "bad": 3, "opsz": float("inf")}
    ) == {"wdth": 88.5, "wght": 625.0}
    document, text = _document()
    normalized = normalize_ui_document(document)
    row = next(item for item in normalized["objects"] if item["id"] == text["id"])
    assert row["style"]["font_axes"] == {"wdth": 88.0, "wght": 625.0}


def test_font_axis_service_sets_and_resets_one_or_all_axes() -> None:
    from app.painter_ui_typography import (
        reset_ui_variable_font_axis,
        set_ui_variable_font_axis,
    )

    document, text = _document()
    document, row = set_ui_variable_font_axis(document, text["id"], "opsz", 24)
    assert row["style"]["font_axes"]["opsz"] == 24.0
    document, row = reset_ui_variable_font_axis(document, text["id"], "wdth")
    assert "wdth" not in row["style"]["font_axes"]
    cleared_document, row = reset_ui_variable_font_axis(document, text["id"])
    assert cleared_document["revision"] > document["revision"]
    assert "font_axes" not in row["style"]
    with pytest.raises(ValueError):
        set_ui_variable_font_axis(document, text["id"], "weight", 500)


def test_qfont_renderer_applies_named_axes() -> None:
    _app()
    from PySide6.QtGui import QFont

    from app.painter_ui_style_renderer import ui_font

    font = ui_font(
        QFont("Arial"),
        {"font_size": 18, "font_axes": {"wght": 640, "wdth": 92}},
    )
    values = {
        bytes(tag.toString()).decode("ascii"): font.variableAxisValue(tag)
        for tag in font.variableAxisTags()
    }
    assert values == {"wdth": 92.0, "wght": 640.0}


def test_inspector_edits_axes_and_action_has_one_step_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import select_ui_object

    document, text = _document()
    document = select_ui_object(document, text["id"])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._refresh_painter_ui_overlay()
    app.processEvents()

    inspector = dialog._paint_ui_inspector
    assert inspector.font_axis_checks["wght"].isChecked()
    assert inspector.font_axis_controls["wght"].value() == 625.0

    registry = ActionRegistry(owner=dialog)
    undo_count = len(dialog._undo_stack)
    result = registry.execute(
        "paint.ui.typography.variable_axis.set",
        {"object_id": text["id"], "axis": "opsz", "value": 22},
    ).to_dict()
    assert result["ok"] is True
    assert result["result"]["font_axes"]["opsz"] == 22.0
    assert len(dialog._undo_stack) == undo_count + 1
    dialog._undo()
    restored = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == text["id"]
    )
    assert "opsz" not in restored["style"]["font_axes"]
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_figma_metadata_and_umg_delivery_do_not_silently_drop_axes() -> None:
    from app.painter_ui_delivery import classify_ui_object_delivery
    from app.painter_ui_figma import _map_style, inspect_figma_compatibility
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, text = _document()
    figma_style = _map_style(
        {
            "id": "1:2",
            "type": "TEXT",
            "style": {"fontFamily": "Inter", "fontSize": 20, "fontWeight": 400},
            "sharedPluginData": {
                "tigerstudio": {"font_axes": '{"wght": 625, "wdth": 88}'}
            },
        }
    )
    assert figma_style["font_axes"] == {"wdth": 88.0, "wght": 625.0}
    compatibility = inspect_figma_compatibility(document)
    axis_row = next(
        row for row in compatibility["objects"] if row["id"].endswith(":font-axes")
    )
    assert axis_row["status"] == "converted"

    source_row = next(row for row in document["objects"] if row["id"] == text["id"])
    assert classify_ui_object_delivery(source_row, "unreal_umg")["disposition"] == "blocked"
    umg = painter_ui_to_umg_document(document)
    layer = next(row for row in umg["Layers"] if row["Id"] == text["id"])
    assert layer["Disposition"] == "Blocked"
    payload = json.loads(layer["PayloadJson"])
    assert payload["font_axes"] == {"wdth": 88.0, "wght": 625.0}
    assert "variable_font_axes_require_unavailable_text_bake" in payload[
        "umg_block_reasons"
    ]

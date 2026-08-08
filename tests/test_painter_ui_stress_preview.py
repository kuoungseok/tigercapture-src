from __future__ import annotations

import copy
import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _stress_document() -> dict:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
    )

    document = create_ui_document(width=390, height=844)
    document, frame = add_ui_object(
        document,
        kind="frame",
        name="Product Card",
        x=20,
        y=20,
        width=350,
        height=260,
    )
    document, text = add_ui_object(
        document,
        kind="text",
        name="Title",
        parent_id=frame["id"],
        x=24,
        y=24,
        width=220,
        height=48,
        style={"font_size": 16},
        content={"text": "Short title"},
    )
    document, image = add_ui_object(
        document,
        kind="image",
        name="Thumbnail",
        parent_id=frame["id"],
        x=24,
        y=88,
        width=220,
        height=120,
        content={"source_path": "existing.png"},
    )
    document["selection"] = {
        "object_id": frame["id"],
        "object_ids": [frame["id"]],
    }
    return document


@pytest.mark.parametrize(
    ("preset", "affected_kind"),
    [
        ("long_ko", "text"),
        ("long_en", "text"),
        ("large_type", "text"),
        ("missing_image", "image"),
        ("empty_list", "frame"),
    ],
)
def test_stress_presets_are_ephemeral_and_scoped(
    preset: str,
    affected_kind: str,
) -> None:
    from app.painter_ui_stress_preview import build_ui_stress_preview

    document = _stress_document()
    original = copy.deepcopy(document)
    target_id = document["selection"]["object_id"]
    preview, report = build_ui_stress_preview(
        document,
        target_id,
        preset,
    )

    assert document == original
    assert preview["revision"] == document["revision"]
    assert report["active"] is True
    assert report["preset"] == preset
    assert report["target_object_id"] == target_id
    assert report["preview_only"] is True
    assert report["affected_count"] >= 1
    if affected_kind == "text":
        text = next(row for row in preview["objects"] if row["kind"] == "text")
        if preset == "large_type":
            assert text["style"]["font_size"] > 16
        else:
            assert len(text["content"]["text"]) > 60
    elif affected_kind == "image":
        image = next(
            row for row in preview["objects"] if row["kind"] == "image"
        )
        assert "stress_missing_image" in image["content"]["source_path"]
    else:
        children = [
            row
            for row in preview["objects"]
            if row["parent_id"] == target_id
        ]
        assert children and not any(row["visible"] for row in children)


def test_stress_preview_rejects_unknown_preset_and_target() -> None:
    from app.painter_ui_stress_preview import (
        PainterUIStressPreviewError,
        build_ui_stress_preview,
    )

    document = _stress_document()
    with pytest.raises(PainterUIStressPreviewError):
        build_ui_stress_preview(document, "missing", "long_ko")
    with pytest.raises(PainterUIStressPreviewError):
        build_ui_stress_preview(document, "", "mystery")


def test_stress_preview_action_does_not_change_document_or_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _stress_document()
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._refresh_painter_ui_overlay()
    app.processEvents()
    registry = ActionRegistry(owner=dialog)
    before = copy.deepcopy(dialog._painter_ui_document)
    undo_count = len(dialog._undo_stack)

    result = registry.execute(
        "paint.ui.layout.stress_preview",
        {"preset": "long_ko"},
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["stress_preview"]["active"] is True
    assert dialog._painter_ui_document == before
    assert len(dialog._undo_stack) == undo_count
    assert (
        dialog._painter_ui_overlay._document["revision"]
        == before["revision"]
    )
    preview_text = next(
        row
        for row in dialog._painter_ui_overlay._document["objects"]
        if row["kind"] == "text"
    )
    assert len(preview_text["content"]["text"]) > 60

    cleared = registry.execute(
        "paint.ui.layout.stress_preview",
        {"preset": "none"},
    ).to_dict()
    assert cleared["ok"] is True
    assert cleared["result"]["stress_preview"]["active"] is False
    assert dialog._painter_ui_document == before
    assert len(dialog._undo_stack) == undo_count

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_inspector_stress_controls_emit_selected_stable_id() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector

    document = _stress_document()
    target_id = document["selection"]["object_id"]
    inspector = PainterUIInspector()
    requests: list[tuple[str, str]] = []
    inspector.stress_preview_requested.connect(
        lambda object_id, preset: requests.append((object_id, preset))
    )
    inspector.set_document(document)
    assert inspector.design_group_visible("content_stress")

    inspector.stress_preview_combo.setCurrentIndex(
        inspector.stress_preview_combo.findData("missing_image")
    )
    app.processEvents()
    assert requests == [(target_id, "missing_image")]

    inspector.set_stress_preview_report(
        {
            "active": True,
            "preset": "missing_image",
            "target_name": "Product Card",
            "affected_count": 1,
            "message": "Preview only",
        }
    )
    assert inspector.stress_preview_clear_button.isEnabled()
    assert "Product Card" in inspector.stress_preview_status_label.text()

    inspector.stress_preview_clear_button.click()
    app.processEvents()
    assert requests[-1] == (target_id, "none")
    inspector.deleteLater()
    app.processEvents()

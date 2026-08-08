from __future__ import annotations

import os


def _document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844)
    document, row = add_ui_object(
        document,
        kind="button",
        x=24,
        y=40,
        width=180,
        height=48,
        name="Continue",
    )
    return document, row


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_dev_handoff_ready_annotation_inspect_and_round_trip() -> None:
    from app.painter_ui_dev_handoff import (
        DEV_HANDOFF_SCHEMA,
        DEV_INSPECT_SCHEMA,
        add_ui_dev_annotation,
        inspect_ui_dev_handoff,
        remove_ui_dev_annotation,
        set_ui_dev_ready,
    )
    from app.painter_ui_document import normalize_ui_document

    document, row = _document()
    document, ready = set_ui_dev_ready(
        document,
        target_type="object",
        target_id=row["id"],
        ready=True,
        note="Keyboard behavior verified",
    )
    assert ready["ready"] is True
    document, annotation = add_ui_dev_annotation(
        document,
        target_type="object",
        target_id=row["id"],
        text="Export at 2x",
    )
    restored = normalize_ui_document(document)
    contract = restored["linked_targets"]["dev_handoff"]
    assert contract["schema"] == DEV_HANDOFF_SCHEMA
    report = inspect_ui_dev_handoff(restored, object_ids=[row["id"]])
    assert report["schema"] == DEV_INSPECT_SCHEMA
    assert report["objects"][0]["ready"]["ready"] is True
    assert report["annotations"][0]["text"] == "Export at 2x"
    assert report["objects"][0]["delivery"]
    assert report["measurements"]["eligible"] is True
    removed = remove_ui_dev_annotation(restored, annotation["id"])
    assert not removed["linked_targets"]["dev_handoff"]["annotations"]


def test_dev_panel_empty_and_requests() -> None:
    _app()
    from app.painter_ui_dev_handoff import (
        add_ui_dev_annotation,
        inspect_ui_dev_handoff,
    )
    from app.painter_ui_dev_panel import PainterUIDevPanel

    document, row = _document()
    document, annotation = add_ui_dev_annotation(
        document,
        target_type="object",
        target_id=row["id"],
        text="Keep baseline",
        kind="measurement",
    )
    panel = PainterUIDevPanel()
    panel.set_report(inspect_ui_dev_handoff(document, object_ids=[row["id"]]))
    ready_requests = []
    annotation_requests = []
    update_requests = []
    remove_requests = []
    panel.ready_set_requested.connect(lambda *args: ready_requests.append(args))
    panel.annotation_add_requested.connect(
        lambda *args: annotation_requests.append(args)
    )
    panel.annotation_update_requested.connect(
        lambda *args: update_requests.append(args)
    )
    panel.annotation_remove_requested.connect(remove_requests.append)
    panel.ready_check.setChecked(True)
    panel.ready_note.setText("Ready")
    panel.ready_button.click()
    panel.annotation_edit.setText("Spacing is intentional")
    panel.annotation_button.click()
    assert ready_requests == [("object", row["id"], True, "Ready")]
    assert annotation_requests == [
        ("object", row["id"], "Spacing is intentional", "note")
    ]
    panel.annotation_list.setCurrentRow(0)
    panel.annotation_edit.setText("Keep 16 px baseline")
    panel.annotation_update_button.click()
    panel.annotation_remove_button.click()
    assert update_requests == [
        (
            annotation["id"],
            {"text": "Keep 16 px baseline", "kind": "measurement"},
        )
    ]
    assert remove_requests == [annotation["id"]]
    panel.set_report(None)
    assert not panel.ready_button.isEnabled()


def test_measurement_annotation_is_exported_as_overlay(tmp_path) -> None:
    import json

    from app.painter_ui_dev_handoff import (
        add_ui_dev_annotation,
        inspect_ui_dev_handoff,
    )
    from app.painter_ui_review import export_ui_review_package

    document, row = _document()
    document, annotation = add_ui_dev_annotation(
        document,
        target_type="object",
        target_id=row["id"],
        text="Preserve button bounds",
        kind="measurement",
    )
    report = inspect_ui_dev_handoff(document, object_ids=[row["id"]])
    assert report["measurement_overlays"][0]["annotation_id"] == annotation["id"]
    assert report["measurement_overlays"][0]["measurement"]["eligible"] is True

    package = export_ui_review_package(document, tmp_path / "review")
    handoff_path = tmp_path / "review" / "dev_handoff.json"
    assert handoff_path.is_file()
    exported = json.loads(handoff_path.read_text(encoding="utf-8"))
    assert exported["measurement_overlays"][0]["target_id"] == row["id"]
    assert "dev_handoff.json" in package["manifest"]["artifacts"]


def test_dev_annotation_panel_mutations_share_undo_and_document() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_dev_handoff import (
        add_ui_dev_annotation,
        inspect_ui_dev_handoff,
    )

    document, row = _document()
    document, annotation = add_ui_dev_annotation(
        document,
        target_type="object",
        target_id=row["id"],
        text="Original",
    )
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    panel = dialog._paint_ui_inspector.dev_panel
    panel.set_report(inspect_ui_dev_handoff(document, object_ids=[row["id"]]))
    undo_before = len(dialog._undo_stack)
    panel.annotation_list.setCurrentRow(0)
    panel.annotation_edit.setText("Updated")
    panel.annotation_update_button.click()
    contract = dialog._painter_ui_document["linked_targets"]["dev_handoff"]
    assert contract["annotations"][0]["text"] == "Updated"
    assert len(dialog._undo_stack) == undo_before + 1

    panel.set_report(
        inspect_ui_dev_handoff(
            dialog._painter_ui_document,
            object_ids=[row["id"]],
        )
    )
    panel.annotation_list.setCurrentRow(0)
    panel.annotation_remove_button.click()
    assert not dialog._painter_ui_document["linked_targets"]["dev_handoff"][
        "annotations"
    ]
    assert len(dialog._undo_stack) == undo_before + 2
    dialog.close()
    app.processEvents()


def test_dev_actions_share_document_and_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, row = _document()
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    registry = ActionRegistry(owner=dialog)
    action_ids = {item["id"] for item in registry.list_actions()}
    assert {
        "paint.ui.dev.ready.set",
        "paint.ui.dev.inspect",
        "paint.ui.dev.snippet.inspect",
        "paint.ui.dev.annotation.add",
        "paint.ui.dev.annotation.update",
        "paint.ui.dev.annotation.remove",
        "paint.ui.dev.revision.compare",
        "paint.ui.delivery.feature.inspect",
        "paint.ui.delivery.artifact.open",
    }.issubset(action_ids)
    ready = registry.execute(
        "paint.ui.dev.ready.set",
        {
            "target_type": "object",
            "target_id": row["id"],
            "ready": True,
            "note": "Ready",
        },
    ).to_dict()
    assert ready["ok"] is True
    report = registry.execute(
        "paint.ui.dev.inspect",
        {"object_ids": [row["id"]]},
    ).to_dict()
    assert report["ok"] is True
    assert report["result"]["objects"][0]["ready"]["ready"] is True
    assert dialog._undo_stack
    dialog.close()
    app.processEvents()

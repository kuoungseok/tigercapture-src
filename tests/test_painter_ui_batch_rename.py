from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document() -> tuple[dict, list[str]]:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_objects,
    )

    document = create_ui_document(800, 600)
    ids = []
    for index, name in enumerate(("Card", "Card", "Footer")):
        document, row = add_ui_object(
            document,
            kind="group",
            name=name,
            x=40 + index * 180,
            y=100,
        )
        ids.append(row["id"])
    document = select_ui_objects(
        document,
        ids,
        primary_object_id=ids[0],
    )
    return document, ids


def test_batch_rename_previews_prefix_replace_suffix_and_numbering() -> None:
    from app.painter_ui_batch_rename import inspect_ui_batch_rename

    document, ids = _document()
    report = inspect_ui_batch_rename(
        document,
        find="Card",
        replacement="Tile",
        prefix="UI_",
        suffix="_Ready",
        numbering=True,
        number_start=7,
        number_padding=2,
        number_separator="_",
    )
    assert report["object_ids"] == ids
    assert [row["proposed"] for row in report["matches"]] == [
        "UI_Tile_Ready_07",
        "UI_Tile_Ready_08",
        "UI_Footer_Ready_09",
    ]


def test_batch_rename_apply_is_selective_immutable_and_one_revision() -> None:
    from app.painter_ui_batch_rename import (
        apply_ui_batch_rename,
        inspect_ui_batch_rename,
    )

    document, ids = _document()
    before = copy.deepcopy(document)
    preview = inspect_ui_batch_rename(document, prefix="UI_")
    selected = preview["matches"][1]
    updated, report = apply_ui_batch_rename(
        document,
        prefix="UI_",
        selected_match_ids=[selected["match_id"]],
    )
    assert document == before
    assert updated["revision"] == before["revision"] + 1
    names = {row["id"]: row["name"] for row in updated["objects"]}
    assert names[ids[0]] == "Card"
    assert names[ids[1]] == "UI_Card"
    assert names[ids[2]] == "Footer"
    assert report["applied_count"] == 1


def test_batch_rename_rejects_missing_object() -> None:
    import pytest

    from app.painter_ui_batch_rename import inspect_ui_batch_rename

    document, _ids = _document()
    with pytest.raises(ValueError, match="not found"):
        inspect_ui_batch_rename(document, object_ids=["missing"], prefix="UI_")


def test_batch_rename_noop_does_not_create_matches() -> None:
    from app.painter_ui_batch_rename import inspect_ui_batch_rename

    document, _ids = _document()
    report = inspect_ui_batch_rename(document)
    assert report["match_count"] == 0


def test_batch_rename_action_is_one_undoable_document_change() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, ids = _document()
    dialog._painter_ui_document = document
    dialog._painter_document_dirty = False
    undo_count = len(dialog._undo_stack)
    registry = ActionRegistry(owner=dialog)
    inspected = registry.execute(
        "paint.ui.batch_rename.inspect",
        {"object_ids": ids, "prefix": "UI_"},
    ).to_dict()
    assert inspected["ok"] is True
    selected = inspected["result"]["matches"][:2]
    applied = registry.execute(
        "paint.ui.batch_rename.apply",
        {
            "object_ids": ids,
            "prefix": "UI_",
            "selected_match_ids": [
                row["match_id"] for row in selected
            ],
        },
    ).to_dict()
    assert applied["ok"] is True
    assert applied["result"]["batch_rename"]["applied_count"] == 2
    names = {
        row["id"]: row["name"]
        for row in dialog._painter_ui_document["objects"]
    }
    assert names[ids[0]] == "UI_Card"
    assert names[ids[1]] == "UI_Card"
    assert names[ids[2]] == "Footer"
    assert len(dialog._undo_stack) == undo_count + 1
    dialog._undo()
    restored = {
        row["id"]: row["name"]
        for row in dialog._painter_ui_document["objects"]
    }
    assert restored[ids[0]] == "Card"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_quick_actions_exposes_batch_rename_for_selection() -> None:
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    document, _ids = _document()
    report = search_painter_ui_quick_actions(document, "batch rename")
    row = next(
        item
        for item in report["results"]
        if item["id"] == "selection.batch_rename"
    )
    assert row["enabled"] is True
    assert row["operation"] == {"type": "batch_rename"}

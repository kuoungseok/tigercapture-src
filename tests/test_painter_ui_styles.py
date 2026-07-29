from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_named_style_crud_propagates_and_unlink_preserves_values() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        validate_ui_document,
    )
    from app.painter_ui_styles import (
        add_ui_style,
        apply_ui_style,
        remove_ui_style,
        unlink_ui_style,
        update_ui_style,
    )

    document, obj = add_ui_object(
        create_ui_document(),
        kind="button",
        style={"fill": "#101820", "radius": 8},
    )
    document, style = add_ui_style(
        document,
        name="Brand Surface",
        kind="color",
        properties={"fill": "#2F6FED"},
    )
    document, applied = apply_ui_style(
        document,
        target_id=obj["id"],
        style_id=style["id"],
    )
    assert applied["style_ids"]["color"] == style["id"]
    assert applied["style"]["fill"] == "#2F6FED"

    document, _style = update_ui_style(
        document,
        style["id"],
        {"properties": {"fill": "#41A6FF"}},
    )
    linked = document["objects"][0]
    assert linked["style"]["fill"] == "#41A6FF"
    assert linked["style"]["radius"] == 8

    document, detached = unlink_ui_style(
        document,
        target_id=obj["id"],
        kind="color",
    )
    assert detached["detached_style_id"] == style["id"]
    assert document["objects"][0]["style"]["fill"] == "#41A6FF"
    assert document["objects"][0]["style_ids"] == {}

    document, removed = remove_ui_style(document, style["id"])
    assert removed["detached_object_ids"] == []
    assert validate_ui_document(document)["ok"] is True


def test_style_token_reference_blocks_delete_and_detaches_explicitly() -> None:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        add_ui_token,
        create_ui_document,
        remove_ui_token,
        validate_ui_document,
    )
    from app.painter_ui_styles import add_ui_style

    document, token = add_ui_token(
        create_ui_document(),
        name="Brand",
        kind="color",
        token_value="#3B82F6",
        scope=["style.fill"],
    )
    document, style = add_ui_style(
        document,
        name="Brand Fill",
        kind="color",
        properties={"fill": "#3B82F6"},
        token_bindings={"style.fill": token["id"]},
    )
    with pytest.raises(PainterUIDocumentError, match="referenced"):
        remove_ui_token(document, token["id"])

    document, report = remove_ui_token(
        document,
        token["id"],
        detach_references=True,
    )
    assert report["detached_style_ids"] == [style["id"]]
    assert document["styles"][0]["token_bindings"] == {}
    assert validate_ui_document(document)["ok"] is True


def test_unified_style_library_includes_existing_layout_grid_styles() -> None:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_styles import (
        add_ui_style,
        apply_ui_style,
        inspect_ui_style_library,
        update_ui_style,
    )

    document, style = add_ui_style(
        create_ui_document(),
        name="Desktop Columns",
        kind="layout_grid",
        properties={"layout_grids": [{"mode": "columns", "count": 12}]},
    )
    document, _artboard = apply_ui_style(
        document,
        target_id="artboard-1",
        style_id=style["id"],
    )
    document, _style = update_ui_style(
        document,
        style["id"],
        {
            "name": "Compact Columns",
            "properties": {
                "layout_grids": [{"mode": "columns", "count": 6}]
            },
        },
    )
    report = inspect_ui_style_library(document)
    assert report["style_count"] == 1
    assert report["styles"][0]["kind"] == "layout_grid"
    assert report["styles"][0]["usage_count"] == 1
    assert document["artboards"][0]["layout_grids"][0]["count"] == 6


def test_style_library_widget_captures_selection_and_emits_apply() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_style_library import PainterUIStyleLibrary
    from app.painter_ui_styles import add_ui_style

    document, obj = add_ui_object(
        create_ui_document(),
        kind="button",
        style={"fill": "#345A7A"},
    )
    document["selection"] = {
        "object_id": obj["id"],
        "object_ids": [obj["id"]],
    }
    document, style = add_ui_style(
        document,
        name="Steel",
        kind="color",
        properties={"fill": "#345A7A"},
    )
    panel = PainterUIStyleLibrary()
    panel.set_document(document)
    emitted: list[tuple[str, str]] = []
    panel.style_apply_requested.connect(
        lambda style_id, target_id: emitted.append((style_id, target_id))
    )
    panel.apply_button.click()
    app.processEvents()
    assert emitted == [(style["id"], obj["id"])]
    assert panel.tree.topLevelItemCount() == 1
    panel.close()
    panel.deleteLater()
    app.processEvents()


def test_style_actions_share_document_mutation_and_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    object_id = registry.execute(
        "paint.ui.object.add",
        {
            "kind": "button",
            "name": "Styled Button",
            "style": {"fill": "#202A36"},
        },
    ).to_dict()["result"]["ui_design"]["selected_object_id"]
    added = registry.execute(
        "paint.ui.style.add",
        {
            "name": "Accent",
            "kind": "color",
            "properties": {"fill": "#55AACC"},
        },
    ).to_dict()
    assert added["ok"] is True
    style_id = added["result"]["style"]["id"]

    applied = registry.execute(
        "paint.ui.style.apply",
        {"style_id": style_id, "target_id": object_id},
    ).to_dict()
    assert applied["ok"] is True
    assert applied["result"]["target"]["style_ids"]["color"] == style_id

    inspected = registry.execute(
        "paint.ui.style.library.inspect",
        {},
    ).to_dict()
    assert inspected["ok"] is True
    assert inspected["result"]["styles"][0]["usage_count"] == 1
    dialog.close()
    dialog.deleteLater()
    app.processEvents()

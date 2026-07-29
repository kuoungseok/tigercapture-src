from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document() -> tuple[dict, dict[str, str]]:
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_token,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_components import convert_ui_object_to_component
    from app.painter_ui_styles import add_ui_style

    document = create_ui_document(800, 600)
    document, primary_root = add_ui_object(
        document,
        kind="button",
        name="Primary Root",
        content={"text": "Buy Product"},
    )
    document, secondary_root = add_ui_object(
        document,
        kind="button",
        name="Secondary Root",
        content={"text": "Secondary"},
    )
    document, primary_component = convert_ui_object_to_component(
        document,
        name="Primary Button",
        root_object_id=primary_root["id"],
    )
    document, secondary_component = convert_ui_object_to_component(
        document,
        name="Secondary Button",
        root_object_id=secondary_root["id"],
    )
    document, primary_style = add_ui_style(
        document,
        name="Primary Text",
        kind="text",
        properties={"font_family": "Inter UI", "font_size": 16},
    )
    document, secondary_style = add_ui_style(
        document,
        name="Secondary Text",
        kind="text",
        properties={"font_family": "Noto Sans", "font_size": 16},
    )
    document, primary_token = add_ui_token(
        document,
        name="Primary Accent",
        token_value="#34506F",
    )
    document, secondary_token = add_ui_token(
        document,
        name="Secondary Accent",
        token_value="#476A8D",
    )
    document, object_row = add_ui_object(
        document,
        kind="text",
        name="Product CTA",
        x=40,
        y=200,
        style={"font_family": "Inter UI", "font_size": 16},
        content={
            "text": "Buy Product now",
            "source_path": "assets/product/hero.png",
        },
    )
    document, object_row = update_ui_object(
        document,
        object_row["id"],
        {
            "style_ids": {"text": primary_style["id"]},
            "token_bindings": {"style.text_color": primary_token["id"]},
        },
    )
    return document, {
        "object": object_row["id"],
        "primary_component": primary_component["id"],
        "secondary_component": secondary_component["id"],
        "primary_style": primary_style["id"],
        "secondary_style": secondary_style["id"],
        "primary_token": primary_token["id"],
        "secondary_token": secondary_token["id"],
    }


def test_find_replace_previews_text_font_asset_names_and_references() -> None:
    from app.painter_ui_find_replace import inspect_ui_find_replace

    document, ids = _document()
    text = inspect_ui_find_replace(
        document,
        find="Product",
        replacement="Library",
        categories=["text", "asset"],
    )
    assert text["match_count"] == 3
    target_matches = [
        row for row in text["matches"] if row["target_id"] == ids["object"]
    ]
    assert {row["path"] for row in target_matches} == {
        "content.text",
        "content.source_path",
    }

    font = inspect_ui_find_replace(
        document,
        find="Inter UI",
        replacement="Noto Sans",
        categories=["font"],
        whole_value=True,
    )
    assert font["match_count"] == 2
    assert font["invalid_match_count"] == 0

    style = inspect_ui_find_replace(
        document,
        find="Primary Text",
        replacement="Secondary Text",
        categories=["style"],
    )
    reference = next(
        row for row in style["matches"] if row["target_type"] == "object"
    )
    assert reference["proposed_value"] == ids["secondary_style"]

    variable = inspect_ui_find_replace(
        document,
        find="Primary Accent",
        replacement="Secondary Accent",
        categories=["variable"],
    )
    reference = next(
        row for row in variable["matches"] if row["target_type"] == "object"
    )
    assert reference["proposed_value"] == ids["secondary_token"]


def test_find_replace_blocks_unsafe_component_reference_swap() -> None:
    from app.painter_ui_components import instantiate_ui_component
    from app.painter_ui_find_replace import inspect_ui_find_replace

    document, ids = _document()
    document, instance = instantiate_ui_component(
        document,
        component_id=ids["primary_component"],
        x=300,
        y=200,
    )
    report = inspect_ui_find_replace(
        document,
        find="Primary Button",
        replacement="Secondary Button",
        categories=["component"],
    )
    reference = next(
        row
        for row in report["matches"]
        if row["target_id"] == instance["root_object_id"]
    )
    assert reference["valid"] is False
    assert "Instance Swap" in reference["reason"]
    assert report["invalid_match_count"] == 1


def test_find_replace_applies_only_selected_valid_matches_in_one_revision() -> None:
    from app.painter_ui_find_replace import (
        apply_ui_find_replace,
        inspect_ui_find_replace,
    )

    document, ids = _document()
    before = copy.deepcopy(document)
    preview = inspect_ui_find_replace(
        document,
        find="Product",
        replacement="Library",
        categories=["text", "asset"],
    )
    text_match = next(
        row
        for row in preview["matches"]
        if row["target_id"] == ids["object"] and row["path"] == "content.text"
    )
    updated, report = apply_ui_find_replace(
        document,
        find="Product",
        replacement="Library",
        categories=["text", "asset"],
        selected_match_ids=[text_match["match_id"]],
    )

    assert document == before
    assert updated["revision"] == before["revision"] + 1
    changed = next(row for row in updated["objects"] if row["id"] == ids["object"])
    assert changed["content"]["text"] == "Buy Library now"
    assert changed["content"]["source_path"] == "assets/product/hero.png"
    assert report["applied_match_ids"] == [text_match["match_id"]]


def test_find_replace_rejects_invalid_selected_reference() -> None:
    import pytest

    from app.painter_ui_find_replace import (
        apply_ui_find_replace,
        inspect_ui_find_replace,
    )

    document, _ids = _document()
    preview = inspect_ui_find_replace(
        document,
        find="Primary Text",
        replacement="Missing Style",
        categories=["style"],
    )
    invalid = next(row for row in preview["matches"] if not row["valid"])
    with pytest.raises(ValueError, match="invalid"):
        apply_ui_find_replace(
            document,
            find="Primary Text",
            replacement="Missing Style",
            categories=["style"],
            selected_match_ids=[invalid["match_id"]],
        )


def test_find_replace_action_uses_shared_service_and_one_undo_step() -> None:
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
        "paint.ui.find_replace.inspect",
        {
            "find": "Product",
            "replacement": "Library",
            "categories": ["text"],
        },
    ).to_dict()
    assert inspected["ok"] is True
    target_match = next(
        row
        for row in inspected["result"]["matches"]
        if row["target_id"] == ids["object"]
    )
    applied = registry.execute(
        "paint.ui.find_replace.apply",
        {
            "find": "Product",
            "replacement": "Library",
            "categories": ["text"],
            "selected_match_ids": [target_match["match_id"]],
        },
    ).to_dict()
    assert applied["ok"] is True
    assert applied["result"]["find_replace"]["applied_count"] == 1
    changed = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == ids["object"]
    )
    assert changed["content"]["text"] == "Buy Library now"
    assert dialog._painter_document_dirty is True
    assert len(dialog._undo_stack) == undo_count + 1

    dialog._undo()
    restored = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == ids["object"]
    )
    assert restored["content"]["text"] == "Buy Product now"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_quick_actions_exposes_find_replace_on_demand() -> None:
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    document, _ids = _document()
    report = search_painter_ui_quick_actions(document, "find replace")
    row = next(
        item
        for item in report["results"]
        if item["id"] == "document.find_replace"
    )
    assert row["operation"] == {"type": "find_replace"}
    assert row["enabled"] is True

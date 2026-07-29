from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_variable_collections_migrate_legacy_theme_tokens_and_artboards() -> None:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_variables import (
        LEGACY_THEME_COLLECTION_ID,
        LEGACY_THEME_MODE_IDS,
    )

    document = normalize_ui_document(
        {
            "version": 19,
            "artboards": [
                {
                    "id": "artboard-legacy",
                    "width": 390,
                    "height": 844,
                    "theme": "dark",
                }
            ],
            "tokens": [
                {
                    "id": "brand",
                    "kind": "color",
                    "value": "#FFFFFF",
                    "theme_values": {"dark": "#111111"},
                }
            ],
        }
    )
    assert document["version"] == 21
    assert document["variable_collections"][0]["id"] == LEGACY_THEME_COLLECTION_ID
    assert (
        document["artboards"][0]["variable_modes"][LEGACY_THEME_COLLECTION_ID]
        == LEGACY_THEME_MODE_IDS["dark"]
    )
    token = document["tokens"][0]
    assert token["collection_id"] == LEGACY_THEME_COLLECTION_ID
    assert token["variable_type"] == "color"
    assert token["mode_values"][LEGACY_THEME_MODE_IDS["dark"]] == "#111111"


def test_variable_collection_mode_crud_resolves_bound_mode_values() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_token,
        create_ui_document,
        update_ui_object,
        validate_ui_document,
    )
    from app.painter_ui_themes import resolve_ui_theme_document
    from app.painter_ui_variables import (
        add_ui_variable_collection,
        add_ui_variable_mode,
        remove_ui_variable_mode,
        set_ui_variable_mode,
        update_ui_variable_collection,
        update_ui_variable_mode,
    )

    document = create_ui_document(390, 844)
    document, collection = add_ui_variable_collection(
        document,
        name="Density",
        kind="density",
    )
    default_mode_id = collection["default_mode_id"]
    document, compact = add_ui_variable_mode(
        document,
        collection_id=collection["id"],
        name="Compact",
    )
    document, compact = update_ui_variable_mode(
        document,
        collection_id=collection["id"],
        mode_id=compact["id"],
        name="Compact UI",
    )
    document, collection = update_ui_variable_collection(
        document,
        collection["id"],
        {"name": "Interface Density"},
    )
    document, token = add_ui_token(
        document,
        name="Control Radius",
        kind="radius",
        token_value=12,
        collection_id=collection["id"],
        variable_type="number",
        mode_values={compact["id"]: 6},
    )
    document, obj = add_ui_object(
        document,
        kind="button",
        style={"radius": 12},
    )
    document, _obj = update_ui_object(
        document,
        obj["id"],
        {"token_bindings": {"style.radius": token["id"]}},
    )
    document, _report = set_ui_variable_mode(
        document,
        artboard_id=document["active_artboard_id"],
        collection_id=collection["id"],
        mode_id=compact["id"],
    )
    resolved = resolve_ui_theme_document(document)
    assert resolved["objects"][0]["style"]["radius"] == 6
    assert validate_ui_document(document)["ok"] is True

    with pytest.raises(ValueError, match="referenced"):
        remove_ui_variable_mode(
            document,
            collection_id=collection["id"],
            mode_id=compact["id"],
        )
    document, report = remove_ui_variable_mode(
        document,
        collection_id=collection["id"],
        mode_id=compact["id"],
        detach_values=True,
    )
    assert report["fallback_mode_id"] == default_mode_id
    assert document["tokens"][-1]["mode_values"] == {}


def test_variable_validation_rejects_wrong_number_and_binding_scope() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        normalize_ui_document,
        validate_ui_document,
    )

    document = create_ui_document()
    document["tokens"] = [
        {
            "id": "gap",
            "name": "Gap",
            "kind": "spacing",
            "value": "large",
            "variable_type": "number",
            "scope": ["layout.gap"],
        }
    ]
    document = normalize_ui_document(document)
    document, obj = add_ui_object(document, kind="button")
    document["objects"][0]["token_bindings"] = {"style.fill": "gap"}
    report = validate_ui_document(document)
    assert "token_value_type_mismatch:gap" in report["errors"]
    assert (
        f"token_scope_mismatch:{obj['id']}:style.fill:gap"
        in report["errors"]
    )


def test_token_library_filters_collection_and_edits_only_active_mode() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_token, create_ui_document
    from app.painter_ui_token_library import PainterUITokenLibrary
    from app.painter_ui_variables import (
        add_ui_variable_collection,
        add_ui_variable_mode,
    )

    document = create_ui_document()
    document, collection = add_ui_variable_collection(
        document,
        name="Density",
        kind="density",
    )
    document, compact = add_ui_variable_mode(
        document,
        collection_id=collection["id"],
        name="Compact",
    )
    document, token = add_ui_token(
        document,
        name="Gap",
        kind="spacing",
        token_value=12,
        collection_id=collection["id"],
        mode_values={compact["id"]: 8},
    )

    panel = PainterUITokenLibrary()
    panel.set_document(document)
    panel.collection_combo.setCurrentIndex(
        panel.collection_combo.findData(collection["id"])
    )
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(compact["id"]))
    assert panel.tree.topLevelItemCount() == 1
    item = panel.tree.topLevelItem(0).child(0)
    assert item.data(0, 256) == token["id"]
    panel.tree.setCurrentItem(item)
    assert panel.mode_value_edit.text() == "8"

    updates: list[tuple[str, dict[str, object]]] = []
    panel.token_update_requested.connect(
        lambda token_id, changes: updates.append((token_id, dict(changes)))
    )
    panel.mode_value_edit.setText("6")
    panel.scope_edit.setText("layout.gap")
    panel.apply_button.click()
    assert updates[-1][0] == token["id"]
    assert updates[-1][1]["mode_values"][compact["id"]] == 6
    assert updates[-1][1]["collection_id"] == collection["id"]
    assert updates[-1][1]["scope"] == ["layout.gap"]

    panel.deleteLater()
    app.processEvents()


def test_variable_collection_actions_share_document_mutation_contract() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    added = registry.execute(
        "paint.ui.variable.collection.add",
        {"name": "Density", "kind": "density"},
    ).to_dict()
    assert added["ok"] is True
    collection = added["result"]["variable_collection"]
    mode = registry.execute(
        "paint.ui.variable.mode.add",
        {"collection_id": collection["id"], "name": "Compact"},
    ).to_dict()
    assert mode["ok"] is True
    mode_id = mode["result"]["variable_mode"]["id"]
    selected = registry.execute(
        "paint.ui.variable.mode.set",
        {
            "collection_id": collection["id"],
            "mode_id": mode_id,
        },
    ).to_dict()
    assert selected["ok"] is True
    inspected = registry.execute(
        "paint.ui.variable.collection.inspect",
        {},
    ).to_dict()
    row = next(
        item
        for item in inspected["result"]["collections"]
        if item["id"] == collection["id"]
    )
    assert row["active_mode_id"] == mode_id
    dialog.close()
    dialog.deleteLater()
    app.processEvents()

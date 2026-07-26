from __future__ import annotations

import os
import json


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _token_document():
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_token,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(390, 844)
    document, obj = add_ui_object(
        document,
        kind="button",
        name="Continue",
        style={"fill": "#000000"},
    )
    document, primary = add_ui_token(
        document,
        name="Brand Primary",
        kind="color",
        token_value="#4267E8",
        theme_values={"dark": "#7895FF"},
    )
    document, alias = add_ui_token(
        document,
        name="Action Fill",
        kind="color",
        alias_token_id=primary["id"],
    )
    document, unused = add_ui_token(
        document,
        name="Spacing Large",
        kind="spacing",
        token_value=24,
    )
    document, _obj = update_ui_object(
        document,
        obj["id"],
        {"token_bindings": {"style.fill": alias["id"]}},
    )
    return document, obj, primary, alias, unused


def test_token_library_report_tracks_bindings_aliases_and_unused_tokens() -> None:
    from app.painter_ui_token_library import inspect_ui_token_library

    document, obj, primary, alias, unused = _token_document()
    report = inspect_ui_token_library(document)
    assert report["token_count"] == 3
    assert report["used_count"] == 2
    assert report["unused_count"] == 1
    rows = {row["id"]: row for row in report["tokens"]}
    assert rows[primary["id"]]["alias_reference_ids"] == [alias["id"]]
    assert rows[alias["id"]]["bindings"] == [
        {
            "object_id": obj["id"],
            "object_name": "Continue",
            "path": "style.fill",
        }
    ]
    assert rows[unused["id"]]["unused"] is True


def test_token_library_widget_edits_and_binds_stable_token_ids() -> None:
    app = _app()
    from app.painter_ui_token_library import PainterUITokenLibrary

    document, obj, primary, _alias, _unused = _token_document()
    library = PainterUITokenLibrary()
    library.set_document(document)

    updates: list[tuple[str, dict[str, object]]] = []
    bindings: list[tuple[str, str, str]] = []
    imports: list[str] = []
    exports: list[bool] = []
    library.token_update_requested.connect(
        lambda token_id, changes: updates.append((token_id, dict(changes)))
    )
    library.token_binding_requested.connect(
        lambda *args: bindings.append(args)
    )
    library.token_import_requested.connect(imports.append)
    library.token_export_requested.connect(lambda: exports.append(True))

    selected = None
    for index in range(library.tree.topLevelItemCount()):
        root = library.tree.topLevelItem(index)
        for child_index in range(root.childCount()):
            child = root.child(child_index)
            if child.data(0, 256) == primary["id"]:
                selected = child
    assert selected is not None
    library.tree.setCurrentItem(selected)
    library.name_edit.setText("Brand Accent")
    library.theme_edits["high_contrast"].setText("#FFFFFF")
    library.apply_button.click()
    assert updates[-1][0] == primary["id"]
    assert updates[-1][1]["name"] == "Brand Accent"
    assert updates[-1][1]["theme_values"]["high_contrast"] == "#FFFFFF"

    library.binding_path_combo.setCurrentText("style.stroke")
    library.bind_button.click()
    assert bindings[-1] == (obj["id"], "style.stroke", primary["id"])
    library.unbind_button.click()
    assert bindings[-1] == (obj["id"], "style.stroke", "")
    library.conflict_policy_combo.setCurrentIndex(2)
    library.import_button.click()
    library.export_button.click()
    assert imports == ["regenerate"]
    assert exports == [True]

    library.search_edit.setText("missing")
    assert library.tree.topLevelItemCount() == 0
    library.search_edit.setText("spacing")
    assert library.tree.topLevelItemCount() == 1
    library.deleteLater()
    app.processEvents()


def test_token_library_json_round_trip_and_conflict_policies(tmp_path) -> None:
    from app.painter_ui_token_io import (
        export_ui_token_library,
        import_ui_token_library,
    )

    document, _obj, primary, alias, _unused = _token_document()
    path = tmp_path / "tokens.json"
    exported = export_ui_token_library(document, path)
    assert exported["ok"] is True
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "tigerstudio.painter.ui.token_library.v1"
    assert payload["tokens"][1]["alias_token_id"] == primary["id"]

    empty = {**document, "tokens": [], "objects": []}
    imported, report = import_ui_token_library(empty, path)
    assert report["added_ids"] == [
        primary["id"],
        alias["id"],
        "ui-token-3",
    ]
    imported_alias = next(
        row for row in imported["tokens"] if row["id"] == alias["id"]
    )
    assert imported_alias["alias_token_id"] == primary["id"]

    regenerated, report = import_ui_token_library(
        document,
        path,
        conflict_policy="regenerate",
    )
    assert len(regenerated["tokens"]) == 6
    assert report["id_map"][primary["id"]] != primary["id"]
    regenerated_alias = next(
        row
        for row in regenerated["tokens"]
        if row["id"] == report["id_map"][alias["id"]]
    )
    assert (
        regenerated_alias["alias_token_id"]
        == report["id_map"][primary["id"]]
    )


def test_token_library_actions_inspect_bind_unbind_and_transfer(
    tmp_path,
) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, obj, primary, _alias, _unused = _token_document()
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)

    inspected = registry.execute("paint.ui.token.library.inspect", {}).to_dict()
    assert inspected["ok"] is True
    assert inspected["changed"] is False
    assert inspected["result"]["token_count"] == 3

    path = tmp_path / "tokens.json"
    exported = registry.execute(
        "paint.ui.token.library.export",
        {"path": str(path)},
    ).to_dict()
    assert exported["ok"] is True
    assert exported["changed"] is False
    assert path.exists()

    bound = registry.execute(
        "paint.ui.token.bind",
        {
            "object_id": obj["id"],
            "path": "style.stroke",
            "token_id": primary["id"],
        },
    ).to_dict()
    assert bound["ok"] is True
    bindings = bound["result"]["ui_design"]["document"]["objects"][0][
        "token_bindings"
    ]
    assert bindings["style.stroke"] == primary["id"]

    unbound = registry.execute(
        "paint.ui.token.unbind",
        {"object_id": obj["id"], "path": "style.stroke"},
    ).to_dict()
    assert unbound["ok"] is True
    bindings = unbound["result"]["ui_design"]["document"]["objects"][0][
        "token_bindings"
    ]
    assert "style.stroke" not in bindings

    imported = registry.execute(
        "paint.ui.token.library.import",
        {"path": str(path), "conflict_policy": "regenerate"},
    ).to_dict()
    assert imported["ok"] is True
    assert imported["result"]["token_import"]["conflict_policy"] == "regenerate"
    assert (
        imported["result"]["ui_design"]["validation"]["token_count"] == 6
    )
    dialog.close()
    dialog.deleteLater()
    app.processEvents()

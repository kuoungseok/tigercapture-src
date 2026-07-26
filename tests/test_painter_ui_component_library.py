from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _library_document():
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        create_ui_component_variant,
        instantiate_ui_component,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844)
    document, root = add_ui_object(
        document,
        kind="button",
        name="Primary Button",
        x=32,
        y=700,
        width=326,
        height=56,
        content={"text": "Continue"},
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Primary Button",
    )
    document, variant = create_ui_component_variant(
        document,
        component_id=component["id"],
        name="Primary Button / Compact",
        variant_key="compact",
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=variant["id"],
        x=32,
        y=620,
    )
    return document, component, variant, instance


def test_component_library_report_groups_variants_and_usage() -> None:
    from app.painter_ui_component_library import inspect_ui_component_library

    document, component, variant, _instance = _library_document()
    report = inspect_ui_component_library(document)
    assert report["family_count"] == 1
    assert report["component_count"] == 2
    assert report["instance_count"] == 1
    family = report["families"][0]
    assert family["family_id"] == component["id"]
    assert family["variant_count"] == 1
    assert [row["component_id"] for row in family["members"]] == [
        component["id"],
        variant["id"],
    ]
    assert family["members"][1]["variant_key"] == "compact"
    assert family["members"][1]["instance_count"] == 1


def test_component_library_widget_search_and_commands_use_stable_ids() -> None:
    app = _app()
    from app.painter_ui_component_library import PainterUIComponentLibrary

    document, component, variant, _instance = _library_document()
    library = PainterUIComponentLibrary()
    library.set_document(document)
    assert library.tree.topLevelItemCount() == 1
    assert library.tree.topLevelItem(0).childCount() == 1

    selected: list[str] = []
    instantiated: list[tuple[str, str, float, float]] = []
    variants: list[tuple[str, str]] = []
    updates: list[tuple[str, dict[str, object]]] = []
    library.object_selected.connect(selected.append)
    library.instantiate_requested.connect(lambda *args: instantiated.append(args))
    library.variant_create_requested.connect(lambda *args: variants.append(args))
    library.component_update_requested.connect(
        lambda component_id, changes: updates.append(
            (component_id, dict(changes))
        )
    )
    variant_item = library.tree.topLevelItem(0).child(0)
    library.tree.setCurrentItem(variant_item)
    library.select_button.click()
    library.instance_button.click()
    library.variant_button.click()
    library.name_edit.setText("Compact CTA")
    library.rename_button.click()
    assert selected[-1] == variant["root_object_id"]
    assert instantiated[-1][0] == variant["id"]
    assert variants[-1][0] == variant["id"]
    assert updates[-1] == (variant["id"], {"name": "Compact CTA"})

    library.search_edit.setText("missing")
    assert library.tree.topLevelItemCount() == 0
    library.search_edit.setText("compact")
    assert library.tree.topLevelItemCount() == 1
    assert library.tree.topLevelItem(0).data(
        0, 256
    ) == component["id"]
    library.deleteLater()
    app.processEvents()


def test_component_library_action_is_read_only() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, _component, _variant, _instance = _library_document()
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.ui.component.library.inspect",
        {},
    ).to_dict()
    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["family_count"] == 1
    assert result["result"]["instance_count"] == 1
    dialog.close()
    dialog.deleteLater()
    app.processEvents()

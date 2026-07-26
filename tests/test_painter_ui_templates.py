from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_builtin_template_catalog_is_broad_and_license_explicit() -> None:
    from app.painter_ui_templates import inspect_ui_template_catalog

    report = inspect_ui_template_catalog()
    assert report["template_count"] >= 12
    assert report["category_count"] >= 10
    assert {
        "Mobile",
        "Web & SaaS",
        "Dashboard",
        "E-commerce",
        "Game UI",
        "Broadcast",
        "Presentation",
        "Design System",
    } <= set(report["categories"])
    for row in report["templates"]:
        assert row["source"]
        assert row["license"]["id"]
        assert isinstance(row["license"]["commercial_use"], bool)
        assert row["artboard_presets"]
        assert row["features"]


def test_every_builtin_template_is_a_valid_complete_editable_document() -> None:
    from app.painter_ui_document import validate_ui_document
    from app.painter_ui_templates import (
        inspect_ui_template_catalog,
        instantiate_ui_template,
    )

    for row in inspect_ui_template_catalog()["templates"]:
        document, report = instantiate_ui_template(row["id"])
        validation = validate_ui_document(document)
        assert validation["ok"], (row["id"], validation["errors"])
        assert report["artboard_count"] >= 1
        assert report["object_count"] >= 5
        assert report["component_count"] >= 1
        assert report["token_count"] >= 7
        assert report["interaction_count"] >= 1
        provenance = document["linked_targets"]["template_source"]
        assert provenance["template_id"] == row["id"]
        assert provenance["template_version"] == row["version"]
        assert provenance["license"]["id"] == row["license"]["id"]


def test_template_gallery_filters_renders_and_emits_stable_id() -> None:
    app = _app()
    from app.painter_ui_template_gallery import (
        PainterUITemplateGalleryDialog,
        PainterUITemplateLibrary,
        ui_template_thumbnail,
    )

    thumbnail = ui_template_thumbnail("game_hud")
    assert not thumbnail.isNull()
    assert thumbnail.width() == 240
    assert thumbnail.height() == 150

    gallery = PainterUITemplateGalleryDialog()
    assert gallery.items.count() >= 12
    gallery.search_edit.setText("tactical")
    assert gallery.items.count() == 1
    assert gallery.items.item(0).data(256) == "game_hud"
    gallery.search_edit.clear()
    gallery.category_combo.setCurrentText("Mobile")
    assert gallery.items.count() == 2

    library = PainterUITemplateLibrary()
    applied: list[str] = []
    library.template_apply_requested.connect(applied.append)
    target = next(
        item
        for item in (
            library.quick_list.item(index)
            for index in range(library.quick_list.count())
        )
        if item.data(256) == "saas_dashboard"
    )
    library.quick_list.itemDoubleClicked.emit(target)
    assert applied == ["saas_dashboard"]
    gallery.deleteLater()
    library.deleteLater()
    app.processEvents()


def test_template_actions_inspect_apply_and_undo() -> None:
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
    inspected = registry.execute(
        "paint.ui.template.catalog.inspect",
        {},
    ).to_dict()
    assert inspected["ok"] is True
    assert inspected["changed"] is False
    assert inspected["result"]["template_count"] >= 12

    before = dialog._painter_ui_document["document_id"]
    applied = registry.execute(
        "paint.ui.template.apply",
        {"template_id": "saas_dashboard"},
    ).to_dict()
    assert applied["ok"] is True
    assert applied["result"]["template"]["artboard_count"] == 2
    assert (
        applied["result"]["ui_design"]["document"]["linked_targets"][
            "template_source"
        ]["template_id"]
        == "saas_dashboard"
    )
    dialog._undo()
    assert dialog._painter_ui_document["document_id"] == before
    dialog.close()
    dialog.deleteLater()
    app.processEvents()

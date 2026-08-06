from __future__ import annotations

import itertools
import math
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


def test_builtin_media_placeholders_do_not_claim_missing_image_sources() -> None:
    from app.painter_ui_templates import (
        inspect_ui_template_catalog,
        instantiate_ui_template,
    )

    observed = 0
    for template in inspect_ui_template_catalog()["templates"]:
        document, _report = instantiate_ui_template(template["id"])
        for row in document["objects"]:
            if row.get("name") != "Hero Media":
                continue
            observed += 1
            assert row["kind"] == "rectangle"
            assert not (row.get("content") or {}).get("source_path")
    assert observed > 0


def test_mobile_onboarding_body_uses_readable_non_clipping_type_size() -> None:
    from app.painter_ui_templates import instantiate_ui_template

    document, _report = instantiate_ui_template("mobile_onboarding")
    body_rows = [
        row for row in document["objects"] if row.get("name") == "Supporting Copy"
    ]
    assert len(body_rows) == 3
    assert {row["style"]["font_size"] for row in body_rows} == {18.0}


def _rectangles_overlap(left: dict, right: dict) -> bool:
    left_x = float(left["x"])
    left_y = float(left["y"])
    left_right = left_x + float(left["width"])
    left_bottom = left_y + float(left["height"])
    right_x = float(right["x"])
    right_y = float(right["y"])
    right_right = right_x + float(right["width"])
    right_bottom = right_y + float(right["height"])
    return (
        left_x < right_right
        and right_x < left_right
        and left_y < right_bottom
        and right_y < left_bottom
    )


def test_builtin_template_objects_stay_inside_their_artboards() -> None:
    from app.painter_ui_templates import (
        inspect_ui_template_catalog,
        instantiate_ui_template,
    )

    for template in inspect_ui_template_catalog()["templates"]:
        document, _report = instantiate_ui_template(template["id"])
        artboards = {row["id"]: row for row in document["artboards"]}
        for row in document["objects"]:
            artboard = artboards[row["artboard_id"]]
            assert float(row["x"]) >= 0, (template["id"], row["name"])
            assert float(row["y"]) >= 0, (template["id"], row["name"])
            assert float(row["x"]) + float(row["width"]) <= float(
                artboard["width"]
            ), (template["id"], artboard["name"], row["name"])
            assert float(row["y"]) + float(row["height"]) <= float(
                artboard["height"]
            ), (template["id"], artboard["name"], row["name"])


def test_hud_broadcast_and_pitch_constraints_preserve_reference_geometry() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_templates import instantiate_ui_template

    expected_modes = {
        "Top Status": ("stretch", "top"),
        "Information Rail": ("right", "stretch"),
        "Lower Third": ("left", "bottom"),
        "Action Prompt": ("center", "bottom"),
    }
    for template_id in ("game_hud", "broadcast_overlay"):
        document, _report = instantiate_ui_template(template_id)
        resolved = resolve_ui_constraints(document)
        rows_by_name = {row["name"]: row for row in document["objects"]}
        for name, (horizontal, vertical) in expected_modes.items():
            row = rows_by_name[name]
            assert row["constraints"]["horizontal"] == horizontal
            assert row["constraints"]["vertical"] == vertical
            for key in ("x", "y", "width", "height"):
                assert abs(float(resolved[row["id"]][key]) - float(row[key])) <= 1e-6

    pitch, _report = instantiate_ui_template("pitch_deck_cover")
    resolved = resolve_ui_constraints(pitch)
    accent_rows = [
        row for row in pitch["objects"] if row["name"] == "Accent Field"
    ]
    assert len(accent_rows) == 3
    for row in accent_rows:
        assert row["constraints"]["horizontal"] == "right"
        assert row["constraints"]["vertical"] == "stretch"
        for key in ("x", "y", "width", "height"):
            assert abs(float(resolved[row["id"]][key]) - float(row[key])) <= 1e-6


def test_hud_broadcast_and_pitch_constraints_export_expected_umg_anchors() -> None:
    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    expected_anchors = {
        "Top Status": ((0.0, 0.0), (1.0, 0.0)),
        "Information Rail": ((1.0, 0.0), (1.0, 1.0)),
        "Lower Third": ((0.0, 1.0), (0.0, 1.0)),
        "Action Prompt": ((0.5, 1.0), (0.5, 1.0)),
    }

    def vector(value: dict) -> tuple[float, float]:
        return float(value["X"]), float(value["Y"])

    for template_id in ("game_hud", "broadcast_overlay"):
        document, _report = instantiate_ui_template(template_id)
        exported = painter_ui_to_umg_document(document)
        layers_by_name = {row["Name"]: row for row in exported["Layers"]}
        for name, (minimum, maximum) in expected_anchors.items():
            slot = layers_by_name[name]["CanvasSlot"]
            assert vector(slot["AnchorMinimum"]) == minimum
            assert vector(slot["AnchorMaximum"]) == maximum

    pitch, _report = instantiate_ui_template("pitch_deck_cover")
    for artboard in pitch["artboards"]:
        exported = painter_ui_to_umg_document(
            pitch,
            artboard_id=artboard["id"],
        )
        accent = next(
            row for row in exported["Layers"] if row["Name"] == "Accent Field"
        )
        slot = accent["CanvasSlot"]
        assert vector(slot["AnchorMinimum"]) == (1.0, 0.0)
        assert vector(slot["AnchorMaximum"]) == (1.0, 1.0)


def test_mobile_dashboard_metrics_chart_and_cta_do_not_overlap() -> None:
    from app.painter_ui_templates import instantiate_ui_template

    observed_artboards = 0
    for template_id in ("mobile_finance", "saas_dashboard"):
        document, _report = instantiate_ui_template(template_id)
        mobile_ids = {
            row["id"]
            for row in document["artboards"]
            if float(row["width"]) <= 700
        }
        for artboard_id in mobile_ids:
            observed_artboards += 1
            regions = [
                row
                for row in document["objects"]
                if row["artboard_id"] == artboard_id
                and (
                    str(row["name"]).startswith("Metric Card")
                    or row["name"] in {"Chart Region", "Primary CTA"}
                )
            ]
            assert len(regions) == 5
            for left, right in itertools.combinations(regions, 2):
                assert not _rectangles_overlap(left, right), (
                    template_id,
                    left["name"],
                    right["name"],
                )
    assert observed_artboards == 3


def test_mobile_generic_hero_copy_cta_and_cards_have_separate_regions() -> None:
    from app.painter_ui_templates import instantiate_ui_template

    key_names = {
        "Hero Headline",
        "Hero Media",
        "Supporting Copy",
        "Primary CTA",
        "Feature Card A",
        "Feature Card B",
    }
    observed_artboards = 0
    for template_id in (
        "mobile_onboarding",
        "commerce_product",
        "wireframe_user_flow",
    ):
        document, _report = instantiate_ui_template(template_id)
        mobile_ids = {
            row["id"]
            for row in document["artboards"]
            if float(row["width"]) <= 700
        }
        for artboard_id in mobile_ids:
            observed_artboards += 1
            regions = [
                row
                for row in document["objects"]
                if row["artboard_id"] == artboard_id
                and row["name"] in key_names
            ]
            assert {row["name"] for row in regions} == key_names
            for left, right in itertools.combinations(regions, 2):
                assert not _rectangles_overlap(left, right), (
                    template_id,
                    left["name"],
                    right["name"],
                )
    assert observed_artboards == 5


def test_desktop_generic_supporting_copy_has_enough_line_height() -> None:
    from app.painter_ui_templates import instantiate_ui_template

    observed = 0
    for template_id in (
        "commerce_product",
        "portfolio_case_study",
        "wireframe_user_flow",
        "accessible_checkout",
    ):
        document, _report = instantiate_ui_template(template_id)
        desktop_ids = {
            row["id"]
            for row in document["artboards"]
            if float(row["width"]) > 700
        }
        for row in document["objects"]:
            if (
                row["artboard_id"] not in desktop_ids
                or row["name"] != "Supporting Copy"
            ):
                continue
            observed += 1
            font_size = float(row["style"]["font_size"])
            text = str((row.get("content") or {}).get("text") or "")
            estimated_chars_per_line = max(
                1,
                int(float(row["width"]) / (font_size * 0.55)),
            )
            estimated_lines = math.ceil(len(text) / estimated_chars_per_line)
            estimated_text_height = estimated_lines * font_size * 1.35
            assert font_size == 18.0
            assert estimated_text_height <= float(row["height"]), (
                template_id,
                estimated_lines,
                row["height"],
            )
    assert observed == 4


def test_template_gallery_filters_renders_and_emits_stable_id() -> None:
    app = _app()
    from PySide6.QtWidgets import QPushButton

    from app.painter_ui_template_gallery import (
        PainterUITemplateGalleryDialog,
        PainterUITemplateLibrary,
        PainterUITemplateStrip,
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
    gallery.category_combo.setCurrentIndex(0)
    gallery.platform_combo.setCurrentText("Mobile")
    assert gallery.items.count() >= 2
    assert all(
        "mobile"
        in gallery.items.item(index).data(257)["platforms"]
        for index in range(gallery.items.count())
    )
    gallery.insert_mode_combo.setCurrentIndex(
        gallery.insert_mode_combo.findData("component_set")
    )
    assert gallery.selected_insert_mode == "component_set"
    assert (
        gallery.findChild(
            QPushButton,
            "PainterUITemplateUseButton",
        ).text()
        == "Insert Components"
    )

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

    strip = PainterUITemplateStrip(quick_count=5)
    strip_applied: list[str] = []
    strip.template_apply_requested.connect(strip_applied.append)
    assert strip.objectName() == "PainterUITemplateStrip"
    assert len(strip.quick_buttons) == 5
    assert all(button.text() == "" for button in strip.quick_buttons)
    assert all(not button.icon().isNull() for button in strip.quick_buttons)
    assert all(button.size().width() == 58 for button in strip.quick_buttons)
    assert all(button.size().height() == 28 for button in strip.quick_buttons)
    assert strip.browse_button.size().width() == 28
    assert strip.browse_button.size().height() == 28
    assert not strip.browse_button.icon().isNull()
    strip.quick_buttons[0].click()
    assert len(strip_applied) == 1
    assert strip_applied[0]
    gallery.deleteLater()
    library.deleteLater()
    strip.deleteLater()
    app.processEvents()


def test_template_search_and_preview_share_gallery_contract(tmp_path) -> None:
    from app.painter_ui_template_store import (
        preview_ui_template,
        search_ui_templates,
        set_ui_template_favorite,
    )

    report = search_ui_templates(
        query="tactical",
        platform="desktop",
        store_root=tmp_path,
    )
    assert report["schema"] == "tigerstudio.painter.ui.template_search.v1"
    assert report["count"] == 1
    assert report["templates"][0]["id"] == "game_hud"
    assert "desktop" in report["templates"][0]["platforms"]
    assert {"mobile", "desktop"} <= set(report["facets"]["platforms"])

    set_ui_template_favorite("game_hud", True, store_root=tmp_path)
    favorites = search_ui_templates(
        view="favorites",
        store_root=tmp_path,
    )
    assert [row["id"] for row in favorites["templates"]] == ["game_hud"]

    preview = preview_ui_template("game_hud", store_root=tmp_path)
    assert preview["schema"] == "tigerstudio.painter.ui.template_preview.v1"
    assert preview["document"]["artboard_count"] >= 1
    assert preview["document"]["component_count"] >= 1
    assert preview["document"]["interaction_count"] >= 1
    assert preview["compatibility"]["web"] == "inspect_on_insert"
    assert search_ui_templates(store_root=tmp_path)["templates"][0]["recent"] is False


def test_template_insert_modes_remap_ids_and_round_trip() -> None:
    import json

    from app.painter_ui_document import (
        create_ui_document,
        normalize_ui_document,
        validate_ui_document,
    )
    from app.painter_ui_template_insert import insert_ui_template
    from app.painter_ui_templates import instantiate_ui_template

    source, _report = instantiate_ui_template("saas_dashboard")
    base = create_ui_document(390, 844)
    pages, first = insert_ui_template(
        base,
        source,
        template_id="saas_dashboard",
        mode="page",
    )
    pages, second = insert_ui_template(
        pages,
        source,
        template_id="saas_dashboard",
        mode="page",
    )
    assert first["inserted_pages"] == second["inserted_pages"] == 1
    assert len(pages["pages"]) == 3
    assert len({row["id"] for row in pages["objects"]}) == len(
        pages["objects"]
    )
    assert validate_ui_document(pages)["ok"] is True
    restored = normalize_ui_document(json.loads(json.dumps(pages)))
    assert len(restored["artboards"]) == len(pages["artboards"])
    assert restored["interactions"] == pages["interactions"]

    components, report = insert_ui_template(
        base,
        source,
        template_id="saas_dashboard",
        mode="component_set",
    )
    assert report["inserted_components"] == 1
    assert len(components["components"]) == 1
    assert components["objects"][0]["artboard_id"] == base["active_artboard_id"]

    themed, _report = insert_ui_template(
        source,
        instantiate_ui_template("game_hud")[0],
        template_id="game_hud",
        mode="theme",
    )
    assert [row["id"] for row in themed["tokens"]] == [
        row["id"] for row in source["tokens"]
    ]
    assert validate_ui_document(themed)["ok"] is True


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
    searched = registry.execute(
        "paint.ui.template.search",
        {"query": "tactical", "platform": "desktop"},
    ).to_dict()
    assert searched["ok"] is True
    assert searched["result"]["templates"][0]["id"] == "game_hud"
    previewed = registry.execute(
        "paint.ui.template.preview",
        {"template_id": "game_hud"},
    ).to_dict()
    assert previewed["ok"] is True
    assert previewed["result"]["document"]["component_count"] >= 1

    initial_page_count = len(dialog._painter_ui_document["pages"])
    inserted = registry.execute(
        "paint.ui.template.insert",
        {"template_id": "saas_dashboard", "mode": "page"},
    ).to_dict()
    assert inserted["ok"] is True
    assert inserted["result"]["template_insert"]["mode"] == "page"
    assert len(dialog._painter_ui_document["pages"]) == initial_page_count + 1
    dialog._undo()
    assert len(dialog._painter_ui_document["pages"]) == initial_page_count

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

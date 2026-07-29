from __future__ import annotations

import json
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document():
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_token,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_variables import (
        LEGACY_THEME_MODE_IDS,
    )

    document = create_ui_document(390, 844)
    document, base = add_ui_token(
        document,
        name="Surface Base",
        kind="color",
        token_value="#F8FAFC",
        mode_values={
            LEGACY_THEME_MODE_IDS["light"]: "#F8FAFC",
            LEGACY_THEME_MODE_IDS["dark"]: "#121820",
        },
        scope=["style.fill"],
    )
    document, alias = add_ui_token(
        document,
        name="Card Surface",
        kind="color",
        alias_token_id=base["id"],
        scope=["style.fill"],
    )
    document, row = add_ui_object(
        document,
        kind="button",
        x=24,
        y=40,
        width=180,
        height=48,
        name="Continue",
    )
    document, row = update_ui_object(
        document,
        row["id"],
        {
            "style": {
                **row["style"],
                "fill": "#F8FAFC",
                "stroke": "#263241",
                "stroke_width": 1,
                "radius": 8,
            },
            "token_bindings": {"style.fill": alias["id"]},
        },
    )
    return document, row, base, alias


def test_dev_snippets_use_real_web_and_umg_adapters() -> None:
    from app.painter_ui_dev_snippets import (
        DEV_SNIPPET_SCHEMA,
        WEB_CSS_ADAPTER,
        inspect_ui_dev_snippets,
    )
    from app.painter_ui_umg_adapter import PAINTER_UMG_ADAPTER_SCHEMA

    document, row, _base, _alias = _document()
    report = inspect_ui_dev_snippets(document, row["id"])
    assert report["schema"] == DEV_SNIPPET_SCHEMA
    snippets = {item["target"]: item for item in report["snippets"]}
    assert snippets["web"]["adapter"] == WEB_CSS_ADAPTER
    assert f'data-tiger-id="{row["id"]}"' in snippets["web"]["code"]
    assert "border-radius: 8px;" in snippets["web"]["code"]
    assert snippets["umg"]["adapter"] == PAINTER_UMG_ADAPTER_SCHEMA
    umg_layer = json.loads(snippets["umg"]["code"])
    assert umg_layer["Id"] == row["id"]
    assert umg_layer["Disposition"] == "Native"
    assert snippets["ios"]["available"] is False
    assert snippets["android"]["unsupported"] == ["adapter_not_implemented"]


def test_dev_handoff_resolves_active_mode_and_alias_terminal() -> None:
    from app.painter_ui_dev_handoff import inspect_ui_dev_handoff
    from app.painter_ui_variables import LEGACY_THEME_MODE_IDS

    document, row, base, alias = _document()
    document["artboards"][0]["variable_modes"][
        "ui-variable-collection-theme"
    ] = LEGACY_THEME_MODE_IDS["dark"]
    report = inspect_ui_dev_handoff(document, object_ids=[row["id"]])
    token = report["objects"][0]["tokens"][0]
    assert token["alias_chain"] == [alias["id"], base["id"]]
    assert token["resolved_token_id"] == base["id"]
    assert token["mode_name"] == "Dark"
    assert token["resolved_value"] == "#121820"
    assert token["alias_cycle"] is False
    assert report["objects"][0]["developer_snippets"]


def test_dev_panel_shows_variables_snippets_and_copies_code() -> None:
    app = _app()
    from app.painter_ui_dev_handoff import inspect_ui_dev_handoff
    from app.painter_ui_dev_panel import PainterUIDevPanel

    document, row, _base, _alias = _document()
    panel = PainterUIDevPanel()
    panel.set_report(inspect_ui_dev_handoff(document, object_ids=[row["id"]]))
    assert panel.variable_list.count() == 1
    assert panel.snippet_combo.count() == 5
    assert panel.snippet_view.toPlainText().startswith("[data-tiger-id")
    panel.copy_button.click()
    assert app.clipboard().text() == panel.snippet_view.toPlainText()
    panel.snippet_combo.setCurrentIndex(3)
    assert not panel.copy_button.isEnabled()
    assert not panel.snippet_view.isVisible()


def test_dev_snippet_action_is_read_only() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, row, _base, _alias = _document()
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    action = next(
        item
        for item in registry.list_actions()
        if item["id"] == "paint.ui.dev.snippet.inspect"
    )
    assert action["mutating"] is False
    result = registry.execute(
        "paint.ui.dev.snippet.inspect",
        {"object_id": row["id"]},
    ).to_dict()
    assert result["ok"] is True
    assert result["result"]["object_id"] == row["id"]
    dialog.close()
    app.processEvents()

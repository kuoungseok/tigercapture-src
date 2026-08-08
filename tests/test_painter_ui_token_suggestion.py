from __future__ import annotations

import copy
import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _suggestion_document():
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_token,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(800, 600, name="Desktop")
    document["artboards"][0]["theme"] = "dark"
    document, frame = add_ui_object(
        document,
        kind="frame",
        name="Metric Card",
        style={
            "fill": "#7895ff",
            "stroke": "#FFFFFF",
            "radius": 12,
        },
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {
            "layout": {
                "mode": "horizontal",
                "gap": 16,
                "cross_gap": 8,
                "padding": {
                    "left": 24,
                    "top": 16,
                    "right": 24,
                    "bottom": 16,
                },
            }
        },
    )
    document, primary = add_ui_token(
        document,
        name="Brand Primary",
        kind="color",
        token_value="#4267E8",
        theme_values={"dark": "#7895FF"},
    )
    document, action_fill = add_ui_token(
        document,
        name="Action Fill",
        kind="color",
        alias_token_id=primary["id"],
    )
    document, gap = add_ui_token(
        document,
        name="Space 16",
        kind="spacing",
        token_value=16,
    )
    document, padding = add_ui_token(
        document,
        name="Space 24",
        kind="spacing",
        token_value=24,
    )
    document, radius = add_ui_token(
        document,
        name="Radius 12",
        kind="radius",
        token_value=12,
    )
    document, wrong_kind = add_ui_token(
        document,
        name="Not A Color",
        kind="spacing",
        token_value="#7895FF",
    )
    document, _frame = update_ui_object(
        document,
        frame["id"],
        {"token_bindings": {"style.stroke": primary["id"]}},
    )
    return {
        "document": document,
        "frame": frame,
        "primary": primary,
        "action_fill": action_fill,
        "gap": gap,
        "padding": padding,
        "radius": radius,
        "wrong_kind": wrong_kind,
    }


def test_token_suggestions_resolve_theme_alias_and_strict_kinds() -> None:
    from app.painter_ui_token_suggestion import suggest_ui_tokens

    fixture = _suggestion_document()
    report = suggest_ui_tokens(fixture["document"])

    assert report["schema"] == "tigerstudio.painter.ui.token_suggestions.v1"
    assert report["selected_object_id"] == fixture["frame"]["id"]
    assert report["theme"] == "dark"
    pairs = {
        (item["property_path"], item["token_id"])
        for item in report["suggestions"]
    }
    assert ("style.fill", fixture["primary"]["id"]) in pairs
    assert ("style.fill", fixture["action_fill"]["id"]) in pairs
    assert ("style.fill", fixture["wrong_kind"]["id"]) not in pairs
    assert ("style.radius", fixture["radius"]["id"]) in pairs
    assert ("layout.gap", fixture["gap"]["id"]) in pairs
    assert ("layout.padding.left", fixture["padding"]["id"]) in pairs
    assert ("layout.padding.right", fixture["padding"]["id"]) in pairs
    assert not any(
        item["property_path"] == "style.stroke"
        for item in report["suggestions"]
    )
    alias = next(
        item
        for item in report["suggestions"]
        if item["token_id"] == fixture["action_fill"]["id"]
    )
    assert alias["resolved_value"] == "#7895FF"
    assert alias["alias_chain"] == [
        fixture["action_fill"]["id"],
        fixture["primary"]["id"],
    ]


def test_token_suggestion_can_filter_one_property_and_rejects_unknown_path() -> None:
    from app.painter_ui_token_suggestion import (
        PainterUITokenSuggestionError,
        suggest_ui_tokens,
    )

    fixture = _suggestion_document()
    report = suggest_ui_tokens(
        fixture["document"],
        object_id=fixture["frame"]["id"],
        property_path="layout.gap",
    )
    assert {
        item["property_path"] for item in report["suggestions"]
    } == {"layout.gap"}
    with pytest.raises(PainterUITokenSuggestionError):
        suggest_ui_tokens(
            fixture["document"],
            property_path="style.unknown",
        )


def test_token_suggestion_panel_emits_selected_stable_binding() -> None:
    app = _app()
    from app.painter_ui_token_suggestion import (
        PainterUITokenSuggestionPanel,
        suggest_ui_tokens,
    )

    fixture = _suggestion_document()
    panel = PainterUITokenSuggestionPanel()
    report = suggest_ui_tokens(
        fixture["document"],
        property_path="layout.gap",
    )
    emitted: list[tuple[str, str, str]] = []
    panel.binding_requested.connect(lambda *args: emitted.append(args))
    panel.set_report(report)

    assert panel.isVisible()
    assert panel.suggestion_combo.count() == 1
    assert "Space 16" in panel.suggestion_combo.currentText()
    panel.bind_button.click()
    app.processEvents()
    assert emitted == [
        (
            fixture["frame"]["id"],
            "layout.gap",
            fixture["gap"]["id"],
        )
    ]

    panel.set_report(None)
    assert panel.isHidden()
    assert not panel.bind_button.isEnabled()
    panel.deleteLater()
    app.processEvents()


def test_token_suggest_action_is_non_mutating_and_inspector_accept_undoes() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    fixture = _suggestion_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(fixture["document"])
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._refresh_painter_ui_overlay()
    app.processEvents()
    registry = ActionRegistry(owner=dialog)
    before = copy.deepcopy(dialog._painter_ui_document)
    undo_count = len(dialog._undo_stack)

    result = registry.execute(
        "paint.ui.token.suggest",
        {"property_path": "layout.gap"},
    ).to_dict()
    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["suggestion_count"] == 1
    assert dialog._painter_ui_document == before
    assert len(dialog._undo_stack) == undo_count

    panel = dialog._paint_ui_inspector.token_suggestion_panel
    target_index = next(
        index
        for index in range(panel.suggestion_combo.count())
        if panel.suggestion_combo.itemData(index)["property_path"]
        == "layout.gap"
    )
    panel.suggestion_combo.setCurrentIndex(target_index)
    panel.bind_button.click()
    app.processEvents()
    selected = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == fixture["frame"]["id"]
    )
    assert selected["token_bindings"]["layout.gap"] == fixture["gap"]["id"]
    assert len(dialog._undo_stack) == undo_count + 1
    assert not dialog._paint_ui_inspector.token_suggestion_panel.report()[
        "suggestions"
    ] or not any(
        item["property_path"] == "layout.gap"
        for item in dialog._paint_ui_inspector.token_suggestion_panel.report()[
            "suggestions"
        ]
    )

    dialog._undo()
    restored = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == fixture["frame"]["id"]
    )
    assert "layout.gap" not in restored["token_bindings"]
    dialog.close()
    dialog.deleteLater()
    app.processEvents()

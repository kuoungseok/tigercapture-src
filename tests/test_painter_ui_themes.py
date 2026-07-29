from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _themed_document():
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_token,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(390, 844)
    document["artboards"][0]["breakpoint"] = "mobile"
    document, base = add_ui_token(
        document,
        name="Surface",
        kind="color",
        token_value="#F4F6FA",
        theme_values={
            "dark": "#171A20",
            "high-contrast": "#000000",
        },
    )
    document, alias = add_ui_token(
        document,
        name="Card Surface",
        kind="color",
        token_value=None,
        alias_token_id=base["id"],
    )
    document, row = add_ui_object(
        document,
        kind="rectangle",
        x=24,
        y=40,
        width=220,
        height=96,
    )
    document, _ = update_ui_object(
        document,
        row["id"],
        {"token_bindings": {"style.fill": alias["id"]}},
    )
    return document, base, alias, row


def test_theme_values_normalize_and_resolve_alias_chain() -> None:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_themes import resolve_ui_theme_document

    document, base, alias, row = _themed_document()
    document["artboards"][0]["theme"] = "high contrast"
    normalized = normalize_ui_document(document)
    assert normalized["version"] == 21
    assert normalized["artboards"][0]["theme"] == "high_contrast"
    assert normalized["tokens"][0]["theme_values"]["high_contrast"] == "#000000"

    resolved = resolve_ui_theme_document(normalized)
    effective = next(item for item in resolved["objects"] if item["id"] == row["id"])
    assert effective["style"]["fill"] == "#000000"
    binding = effective["resolved_tokens"]["style.fill"]
    assert binding["token_id"] == alias["id"]
    assert binding["alias_chain"] == [alias["id"], base["id"]]


def test_theme_resolution_applies_supported_property_paths() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_token,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_themes import resolve_ui_theme_document

    document = create_ui_document()
    document["artboards"][0]["theme"] = "dark"
    document, opacity = add_ui_token(
        document,
        name="Muted opacity",
        kind="opacity",
        token_value=1.0,
        theme_values={"dark": 0.62},
    )
    document, gap = add_ui_token(
        document,
        name="Compact gap",
        kind="spacing",
        token_value=12,
        theme_values={"dark": 18},
    )
    document, row = add_ui_object(document, kind="frame")
    document, _ = update_ui_object(
        document,
        row["id"],
        {
            "token_bindings": {
                "opacity": opacity["id"],
                "layout.gap": gap["id"],
            }
        },
    )
    effective = resolve_ui_theme_document(document)["objects"][0]
    assert effective["opacity"] == 0.62
    assert effective["layout"]["gap"] == 18


def test_canvas_and_inspector_switch_to_artboard_theme() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, _base, _alias, row = _themed_document()
    document["artboards"][0]["theme"] = "dark"
    overlay = PainterUIDesignOverlay()
    overlay.set_document(document)
    effective = next(
        item for item in overlay._effective_document["objects"] if item["id"] == row["id"]
    )
    assert effective["style"]["fill"] == "#171A20"

    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[tuple[str, dict]] = []
    inspector.artboard_layout_changed.connect(
        lambda artboard_id, changes: emitted.append((artboard_id, changes))
    )
    index = inspector.artboard_theme_combo.findData("high_contrast")
    inspector.artboard_theme_combo.setCurrentIndex(index)
    assert emitted[-1][1]["theme"] == "high_contrast"
    overlay.deleteLater()
    inspector.deleteLater()
    app.processEvents()


def test_theme_actions_update_inspect_remove_and_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, base, _alias, _row = _themed_document()
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.ui.theme.set",
        "paint.ui.theme.inspect",
        "paint.ui.token.theme.set",
        "paint.ui.token.theme.remove",
    } <= action_ids

    result = registry.execute(
        "paint.ui.theme.set",
        {"theme": "dark"},
    ).to_dict()
    assert result["ok"] is True
    assert dialog._painter_ui_document["artboards"][0]["theme"] == "dark"

    result = registry.execute(
        "paint.ui.token.theme.set",
        {
            "token_id": base["id"],
            "theme": "dark",
            "value": "#20242C",
        },
    ).to_dict()
    assert result["ok"] is True
    report = registry.execute(
        "paint.ui.theme.inspect",
        {},
    ).to_dict()["result"]
    assert report["theme"] == "dark"
    assert report["resolved_binding_count"] == 1

    removed = registry.execute(
        "paint.ui.token.theme.remove",
        {"token_id": base["id"], "theme": "dark"},
    ).to_dict()
    assert removed["ok"] is True
    dialog._undo()
    token = next(
        item
        for item in dialog._painter_ui_document["tokens"]
        if item["id"] == base["id"]
    )
    assert token["theme_values"]["dark"] == "#20242C"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()

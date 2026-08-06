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
    from app.painter_ui_document import UI_DOCUMENT_VERSION, normalize_ui_document
    from app.painter_ui_themes import resolve_ui_theme_document

    document, base, alias, row = _themed_document()
    document["artboards"][0]["theme"] = "high contrast"
    normalized = normalize_ui_document(document)
    assert normalized["version"] == UI_DOCUMENT_VERSION
    assert normalized["artboards"][0]["theme"] == "high_contrast"
    assert normalized["tokens"][0]["theme_values"]["high_contrast"] == "#000000"

    resolved = resolve_ui_theme_document(normalized)
    effective = next(item for item in resolved["objects"] if item["id"] == row["id"])
    assert effective["style"]["fill"] == "#000000"
    assert effective["style"]["fills"][0]["color"] == "#000000"
    binding = effective["resolved_tokens"]["style.fill"]
    assert binding["token_id"] == alias["id"]
    assert binding["alias_chain"] == [alias["id"], base["id"]]


def test_theme_resolution_synchronizes_first_canonical_fill_and_stroke() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_token,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_themes import resolve_ui_theme_document

    document = create_ui_document(320, 180)
    document["artboards"][0]["theme"] = "dark"
    document, fill = add_ui_token(
        document,
        name="Fill",
        kind="color",
        token_value="#FFFFFFFF",
        theme_values={"dark": "#172033FF"},
        scope=["style.fill"],
    )
    document, stroke = add_ui_token(
        document,
        name="Stroke",
        kind="color",
        token_value="#000000FF",
        theme_values={"dark": "#93C5FDFF"},
        scope=["style.stroke"],
    )
    document, stroke_width = add_ui_token(
        document,
        name="Stroke Width",
        kind="spacing",
        token_value=1.0,
        theme_values={"dark": 3.5},
        scope=["style.stroke_width"],
    )
    document, row = add_ui_object(
        document,
        kind="rectangle",
        style={
            "fill": "#FFFFFFFF",
            "fills": [
                {"type": "solid", "color": "#FFFFFFFF"},
                {"type": "solid", "color": "#445566FF"},
            ],
            "stroke": "#000000FF",
            "stroke_width": 1.0,
            "strokes": [
                {"type": "solid", "color": "#000000FF", "width": 1.0},
                {"type": "solid", "color": "#778899FF", "width": 2.0},
            ],
        },
    )
    document, _ = update_ui_object(
        document,
        row["id"],
        {
            "token_bindings": {
                "style.fill": fill["id"],
                "style.stroke": stroke["id"],
                "style.stroke_width": stroke_width["id"],
            }
        },
    )

    effective = resolve_ui_theme_document(document)["objects"][0]
    assert effective["style"]["fill"] == "#172033FF"
    assert effective["style"]["fills"][0]["color"] == "#172033FF"
    assert effective["style"]["fills"][1]["color"] == "#445566FF"
    assert effective["style"]["stroke"] == "#93C5FDFF"
    assert effective["style"]["strokes"][0]["color"] == "#93C5FDFF"
    assert effective["style"]["stroke_width"] == 3.5
    assert effective["style"]["strokes"][0]["width"] == 3.5
    assert effective["style"]["strokes"][1]["color"] == "#778899FF"
    assert effective["style"]["strokes"][1]["width"] == 2.0


def test_theme_resolution_does_not_replace_non_solid_canonical_paint() -> None:
    from app.painter_ui_themes import resolve_ui_theme_object

    gradient = {
        "type": "linear",
        "color": "#FFFFFFFF",
        "gradient": {
            "stops": [
                {"position": 0.0, "color": "#000000FF"},
                {"position": 1.0, "color": "#FFFFFFFF"},
            ]
        },
    }
    resolved = resolve_ui_theme_object(
        {
            "style": {"fill": "#FFFFFFFF", "fills": [gradient]},
            "token_bindings": {"style.fill": "gradient-color"},
        },
        theme="dark",
        tokens={
            "gradient-color": {
                "id": "gradient-color",
                "collection_id": "",
                "value": "#172033FF",
            }
        },
    )

    assert resolved["style"]["fill"] == "#172033FF"
    assert resolved["style"]["fills"][0] == gradient


def test_theme_bound_fill_reaches_umg_rounded_card_material() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_token,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document = create_ui_document(320, 180)
    document["artboards"][0]["theme"] = "dark"
    document, surface = add_ui_token(
        document,
        name="Surface",
        kind="color",
        token_value="#FFFFFFFF",
        theme_values={"dark": "#172033FF"},
        scope=["style.fill"],
    )
    document, card = add_ui_object(
        document,
        kind="rectangle",
        x=20,
        y=20,
        width=160,
        height=80,
        style={"fill": "#FFFFFFFF", "radius": 12},
    )
    document, _ = update_ui_object(
        document,
        card["id"],
        {"token_bindings": {"style.fill": surface["id"]}},
    )

    layer = next(
        row
        for row in painter_ui_to_umg_document(document)["Layers"]
        if row["Id"] == card["id"]
    )
    assert layer["Disposition"] == "Material"
    assert layer["Material"]["Kind"] == "RoundedCard"
    assert layer["Material"]["FillColor"] == "#172033FF"


def test_game_hud_token_fills_reach_umg_materials() -> None:
    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, _report = instantiate_ui_template("game_hud")
    layers = {
        row["Name"]: row
        for row in painter_ui_to_umg_document(document)["Layers"]
    }

    assert layers["Top Status"]["Material"]["FillColor"] == "#07100EFF"
    assert layers["Information Rail"]["Material"]["FillColor"] == "#07100EFF"
    assert layers["Lower Third"]["Material"]["FillColor"] == "#45E0A8FF"


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

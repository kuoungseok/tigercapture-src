from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document_with_rectangle():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(640, 480, name="Appearance")
    document, row = add_ui_object(
        document,
        kind="rectangle",
        name="Card",
        artboard_id=document["active_artboard_id"],
        x=40,
        y=40,
        width=240,
        height=120,
        style={"fill": "#20242CFF", "radius": 12},
    )
    return document, row


def test_ui_appearance_mutations_preserve_gradient_and_effect_order() -> None:
    from app.painter_ui_appearance import (
        add_ui_effect,
        inspect_ui_appearance,
        remove_ui_effect,
        reorder_ui_effect,
        set_ui_fill_gradient,
        update_ui_effect,
    )

    document, row = _document_with_rectangle()
    document, _ = set_ui_fill_gradient(
        document,
        row["id"],
        {
            "type": "linear",
            "start": {"x": 0, "y": 0.5},
            "end": {"x": 1, "y": 0.5},
            "stops": [
                {"position": 1, "color": "#0000FFFF"},
                {"position": 0, "color": "#FF0000FF"},
            ],
        },
    )
    document, _ = add_ui_effect(
        document,
        row["id"],
        {
            "type": "drop_shadow",
            "color": "#00000080",
            "x": 0,
            "y": 8,
            "blur": 20,
        },
    )
    document, _ = add_ui_effect(
        document,
        row["id"],
        {"type": "background_blur", "radius": 14},
    )
    document, _ = add_ui_effect(
        document,
        row["id"],
        {
            "type": "inner_shadow",
            "color": "#FFFFFFFF",
            "x": 0,
            "y": 1,
            "blur": 3,
        },
    )
    document, _ = update_ui_effect(
        document,
        row["id"],
        2,
        {"spread": -2, "blend_mode": "screen"},
    )
    document, effects = reorder_ui_effect(document, row["id"], 2, 0)
    assert [effect["type"] for effect in effects] == [
        "inner_shadow",
        "drop_shadow",
        "background_blur",
    ]

    appearance = inspect_ui_appearance(document, row["id"])
    assert appearance["gradient"]["stops"][0]["color"] == "#FF0000FF"
    assert appearance["effects"][0]["spread"] == -2
    assert appearance["effects"][0]["blend_mode"] == "screen"
    assert appearance["effects"][2] == {
        "type": "background_blur",
        "radius": 14.0,
    }
    object_row = next(
        item for item in document["objects"] if item["id"] == row["id"]
    )
    assert object_row["style"]["shadow"]["y"] == 8

    document, removed = remove_ui_effect(document, row["id"], 1)
    assert removed["type"] == "drop_shadow"
    object_row = next(
        item for item in document["objects"] if item["id"] == row["id"]
    )
    assert "shadow" not in object_row["style"]


def test_ui_appearance_dialog_round_trips_gradient_stops_and_effects() -> None:
    from app.painter_ui_appearance_editor import (
        PainterUIAppearanceDialog,
        appearance_summary,
    )

    _app()
    style = {
        "fill": "#20242CFF",
        "fill_gradient": {
            "type": "radial",
            "start": {"x": 0.4, "y": 0.4},
            "end": {"x": 0.9, "y": 0.4},
            "width": {"x": 0.4, "y": 0.9},
            "stops": [
                {"position": 0, "color": "#FFFFFFFF"},
                {"position": 1, "color": "#00000000"},
            ],
        },
        "effects": [
            {
                "type": "inner_shadow",
                "color": "#00000080",
                "x": 0,
                "y": 2,
                "blur": 6,
                "spread": 0,
                "blend_mode": "multiply",
            }
        ],
    }
    dialog = PainterUIAppearanceDialog(style)
    assert dialog.gradient_type_combo.currentData() == "radial"
    assert dialog.gradient_stop_list.count() == 2
    assert dialog.effect_list.count() == 1
    assert appearance_summary(style) == "Radial · 1 FX"

    dialog.gradient_center_x_spin.setValue(0.25)
    dialog.gradient_center_y_spin.setValue(0.75)
    dialog.gradient_radius_spin.setValue(0.4)
    result = dialog.appearance_style()
    assert result["fill_gradient"]["start"] == {"x": 0.25, "y": 0.75}
    assert result["fill_gradient"]["end"] == {"x": 0.65, "y": 0.75}
    assert result["effects"][0]["type"] == "inner_shadow"
    dialog.close()


def test_ui_appearance_actions_are_registered_and_mutate_the_same_document() -> None:
    _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 480, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, row = _document_with_rectangle()
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    action_ids = {item["id"] for item in registry.list_actions()}
    assert {
        "paint.ui.appearance.inspect",
        "paint.ui.appearance.gradient.set",
        "paint.ui.appearance.gradient.remove",
        "paint.ui.appearance.effect.add",
        "paint.ui.appearance.effect.update",
        "paint.ui.appearance.effect.remove",
        "paint.ui.appearance.effect.reorder",
        "paint.ui.appearance.blur.add",
        "paint.ui.appearance.blur.update",
        "paint.ui.appearance.blur.remove",
        "paint.ui.appearance.blur.reorder",
    } <= action_ids

    result = registry.execute(
        "paint.ui.appearance.gradient.set",
        {
            "object_id": row["id"],
            "gradient": {
                "type": "linear",
                "stops": [
                    {"position": 0, "color": "#FF0000FF"},
                    {"position": 1, "color": "#0000FFFF"},
                ],
            },
        },
    ).to_dict()
    assert result["ok"]
    result = registry.execute(
        "paint.ui.appearance.effect.add",
        {
            "object_id": row["id"],
            "effect": {
                "type": "drop_shadow",
                "color": "#00000080",
                "y": 6,
                "blur": 12,
            },
        },
    ).to_dict()
    assert result["ok"]
    inspected = registry.execute(
        "paint.ui.appearance.inspect",
        {"object_id": row["id"]},
    ).to_dict()
    assert inspected["ok"]
    assert inspected["result"]["gradient"]["type"] == "linear"
    assert inspected["result"]["effects"][0]["blur"] == 12
    result = registry.execute(
        "paint.ui.appearance.blur.add",
        {
            "object_id": row["id"],
            "blur_type": "layer_blur",
            "radius": 9,
        },
    ).to_dict()
    assert result["ok"]
    inspected = registry.execute(
        "paint.ui.appearance.inspect",
        {"object_id": row["id"]},
    ).to_dict()
    assert inspected["result"]["effects"][1] == {
        "type": "layer_blur",
        "radius": 9.0,
    }
    dialog.close()

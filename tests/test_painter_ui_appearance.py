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


def test_extended_fill_types_round_trip_and_render() -> None:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    from app.painter_ui_advanced_appearance import normalize_ui_paints
    from app.painter_ui_style_renderer import ui_fill_brush

    paints = normalize_ui_paints(
        [
            {
                "type": "pattern",
                "opacity": 0.8,
                "blend_mode": "multiply",
                "pattern": {
                    "kind": "dots",
                    "foreground": "#3366FFFF",
                    "background": "#FFFFFFFF",
                    "scale": 10,
                },
            },
            {"type": "solid", "color": "#FFFFFFFF"},
        ]
    )
    assert paints[0]["type"] == "pattern"
    assert paints[0]["pattern"]["kind"] == "dots"
    assert paints[0]["blend_mode"] == "multiply"

    image = QImage(80, 48, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.fillRect(QRectF(0, 0, 80, 48), ui_fill_brush({"fills": paints}, QRectF(0, 0, 80, 48)))
    painter.end()
    assert image.pixelColor(40, 24).alpha() > 0


def test_paint_dialog_exposes_shared_figma_fill_families() -> None:
    _app()
    from app.painter_ui_paint_editor import PainterUIPaintDialog

    dialog = PainterUIPaintDialog({"type": "solid", "color": "#FFFFFFFF"})
    values = {dialog.type_combo.itemData(i) for i in range(dialog.type_combo.count())}
    assert values == {"solid", "linear", "radial", "pattern", "image", "video", "shader"}
    dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("video"))
    dialog.video_path.setText("sample.mp4")
    assert dialog.paint()["source_path"] == "sample.mp4"
    dialog.close()


def test_shared_fill_component_round_trips_gradient_image_and_shader() -> None:
    _app()
    from app.painter_ui_fill_component import PainterUIFillComponent

    component = PainterUIFillComponent({"type": "linear"})
    component.stop_start_color.setText("#112233FF")
    component.stop_end_color.setText("#AABBCCFF")
    component._reverse_gradient()
    gradient = component.paint()
    assert gradient["gradient"]["stops"][0]["color"] == "#AABBCCFF"

    component.set_fill_type("image")
    component.image_path.setText("photo.png")
    component.image_fit.setCurrentIndex(component.image_fit.findData("crop"))
    component.image_adjustments["exposure"].setValue(12)
    image = component.paint()
    assert image["fit"] == "crop"
    assert image["adjustments"]["exposure"] == 12

    component.set_fill_type("shader")
    component.shader_combo.setCurrentIndex(component.shader_combo.findData("water_caustic"))
    shader = component.paint()
    assert shader["type"] == "shader"
    assert shader["shader_preset"] == "water_caustic"
    component.close()


def test_paint_stack_color_swatch_is_an_edit_button() -> None:
    _app()
    from PySide6.QtWidgets import QToolButton
    from app.painter_ui_paint_editor import PainterUIPaintStackEditor

    stack = PainterUIPaintStackEditor("채우기")
    stack.set_paints([{"type": "solid", "color": "#D9D9D9FF"}])
    swatch = stack.findChild(QToolButton, "PainterUIPaintSwatch")
    assert swatch is not None
    assert swatch.toolTip() == "색상 및 채우기 편집"
    stack.close()


def test_shader_fill_is_explicit_umg_preflight_blocker() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, _row = add_ui_object(
        create_ui_document(320, 240),
        kind="rectangle",
        style={"fills": [{"type": "shader", "shader_preset": "mesh_gradient"}]},
    )
    layer = painter_ui_to_umg_document(document)["Layers"][0]
    assert layer["Disposition"] == "Blocked"
    assert "shader_fill_requires_ui_material_or_bake" in layer["BlockReasons"]


def test_pattern_and_video_fills_are_explicit_umg_preflight_blockers() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, _frame = add_ui_object(
        create_ui_document(640, 480),
        kind="frame",
        name="Media frame",
        x=20,
        y=20,
        width=320,
        height=240,
        style={
            "fills": [
                {
                    "type": "video",
                    "source_path": "missing.mp4",
                    "visible": True,
                }
            ]
        },
    )
    umg = painter_ui_to_umg_document(document)
    layer = next(row for row in umg["Layers"] if row["Name"] == "Media frame")
    assert layer["Disposition"] == "Blocked"
    assert "video_fill_requires_runtime_media_adapter" in layer["BlockReasons"]


def test_object_flip_is_explicitly_blocked_for_umg_until_supported() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, _rectangle = add_ui_object(
        create_ui_document(320, 240),
        kind="rectangle",
        name="Flipped rectangle",
        content={"flip_x": True},
    )
    exported = painter_ui_to_umg_document(document)["Layers"][0]
    assert exported["Disposition"] == "Blocked"
    assert (
        "object_flip_requires_umg_render_transform_support"
        in exported["BlockReasons"]
    )


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
        "corner_smoothing": 0.6,
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
    assert dialog.corner_smoothing_spin.value() == 60.0
    assert appearance_summary(style) == "Radial · 1 FX"

    dialog.gradient_center_x_spin.setValue(0.25)
    dialog.gradient_center_y_spin.setValue(0.75)
    dialog.gradient_radius_spin.setValue(0.4)
    result = dialog.appearance_style()
    assert result["fill_gradient"]["start"] == {"x": 0.25, "y": 0.75}
    assert result["fill_gradient"]["end"] == {"x": 0.65, "y": 0.75}
    assert result["effects"][0]["type"] == "inner_shadow"
    assert result["corner_smoothing"] == 0.6
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

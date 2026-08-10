from __future__ import annotations

import copy


def _painter_document():
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(400, 300, name="HUD")
    document, group = add_ui_object(
        document,
        kind="frame",
        name="Panel",
        x=40,
        y=50,
        width=200,
        height=120,
    )
    document, group = update_ui_object(
        document,
        group["id"],
        {"clip_content": True},
    )
    document, text = add_ui_object(
        document,
        kind="text",
        name="Title",
        parent_id=group["id"],
        x=10,
        y=20,
        width=100,
        height=30,
        style={"text_color": "#22AAEEFF", "font_size": 19.6},
        content={"text": "Tiger"},
    )
    document, button = add_ui_object(
        document,
        kind="button",
        name="Continue",
        x=250,
        y=210,
        width=120,
        height=48,
        style={"fill": "#FF0000FF"},
        content={"text": "Continue"},
    )
    return document, group, text, button


def _layer(
    layer_id: str,
    *,
    kind: str = "Image",
    disposition: str = "Native",
    parent_id: str = "",
    position: tuple[float, float] = (50.0, 50.0),
    size: tuple[float, float] = (100.0, 100.0),
    anchor: tuple[float, float] = (0.5, 0.5),
    payload: str = '{"fill":"#FFFFFFFF"}',
    reasons: list[str] | None = None,
    material: dict | None = None,
):
    return {
        "Id": layer_id,
        "ParentId": parent_id,
        "Name": layer_id,
        "Kind": kind,
        "Disposition": disposition,
        "BlockReasons": list(reasons or []),
        "Position": {"X": position[0], "Y": position[1]},
        "Size": {"X": size[0], "Y": size[1]},
        "Scale": {"X": 1.0, "Y": 1.0},
        "Anchor": {"X": anchor[0], "Y": anchor[1]},
        "RotationDegrees": 0.0,
        "Opacity": 1.0,
        "AssetId": "",
        "Material": copy.deepcopy(material or {}),
        "PayloadJson": payload,
    }


def _gradient_material(*, opacity: float = 1.0):
    return {
        "Schema": "tigerstudio.umg.ui_material.v1",
        "Generator": "tiger_ui_gradient_custom_hlsl_v1",
        "Kind": "LinearGradient",
        "CoordinateSpace": "LocalUV",
        "Start": {"X": 0.0, "Y": 0.5},
        "End": {"X": 1.0, "Y": 0.5},
        "Width": {"X": 0.0, "Y": 1.0},
        "Stops": [
            {"Position": 0.0, "Color": "#FF000080"},
            {"Position": 1.0, "Color": "#0000FFFF"},
        ],
        "Opacity": opacity,
    }


def _rounded_card_material(*, size_binding: str | None = None):
    result = {
        "Schema": "tigerstudio.umg.ui_material.v2",
        "Generator": "tiger_ui_rounded_card_sdf_custom_hlsl_v1",
        "Kind": "RoundedCard",
        "CoordinateSpace": "LocalUV",
        "Size": {"X": 240.0, "Y": 120.0},
        "FillKind": "Solid",
        "FillColor": "#3278D4FF",
        "Start": {"X": 0.0, "Y": 0.5},
        "End": {"X": 1.0, "Y": 0.5},
        "Width": {"X": 0.0, "Y": 1.0},
        "Stops": [
            {"Position": 0.0, "Color": "#3278D4FF"},
            {"Position": 1.0, "Color": "#2356A3FF"},
        ],
        "Opacity": 1.0,
        "CornerRadii": {"X": 30.0, "Y": 4.0, "Z": 18.0, "W": 10.0},
        "CornerSmoothing": 0.6,
        "Stroke": {
            "Width": 4.0,
            "Alignment": "Outside",
            "Color": "#E8F2FFFF",
        },
        "DropShadow": {
            "Enabled": True,
            "Color": "#00000099",
            "Offset": {"X": 8.0, "Y": 10.0},
            "Blur": 14.0,
            "Spread": 2.0,
        },
        "InnerShadow": {
            "Enabled": True,
            "Color": "#07162988",
            "Offset": {"X": 1.0, "Y": 3.0},
            "Blur": 5.0,
            "Spread": 1.0,
        },
        "VisualPadding": {
            "Left": 12.0,
            "Top": 10.0,
            "Right": 28.0,
            "Bottom": 30.0,
        },
    }
    if size_binding is not None:
        result["SizeBinding"] = size_binding
    return result


def _tiger_document(
    layers,
    *,
    schema_version: int = 6,
    resources: list[dict] | None = None,
):
    result = {
        "SchemaVersion": schema_version,
        "Provider": "painter",
        "DocumentId": "painter-test",
        "Revision": 7,
        "Width": 400,
        "Height": 300,
        "Resources": copy.deepcopy(resources or []),
        "Layers": layers,
        "Interactions": [],
    }
    if schema_version >= 18:
        result["Components"] = []
        result["ComponentInstances"] = []
    return result


def _schema19_layer_defaults(layer: dict) -> dict:
    result = copy.deepcopy(layer)
    result.setdefault("Visibility", "Visible")
    result.setdefault("PanelKind", "None")
    result.setdefault(
        "FlowSlot",
        {
            "Padding": {
                "Left": 0.0,
                "Top": 0.0,
                "Right": 0.0,
                "Bottom": 0.0,
            },
            "HorizontalAlignment": "Fill",
            "VerticalAlignment": "Fill",
            "SizeRule": "Auto",
            "FillCoefficient": 1.0,
            "Row": 0,
            "Column": 0,
            "RowSpan": 1,
            "ColumnSpan": 1,
        },
    )
    result.setdefault("SpacingStrategy", "Padding")
    result.setdefault("SpacerSizeRule", "Auto")
    result.setdefault("SpacerFillCoefficient", 1.0)
    return result


def test_painter_umg_projection_is_non_mutating_and_uses_adapter_preflight():
    from app.painter_ui_umg_simulator import (
        PAINTER_UMG_SIMULATOR_SCHEMA,
        project_painter_ui_umg_widgets,
    )

    document, _group, _text, _button = _painter_document()
    before = copy.deepcopy(document)

    projection = project_painter_ui_umg_widgets(document)

    assert document == before
    assert projection["schema"] == PAINTER_UMG_SIMULATOR_SCHEMA
    # A plain frame now uses the production-default Auto policy. Its children
    # fit native UOverlaySlot constraints, so the adapter emits schema 17's
    # Overlay/spacing contract instead of silently retaining Canvas.
    assert projection["contract"]["schema_version"] == 17
    assert projection["contract"]["supported_schema_version"] == 20
    assert projection["contract"]["schema_version"] in (
        projection["contract"]["supported_schema_versions"]
    )
    assert projection["contract"]["local_preview"] == "compatibility_proxy"
    assert projection["contract"]["authority"] == "unreal_generation_and_capture"
    assert projection["counts"] == projection["preflight"]["counts"]
    assert projection["ready"] == projection["preflight"]["ok"]
    assert projection["canvas"]["root_widget_class"] == "UCanvasPanel"
    assert projection["document"] is not document
    group = next(
        row for row in projection["document"]["objects"]
        if row["name"] == "Panel"
    )
    classification = projection["widgets_by_id"][group["id"]]
    assert classification["widget_class"] == "UOverlay"
    assert classification["panel_kind"] == "Overlay"
    assert classification["spacing_strategy"] == "Padding"


def test_schema18_component_preview_expands_instances_properties_and_slots():
    from app.painter_ui_umg_simulator import project_tiger_umg_document
    from tools.qa_painter_ui_unreal_umg_component import (
        build_component_contract_evidence,
    )

    evidence = build_component_contract_evidence()
    document = evidence["umg_document"]
    before = copy.deepcopy(document)

    projection = project_tiger_umg_document(document)

    assert document == before
    assert projection["counts"] == evidence["preflight"]["counts"]
    assert projection["component_count"] == 2
    assert projection["component_instance_count"] == 2
    assert projection["component_summary"]["expanded_instance_count"] == 4
    assert projection["ready"] is True

    fixture = evidence["fixture"]
    primary_component_id = evidence["primary_component_id"]
    dependency_component_id = evidence["dependency_component_id"]
    primary_class = f"WBP_TS_C_{primary_component_id.replace('-', '_')}_C"
    dependency_class = (
        f"WBP_TS_C_{dependency_component_id.replace('-', '_')}_C"
    )
    first_id, second_id = fixture["primary_instance_root_ids"]
    widgets = projection["widgets_by_id"]
    objects = {
        row["id"]: row for row in projection["document"]["objects"]
    }

    for instance_id in (first_id, second_id):
        instance = widgets[instance_id]
        assert instance["widget_class"] == primary_class
        assert instance["generated_widget_type"] == "UUserWidget"
        assert instance["generator_action"] == "construct_component_instance"
        nested_id = (
            f"{instance_id}::{fixture['nested_definition_instance_root_id']}"
        )
        assert widgets[nested_id]["widget_class"] == dependency_class
        assert widgets[nested_id]["component_instance"]["nested"] is True

    title_source_id = fixture["title_source_id"]
    assert objects[f"{first_id}::{title_source_id}"]["content"]["text"] == (
        "First card"
    )
    assert objects[f"{second_id}::{title_source_id}"]["content"]["text"] == (
        "Second card"
    )
    second_nested_id = (
        f"{second_id}::{fixture['nested_definition_instance_root_id']}"
    )
    assert widgets[second_nested_id]["runtime_visibility"] == "Collapsed"
    assert objects[second_nested_id]["visible"] is False

    default_slot_source_id = fixture["slot_default_id"]
    assert f"{first_id}::{default_slot_source_id}" in widgets
    assert f"{second_id}::{default_slot_source_id}" not in widgets
    assert fixture["custom_slot_content_id"] in widgets
    assert widgets[fixture["custom_slot_content_id"]][
        "component_slot_content"
    ] == {"instance_id": second_id, "slot_name": "Content"}

    slot_source_id = fixture["slot_source_id"]
    default_slot = widgets[f"{first_id}::{slot_source_id}"]
    custom_slot = widgets[f"{second_id}::{slot_source_id}"]
    assert default_slot["widget_class"] == "UOverlay"
    assert default_slot["component_slot"]["content_mode"] == "default"
    assert custom_slot["component_slot"]["content_mode"] == "custom"
    assert set(custom_slot["component_generated_widgets"].values()) == {
        "UImage",
        "UNamedSlot",
        "UOverlay",
    }

    root_source_id = evidence["primary_component"]["RootLayerId"]
    component_root = widgets[f"{first_id}::{root_source_id}"]
    assert component_root["widget_class"] == "UOverlay"
    assert component_root["component_generated_widgets"][
        f"{first_id}::{root_source_id}#background"
    ] == "UImage"
    assert component_root["component_content_panel_class"] in {
        "UCanvasPanel",
        "UHorizontalBox",
        "UVerticalBox",
        "UGridPanel",
        "UOverlay",
    }


def test_mobile_onboarding_component_visual_fills_its_placement_not_canvas():
    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets

    document, _report = instantiate_ui_template("mobile_onboarding")
    projection = project_painter_ui_umg_widgets(document)
    placement_id = "ui-object-1-button"
    definition_visual_id = f"{placement_id}::{placement_id}"
    widgets = projection["widgets_by_id"]
    objects = {
        row["id"]: row for row in projection["document"]["objects"]
    }

    placement = widgets[placement_id]
    assert placement["rendered"] is True
    assert placement["generator_action"] == "construct_component_instance"
    assert placement["reasons"] == []
    assert placement["widget_class"] == (
        "WBP_TS_C_ui_component_primary_button_C"
    )
    assert not any(
        blocker["object_id"] == placement_id
        and "button_style_missing" in blocker["reasons"]
        for blocker in projection["blockers"]
    )

    assert objects[placement_id]["x"] == 24.0
    assert objects[placement_id]["y"] == 541.0
    assert objects[placement_id]["width"] == 260.0
    assert objects[placement_id]["height"] == 56.0
    assert objects[placement_id]["kind"] == "frame"
    assert objects[placement_id]["style"]["fill"] == "#00000000"

    definition_visual = widgets[definition_visual_id]
    assert definition_visual["effective_parent_id"] == placement_id
    assert definition_visual["slot"]["anchor_minimum"] == {
        "x": 0.0,
        "y": 0.0,
    }
    assert definition_visual["slot"]["anchor_maximum"] == {
        "x": 1.0,
        "y": 1.0,
    }
    assert definition_visual["slot"]["resolved_geometry"] == {
        "x": 0.0,
        "y": 0.0,
        "width": 260.0,
        "height": 56.0,
    }
    assert objects[definition_visual_id]["parent_id"] == placement_id
    assert objects[definition_visual_id]["x"] == 24.0
    assert objects[definition_visual_id]["y"] == 541.0
    assert objects[definition_visual_id]["width"] == 260.0
    assert objects[definition_visual_id]["height"] == 56.0
    background = objects["__tiger_artboard_background"]
    assert background["z_index"] < objects[placement_id]["z_index"]
    assert (
        objects[placement_id]["z_index"]
        < objects[definition_visual_id]["z_index"]
    )
    assert objects[definition_visual_id]["style"]["fill"] == "#5B6CFFFF"


def test_pre_schema18_projection_ignores_component_only_containers():
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    screen = _layer("legacy-screen", kind="Group")
    screen.update(
        {
            "PanelKind": "Canvas",
            "Visibility": "Visible",
            "SpacingStrategy": "Padding",
            "SpacerSizeRule": "Auto",
            "SpacerFillCoefficient": 1.0,
        }
    )
    ignored_root = _layer("ignored-root", kind="Group")
    ignored_root.update(copy.deepcopy(screen))
    ignored_root["Id"] = "ignored-root"
    ignored_root["Name"] = "ignored-root"
    legacy = _tiger_document([screen], schema_version=17)
    legacy["Components"] = [
        {
            "Id": "ignored-component",
            "RootLayerId": "ignored-root",
            "Layers": [ignored_root],
        }
    ]
    legacy["ComponentInstances"] = [
        {
            "Id": "legacy-screen",
            "LayerId": "legacy-screen",
            "ComponentId": "ignored-component",
        }
    ]

    projection = project_tiger_umg_document(legacy)

    assert projection["component_count"] == 0
    assert projection["component_instance_count"] == 0
    assert projection["widgets_by_id"]["legacy-screen"]["widget_class"] == (
        "UCanvasPanel"
    )
    assert not any("::" in row["id"] for row in projection["widgets"])


def test_v10_projection_reports_scrollbox_graph_and_fixed_child_contract():
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    scroll_frame = _layer(
        "scroll-frame",
        kind="Group",
        position=(20.0, 20.0),
        size=(240.0, 160.0),
    )
    scroll_frame.update(
        {
            "PanelKind": "Canvas",
            "ScrollOverflow": "Both",
            "ScrollPosition": "Scroll",
        }
    )
    fixed_child = _layer(
        "fixed-child",
        parent_id="scroll-frame",
        position=(12.0, 12.0),
        size=(80.0, 32.0),
    )
    fixed_child["ScrollPosition"] = "Fixed"

    projection = project_tiger_umg_document(
        _tiger_document([scroll_frame, fixed_child], schema_version=10)
    )

    assert projection["ready"] is True
    widgets = {widget["id"]: widget for widget in projection["widgets"]}
    assert widgets["scroll-frame"]["scroll_overflow"] == "Both"
    assert widgets["scroll-frame"]["generated_container_classes"] == [
        "UOverlay",
        "UScrollBox",
        "UScrollBox",
        "UCanvasPanel",
    ]
    assert widgets["fixed-child"]["scroll_position"] == "Fixed"
    objects = {
        item["id"]: item
        for item in projection["document"]["objects"]
    }
    assert objects["scroll-frame"]["scroll"] == {
        "overflow": "both",
        "position": "scroll",
        "preserve_position": True,
    }
    assert objects["fixed-child"]["scroll"]["position"] == "fixed"


def test_projection_visualizes_native_and_valid_material_layers():
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    document = _tiger_document(
        [
            _layer("native"),
            _layer(
                "material",
                disposition="Material",
                material=_gradient_material(),
            ),
            _layer("baked", disposition="Baked"),
            _layer(
                "blocked",
                disposition="Blocked",
                reasons=["unsupported_effect"],
            ),
        ]
    )

    projection = project_tiger_umg_document(document)

    assert projection["counts"] == {
        "Native": 1,
        "Material": 1,
        "Baked": 1,
        "Blocked": 1,
    }
    assert [row["id"] for row in projection["document"]["objects"]] == [
        "native",
        "material",
    ]
    assert {
        row["id"]: (row["disposition"], row["generator_action"])
        for row in projection["widgets"]
    } == {
        "native": ("Native", "construct"),
        "material": ("Material", "construct_material"),
        "baked": ("Baked", "skip"),
        "blocked": ("Blocked", "skip"),
    }
    assert projection["blockers"] == [
        {
            "object_id": "baked",
            "name": "baked",
            "reasons": ["baked_generation_unavailable"],
        },
        {
            "object_id": "blocked",
            "name": "blocked",
            "reasons": ["unsupported_effect"],
        }
    ]
    assert projection["complete"] is False


def test_projection_rejects_unknown_material_contract_without_false_preview():
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    projection = project_tiger_umg_document(
        _tiger_document([_layer("material", disposition="Material")])
    )

    widget = projection["widgets_by_id"]["material"]
    assert widget["rendered"] is False
    assert widget["generator_action"] == "skip"
    assert "ui_material_schema_unsupported" in widget["reasons"]
    assert projection["document"]["objects"] == []
    assert projection["ready"] is False
    assert projection["complete"] is False


def test_projection_mirrors_canvas_slot_alignment_and_nested_group_coordinates():
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    group = _layer(
        "group",
        kind="Group",
        position=(100.0, 100.0),
        size=(100.0, 100.0),
        payload='{"clip_content":true}',
    )
    child = _layer(
        "child",
        parent_id="group",
        position=(20.0, 20.0),
        size=(20.0, 20.0),
    )

    projection = project_tiger_umg_document(_tiger_document([group, child]))
    objects = {row["id"]: row for row in projection["document"]["objects"]}

    assert objects["group"]["x"] == 50.0
    assert objects["group"]["y"] == 50.0
    assert objects["group"]["clip_content"] is True
    assert objects["child"]["x"] == 60.0
    assert objects["child"]["y"] == 60.0
    assert objects["child"]["parent_id"] == "group"
    assert projection["widgets_by_id"]["group"]["widget_class"] == "UCanvasPanel"
    assert projection["widgets_by_id"]["child"]["widget_class"] == "UImage"
    assert projection["widgets_by_id"]["group"]["slot_kind"] == "CanvasPanelSlot"
    assert projection["widgets_by_id"]["child"]["slot_kind"] == "CanvasPanelSlot"
    assert projection["widgets_by_id"]["child"]["parent_panel_kind"] == "Canvas"
    assert projection["widgets_by_id"]["child"]["proxy_accuracy"] == "exact_affine"


def test_projection_reports_the_concrete_non_canvas_parent_slot_kind() -> None:
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    group = _layer("flow", kind="Group")
    group["PanelKind"] = "Horizontal"
    child = _layer("flow-child", parent_id="flow")

    projection = project_tiger_umg_document(
        _tiger_document([group, child], schema_version=7)
    )
    widgets = projection["widgets_by_id"]

    assert widgets["flow"]["slot_kind"] == "CanvasPanelSlot"
    assert widgets["flow-child"]["slot_kind"] == "HorizontalBoxSlot"
    assert widgets["flow-child"]["parent_panel_kind"] == "Horizontal"


def test_schema17_overlay_projects_native_overlay_slot_metadata() -> None:
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    group = _layer("overlay", kind="Group", size=(300.0, 180.0))
    group.update(
        {
            "PanelKind": "Overlay",
            "Visibility": "Visible",
            "SpacingStrategy": "Padding",
            "SpacerSizeRule": "Auto",
            "SpacerFillCoefficient": 1.0,
        }
    )
    child = _layer(
        "overlay-child",
        parent_id="overlay",
        size=(80.0, 50.0),
    )
    child.update(
        {
            "Visibility": "Visible",
            "FlowSlot": {
                "Padding": {
                    "Left": 20.0,
                    "Top": 30.0,
                    "Right": 0.0,
                    "Bottom": 0.0,
                },
                "HorizontalAlignment": "Left",
                "VerticalAlignment": "Top",
                "SizeRule": "Auto",
                "FillCoefficient": 1.0,
            },
        }
    )

    projection = project_tiger_umg_document(
        _tiger_document([group, child], schema_version=17)
    )
    widgets = projection["widgets_by_id"]

    assert widgets["overlay"]["widget_class"] == "UOverlay"
    assert widgets["overlay-child"]["slot_kind"] == "OverlaySlot"
    assert widgets["overlay-child"]["parent_panel_kind"] == "Overlay"
    assert widgets["overlay-child"]["slot"]["padding"] == {
        "left": 20.0,
        "top": 30.0,
        "right": 0.0,
        "bottom": 0.0,
    }
    assert widgets["overlay-child"]["slot"]["horizontal_alignment"] == "Left"
    assert widgets["overlay-child"]["slot"]["vertical_alignment"] == "Top"


def test_projection_exposes_only_properties_consumed_by_current_cpp_generator():
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets

    document, group, text, button = _painter_document()
    projection = project_painter_ui_umg_widgets(document)
    widgets = projection["widgets_by_id"]
    objects = {row["id"]: row for row in projection["document"]["objects"]}

    assert widgets[group["id"]]["widget_class"] == "UOverlay"
    assert widgets[group["id"]]["panel_kind"] == "Overlay"
    assert widgets[group["id"]]["spacing_strategy"] == "Padding"
    assert widgets[group["id"]]["consumed_properties"][-5:] == [
        "PayloadJson.clip_content",
        "SpacingStrategy",
        "SpacerSizeRule",
        "SpacerFillCoefficient",
        "Visibility",
    ]
    assert widgets[text["id"]]["widget_class"] == "UTextBlock"
    assert set(widgets[text["id"]]["consumed_properties"]) >= {
        "PayloadJson.text",
        "PayloadJson.fill",
        "PayloadJson.font_size",
    }
    assert widgets[button["id"]]["widget_class"] == "UTigerStudioButton"
    assert "PayloadJson.source_params" not in widgets[button["id"]][
        "consumed_properties"
    ]
    # Schema 16 consumes Painter's typed normal button state directly.
    assert objects[button["id"]]["style"]["fill"] == "#FF0000FF"
    assert "ButtonStyle.Normal" in widgets[button["id"]][
        "consumed_properties"
    ]
    assert objects[text["id"]]["content"]["text"] == "Tiger"
    assert objects[text["id"]]["style"]["text_color"] == "#22AAEEFF"
    assert objects[text["id"]]["style"]["font_size"] == 20.0


def test_painter_gradient_material_is_rendered_as_compatibility_proxy():
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets

    document = create_ui_document(320, 180)
    document, gradient = add_ui_object(
        document,
        kind="rectangle",
        name="Gradient",
        x=20,
        y=20,
        width=100,
        height=80,
        style={
            "fills": [
                {
                    "type": "linear",
                    "opacity": 0.5,
                    "gradient": {
                        "stops": [
                            {"position": 0.0, "color": "#FF0000FF"},
                            {"position": 1.0, "color": "#0000FFFF"},
                        ]
                    },
                }
            ]
        },
    )

    projection = project_painter_ui_umg_widgets(document)

    diagnostic = projection["widgets_by_id"][gradient["id"]]
    assert diagnostic["disposition"] == "Material"
    assert diagnostic["rendered"] is True
    assert diagnostic["generator_action"] == "construct_material"
    assert diagnostic["reasons"] == []
    proxy = next(
        row
        for row in projection["document"]["objects"]
        if row["id"] == gradient["id"]
    )
    assert proxy["style"]["fill_gradient"]["type"] == "linear"
    assert proxy["style"]["fill_gradient"]["stops"] == [
        {"position": 0.0, "color": "#FF000080"},
        {"position": 1.0, "color": "#0000FF80"},
    ]
    assert proxy["style"]["fills"][0]["type"] == "linear"
    assert proxy["style"]["fills"][0]["gradient"]["stops"] == [
        {"position": 0.0, "color": "#FF000080"},
        {"position": 1.0, "color": "#0000FF80"},
    ]

    # Regression: normalized Painter styles always contain ``fills`` and the
    # renderer gives that list precedence over legacy ``fill_gradient``. The
    # UMG proxy therefore has to carry a canonical gradient paint, otherwise
    # the right-hand preview resolves to its white fallback fill.
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter

    from app.painter_ui_style_renderer import ui_fill_brush

    surface = QImage(100, 20, QImage.Format.Format_ARGB32_Premultiplied)
    surface.fill(Qt.GlobalColor.transparent)
    painter = QPainter(surface)
    rect = QRectF(0.0, 0.0, 100.0, 20.0)
    painter.fillRect(rect, ui_fill_brush(proxy["style"], rect))
    painter.end()
    left = surface.pixelColor(5, 10)
    right = surface.pixelColor(95, 10)
    assert left.red() > left.blue()
    assert right.blue() > right.red()
    assert left != right
    assert projection["ready"] is True
    assert projection["complete"] is True


def test_v8_rounded_card_material_preserves_full_appearance_proxy() -> None:
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    projection = project_tiger_umg_document(
        _tiger_document(
            [
                _layer(
                    "rounded-card",
                    disposition="Material",
                    size=(240.0, 120.0),
                    material=_rounded_card_material(),
                )
            ],
            schema_version=8,
        )
    )

    widget = projection["widgets_by_id"]["rounded-card"]
    assert widget["rendered"] is True
    assert widget["generator_action"] == "construct_material"
    assert widget["reasons"] == []
    assert widget["material"] == _rounded_card_material()
    assert widget["widget_class"] == "UCanvasPanel"
    assert widget["visual_widget_id"] == "rounded-card_Visual"
    assert widget["generated_children"] == ["rounded-card_Visual"]
    assert not any(
        value.startswith("Material.")
        for value in widget["consumed_properties"]
    )

    visual = projection["widgets_by_id"]["rounded-card_Visual"]
    assert visual["synthetic"] is True
    assert visual["source_layer_id"] == "rounded-card"
    assert visual["widget_class"] == "UImage"
    assert visual["effective_parent_id"] == "rounded-card"
    assert visual["generator_action"] == "construct_material_visual"
    assert set(visual["consumed_properties"]) >= {
        "Material.FillColor",
        "Material.CornerRadii",
        "Material.CornerSmoothing",
        "Material.Stroke",
        "Material.DropShadow",
        "Material.InnerShadow",
        "Material.VisualPadding",
        "DesiredSizeOverride",
        "CanvasSlot.Position",
        "CanvasSlot.Size",
    }
    assert visual["slot"]["position"] == {"x": -12.0, "y": -10.0}
    assert visual["slot"]["size"] == {"x": 280.0, "y": 160.0}
    assert visual["slot"]["alignment"] == {"x": 0.0, "y": 0.0}
    assert visual["slot"]["auto_size"] is False

    proxies = {row["id"]: row for row in projection["document"]["objects"]}
    host_proxy = proxies["rounded-card"]
    proxy = proxies["rounded-card_Visual"]
    style = proxy["style"]
    assert host_proxy["kind"] == "frame"
    assert host_proxy["style"]["fill"] == "#00000000"
    assert host_proxy["clip_content"] is False
    assert proxy["kind"] == "rectangle"
    assert proxy["parent_id"] == "rounded-card"
    assert style["fill"] == "#3278D4FF"
    assert style["corner_radii"] == {
        "top_left": 30.0,
        "top_right": 4.0,
        "bottom_right": 18.0,
        "bottom_left": 10.0,
    }
    assert style["corner_smoothing"] == 0.6
    assert style["stroke"] == "#E8F2FFFF"
    assert style["stroke_width"] == 4.0
    assert style["stroke_align"] == "outside"
    assert {row["type"] for row in style["effects"]} == {
        "drop_shadow",
        "inner_shadow",
    }
    assert visual["material_preview_style"]["corner_radii"] == (
        style["corner_radii"]
    )
    assert projection["ready"] is True
    assert projection["complete"] is True


def test_schema19_widget_geometry_uses_live_host_size_in_local_umg_view() -> None:
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    layer = _layer(
        "responsive-card",
        disposition="Material",
        size=(240.0, 120.0),
        material=_rounded_card_material(size_binding="WidgetGeometry"),
    )
    layer["CanvasSlot"] = {
        "AnchorMinimum": {"X": 0.0, "Y": 0.0},
        "AnchorMaximum": {"X": 1.0, "Y": 1.0},
        "Offsets": {
            "Left": 20.0,
            "Top": 30.0,
            "Right": 40.0,
            "Bottom": 50.0,
        },
        "Alignment": {"X": 0.0, "Y": 0.0},
    }
    layer["RenderTransformPivot"] = {"X": 0.5, "Y": 0.5}

    projection = project_tiger_umg_document(
        _tiger_document([_schema19_layer_defaults(layer)], schema_version=19)
    )
    host = projection["widgets_by_id"]["responsive-card"]
    visual = projection["widgets_by_id"]["responsive-card_Visual"]

    assert host["size_binding"] == "WidgetGeometry"
    assert "Material.SizeBinding" in host["consumed_properties"]
    assert host["fixed_material_size"] == {"x": 240.0, "y": 120.0}
    assert host["live_material_size"] == {"x": 340.0, "y": 220.0}
    assert visual["live_material_size"] == {"x": 340.0, "y": 220.0}
    assert visual["runtime_material_parameters"]["CardSize"] == {
        "x": 340.0,
        "y": 220.0,
    }
    assert visual["slot"]["position"] == {"x": -12.0, "y": -10.0}
    assert visual["slot"]["size"] == {"x": 380.0, "y": 260.0}
    assert "Material.SizeBinding" in visual["consumed_properties"]
    visual_proxy = next(
        row
        for row in projection["document"]["objects"]
        if row["id"] == "responsive-card_Visual"
    )
    assert visual_proxy["width"] == 380.0
    assert visual_proxy["height"] == 260.0


def test_schema19_fixed_size_preserves_authored_rounded_card_surface() -> None:
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    layer = _layer(
        "fixed-card",
        disposition="Material",
        size=(300.0, 160.0),
        material=_rounded_card_material(size_binding="FixedSize"),
    )
    layer["CanvasSlot"] = {
        "AnchorMinimum": {"X": 0.0, "Y": 0.0},
        "AnchorMaximum": {"X": 0.0, "Y": 0.0},
        "Offsets": {
            "Left": 50.0,
            "Top": 50.0,
            "Right": 300.0,
            "Bottom": 160.0,
        },
        "Alignment": {"X": 0.0, "Y": 0.0},
    }
    layer["RenderTransformPivot"] = {"X": 0.5, "Y": 0.5}
    projection = project_tiger_umg_document(
        _tiger_document([_schema19_layer_defaults(layer)], schema_version=19)
    )
    visual = projection["widgets_by_id"]["fixed-card_Visual"]

    assert visual["fixed_material_size"] == {"x": 240.0, "y": 120.0}
    assert visual["live_material_size"] == {"x": 240.0, "y": 120.0}
    assert visual["slot"]["size"] == {"x": 280.0, "y": 160.0}


def test_pre_v8_rounded_card_is_blocked_without_false_preview() -> None:
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    projection = project_tiger_umg_document(
        _tiger_document(
            [
                _layer(
                    "rounded-card",
                    disposition="Material",
                    material=_rounded_card_material(),
                )
            ],
            schema_version=7,
        )
    )

    widget = projection["widgets_by_id"]["rounded-card"]
    assert widget["rendered"] is False
    assert widget["generator_action"] == "skip"
    assert widget["reasons"] == ["ui_material_requires_schema_8"]
    assert projection["document"]["objects"] == []
    assert projection["ready"] is False


def test_rounded_card_runtime_resize_blocker_is_preserved_verbatim() -> None:
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    reason = "rounded_card_runtime_resize_requires_dynamic_size_binding"
    layer = _layer(
        "responsive-card",
        disposition="Blocked",
        reasons=[reason],
        material=_rounded_card_material(),
    )
    layer["CanvasSlot"] = {
        "AnchorMinimum": {"X": 0.0, "Y": 0.0},
        "AnchorMaximum": {"X": 1.0, "Y": 0.0},
        "Offsets": {
            "Left": 16.0,
            "Top": 24.0,
            "Right": 16.0,
            "Bottom": 120.0,
        },
        "Alignment": {"X": 0.0, "Y": 0.0},
    }

    projection = project_tiger_umg_document(
        _tiger_document([layer], schema_version=9)
    )

    widget = projection["widgets_by_id"]["responsive-card"]
    assert widget["disposition"] == "Blocked"
    assert widget["rendered"] is False
    assert widget["generator_action"] == "skip"
    assert widget["reasons"] == [reason]
    assert projection["blockers"] == [
        {
            "object_id": "responsive-card",
            "name": "responsive-card",
            "reasons": [reason],
        }
    ]
    assert projection["unrendered"][0]["reasons"] == [reason]
    assert projection["document"]["objects"] == []


def test_v5_projection_uses_real_canvas_anchors_offsets_and_separate_pivot():
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    layer = _layer(
        "anchored",
        position=(320.0, 240.0),
        size=(100.0, 50.0),
        anchor=(0.5, 0.5),
    )
    layer.update(
        {
            "CanvasSlot": {
                "AnchorMinimum": {"X": 1.0, "Y": 1.0},
                "AnchorMaximum": {"X": 1.0, "Y": 1.0},
                "Offsets": {
                    "Left": -80.0,
                    "Top": -60.0,
                    "Right": 100.0,
                    "Bottom": 50.0,
                },
                "Alignment": {"X": 0.2, "Y": 0.8},
            },
            "RenderTransformPivot": {"X": 0.25, "Y": 0.75},
        }
    )

    projection = project_tiger_umg_document(
        _tiger_document([layer], schema_version=5)
    )
    row = projection["document"]["objects"][0]
    widget = projection["widgets_by_id"]["anchored"]

    assert row["x"] == 300.0
    assert row["y"] == 200.0
    assert row["width"] == 100.0
    assert row["height"] == 50.0
    assert row["constraints"]["pivot_x"] == 0.25
    assert row["constraints"]["pivot_y"] == 0.75
    assert widget["slot"]["anchor_minimum"] == {"x": 1.0, "y": 1.0}
    assert widget["slot"]["anchor_maximum"] == {"x": 1.0, "y": 1.0}
    assert widget["slot"]["alignment"] == {"x": 0.2, "y": 0.8}
    assert widget["render_transform_pivot"] == {"x": 0.25, "y": 0.75}
    assert "CanvasSlot.AnchorMinimum" in widget["consumed_properties"]
    assert "Anchor" not in widget["consumed_properties"]


def test_v5_projection_resolves_stretched_canvas_slot_size():
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    layer = _layer("stretch", size=(1.0, 1.0))
    layer.update(
        {
            "CanvasSlot": {
                "AnchorMinimum": {"X": 0.0, "Y": 0.0},
                "AnchorMaximum": {"X": 1.0, "Y": 1.0},
                "Offsets": {
                    "Left": 20.0,
                    "Top": 30.0,
                    "Right": 40.0,
                    "Bottom": 50.0,
                },
                "Alignment": {"X": 0.5, "Y": 0.5},
            },
            "RenderTransformPivot": {"X": 0.5, "Y": 0.5},
        }
    )

    projection = project_tiger_umg_document(
        _tiger_document([layer], schema_version=5)
    )
    row = projection["document"]["objects"][0]

    assert row["x"] == 20.0
    assert row["y"] == 30.0
    assert row["width"] == 340.0
    assert row["height"] == 220.0


def test_v4_v5_material_is_not_previewed_but_native_remains_compatible():
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    for schema_version in (4, 5):
        native_only = project_tiger_umg_document(
            _tiger_document(
                [_layer("native")],
                schema_version=schema_version,
            )
        )
        assert [
            row["id"] for row in native_only["document"]["objects"]
        ] == ["native"]
        assert native_only["widgets_by_id"]["native"]["rendered"] is True
        assert native_only["ready"] is True
        assert native_only["complete"] is True

        mixed = project_tiger_umg_document(
            _tiger_document(
                [
                    _layer("native"),
                    _layer(
                        "gradient",
                        disposition="Material",
                        material=_gradient_material(),
                    ),
                ],
                schema_version=schema_version,
            )
        )
        assert [row["id"] for row in mixed["document"]["objects"]] == [
            "native"
        ]
        material_widget = mixed["widgets_by_id"]["gradient"]
        assert material_widget["rendered"] is False
        assert material_widget["generator_action"] == "skip"
        assert material_widget["reasons"] == [
            "ui_material_requires_schema_6"
        ]
        assert mixed["blockers"] == [
            {
                "object_id": "gradient",
                "name": "gradient",
                "reasons": ["ui_material_requires_schema_6"],
            }
        ]
        assert mixed["ready"] is False
        assert mixed["complete"] is False


def test_v11_image_fill_projection_renders_modes_and_keeps_ui_semantics(
    tmp_path,
) -> None:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_image_renderer import draw_ui_image
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    texture_path = tmp_path / "image-fill.png"
    texture = QImage(8, 4, QImage.Format.Format_ARGB32)
    for y in range(texture.height()):
        for x in range(texture.width()):
            texture.setPixelColor(
                x,
                y,
                QColor("#EF4444") if x < 4 else QColor("#2563EB"),
            )
    assert texture.save(str(texture_path))
    resource = {
        "Id": "texture-1",
        "Kind": "texture",
        "SourcePath": str(texture_path),
    }

    def image_fill(mode: str, *, radii=(0.0, 0.0, 0.0, 0.0)):
        return {
            "AssetId": "texture-1",
            "Mode": mode,
            "FocalPoint": {"X": 0.75, "Y": 0.5},
            "TileScale": 1.0,
            "Crop": {
                "Enabled": False,
                "Units": "Normalized",
                "X": 0.0,
                "Y": 0.0,
                "Width": 1.0,
                "Height": 1.0,
            },
            "NineSlice": {
                "Enabled": False,
                "Units": "Pixels",
                "Left": 0.0,
                "Top": 0.0,
                "Right": 0.0,
                "Bottom": 0.0,
            },
            "CornerRadii": dict(zip(("X", "Y", "Z", "W"), radii)),
            "Opacity": 1.0,
            "Tint": "#FFFFFFFF",
        }

    frame = _layer(
        "panel",
        kind="Group",
        position=(10.0, 10.0),
        size=(180.0, 120.0),
        payload='{"source_kind":"frame","clip_content":true}',
    )
    frame["AssetId"] = "texture-1"
    frame["ImageFill"] = image_fill("Fit", radii=(12.0, 8.0, 4.0, 2.0))
    child = _layer(
        "panel-label",
        kind="Text",
        parent_id="panel",
        position=(12.0, 12.0),
        size=(100.0, 24.0),
        payload='{"text":"Panel child","fill":"#FFFFFFFF","font_size":16}',
    )
    shape = _layer(
        "filled-shape",
        position=(210.0, 10.0),
        size=(80.0, 80.0),
        payload='{"source_kind":"rectangle","fill":"#FFFFFFFF"}',
    )
    shape["AssetId"] = "texture-1"
    shape["ImageFill"] = image_fill("Fill")
    button = _layer(
        "continue",
        kind="Button",
        position=(210.0, 110.0),
        size=(120.0, 48.0),
        payload='{"source_kind":"button","text":"Continue"}',
    )
    button["AssetId"] = "texture-1"
    button["ImageFill"] = image_fill("Stretch", radii=(6.0, 6.0, 6.0, 6.0))

    projection = project_tiger_umg_document(
        _tiger_document(
            [frame, child, shape, button],
            schema_version=11,
            resources=[resource],
        )
    )

    assert projection["ready"] is True
    assert projection["resource_warnings"] == []
    objects = {
        row["id"]: row for row in projection["document"]["objects"]
    }
    assert objects["panel"]["kind"] == "frame"
    assert objects["panel"]["content"]["image_fit"] == "fit"
    assert objects["panel-label"]["parent_id"] == "panel"
    assert objects["filled-shape"]["kind"] == "rectangle"
    assert objects["filled-shape"]["content"]["image_fit"] == "fill"
    assert objects["continue"]["content"]["image_fit"] == "stretch"
    assert objects["continue"]["content"]["text"] == "Continue"
    assert objects["panel"]["style"]["corner_radii"] == {
        "top_left": 12.0,
        "top_right": 8.0,
        "bottom_right": 4.0,
        "bottom_left": 2.0,
    }
    assert [row["id"] for row in projection["document"]["objects"]].index(
        "panel"
    ) < [row["id"] for row in projection["document"]["objects"]].index(
        "panel-label"
    )

    widget = projection["widgets_by_id"]["continue"]
    assert widget["image_fill"]["status"] == "ready"
    assert "ImageFill.Mode" in widget["consumed_properties"]
    assert "ImageFill.CornerRadii" in widget["consumed_properties"]

    def rendered(content: dict) -> QImage:
        result = QImage(20, 20, QImage.Format.Format_ARGB32)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        assert draw_ui_image(painter, QRectF(0.0, 0.0, 20.0, 20.0), content)
        painter.end()
        return result

    fit_image = rendered(objects["panel"]["content"])
    fill_image = rendered(objects["filled-shape"]["content"])
    stretch_image = rendered(objects["continue"]["content"])
    assert fit_image.pixelColor(10, 0).alpha() == 0
    assert fit_image.pixelColor(0, 5).alpha() == 0
    assert fit_image.pixelColor(5, 5).alpha() > 0
    assert fit_image.pixelColor(10, 10).alpha() > 0
    assert fill_image.pixelColor(10, 0).alpha() > 0
    assert stretch_image.pixelColor(10, 0).alpha() > 0


def test_image_renderer_matches_crop_tile_nine_slice_and_tint_contract(
    tmp_path,
) -> None:
    from PySide6.QtCore import QRectF, QSizeF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_image_renderer import draw_ui_image, image_draw_plan

    target = QRectF(0.0, 0.0, 40.0, 40.0)
    crop_plan = image_draw_plan(
        QSizeF(100.0, 50.0),
        target,
        {
            "image_fit": "crop",
            "image_crop": {
                "Enabled": True,
                "Units": "Normalized",
                "X": 0.25,
                "Y": 0.2,
                "Width": 0.5,
                "Height": 0.6,
            },
        },
    )
    assert len(crop_plan) == 1
    assert crop_plan[0][1] == QRectF(25.0, 10.0, 50.0, 30.0)

    base_crop = {
        "Enabled": True,
        "Units": "Normalized",
        "X": 0.25,
        "Y": 0.0,
        "Width": 0.5,
        "Height": 1.0,
    }
    fit_crop_plan = image_draw_plan(
        QSizeF(100.0, 50.0),
        QRectF(0.0, 0.0, 80.0, 40.0),
        {"image_fit": "fit", "image_crop": base_crop},
    )
    assert fit_crop_plan == [
        (QRectF(20.0, 0.0, 40.0, 40.0), QRectF(25.0, 0.0, 50.0, 50.0))
    ]
    fill_crop_plan = image_draw_plan(
        QSizeF(100.0, 50.0),
        QRectF(0.0, 0.0, 80.0, 40.0),
        {
            "image_fit": "fill",
            "image_crop": base_crop,
            "focal_x": 0.5,
            "focal_y": 1.0,
        },
    )
    assert fill_crop_plan == [
        (QRectF(0.0, 0.0, 80.0, 40.0), QRectF(25.0, 25.0, 50.0, 25.0))
    ]
    stretch_crop_plan = image_draw_plan(
        QSizeF(100.0, 50.0),
        QRectF(0.0, 0.0, 80.0, 40.0),
        {"image_fit": "stretch", "image_crop": base_crop},
    )
    assert stretch_crop_plan == [
        (QRectF(0.0, 0.0, 80.0, 40.0), QRectF(25.0, 0.0, 50.0, 50.0))
    ]
    tile_crop_plan = image_draw_plan(
        QSizeF(100.0, 50.0),
        QRectF(0.0, 0.0, 80.0, 40.0),
        {
            "image_fit": "tile",
            "image_crop": base_crop,
            "tile_scale": 0.5,
        },
    )
    assert len(tile_crop_plan) == 8
    assert tile_crop_plan[0] == (
        QRectF(0.0, 0.0, 25.0, 25.0),
        QRectF(25.0, 0.0, 50.0, 50.0),
    )

    tile_plan = image_draw_plan(
        QSizeF(8.0, 4.0),
        target,
        {"image_fit": "tile", "tile_scale": 2.0},
    )
    assert len(tile_plan) == 15
    nine_slice = {
        "nine_slice_enabled": True,
        "nine_slice": {"left": 2, "top": 1, "right": 2, "bottom": 1},
    }
    assert len(
        image_draw_plan(
            QSizeF(8.0, 4.0),
            target,
            {**nine_slice, "image_fit": "stretch"},
        )
    ) == 9
    assert len(
        image_draw_plan(
            QSizeF(8.0, 4.0),
            target,
            {**nine_slice, "image_fit": "fill"},
        )
    ) == 9

    texture_path = tmp_path / "white.png"
    texture = QImage(2, 2, QImage.Format.Format_ARGB32)
    texture.fill(QColor("white"))
    assert texture.save(str(texture_path))
    result = QImage(4, 4, QImage.Format.Format_ARGB32)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    assert draw_ui_image(
        painter,
        QRectF(0.0, 0.0, 4.0, 4.0),
        {
            "source_path": str(texture_path),
            "image_fit": "stretch",
            "image_opacity": 0.5,
            "image_tint": "#FF000080",
        },
    )
    painter.end()
    pixel = result.pixelColor(2, 2)
    assert pixel.red() > 240
    assert pixel.green() < 20
    assert 50 <= pixel.alpha() <= 80

    logical_path = tmp_path / "logical-source-size.png"
    logical_source = QImage(4, 1, QImage.Format.Format_ARGB32)
    logical_source.setPixelColor(0, 0, QColor("#EF4444"))
    logical_source.setPixelColor(1, 0, QColor("#EF4444"))
    logical_source.setPixelColor(2, 0, QColor("#2563EB"))
    logical_source.setPixelColor(3, 0, QColor("#2563EB"))
    assert logical_source.save(str(logical_path))
    logical_result = QImage(4, 2, QImage.Format.Format_ARGB32)
    logical_result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(logical_result)
    assert draw_ui_image(
        painter,
        QRectF(0.0, 0.0, 4.0, 2.0),
        {
            "source_path": str(logical_path),
            "image_fit": "stretch",
            "original_width": 100,
            "original_height": 25,
            "image_crop": {
                "Enabled": True,
                "Units": "Pixels",
                "X": 50,
                "Y": 0,
                "Width": 50,
                "Height": 25,
            },
        },
    )
    painter.end()
    logical_pixel = logical_result.pixelColor(2, 1)
    assert logical_pixel.blue() > 220
    assert logical_pixel.red() < 80


def test_image_fill_failures_are_readable_and_block_reasons_stay_verbatim(
    tmp_path,
) -> None:
    from PySide6.QtGui import QColor, QImage

    from app.painter_ui_umg_simulator import project_tiger_umg_document

    texture_path = tmp_path / "valid.png"
    image = QImage(2, 2, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    assert image.save(str(texture_path))
    resources = [
        {
            "Id": "valid-texture",
            "Kind": "texture",
            "SourcePath": str(texture_path),
        }
    ]
    missing = _layer(
        "missing-image",
        payload='{"source_kind":"rectangle"}',
    )
    missing["AssetId"] = "ghost-texture"
    missing["ImageFill"] = {
        "AssetId": "ghost-texture",
        "Mode": "Fit",
    }
    unsupported = _layer(
        "unsupported-mode",
        payload='{"source_kind":"rectangle"}',
    )
    unsupported["AssetId"] = "valid-texture"
    unsupported["ImageFill"] = {
        "AssetId": "valid-texture",
        "Mode": "Warp",
    }
    reason = "image_fill_mode_unsupported:warp"
    blocked = _layer(
        "blocked-mode",
        disposition="Blocked",
        reasons=[reason],
        payload='{"source_kind":"rectangle"}',
    )
    blocked["AssetId"] = "valid-texture"
    blocked["ImageFill"] = {
        "AssetId": "valid-texture",
        "Mode": "Warp",
    }

    projection = project_tiger_umg_document(
        _tiger_document(
            [missing, unsupported, blocked],
            schema_version=11,
            resources=resources,
        )
    )

    assert projection["ready"] is False
    warnings = {
        row["object_id"]: row for row in projection["resource_warnings"]
    }
    assert warnings["missing-image"]["status"] == "missing_resource"
    assert "ghost-texture" in warnings["missing-image"]["message"]
    assert warnings["unsupported-mode"]["status"] == "unsupported_fit"
    assert "Warp" in warnings["unsupported-mode"]["message"]
    objects = {
        row["id"]: row for row in projection["document"]["objects"]
    }
    assert objects["missing-image"]["content"]["image_preview_status"] == (
        "missing_resource"
    )
    assert objects["unsupported-mode"]["content"]["image_fit"] == "fit"
    blocked_widget = projection["widgets_by_id"]["blocked-mode"]
    assert blocked_widget["reasons"] == [reason]
    assert projection["unrendered"][0]["reasons"] == [reason]


def _blocked_painter_document():
    """Return a document with one Native and one Blocked leaf."""
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(400, 300, name="HUD")
    document, kept = add_ui_object(
        document,
        kind="rectangle",
        name="Card",
        x=10,
        y=10,
        width=100,
        height=60,
        style={"fill": "#3366FFFF"},
    )
    document, blocked = add_ui_object(
        document,
        kind="rectangle",
        name="Layered",
        x=150,
        y=40,
        width=120,
        height=80,
        style={
            "fills": [
                {
                    "type": "solid",
                    "visible": True,
                    "opacity": 1.0,
                    "color": "#FF0000FF",
                },
                {
                    "type": "solid",
                    "visible": True,
                    "opacity": 1.0,
                    "color": "#00FF00FF",
                },
            ]
        },
    )
    return document, kept, blocked


def test_umg_projection_omits_unrendered_layers_without_the_reference_flag():
    from app.painter_ui_umg_simulator import (
        UMG_REFERENCE_ID_PREFIX,
        project_painter_ui_umg_widgets,
    )

    document, _kept, blocked = _blocked_painter_document()
    artboard_id = document["artboards"][0]["id"]

    projection = project_painter_ui_umg_widgets(document, artboard_id=artboard_id)

    assert projection["reference_object_ids"] == []
    object_ids = {row["id"] for row in projection["document"]["objects"]}
    assert blocked["id"] not in object_ids
    assert not any(
        str(row["id"]).startswith(UMG_REFERENCE_ID_PREFIX)
        for row in projection["document"]["objects"]
    )


def test_umg_projection_reference_rows_restore_blocked_layers_as_marked_stand_ins():
    from app.painter_ui_umg_simulator import (
        UMG_REFERENCE_ID_PREFIX,
        UMG_REFERENCE_ONLY_KEY,
        UMG_REFERENCE_OPACITY,
        project_painter_ui_umg_widgets,
    )

    document, _kept, blocked = _blocked_painter_document()
    artboard_id = document["artboards"][0]["id"]

    projection = project_painter_ui_umg_widgets(
        document,
        artboard_id=artboard_id,
        reference_unrendered=True,
    )

    reference_id = f"{UMG_REFERENCE_ID_PREFIX}{blocked['id']}"
    assert projection["reference_object_ids"] == [reference_id]
    objects = {row["id"]: row for row in projection["document"]["objects"]}
    row = objects[reference_id]
    # The stand-in keeps the source geometry exactly: Painter coordinates are
    # artboard-absolute, so flattening the parent chain cannot move it.
    assert (row["x"], row["y"], row["width"], row["height"]) == (
        blocked["x"],
        blocked["y"],
        blocked["width"],
        blocked["height"],
    )
    assert row["parent_id"] == ""
    assert row["locked"] is True
    assert row["clip_content"] is False
    assert row["opacity"] == UMG_REFERENCE_OPACITY
    marker = row["content"][UMG_REFERENCE_ONLY_KEY]
    assert marker["source_object_id"] == blocked["id"]
    assert marker["disposition"] == "Blocked"
    assert marker["reasons"] == [
        "multiple_fills_require_umg_material_or_bake"
    ]
    # The UMG contract exports the artboard background as a full-size Image, so
    # a reference row below it would be invisible.
    other_z = [
        int(other["z_index"])
        for other in projection["document"]["objects"]
        if other["id"] != reference_id
    ]
    assert int(row["z_index"]) > max(other_z)


def test_umg_projection_reference_flag_never_changes_readiness_or_counts():
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets

    document, _kept, _blocked = _blocked_painter_document()
    artboard_id = document["artboards"][0]["id"]

    plain = project_painter_ui_umg_widgets(document, artboard_id=artboard_id)
    referenced = project_painter_ui_umg_widgets(
        document,
        artboard_id=artboard_id,
        reference_unrendered=True,
    )

    for key in (
        "counts",
        "blockers",
        "unrendered",
        "widgets",
        "widgets_by_id",
        "ready",
        "complete",
        "preflight",
    ):
        assert referenced[key] == plain[key], key


def test_umg_projection_reference_rows_skip_layers_without_a_painter_twin():
    """Generated component-definition layers have no source row to stand in for."""
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets

    document, _kept, blocked = _blocked_painter_document()
    artboard_id = document["artboards"][0]["id"]

    projection = project_painter_ui_umg_widgets(
        document,
        artboard_id=artboard_id,
        reference_unrendered=True,
    )

    source_ids = {row["id"] for row in document["objects"]}
    for entry in projection["unrendered"]:
        expected = entry["object_id"] in source_ids
        produced = any(
            row.endswith(f"::{entry['object_id']}")
            for row in projection["reference_object_ids"]
        )
        assert produced is expected

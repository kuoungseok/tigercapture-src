from __future__ import annotations

import copy
import json

import pytest


_CURRENT_UMG_LAYER_KEYS = {
    "Id",
    "ParentId",
    "Name",
    "Kind",
    "Disposition",
    "BlockReasons",
    "Position",
    "Size",
    "Scale",
    "Anchor",
    "CanvasSlot",
    "PanelKind",
    "FlowSlot",
    "ScrollOverflow",
    "ScrollPosition",
    "Visibility",
    "RenderTransformPivot",
    "RotationDegrees",
    "Opacity",
    "AssetId",
    "ImageFill",
    "Material",
    "Flipbook",
    "ButtonStyle",
    "PayloadJson",
}


def _native_button_layer(*, button_style: dict | None = None) -> dict:
    row = {
        "Id": "cta",
        "ParentId": "",
        "Name": "Continue",
        "Kind": "Button",
        "Disposition": "Native",
        "BlockReasons": [],
        "Position": {"X": 50.0, "Y": 40.0},
        "Size": {"X": 160.0, "Y": 52.0},
        "Scale": {"X": 1.0, "Y": 1.0},
        "Anchor": {"X": 0.5, "Y": 0.5},
        "RotationDegrees": 0.0,
        "Opacity": 1.0,
        "Visibility": "Visible",
        "AssetId": "",
        "ImageFill": {},
        "Material": {},
        "PayloadJson": '{"text":"Continue","fill":"#3366CCFF"}',
    }
    if button_style is not None:
        row["ButtonStyle"] = copy.deepcopy(button_style)
    return row


def _document(schema_version: int, layer: dict) -> dict:
    return {
        "SchemaVersion": schema_version,
        "Provider": "test",
        "DocumentId": "button-test",
        "Revision": 1,
        "Width": 400,
        "Height": 300,
        "Resources": [],
        "Layers": [copy.deepcopy(layer)],
        "Animations": [],
        "Interactions": [],
    }


def test_button_style_builder_derives_all_states_deterministically() -> None:
    from app.unreal_umg_button import (
        TIGER_UMG_BUTTON_STYLE_SCHEMA,
        make_umg_button_style,
        validate_umg_button_style_record,
    )

    record = make_umg_button_style(
        fill="#3366CC",
        stroke="#112233",
        stroke_width=2,
        corner_radii={
            "top_left": 4,
            "top_right": 8,
            "bottom_right": 12,
            "bottom_left": 16,
        },
        text_color="#F8FAFC",
        font_size=18,
        font_weight=600,
    )

    assert record["Schema"] == TIGER_UMG_BUTTON_STYLE_SCHEMA
    assert record["Enabled"] is True
    assert record["Normal"] == {
        "Fill": "#3366CCFF",
        "Stroke": "#112233FF",
        "StrokeWidth": 2.0,
        "CornerRadii": {"X": 4.0, "Y": 8.0, "Z": 12.0, "W": 16.0},
        "TextColor": "#F8FAFCFF",
        "FontSize": 18.0,
        "FontWeight": 600,
        "Opacity": 1.0,
    }
    assert record["Hovered"]["Fill"] == "#4372D0FF"
    assert record["Pressed"]["Fill"] == "#2D5AB4FF"
    assert record["Disabled"]["Opacity"] == pytest.approx(0.45)
    assert validate_umg_button_style_record(
        record,
        layer_kind="Button",
        document_schema_version=16,
        required=True,
    ) == []


def test_button_style_validation_is_strict_and_schema_gated() -> None:
    from app.unreal_umg_button import (
        make_umg_button_style,
        validate_umg_button_style_record,
    )

    record = make_umg_button_style()
    malformed = copy.deepcopy(record)
    malformed["ProviderFill"] = "#FF0000FF"
    malformed["Normal"]["FontWeight"] = 600.0
    malformed["Hovered"]["CornerRadii"].pop("W")
    malformed["Pressed"]["Fill"] = "red"
    malformed["Disabled"]["Opacity"] = 2.0

    reasons = validate_umg_button_style_record(
        malformed,
        layer_kind="Image",
        document_schema_version=15,
        required=True,
    )
    assert set(reasons) >= {
        "button_style_requires_schema_16",
        "button_style_layer_kind_unsupported",
        "button_style_record_fields_invalid",
        "button_style_normal_font_weight_invalid",
        "button_style_hovered_corner_radii_invalid",
        "button_style_pressed_fill_invalid",
        "button_style_disabled_opacity_invalid",
    }
    assert validate_umg_button_style_record({}, required=True) == [
        "button_style_missing"
    ]


def test_painter_solid_button_is_native_schema16_and_preserves_style() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )
    from app.unreal_umg_layout import TIGER_UMG_SCHEMA_VERSION

    document, button = add_ui_object(
        create_ui_document(640, 360),
        kind="button",
        name="Continue",
        x=40,
        y=50,
        width=220,
        height=64,
        style={
            "fill": "#3366CC",
            "stroke": "#DDE8FF",
            "stroke_width": 2,
            "radius": 12,
            "text_color": "#F8FAFC",
            "font_size": 18,
            "font_weight": 600,
        },
        content={"text": "Continue"},
    )

    exported = painter_ui_to_umg_document(document)
    layer = next(
        row for row in exported["Layers"] if row["Id"] == button["id"]
    )
    assert TIGER_UMG_SCHEMA_VERSION == 13
    assert exported["SchemaVersion"] == 16
    assert {
        row["Id"]: row["Visibility"] for row in exported["Layers"]
    } == {
        "__tiger_artboard_background": "HitTestInvisible",
        button["id"]: "Visible",
    }
    assert layer["Id"] == button["id"]
    assert layer["Kind"] == "Button"
    assert layer["Disposition"] == "Native"
    assert layer["ButtonStyle"]["Normal"]["Fill"] == "#3366CCFF"
    assert layer["ButtonStyle"]["Normal"]["Stroke"] == "#DDE8FFFF"
    assert layer["ButtonStyle"]["Normal"]["StrokeWidth"] == 2.0
    assert layer["ButtonStyle"]["Normal"]["CornerRadii"] == {
        "X": 12.0,
        "Y": 12.0,
        "Z": 12.0,
        "W": 12.0,
    }
    assert json.loads(layer["PayloadJson"])["umg_button_style"] == (
        layer["ButtonStyle"]
    )
    assert preflight_painter_umg(document)["ok"] is True


def test_painter_unsupported_button_paint_stays_explicitly_blocked() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, button = add_ui_object(
        create_ui_document(640, 360),
        kind="button",
        style={
            "fills": [
                {
                    "type": "linear",
                    "gradient": {
                        "type": "linear",
                        "stops": [
                            {"position": 0, "color": "#FF0000FF"},
                            {"position": 1, "color": "#0000FFFF"},
                        ],
                    },
                }
            ]
        },
    )

    exported = painter_ui_to_umg_document(document)
    layer = next(
        row for row in exported["Layers"] if row["Id"] == button["id"]
    )
    assert layer["Disposition"] == "Blocked"
    assert "button_style_fill_requires_solid_or_image" in layer[
        "BlockReasons"
    ]
    assert layer["ButtonStyle"] == {}
    assert exported["SchemaVersion"] == 16


def test_schema16_simulator_exposes_typed_and_painter_button_states() -> None:
    from app.painter_ui_umg_simulator import project_tiger_umg_document
    from app.unreal_umg_button import make_umg_button_style

    record = make_umg_button_style(
        fill="#246BCE",
        stroke="#BFD7FF",
        stroke_width=1.5,
        radius=10,
        text_color="#FFFFFFFF",
        font_size=17,
        font_weight=700,
    )
    projection = project_tiger_umg_document(
        _document(16, _native_button_layer(button_style=record))
    )

    widget = projection["widgets_by_id"]["cta"]
    projected = next(
        row for row in projection["document"]["objects"] if row["id"] == "cta"
    )
    assert projection["ready"] is True
    assert widget["button_style"] == record
    assert projected["style"]["fill"] == record["Normal"]["Fill"]
    assert projected["content"]["umg_button_style"] == {
        "enabled": True,
        "states": {
            state: projected["content"]["umg_button_style"]["states"][state]
            for state in ("normal", "hovered", "pressed", "disabled")
        },
    }
    assert projected["content"]["umg_button_style"]["states"]["pressed"][
        "fill"
    ] == record["Pressed"]["Fill"]


def test_motion_button_uses_shared_record_only_when_component_exists() -> None:
    from app.motion_designer.interactive_button import create_button_component
    from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
    from app.unreal_umg_document import (
        motion_composition_to_umg_document,
        preflight_umg_document,
    )

    plain = MotionLayer(id="plain", layer_type="shape")
    plain_document = motion_composition_to_umg_document(
        MotionComposition(id="plain-document", layers=[plain])
    )
    assert plain_document["SchemaVersion"] == 13
    assert plain_document["Layers"][0]["ButtonStyle"] == {}
    assert "Visibility" not in plain_document["Layers"][0]
    assert (
        _CURRENT_UMG_LAYER_KEYS - {"Visibility"}
        <= set(plain_document["Layers"][0])
    )

    button = MotionLayer(
        id="motion-cta",
        name="Motion CTA",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "shape": "rectangle",
                "width": 240,
                "height": 72,
                "fill": "#2255AA",
                "stroke": "#FFFFFFFF",
                "stroke_width": 2,
                "radius": 14,
                "font_size": 20,
                "font_weight": 700,
            },
        ),
    )
    create_button_component(button)
    sibling = MotionLayer(
        id="motion-label",
        name="Motion Label",
        layer_type="text",
        source=SourceRef(
            kind="text",
            params={"text": "Details", "font_size": 16},
        ),
    )
    document = motion_composition_to_umg_document(
        MotionComposition(id="motion-button", layers=[button, sibling])
    )
    layer = next(row for row in document["Layers"] if row["Id"] == button.id)
    assert document["SchemaVersion"] == 16
    assert all(
        row["Visibility"] == "Visible" for row in document["Layers"]
    )
    assert all(
        _CURRENT_UMG_LAYER_KEYS <= set(row) for row in document["Layers"]
    )
    assert all(row["PanelKind"] == "None" for row in document["Layers"])
    assert all(row["FlowSlot"] == {} for row in document["Layers"])
    assert all(row["ScrollOverflow"] == "None" for row in document["Layers"])
    assert all(row["ScrollPosition"] == "Scroll" for row in document["Layers"])
    assert all(row["Flipbook"] == {} for row in document["Layers"])
    assert layer["Kind"] == "Button"
    assert layer["Disposition"] == "Native"
    assert layer["ButtonStyle"]["Normal"]["Fill"] == "#2255AAFF"
    assert layer["ButtonStyle"]["Normal"]["CornerRadii"]["X"] == 14.0
    assert preflight_umg_document(document)["ok"] is True


@pytest.mark.parametrize("schema_version", range(4, 16))
def test_legacy_button_documents_remain_compatible_without_typed_style(
    schema_version: int,
) -> None:
    from app.unreal_umg_document import preflight_umg_document

    result = preflight_umg_document(
        _document(schema_version, _native_button_layer())
    )
    assert result["ok"] is True


def test_schema16_native_button_requires_typed_style() -> None:
    from app.painter_ui_umg_simulator import project_tiger_umg_document
    from app.unreal_umg_document import preflight_umg_document

    document = _document(16, _native_button_layer())
    preflight = preflight_umg_document(document)
    projection = project_tiger_umg_document(document)
    assert preflight["ok"] is False
    assert preflight["blockers"][0]["reasons"] == ["button_style_missing"]
    assert projection["ready"] is False
    assert projection["unrendered"][0]["reasons"] == [
        "button_style_missing"
    ]


def test_opaque_painter_artboard_is_a_first_native_background_layer() -> None:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets
    from app.unreal_umg_document import preflight_umg_document

    document = create_ui_document(320, 180)
    document["artboards"][0]["background"] = "#F7F9FC"
    exported = painter_ui_to_umg_document(document)
    layer = exported["Layers"][0]

    assert exported["SchemaVersion"] == 16
    assert layer["Id"] == "__tiger_artboard_background"
    assert layer["Kind"] == "Image"
    assert layer["Disposition"] == "Native"
    assert layer["Visibility"] == "HitTestInvisible"
    assert layer["CanvasSlot"] == {
        "AnchorMinimum": {"X": 0.0, "Y": 0.0},
        "AnchorMaximum": {"X": 1.0, "Y": 1.0},
        "Offsets": {"Left": 0.0, "Top": 0.0, "Right": 0.0, "Bottom": 0.0},
        "Alignment": {"X": 0.0, "Y": 0.0},
    }
    assert json.loads(layer["PayloadJson"])["fill"] == "#F7F9FCFF"
    assert exported["PainterSource"]["ArtboardBackground"] == {
        "mode": "included",
        "color": "#F7F9FCFF",
        "layer_id": "__tiger_artboard_background",
    }
    downgraded = copy.deepcopy(exported)
    downgraded["SchemaVersion"] = 15
    assert preflight_umg_document(downgraded)["blockers"][0]["reasons"] == [
        "umg_visibility_requires_schema_16"
    ]

    projection = project_painter_ui_umg_widgets(document)
    projected = projection["document"]["objects"][0]
    assert projection["counts"] == {
        "Native": 1,
        "Material": 0,
        "Baked": 0,
        "Blocked": 0,
    }
    assert projection["preflight"]["counts"] == projection["counts"]
    assert projected["id"] == "__tiger_artboard_background"
    assert projected["style"]["fill"] == "#F7F9FCFF"
    assert projection["contract"]["artboard_background"] == (
        exported["PainterSource"]["ArtboardBackground"]
    )


def test_transparent_painter_artboard_omits_reserved_background_layer() -> None:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets

    document = create_ui_document(320, 180)
    document["artboards"][0]["background"] = "#11223300"
    exported = painter_ui_to_umg_document(document)

    assert exported["SchemaVersion"] == 13
    assert exported["Layers"] == []
    assert exported["PainterSource"]["ArtboardBackground"] == {
        "mode": "transparent",
        "color": "#11223300",
        "layer_id": "",
    }
    projection = project_painter_ui_umg_widgets(document)
    assert projection["document"]["objects"] == []
    assert projection["source"]["artboard_background"]["mode"] == (
        "transparent"
    )


def test_mobile_onboarding_resolves_background_and_cta_tokens_for_umg() -> None:
    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_adapter import (
        PAINTER_UMG_FONT_SIZE_UNIT,
        painter_ui_to_umg_document,
    )
    from app.unreal_umg_component import (
        TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION,
    )

    document, _report = instantiate_ui_template("mobile_onboarding")
    exported = painter_ui_to_umg_document(document)
    background = exported["Layers"][0]
    cta = next(
        row for row in exported["Layers"] if row["Name"] == "Primary CTA"
    )
    cta_definition = next(
        row
        for component in exported["Components"]
        for row in component["Layers"]
        if row["Name"] == "Primary CTA"
    )
    headline = next(
        row for row in exported["Layers"] if row["Name"] == "Hero Headline"
    )
    body = next(
        row for row in exported["Layers"] if row["Name"] == "Supporting Copy"
    )

    assert (
        exported["SchemaVersion"]
        == TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION
    )
    assert background["Id"] == "__tiger_artboard_background"
    assert json.loads(background["PayloadJson"])["fill"] == "#F7F8FCFF"
    assert cta["ButtonStyle"] == {}
    assert cta_definition["ButtonStyle"]["Normal"]["Fill"] == "#5B6CFFFF"
    assert (
        cta_definition["ButtonStyle"]["Normal"]["TextColor"]
        == "#111827FF"
    )
    headline_payload = json.loads(headline["PayloadJson"])
    assert headline_payload["auto_wrap"] is True
    assert headline_payload["font_weight"] == 400
    assert headline_payload["font_family"] == "Inter"
    assert headline_payload["font_size"] == 38.0
    assert headline_payload["font_size_unit"] == PAINTER_UMG_FONT_SIZE_UNIT
    body_payload = json.loads(body["PayloadJson"])
    assert body_payload["font_size"] == 18.0
    assert body_payload["font_size_unit"] == PAINTER_UMG_FONT_SIZE_UNIT
    cta_payload = json.loads(cta["PayloadJson"])
    assert cta_payload["font_size"] == 19.0
    assert cta_payload["font_size_unit"] == PAINTER_UMG_FONT_SIZE_UNIT

    source_headline = next(
        row for row in document["objects"] if row["name"] == "Hero Headline"
    )
    source_headline["content"]["text_resize"] = "auto_width"
    auto_width = painter_ui_to_umg_document(document)
    auto_width_headline = next(
        row
        for row in auto_width["Layers"]
        if row["Name"] == "Hero Headline"
    )
    assert json.loads(auto_width_headline["PayloadJson"])["auto_wrap"] is False

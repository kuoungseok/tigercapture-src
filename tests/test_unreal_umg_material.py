from __future__ import annotations

import copy
import json

import pytest

from app.unreal_umg_layout import TIGER_UMG_SCHEMA_VERSION
from app.unreal_umg_material import (
    TIGER_UMG_CUSTOM_HLSL_GENERATOR,
    TIGER_UMG_ROUNDED_CARD_GENERATOR,
    TIGER_UMG_ROUNDED_CARD_SCHEMA,
    TIGER_UMG_UI_MATERIAL_SCHEMA,
    gradient_custom_hlsl,
    material_custom_hlsl,
    normalize_umg_gradient,
    normalize_umg_rounded_card,
    rounded_card_custom_hlsl,
    umg_material_graph,
    umg_material_preview_style,
    validate_umg_material_record,
)


def _gradient(*, kind: str = "linear", opacity: float = 0.5):
    return {
        "type": kind,
        "start": {"x": 0.1, "y": 0.2},
        "end": {"x": 0.9, "y": 0.8},
        "width": {"x": 0.2, "y": 0.7},
        "stops": [
            {"position": 0.0, "color": "#11223344"},
            {"position": 0.35, "color": "#55667788"},
            {"position": 1.0, "color": "#AABBCCDD"},
        ],
        "opacity": opacity,
    }


def _painter_layer(document: dict, object_id: str) -> dict:
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    return next(
        row
        for row in painter_ui_to_umg_document(document)["Layers"]
        if row["Id"] == object_id
    )


def test_gradient_normalization_emits_provider_neutral_material_contract() -> None:
    material = normalize_umg_gradient(
        {
            "type": "radial",
            "start": {"x": 0.25, "y": 0.75},
            "end": {"x": 1.0, "y": 0.75},
            "stops": [
                {"position": 1.2, "color": "#abc"},
                {"position": -0.2, "color": "#10203040"},
            ],
            "opacity": 1.5,
        }
    )

    assert material == {
        "Schema": TIGER_UMG_UI_MATERIAL_SCHEMA,
        "Generator": TIGER_UMG_CUSTOM_HLSL_GENERATOR,
        "Kind": "RadialGradient",
        "CoordinateSpace": "LocalUV",
        "Start": {"X": 0.25, "Y": 0.75},
        "End": {"X": 1.0, "Y": 0.75},
        "Width": {"X": 0.0, "Y": 1.0},
        "Stops": [
            {"Position": 0.0, "Color": "#10203040"},
            {"Position": 1.0, "Color": "#AABBCCFF"},
        ],
        "Opacity": 1.0,
    }
    assert validate_umg_material_record(material, layer_kind="Image") == []


def test_material_validation_rejects_untrusted_or_ambiguous_records() -> None:
    material = normalize_umg_gradient(_gradient())
    invalid = copy.deepcopy(material)
    invalid.update(
        {
            "Schema": "vendor.material.v99",
            "Generator": "arbitrary_hlsl",
            "Kind": "Custom",
            "CoordinateSpace": "World",
            "Stops": [{"Position": 0.0, "Color": "#FFFFFFFF"}],
        }
    )

    assert set(validate_umg_material_record(invalid, layer_kind="Button")) == {
        "ui_material_schema_unsupported",
        "ui_material_generator_unsupported",
        "ui_material_kind_unsupported",
        "ui_material_coordinate_space_unsupported",
        "ui_material_layer_kind_unsupported",
        "ui_material_gradient_requires_two_stops",
    }

    unsorted = copy.deepcopy(material)
    unsorted["Stops"] = list(reversed(unsorted["Stops"]))
    assert validate_umg_material_record(unsorted) == [
        "ui_material_gradient_stops_not_sorted"
    ]

    too_many = copy.deepcopy(material)
    too_many["Stops"] = [
        {"Position": index / 16.0, "Color": "#FFFFFFFF"}
        for index in range(17)
    ]
    assert validate_umg_material_record(too_many) == [
        "ui_material_gradient_stop_limit_exceeded"
    ]


@pytest.mark.parametrize(
    ("kind", "coordinate_fragment"),
    [
        ("linear", "float2 Axis = End.xy - Start.xy;"),
        ("radial", "float Radius = max(length(End.xy - Start.xy)"),
    ],
)
def test_custom_hlsl_is_fixed_and_preserves_color_alpha_and_fill_opacity(
    kind: str,
    coordinate_fragment: str,
) -> None:
    authored = _gradient(kind=kind)
    authored["custom_hlsl"] = "discard; // must never enter generated code"

    code = gradient_custom_hlsl(authored)

    assert coordinate_fragment in code
    assert "float4 Result = Color0;" in code
    assert "lerp(Color0, Color1" in code
    assert "lerp(Color1, Color2" in code
    assert "Result.a *= saturate(FillOpacity);" in code
    assert code.endswith("return Result;")
    assert "discard" not in code


def test_material_graph_exposes_fixed_four_node_pipeline() -> None:
    graph = umg_material_graph(normalize_umg_gradient(_gradient()))

    assert graph["schema"] == "tigerstudio.umg.ui_material_graph.v1"
    assert [row["type"] for row in graph["nodes"]] == [
        "TextureCoordinate",
        "Parameters",
        "CustomHLSL",
        "UIOutput",
    ]
    assert graph["connections"] == [
        {"from": "uv", "to": "custom_hlsl", "port": "UV"},
        {
            "from": "parameters",
            "to": "custom_hlsl",
            "port": "Parameters",
        },
        {
            "from": "custom_hlsl",
            "to": "output",
            "port": "Final Color / Opacity",
        },
    ]


def test_material_preview_multiplies_stop_alpha_by_fill_opacity() -> None:
    style = umg_material_preview_style(
        normalize_umg_gradient(_gradient(opacity=0.5))
    )

    assert style["fill_gradient"]["type"] == "linear"
    assert [row["color"] for row in style["fill_gradient"]["stops"]] == [
        "#11223322",
        "#55667744",
        "#AABBCC6E",
    ]


def test_painter_gradient_exports_valid_material_and_passes_preflight() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, row = add_ui_object(
        create_ui_document(320, 180),
        kind="rectangle",
        name="Gradient Card",
        style={
            "fills": [
                {
                    "type": "linear",
                    "opacity": 0.5,
                    "gradient": _gradient(opacity=1.0),
                }
            ]
        },
    )

    umg_document = painter_ui_to_umg_document(document)
    layer = next(item for item in umg_document["Layers"] if item["Id"] == row["id"])
    payload = json.loads(layer["PayloadJson"])

    assert TIGER_UMG_SCHEMA_VERSION == 13
    assert umg_document["SchemaVersion"] == 16
    assert layer["Disposition"] == "Material"
    assert layer["Kind"] == "Image"
    assert layer["BlockReasons"] == []
    assert layer["Material"]["Generator"] == TIGER_UMG_CUSTOM_HLSL_GENERATOR
    assert layer["Material"]["Opacity"] == pytest.approx(0.5)
    assert validate_umg_material_record(
        layer["Material"],
        layer_kind=layer["Kind"],
    ) == []
    assert payload["umg_mapping"] == "ui_material_custom_hlsl"
    assert preflight_painter_umg(document)["counts"] == {
        "Native": 1,
        "Material": 1,
        "Baked": 0,
        "Blocked": 0,
    }
    assert preflight_painter_umg(document)["ok"] is True


def test_motion_and_painter_share_the_same_gradient_material_record() -> None:
    from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.unreal_umg_document import (
        motion_composition_to_umg_document,
        preflight_umg_document,
    )

    gradient = _gradient(kind="radial", opacity=0.75)
    painter_document, painter_row = add_ui_object(
        create_ui_document(320, 180),
        kind="rectangle",
        style={"fill_gradient": gradient},
    )
    motion_layer = MotionLayer(
        id="motion-gradient",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={"shape": "rectangle", "gradient": gradient},
        ),
    )

    painter_layer = _painter_layer(painter_document, painter_row["id"])
    motion_document = motion_composition_to_umg_document(
        MotionComposition(id="motion-material", layers=[motion_layer])
    )
    motion_export = motion_document["Layers"][0]

    assert painter_layer["Disposition"] == "Material"
    assert motion_export["Disposition"] == "Material"
    assert painter_layer["Material"] == motion_export["Material"]
    assert preflight_umg_document(motion_document) == {
        "schema_version": 13,
        "ok": True,
        "counts": {
            "Native": 0,
            "Material": 1,
            "Baked": 0,
            "Blocked": 0,
        },
        "blockers": [],
    }


@pytest.mark.parametrize("kind", ["frame", "group"])
def test_painted_leaf_container_uses_existing_rectangle_material_path(
    kind: str,
) -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, container = add_ui_object(
        create_ui_document(320, 180),
        kind=kind,
        style={"fill_gradient": _gradient()},
    )
    layer = _painter_layer(document, container["id"])
    payload = json.loads(layer["PayloadJson"])

    assert layer["Id"] == container["id"]
    assert layer["Kind"] == "Image"
    assert layer["Disposition"] == "Material"
    assert layer["BlockReasons"] == []
    assert layer["Material"]["Kind"] in {"LinearGradient", "RadialGradient"}
    assert payload["source_kind"] == kind
    assert payload["umg_leaf_rectangle_classification"] == {
        "classification": "painted_leaf_container",
        "original_source_kind": kind,
        "effective_source_kind": "rectangle",
        "effective_widget_kind": "Image",
        "preserves_container_semantics": False,
        "authored_panel_kind": "Overlay",
        "authored_spacing_strategy": "Padding",
        "authored_spacer_size_rule": "Auto",
        "authored_spacer_fill_coefficient": 1.0,
    }
    assert payload["auto_layout"]["panel_classification"] == {
        "policy": "auto",
        "requested": "auto",
        "effective": "Overlay",
        "reasons": ["all_children_support_overlay_slots"],
    }


def test_painted_container_with_child_keeps_group_semantics() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, frame = add_ui_object(
        create_ui_document(320, 180),
        kind="frame",
        style={"fill_gradient": _gradient()},
    )
    document, _child = add_ui_object(
        document,
        kind="text",
        parent_id=frame["id"],
        content={"text": "Child"},
    )
    layers = painter_ui_to_umg_document(document)["Layers"]
    layer = next(row for row in layers if row["Id"] == frame["id"])
    background = next(
        row for row in layers if row["Id"] == f"{frame['id']}::umg-background"
    )

    # The container's own gradient paint moves onto a synthetic leaf
    # background (see _split_painted_containers), so the group itself keeps
    # structural semantics instead of being blocked by its own appearance.
    assert layer["Kind"] == "Group"
    assert layer["Disposition"] == "Native"
    assert layer["BlockReasons"] == []
    assert background["Disposition"] == "Material"


def test_saas_dashboard_leaf_frames_export_as_native_or_material_images() -> None:
    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, _report = instantiate_ui_template("saas_dashboard")
    target_names = {
        "Metric Card 1",
        "Metric Card 2",
        "Metric Card 3",
        "Chart Region",
    }
    for artboard in document["artboards"]:
        artboard_id = str(artboard["id"])
        source_rows = {
            row["id"]: row
            for row in document["objects"]
            if row["artboard_id"] == artboard_id
            and row["name"] in target_names
        }
        exported = painter_ui_to_umg_document(
            document,
            artboard_id=artboard_id,
        )
        layers = {row["Id"]: row for row in exported["Layers"]}

        assert len(source_rows) == 4
        for object_id, source in source_rows.items():
            layer = layers[object_id]
            payload = json.loads(layer["PayloadJson"])
            assert layer["Name"] == source["name"]
            assert layer["Kind"] == "Image"
            assert layer["Disposition"] == "Material"
            assert layer["BlockReasons"] == []
            assert layer["Material"]["Kind"] == "RoundedCard"
            assert layer["Material"]["Generator"] == (
                TIGER_UMG_ROUNDED_CARD_GENERATOR
            )
            assert layer["Size"] == {
                "X": pytest.approx(source["width"]),
                "Y": pytest.approx(source["height"]),
            }
            assert layer["Position"] == {
                "X": pytest.approx(source["x"] + source["width"] * 0.5),
                "Y": pytest.approx(source["y"] + source["height"] * 0.5),
            }
            assert payload["source_kind"] == "frame"
            assert payload["umg_leaf_rectangle_classification"][
                "classification"
            ] == "painted_leaf_container"
            assert "advanced_appearance_requires_leaf_rectangle" not in (
                payload["umg_block_reasons"]
            )

        navigation = next(
            row
            for row in exported["Layers"]
            if row["Name"] == "Navigation"
        )
        assert navigation["Kind"] == "Image"
        assert navigation["Disposition"] == "Native"
        assert navigation["Material"] == {}
        assert json.loads(navigation["PayloadJson"])[
            "painter_conversion"
        ] == "painted_leaf_container_to_slate_image"


def test_rounded_card_normalization_fits_independent_radii_to_size() -> None:
    material = normalize_umg_rounded_card(
        {
            "fill": "#123456CC",
            "radius": 80,
            "corner_radii": {
                "top_left": 80,
                "top_right": 80,
                "bottom_right": 60,
                "bottom_left": 60,
            },
            "corner_smoothing": 1.5,
        },
        size={"width": 100, "height": 50},
    )

    assert material["Schema"] == TIGER_UMG_ROUNDED_CARD_SCHEMA
    assert material["Generator"] == TIGER_UMG_ROUNDED_CARD_GENERATOR
    assert material["Kind"] == "RoundedCard"
    assert material["FillKind"] == "Solid"
    assert material["FillColor"] == "#123456CC"
    assert material["Size"] == {"X": 100.0, "Y": 50.0}
    assert material["SizeBinding"] == "FixedSize"
    assert material["CornerSmoothing"] == 1.0
    radii = material["CornerRadii"]
    assert radii["X"] + radii["W"] == pytest.approx(50.0)
    assert radii["Y"] + radii["Z"] == pytest.approx(50.0)
    assert validate_umg_material_record(
        material,
        layer_kind="Image",
        document_schema_version=8,
    ) == []
    assert validate_umg_material_record(
        material,
        document_schema_version=7,
    ) == ["ui_material_requires_schema_8"]


def test_dynamic_rounded_card_size_binding_requires_schema_19() -> None:
    material = normalize_umg_rounded_card(
        {"fill": "#123456FF", "radius": 12},
        size={"X": 100, "Y": 50},
    )
    material["SizeBinding"] = "WidgetGeometry"

    assert validate_umg_material_record(
        material,
        layer_kind="Image",
        document_schema_version=19,
    ) == []
    assert validate_umg_material_record(
        material,
        layer_kind="Image",
        document_schema_version=18,
    ) == ["ui_material_dynamic_size_binding_requires_schema_19"]
    missing = copy.deepcopy(material)
    missing.pop("SizeBinding")
    assert validate_umg_material_record(
        missing,
        layer_kind="Image",
        document_schema_version=18,
    ) == []
    assert validate_umg_material_record(
        missing,
        layer_kind="Image",
        document_schema_version=19,
    ) == ["ui_material_rounded_card_size_binding_invalid"]


def test_rounded_card_validation_rejects_invalid_geometry_and_padding() -> None:
    material = normalize_umg_rounded_card(
        {"fill": "#123456FF", "radius": 12},
        size={"X": 100, "Y": 50},
    )
    invalid = copy.deepcopy(material)
    invalid["FillKind"] = "AngularGradient"
    invalid["CornerRadii"] = {"X": 80, "Y": 80, "Z": 80, "W": 80}
    invalid["CornerSmoothing"] = 2.0
    invalid["Stroke"]["Alignment"] = "Edge"
    invalid["DropShadow"]["Blur"] = -1.0
    invalid["VisualPadding"]["Left"] = 999.0

    assert set(validate_umg_material_record(invalid, layer_kind="Image")) >= {
        "ui_material_rounded_card_fill_kind_unsupported",
        "ui_material_rounded_card_radii_exceed_size",
        "ui_material_rounded_card_smoothing_invalid",
        "ui_material_rounded_card_stroke_invalid",
        "ui_material_rounded_card_drop_shadow_invalid",
        "ui_material_visual_padding_invalid",
    }


def test_rounded_card_gradient_stroke_shadows_and_padding_export() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, row = add_ui_object(
        create_ui_document(320, 180),
        kind="rectangle",
        width=200,
        height=100,
        style={
            "fills": [
                {
                    "type": "radial",
                    "opacity": 0.75,
                    "gradient": _gradient(kind="radial", opacity=1.0),
                }
            ],
            "corner_radii": {
                "top_left": 24,
                "top_right": 12,
                "bottom_right": 8,
                "bottom_left": 4,
            },
            "corner_smoothing": 0.6,
            "strokes": [
                {
                    "type": "solid",
                    "visible": True,
                    "color": "#AABBCCDD",
                    "width": 4,
                    "align": "outside",
                }
            ],
            "effects": [
                {
                    "type": "drop_shadow",
                    "color": "#00000080",
                    "x": -3,
                    "y": 5,
                    "blur": 10,
                    "spread": 2,
                    "blend_mode": "normal",
                },
                {
                    "type": "inner_shadow",
                    "color": "#FFFFFF40",
                    "x": 1,
                    "y": 2,
                    "blur": 3,
                    "spread": -1,
                    "blend_mode": "normal",
                },
            ],
        },
    )

    layer = next(
        item
        for item in painter_ui_to_umg_document(document)["Layers"]
        if item["Id"] == row["id"]
    )
    material = layer["Material"]
    assert layer["Disposition"] == "Material"
    assert material["FillKind"] == "RadialGradient"
    assert material["Opacity"] == pytest.approx(0.75)
    assert material["Stroke"] == {
        "Width": 4.0,
        "Alignment": "Outside",
        "Color": "#AABBCCDD",
    }
    assert material["DropShadow"]["Enabled"] is True
    assert material["InnerShadow"]["Enabled"] is True
    assert material["VisualPadding"] == {
        "Left": 19.0,
        "Top": 11.0,
        "Right": 13.0,
        "Bottom": 21.0,
    }
    assert validate_umg_material_record(
        material,
        layer_kind="Image",
        document_schema_version=8,
    ) == []


@pytest.mark.parametrize(
    ("kind", "style", "reason"),
    [
        (
            "rectangle",
            {
                "strokes": [
                    {"type": "solid", "width": 1, "color": "#FFFFFFFF"},
                    {"type": "solid", "width": 2, "color": "#000000FF"},
                ]
            },
            "multiple_strokes_require_umg_material_or_bake",
        ),
        (
            "rectangle",
            {
                "strokes": [
                    {
                        "type": "linear",
                        "width": 2,
                        "gradient": _gradient(),
                    }
                ]
            },
            "gradient_stroke_requires_deterministic_bake",
        ),
        (
            "rectangle",
            {
                "effects": [
                    {
                        "type": "drop_shadow",
                        "blend_mode": "multiply",
                        "blur": 8,
                    }
                ]
            },
            "effect_blend_mode_requires_deterministic_bake",
        ),
        (
            "rectangle",
            {"effects": [{"type": "background_blur", "radius": 8}]},
            "background_blur_requires_native_umg_widget",
        ),
    ],
)
def test_rounded_card_preflight_explicitly_blocks_unsupported_appearance(
    kind: str,
    style: dict,
    reason: str,
) -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, row = add_ui_object(
        create_ui_document(320, 180),
        kind=kind,
        style=style,
    )
    layer = _painter_layer(document, row["id"])

    assert layer["Disposition"] == "Blocked"
    assert layer["Material"] == {}
    assert reason in layer["BlockReasons"]


def test_rounded_card_graph_preview_and_hlsl_use_fixed_v2_generator() -> None:
    authored = {
        "fill": "#223344FF",
        "radius": 18,
        "custom_hlsl": "discard; // must never enter generated code",
    }
    material = normalize_umg_rounded_card(authored, size={"X": 120, "Y": 60})
    graph = umg_material_graph(material)
    preview = umg_material_preview_style(material)
    code = rounded_card_custom_hlsl(material)

    assert graph["schema"] == "tigerstudio.umg.ui_material_graph.v2"
    assert [row["id"] for row in graph["nodes"]] == [
        "geometry_uv",
        "fill",
        "corners_border",
        "shadows",
        "custom_hlsl",
        "output",
    ]
    assert preview["corner_radii"] == {
        "top_left": 18.0,
        "top_right": 18.0,
        "bottom_right": 18.0,
        "bottom_left": 18.0,
    }
    assert "float BasePower = lerp(2.0, 4.0" in code
    assert "float2 SurfaceSize = max(CardSize.xy + float2(VisualPadding.x" in code
    assert "float2 PixelPosition = UV * SurfaceSize - VisualPadding.xy;" in code
    assert "float RadiusScaleX = CardSize.x /" in code
    assert "float RadiusScaleY = CardSize.y /" in code
    assert "float4 EffectiveCornerRadii = CornerRadii *" in code
    assert "? EffectiveCornerRadii.x : EffectiveCornerRadii.w" in code
    assert "CardPoint - DropShadowOffset.xy" in code
    assert "CardPoint - InnerShadowOffset.xy" in code
    assert "float OuterOffset = (Alignment < 0.5) ? 0.0" in code
    assert "float StrokeMask" in code
    assert "DropShadowEnabled" in code
    assert "float3 BasePremultiplied = Fill.rgb * Fill.a;" in code
    assert "AccumulatedRGB = BasePremultiplied + AccumulatedRGB" in code
    assert "return float4(ResultRGB, saturate(AccumulatedAlpha));" in code
    assert "discard" not in code
    assert material_custom_hlsl(material) == code
    assert material_custom_hlsl(normalize_umg_gradient(_gradient())).endswith(
        "return Result;"
    )


def test_rounded_card_radial_hlsl_consumes_two_axis_basis() -> None:
    material = normalize_umg_rounded_card(
        {
            "fills": [
                {
                    "type": "radial",
                    "opacity": 0.75,
                    "gradient": {
                        **_gradient(kind="radial"),
                        "start": {"x": 0.35, "y": 0.4},
                        "end": {"x": 0.8, "y": 0.45},
                        "width": {"x": 0.25, "y": 0.9},
                    },
                }
            ],
            "radius": 12,
        },
        size={"X": 180, "Y": 90},
    )
    code = rounded_card_custom_hlsl(material)

    assert material["FillKind"] == "RadialGradient"
    assert material["Width"] == {"X": 0.25, "Y": 0.9}
    assert "GradientBasisX = GradientEnd.xy - GradientStart.xy" in code
    assert "GradientBasisY = GradientWidth.xy - GradientStart.xy" in code
    assert "float GradientDeterminant" in code
    assert "float2 GradientLocal" in code
    assert "GradientT = saturate(length(GradientLocal))" in code
    assert "length(CardUV - GradientStart.xy) / GradientRadius" not in code


def test_uniform_radius_converts_leaf_frame_but_keeps_other_widget_rules() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document = create_ui_document(400, 300)
    ids: dict[str, str] = {}
    for kind in ("frame", "button", "image", "text"):
        document, row = add_ui_object(
            document,
            kind=kind,
            style={
                "radius": 8,
                **({"fill": "#FFFFFFFF"} if kind == "frame" else {}),
            },
        )
        ids[kind] = row["id"]

    layers = {
        row["Id"]: row for row in painter_ui_to_umg_document(document)["Layers"]
    }
    frame_layer = layers[ids["frame"]]
    assert frame_layer["Kind"] == "Image"
    assert frame_layer["Disposition"] == "Material"
    assert frame_layer["Material"]["Kind"] == "RoundedCard"
    image_layer = layers[ids["image"]]
    assert image_layer["Disposition"] == "Blocked"
    assert image_layer["BlockReasons"] == [
        "advanced_appearance_requires_leaf_rectangle"
    ]
    assert layers[ids["button"]]["Disposition"] == "Native"
    assert layers[ids["button"]]["ButtonStyle"]["Normal"]["CornerRadii"] == {
        "X": 8.0,
        "Y": 8.0,
        "Z": 8.0,
        "W": 8.0,
    }
    assert layers[ids["text"]]["Disposition"] == "Native"
    assert layers[ids["text"]]["BlockReasons"] == []


@pytest.mark.parametrize("mode", ["stretch", "scale", "custom"])
def test_rounded_card_binds_runtime_resizing_canvas_constraints(mode: str) -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, card = add_ui_object(
        create_ui_document(400, 300),
        kind="rectangle",
        style={"fill": "#245DA8FF", "radius": 12},
    )
    constraints = {"horizontal": mode, "vertical": "top"}
    if mode == "custom":
        constraints.update(
            {
                "anchor_min_x": 0.2,
                "anchor_max_x": 0.8,
                "anchor_offset_left": 10,
                "anchor_offset_right": 10,
            }
        )
    document, _card = update_ui_object(
        document,
        card["id"],
        {"constraints": constraints},
    )
    layer = _painter_layer(document, card["id"])

    assert layer["Disposition"] == "Material"
    assert layer["Material"]["Kind"] == "RoundedCard"
    assert layer["Material"]["SizeBinding"] == "WidgetGeometry"
    assert layer["BlockReasons"] == []


def test_dynamic_rounded_card_document_uses_schema_19_and_fixed_fallback_blocks() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import (
        _preflight_painter_umg_document,
        painter_ui_to_umg_document,
    )

    document, card = add_ui_object(
        create_ui_document(400, 300),
        kind="rectangle",
        style={"fill": "#245DA8FF", "radius": 12},
    )
    document, _ = update_ui_object(
        document,
        card["id"],
        {"constraints": {"horizontal": "stretch", "vertical": "top"}},
    )
    exported = painter_ui_to_umg_document(document)
    layer = next(row for row in exported["Layers"] if row["Id"] == card["id"])

    assert exported["SchemaVersion"] == 19
    assert _preflight_painter_umg_document(exported)["ok"] is True

    fixed = copy.deepcopy(exported)
    fixed_layer = next(row for row in fixed["Layers"] if row["Id"] == card["id"])
    fixed_layer["Material"]["SizeBinding"] = "FixedSize"
    preflight = _preflight_painter_umg_document(fixed)
    assert preflight["ok"] is False
    assert preflight["blockers"] == [
        {
            "object_id": card["id"],
            "name": layer["Name"],
            "reasons": [
                "rounded_card_runtime_resize_requires_dynamic_size_binding"
            ],
        }
    ]


def test_blocked_dynamic_card_does_not_promote_unrelated_fixed_materials() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, blocked = add_ui_object(
        create_ui_document(400, 300),
        kind="rectangle",
        name="Masked dynamic card",
        style={"fill": "#245DA8FF", "radius": 12},
    )
    document, _ = update_ui_object(
        document,
        blocked["id"],
        {
            "constraints": {"horizontal": "stretch", "vertical": "top"},
            "mask": {"enabled": True, "target_ids": []},
        },
    )
    document, fixed = add_ui_object(
        document,
        kind="rectangle",
        name="Fixed card",
        style={"fill": "#123456FF", "radius": 8},
    )

    exported = painter_ui_to_umg_document(document)
    layers = {row["Id"]: row for row in exported["Layers"]}

    assert layers[blocked["id"]]["Disposition"] == "Blocked"
    assert layers[blocked["id"]]["Material"] == {}
    assert exported["SchemaVersion"] == 16
    assert layers[fixed["id"]]["Disposition"] == "Material"
    assert "SizeBinding" not in layers[fixed["id"]]["Material"]


@pytest.mark.parametrize(
    ("horizontal", "expected_binding", "expected_schema"),
    [
        ("stretch", "WidgetGeometry", 19),
        ("left", None, 17),
    ],
)
def test_overlay_rounded_card_binds_only_fill_allocations(
    horizontal: str,
    expected_binding: str | None,
    expected_schema: int,
) -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, frame = add_ui_object(
        create_ui_document(500, 320),
        kind="frame",
        x=20,
        y=20,
        width=400,
        height=240,
    )
    document, _ = update_ui_object(
        document,
        frame["id"],
        {"layout": {"mode": "overlay"}},
    )
    document, card = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
        x=40,
        y=50,
        width=120,
        height=60,
        style={"fill": "#245DA8FF", "radius": 12},
    )
    document, _ = update_ui_object(
        document,
        card["id"],
        {"constraints": {"horizontal": horizontal, "vertical": "top"}},
    )

    exported = painter_ui_to_umg_document(document)
    layer = next(row for row in exported["Layers"] if row["Id"] == card["id"])

    assert exported["SchemaVersion"] == expected_schema
    assert layer["Disposition"] == "Material"
    assert layer["BlockReasons"] == []
    assert layer["Material"].get("SizeBinding") == expected_binding
    assert layer["FlowSlot"]["HorizontalAlignment"] == (
        "Fill" if horizontal == "stretch" else "Left"
    )


def test_synthetic_named_slot_overlay_ignores_stale_canvas_anchors() -> None:
    from app.painter_ui_umg_adapter import _umg_layer_requires_runtime_size

    layer = {
        "Id": "slot-root",
        "ParentId": "component-instance",
        "CanvasSlot": {
            "AnchorMinimum": {"X": 0.0, "Y": 0.0},
            "AnchorMaximum": {"X": 1.0, "Y": 1.0},
        },
        "FlowSlot": {
            "HorizontalAlignment": "Left",
            "VerticalAlignment": "Top",
            "SizeRule": "Auto",
        },
    }
    synthetic = {"slot-root"}

    assert _umg_layer_requires_runtime_size(
        layer,
        {"component-instance": "Canvas"},
        synthetic_overlay_root_ids=synthetic,
    ) is False
    layer["FlowSlot"]["HorizontalAlignment"] = "Fill"
    assert _umg_layer_requires_runtime_size(
        layer,
        {"component-instance": "Canvas"},
        synthetic_overlay_root_ids=synthetic,
    ) is True


def test_schema19_mixes_legacy_gradient_and_explicit_dynamic_rounded_card() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import (
        _preflight_painter_umg_document,
        painter_ui_to_umg_document,
    )

    document, gradient = add_ui_object(
        create_ui_document(500, 320),
        kind="rectangle",
        name="Legacy Gradient",
        style={"fill_gradient": _gradient()},
    )
    document, card = add_ui_object(
        document,
        kind="rectangle",
        name="Dynamic Card",
        style={"fill": "#245DA8FF", "radius": 12},
    )
    document, _ = update_ui_object(
        document,
        card["id"],
        {"constraints": {"horizontal": "stretch", "vertical": "top"}},
    )
    exported = painter_ui_to_umg_document(document)
    layers = {row["Id"]: row for row in exported["Layers"]}

    assert exported["SchemaVersion"] == 19
    assert layers[gradient["id"]]["Material"]["Schema"] == (
        TIGER_UMG_UI_MATERIAL_SCHEMA
    )
    assert "SizeBinding" not in layers[gradient["id"]]["Material"]
    assert layers[card["id"]]["Material"]["SizeBinding"] == "WidgetGeometry"
    assert _preflight_painter_umg_document(exported)["ok"] is True


@pytest.mark.parametrize(
    ("mode", "child_layout", "expected_binding"),
    [
        ("horizontal", {}, None),
        ("horizontal", {"width_sizing": "fill"}, "WidgetGeometry"),
        ("grid", {}, "WidgetGeometry"),
    ],
)
def test_rounded_card_binds_only_actual_runtime_resizing_flow_allocations(
    mode: str,
    child_layout: dict,
    expected_binding: str | None,
) -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, frame = add_ui_object(
        create_ui_document(500, 320),
        kind="frame",
        width=420,
        height=240,
    )
    document, _frame = update_ui_object(
        document,
        frame["id"],
        {
            "layout": {
                "mode": mode,
                "grid_columns": 2,
                "main_alignment": "start",
                "cross_alignment": "start",
            }
        },
    )
    document, card = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
        style={"fill": "#245DA8FF", "radius": 12},
    )
    if child_layout:
        document, _ = update_ui_object(
            document,
            card["id"],
            {"layout": child_layout},
        )
    exported = painter_ui_to_umg_document(document)
    layers = {row["Id"]: row for row in exported["Layers"]}

    assert layers[card["id"]]["Disposition"] == "Material"
    assert layers[card["id"]]["Material"].get("SizeBinding") == expected_binding
    assert layers[card["id"]]["BlockReasons"] == []
    assert exported["SchemaVersion"] == (19 if expected_binding else 16)


def test_legacy_gradient_can_still_use_runtime_resizing_canvas_constraints() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, gradient = add_ui_object(
        create_ui_document(400, 300),
        kind="rectangle",
        style={"fill_gradient": _gradient()},
    )
    document, _gradient_row = update_ui_object(
        document,
        gradient["id"],
        {"constraints": {"horizontal": "stretch", "vertical": "top"}},
    )
    layer = _painter_layer(document, gradient["id"])

    assert layer["Disposition"] == "Material"
    assert layer["Material"]["Schema"] == TIGER_UMG_UI_MATERIAL_SCHEMA
    assert layer["BlockReasons"] == []

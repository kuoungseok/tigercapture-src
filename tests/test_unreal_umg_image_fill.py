from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.motion_designer.interactive_button import create_button_component
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.painter_ui_document import (
    add_ui_object,
    create_ui_document,
    update_ui_object,
)
from app.painter_ui_umg_adapter import painter_ui_to_umg_document
from app.unreal_umg_document import (
    motion_composition_to_umg_document,
    preflight_umg_document,
)
from app.unreal_umg_layout import TIGER_UMG_SCHEMA_VERSION


def _texture(tmp_path: Path, name: str = "card.png") -> Path:
    path = tmp_path / name
    path.write_bytes(b"test-texture")
    return path


def _decodable_texture(tmp_path: Path, name: str = "decoded.png") -> Path:
    from PySide6.QtGui import QColor, QImage

    path = tmp_path / name
    image = QImage(40, 20, QImage.Format.Format_ARGB32)
    image.fill(QColor("#4080C0"))
    assert image.save(str(path))
    return path


def _layer(document: dict, object_id: str) -> dict:
    return next(row for row in document["Layers"] if row["Id"] == object_id)


@pytest.mark.parametrize(
    ("kind", "umg_kind", "expected_schema"),
    [
        ("rectangle", "Image", 16),
        # Painter's production-default Auto panel policy maps a Frame to the
        # schema-17 Overlay contract, including when its only visual is an
        # ImageFill surface.
        ("frame", "Group", 17),
        ("button", "Button", 16),
        ("image", "Image", 16),
    ],
)
def test_painter_content_image_fill_uses_shared_typed_resource(
    tmp_path: Path,
    kind: str,
    umg_kind: str,
    expected_schema: int,
) -> None:
    texture = _texture(tmp_path, f"{kind}.png")
    document, row = add_ui_object(
        create_ui_document(640, 360),
        kind=kind,
        width=240,
        height=120,
        style={"radius": 18},
        content={
            "source_path": str(texture),
            "image_fit": "fill",
            "focal_x": 0.25,
            "focal_y": 0.75,
            "original_width": 800,
            "original_height": 600,
            "image_opacity": 0.7,
            "image_tint": "#80C0FF",
        },
    )

    exported = painter_ui_to_umg_document(document)
    layer = _layer(exported, row["id"])
    fill = layer["ImageFill"]

    assert TIGER_UMG_SCHEMA_VERSION == 13
    assert exported["SchemaVersion"] == expected_schema
    assert layer["Kind"] == umg_kind
    assert layer["Disposition"] == "Native"
    assert layer["AssetId"] == fill["AssetId"] == exported["Resources"][0]["Id"]
    assert exported["Resources"][0]["Kind"] == "texture"
    assert exported["Resources"][0]["SourcePath"] == str(texture)
    assert json.loads(exported["Resources"][0]["SettingsJson"]) == {
        "Usage": "ImageFill",
        "SRGB": True,
    }
    assert fill["Mode"] == "Fill"
    assert fill["FocalPoint"] == {"X": 0.25, "Y": 0.75}
    assert fill["SourceSize"] == {"X": 800.0, "Y": 600.0}
    assert fill["Opacity"] == pytest.approx(0.7)
    assert fill["Tint"] == "#80C0FFFF"
    assert fill["CornerRadii"] == {
        "X": 18.0,
        "Y": 18.0,
        "Z": 18.0,
        "W": 18.0,
    }
    assert json.loads(layer["PayloadJson"])["image_fill"] == fill


def test_painter_image_fill_command_flows_into_typed_umg_record(
    tmp_path: Path,
) -> None:
    from app.painter_ui_image_assets import set_ui_image_fill

    texture = _decodable_texture(tmp_path)
    document, button = add_ui_object(
        create_ui_document(320, 180),
        kind="button",
        style={"radius": 10},
    )
    document, _button, report = set_ui_image_fill(
        document,
        button["id"],
        texture,
        image_fit="fill",
        focal_x=0.15,
        focal_y=0.85,
        tile_scale=1.25,
    )

    layer = _layer(painter_ui_to_umg_document(document), button["id"])

    assert report["schema"] == "tigerstudio.painter.ui.image.fill.v1"
    assert layer["Disposition"] == "Native"
    assert layer["ImageFill"]["Mode"] == "Fill"
    assert layer["ImageFill"]["FocalPoint"] == {"X": 0.15, "Y": 0.85}
    assert layer["ImageFill"]["TileScale"] == pytest.approx(1.25)
    assert layer["ImageFill"]["SourceSize"] == {"X": 40.0, "Y": 20.0}


def test_painter_style_image_paint_is_fallback_and_adjustments_are_explicit(
    tmp_path: Path,
) -> None:
    texture = _texture(tmp_path)
    document, row = add_ui_object(
        create_ui_document(320, 180),
        kind="rectangle",
        style={
            "fills": [
                {
                    "type": "image",
                    "source_path": str(texture),
                    "fit": "tile",
                    "tile_scale": 0.75,
                    "opacity": 0.6,
                    "color": "#FF8040FF",
                    "adjustments": {"contrast": 12},
                }
            ]
        },
    )

    layer = _layer(painter_ui_to_umg_document(document), row["id"])

    assert layer["ImageFill"]["Mode"] == "Tile"
    assert layer["ImageFill"]["TileScale"] == pytest.approx(0.75)
    assert layer["ImageFill"]["Opacity"] == pytest.approx(0.6)
    assert layer["ImageFill"]["Tint"] == "#FF8040FF"
    assert layer["ImageFill"]["Adjustments"]["Contrast"] == 12.0
    assert layer["Disposition"] == "Blocked"
    assert layer["BlockReasons"] == [
        "image_fill_adjustments_require_ui_material_or_bake"
    ]


def test_painter_content_path_wins_without_silently_dropping_second_image(
    tmp_path: Path,
) -> None:
    content_texture = _texture(tmp_path, "content.png")
    paint_texture = _texture(tmp_path, "paint.png")
    document, row = add_ui_object(
        create_ui_document(320, 180),
        kind="button",
        content={"source_path": str(content_texture), "image_fit": "stretch"},
        style={
            "fills": [
                {
                    "type": "image",
                    "source_path": str(paint_texture),
                    "fit": "fill",
                }
            ]
        },
    )

    exported = painter_ui_to_umg_document(document)
    layer = _layer(exported, row["id"])

    assert exported["Resources"][0]["SourcePath"] == str(content_texture)
    assert layer["ImageFill"]["Mode"] == "Stretch"
    assert layer["Disposition"] == "Blocked"
    assert "multiple_image_fill_sources_require_ui_material_or_bake" in layer[
        "BlockReasons"
    ]


def test_painter_content_geometry_keeps_image_paint_opacity_and_tint(
    tmp_path: Path,
) -> None:
    texture = _texture(tmp_path)
    document, row = add_ui_object(
        create_ui_document(320, 180),
        kind="frame",
        content={"source_path": str(texture), "image_fit": "fit"},
        style={
            "fills": [
                {
                    "type": "image",
                    # Figma resolves imageRef into content.source_path while
                    # paint-local opacity/tint remain on the fill record.
                    "source_path": "",
                    "opacity": 0.35,
                    "color": "#4080C0FF",
                }
            ]
        },
    )

    layer = _layer(painter_ui_to_umg_document(document), row["id"])

    assert layer["Disposition"] == "Native"
    assert layer["ImageFill"]["Mode"] == "Fit"
    assert layer["ImageFill"]["Opacity"] == pytest.approx(0.35)
    assert layer["ImageFill"]["Tint"] == "#4080C0FF"


def test_painter_nine_slice_is_native_stretch_but_incompatible_brushes_block(
    tmp_path: Path,
) -> None:
    texture = _texture(tmp_path)
    base_content = {
        "source_path": str(texture),
        "image_fit": "fill",
        "original_width": 100,
        "original_height": 50,
        "nine_slice_enabled": True,
        "nine_slice": {"left": 8, "top": 6, "right": 8, "bottom": 6},
    }
    native_document, native = add_ui_object(
        create_ui_document(320, 180),
        kind="frame",
        style={"radius": 0},
        content=base_content,
    )
    rounded_document, rounded = add_ui_object(
        create_ui_document(320, 180),
        kind="button",
        style={"radius": 12},
        content=base_content,
    )

    native_layer = _layer(painter_ui_to_umg_document(native_document), native["id"])
    rounded_layer = _layer(
        painter_ui_to_umg_document(rounded_document),
        rounded["id"],
    )

    assert native_layer["Disposition"] == "Native"
    assert native_layer["ImageFill"]["Mode"] == "Stretch"
    assert native_layer["ImageFill"]["NineSlice"] == {
        "Enabled": True,
        "Units": "Pixels",
        "Left": 8.0,
        "Top": 6.0,
        "Right": 8.0,
        "Bottom": 6.0,
    }
    assert rounded_layer["Disposition"] == "Blocked"
    assert (
        "image_fill_nine_slice_rounded_corners_require_ui_material_or_bake"
        in rounded_layer["BlockReasons"]
    )


def test_painter_crop_content_maps_to_native_source_region(
    tmp_path: Path,
) -> None:
    texture = _texture(tmp_path)
    document, row = add_ui_object(
        create_ui_document(320, 180),
        kind="rectangle",
        content={
            "source_path": str(texture),
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

    layer = _layer(painter_ui_to_umg_document(document), row["id"])

    assert layer["Disposition"] == "Native"
    assert layer["ImageFill"]["Mode"] == "Crop"
    assert layer["ImageFill"]["Crop"] == {
        "Enabled": True,
        "Units": "Normalized",
        "X": 0.25,
        "Y": 0.2,
        "Width": 0.5,
        "Height": 0.6,
    }


def test_figma_axis_aligned_image_transform_reuses_native_crop_contract(
    tmp_path: Path,
) -> None:
    texture = _texture(tmp_path)
    document, row = add_ui_object(
        create_ui_document(320, 180),
        kind="image",
        content={
            "source_path": str(texture),
            "image_fit": "stretch",
            "figma_image_transform": [
                [0.6, 0.0, 0.2],
                [0.0, 0.5, 0.25],
            ],
        },
    )

    layer = _layer(painter_ui_to_umg_document(document), row["id"])

    assert layer["Disposition"] == "Native"
    assert layer["ImageFill"]["Mode"] == "Crop"
    assert layer["ImageFill"]["Crop"] == {
        "Enabled": True,
        "Units": "Normalized",
        "X": 0.2,
        "Y": 0.25,
        "Width": 0.6,
        "Height": 0.5,
    }


def test_figma_skewed_image_transform_and_shadows_filter_are_explicitly_blocked(
    tmp_path: Path,
) -> None:
    texture = _texture(tmp_path)
    document, row = add_ui_object(
        create_ui_document(320, 180),
        kind="image",
        content={
            "source_path": str(texture),
            "image_fit": "stretch",
            "figma_image_transform": [
                [1.0, 0.2, 0.0],
                [0.0, 1.0, 0.0],
            ],
            "image_adjustments": {"shadows": 25},
        },
    )

    layer = _layer(painter_ui_to_umg_document(document), row["id"])

    assert layer["Disposition"] == "Blocked"
    assert {
        "image_fill_adjustments_require_ui_material_or_bake",
        "image_fill_transform_requires_ui_material_or_bake",
    } <= set(layer["BlockReasons"])


def test_painter_fill_with_runtime_size_and_ellipse_are_not_claimed_native(
    tmp_path: Path,
) -> None:
    texture = _texture(tmp_path)
    document, stretch = add_ui_object(
        create_ui_document(640, 360),
        kind="rectangle",
        content={"source_path": str(texture), "image_fit": "fill"},
    )
    document, stretch = update_ui_object(
        document,
        stretch["id"],
        {"constraints": {"horizontal": "stretch", "vertical": "top"}},
    )
    document, ellipse = add_ui_object(
        document,
        kind="ellipse",
        content={"source_path": str(texture), "image_fit": "stretch"},
    )

    exported = painter_ui_to_umg_document(document)
    stretch_layer = _layer(exported, stretch["id"])
    ellipse_layer = _layer(exported, ellipse["id"])

    assert "image_fill_runtime_resize_requires_dynamic_uv_binding" in stretch_layer[
        "BlockReasons"
    ]
    assert "image_fill_ellipse_clip_requires_ui_material_or_bake" in ellipse_layer[
        "BlockReasons"
    ]


def test_motion_image_and_shape_image_fill_share_the_same_contract(
    tmp_path: Path,
) -> None:
    texture = _texture(tmp_path)
    image = MotionLayer(
        id="photo",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(texture),
            params={
                "width": 300,
                "height": 160,
                "fit": "contain",
                "crop": [10, 20, 100, 80],
                "source_width": 640,
                "source_height": 480,
            },
        ),
    )
    shape = MotionLayer(
        id="card",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "shape": "rectangle",
                "width": 240,
                "height": 120,
                "image_fill": {
                    "source_path": str(texture),
                    "fit": "cover",
                    "focal_x": 0.2,
                    "focal_y": 0.8,
                    "opacity": 0.5,
                    "tint": "#AABBCCDD",
                    "corner_radii": {
                        "top_left": 4,
                        "top_right": 8,
                        "bottom_right": 12,
                        "bottom_left": 16,
                    },
                },
            },
        ),
    )
    create_button_component(shape)

    exported = motion_composition_to_umg_document(
        MotionComposition(id="image-fill", layers=[image, shape])
    )
    rows = {row["Id"]: row for row in exported["Layers"]}

    assert len(exported["Resources"]) == 1
    assert rows["photo"]["Disposition"] == "Native"
    assert rows["photo"]["ImageFill"]["Mode"] == "Fit"
    assert rows["photo"]["ImageFill"]["Crop"] == {
        "Enabled": True,
        "Units": "Pixels",
        "X": 10.0,
        "Y": 20.0,
        "Width": 100.0,
        "Height": 80.0,
    }
    assert rows["card"]["Kind"] == "Button"
    assert rows["card"]["Disposition"] == "Native"
    assert rows["card"]["AssetId"] == rows["photo"]["AssetId"]
    assert rows["card"]["ImageFill"]["Mode"] == "Fill"
    assert rows["card"]["ImageFill"]["FocalPoint"] == {"X": 0.2, "Y": 0.8}
    assert rows["card"]["ImageFill"]["CornerRadii"] == {
        "X": 4.0,
        "Y": 8.0,
        "Z": 12.0,
        "W": 16.0,
    }


def test_motion_adjusted_or_missing_image_fill_is_explicitly_blocked(
    tmp_path: Path,
) -> None:
    adjusted = MotionLayer(
        id="adjusted",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "image_fill": {
                    "source_path": str(_texture(tmp_path)),
                    "fit": "tile",
                    "radius": 6,
                    "adjustments": {"saturation": -20},
                }
            },
        ),
    )
    missing = MotionLayer(
        id="missing",
        layer_type="image",
        source=SourceRef(kind="image", uri="", params={"fit": "stretch"}),
    )

    rows = {
        row["Id"]: row
        for row in motion_composition_to_umg_document(
            MotionComposition(layers=[adjusted, missing])
        )["Layers"]
    }

    assert rows["adjusted"]["Disposition"] == "Blocked"
    assert {
        "image_fill_adjustments_require_ui_material_or_bake",
        "image_fill_tile_rounded_corners_require_ui_material_or_bake",
    } <= set(rows["adjusted"]["BlockReasons"])
    assert rows["missing"]["Disposition"] == "Blocked"
    assert rows["missing"]["BlockReasons"] == ["image_fill_missing_source_path"]


def test_provider_neutral_preflight_rejects_malformed_native_image_fill() -> None:
    result = preflight_umg_document(
        {
            "SchemaVersion": 11,
            "Layers": [
                {
                    "Id": "invalid",
                    "Name": "Invalid image fill",
                    "Kind": "Image",
                    "Disposition": "Native",
                    "AssetId": "texture_a",
                    "ImageFill": {
                        "AssetId": "texture_b",
                        "Mode": "Unknown",
                        "FocalPoint": {"X": 2, "Y": 0.5},
                        "TileScale": 0,
                        "Opacity": 2,
                        "Tint": "not-a-color",
                        "Crop": {"Enabled": False},
                        "NineSlice": {"Enabled": False},
                        "CornerRadii": {"X": 0, "Y": 0, "Z": 0, "W": 0},
                        "Adjustments": {},
                    },
                }
            ],
        }
    )

    assert result["ok"] is False
    assert {
        "image_fill_asset_id_mismatch",
        "image_fill_mode_unsupported:Unknown",
        "image_fill_focal_point_invalid",
        "image_fill_tile_scale_invalid",
        "image_fill_opacity_invalid",
        "image_fill_tint_invalid",
    } <= set(result["blockers"][0]["reasons"])

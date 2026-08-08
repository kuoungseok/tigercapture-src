from __future__ import annotations

from app.unreal_umg_flipbook import (
    TIGER_UMG_FLIPBOOK_GENERATOR,
    TIGER_UMG_FLIPBOOK_SCHEMA,
    flipbook_custom_hlsl,
    flipbook_frame_index,
    flipbook_material_graph,
    normalize_umg_flipbook,
    painter_flipbook_conversion,
    validate_umg_flipbook_record,
)


def _record(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = normalize_umg_flipbook(
        {
            "asset_id": "atlas",
            "columns": 2,
            "rows": 2,
            "frame_count": 4,
            "fps": 8.0,
            "start_frame": 0,
            "loop": True,
            "phase": 0.0,
            "static_frame_override": -1,
        }
    )
    result.update(overrides)
    return result


def test_flipbook_contract_normalizes_only_the_fixed_generator() -> None:
    record = _record()

    assert record["Schema"] == TIGER_UMG_FLIPBOOK_SCHEMA
    assert record["Generator"] == TIGER_UMG_FLIPBOOK_GENERATOR
    assert record["Kind"] == "FlipbookAtlas"
    assert validate_umg_flipbook_record(
        record,
        layer_kind="Image",
        document_schema_version=12,
        resource_ids=["atlas"],
    ) == []
    assert "Code" not in record
    assert "HLSL" not in record


def test_flipbook_validation_blocks_bad_generator_and_ranges() -> None:
    reasons = validate_umg_flipbook_record(
        _record(
            Generator="document_supplied_hlsl",
            Columns=0,
            Rows=257,
            FrameCount=5000,
            FramesPerSecond=241.0,
            StartFrame=-1,
            Loop="yes",
            Phase=1.5,
            StaticFrameOverride=5000,
        ),
        layer_kind="Button",
        document_schema_version=11,
        resource_ids=[],
    )

    assert "flipbook_requires_schema_12" in reasons
    assert "flipbook_generator_unsupported" in reasons
    assert "flipbook_layer_kind_unsupported" in reasons
    assert "flipbook_atlas_resource_missing" in reasons
    assert "flipbook_columns_out_of_range" in reasons
    assert "flipbook_rows_out_of_range" in reasons
    assert "flipbook_frame_count_out_of_range" in reasons
    assert "flipbook_fps_out_of_range" in reasons
    assert "flipbook_start_frame_out_of_range" in reasons
    assert "flipbook_loop_invalid" in reasons
    assert "flipbook_phase_out_of_range" in reasons
    assert "flipbook_static_frame_override_out_of_range" in reasons


def test_flipbook_frame_selector_matches_row_major_2x2_atlas() -> None:
    assert [
        flipbook_frame_index(
            _record(StaticFrameOverride=frame),
            time_seconds=999.0,
        )
        for frame in range(4)
    ] == [0, 1, 2, 3]
    assert flipbook_frame_index(_record(), time_seconds=0.0) == 0
    assert flipbook_frame_index(_record(), time_seconds=0.125) == 1
    assert flipbook_frame_index(
        _record(StartFrame=3),
        time_seconds=0.125,
    ) == 0
    assert flipbook_frame_index(
        _record(StartFrame=3, Loop=False),
        time_seconds=0.125,
    ) == 3


def test_flipbook_fixed_hlsl_and_graph_select_uv_before_atlas_sample() -> None:
    code = flipbook_custom_hlsl()
    graph = flipbook_material_graph(_record())

    assert "Texture2DSample" not in code
    assert "StaticFrameOverride" in code
    assert "fmod(RawFrame, SafeFrameCount)" in code
    assert "return (CellUV + float2(Column, Row))" in code
    assert [row["type"] for row in graph["nodes"]] == [
        "TextureCoordinate",
        "Time",
        "ValidatedScalarParameters",
        "CustomHLSL",
        "TextureSampleParameter2D",
        "UIOutput",
    ]
    assert graph["connections"][-2] == {
        "from": "frame_uv",
        "to": "atlas",
        "port": "Coordinates",
    }


def test_painter_flipbook_conversion_uses_full_axis_aligned_atlas() -> None:
    conversion = painter_flipbook_conversion(
        {"kind": "image"},
        {
            "fills": [
                {
                    "type": "image",
                    "source_path": "atlas.png",
                    "image_fit": "stretch",
                }
            ]
        },
        {
            "flipbook": {
                "columns": 2,
                "rows": 2,
                "frame_count": 4,
                "fps": 12,
                "static_frame_override": 2,
            }
        },
    )

    assert conversion is not None
    assert conversion.source_path == "atlas.png"
    assert conversion.block_reasons == []
    assert conversion.bind_asset("atlas-id")["AssetId"] == "atlas-id"


def test_painter_flipbook_conversion_never_silently_drops_atlas_transforms() -> None:
    conversion = painter_flipbook_conversion(
        {"kind": "image"},
        {"radius": 8.0},
        {
            "source_path": "atlas.png",
            "image_crop": {"x": 0.0, "y": 0.0, "width": 0.5, "height": 0.5},
            "image_rotation": 90,
            "flipbook": {
                "columns": 2,
                "rows": 2,
                "frame_count": 4,
            },
        },
    )

    assert conversion is not None
    assert "flipbook_atlas_crop_unsupported" in conversion.block_reasons
    assert "flipbook_atlas_rotation_unsupported" in conversion.block_reasons
    assert (
        "flipbook_rounded_clip_requires_ui_material_extension"
        in conversion.block_reasons
    )


def test_painter_adapter_exports_flipbook_resource_and_passes_preflight(
    tmp_path,
) -> None:
    import json

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import (
        PAINTER_UMG_ADAPTER_SCHEMA,
        package_painter_umg,
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    atlas = tmp_path / "atlas.png"
    atlas.write_bytes(b"deterministic-atlas-bytes")
    document, row = add_ui_object(
        create_ui_document(256, 256),
        kind="image",
        width=128,
        height=128,
        style={
            "radius": 0,
            "corner_radii": {
                "top_left": 0,
                "top_right": 0,
                "bottom_right": 0,
                "bottom_left": 0,
            },
            "fills": [
                {
                    "type": "image",
                    "source_path": str(atlas),
                    "fit": "stretch",
                }
            ],
        },
        content={
            "flipbook": {
                "columns": 2,
                "rows": 2,
                "frame_count": 4,
                "fps": 8,
                "start_frame": 0,
                "loop": True,
                "phase": 0.25,
                "static_frame_override": -1,
            }
        },
    )

    exported = painter_ui_to_umg_document(document)
    layer = next(item for item in exported["Layers"] if item["Id"] == row["id"])
    resource = exported["Resources"][0]
    payload = json.loads(layer["PayloadJson"])

    assert PAINTER_UMG_ADAPTER_SCHEMA.endswith(".v12")
    assert exported["SchemaVersion"] == 16
    assert layer["Disposition"] == "Material"
    assert layer["AssetId"] == ""
    assert layer["ImageFill"] == {}
    assert layer["Material"] == {}
    assert layer["Flipbook"]["AssetId"] == resource["Id"]
    assert layer["Flipbook"]["Generator"] == TIGER_UMG_FLIPBOOK_GENERATOR
    assert resource["Id"].startswith("flipbook_")
    assert resource["Kind"] == "texture"
    assert resource["SourcePath"] == str(atlas)
    assert json.loads(resource["SettingsJson"]) == {
        "Usage": "FlipbookAtlas",
        "SRGB": True,
        "AddressX": "Clamp",
        "AddressY": "Clamp",
    }
    assert payload["painter_conversion"] == "flipbook_ui_material"
    assert payload["umg_mapping"] == "flipbook_ui_material"
    assert payload["flipbook"] == layer["Flipbook"]
    preflight = preflight_painter_umg(document)
    assert preflight["ok"] is True
    assert preflight["counts"] == {
        "Native": 1,
        "Material": 1,
        "Baked": 0,
        "Blocked": 0,
    }

    package = package_painter_umg(document, tmp_path / "package")
    packaged_resource = package["document"]["Resources"][0]
    assert package["ok"] is True
    assert package["asset_count"] == 1
    assert packaged_resource["SourcePath"].startswith("assets/flipbook_")
    assert (tmp_path / "package" / packaged_resource["SourcePath"]).is_file()


def test_painter_adapter_blocks_invalid_flipbook_without_falling_back_to_image(
    tmp_path,
) -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    atlas = tmp_path / "atlas.png"
    atlas.write_bytes(b"atlas")
    document, row = add_ui_object(
        create_ui_document(256, 256),
        kind="image",
        style={"radius": 0},
        content={
            "source_path": str(atlas),
            "image_fit": "stretch",
            "image_crop": {"x": 0, "y": 0, "width": 0.5, "height": 1},
            "flipbook": {
                "columns": 2,
                "rows": 2,
                "frame_count": 4,
            },
        },
    )

    layer = next(
        item
        for item in painter_ui_to_umg_document(document)["Layers"]
        if item["Id"] == row["id"]
    )

    assert layer["Disposition"] == "Blocked"
    assert "flipbook_atlas_crop_unsupported" in layer["BlockReasons"]
    assert layer["ImageFill"] == {}
    assert layer["Material"] == {}
    assert layer["Flipbook"]["AssetId"].startswith("flipbook_")


def test_painter_adapter_preserves_flipbook_bake_material_readiness(
    tmp_path,
) -> None:
    import copy
    import json

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    blocker = "flipbook_trigger_requires_dynamic_material_time_origin"
    atlas = tmp_path / "atlas.png"
    atlas.write_bytes(b"atlas")
    ambient, row = add_ui_object(
        create_ui_document(256, 256),
        kind="image",
        style={"radius": 0},
        content={
            "source_path": str(atlas),
            "image_fit": "stretch",
            "flipbook": {
                "columns": 2,
                "rows": 2,
                "frame_count": 4,
            },
            "flipbook_bake": {
                "playback_scope": "ambient_loop",
                "material_ready": True,
                "block_reasons": [],
            },
        },
    )
    event_triggered = copy.deepcopy(ambient)
    event_triggered["objects"][0]["content"]["flipbook_bake"] = {
        "playback_scope": "event_triggered",
        "material_ready": False,
        "block_reasons": [blocker],
    }

    ambient_layer = next(
        item
        for item in painter_ui_to_umg_document(ambient)["Layers"]
        if item["Id"] == row["id"]
    )
    event_layer = next(
        item
        for item in painter_ui_to_umg_document(event_triggered)["Layers"]
        if item["Id"] == row["id"]
    )

    assert ambient_layer["Disposition"] == "Material"
    assert ambient_layer["BlockReasons"] == []
    assert event_layer["Disposition"] == "Blocked"
    assert event_layer["BlockReasons"] == [blocker]
    assert event_layer["Flipbook"]["AssetId"].startswith("flipbook_")
    assert json.loads(event_layer["PayloadJson"])["flipbook_bake"] == {
        "playback_scope": "event_triggered",
        "material_ready": False,
        "block_reasons": [blocker],
    }

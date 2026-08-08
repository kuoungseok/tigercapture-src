from __future__ import annotations

from pathlib import Path


def test_flipbook_qa_builds_reproducible_2x2_atlas_and_schema12_document(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from tools.qa_painter_ui_unreal_umg_flipbook import (
        FRAME_COLORS,
        _flipbook_document,
        _write_atlas,
    )

    atlas = _write_atlas(tmp_path / "atlas.png", cell_size=16)
    image = Image.open(atlas).convert("RGBA")
    assert image.size == (32, 32)
    assert [
        image.getpixel(point)
        for point in ((8, 8), (24, 8), (8, 24), (24, 24))
    ] == list(FRAME_COLORS)

    document = _flipbook_document(atlas)
    assert document["SchemaVersion"] == 12
    assert len(document["Resources"]) == 1
    assert document["Resources"][0]["SettingsJson"] == (
        '{"Usage":"FlipbookAtlas","SRGB":true,'
        '"AddressX":"Clamp","AddressY":"Clamp"}'
    )
    assert [
        row["Flipbook"]["StaticFrameOverride"]
        for row in document["Layers"]
    ] == [0, 1, 2, 3]
    assert {
        row["Flipbook"]["AssetId"] for row in document["Layers"]
    } == {document["Resources"][0]["Id"]}
    assert all(row["Disposition"] == "Material" for row in document["Layers"])
    assert all(row["Material"] == {} for row in document["Layers"])
    assert all(row["ImageFill"] == {} for row in document["Layers"])


def test_flipbook_qa_pixel_comparison_checks_every_static_frame(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_unreal_umg_flipbook import (
        _compare_frame_grid,
        _write_expected_grid,
    )

    actual = _write_expected_grid(tmp_path / "actual.png")
    expected = _write_expected_grid(tmp_path / "expected.png")
    report = _compare_frame_grid(actual, expected)

    assert report["ok"] is True
    assert report["size_matches"] is True
    assert report["positional_match"] is True
    assert report["pairwise_distinct"] is True
    assert [row["frame"] for row in report["frames"]] == [0, 1, 2, 3]
    assert all(row["rgb_mae"] == 0.0 for row in report["frames"])
    assert all(
        row["rgb_channel_abs_error_max"] == [0, 0, 0]
        for row in report["frames"]
    )
    assert all(row["alpha_error_pixel_count"] == 0 for row in report["frames"])
    assert report["thresholds"]["rgb_channel_abs_error_max"] == 2
    assert report["thresholds"]["alpha_exact"] == 255
    assert report["thresholds"]["rgb_mae_role"] == "diagnostic_only"


def test_flipbook_qa_pixel_comparison_rejects_one_hidden_bad_pixel(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from tools.qa_painter_ui_unreal_umg_flipbook import (
        _compare_frame_grid,
        _write_expected_grid,
    )

    expected = _write_expected_grid(tmp_path / "expected.png")
    tolerated = tmp_path / "one_tolerated_pixel.png"
    tolerated_image = Image.open(expected).convert("RGBA")
    tolerated_image.putpixel((16, 16), (255, 34, 32, 255))
    tolerated_image.save(tolerated)
    tolerated_report = _compare_frame_grid(tolerated, expected)
    assert tolerated_report["ok"] is True
    assert tolerated_report["frames"][0]["rgb_channel_abs_error_max"] == [
        0,
        2,
        0,
    ]

    actual = tmp_path / "one_bad_pixel.png"
    image = Image.open(expected).convert("RGBA")
    image.putpixel((16, 16), (255, 35, 32, 255))
    image.save(actual)

    report = _compare_frame_grid(actual, expected)

    assert report["ok"] is False
    assert report["positional_match"] is False
    assert report["frames"][0]["rgb_error_pixel_count"] == 1
    assert report["frames"][0]["rgb_channel_abs_error_max"] == [0, 3, 0]
    assert report["frames"][0]["rgb_mae"] < 8.0


def test_flipbook_qa_pixel_comparison_rejects_exact_alpha_error(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from tools.qa_painter_ui_unreal_umg_flipbook import (
        _compare_frame_grid,
        _write_expected_grid,
    )

    expected = _write_expected_grid(tmp_path / "expected.png")
    actual = tmp_path / "alpha_error.png"
    image = Image.open(expected).convert("RGBA")
    rgb = image.getpixel((17, 17))[:3]
    image.putpixel((17, 17), (*rgb, 254))
    image.save(actual)

    report = _compare_frame_grid(actual, expected)

    assert report["ok"] is False
    assert report["frames"][0]["rgb_mae"] == 0.0
    assert report["frames"][0]["alpha_error_pixel_count"] == 1


def test_flipbook_qa_pixel_comparison_rejects_swapped_or_duplicate_cells(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from tools.qa_painter_ui_unreal_umg_flipbook import (
        _compare_frame_grid,
        _write_expected_grid,
    )

    expected = _write_expected_grid(tmp_path / "expected.png")
    source = Image.open(expected).convert("RGBA")
    first = source.crop((0, 0, 128, 128))
    second = source.crop((128, 0, 256, 128))

    swapped_path = tmp_path / "swapped.png"
    swapped = source.copy()
    swapped.paste(second, (0, 0))
    swapped.paste(first, (128, 0))
    swapped.save(swapped_path)
    swapped_report = _compare_frame_grid(swapped_path, expected)
    assert swapped_report["ok"] is False
    assert swapped_report["positional_match"] is False
    assert swapped_report["pairwise_distinct"] is True

    duplicate_path = tmp_path / "duplicate.png"
    duplicate = source.copy()
    duplicate.paste(first, (128, 0))
    duplicate.save(duplicate_path)
    duplicate_report = _compare_frame_grid(duplicate_path, expected)
    assert duplicate_report["ok"] is False
    assert duplicate_report["positional_match"] is False
    assert duplicate_report["pairwise_distinct"] is False


def test_flipbook_qa_pixel_comparison_requires_exact_capture_size(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from tools.qa_painter_ui_unreal_umg_flipbook import (
        _compare_frame_grid,
        _write_expected_grid,
    )

    expected = _write_expected_grid(tmp_path / "expected.png")
    actual = tmp_path / "wrong_size.png"
    Image.open(expected).convert("RGBA").resize((255, 256)).save(actual)

    report = _compare_frame_grid(actual, expected)

    assert report["ok"] is False
    assert report["size_matches"] is False
    assert report["required_size"] == [256, 256]
    assert report["frames"] == []


def test_flipbook_qa_unreal_script_verifies_fixed_graph_and_texture_reference(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_unreal_umg_flipbook import _inspection_script

    script = _inspection_script(
        [f"/Game/M{i}.M{i}" for i in range(4)],
        "/Game/Atlas.Atlas",
        tmp_path / "report.json",
    )

    assert 'classes.count("MaterialExpressionTime") == 1' in script
    assert "len(classes) == 12" in script
    assert 'classes.count("MaterialExpressionScalarParameter") == 8' in script
    assert (
        'classes.count("MaterialExpressionTextureSampleParameter2D") == 1'
        in script
    )
    assert 'classes.count("MaterialExpressionComponentMask") == 0' in script
    assert '"StaticFrameOverride": float(expected_overrides[material_path])' in script
    assert '"Texture2DSample" not in row["custom_code"]' in script
    assert 'row["atlas_texture_path"] == texture_path' in script
    assert '"SAMPLERTYPE_COLOR" in row["sampler_type"].upper()' in script
    assert 'and texture_row["srgb"]' in script
    assert "expected_material_packages" in script


def test_flipbook_qa_records_source_backed_render_contract() -> None:
    from tools.qa_painter_ui_unreal_umg_flipbook import RENDER_CONTRACT

    assert RENDER_CONTRACT["platform_path"] == "windows_d3d12"
    assert RENDER_CONTRACT["launch_pins"] == {
        "rhi": "D3D12",
        "display_gamma": 2.2,
        "slate_contrast": 1.0,
    }
    requirements = RENDER_CONTRACT["source_backed_requirements"]
    assert requirements["widget_renderer_use_gamma_correction"] is False
    assert requirements["render_target_pixel_format"] == "PF_B8G8R8A8"
    assert requirements["render_target_srgb"] is True
    assert requirements["atlas_texture_srgb"] is True
    assert requirements["material_sampler_type"] == "SAMPLERTYPE_Color"
    assert requirements["readback_linear_to_gamma"] is False
    assert RENDER_CONTRACT["runtime_probe_scope"]["launch_pinned_not_probed"] == [
        "rhi",
        "display_gamma",
        "slate_contrast",
    ]


def test_flipbook_qa_detects_material_compile_failures() -> None:
    from tools.qa_painter_ui_unreal_umg_flipbook import (
        _material_compile_failures,
    )

    failures = _material_compile_failures(
        "LogMaterial: Failed to compile Material for platform PCD3D_SM5\n"
        "  (Node ComponentMask) Not enough components\n"
    )

    assert len(failures) == 1
    assert "Failed to compile Material" in failures[0]
    assert "Not enough components" in failures[0]

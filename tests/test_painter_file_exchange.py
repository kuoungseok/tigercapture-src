from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest
import numpy as np
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _model(name: str, layer_id: str, **values):
    defaults = dict(
        node_type="paint", parent_id="", visible=True, opacity=100,
        blend_mode="normal", clipping=False, mask=[], layer_type="standard",
        expanded=True,
    )
    defaults.update(values)
    return SimpleNamespace(name=name, layer_id=layer_id, **defaults)


def _art() -> Image.Image:
    image = Image.new("RGBA", (19, 13), (20, 40, 80, 0))
    for y in range(2, 11):
        for x in range(3, 16):
            image.putpixel((x, y), (x * 11, y * 17, 180, 40 + x * 10))
    return image


def test_uint16_to_uint8_uses_png_linear_nearest_rescaling() -> None:
    from app.painter_file_exchange import _rgba16_to_rgba8

    values = np.array(
        [[(0, 129, 32767, 65535), (65534, 32896, 257, 128)]],
        dtype=np.uint16,
    )
    converted = _rgba16_to_rgba8(values)
    expected = np.floor(values.astype(np.float64) * 255.0 / 65535.0 + 0.5).astype(
        np.uint8
    )

    assert np.array_equal(converted, expected)
    assert int(converted[0, 0, 1]) == 1
    assert int((values >> 8)[0, 0, 1]) == 0


@pytest.mark.parametrize("fmt,suffix,alpha", [
    ("png", ".png", True), ("jpeg", ".jpg", False),
    ("webp", ".webp", True), ("tiff", ".tiff", True),
])
def test_flat_8bit_exports_have_dimensions_and_embedded_icc(tmp_path: Path, fmt: str, suffix: str, alpha: bool) -> None:
    from app.painter_file_exchange import export_flat_image

    report = export_flat_image(tmp_path / f"art{suffix}", _art(), format_name=fmt, bit_depth=8)
    assert report["inspection"]["width"] == 19
    assert report["inspection"]["height"] == 13
    assert report["inspection"]["bit_depth"] == 8
    assert report["inspection"]["has_alpha"] is alpha
    assert report["inspection"]["icc_embedded"] is True


@pytest.mark.parametrize("fmt", ["png", "tiff"])
def test_png_and_tiff_16bit_files_reopen_with_icc(tmp_path: Path, fmt: str) -> None:
    from app.painter_file_exchange import export_flat_image

    report = export_flat_image(tmp_path / f"sixteen.{fmt}", _art(), format_name=fmt, bit_depth=16)
    assert report["inspection"]["bit_depth"] == 16
    assert report["inspection"]["icc_embedded"] is True
    with Image.open(report["path"]) as reopened:
        assert reopened.size == _art().size
        assert reopened.getpixel((8, 6))[3] == _art().getpixel((8, 6))[3]


def test_uint8_to_uint16_channel_conversion_spans_exact_full_range() -> None:
    from app.painter_file_exchange import _rgba16_values

    source = np.array([[[0, 1, 254, 255]]], dtype=np.uint8)
    converted = _rgba16_values(source)

    assert converted.dtype == np.uint16
    np.testing.assert_array_equal(
        converted[0, 0],
        np.array([0, 257, 65278, 65535], dtype=np.uint16),
    )


def test_uint16_channel_conversion_preserves_exact_values() -> None:
    from app.painter_file_exchange import _rgba16_values

    source = np.array([[[0, 257, 65278, 65535]]], dtype=np.uint16)
    converted = _rgba16_values(source)

    assert converted.dtype == np.uint16
    np.testing.assert_array_equal(converted, source)
    assert converted is not source


@pytest.mark.parametrize("dtype", [np.int8, np.int16, np.int32, np.uint32, np.bool_])
def test_unsupported_integer_channel_types_are_rejected(dtype) -> None:
    from app.painter_file_exchange import _rgba16_values

    source = np.zeros((1, 1, 4), dtype=dtype)
    with pytest.raises(
        ValueError,
        match="integer input must use uint8 or uint16 channels",
    ):
        _rgba16_values(source)


def test_tiff16_icc_profile_uses_required_undefined_field_type(tmp_path: Path) -> None:
    from app.painter_file_exchange import export_flat_image

    report = export_flat_image(
        tmp_path / "icc-type.tiff", _art(), format_name="tiff", bit_depth=16
    )
    payload = Path(report["path"]).read_bytes()
    byte_order = "<" if payload[:2] == b"II" else ">"
    ifd_offset = struct.unpack_from(f"{byte_order}I", payload, 4)[0]
    entry_count = struct.unpack_from(f"{byte_order}H", payload, ifd_offset)[0]
    entries = [
        struct.unpack_from(f"{byte_order}HHII", payload, ifd_offset + 2 + index * 12)
        for index in range(entry_count)
    ]
    icc_entries = [entry for entry in entries if entry[0] == 34675]

    assert len(icc_entries) == 1
    assert icc_entries[0][1] == 7


def test_tiff16_gray_icc_profile_uses_required_undefined_field_type(tmp_path: Path) -> None:
    from app.painter_file_exchange import export_height_map16

    report = export_height_map16(
        tmp_path / "icc-type-gray.tiff",
        np.linspace(0.0, 1.0, 16, dtype=np.float32).reshape(4, 4),
        format_name="tiff",
    )
    payload = Path(report["path"]).read_bytes()
    byte_order = "<" if payload[:2] == b"II" else ">"
    ifd_offset = struct.unpack_from(f"{byte_order}I", payload, 4)[0]
    entry_count = struct.unpack_from(f"{byte_order}H", payload, ifd_offset)[0]
    entries = [
        struct.unpack_from(f"{byte_order}HHII", payload, ifd_offset + 2 + index * 12)
        for index in range(entry_count)
    ]
    icc_entries = [entry for entry in entries if entry[0] == 34675]

    assert len(icc_entries) == 1
    assert icc_entries[0][1] == 7


@pytest.mark.parametrize("fmt", ["png", "tiff"])
def test_material_height_16bit_preserves_more_than_8bit_precision(tmp_path: Path, fmt: str) -> None:
    import cv2
    from app.painter_file_exchange import export_height_map16

    values = np.linspace(0.0, 1.0, 1024, dtype=np.float32).reshape(16, 64)
    report = export_height_map16(tmp_path / f"height.{fmt}", values, format_name=fmt)
    assert report["inspection"]["bit_depth"] == 16
    assert report["inspection"]["icc_embedded"] is True
    pixels = cv2.imread(report["path"], cv2.IMREAD_UNCHANGED)
    assert pixels is not None and pixels.dtype == np.uint16
    assert len(np.unique(pixels)) > 256


@pytest.mark.parametrize("fmt", ["png", "tiff"])
def test_high_precision_rgba_input_preserves_more_than_8bit_tones(tmp_path: Path, fmt: str) -> None:
    import cv2
    from app.painter_file_exchange import export_flat_image

    ramp = np.linspace(0, 65535, 1024, dtype=np.uint16).reshape(16, 64)
    rgba = np.stack((ramp, np.flip(ramp, axis=1), ramp // 2, np.full_like(ramp, 65535)), axis=2)
    report = export_flat_image(tmp_path / f"rgba16.{fmt}", rgba, format_name=fmt, bit_depth=16)
    reopened = cv2.imread(report["path"], cv2.IMREAD_UNCHANGED)
    assert reopened is not None and reopened.dtype == np.uint16
    assert len(np.unique(reopened[..., 0])) > 256
    assert np.any((reopened[..., 0] % 257) != 0)
    assert report["source_precision_bits"] == 16


def test_print_geometry_reports_real_bleed_trim_and_safe_rects() -> None:
    from app.painter_file_exchange import print_geometry

    geometry = print_geometry({
        "mode": "print", "width_mm": 100, "height_mm": 50, "ppi": 300,
        "bleed_mm": 5, "include_bleed": True, "safe_margin_mm": 4,
    }, 1100, 600)
    assert geometry["bleed_px"] == [50, 50]
    assert geometry["trim_rect_px"] == [50, 50, 1000, 500]
    assert geometry["safe_rect_px"] == [90, 90, 920, 420]


def test_psd_preflight_blocks_or_explicitly_bakes_unsupported_features() -> None:
    from app.painter_file_exchange import exchange_preflight

    layers = [
        _model("Adjustment", "a", node_type="adjustment"),
        _model("Clipped", "b", clipping=True),
        _model("Masked", "c", mask=[(0, 0), (1, 0), (1, 1)]),
        _model("Unsupported Group", "d", node_type="group", blend_mode="vivid_light"),
    ]
    blocked = exchange_preflight(layers, format_name="psd")
    assert blocked["ok"] is False and blocked["unsupported_policy"] == "blocked"
    assert blocked["soft_proof"]["cmyk_conversion_supported"] is False
    assert "proofed" in blocked["soft_proof"]["warning"]
    assert {row["reason"] for row in blocked["unsupported"]} == {"adjustment_layer", "clipping_mask", "layer_mask", "blend_mode:vivid_light"}
    baked = exchange_preflight(layers, format_name="psd", bake_unsupported=True)
    assert baked["ok"] is True and baked["unsupported_policy"] == "bake"
    cmyk = exchange_preflight([], format_name="tiff", color_mode="CMYK")
    assert cmyk["ok"] is False and "not implemented" in cmyk["errors"][0]


def test_layered_psd_roundtrip_preserves_supported_hierarchy_and_properties(tmp_path: Path) -> None:
    from app.painter_file_exchange import export_layered_psd, import_layered_psd

    transparent = Image.new("RGBA", (19, 13), (0, 0, 0, 0))
    rows = [
        {"model": _model("Background", "bottom", opacity=72, blend_mode="multiply"), "image": _art()},
        {"model": _model("Characters", "group", node_type="group", visible=False, opacity=73, blend_mode="multiply"), "image": None},
        {"model": _model("Ink", "ink", parent_id="group", opacity=84, blend_mode="screen"), "image": transparent},
    ]
    report = export_layered_psd(tmp_path / "layers.psd", rows, size=(19, 13))
    assert report["icc_embedded"] is True
    assert report["icc"]["valid"] is True
    assert report["inspection"]["integrity"]["valid"] is True
    reopened = import_layered_psd(report["path"])
    by_name = {row["name"]: row for row in reopened["layers"]}
    assert [row["name"] for row in reopened["layers"]] == ["Background", "Characters", "Ink"]
    assert by_name["Background"]["opacity"] == 72
    assert by_name["Background"]["blend_mode"] == "multiply"
    assert by_name["Ink"]["opacity"] == 84
    assert by_name["Ink"]["parent_id"] == by_name["Characters"]["source_id"]
    assert by_name["Characters"]["visible"] is False
    assert by_name["Characters"]["opacity"] == 73
    assert by_name["Characters"]["blend_mode"] == "multiply"


def test_psd_corruption_is_reported_and_import_is_blocked(tmp_path: Path) -> None:
    from app.painter_file_exchange import (
        export_layered_psd,
        import_layered_psd,
        inspect_layered_psd,
    )

    report = export_layered_psd(
        tmp_path / "valid.psd",
        [{"model": _model("Paint", "paint"), "image": _art()}],
        size=_art().size,
        composite=_art(),
    )
    payload = Path(report["path"]).read_bytes()
    damaged = tmp_path / "damaged.psd"
    damaged.write_bytes(b"NOPE" + payload[4:])
    truncated = tmp_path / "truncated.psd"
    truncated.write_bytes(payload[:40])
    assert inspect_layered_psd(damaged)["integrity"]["valid"] is False
    assert inspect_layered_psd(truncated)["integrity"]["valid"] is False
    with pytest.raises(ValueError, match="corrupted PSD"):
        import_layered_psd(damaged)


def test_flat_image_decoder_failure_is_reported_as_invalid(
    tmp_path: Path, monkeypatch
) -> None:
    from PIL import Image
    from app.painter_file_exchange import inspect_flat_image

    source = tmp_path / "decoder-failure.jpg"
    source.write_bytes(b"not-an-image")

    def fail_decode(*_args, **_kwargs):
        raise OSError("forced flat decoder failure")

    monkeypatch.setattr(Image, "open", fail_decode)
    report = inspect_flat_image(source)

    assert report["integrity"]["valid"] is False
    assert report["integrity"]["decode_complete"] is False
    assert report["width"] == 0
    assert report["height"] == 0
    assert "decode failed: OSError: forced flat decoder failure" in report["integrity"]["errors"]
    assert report["integrity"]["decode_error"] == {
        "type": "OSError",
        "message": "forced flat decoder failure",
    }


def test_psd_decoder_failure_is_reported_and_import_remains_blocked(
    tmp_path: Path, monkeypatch
) -> None:
    from psd_tools import PSDImage
    from app.painter_file_exchange import (
        export_layered_psd,
        import_layered_psd,
        inspect_layered_psd,
    )

    exported = export_layered_psd(
        tmp_path / "decoder-failure.psd",
        [{"model": _model("Paint", "paint"), "image": _art()}],
        size=_art().size,
        composite=_art(),
    )
    source = Path(exported["path"])

    def fail_decode(*_args, **_kwargs):
        raise OSError("forced PSD decoder failure")

    monkeypatch.setattr(PSDImage, "open", fail_decode)
    report = inspect_layered_psd(source)

    assert report["integrity"]["valid"] is False
    assert report["integrity"]["decode_complete"] is False
    assert report["layers"] == []
    assert "decode failed: OSError: forced PSD decoder failure" in report["integrity"]["errors"]
    assert report["integrity"]["decode_error"] == {
        "type": "OSError",
        "message": "forced PSD decoder failure",
    }
    with pytest.raises(ValueError, match="decode failed: OSError"):
        import_layered_psd(source)


def test_layered_psd_composite_preserves_bottom_to_top_paint_order(tmp_path: Path) -> None:
    import numpy as np
    from PIL import Image
    from psd_tools import PSDImage
    from app.painter_file_exchange import export_layered_psd

    bottom = Image.new("RGBA", (12, 8), (18, 34, 58, 255))
    middle = Image.new("RGBA", (12, 8), (0, 0, 0, 0))
    for y in range(2, 7):
        for x in range(1, 8):
            middle.putpixel((x, y), (210, 88, 42, 255))
    top = Image.new("RGBA", (12, 8), (0, 0, 0, 0))
    top.putpixel((9, 1), (250, 220, 90, 255))
    expected = Image.alpha_composite(Image.alpha_composite(bottom, middle), top)
    report = export_layered_psd(
        tmp_path / "paint-order.psd",
        [
            {"model": _model("Bottom", "bottom"), "image": bottom},
            {"model": _model("Middle", "middle"), "image": middle},
            {"model": _model("Top", "top"), "image": top},
        ],
        size=(12, 8),
        composite=expected,
    )
    reopened = PSDImage.open(report["path"])
    actual = reopened.composite(force=True).convert("RGBA")
    delta = np.abs(np.asarray(expected, dtype=np.int16) - np.asarray(actual, dtype=np.int16))
    assert [layer.name for layer in reopened] == ["Bottom", "Middle", "Top"]
    assert int(delta.max()) <= report["composite_parity"]["visible_pixel_layer_stages"]
    assert report["composite_parity"]["within_tolerance"] is True
    assert report["composite_parity"]["max_delta_lsb"] == report["composite_parity"]["visible_pixel_layer_stages"]
    assert report["composite_parity"]["visible_pixel_layer_stages"] == 3
    assert report["composite_parity"]["tolerance_contract"] == "8bit_one_lsb_per_visible_alpha_over_stage"
    assert report["composite_parity"]["byte_identical_claim"] is False


def test_psd_named_extra_alpha_channels_round_trip_exact_bytes(tmp_path: Path) -> None:
    from psd_tools import PSDImage
    from psd_tools.constants import Resource
    from app.painter_alpha_channel_exchange import qimage_from_alpha8_bytes
    from app.painter_file_exchange import export_layered_psd, import_layered_psd
    from app.painter_saved_selection_channels import SavedSelectionChannel

    width, height = _art().size
    first = bytes((index * 17) % 256 for index in range(width * height))
    second = bytes(255 - value for value in first)
    channels = [
        SavedSelectionChannel(
            "saved-selection-1",
            "인물 선택",
            qimage_from_alpha8_bytes(first, width, height),
            "selected_areas",
            "#123456",
            75,
        ),
        SavedSelectionChannel(
            "saved-selection-2",
            "Edge Mask",
            qimage_from_alpha8_bytes(second, width, height),
        ),
    ]
    exported = export_layered_psd(
        tmp_path / "extra-alpha.psd",
        [{"model": _model("Paint", "paint"), "image": _art()}],
        size=(width, height),
        composite=_art(),
        saved_selection_channels=channels,
    )

    reopened = PSDImage.open(exported["path"])
    assert reopened.channels == 6
    assert reopened.topil().mode == "RGBA"
    assert reopened.topil(channel=4, apply_icc=False).tobytes() == first
    assert reopened.topil(channel=5, apply_icc=False).tobytes() == second
    assert list(reopened.image_resources.get_data(Resource.ALPHA_IDENTIFIERS)) == [
        0,
        1,
        2,
    ]
    assert list(reopened.image_resources.get_data(Resource.ALPHA_NAMES_UNICODE)) == [
        "인물 선택",
        "Edge Mask",
    ]
    assert [
        row["name"] for row in exported["inspection"]["saved_selection_channels"]
    ] == ["인물 선택", "Edge Mask"]
    imported = import_layered_psd(exported["path"])
    assert [row["pixels"] for row in imported["saved_selection_channels"]] == [
        first,
        second,
    ]
    assert [row["name"] for row in imported["saved_selection_channels"]] == [
        "인물 선택",
        "Edge Mask",
    ]
    saved_report = exported["saved_selection_channels"]
    assert saved_report["preserved"] is True
    assert saved_report["names_preserved"] is True
    assert saved_report["display_options_preserved"] is False
    assert saved_report["channels"][0]["source_display_options"] == {
        "display_mode": "selected_areas",
        "overlay_color": "#123456",
        "overlay_opacity_percent": 75,
    }


def test_psd_extra_alpha_import_rejects_non_8bit_depth_before_decode() -> None:
    from psd_tools import PSDImage
    from app.painter_alpha_channel_exchange import read_psd_saved_selection_channels

    psd = PSDImage.new("RGBA", (2, 1), depth=16, color=(0, 0, 0, 0))
    with pytest.raises(ValueError, match="requires 8-bit channel depth"):
        read_psd_saved_selection_channels(psd)


@pytest.mark.parametrize("bit_depth", [8, 16])
def test_tiff_unspecified_extra_alpha_channels_round_trip_exact_alpha8(
    tmp_path: Path,
    bit_depth: int,
) -> None:
    from app.painter_alpha_channel_exchange import (
        qimage_from_alpha8_bytes,
        read_tiff_saved_selection_channels,
    )
    from app.painter_file_exchange import export_flat_image
    from app.painter_saved_selection_channels import SavedSelectionChannel

    width, height = _art().size
    first = bytes((index * 31) % 256 for index in range(width * height))
    second = bytes(255 - value for value in first)
    channels = [
        SavedSelectionChannel(
            "saved-selection-1",
            "Subject",
            qimage_from_alpha8_bytes(first, width, height),
        ),
        SavedSelectionChannel(
            "saved-selection-2",
            "Edge",
            qimage_from_alpha8_bytes(second, width, height),
        ),
    ]
    exported = export_flat_image(
        tmp_path / f"extra-alpha-{bit_depth}.tiff",
        _art(),
        format_name="tiff",
        bit_depth=bit_depth,
        saved_selection_channels=channels,
    )
    reopened = read_tiff_saved_selection_channels(exported["path"])

    assert reopened["bit_depth"] == bit_depth
    assert reopened["samples_per_pixel"] == 6
    assert reopened["extra_samples"] == [2, 0, 0]
    assert [row["pixels"] for row in reopened["saved_selection_channels"]] == [
        first,
        second,
    ]
    assert [row["name"] for row in reopened["saved_selection_channels"]] == [
        "Alpha 1",
        "Alpha 2",
    ]
    assert reopened["names_preserved"] is False
    assert exported["saved_selection_channels"]["preserved"] is True
    exchange = exported["inspection"]["saved_selection_channel_exchange"]
    assert exchange["extra_samples"] == [2, 0, 0]
    assert len(exchange["saved_selection_channels"]) == 2


def test_flat_format_reports_saved_channel_omission_instead_of_silent_drop(
    tmp_path: Path,
) -> None:
    from app.painter_alpha_channel_exchange import qimage_from_alpha8_bytes
    from app.painter_file_exchange import export_flat_image
    from app.painter_saved_selection_channels import SavedSelectionChannel

    width, height = _art().size
    channel = SavedSelectionChannel(
        "saved-selection-1",
        "Subject",
        qimage_from_alpha8_bytes(bytes([255]) * (width * height), width, height),
    )
    exported = export_flat_image(
        tmp_path / "flat.png",
        _art(),
        format_name="png",
        saved_selection_channels=[channel],
    )

    assert exported["saved_selection_channels"]["count"] == 1
    assert exported["saved_selection_channels"]["preserved"] is False
    assert any(
        "not preserved" in warning
        for warning in exported["preflight"]["warnings"]
    )


def test_dialog_export_actions_and_psd_import_have_undo(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(background_pixmap=create_blank_paint_pixmap(19, 13, "transparent"), initial_strokes=[], time_ms=0, standalone=True)
    dialog._set_paint_layer_raster(dialog._active_paint_layer_id, dialog._pil_rgba_to_qimage(_art()))
    dialog._paint_layer_by_id(dialog._active_paint_layer_id).name = "Original"
    original_pixels = dialog._painter_composite_pil(include_background=False).tobytes()
    from app.painter_alpha_channel_exchange import (
        qimage_from_alpha8_bytes,
        saved_selection_exchange_records,
    )
    from app.painter_saved_selection_channels import SavedSelectionChannel

    alpha_pixels = bytes(
        (index * 29) % 256
        for index in range(19 * 13)
    )
    dialog._saved_selection_channels = [SavedSelectionChannel(
        "saved-selection-1",
        "Subject",
        qimage_from_alpha8_bytes(alpha_pixels, 19, 13),
        "selected_areas",
        "#00ff00",
        25,
    )]
    dialog._saved_selection_channel_serial = 1
    dialog._channel_visibility["saved-selection-1"] = True
    psd = tmp_path / "dialog.psd"
    report = dialog.export_document_to_path(psd)
    assert Path(report["path"]).exists()
    imported = dialog.import_psd_document_from_path(psd)
    assert imported["layers"][0]["name"] == "Original"
    assert dialog._paint_layers[0].name == "Original"
    assert dialog._canvas_document_size == (19, 13)
    assert dialog._painter_composite_pil(include_background=False).tobytes() == original_pixels
    assert imported["imported_saved_selection_channel_ids"] == [
        "saved-selection-1"
    ]
    restored_channel = dialog._saved_selection_channels[0]
    assert restored_channel.name == "Subject"
    assert saved_selection_exchange_records(
        [restored_channel], 19, 13
    )[0]["pixels"] == alpha_pixels
    assert restored_channel.display_mode == "masked_areas"
    assert restored_channel.overlay_color == "#ff0000"
    assert restored_channel.overlay_opacity_percent == 50
    assert dialog._channel_visibility[restored_channel.channel_id] is False
    dialog._undo()
    assert dialog._paint_layers[0].name == "Original"
    registry = ActionRegistry(owner=dialog)
    ids = {row["id"] for row in registry.list_actions()}
    assert {"paint.document.exchange.preflight", "paint.document.export", "paint.document.import_psd"} <= ids
    action_import = registry.execute(
        "paint.document.import_psd",
        {"path": str(psd)},
    ).to_dict()
    assert action_import["ok"]
    json.dumps(action_import)
    assert "image" not in action_import["result"]["layers"][0]
    assert "pixels" not in action_import["result"]["saved_selection_channels"][0]
    dialog.close(); app.processEvents()


def test_tiff_channel_action_import_is_exact_atomic_and_one_undo(
    tmp_path: Path,
) -> None:
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_alpha_channel_exchange import (
        qimage_from_alpha8_bytes,
        saved_selection_exchange_records,
    )
    from app.painter_file_exchange import export_flat_image
    from app.painter_saved_selection_channels import SavedSelectionChannel

    app = QApplication.instance() or QApplication([])
    width, height = _art().size
    alpha_pixels = bytes((index * 43) % 256 for index in range(width * height))
    source = tmp_path / "action-alpha.tiff"
    export_flat_image(
        source,
        _art(),
        format_name="tiff",
        bit_depth=16,
        saved_selection_channels=[SavedSelectionChannel(
            "saved-selection-1",
            "Source name is not a TIFF field",
            qimage_from_alpha8_bytes(alpha_pixels, width, height),
        )],
    )
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(width, height, "#203040"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    background_before = QImage(dialog._bg_pixmap_source.toImage())
    layers_before = [row.layer_id for row in dialog._paint_layers]
    undo_before = len(dialog._undo_stack)
    result = ActionRegistry(owner=dialog).execute(
        "paint.selection.channels.import_file",
        {"path": str(source)},
    ).to_dict()

    assert result["ok"]
    json.dumps(result)
    assert result["result"]["count"] == 1
    assert result["result"]["names"] == ["Alpha 1"]
    assert result["result"]["names_preserved"] is False
    assert result["result"]["display_options_preserved"] is False
    assert len(dialog._undo_stack) == undo_before + 1
    assert dialog._bg_pixmap_source.toImage() == background_before
    assert [row.layer_id for row in dialog._paint_layers] == layers_before
    assert saved_selection_exchange_records(
        dialog._saved_selection_channels, width, height
    )[0]["pixels"] == alpha_pixels
    assert dialog._channel_visibility[dialog._saved_selection_channels[0].channel_id] is False
    dialog._undo()
    assert dialog._saved_selection_channels == []
    dialog._redo()
    assert saved_selection_exchange_records(
        dialog._saved_selection_channels, width, height
    )[0]["pixels"] == alpha_pixels
    undo_after_redo = len(dialog._undo_stack)
    channels_after_redo = list(dialog._saved_selection_channels)
    duplicate_name = ActionRegistry(owner=dialog).execute(
        "paint.selection.channels.import_file",
        {"path": str(source)},
    ).to_dict()
    assert not duplicate_name["ok"]
    assert len(dialog._undo_stack) == undo_after_redo
    assert dialog._saved_selection_channels == channels_after_redo

    mismatch = tmp_path / "mismatched-alpha.tiff"
    mismatch_width = width + 1
    export_flat_image(
        mismatch,
        Image.new("RGBA", (mismatch_width, height), (0, 0, 0, 0)),
        format_name="tiff",
        saved_selection_channels=[SavedSelectionChannel(
            "saved-selection-1",
            "Mismatch",
            qimage_from_alpha8_bytes(
                bytes(mismatch_width * height), mismatch_width, height
            ),
        )],
    )
    mismatch_result = ActionRegistry(owner=dialog).execute(
        "paint.selection.channels.import_file",
        {"path": str(mismatch)},
    ).to_dict()
    assert not mismatch_result["ok"]
    assert len(dialog._undo_stack) == undo_after_redo
    assert dialog._saved_selection_channels == channels_after_redo
    dialog.close()
    app.processEvents()


def test_psd_saved_alpha_channel_count_cannot_exceed_format_header_limit(
    tmp_path: Path,
) -> None:
    from app.painter_alpha_channel_exchange import qimage_from_alpha8_bytes
    from app.painter_file_exchange import export_layered_psd
    from app.painter_saved_selection_channels import SavedSelectionChannel

    width, height = _art().size
    mask = qimage_from_alpha8_bytes(bytes(width * height), width, height)
    channels = [
        SavedSelectionChannel(f"saved-selection-{index}", f"Alpha {index}", mask)
        for index in range(1, 54)
    ]
    destination = tmp_path / "too-many-alpha.psd"
    with pytest.raises(ValueError, match="at most 56"):
        export_layered_psd(
            destination,
            [{"model": _model("Paint", "paint"), "image": _art()}],
            size=(width, height),
            composite=_art(),
            saved_selection_channels=channels,
        )
    assert not destination.exists()


def test_tiff16_saved_alpha_rejects_values_not_exactly_representable_as_alpha8(
    tmp_path: Path,
) -> None:
    from app.painter_alpha_channel_exchange import (
        qimage_from_alpha8_bytes,
        read_tiff_saved_selection_channels,
    )
    from app.painter_file_exchange import export_flat_image, inspect_flat_image
    from app.painter_saved_selection_channels import SavedSelectionChannel

    width, height = _art().size
    destination = tmp_path / "non-alpha8.tiff"
    export_flat_image(
        destination,
        _art(),
        format_name="tiff",
        bit_depth=16,
        saved_selection_channels=[SavedSelectionChannel(
            "saved-selection-1",
            "Alpha",
            qimage_from_alpha8_bytes(bytes(width * height), width, height),
        )],
    )
    payload = bytearray(destination.read_bytes())
    endian = "<" if payload[:2] == b"II" else ">"
    ifd_offset = struct.unpack_from(f"{endian}I", payload, 4)[0]
    entry_count = struct.unpack_from(f"{endian}H", payload, ifd_offset)[0]
    entries = {
        tag: (field_type, count, value)
        for tag, field_type, count, value in (
            struct.unpack_from(f"{endian}HHII", payload, ifd_offset + 2 + index * 12)
            for index in range(entry_count)
        )
    }
    strip_offset = entries[273][2]
    # RGBA is followed by the first saved-selection sample in chunky order.
    struct.pack_into(f"{endian}H", payload, strip_offset + 4 * 2, 1)
    destination.write_bytes(payload)

    with pytest.raises(ValueError, match="exactly as Alpha8"):
        read_tiff_saved_selection_channels(destination)
    inspected = inspect_flat_image(destination)
    assert inspected["integrity"]["valid"] is False
    assert inspected["integrity"]["custom_decode_error"] == {
        "type": "ValueError",
        "message": "16-bit TIFF alpha channel cannot be represented exactly as Alpha8",
    }
    assert any(
        "Tiger TIFF decoder failed" in message
        for message in inspected["integrity"]["errors"]
    )


def test_tiff_extra_alpha_rejects_wrong_required_type_and_duplicate_ifd_tag(
    tmp_path: Path,
) -> None:
    from app.painter_alpha_channel_exchange import (
        qimage_from_alpha8_bytes,
        read_tiff_saved_selection_channels,
    )
    from app.painter_file_exchange import export_flat_image
    from app.painter_saved_selection_channels import SavedSelectionChannel

    width, height = _art().size
    source = tmp_path / "strict-ifd.tiff"
    export_flat_image(
        source,
        _art(),
        format_name="tiff",
        saved_selection_channels=[SavedSelectionChannel(
            "saved-selection-1",
            "Alpha",
            qimage_from_alpha8_bytes(bytes(width * height), width, height),
        )],
    )
    original = bytearray(source.read_bytes())
    endian = "<" if original[:2] == b"II" else ">"
    ifd_offset = struct.unpack_from(f"{endian}I", original, 4)[0]
    entry_count = struct.unpack_from(f"{endian}H", original, ifd_offset)[0]
    entry_offsets = {}
    for index in range(entry_count):
        offset = ifd_offset + 2 + index * 12
        tag = struct.unpack_from(f"{endian}H", original, offset)[0]
        entry_offsets[tag] = offset

    wrong_type = bytearray(original)
    struct.pack_into(f"{endian}H", wrong_type, entry_offsets[259] + 2, 4)
    wrong_type_path = tmp_path / "wrong-compression-type.tiff"
    wrong_type_path.write_bytes(wrong_type)
    with pytest.raises(ValueError, match="tag 259 has an invalid field type"):
        read_tiff_saved_selection_channels(wrong_type_path)

    duplicate = bytearray(original)
    struct.pack_into(f"{endian}H", duplicate, entry_offsets[34675], 259)
    duplicate_path = tmp_path / "duplicate-compression-tag.tiff"
    duplicate_path.write_bytes(duplicate)
    with pytest.raises(ValueError, match="duplicate IFD tag"):
        read_tiff_saved_selection_channels(duplicate_path)


def test_layered_psd_export_rejects_invalid_dimensions_instead_of_resizing(
    tmp_path: Path,
) -> None:
    from app.painter_file_exchange import export_layered_psd

    with pytest.raises(ValueError, match="PSD export width must be positive"):
        export_layered_psd(tmp_path / "invalid.psd", [], size=(0, 13))

    with pytest.raises(TypeError, match="PSD export width must be an integer"):
        export_layered_psd(tmp_path / "invalid.psd", [], size=(12.5, 13))

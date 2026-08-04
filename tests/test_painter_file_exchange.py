from __future__ import annotations

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


def test_dialog_export_actions_and_psd_import_have_undo(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(background_pixmap=create_blank_paint_pixmap(19, 13, "transparent"), initial_strokes=[], time_ms=0, standalone=True)
    dialog._set_paint_layer_raster(dialog._active_paint_layer_id, dialog._pil_rgba_to_qimage(_art()))
    dialog._paint_layer_by_id(dialog._active_paint_layer_id).name = "Original"
    original_pixels = dialog._painter_composite_pil(include_background=False).tobytes()
    psd = tmp_path / "dialog.psd"
    report = dialog.export_document_to_path(psd)
    assert Path(report["path"]).exists()
    imported = dialog.import_psd_document_from_path(psd)
    assert imported["layers"][0]["name"] == "Original"
    assert dialog._paint_layers[0].name == "Original"
    assert dialog._canvas_document_size == (19, 13)
    assert dialog._painter_composite_pil(include_background=False).tobytes() == original_pixels
    dialog._undo()
    assert dialog._paint_layers[0].name == "Original"
    registry = ActionRegistry(owner=dialog)
    ids = {row["id"] for row in registry.list_actions()}
    assert {"paint.document.exchange.preflight", "paint.document.export", "paint.document.import_psd"} <= ids
    dialog.close(); app.processEvents()

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _rgba() -> Image.Image:
    image = Image.new("RGBA", (8, 6), (30, 90, 170, 0))
    for y in range(6):
        for x in range(8):
            image.putpixel((x, y), (20 + x * 20, 30 + y * 24, 180, 20 + x * 25))
    return image


def test_icc_v4_validation_transform_and_soft_proof_preserve_alpha() -> None:
    from app.painter_color_management import (
        inspect_icc_profile,
        soft_proof_rgba,
        transform_rgba_profile,
    )
    from app.painter_file_exchange import srgb_icc_bytes

    profile = srgb_icc_bytes()
    inspected = inspect_icc_profile(profile, require_v4=True)
    assert inspected["valid"] is True
    assert inspected["version_major"] == 4
    assert inspected["color_space"].strip() == "RGB"
    transformed, transform = transform_rgba_profile(
        _rgba(), source_profile=profile, output_profile=profile
    )
    assert transform["applied"] is True
    assert transform["identity_profiles"] is True
    assert transform["alpha_preserved"] is True
    assert transformed.getchannel("A").tobytes() == _rgba().getchannel("A").tobytes()
    proofed, proof = soft_proof_rgba(
        _rgba(), source_profile=profile, proof_profile=profile, display_profile=profile
    )
    assert proof["applied"] is True
    assert proof["alpha_preserved"] is True
    assert proofed.getchannel("A").tobytes() == _rgba().getchannel("A").tobytes()


def test_icc_validation_rejects_bad_size_signature_and_v2_requirement() -> None:
    from app.painter_color_management import inspect_icc_profile
    from app.painter_file_exchange import srgb_icc_bytes

    profile = bytearray(srgb_icc_bytes())
    profile[0:4] = (len(profile) + 9).to_bytes(4, "big")
    profile[36:40] = b"nope"
    report = inspect_icc_profile(bytes(profile), require_v4=True)
    assert report["valid"] is False
    assert any("size" in error for error in report["errors"])
    assert any("acsp" in error for error in report["errors"])


def test_icc_validation_reports_littlecms_rejection_as_typed_validation_error() -> None:
    from app.painter_color_management import inspect_icc_profile

    report = inspect_icc_profile(b"not-an-icc-profile")

    assert report["valid"] is False
    assert report["littlecms_valid"] is False
    assert any(error.startswith("LittleCMS rejected profile: ") for error in report["errors"])
    assert any("PIL" in error or "OSError" in error for error in report["errors"])


def test_export_reports_native_vs_promoted_precision_and_real_transform(tmp_path: Path) -> None:
    from app.painter_file_exchange import export_flat_image, srgb_icc_bytes

    promoted = export_flat_image(
        tmp_path / "promoted.png", _rgba(), format_name="png", bit_depth=16
    )
    assert promoted["source_precision_kind"] == "promoted_from_8bit"
    assert promoted["new_precision_created"] is False
    assert promoted["inspection"]["integrity"]["valid"] is True
    ramp = np.linspace(0, 65535, 384, dtype=np.uint16).reshape(6, 8, 8)[..., :4]
    native = export_flat_image(
        tmp_path / "native.png", ramp, format_name="png", bit_depth=16
    )
    assert native["source_precision_kind"] == "native_high_precision"
    explicit = export_flat_image(
        tmp_path / "managed.png",
        _rgba(),
        format_name="png",
        source_icc=srgb_icc_bytes(),
        output_icc=srgb_icc_bytes(),
    )
    assert explicit["profile_transform"]["applied"] is True
    assert explicit["profile_transform"]["alpha_preserved"] is True


def test_png_crc_and_truncated_tiff_are_reported_as_corruption(tmp_path: Path) -> None:
    from app.painter_file_exchange import export_flat_image, inspect_flat_image

    png = export_flat_image(tmp_path / "clean.png", _rgba(), format_name="png")["path"]
    data = bytearray(Path(png).read_bytes())
    data[-8] ^= 0x01  # damage the IEND CRC without changing file length
    damaged_png = tmp_path / "damaged.png"
    damaged_png.write_bytes(data)
    png_report = inspect_flat_image(damaged_png)
    assert png_report["integrity"]["valid"] is False
    assert any("CRC" in error for error in png_report["integrity"]["errors"])

    tiff = export_flat_image(tmp_path / "clean.tiff", _rgba(), format_name="tiff")["path"]
    truncated = tmp_path / "truncated.tiff"
    truncated.write_bytes(Path(tiff).read_bytes()[:64])
    tiff_report = inspect_flat_image(truncated)
    assert tiff_report["integrity"]["valid"] is False
    assert tiff_report["integrity"]["decode_complete"] is False
    assert tiff_report["integrity"]["container_valid"] is False

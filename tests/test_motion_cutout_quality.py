from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from app.motion_designer.cutout_quality import (
    analyze_cutout_rgba,
    evaluate_decomposition_cutout_quality,
)
from app.motion_designer.image_decomposition import (
    DecomposedImageElement,
    ImageDecompositionResult,
    compile_decomposition_layers,
)
from app.motion_designer.schema import MotionComposition


def test_opaque_background_plate_is_rejected() -> None:
    rgba = np.zeros((180, 320, 4), dtype=np.uint8)
    rgba[:, :, :3] = (236, 232, 224)
    rgba[:, :, 3] = 255

    report = analyze_cutout_rgba(rgba, element_id="subject")

    assert report.accepted is False
    assert report.status == "failed"
    assert "opaque_background_plate" in report.to_dict()["blockers"]
    assert "foreground_covers_frame" in report.to_dict()["blockers"]


def test_clean_transparent_subject_passes() -> None:
    image = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((95, 18, 225, 174), fill=(205, 54, 45, 255))

    report = analyze_cutout_rgba(np.asarray(image), element_id="subject")

    assert report.accepted is True
    assert report.status == "passed"
    assert report.blockers == []


def test_bright_boundary_requests_review_without_false_success_failure() -> None:
    image = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((82, 12, 238, 176), fill=(245, 245, 242, 255))
    draw.ellipse((90, 20, 230, 176), fill=(185, 52, 44, 255))

    report = analyze_cutout_rgba(np.asarray(image), element_id="subject")

    assert report.accepted is True
    assert report.status == "review"
    assert "bright_edge_spill" in report.to_dict()["warnings"]


def test_mask_boundary_cutting_through_same_background_is_rejected() -> None:
    rgba = np.zeros((180, 320, 4), dtype=np.uint8)
    rgba[:, :, :3] = (232, 228, 219)
    rgba[32:176, 108:212, :3] = (176, 54, 45)
    alpha = Image.new("L", (320, 180), 0)
    draw = ImageDraw.Draw(alpha)
    draw.ellipse((54, 8, 266, 179), fill=255)
    rgba[:, :, 3] = np.asarray(alpha)

    report = analyze_cutout_rgba(rgba, element_id="subject")

    assert report.accepted is False
    assert "background_connected_to_subject" in report.to_dict()["blockers"]


def test_failed_quality_contract_blocks_motion_compilation(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    background = tmp_path / "background.png"
    element_path = tmp_path / "element.png"
    mask_path = tmp_path / "mask.png"
    Image.new("RGB", (320, 180), (30, 35, 40)).save(source)
    Image.new("RGB", (320, 180), (30, 35, 40)).save(background)
    Image.new("RGBA", (320, 180), (220, 220, 220, 255)).save(element_path)
    Image.new("L", (320, 180), 255).save(mask_path)
    result = ImageDecompositionResult(
        source_path=str(source),
        source_hash="opaque-test",
        width=320,
        height=180,
        background_path=str(background),
        elements=[
            DecomposedImageElement(
                id="subject",
                role="primary_subject",
                label="Subject",
                bbox=(0, 0, 320, 180),
                rgba_path=str(element_path),
                mask_path=str(mask_path),
                area_ratio=1.0,
                depth=0.5,
                confidence=0.8,
            )
        ],
    )

    quality = evaluate_decomposition_cutout_quality(result)
    assert quality["accepted"] is False

    composition = MotionComposition(width=320, height=180, duration_ms=1000)
    try:
        compile_decomposition_layers(
            composition,
            result,
            reference_id="opaque",
            name="Opaque",
            in_ms=0,
            out_ms=1000,
            center=(160.0, 90.0),
            size=(320, 180),
        )
    except ValueError as exc:
        assert "Cutout quality gate rejected" in str(exc)
    else:
        raise AssertionError("opaque cutout should not compile without an override")

    layers = compile_decomposition_layers(
        composition,
        result,
        reference_id="opaque",
        name="Opaque",
        in_ms=0,
        out_ms=1000,
        center=(160.0, 90.0),
        size=(320, 180),
        allow_quality_override=True,
    )
    assert layers

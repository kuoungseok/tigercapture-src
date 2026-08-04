from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.motion_designer.image_decomposition import (
    DecomposedImageElement,
    ImageDecompositionResult,
)
from app.motion_designer.layer_readiness import (
    LAYER_READINESS_SCHEMA,
    assess_layer_motion_readiness,
)


def _result(tmp_path: Path, *, opaque: bool) -> ImageDecompositionResult:
    source = tmp_path / "source.png"
    background = tmp_path / "background.png"
    foreground = tmp_path / "foreground.png"
    mask = tmp_path / "mask.png"

    source_image = Image.new("RGBA", (160, 90), (0, 0, 0, 0))
    source_draw = ImageDraw.Draw(source_image)
    source_draw.ellipse((48, 8, 112, 88), fill=(220, 70, 45, 255))
    source_image.save(source)
    Image.new("RGBA", (160, 90), (0, 0, 0, 0)).save(background)
    if opaque:
        Image.new("RGBA", (160, 90), (235, 232, 225, 255)).save(foreground)
        Image.new("L", (160, 90), 255).save(mask)
    else:
        source_image.save(foreground)
        source_image.getchannel("A").save(mask)

    return ImageDecompositionResult(
        source_path=str(source),
        source_hash="readiness-test",
        width=160,
        height=90,
        background_path=str(background),
        elements=[DecomposedImageElement(
            id="subject",
            role="primary_subject",
            label="Subject",
            bbox=(48, 8, 65, 81),
            rgba_path=str(foreground),
            mask_path=str(mask),
            area_ratio=0.36,
            depth=0.6,
            confidence=0.95,
        )],
        diagnostics={
            "transparent_source": True,
            "segmentation": {
                "provider": "source_alpha",
                "confidence": 1.0,
            },
            "inpaint": {
                "provider": "transparent_canvas",
                "confidence": 1.0,
                "coverage": 0.36,
                "max_camera_travel_ratio": 0.12,
            },
        },
    )


def test_clean_source_alpha_decomposition_is_ready(tmp_path: Path) -> None:
    report = assess_layer_motion_readiness(
        _result(tmp_path, opaque=False),
        setup_status={
            "automatic_cutout_ready": False,
            "assisted_segmentation_ready": False,
        },
    )

    assert report["schema"] == LAYER_READINESS_SCHEMA
    assert report["status"] == "ready"
    assert report["ready"] is True
    assert report["can_compile"] is True
    assert report["repair_plan"] == []


def test_opaque_foreground_returns_ordered_repair_and_fallback(tmp_path: Path) -> None:
    report = assess_layer_motion_readiness(
        _result(tmp_path, opaque=True),
        setup_status={
            "automatic_cutout_ready": True,
            "assisted_segmentation_ready": True,
        },
    )

    assert report["status"] == "repair_required"
    assert report["ready"] is False
    assert report["can_compile"] is False
    assert "opaque_background_plate" in {
        row["code"] for row in report["issues"]
    }
    assert report["repair_plan"][0]["action_id"] == "motion.ai.layer.mask.refine"
    assert report["fallback"]["mode"] == "single_layer_motion"

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.actions.registry import ActionRegistry
from app.motion_designer.image_decomposition import (
    DecomposedImageElement,
    ImageDecompositionResult,
)
from app.motion_designer.restoration_preflight import (
    assess_decomposition_restoration_preflight,
    assess_restoration_preflight,
)


def _mask(path: Path) -> Path:
    image = np.zeros((100, 160), dtype=np.uint8)
    image[25:80, 50:120] = 255
    assert cv2.imwrite(str(path), image)
    return path


def test_restoration_preflight_clamps_unsafe_camera_move(tmp_path: Path) -> None:
    report = assess_restoration_preflight(
        restoration_mask_path=_mask(tmp_path / "mask.png"),
        confidence=0.55,
        max_camera_travel_ratio=0.04,
        camera_dx_ratio=0.06,
        camera_dy_ratio=0.08,
    )

    assert report["status"] == "blocked"
    assert report["camera"]["requested"]["travel_ratio"] == 0.1
    assert report["camera"]["safe_path"]["travel_ratio"] == 0.04
    assert report["camera"]["safe_path"]["was_clamped"] is True
    assert len(report["restoration"]["risk_heatmap"]) == 8
    assert report["issues"][0]["code"] == "camera_travel_exceeds_restoration_limit"


def test_restoration_preflight_accepts_small_high_confidence_move(tmp_path: Path) -> None:
    report = assess_restoration_preflight(
        restoration_mask_path=_mask(tmp_path / "mask.png"),
        confidence=0.92,
        max_camera_travel_ratio=0.08,
        camera_dx_ratio=0.02,
    )

    assert report["status"] == "safe"
    assert report["can_render"] is True
    assert report["issues"] == []


def test_restoration_preflight_is_available_as_ownerless_action(tmp_path: Path) -> None:
    registry = ActionRegistry()
    execution = registry.execute("motion.restoration.preflight", {
        "restoration_mask_path": str(_mask(tmp_path / "mask.png")),
        "confidence": 0.9,
        "max_camera_travel_ratio": 0.05,
        "camera_dx_ratio": 0.01,
    })

    assert execution.ok
    assert execution.result["schema"] == "tigerstudio.motion.restoration_preflight.v1"
    assert execution.result["status"] == "safe"


def test_decomposition_preflight_uses_saved_inpaint_diagnostics(tmp_path: Path) -> None:
    mask_path = _mask(tmp_path / "subject.png")
    result = ImageDecompositionResult(
        source_path=str(tmp_path / "source.png"),
        source_hash="test",
        width=160,
        height=100,
        background_path=str(tmp_path / "background.png"),
        elements=[DecomposedImageElement(
            id="subject",
            role="subject",
            label="Subject",
            bbox=(50, 25, 70, 55),
            rgba_path=str(tmp_path / "subject_rgba.png"),
            mask_path=str(mask_path),
            area_ratio=0.24,
            depth=0.2,
            confidence=0.9,
        )],
        diagnostics={
            "inpaint": {
                "provider": "test_clean_plate",
                "confidence": 0.8,
                "max_camera_travel_ratio": 0.05,
            }
        },
    )

    report = assess_decomposition_restoration_preflight(
        result,
        camera_dx_ratio=0.08,
    )
    assert report["status"] == "blocked"
    assert report["restoration"]["provider"] == "test_clean_plate"
    assert report["camera"]["safe_path"]["dx_ratio"] == 0.05

    registry = ActionRegistry()
    execution = registry.execute("motion.ai.restoration.preflight", {
        "decomposition": result.to_dict(),
        "camera_dx_ratio": 0.02,
    })
    assert execution.ok
    assert execution.result["status"] == "safe"

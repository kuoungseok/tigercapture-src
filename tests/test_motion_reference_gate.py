from __future__ import annotations

import numpy as np
from PIL import Image

from app.motion_designer.reference_gate import compare_reference_frame


def test_reference_gate_passes_identical_frame_and_records_source(tmp_path) -> None:
    rgba = np.zeros((12, 20, 4), dtype=np.uint8)
    rgba[..., 0] = 80
    rgba[..., 3] = 255
    reference = tmp_path / "official_reference.png"
    Image.fromarray(rgba, "RGBA").save(reference)
    report = compare_reference_frame(rgba, reference, reference_source="external-reference-scene")
    assert report["ok"] is True
    assert report["metrics"]["mean_abs_error"] == 0
    assert report["reference_source"] == "external-reference-scene"


def test_reference_gate_rejects_visual_and_alpha_mismatch() -> None:
    reference = np.zeros((10, 10, 4), dtype=np.uint8)
    actual = reference.copy()
    actual[:, :, 1] = 255
    actual[:5, :, 3] = 255
    report = compare_reference_frame(actual, reference)
    assert report["ok"] is False
    assert report["status"] == "mismatch"
    assert report["checks"]["minimum_ssim"] is False
    assert report["checks"]["alpha_mismatch_ratio"] is False


def test_reference_gate_rejects_dimension_mismatch() -> None:
    report = compare_reference_frame(
        np.zeros((10, 10, 4), dtype=np.uint8),
        np.zeros((9, 10, 4), dtype=np.uint8),
    )
    assert report["ok"] is False
    assert report["status"] == "dimension_mismatch"

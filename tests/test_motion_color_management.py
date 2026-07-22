from __future__ import annotations

import numpy as np

from app.motion_designer.color_management import (
    MotionColorSettings,
    composite_premultiplied_srgb_over_srgb,
    default_motion_metadata,
    linear_to_srgb,
    settings_from_composition_metadata,
    srgb_to_linear,
    validate_motion_color_settings,
)
from app.motion_designer.schema import MotionComposition


def test_srgb_linear_round_trip_is_stable() -> None:
    values = np.array([0.0, 0.04045, 0.18, 0.5, 1.0], dtype=np.float32)
    restored = linear_to_srgb(srgb_to_linear(values))
    assert np.allclose(restored, values, atol=1e-6)


def test_linear_premultiplied_composite_uses_correct_alpha_gamma_order() -> None:
    base = np.zeros((1, 1, 3), dtype=np.uint8)
    overlay = np.array([[[128, 0, 0, 128]]], dtype=np.uint8)
    result = composite_premultiplied_srgb_over_srgb(base, overlay)
    assert 187 <= int(result[0, 0, 0]) <= 189
    assert result[0, 0, 1:].tolist() == [0, 0]


def test_zero_alpha_does_not_leak_encoded_rgb() -> None:
    base = np.array([[[30, 80, 140]]], dtype=np.uint8)
    overlay = np.array([[[255, 255, 255, 0]]], dtype=np.uint8)
    assert np.array_equal(composite_premultiplied_srgb_over_srgb(base, overlay), base)


def test_new_compositions_are_explicit_but_legacy_documents_remain_compatible() -> None:
    current = MotionComposition()
    assert settings_from_composition_metadata(current.metadata).blend_space == "linear-srgb"
    legacy = MotionComposition.from_dict({"name": "Legacy"})
    assert legacy.metadata == {}
    assert settings_from_composition_metadata(legacy.metadata).blend_space == "display-srgb"


def test_motion_color_metadata_round_trip_and_validation() -> None:
    settings = MotionColorSettings.from_dict(default_motion_metadata()["color_management"])
    report = validate_motion_color_settings(settings)
    assert report["ok"] is True
    assert report["settings"]["alpha"] == {
        "storage": "straight",
        "composite": "premultiplied",
        "premultiply_space": "linear",
    }
    assert report["internal_layer_blend"] == "qt-display-space"


def test_invalid_alpha_contract_is_rejected() -> None:
    report = validate_motion_color_settings({
        "blend_space": "linear-srgb",
        "alpha": {"storage": "premultiplied", "composite": "straight", "premultiply_space": "display"},
    })
    assert report["ok"] is False
    assert len(report["errors"]) == 3


def test_unimplemented_hdr_tone_map_and_ocio_paths_are_blocked_not_silently_ignored() -> None:
    report = validate_motion_color_settings({
        "tone_map": "aces-fitted",
        "project": {
            "output_space": "rec2020", "output_transfer": "pq", "hdr_mode": True,
            "ocio_config_path": "missing.ocio",
        },
    })
    assert report["ok"] is False
    assert any("tone mapping" in error for error in report["errors"])
    assert any("HDR output" in error for error in report["errors"])
    assert any("OCIO" in error for error in report["errors"])

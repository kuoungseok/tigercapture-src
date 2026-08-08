from __future__ import annotations

import numpy as np

from app.actions.editor_adapter_motion_export import MotionExportAdapterMixin
from app.color_ocio import preferred_aces_ocio_uri
from app.motion_designer.color_management import (
    MotionColorSettings,
    composite_premultiplied_srgb_over_srgb,
    default_motion_metadata,
    linear_to_srgb,
    settings_from_composition_metadata,
    srgb_to_linear,
    validate_motion_color_settings,
)
from app.motion_designer.color_runtime import (
    apply_motion_color_pipeline_premultiplied_rgba,
    apply_motion_color_pipeline_rgb,
)
from app.motion_designer.export_pipeline import MotionProfileExporter
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


def test_hdr_and_tone_map_are_supported_but_missing_ocio_is_blocked() -> None:
    report = validate_motion_color_settings({
        "tone_map": "aces-fitted",
        "project": {
            "output_space": "rec2020", "output_transfer": "pq", "hdr_mode": True,
            "ocio_config_path": "missing.ocio",
        },
    })
    assert report["ok"] is False
    assert any("OCIO" in error for error in report["errors"])

    hdr_only = validate_motion_color_settings({
        "project": {
            "output_space": "rec2020",
            "output_transfer": "pq",
            "hdr_mode": True,
        },
    })
    assert hdr_only["ok"] is True


def _write_swap_red_blue_cube(path) -> None:
    lines = [
        'TITLE "Swap red and blue"',
        "LUT_3D_SIZE 2",
        "DOMAIN_MIN 0 0 0",
        "DOMAIN_MAX 1 1 1",
    ]
    for blue in (0.0, 1.0):
        for green in (0.0, 1.0):
            for red in (0.0, 1.0):
                lines.append(f"{blue:.1f} {green:.1f} {red:.1f}")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def test_motion_lut_chain_tone_map_and_alpha_are_preview_export_safe(tmp_path) -> None:
    lut_path = tmp_path / "swap.cube"
    _write_swap_red_blue_cube(lut_path)
    settings = MotionColorSettings.from_dict({
        "tone_map": "reinhard",
        "project": {
            "input_space": "srgb",
            "input_transfer": "srgb",
            "working_space": "srgb",
            "output_space": "srgb",
            "output_transfer": "srgb",
            "view_transform": "srgb",
            "input_lut": {"path": str(lut_path), "strength": 1.0, "enabled": True},
            "creative_lut": {"path": str(lut_path), "strength": 0.5, "enabled": True},
            "output_lut": {"path": str(lut_path), "strength": 1.0, "enabled": True},
        },
    })
    assert validate_motion_color_settings(settings)["ok"]
    rgb = np.array([[[220, 80, 25], [20, 120, 240]]], dtype=np.uint8)
    transformed, report = apply_motion_color_pipeline_rgb(rgb, settings)
    assert transformed.shape == rgb.shape
    assert [stage["stage"] for stage in report["stages"]] == [
        "input_lut", "tone_map", "creative_lut", "output_lut",
    ]
    rgba = np.array([[[110, 40, 12, 128], [0, 0, 0, 0]]], dtype=np.uint8)
    alpha_safe, _ = apply_motion_color_pipeline_premultiplied_rgba(rgba, settings)
    assert alpha_safe[..., 3].tolist() == rgba[..., 3].tolist()
    assert alpha_safe[0, 1].tolist() == [0, 0, 0, 0]


def test_motion_preflight_rejects_malformed_and_non_cube_luts(tmp_path) -> None:
    malformed = tmp_path / "broken.cube"
    malformed.write_text("LUT_3D_SIZE 2\n0 0 0\n", encoding="ascii")
    report = validate_motion_color_settings({
        "project": {
            "creative_lut": {
                "path": str(malformed), "strength": 1.0, "enabled": True,
            },
        },
    })
    assert report["ok"] is False
    assert any("LUT is invalid" in error for error in report["errors"])

    unsupported = tmp_path / "look.3dl"
    unsupported.write_text("0 0 0\n", encoding="ascii")
    report = validate_motion_color_settings({
        "project": {
            "output_lut": {
                "path": str(unsupported), "strength": 1.0, "enabled": True,
            },
        },
    })
    assert report["ok"] is False
    assert any("must be a 3D .cube" in error for error in report["errors"])


def test_motion_still_export_uses_the_same_color_pipeline(tmp_path) -> None:
    lut_path = tmp_path / "swap.cube"
    _write_swap_red_blue_cube(lut_path)
    composition = MotionComposition(width=2, height=1, duration_ms=1000)
    color = settings_from_composition_metadata(composition.metadata).to_dict()
    color["tone_map"] = "aces-fitted"
    color["project"]["creative_lut"] = {
        "path": str(lut_path), "strength": 0.75, "enabled": True,
    }
    composition.metadata["color_management"] = color
    source = np.array([[[220, 80, 25, 255], [20, 120, 240, 255]]], dtype=np.uint8)

    class Renderer:
        def render_rgba_array(self, *_args, **_kwargs):
            return source.copy()

    expected, _ = apply_motion_color_pipeline_premultiplied_rgba(
        source,
        settings_from_composition_metadata(composition.metadata),
    )
    output = tmp_path / "parity.png"
    MotionProfileExporter(renderer=Renderer()).export(
        composition, "png_still", output, time_ms=0.0,
    )
    from PySide6.QtGui import QImage

    image = QImage(str(output)).convertToFormat(QImage.Format_RGBA8888_Premultiplied)
    rows = np.frombuffer(image.bits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
    actual = rows[:, : image.width() * 4].reshape(image.height(), image.width(), 4).copy()
    assert np.array_equal(actual, expected)


def test_motion_color_action_auto_selects_builtin_aces_config() -> None:
    composition = MotionComposition()

    class Adapter(MotionExportAdapterMixin):
        def __init__(self) -> None:
            self.rows = {composition.id: composition}
            self.synced = False

        def _motion_store(self):
            return self.rows

        def _motion_sync_owner(self) -> None:
            self.synced = True

    adapter = Adapter()
    settings = settings_from_composition_metadata(composition.metadata).to_dict()
    settings["project"]["working_space"] = "acescg"
    settings["project"]["view_transform"] = "aces-1.3"
    result = adapter.motion_color_set(
        composition_id=composition.id,
        settings=settings,
    )
    assert result["report"]["ok"]
    assert result["report"]["settings"]["project"]["ocio_config_path"] == preferred_aces_ocio_uri()
    assert adapter.synced

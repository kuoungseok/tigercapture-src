from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_media_response_matrix_measures_each_implemented_control() -> None:
    from PySide6.QtWidgets import QApplication
    from app.painter_media_response import measure_painter_media_response

    _app = QApplication.instance() or QApplication([])
    report = measure_painter_media_response()
    assert report["evidence_kind"] == "automated_measurement"
    assert report["physical_media_validation"] is False
    assert all(
        report["smudge"][key]
        for key in ("length_response", "radius_response", "color_rate_response")
    )
    assert report["smudge"]["overlay_frozen_replay_response"] is True
    assert report["smudge"]["all_layer_sampling_supported"] is True
    assert all(
        report["wet_canvas"][key]
        for key in (
            "mixing_response",
            "pickup_response",
            "diffusion_response",
            "drying_response",
        )
    )
    assert all(
        report["material_paint"][key]
        for key in (
            "load_response",
            "thickness_response",
            "wetness_response",
            "gloss_response",
            "roughness_response",
            "load_depletion_response",
            "authored_load_recovery_response",
            "automatic_resaturation_response",
            "tilt_knife_response",
            "plow_response",
            "negative_depth_response",
        )
    )
    assert report["material_paint"]["plow_supported"] is True
    assert report["material_paint"]["negative_depth_supported"] is True
    assert report["material_paint"]["automatic_resaturation_supported"] is True

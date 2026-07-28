from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.motion_designer.trend_product_qa import run_trend_product_gate


def test_trend_product_gate_cancel_resume_recovery_alpha_nested_hdr_and_mp4(
    tmp_path,
):
    QApplication.instance() or QApplication([])

    report = run_trend_product_gate(
        tmp_path,
        duration_ms=3000,
        sequence_fps=2,
        cancel_after_frames=2,
    )

    assert report["ok"] is True
    assert report["cancelled"] is True
    assert report["partial_frame_count"] == 2
    assert report["corrupt_frame_repaired"] is True
    assert report["resume"]["frame_count"] == 6
    assert report["resume"]["sequence_complete"] is True
    assert report["recovery_roundtrip"] is True
    assert report["alpha"]["minimum"] == 0
    assert report["alpha"]["maximum"] > 0
    assert report["nested_preview_export_parity"] is True
    assert report["hdr_h265_preflight"]["ok"] is True
    assert report["hdr_h265_artifact"]["color_primaries"] == "bt2020"
    assert report["hdr_h265_artifact"]["color_transfer"] == "smpte2084"
    assert report["hdr_h265_artifact"]["bytes"] > 0
    assert report["hdr_h265_artifact"]["glass_effect_count"] == 3
    assert report["hdr_h265_artifact"]["glass_changed_pixel_count"] > 0
    assert report["hdr_h265_artifact"]["glass_mean_rgb_abs_difference"] > 0.0
    tiled = report["hdr_h265_artifact"]["tiled_export"]
    assert tiled["tile_count"] > 1
    assert tiled["full_frame_intermediate_avoided"] is True
    assert report["hdr_h265_artifact"]["tiled_full_mean_abs_difference"] < 0.5
    assert report["mp4"]["bytes"] > 0

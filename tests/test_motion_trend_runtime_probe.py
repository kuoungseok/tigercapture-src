from __future__ import annotations

import sys

import numpy as np
from PySide6.QtGui import QImage

from app.motion_designer.trend_runtime_probe import (
    _memory_bytes,
    _runtime_identity,
    evaluate_runtime_probe,
    evaluate_visual_parity,
)


def test_runtime_probe_requires_wall_clock_loops_gpu_and_screenshot(
    tmp_path,
) -> None:
    screenshot = tmp_path / "workspace.png"
    screenshot.write_bytes(b"png")
    preview = tmp_path / "preview.png"
    preview.write_bytes(b"png")
    report = evaluate_runtime_probe(
        target_seconds=60.0,
        elapsed_seconds=60.1,
        frame_swaps=1800,
        loop_count=5,
        diagnostics={"context_valid": True, "backend": "motion_vector_gpu"},
        screenshot_path=screenshot,
        preview_framebuffer_path=preview,
    )
    assert report["ok"] is True
    assert all(report["checks"].values())
    assert all(report["realtime_checks"].values())
    assert report["software_renderer_used"] is False


def test_runtime_probe_rejects_painter_fallback_and_short_run(tmp_path) -> None:
    report = evaluate_runtime_probe(
        target_seconds=60.0,
        elapsed_seconds=4.0,
        frame_swaps=1,
        loop_count=0,
        diagnostics={
            "context_valid": False,
            "backend": "qt_painter_fallback",
        },
        screenshot_path=tmp_path / "missing.png",
    )
    assert report["ok"] is False
    assert report["software_renderer_used"] is True
    assert report["checks"]["wall_clock_duration"] is False
    assert report["realtime_checks"]["gpu_render_path"] is False


def test_runtime_probe_reads_process_memory_without_optional_psutil() -> None:
    if sys.platform == "win32":
        assert _memory_bytes() > 0


def test_source_runtime_identity_is_not_frozen() -> None:
    identity = _runtime_identity()
    assert identity["frozen"] is False
    assert identity["executable_size_bytes"] > 0
    assert identity["executable_sha256"] == ""


def test_glass_runtime_probe_requires_exact_backend_and_visual_parity(
    tmp_path,
) -> None:
    screenshot = tmp_path / "workspace.png"
    screenshot.write_bytes(b"png")
    preview = tmp_path / "preview.png"
    preview.write_bytes(b"png")
    report = evaluate_runtime_probe(
        target_seconds=15.0,
        elapsed_seconds=15.1,
        frame_swaps=400,
        loop_count=1,
        diagnostics={"context_valid": True, "backend": "motion_vector_gpu"},
        screenshot_path=screenshot,
        preview_framebuffer_path=preview,
        expected_backend="motion_glass_gpu",
        visual_parity={"mean_abs_rgb": 4.0, "p95_abs_rgb": 10.0},
    )
    assert report["ok"] is False
    assert report["realtime_checks"]["expected_backend"] is False
    assert report["realtime_checks"]["glass_visual_parity"] is True


def test_glass_visual_parity_measures_rgb_error() -> None:
    base = np.zeros((4, 4, 4), dtype=np.uint8)
    base[..., 3] = 255
    changed = base.copy()
    changed[..., :3] = 8
    base_image = QImage(
        base.data,
        4,
        4,
        base.strides[0],
        QImage.Format_RGBA8888,
    ).copy()
    changed_image = QImage(
        changed.data,
        4,
        4,
        changed.strides[0],
        QImage.Format_RGBA8888,
    ).copy()
    report = evaluate_visual_parity(changed_image, base_image)
    assert report["mean_abs_rgb"] == 8.0
    assert report["p95_abs_rgb"] == 8.0
    assert report["maximum_abs_rgb"] == 8.0

from __future__ import annotations

import sys

from app.motion_designer.trend_runtime_probe import _memory_bytes, evaluate_runtime_probe


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

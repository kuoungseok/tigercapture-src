from __future__ import annotations

import json

from app.motion_designer.trend_distribution_qa import (
    DISTRIBUTION_QA_SCHEMA,
    evaluate_frozen_distribution,
)
from app.motion_designer.trend_runtime_probe import RUNTIME_PROBE_SCHEMA


def _bundle(tmp_path):
    bundle = tmp_path / "TigerCapture"
    bundle.mkdir()
    for name in ("TigerCapture.exe", "TigerStudio.exe", "TigerCaptureUpdater.exe"):
        size = 1_100_000 if name == "TigerStudio.exe" else 1
        (bundle / name).write_bytes(b"x" * size)
    return bundle


def _runtime_report(tmp_path, *, realtime_ready: bool):
    screenshot = tmp_path / "workspace.png"
    framebuffer = tmp_path / "framebuffer.png"
    screenshot.write_bytes(b"png")
    framebuffer.write_bytes(b"png")
    return {
        "schema": RUNTIME_PROBE_SCHEMA,
        "target_seconds": 60.0,
        "elapsed_seconds": 60.2,
        "frame_swaps": 252,
        "loop_count": 4,
        "measured_frame_rate": 4.18,
        "memory_before_bytes": 300_000_000,
        "memory_after_bytes": 320_000_000,
        "measurement_ok": True,
        "product_realtime_ready": realtime_ready,
        "realtime_checks": {
            "minimum_24_fps": realtime_ready,
            "gpu_render_path": realtime_ready,
        },
        "backend": {
            "context_valid": True,
            "backend": "motion_vector_gpu" if realtime_ready else "qt_painter_fallback",
        },
        "screenshot_path": str(screenshot),
        "preview_framebuffer_path": str(framebuffer),
    }


def test_distribution_gate_separates_bundle_smoke_from_realtime(tmp_path) -> None:
    bundle = _bundle(tmp_path)
    runtime = _runtime_report(tmp_path, realtime_ready=False)
    report_path = tmp_path / "runtime.json"
    report_path.write_text(json.dumps(runtime), encoding="utf-8")

    result = evaluate_frozen_distribution(
        studio_exe=bundle / "TigerStudio.exe",
        runtime_report_path=report_path,
        runtime_report=runtime,
    )

    assert result["schema"] == DISTRIBUTION_QA_SCHEMA
    assert result["frozen_bundle_smoke_ok"] is True
    assert result["product_realtime_ready"] is False
    assert result["ok"] is False
    assert result["blockers"] == [
        "realtime:minimum_24_fps",
        "realtime:gpu_render_path",
    ]


def test_distribution_gate_rejects_short_or_incomplete_bundle(tmp_path) -> None:
    bundle = _bundle(tmp_path)
    (bundle / "TigerCaptureUpdater.exe").unlink()
    runtime = _runtime_report(tmp_path, realtime_ready=True)
    runtime["target_seconds"] = 3.0
    runtime["elapsed_seconds"] = 3.1
    runtime["memory_before_bytes"] = 0
    runtime["memory_after_bytes"] = 0
    report_path = tmp_path / "runtime.json"
    report_path.write_text(json.dumps(runtime), encoding="utf-8")

    result = evaluate_frozen_distribution(
        studio_exe=bundle / "TigerStudio.exe",
        runtime_report_path=report_path,
        runtime_report=runtime,
    )

    assert result["frozen_bundle_smoke_ok"] is False
    assert result["checks"]["bundle_launchers"] is False
    assert result["checks"]["minimum_duration"] is False
    assert result["checks"]["memory_sample"] is False
    assert result["checks"]["memory_stable"] is False
    assert "bundle_launchers" in result["blockers"]
    assert "minimum_duration" in result["blockers"]

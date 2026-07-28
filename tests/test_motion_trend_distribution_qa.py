from __future__ import annotations

import hashlib
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
    preview_crop = tmp_path / "preview_crop.png"
    cpu_reference = tmp_path / "cpu_reference.png"
    screenshot.write_bytes(b"png")
    framebuffer.write_bytes(b"png")
    preview_crop.write_bytes(b"png")
    cpu_reference.write_bytes(b"png")
    studio = tmp_path / "TigerCapture" / "TigerStudio.exe"
    return {
        "schema": RUNTIME_PROBE_SCHEMA,
        "target_seconds": 60.0,
        "elapsed_seconds": 60.2,
        "frame_swaps": 1_590,
        "loop_count": 4,
        "measured_frame_rate": 26.4 if realtime_ready else 4.18,
        "memory_before_bytes": 300_000_000,
        "memory_after_bytes": 320_000_000,
        "runtime_identity": {
            "frozen": True,
            "executable": str(studio),
            "executable_size_bytes": studio.stat().st_size,
            "executable_sha256": hashlib.sha256(studio.read_bytes()).hexdigest(),
        },
        "measurement_ok": True,
        "product_realtime_ready": realtime_ready,
        "realtime_checks": {
            "minimum_24_fps": realtime_ready,
            "gpu_render_path": realtime_ready,
            "expected_backend": realtime_ready,
            "glass_visual_parity": realtime_ready,
        },
        "backend": {
            "context_valid": True,
            "backend": "motion_glass_gpu" if realtime_ready else "qt_painter_fallback",
            "backdrop_shader": realtime_ready,
            "framebuffer_feedback": realtime_ready,
            "gl_error": 0,
        },
        "glass_gpu_visual_parity": {
            "mean_abs_rgb": 4.0,
            "p95_abs_rgb": 8.0,
        },
        "screenshot_path": str(screenshot),
        "preview_framebuffer_path": str(framebuffer),
        "preview_crop_path": str(preview_crop),
        "cpu_reference_path": str(cpu_reference),
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
    assert "realtime:minimum_24_fps" in result["blockers"]
    assert "realtime:gpu_render_path" in result["blockers"]
    assert "realtime:expected_backend" in result["blockers"]


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


def test_distribution_gate_rejects_forged_realtime_claim(tmp_path) -> None:
    bundle = _bundle(tmp_path)
    runtime = _runtime_report(tmp_path, realtime_ready=True)
    runtime["backend"]["backend"] = "motion_vector_gpu"
    report_path = tmp_path / "runtime.json"
    report_path.write_text(json.dumps(runtime), encoding="utf-8")

    result = evaluate_frozen_distribution(
        studio_exe=bundle / "TigerStudio.exe",
        runtime_report_path=report_path,
        runtime_report=runtime,
    )

    assert result["frozen_bundle_smoke_ok"] is True
    assert result["product_realtime_ready"] is False
    assert result["realtime_evidence_checks"]["expected_backend"] is False
    assert "realtime:expected_backend" in result["blockers"]


def test_distribution_gate_rejects_report_from_another_executable(tmp_path) -> None:
    bundle = _bundle(tmp_path)
    runtime = _runtime_report(tmp_path, realtime_ready=True)
    runtime["runtime_identity"]["executable_sha256"] = "0" * 64
    report_path = tmp_path / "runtime.json"
    report_path.write_text(json.dumps(runtime), encoding="utf-8")

    result = evaluate_frozen_distribution(
        studio_exe=bundle / "TigerStudio.exe",
        runtime_report_path=report_path,
        runtime_report=runtime,
    )

    assert result["frozen_bundle_smoke_ok"] is False
    assert result["checks"]["runtime_executable_sha256"] is False
    assert "runtime_executable_sha256" in result["blockers"]

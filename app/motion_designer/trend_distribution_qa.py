"""Distribution-level QA evaluation for the Motion Designer trend runtime."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path
from typing import Any

from app.motion_designer.trend_runtime_probe import (
    GLASS_VISUAL_MEAN_ABS_LIMIT,
    GLASS_VISUAL_P95_ABS_LIMIT,
    RUNTIME_PROBE_SCHEMA,
)


DISTRIBUTION_QA_SCHEMA = "tigerstudio.motion.trend_distribution_qa.v2"
MINIMUM_FROZEN_EXE_BYTES = 1_000_000


def _nonempty_file(path: Path | None) -> bool:
    return bool(path is not None and path.is_file() and path.stat().st_size > 0)


def _report_artifact(
    runtime_report: dict[str, Any],
    key: str,
    *,
    report_path: Path,
) -> Path | None:
    raw = str(runtime_report.get(key) or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = report_path.parent / path
    return path.resolve(strict=False)


def _finite_metric(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def evaluate_frozen_distribution(
    *,
    studio_exe: Path,
    runtime_report_path: Path,
    runtime_report: dict[str, Any],
    minimum_runtime_seconds: float = 60.0,
) -> dict[str, Any]:
    """Evaluate frozen-bundle stability without hiding realtime failures."""
    studio = studio_exe.expanduser().resolve(strict=False)
    report_path = runtime_report_path.expanduser().resolve(strict=False)
    screenshot = _report_artifact(
        runtime_report,
        "screenshot_path",
        report_path=report_path,
    )
    framebuffer = _report_artifact(
        runtime_report,
        "preview_framebuffer_path",
        report_path=report_path,
    )
    preview_crop = _report_artifact(
        runtime_report,
        "preview_crop_path",
        report_path=report_path,
    )
    cpu_reference = _report_artifact(
        runtime_report,
        "cpu_reference_path",
        report_path=report_path,
    )
    bundle_dir = studio.parent
    required_launchers = {
        name: bundle_dir / name
        for name in ("TigerCapture.exe", "TigerStudio.exe", "TigerCaptureUpdater.exe")
    }
    target_seconds = float(runtime_report.get("target_seconds") or 0.0)
    elapsed_seconds = float(runtime_report.get("elapsed_seconds") or 0.0)
    memory_before = int(runtime_report.get("memory_before_bytes") or 0)
    memory_after = int(runtime_report.get("memory_after_bytes") or 0)
    memory_growth = memory_after - memory_before
    memory_growth_limit = max(256 * 1024 * 1024, int(memory_before * 0.5))
    backend_data = runtime_report.get("backend")
    if not isinstance(backend_data, dict):
        backend_data = {}
    realtime_reported_checks = runtime_report.get("realtime_checks")
    if not isinstance(realtime_reported_checks, dict):
        realtime_reported_checks = {}
    visual_parity = runtime_report.get("glass_gpu_visual_parity")
    if not isinstance(visual_parity, dict):
        visual_parity = {}
    mean_abs_rgb = _finite_metric(visual_parity.get("mean_abs_rgb"))
    p95_abs_rgb = _finite_metric(visual_parity.get("p95_abs_rgb"))
    runtime_identity = runtime_report.get("runtime_identity")
    if not isinstance(runtime_identity, dict):
        runtime_identity = {}
    runtime_executable = Path(
        str(runtime_identity.get("executable") or "")
    ).expanduser().resolve(strict=False)
    reported_executable_size = int(
        runtime_identity.get("executable_size_bytes") or 0
    )
    reported_executable_sha256 = str(
        runtime_identity.get("executable_sha256") or ""
    ).lower()
    studio_sha256 = _sha256(studio) if studio.is_file() else ""
    checks = {
        "studio_executable": (
            studio.is_file() and studio.stat().st_size >= MINIMUM_FROZEN_EXE_BYTES
        ),
        "bundle_launchers": all(_nonempty_file(path) for path in required_launchers.values()),
        "runtime_report": _nonempty_file(report_path),
        "runtime_schema": runtime_report.get("schema") == RUNTIME_PROBE_SCHEMA,
        "frozen_runtime": bool(runtime_identity.get("frozen")),
        "runtime_executable": (
            studio.is_file()
            and runtime_executable == studio
            and reported_executable_size == studio.stat().st_size
        ),
        "runtime_executable_sha256": (
            bool(studio_sha256)
            and reported_executable_sha256 == studio_sha256
        ),
        "minimum_duration": (
            target_seconds >= float(minimum_runtime_seconds) - 0.01
            and elapsed_seconds >= target_seconds - 0.35
        ),
        "measurement_valid": bool(runtime_report.get("measurement_ok")),
        "opengl_context": bool(backend_data.get("context_valid")),
        "memory_sample": memory_before > 0 and memory_after > 0,
        "memory_stable": (
            memory_before > 0
            and memory_after > 0
            and memory_growth <= memory_growth_limit
        ),
        "workspace_capture": _nonempty_file(screenshot),
        "preview_framebuffer": _nonempty_file(framebuffer),
    }
    bundle_smoke_ok = all(checks.values())
    realtime_evidence_checks = {
        "runtime_claim": bool(runtime_report.get("product_realtime_ready")),
        "minimum_24_fps": (
            float(runtime_report.get("measured_frame_rate") or 0.0) >= 24.0
            and bool(realtime_reported_checks.get("minimum_24_fps"))
        ),
        "gpu_render_path": bool(realtime_reported_checks.get("gpu_render_path")),
        "expected_backend": (
            str(backend_data.get("backend") or "") == "motion_glass_gpu"
            and bool(realtime_reported_checks.get("expected_backend"))
        ),
        "glass_visual_parity": (
            bool(realtime_reported_checks.get("glass_visual_parity"))
            and mean_abs_rgb is not None
            and p95_abs_rgb is not None
            and mean_abs_rgb <= GLASS_VISUAL_MEAN_ABS_LIMIT
            and p95_abs_rgb <= GLASS_VISUAL_P95_ABS_LIMIT
        ),
        "glass_shader_feedback": (
            bool(backend_data.get("backdrop_shader"))
            and bool(backend_data.get("framebuffer_feedback"))
            and int(backend_data.get("gl_error") or 0) == 0
        ),
        "preview_composition": _nonempty_file(preview_crop),
        "cpu_reference": _nonempty_file(cpu_reference),
    }
    product_realtime_ready = all(realtime_evidence_checks.values())
    blockers: list[str] = []
    if not bundle_smoke_ok:
        blockers.extend(name for name, passed in checks.items() if not passed)
    if not product_realtime_ready:
        blockers.extend(
            f"realtime:{name}"
            for name, passed in realtime_evidence_checks.items()
            if not bool(passed)
        )
    return {
        "schema": DISTRIBUTION_QA_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": bundle_smoke_ok and product_realtime_ready,
        "frozen_bundle_smoke_ok": bundle_smoke_ok,
        "product_realtime_ready": product_realtime_ready,
        "checks": checks,
        "realtime_evidence_checks": realtime_evidence_checks,
        "blockers": blockers,
        "studio_executable": str(studio),
        "bundle_launchers": {
            name: str(path.resolve(strict=False))
            for name, path in required_launchers.items()
        },
        "runtime_report": str(report_path),
        "runtime_summary": {
            "target_seconds": target_seconds,
            "elapsed_seconds": elapsed_seconds,
            "frame_swaps": int(runtime_report.get("frame_swaps") or 0),
            "loop_count": int(runtime_report.get("loop_count") or 0),
            "measured_frame_rate": float(
                runtime_report.get("measured_frame_rate") or 0.0
            ),
            "backend": str(backend_data.get("backend") or ""),
            "memory_before_bytes": memory_before,
            "memory_after_bytes": memory_after,
            "memory_growth_bytes": memory_growth,
            "memory_growth_limit_bytes": memory_growth_limit,
            "runtime_executable_sha256": reported_executable_sha256,
            "glass_visual_mean_abs_rgb": mean_abs_rgb,
            "glass_visual_p95_abs_rgb": p95_abs_rgb,
        },
        "artifacts": {
            "workspace_capture": str(screenshot) if screenshot is not None else "",
            "preview_framebuffer": (
                str(framebuffer) if framebuffer is not None else ""
            ),
            "preview_composition": (
                str(preview_crop) if preview_crop is not None else ""
            ),
            "cpu_reference": (
                str(cpu_reference) if cpu_reference is not None else ""
            ),
        },
    }


__all__ = [
    "DISTRIBUTION_QA_SCHEMA",
    "MINIMUM_FROZEN_EXE_BYTES",
    "evaluate_frozen_distribution",
]

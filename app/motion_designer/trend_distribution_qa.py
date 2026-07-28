"""Distribution-level QA evaluation for the Motion Designer trend runtime."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.motion_designer.trend_runtime_probe import RUNTIME_PROBE_SCHEMA


DISTRIBUTION_QA_SCHEMA = "tigerstudio.motion.trend_distribution_qa.v1"
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
    checks = {
        "studio_executable": (
            studio.is_file() and studio.stat().st_size >= MINIMUM_FROZEN_EXE_BYTES
        ),
        "bundle_launchers": all(_nonempty_file(path) for path in required_launchers.values()),
        "runtime_report": _nonempty_file(report_path),
        "runtime_schema": runtime_report.get("schema") == RUNTIME_PROBE_SCHEMA,
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
    product_realtime_ready = bool(runtime_report.get("product_realtime_ready"))
    blockers: list[str] = []
    if not bundle_smoke_ok:
        blockers.extend(name for name, passed in checks.items() if not passed)
    if not product_realtime_ready:
        realtime_checks = runtime_report.get("realtime_checks") or {}
        blockers.extend(
            f"realtime:{name}"
            for name, passed in realtime_checks.items()
            if not bool(passed)
        )
    return {
        "schema": DISTRIBUTION_QA_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": bundle_smoke_ok and product_realtime_ready,
        "frozen_bundle_smoke_ok": bundle_smoke_ok,
        "product_realtime_ready": product_realtime_ready,
        "checks": checks,
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
        },
        "artifacts": {
            "workspace_capture": str(screenshot) if screenshot is not None else "",
            "preview_framebuffer": (
                str(framebuffer) if framebuffer is not None else ""
            ),
        },
    }


__all__ = [
    "DISTRIBUTION_QA_SCHEMA",
    "MINIMUM_FROZEN_EXE_BYTES",
    "evaluate_frozen_distribution",
]

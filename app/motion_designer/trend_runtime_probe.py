"""Real-time Motion Designer trend playback probe for source and frozen builds."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication


RUNTIME_PROBE_SCHEMA = "tigerstudio.motion.trend_runtime_probe.v1"
GLASS_VISUAL_MEAN_ABS_LIMIT = 12.0
GLASS_VISUAL_P95_ABS_LIMIT = 36.0


def _memory_bytes() -> int:
    try:
        import psutil

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        pass
    if sys.platform != "win32":
        return 0
    try:
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.argtypes = []
        get_current_process.restype = wintypes.HANDLE
        get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        get_process_memory_info.restype = wintypes.BOOL
        process = get_current_process()
        ok = get_process_memory_info(
            process,
            ctypes.byref(counters),
            counters.cb,
        )
        return int(counters.WorkingSetSize) if ok else 0
    except Exception:
        return 0


def _runtime_identity() -> dict[str, Any]:
    executable = Path(sys.executable).expanduser().resolve(strict=False)
    frozen = bool(getattr(sys, "frozen", False))
    digest = ""
    if frozen and executable.is_file():
        hasher = hashlib.sha256()
        with executable.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
    return {
        "frozen": frozen,
        "executable": str(executable),
        "executable_size_bytes": (
            executable.stat().st_size if executable.is_file() else 0
        ),
        "executable_sha256": digest,
    }


def evaluate_runtime_probe(
    *,
    target_seconds: float,
    elapsed_seconds: float,
    frame_swaps: int,
    loop_count: int,
    diagnostics: dict[str, Any],
    screenshot_path: Path,
    preview_framebuffer_path: Path | None = None,
    expected_backend: str | None = None,
    visual_parity: dict[str, float] | None = None,
) -> dict[str, Any]:
    backend = str(diagnostics.get("backend") or "")
    context_valid = bool(diagnostics.get("context_valid"))
    raster_fallback = bool(
        diagnostics.get("software_renderer_used")
        or "software" in backend.lower()
        or backend == "qt_painter_fallback"
    )
    elapsed_floor = max(0.0, float(target_seconds) - 0.35)
    expected_loops = max(0, int(max(0.0, float(target_seconds) - 0.5) // 12.0))
    frame_rate = int(frame_swaps) / max(0.001, float(elapsed_seconds))
    checks = {
        "wall_clock_duration": float(elapsed_seconds) >= elapsed_floor,
        "frame_swaps": int(frame_swaps) >= max(1, int(target_seconds * 2.0)),
        "timeline_loops": int(loop_count) >= expected_loops,
        "opengl_context": context_valid,
        "renderer_reported": bool(backend),
        "screenshot": screenshot_path.is_file() and screenshot_path.stat().st_size > 0,
        "preview_framebuffer": bool(
            preview_framebuffer_path is not None
            and preview_framebuffer_path.is_file()
            and preview_framebuffer_path.stat().st_size > 0
        ),
    }
    measurement_ok = all(checks.values())
    realtime_checks = {
        "minimum_24_fps": frame_rate >= 24.0,
        "gpu_render_path": not raster_fallback,
    }
    if expected_backend:
        realtime_checks["expected_backend"] = backend == expected_backend
    if visual_parity is not None:
        realtime_checks["glass_visual_parity"] = bool(
            float(visual_parity.get("mean_abs_rgb", float("inf")))
            <= GLASS_VISUAL_MEAN_ABS_LIMIT
            and float(visual_parity.get("p95_abs_rgb", float("inf")))
            <= GLASS_VISUAL_P95_ABS_LIMIT
        )
    return {
        "ok": measurement_ok and all(realtime_checks.values()),
        "measurement_ok": measurement_ok,
        "product_realtime_ready": measurement_ok and all(realtime_checks.values()),
        "checks": checks,
        "realtime_checks": realtime_checks,
        "measured_frame_rate": frame_rate,
        "software_renderer_used": raster_fallback,
        "expected_minimum_loop_count": expected_loops,
    }


def _qimage_rgb(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    rows = np.frombuffer(converted.bits(), dtype=np.uint8).reshape(
        converted.height(),
        converted.bytesPerLine(),
    )
    return rows[:, : converted.width() * 4].reshape(
        converted.height(),
        converted.width(),
        4,
    )[..., :3].copy()


def evaluate_visual_parity(
    gpu_image: QImage,
    cpu_image: QImage,
) -> dict[str, float]:
    if (
        gpu_image.size() != cpu_image.size()
        or gpu_image.isNull()
        or cpu_image.isNull()
    ):
        return {
            "mean_abs_rgb": float("inf"),
            "p95_abs_rgb": float("inf"),
            "maximum_abs_rgb": float("inf"),
        }
    difference = np.abs(
        _qimage_rgb(gpu_image).astype(np.int16)
        - _qimage_rgb(cpu_image).astype(np.int16)
    )
    return {
        "mean_abs_rgb": float(difference.mean()),
        "p95_abs_rgb": float(np.percentile(difference, 95)),
        "maximum_abs_rgb": float(difference.max(initial=0)),
    }


def run_trend_runtime_probe(
    output_path: str | Path,
    *,
    target_seconds: float = 60.0,
) -> dict[str, Any]:
    target = max(1.0, float(target_seconds))
    report_path = Path(output_path).expanduser().resolve(strict=False)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    from app.motion_designer.render_graph import build_render_graph, render_graph_image
    from app.motion_designer.templates import instantiate_template
    from app.motion_designer.ui.window import MotionDesignerWindow

    app = QApplication.instance() or QApplication([])
    composition = instantiate_template("liquid_glass_app_promo", variant="16:9")
    window = MotionDesignerWindow(composition)
    window.resize(1280, 800)
    window.viewer_tabs.setCurrentWidget(window.preview)
    window.show()
    app.processEvents()

    screenshot_path = report_path.with_name("trend_runtime_workspace.png")
    preview_framebuffer_path = report_path.with_name(
        "trend_runtime_preview_framebuffer.png"
    )
    preview_crop_path = report_path.with_name(
        "trend_runtime_preview_composition.png"
    )
    cpu_reference_path = report_path.with_name(
        "trend_runtime_cpu_reference.png"
    )
    frame_swaps = 0
    loop_count = 0
    previous_time = 0
    started = time.monotonic()
    memory_before = _memory_bytes()
    state: dict[str, Any] = {}

    def on_frame_swapped() -> None:
        nonlocal frame_swaps
        frame_swaps += 1

    def sample() -> None:
        nonlocal loop_count, previous_time
        current_time = int(window._time_ms)
        if current_time < previous_time:
            loop_count += 1
        previous_time = current_time
        if time.monotonic() - started < target:
            return
        window._set_playback_direction(0)
        app.processEvents()
        framebuffer = window.preview.grabFramebuffer()
        framebuffer.save(
            str(preview_framebuffer_path),
            "PNG",
        )
        target_rect = window.preview._composition_target()
        ratio = float(window.preview.devicePixelRatioF())
        crop_x = max(0, int(round(target_rect.x() * ratio)))
        crop_y = max(0, int(round(target_rect.y() * ratio)))
        crop_width = min(
            framebuffer.width() - crop_x,
            max(1, int(round(target_rect.width() * ratio))),
        )
        crop_height = min(
            framebuffer.height() - crop_y,
            max(1, int(round(target_rect.height() * ratio))),
        )
        gpu_crop = framebuffer.copy(
            crop_x,
            crop_y,
            max(1, crop_width),
            max(1, crop_height),
        )
        gpu_crop.save(str(preview_crop_path), "PNG")
        cpu_graph = build_render_graph(
            composition,
            window._time_ms,
            include_vector_gpu=False,
            render_quality="preview",
            output_size=(composition.width, composition.height),
            runtime_inputs=window.preview.runtime_glass_inputs(),
        )
        cpu_reference = render_graph_image(
            cpu_graph,
            output_size=(gpu_crop.width(), gpu_crop.height()),
        )
        cpu_reference.save(str(cpu_reference_path), "PNG")
        visual_parity = evaluate_visual_parity(gpu_crop, cpu_reference)
        screen = window.screen()
        if screen is not None:
            screen.grabWindow(int(window.winId())).save(
                str(screenshot_path),
                "PNG",
            )
        elapsed = time.monotonic() - started
        diagnostics = dict(window.preview.diagnostics())
        evaluation = evaluate_runtime_probe(
            target_seconds=target,
            elapsed_seconds=elapsed,
            frame_swaps=frame_swaps,
            loop_count=loop_count,
            diagnostics=diagnostics,
            screenshot_path=screenshot_path,
            preview_framebuffer_path=preview_framebuffer_path,
            expected_backend="motion_glass_gpu",
            visual_parity=visual_parity,
        )
        state.update({
            "schema": RUNTIME_PROBE_SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ok": evaluation["ok"],
            "target_seconds": target,
            "elapsed_seconds": elapsed,
            "template_id": "liquid_glass_app_promo",
            "composition_duration_ms": composition.duration_ms,
            "frame_swaps": frame_swaps,
            "average_frame_swaps_per_second": (
                frame_swaps / elapsed if elapsed > 0.0 else 0.0
            ),
            "loop_count": loop_count,
            "timeline_time_ms": int(window._time_ms),
            "memory_before_bytes": memory_before,
            "memory_after_bytes": _memory_bytes(),
            "runtime_identity": _runtime_identity(),
            "backend": diagnostics,
            "screenshot_path": str(screenshot_path),
            "preview_framebuffer_path": str(preview_framebuffer_path),
            "preview_crop_path": str(preview_crop_path),
            "cpu_reference_path": str(cpu_reference_path),
            "glass_gpu_visual_parity": visual_parity,
            **evaluation,
        })
        report_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        window._document_dirty = False
        window.close()
        app.quit()

    window.preview.frameSwapped.connect(on_frame_swapped)
    monitor = QTimer(window)
    monitor.setInterval(50)
    monitor.timeout.connect(sample)
    monitor.start()
    window._set_loop_playback(True)
    window._set_playback_direction(1)
    exit_code = app.exec()
    if not state:
        state = {
            "schema": RUNTIME_PROBE_SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ok": False,
            "error": f"Qt event loop exited before probe completion ({exit_code})",
        }
        report_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    state["report_path"] = str(report_path)
    return state


__all__ = [
    "RUNTIME_PROBE_SCHEMA",
    "evaluate_visual_parity",
    "evaluate_runtime_probe",
    "run_trend_runtime_probe",
]

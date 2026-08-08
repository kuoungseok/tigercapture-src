from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if os.name == "nt":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    os.environ.setdefault("QT_OPENGL", "desktop")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.particles import create_particle_layer
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui.window import MotionDesignerWindow


DEFAULT_OUTPUT = ROOT / "debugCapture" / "motion_designer" / "long_run_30m"


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _acquire_run_lock(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir / ".running.json"
    for _ in range(2):
        try:
            descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                owner = json.loads(lock_path.read_text(encoding="utf-8"))
                owner_pid = int(owner.get("pid", 0))
            except Exception:
                owner_pid = 0
            if _pid_is_running(owner_pid):
                raise RuntimeError(f"Motion long-run QA is already running with PID {owner_pid}")
            lock_path.unlink(missing_ok=True)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({
                "pid": os.getpid(),
                "started_at": datetime.now(timezone.utc).isoformat(),
            }, stream, ensure_ascii=False, indent=2)
        return lock_path
    raise RuntimeError("Could not acquire the Motion long-run QA lock")


def _release_run_lock(lock_path: Path) -> None:
    try:
        owner = json.loads(lock_path.read_text(encoding="utf-8"))
        if int(owner.get("pid", 0)) == os.getpid():
            lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def _composition(duration_ms: int) -> MotionComposition:
    plate = MotionLayer(
        name="Long Run Plate", layer_type="shape",
        source=SourceRef(kind="shape", params={
            "shape": "rectangle", "width": 520, "height": 220,
            "corner_radius": 28, "fill": "#24677f", "stroke": "#eaf7ff",
            "stroke_width": 5,
        }), out_ms=duration_ms,
    )
    plate.transform.position.default = [640, 360]
    particles = create_particle_layer(
        width=1280, height=720, duration_ms=duration_ms,
        params={
            "seed": 20260722, "birth_rate": 24,
            "emitter": {"kind": "circle", "position": [640, 360], "radius": 130, "size": [260, 260], "path": []},
            "velocity": {"speed": 110, "speed_variance": .25, "angle_deg": -90, "spread_deg": 120},
            "gravity": [0, 55], "turbulence": {"strength": 8, "frequency": 1.0},
            "particle": {
                "shape": "square", "size_start": 12, "size_end": 2,
                "opacity_start": 1, "opacity_end": 0, "color_start": "#55e0c1",
                "color_end": "#f5cb6900", "rotation_speed": 55, "sprite_uri": "",
            },
        },
    )
    particles.blend_mode = "screen"
    return MotionComposition(
        id="motion_long_run_30m", name="Motion 30 Minute OpenGL Burn-in",
        width=1280, height=720, fps=30, duration_ms=duration_ms,
        layers=[plate, particles],
    )


def _rss_bytes() -> int:
    try:
        import psutil

        return int(psutil.Process().memory_info().rss)
    except Exception:
        if os.name != "nt":
            return 0
        try:
            import ctypes

            class ProcessMemoryCounters(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
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
            get_current_process.restype = ctypes.c_void_p
            process = get_current_process()
            get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
            get_memory_info.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
            if get_memory_info(
                process, ctypes.byref(counters), counters.cb,
            ):
                return int(counters.WorkingSetSize)
        except Exception:
            pass
        return 0


def run(output_dir: Path, *, duration_seconds: float) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    target_seconds = max(1.0, float(duration_seconds))
    duration_ms = int(round(target_seconds * 1000.0))
    composition = _composition(duration_ms)
    window = MotionDesignerWindow(composition)
    window.resize(1440, 900)
    window.show()
    window.viewer_tabs.setCurrentWidget(window.preview)
    frame_swaps = 0

    def on_frame_swapped() -> None:
        nonlocal frame_swaps
        frame_swaps += 1

    window.preview.frameSwapped.connect(on_frame_swapped)
    for _ in range(40):
        app.processEvents()
        time.sleep(.015)
    start_image = window.preview.grabFramebuffer()
    start_path = output_dir / "start.png"
    if start_image.isNull() or not start_image.save(str(start_path), "PNG"):
        raise RuntimeError("Could not capture Motion long-run start frame")
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    start_rss = _rss_bytes()
    samples: list[dict] = []
    next_sample = 0.0
    window._set_playback_direction(1)
    while True:
        app.processEvents()
        elapsed = time.monotonic() - started
        if elapsed >= next_sample or elapsed >= target_seconds:
            sample = {
                "elapsed_seconds": elapsed,
                "timeline_time_ms": int(window._time_ms),
                "frame_swaps": frame_swaps,
                "rss_bytes": _rss_bytes(),
                "diagnostics": window.preview.diagnostics(),
            }
            samples.append(sample)
            _write_json(output_dir / "progress.json", {
                "ok": True,
                "target_seconds": target_seconds,
                "started_at": started_at,
                "latest": sample,
                "sample_count": len(samples),
            })
            print(json.dumps({"motion_long_run": sample}), flush=True)
            next_sample += 60.0
        if elapsed >= target_seconds:
            break
        time.sleep(.004)
    window._set_playback_direction(0)
    for _ in range(20):
        app.processEvents()
        time.sleep(.01)
    end_image = window.preview.grabFramebuffer()
    end_path = output_dir / "end.png"
    if end_image.isNull() or not end_image.save(str(end_path), "PNG"):
        raise RuntimeError("Could not capture Motion long-run end frame")
    elapsed = time.monotonic() - started
    final_rss = _rss_bytes()
    diagnostics = window.preview.diagnostics()
    average_fps = frame_swaps / max(elapsed, .001)
    timeline_reached = int(window._time_ms) >= duration_ms - 1000
    memory_growth = max(0, final_rss - start_rss)
    ok = bool(
        elapsed >= target_seconds * .995
        and timeline_reached
        and average_fps >= 20.0
        and diagnostics.get("context_valid")
        and str(diagnostics.get("backend") or "").startswith("motion_")
        and int(diagnostics.get("gl_error", -1)) == 0
        and memory_growth <= 512 * 1024 * 1024
    )
    report = {
        "ok": ok,
        "scope": "continuous_wall_clock_motion_opengl_preview",
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "target_seconds": target_seconds,
        "elapsed_seconds": elapsed,
        "timeline_duration_ms": duration_ms,
        "timeline_final_ms": int(window._time_ms),
        "timeline_reached_end": timeline_reached,
        "frame_swaps": frame_swaps,
        "average_frame_swaps_per_second": average_fps,
        "start_rss_bytes": start_rss,
        "final_rss_bytes": final_rss,
        "memory_growth_bytes": memory_growth,
        "software_renderer_used": False,
        "backend": diagnostics,
        "samples": samples,
        "outputs": {"start": str(start_path.resolve()), "end": str(end_path.resolve())},
    }
    report_path = output_dir / "report.json"
    _write_json(report_path, report)
    window.close()
    app.processEvents()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a continuous Motion OpenGL preview burn-in")
    parser.add_argument("--duration-seconds", type=float, default=1800.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output_dir = args.output.resolve()
    lock_path = _acquire_run_lock(output_dir)
    try:
        for stale_name in ("progress.json", "report.json"):
            (output_dir / stale_name).unlink(missing_ok=True)
        report = run(output_dir, duration_seconds=args.duration_seconds)
    finally:
        _release_run_lock(lock_path)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

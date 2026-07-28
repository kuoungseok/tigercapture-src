from __future__ import annotations

import json
import gc
import ctypes
import math
import os
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.puppet_mesh import (
    add_puppet_pin,
    create_grid_puppet_mesh,
    evaluate_puppet_render_vertices,
    layer_puppet_mesh,
)
from app.motion_designer.schema import Keyframe, MotionLayer


OUTPUT = ROOT / "debugCapture" / "motion_designer" / "m14_long_playback"


def _rss_bytes() -> int | None:
    if os.name != "nt":
        return None

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
    get_process = ctypes.windll.kernel32.GetCurrentProcess
    get_process.restype = ctypes.c_void_p
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    get_memory.restype = ctypes.c_int
    handle = get_process()
    if not get_memory(
        handle, ctypes.byref(counters), counters.cb,
    ):
        return None
    return int(counters.WorkingSetSize)


def _mesh():
    layer = MotionLayer(
        id="m14_long_playback",
        name="M14 Long Playback",
        layer_type="image",
        out_ms=600_000,
    )
    create_grid_puppet_mesh(layer, columns=8, rows=8)
    position = add_puppet_pin(
        layer, kind="position", position=[0.5, 0.48], radius=0.38,
    )
    bend = add_puppet_pin(
        layer, kind="bend", position=[0.34, 0.48], radius=0.42,
    )
    add_puppet_pin(
        layer, kind="starch", position=[0.84, 0.5], radius=0.22, strength=1.4,
    )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    position_pin = next(pin for pin in mesh.pins if pin.id == position.id)
    position_pin.position.keyframes = [
        Keyframe(time_ms=0, value=[0.5, 0.48]),
        Keyframe(time_ms=1000, value=[0.57, 0.42]),
        Keyframe(time_ms=2000, value=[0.5, 0.48]),
        Keyframe(time_ms=3000, value=[0.43, 0.54]),
        Keyframe(time_ms=4000, value=[0.5, 0.48]),
    ]
    bend_pin = next(pin for pin in mesh.pins if pin.id == bend.id)
    bend_pin.rotation.keyframes = [
        Keyframe(time_ms=0, value=0.0),
        Keyframe(time_ms=1000, value=16.0),
        Keyframe(time_ms=2000, value=0.0),
        Keyframe(time_ms=3000, value=-16.0),
        Keyframe(time_ms=4000, value=0.0),
    ]
    mesh.metadata["tear_repair"] = {
        "enabled": True,
        "mode": "local",
        "max_edge_stretch": 6.0,
    }
    return mesh


def main() -> int:
    fps = 30
    duration_ms = 600_000
    frame_count = duration_ms * fps // 1000 + 1
    mesh = _mesh()
    unsafe_frames = 0
    non_finite_vertices = 0
    repaired_frames = 0
    max_displacement = 0.0
    cycle_samples: dict[int, tuple[tuple[float, float], ...]] = {}
    cycle_mismatch_count = 0
    gc.collect()
    initial_bytes = _rss_bytes()
    started = perf_counter()
    for frame in range(frame_count):
        absolute_time = frame * 1000.0 / fps
        cycle_time = int(round(absolute_time)) % 4000
        points, repair = evaluate_puppet_render_vertices(
            mesh,
            cycle_time,
            width=1920,
            height=1080,
        )
        unsafe_frames += int(not repair.get("render_safe", False))
        repaired_frames += int(repair.get("mode") not in {"none", "disabled"})
        for vertex, point in zip(mesh.vertices, points):
            if not math.isfinite(point[0]) or not math.isfinite(point[1]):
                non_finite_vertices += 1
                continue
            max_displacement = max(
                max_displacement,
                math.hypot(point[0] - vertex.uv[0], point[1] - vertex.uv[1]),
            )
        if cycle_time in {0, 1000, 2000, 3000}:
            rounded = tuple((round(x, 9), round(y, 9)) for x, y in points)
            previous = cycle_samples.setdefault(cycle_time, rounded)
            cycle_mismatch_count += int(previous != rounded)
    gc.collect()
    current_bytes = _rss_bytes()
    growth_bytes = (
        max(0, current_bytes - initial_bytes)
        if current_bytes is not None and initial_bytes is not None
        else None
    )
    elapsed = perf_counter() - started
    report = {
        "ok": bool(
            frame_count == 18_001
            and unsafe_frames == 0
            and non_finite_vertices == 0
            and cycle_mismatch_count == 0
            and growth_bytes is not None
            and growth_bytes < 16 * 1024 * 1024
        ),
        "duration_ms": duration_ms,
        "fps": fps,
        "frame_count": frame_count,
        "mesh": {
            "vertex_count": len(mesh.vertices),
            "triangle_count": len(mesh.triangles),
            "pin_count": len(mesh.pins),
        },
        "stability": {
            "unsafe_frame_count": unsafe_frames,
            "non_finite_vertex_count": non_finite_vertices,
            "cycle_mismatch_count": cycle_mismatch_count,
            "repair_frame_count": repaired_frames,
            "max_normalized_displacement": max_displacement,
        },
        "memory": {
            "measurement": "windows_working_set",
            "initial_bytes": initial_bytes,
            "current_bytes": current_bytes,
            "growth_bytes": growth_bytes,
        },
        "elapsed_seconds": elapsed,
        "solver": "cpu_pins_with_local_tear_repair",
        "preview_rasterizer": "opengl_verified_separately",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise RuntimeError(f"M14 long playback QA failed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

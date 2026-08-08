"""Native DXR bridge for AR/PBR asset rendering.

The native helper runs in a separate process. This module converts the existing
model-view vertex contract into the compact non-indexed triangle layout used by
the DXR BLAS builder; it never imports Painter or drawing modules.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Mapping

import numpy as np


NATIVE_RT_SCHEMA = "tigerstudio.ar_pbr.native_rt_render.v1"
NATIVE_RT_VERTEX_FLOATS = 11


def default_native_rt_helper_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    candidates = (
        root / "external" / "tools" / "ar_pbr_dxr" / "TigerStudioDxrHelper.exe",
        root / "bundled" / "tools" / "ar_pbr_dxr" / "TigerStudioDxrHelper.exe",
    )
    return next((path for path in candidates if path.is_file()), candidates[0])


def pack_model_view_vertices(vertices: Any) -> np.ndarray:
    """Convert Tiger's 29-float GPU vertex packet to the native 11-float ABI."""
    source = np.asarray(vertices, dtype=np.float32)
    if source.ndim != 2 or source.shape[1] < 13 or len(source) < 3 or len(source) % 3:
        raise ValueError("native RT requires non-indexed triangle vertices with the Tiger GPU material layout")
    packed = np.empty((len(source), NATIVE_RT_VERTEX_FLOATS), dtype=np.float32)
    packed[:, 0:3] = source[:, 0:3]
    packed[:, 3:6] = source[:, 3:6]
    packed[:, 6:9] = source[:, 6:9]
    packed[:, 9] = np.clip(source[:, 11], 0.0, 1.0)  # metallic
    packed[:, 10] = np.clip(source[:, 10], 0.03, 1.0)  # roughness
    return np.ascontiguousarray(packed, dtype=np.float32)


def render_descriptor_native_rt(
    descriptor: Mapping[str, Any],
    *,
    output_path: str | Path,
    track: Mapping[str, Any] | None = None,
    time_ms: int = 0,
    mode: str = "hybrid_rt",
    width: int = 960,
    height: int = 720,
    samples: int = 16,
    bounces: int = 3,
    camera_visible: bool = True,
    reflection_visible: bool = True,
    hdri_path: str | Path | None = None,
    ibl_rotation: float = 0.0,
    helper_path: str | Path | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    from tools.ar_pbr_gpu_window import build_vertex_buffer

    helper = Path(helper_path or default_native_rt_helper_path()).expanduser().resolve()
    if not helper.is_file():
        raise FileNotFoundError(f"native DXR helper not found: {helper}")
    requested_mode = str(mode or "hybrid_rt").strip().casefold()
    if requested_mode not in {"hybrid_rt", "path_traced"}:
        raise ValueError("native RT mode must be hybrid_rt or path_traced")
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    gpu_vertices, mesh_diagnostics = build_vertex_buffer(
        descriptor,
        track=dict(track or {}),
        time_ms=max(0, int(time_ms)),
    )
    native_vertices = pack_model_view_vertices(gpu_vertices)
    with tempfile.TemporaryDirectory(prefix="tigerstudio_dxr_") as temp_text:
        vertices_path = Path(temp_text) / "scene_vertices.bin"
        native_vertices.tofile(vertices_path)
        environment_args: list[str] = []
        environment_source = Path(hdri_path).expanduser().resolve() if hdri_path else None
        environment_size: list[int] = []
        if environment_source is not None and environment_source.is_file():
            from app.ar_pbr.hdr import load_radiance_hdr

            hdr = load_radiance_hdr(environment_source)
            rgb = np.asarray(hdr.pixels, dtype=np.float32)
            step = max(1, int(np.ceil(max(1, rgb.shape[1]) / 2048.0)))
            rgb = np.ascontiguousarray(rgb[::step, ::step, :3], dtype=np.float32)
            alpha = np.ones((*rgb.shape[:2], 1), dtype=np.float32)
            rgba = np.ascontiguousarray(np.concatenate((rgb, alpha), axis=2), dtype=np.float32)
            environment_path = Path(temp_text) / "environment_rgba32f.bin"
            rgba.tofile(environment_path)
            environment_size = [int(rgba.shape[1]), int(rgba.shape[0])]
            environment_args = [
                "--environment",
                str(environment_path),
                "--environment-width",
                str(environment_size[0]),
                "--environment-height",
                str(environment_size[1]),
                "--environment-rotation",
                str(float(ibl_rotation) / 360.0),
            ]
        command = [
            str(helper),
            "--render",
            "--mode",
            requested_mode,
            "--output",
            str(output),
            "--vertices",
            str(vertices_path),
            "--width",
            str(max(16, min(4096, int(width)))),
            "--height",
            str(max(16, min(4096, int(height)))),
            "--samples",
            str(max(1, min(256, int(samples)))),
            "--bounces",
            str(max(1, min(8, int(bounces)))),
            "--camera-visible",
            "1" if camera_visible else "0",
            "--reflection-visible",
            "1" if reflection_visible else "0",
            *environment_args,
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(10, int(timeout_seconds)),
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    raw = (completed.stdout or completed.stderr or "").strip()
    try:
        native = json.loads(raw or "{}")
    except json.JSONDecodeError:
        native = {"raw": raw[:4000]}
    ok = completed.returncode == 0 and bool(native.get("ok")) and output.is_file()
    return {
        "schema": NATIVE_RT_SCHEMA,
        "ok": ok,
        "mode": requested_mode,
        "hardware_ray_tracing": bool(ok and native.get("hardware_ray_tracing")),
        "output_path": str(output),
        "helper_path": str(helper),
        "vertex_count": int(len(native_vertices)),
        "triangle_count": int(len(native_vertices) // 3),
        "hdri_path": str(environment_source) if environment_source is not None else "",
        "environment_size": environment_size,
        "mesh_diagnostics": dict(mesh_diagnostics or {}),
        "native": native,
        "returncode": int(completed.returncode),
        "stderr": (completed.stderr or "").strip()[:4000],
        "process_isolated": True,
        "painter_hot_path": False,
    }

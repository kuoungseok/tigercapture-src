"""AR/PBR full GPU export service bridge.

The exporter must not create Qt/OpenGL objects inside VideoExportThread.  This
module launches the model-view-style PBR renderer in a separate helper process
and keeps the deterministic packet fallback for every helper failure.
"""
from __future__ import annotations

import json
import os
import queue
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Mapping

from app.ar_pbr.depth_occlusion import normalize_depth_frame


FULL_GPU_EXPORT_SERVICE_COMMAND_ENV = "TIGERCAPTURE_AR_PBR_FULL_GPU_SERVICE_COMMAND"
FULL_GPU_EXPORT_SERVICE_TIMEOUT_ENV = "TIGERCAPTURE_AR_PBR_FULL_GPU_SERVICE_TIMEOUT"
FULL_GPU_EXPORT_SERVICE_QPA_ENV = "TIGERCAPTURE_AR_PBR_FULL_GPU_SERVICE_QPA_PLATFORM"
FULL_GPU_EXPORT_SERVICE_QT_OPENGL_ENV = "TIGERCAPTURE_AR_PBR_FULL_GPU_SERVICE_QT_OPENGL"
FULL_GPU_EXPORT_SERVICE_PERSISTENT_ENV = "TIGERCAPTURE_AR_PBR_FULL_GPU_SERVICE_PERSISTENT"


_PERSISTENT_CLIENTS: dict[tuple[str, str, str, str], "_PersistentFullGpuServiceClient"] = {}
_PERSISTENT_CLIENTS_LOCK = threading.Lock()


def _quote(value: str | Path) -> str:
    text = str(value)
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or any(ch in text for ch in ('"', "'")):
        return json.dumps(text)
    return text


def default_full_gpu_export_service_command(root: str | Path | None = None) -> str:
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    script = root_path / "tools" / "ar_pbr_full_gpu_export_service.py"
    if not script.is_file():
        return ""
    candidates = []
    if os.name == "nt":
        candidates.extend([
            root_path / ".venv" / "Scripts" / "python.exe",
            root_path / ".venv" / "Scripts" / "pythonw.exe",
        ])
    else:
        candidates.extend([
            root_path / ".venv" / "bin" / "python",
            root_path / ".venv" / "bin" / "python3",
        ])
    candidates.append(Path(sys.executable))
    exe = next((path for path in candidates if path and path.is_file()), None)
    if exe is None:
        return ""
    return f"{_quote(exe)} {_quote(script)}"


def _env(env: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return env if env is not None else os.environ


def _command_parts(command: str) -> list[str]:
    text = str(command or "").strip()
    if not text:
        return []
    if os.name == "nt":
        parts = shlex.split(text, posix=False)
    else:
        parts = shlex.split(text)
    return [str(part).strip().strip('"').strip("'") for part in parts if str(part).strip()]


def _command_available(command: str) -> bool:
    parts = _command_parts(command)
    if not parts:
        return False
    exe = parts[0].strip('"')
    if Path(exe).is_file():
        return True
    return shutil.which(exe) is not None


def _probe_service(command: str, *, timeout_seconds: int, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    parts = _command_parts(command)
    if not parts:
        return {"ok": False, "error": "service_command_empty"}
    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            [*parts, "--probe"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1, int(timeout_seconds or 10)),
            creationflags=creationflags,
            env=_service_process_env(env),
        )
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    raw = (completed.stdout or completed.stderr or "").strip()
    payload: dict[str, Any] = {}
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                payload = data
        except Exception:
            payload = {"raw": raw[:2000]}
    ok = int(completed.returncode or 0) == 0 and bool(payload.get("ok", True))
    return {
        "ok": ok,
        "returncode": int(completed.returncode or 0),
        "payload": payload,
        "stderr": (completed.stderr or "").strip()[:2000],
    }


class _PersistentFullGpuServiceClient:
    def __init__(self, command: str, *, env: Mapping[str, str] | None = None) -> None:
        self.command = str(command)
        self.env = _service_process_env(env)
        self.parts = _command_parts(self.command)
        self._lock = threading.Lock()
        self._stdout: "queue.Queue[str]" = queue.Queue()
        self._stderr_tail: list[str] = []
        self._proc = self._start()

    def _start(self) -> subprocess.Popen[str]:
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            [*self.parts, "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            env=self.env,
        )
        threading.Thread(target=self._read_stdout, args=(proc,), daemon=True).start()
        threading.Thread(target=self._read_stderr, args=(proc,), daemon=True).start()
        return proc

    def _read_stdout(self, proc: subprocess.Popen[str]) -> None:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                self._stdout.put(str(line).strip())
        except Exception:
            pass

    def _read_stderr(self, proc: subprocess.Popen[str]) -> None:
        try:
            assert proc.stderr is not None
            for line in proc.stderr:
                text = str(line).strip()
                if text:
                    self._stderr_tail.append(text)
                    del self._stderr_tail[:-8]
        except Exception:
            pass

    def request(self, request_path: Path, *, timeout_seconds: int) -> dict[str, Any]:
        with self._lock:
            if self._proc.poll() is not None:
                raise RuntimeError(f"persistent_service_exited:{self._proc.returncode}")
            if self._proc.stdin is None:
                raise RuntimeError("persistent_service_stdin_missing")
            payload = {"request_path": str(request_path)}
            self._proc.stdin.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
            self._proc.stdin.flush()
            deadline = time.monotonic() + max(1.0, float(timeout_seconds or 1))
            line = ""
            while time.monotonic() < deadline:
                if self._proc.poll() is not None and self._stdout.empty():
                    detail = " | ".join(self._stderr_tail[-3:])
                    raise RuntimeError(f"persistent_service_exited:{self._proc.returncode}:{detail}")
                try:
                    line = self._stdout.get(timeout=0.1)
                    break
                except queue.Empty:
                    continue
            if not line:
                self.close()
                detail = " | ".join(self._stderr_tail[-3:])
                raise TimeoutError(f"persistent_service_timeout:{detail}")
            if not line:
                raise RuntimeError("persistent_service_empty_response")
            try:
                data = json.loads(line)
            except Exception as exc:
                raise RuntimeError(f"persistent_service_bad_json:{line[:500]}") from exc
            return data if isinstance(data, dict) else {}

    def close(self) -> None:
        proc = self._proc
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except Exception:
            pass
        try:
            if proc.poll() is None:
                proc.terminate()
        except Exception:
            pass


def _persistent_service_enabled(env: Mapping[str, str] | None = None) -> bool:
    value = str(_env(env).get(FULL_GPU_EXPORT_SERVICE_PERSISTENT_ENV, "1") or "1").strip().casefold()
    return value not in {"0", "false", "no", "off", "disabled"}


def _persistent_client_key(command: str, env: Mapping[str, str] | None = None) -> tuple[str, str, str, str]:
    e = _env(env)
    return (
        str(command),
        str(e.get(FULL_GPU_EXPORT_SERVICE_QPA_ENV) or ""),
        str(e.get(FULL_GPU_EXPORT_SERVICE_QT_OPENGL_ENV) or ""),
        str(e.get("QT_OPENGL") or ""),
    )


def _persistent_client(command: str, env: Mapping[str, str] | None = None) -> _PersistentFullGpuServiceClient:
    key = _persistent_client_key(command, env)
    with _PERSISTENT_CLIENTS_LOCK:
        client = _PERSISTENT_CLIENTS.get(key)
        if client is None or client._proc.poll() is not None:
            client = _PersistentFullGpuServiceClient(command, env=env)
            _PERSISTENT_CLIENTS[key] = client
        return client


def _render_via_persistent_service(
    *,
    command: str,
    request_path: Path,
    out_path: Path,
    timeout_seconds: int,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    client = _persistent_client(command, env)
    diag = client.request(request_path, timeout_seconds=timeout_seconds)
    diag = dict(diag or {})
    diag["service_command"] = command
    diag["persistent_service"] = True
    if not out_path.is_file():
        diag["ok"] = False
        diag.setdefault("errors", []).append("service_output_frame_missing")
    return diag


def full_gpu_export_service_contract() -> dict[str, Any]:
    return {
        "input": {
            "request_json": {
                "schema": "tigerstudio.ar_pbr.full_gpu_export_request.v1",
                "base_frame": "absolute path to RGBA/PNG/NPY frame or shared temp frame",
                "ar_tracks": "normalized AR/PBR descriptors with material_override preserved",
                "camera_solution": "resolved camera/depth/anchor state",
                "depth_frame": "optional depth map path or inline metadata",
                "settings": "HDRI, light, exposure, shadow/reflection catcher options",
            }
        },
        "output": {
            "rgba_frame": "absolute path to rendered RGBA frame",
            "diagnostics_json": {
                "ok": "bool",
                "renderer_quality": "full_model_view_gpu_pbr",
                "texture_maps_sampled": "int",
                "hdri_ibl": "bool",
                "shadow_map": "bool",
                "shadow_filter": "PCF/PCSS diagnostics when shadow map is requested",
                "catcher": "matte shadow/reflection catcher diagnostics",
        "color_management": "tone mapping/exposure/white balance/gamma diagnostics",
        "hybrid_rendering": "hybrid accumulation, diffuse/specular GI, and denoise diagnostics",
        "ray_gi_detail": "ray/hybrid GI bounce, clamp, light sampling, and denoise-channel diagnostics",
        "ambient_occlusion_rendering": "screen/ray-traced ambient occlusion diagnostics",
        "depth_occlusion": "video-depth matte availability, tolerance, and occluded-pixel diagnostics",
        "transmission_rendering": "transmission/refraction and glass absorption diagnostics",
        "clearcoat_rendering": "clearcoat secondary specular layer diagnostics",
        "parallax_rendering": "height-map tangent-space UV offset diagnostics",
        "displacement_rendering": "height/vector geometry displacement contract and parallax fallback diagnostics",
        "bevel_rendering": "shader-only rounded-edge normal diagnostics",
        "material_layering": "single overlay material layer diagnostics",
        "subsurface_rendering": "single-scatter subsurface approximation diagnostics",
        "hair_groom_rendering": "dual-lobe anisotropic hair/groom diagnostics",
        "cloth_sheen_rendering": "Charlie-style cloth/fabric sheen diagnostics",
        "glint_sparkle_rendering": "deterministic microflake glint/sparkle diagnostics",
        "caustics_rendering": "glass/specular caustic highlight approximation diagnostics",
        "anisotropic_rendering": "general anisotropic reflection, clearcoat anisotropy, and thin-film diagnostics",
        "microsurface_rendering": "detail normal layering and advanced roughness/gloss microsurface diagnostics",
        "depth_of_field_rendering": "depth-banded camera/lens post-blur diagnostics",
        "post_effects_rendering": "beauty-pass bloom/vignette/grain/sharpen diagnostics",
        "lens_effects_rendering": "camera/lens distortion and chromatic aberration diagnostics",
        "lens_flare_rendering": "lens flare, aperture flare, dirt, and scratch diagnostics",
        "render_passes": "multi-pass render output request/contract diagnostics",
        "motion_blur": "final-render shutter/sample motion blur request/contract diagnostics",
        "udim_rendering": "UDIM tile-set texture-plan diagnostics",
        "triplanar_rendering": "normal-weighted axis texture projection diagnostics",
        "material_override_preserved": "bool",
            },
        },
        "safety": [
            "The service runs outside VideoExportThread.",
            "The exporter must keep packet PBR fallback on failure.",
            "The service must not mutate project files.",
            "material_override=false must stay false through normalization.",
        ],
        "probe": "Service command must accept --probe and print JSON with ok=true.",
    }


def build_full_gpu_export_service_report(
    *,
    env: Mapping[str, str] | None = None,
    probe: bool = False,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    e = _env(env)
    command = str(e.get(FULL_GPU_EXPORT_SERVICE_COMMAND_ENV) or default_full_gpu_export_service_command()).strip()
    configured = bool(command)
    available = bool(configured and _command_available(command))
    probe_result: dict[str, Any] = {}
    if probe and available:
        probe_result = _probe_service(command, timeout_seconds=timeout_seconds, env=e)

    probe_ok = bool(probe_result.get("ok")) if probe else False
    full_available = bool(available and (probe_ok if probe else False))
    blockers: list[str] = []
    if not configured:
        blockers.append("service_command_not_configured")
    elif not available:
        blockers.append("service_command_not_found")
    elif probe and not probe_ok:
        blockers.append("service_probe_failed")
    else:
        blockers.append("service_probe_not_run")

    return {
        "kind": "ar_pbr_full_gpu_export_service",
        "ok": True,
        "contract_ready": True,
        "full_gpu_export_available": full_available,
        "worker_safe": full_available,
        "service_command_env": FULL_GPU_EXPORT_SERVICE_COMMAND_ENV,
        "qt_opengl_env": FULL_GPU_EXPORT_SERVICE_QT_OPENGL_ENV,
        "persistent_service_env": FULL_GPU_EXPORT_SERVICE_PERSISTENT_ENV,
        "service_command": command,
        "configured": configured,
        "default_command": default_full_gpu_export_service_command(),
        "available": available,
        "probe_requested": bool(probe),
        "probe": probe_result,
        "blockers": blockers if not full_available else [],
        "contract": full_gpu_export_service_contract(),
        "next_actions": [
            f"Set {FULL_GPU_EXPORT_SERVICE_COMMAND_ENV} to override the default helper process if needed.",
            f"Set {FULL_GPU_EXPORT_SERVICE_PERSISTENT_ENV}=0 only for diagnosing one-shot helper startup.",
            "Run probe+smoke QA before claiming full GPU export parity on a machine.",
            "Tune material/IBL/shadow parity against real FBX/GLB samples; keep packet fallback on every failure.",
        ],
    }


def _frame_to_pil_rgba(base_frame: Any):
    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:
        return None, "", f"missing image dependency: {type(exc).__name__}"
    if isinstance(base_frame, Image.Image):
        return base_frame.convert("RGBA"), "pil", ""
    try:
        arr = np.asarray(base_frame)
    except Exception:
        return None, "", "unsupported base_frame type"
    if arr.ndim != 3 or arr.shape[2] not in {3, 4}:
        return None, "", "base_frame must be HxWx3 or HxWx4"
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.shape[2] == 3:
        return Image.fromarray(arr, "RGB").convert("RGBA"), "numpy_rgb", ""
    return Image.fromarray(arr, "RGBA"), "numpy_rgba", ""


def _pil_to_original_kind(image: Any, kind: str, original: Any):
    if kind == "pil":
        return image.convert("RGBA")
    try:
        import numpy as np

        arr = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        if kind == "numpy_rgb":
            return arr[:, :, :3].copy()
        return arr.copy()
    except Exception:
        return original


def _serialize_depth_frame(depth_frame: Any, path: Path, *, width: int, height: int) -> dict[str, Any] | None:
    if depth_frame is None:
        return None
    try:
        import numpy as np

        if isinstance(depth_frame, (str, Path)):
            source = Path(depth_frame)
            if source.is_file():
                return {
                    "kind": "path",
                    "path": str(source),
                    "width": int(width),
                    "height": int(height),
                }
        arr = normalize_depth_frame(depth_frame, width, height)
        if arr is None:
            return None
        np.save(path, np.asarray(arr, dtype=np.float32))
        return {
            "kind": "npy",
            "path": str(path),
            "width": int(width),
            "height": int(height),
            "dtype": "float32",
        }
    except Exception:
        return None


def _service_process_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = dict(os.environ)
    if env:
        source.update({str(k): str(v) for k, v in env.items()})
    qt_opengl_override = str(source.get(FULL_GPU_EXPORT_SERVICE_QT_OPENGL_ENV) or "").strip()
    if qt_opengl_override:
        source["QT_OPENGL"] = qt_opengl_override
    elif os.name == "nt":
        # PyOpenGL + Qt's ANGLE/software default can leave QOpenGLWidget with
        # an invalid context in the worker helper.  The model-view renderer is
        # a desktop OpenGL path, so make that the service default on Windows.
        source["QT_OPENGL"] = "desktop"
    qpa_override = str(source.get(FULL_GPU_EXPORT_SERVICE_QPA_ENV) or "").strip()
    if qpa_override:
        source["QT_QPA_PLATFORM"] = qpa_override
    elif os.name == "nt" and str(source.get("QT_QPA_PLATFORM") or "").strip().lower() == "offscreen":
        # The helper uses QOpenGLWidget. On Windows the offscreen QPA plugin can
        # fail to create the widget/context, especially after other QA modules
        # set QT_QPA_PLATFORM=offscreen globally. Let the helper use the normal
        # Windows platform while the helper window stays offscreen.
        source.pop("QT_QPA_PLATFORM", None)
    return source


def render_frame_via_full_gpu_export_service(
    base_frame: Any,
    *,
    time_ms: int,
    ar_tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any = None,
    settings: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[Any, dict[str, Any]]:
    e = _env(env)
    command = str(e.get(FULL_GPU_EXPORT_SERVICE_COMMAND_ENV) or default_full_gpu_export_service_command()).strip()
    if not command:
        return base_frame, {
            "ok": False,
            "mode": "full_model_view_gpu_export_service",
            "fallback": True,
            "errors": ["service_command_not_configured"],
        }
    if not _command_available(command):
        return base_frame, {
            "ok": False,
            "mode": "full_model_view_gpu_export_service",
            "fallback": True,
            "service_command": command,
            "errors": ["service_command_not_found"],
        }
    image, kind, error = _frame_to_pil_rgba(base_frame)
    if image is None:
        return base_frame, {
            "ok": False,
            "mode": "full_model_view_gpu_export_service",
            "fallback": True,
            "service_command": command,
            "errors": [error or "unsupported frame"],
        }

    timeout = 90
    try:
        timeout = max(1, int(str(e.get(FULL_GPU_EXPORT_SERVICE_TIMEOUT_ENV) or "90").strip()))
    except Exception:
        timeout = 90
    with tempfile.TemporaryDirectory(prefix="tiger_ar_pbr_full_gpu_") as raw_tmp:
        tmp = Path(raw_tmp)
        base_path = tmp / "base.png"
        out_path = tmp / "out.png"
        request_path = tmp / "request.json"
        depth_path = tmp / "depth.npy"
        image.save(base_path)
        depth_payload = _serialize_depth_frame(depth_frame, depth_path, width=image.size[0], height=image.size[1])
        request = {
            "schema": "tigerstudio.ar_pbr.full_gpu_export_request.v1",
            "base_frame_path": str(base_path),
            "output_frame_path": str(out_path),
            "time_ms": int(time_ms),
            "ar_tracks": list(ar_tracks or []),
            "camera_solution": dict(camera_solution or {}),
            "depth_frame": depth_payload,
            "settings": dict(settings or {}),
        }
        request_path.write_text(json.dumps(request, ensure_ascii=False, default=str), encoding="utf-8")
        parts = _command_parts(command)
        persistent_diag: dict[str, Any] = {}
        if _persistent_service_enabled(e):
            try:
                persistent_diag = _render_via_persistent_service(
                    command=command,
                    request_path=request_path,
                    out_path=out_path,
                    timeout_seconds=timeout,
                    env=e,
                )
                if bool(persistent_diag.get("ok")) and out_path.is_file():
                    from PIL import Image

                    out = Image.open(out_path).convert("RGBA")
                    final = _pil_to_original_kind(out, kind, base_frame)
                    persistent_diag["ok"] = True
                    persistent_diag["full_gpu_export_available"] = True
                    persistent_diag["worker_safe"] = True
                    persistent_diag["service_command"] = command
                    persistent_diag["persistent_service"] = True
                    return final, persistent_diag
            except Exception as exc:
                persistent_diag = {
                    "ok": False,
                    "mode": "full_model_view_gpu_export_service",
                    "fallback": True,
                    "persistent_service": True,
                    "service_command": command,
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }
        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc_env = _service_process_env(e)
            completed = subprocess.run(
                [*parts, "--request", str(request_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
                env=proc_env,
            )
        except Exception as exc:
            return base_frame, {
                "ok": False,
                "mode": "full_model_view_gpu_export_service",
                "fallback": True,
                "service_command": command,
                "persistent_service_attempt": persistent_diag,
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
        raw = (completed.stdout or completed.stderr or "").strip()
        try:
            diag = json.loads(raw) if raw else {}
        except Exception:
            diag = {"raw": raw[:2000]}
        if int(completed.returncode or 0) != 0 or not bool(diag.get("ok")) or not out_path.is_file():
            diag = dict(diag or {})
            diag.update({
                "ok": False,
                "mode": "full_model_view_gpu_export_service",
                "fallback": True,
                "service_command": command,
                "persistent_service_attempt": persistent_diag,
                "returncode": int(completed.returncode or 0),
            })
            diag.setdefault("errors", [])
            if completed.stderr:
                diag["errors"].append(completed.stderr.strip()[:2000])
            if not out_path.is_file():
                diag["errors"].append("service_output_frame_missing")
            return base_frame, diag
        try:
            from PIL import Image

            out = Image.open(out_path).convert("RGBA")
            final = _pil_to_original_kind(out, kind, base_frame)
        except Exception as exc:
            return base_frame, {
                "ok": False,
                "mode": "full_model_view_gpu_export_service",
                "fallback": True,
                "service_command": command,
                "persistent_service_attempt": persistent_diag,
                "errors": [f"service_output_decode_failed: {type(exc).__name__}: {exc}"],
            }
        diag = dict(diag or {})
        diag["ok"] = True
        diag["service_command"] = command
        diag["persistent_service_attempt"] = persistent_diag
        diag["persistent_service"] = False
        diag["full_gpu_export_available"] = True
        diag["worker_safe"] = True
        return final, diag

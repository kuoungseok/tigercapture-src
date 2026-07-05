from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import sys
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.subprocess_utils import hidden_subprocess_kwargs


PROTOCOL_VERSION = "json-lines-v1"
WORKER_ENV = "TIGERCAPTURE_NATIVE_WORKER"
_MEDIA_PROBE_CACHE_LIMIT = 256
_MEDIA_PROBE_CACHE: "OrderedDict[tuple[str, int, int, str], NativeMediaProbe]" = OrderedDict()
_SHARED_WORKER_ENV = "TIGERCAPTURE_NATIVE_WORKER_SHARED"
_SHARED_WORKER_DISABLED = {"0", "false", "no", "off"}
_SHARED_WORKER_LOCK = threading.RLock()
_SHARED_WORKER_CLIENT: "NativeWorkerClient | None" = None
_SHARED_WORKER_COMMAND: tuple[str, ...] | None = None


class NativeWorkerError(RuntimeError):
    """Raised when the native worker process fails or rejects a request."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class NativeWorkerCapabilities:
    name: str
    version: str
    protocol: str
    features: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NativeWorkerCapabilities":
        return cls(
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            protocol=str(data.get("protocol", "")),
            features=tuple(str(v) for v in data.get("features", []) or []),
        )


@dataclass(frozen=True)
class NativeWorkerProgressEvent:
    event: str
    current: int
    total: int
    message: str = ""
    payload: dict[str, Any] | None = None

    @classmethod
    def from_event(cls, event: str, payload: Any) -> "NativeWorkerProgressEvent":
        data = payload if isinstance(payload, dict) else {}
        return cls(
            event=str(event),
            current=int(data.get("current", 0) or 0),
            total=int(data.get("total", 0) or 0),
            message=str(data.get("message", "") or ""),
            payload=dict(data),
        )


@dataclass(frozen=True)
class NativeWorkerFileContract:
    path: str
    role: str
    kind: str = "file"
    must_exist: bool = False

    @classmethod
    def input_file(cls, path: Path | str, *, role: str = "input") -> "NativeWorkerFileContract":
        return cls(path=str(path), role=role, kind="file", must_exist=True)

    @classmethod
    def output_dir(cls, path: Path | str, *, role: str = "output") -> "NativeWorkerFileContract":
        return cls(path=str(path), role=role, kind="directory", must_exist=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "role": self.role,
            "kind": self.kind,
            "must_exist": self.must_exist,
        }


@dataclass(frozen=True)
class NativeMediaProbe:
    path: str
    exists: bool
    size: int
    mtime_ns: int
    duration_ms: int
    has_video: bool
    has_audio: bool
    width: int
    height: int
    fps: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NativeMediaProbe":
        return cls(
            path=str(data.get("path", "")),
            exists=bool(data.get("exists", False)),
            size=int(data.get("size", 0) or 0),
            mtime_ns=int(data.get("mtime_ns", 0) or 0),
            duration_ms=int(data.get("duration_ms", 0) or 0),
            has_video=bool(data.get("has_video", False)),
            has_audio=bool(data.get("has_audio", False)),
            width=int(data.get("width", 0) or 0),
            height=int(data.get("height", 0) or 0),
            fps=float(data.get("fps", 0.0) or 0.0),
        )


class NativeWorkerClient:
    """Small JSON-lines subprocess client for Rust helper workers.

    This is intentionally process-first instead of a Python extension binding.
    It keeps crashes isolated while the worker API is still young.
    """

    def __init__(
        self,
        command: list[str | Path],
        *,
        timeout_s: float = 5.0,
    ) -> None:
        if not command:
            raise ValueError("command must not be empty")
        self._command = [str(part) for part in command]
        self._timeout_s = float(timeout_s)
        self._next_id = 1
        self._proc: subprocess.Popen[str] | None = None

    def __enter__(self) -> "NativeWorkerClient":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **hidden_subprocess_kwargs(),
        )

    def close(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                try:
                    self.request("shutdown", {})
                except Exception:
                    pass
        finally:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            self._proc = None

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        return self.request_with_events(method, params, on_event=None)

    def request_with_events(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        on_event: Callable[[NativeWorkerProgressEvent], None] | None = None,
    ) -> Any:
        self.start()
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise NativeWorkerError("native worker did not start")
        if proc.poll() is not None:
            stderr = _read_available_stderr(proc)
            raise NativeWorkerError(f"native worker exited early: {stderr}")

        req_id = self._next_id
        self._next_id += 1
        payload = {
            "id": req_id,
            "method": str(method),
            "params": params or {},
        }
        proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        proc.stdin.flush()

        while True:
            line = _readline_with_timeout(proc.stdout, self._timeout_s)
            if not line:
                stderr = _read_available_stderr(proc)
                raise NativeWorkerError(f"native worker returned no response: {stderr}")
            try:
                response = json.loads(line)
            except json.JSONDecodeError as exc:
                raise NativeWorkerError(f"invalid worker response: {line!r}") from exc
            if response.get("id") != req_id:
                raise NativeWorkerError(
                    f"worker response id mismatch: expected {req_id}, got {response.get('id')}"
                )
            event = response.get("event")
            if event:
                if on_event is not None:
                    on_event(
                        NativeWorkerProgressEvent.from_event(
                            str(event),
                            response.get("result") or {},
                        )
                    )
                continue
            if "ok" not in response:
                raise NativeWorkerError(f"invalid worker event/response: {line!r}")
            if not response.get("ok"):
                raise NativeWorkerError(
                    str(response.get("error") or "native worker error"),
                    code=(
                        str(response.get("error_code"))
                        if response.get("error_code") is not None
                        else None
                    ),
                    details=response.get("details")
                    if isinstance(response.get("details"), dict)
                    else None,
                )
            return response.get("result")

    def capabilities(self) -> NativeWorkerCapabilities:
        result = self.request("capabilities", {})
        if not isinstance(result, dict):
            raise NativeWorkerError("capabilities response was not an object")
        caps = NativeWorkerCapabilities.from_dict(result)
        if caps.protocol != PROTOCOL_VERSION:
            raise NativeWorkerError(
                f"unsupported worker protocol: {caps.protocol or '<missing>'}"
            )
        return caps


def discover_native_worker_command() -> list[str] | None:
    env = os.environ.get(WORKER_ENV, "").strip()
    if env:
        return _command_from_env(env)

    exe_name = "tigercapture-worker.exe" if sys.platform == "win32" else "tigercapture-worker"
    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / "native" / "tigercapture_worker" / "target" / "release" / exe_name,
        root / "native" / "tigercapture_worker" / "target" / "debug" / exe_name,
        root / "bundled" / "native" / exe_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return [str(candidate)]
    return None


def get_native_worker_capabilities() -> NativeWorkerCapabilities | None:
    command = discover_native_worker_command()
    if command is None:
        return None
    try:
        result = _native_worker_request(command, "capabilities", {}, timeout_s=5.0)
        if not isinstance(result, dict):
            return None
        caps = NativeWorkerCapabilities.from_dict(result)
        if caps.protocol != PROTOCOL_VERSION:
            return None
        return caps
    except Exception:
        return None


def _media_probe_cache_key(path: Path | str, ffmpeg_path: str | None) -> tuple[str, int, int, str]:
    p = Path(path)
    try:
        st = p.stat()
        return (
            str(p.resolve()),
            int(st.st_mtime_ns),
            int(st.st_size),
            str(ffmpeg_path or ""),
        )
    except Exception:
        return (str(p), 0, 0, str(ffmpeg_path or ""))


def _media_probe_cache_get(key):
    if key not in _MEDIA_PROBE_CACHE:
        return None
    value = _MEDIA_PROBE_CACHE.pop(key)
    _MEDIA_PROBE_CACHE[key] = value
    return value


def _media_probe_cache_put(key, value: NativeMediaProbe) -> None:
    _MEDIA_PROBE_CACHE[key] = value
    while len(_MEDIA_PROBE_CACHE) > _MEDIA_PROBE_CACHE_LIMIT:
        _MEDIA_PROBE_CACHE.popitem(last=False)


def native_media_probe(path: Path | str, *, ffmpeg_path: str | None = None) -> NativeMediaProbe | None:
    key = _media_probe_cache_key(path, ffmpeg_path)
    cached = _media_probe_cache_get(key)
    if cached is not None:
        return cached
    command = discover_native_worker_command()
    if command is None:
        return None
    params: dict[str, Any] = {"path": str(path)}
    if ffmpeg_path:
        params["ffmpeg_path"] = str(ffmpeg_path)
    try:
        result = _native_worker_request(command, "media_probe", params, timeout_s=10.0)
        if not isinstance(result, dict):
            return None
        probe = NativeMediaProbe.from_dict(result)
        _media_probe_cache_put(key, probe)
        return probe
    except Exception:
        return None


def native_media_probe_many(
    paths: list[Path | str],
    *,
    ffmpeg_path: str | None = None,
) -> list[NativeMediaProbe | None] | None:
    if not paths:
        return []
    command = discover_native_worker_command()
    if command is None:
        return None
    params: dict[str, Any] = {"paths": [str(p) for p in paths]}
    if ffmpeg_path:
        params["ffmpeg_path"] = str(ffmpeg_path)
    try:
        result = _native_worker_request(
            command,
            "batch_media_probe",
            params,
            timeout_s=max(10.0, 5.0 * len(paths)),
        )
        if not isinstance(result, dict):
            return None
        items = result.get("items")
        if not isinstance(items, list):
            return None
        probes: list[NativeMediaProbe | None] = []
        for item in items:
            if isinstance(item, dict) and item.get("ok", True):
                probe = NativeMediaProbe.from_dict(item)
                key = _media_probe_cache_key(probe.path, ffmpeg_path)
                _media_probe_cache_put(key, probe)
                probes.append(probe)
            else:
                probes.append(None)
        return probes
    except Exception:
        return None


def native_generate_timeline_thumbnails(
    path: Path | str,
    out_dir: Path | str,
    *,
    ffmpeg_path: str | None = None,
    thumb_h: int = 48,
    min_thumbs: int = 10,
    max_thumbs: int = 60,
    seconds_per_tile: float = 4.0,
    on_progress: Callable[[NativeWorkerProgressEvent], None] | None = None,
    cancel_token_path: Path | str | None = None,
) -> list[Path] | None:
    command = discover_native_worker_command()
    if command is None:
        return None
    try:
        input_contract = NativeWorkerFileContract.input_file(path, role="source_media")
        output_contract = NativeWorkerFileContract.output_dir(out_dir, role="thumbnail_dir")
        _validate_file_contract(input_contract)
        _validate_file_contract(output_contract)
        params: dict[str, Any] = {
            "path": str(path),
            "out_dir": str(out_dir),
            "thumb_h": int(thumb_h),
            "min_thumbs": int(min_thumbs),
            "max_thumbs": int(max_thumbs),
            "seconds_per_tile": float(seconds_per_tile),
            "files": [input_contract.to_dict(), output_contract.to_dict()],
        }
        if ffmpeg_path:
            params["ffmpeg_path"] = str(ffmpeg_path)
        if on_progress is not None:
            params["emit_progress"] = True
        if cancel_token_path is not None:
            params["cancel_token_path"] = str(cancel_token_path)
        result = _native_worker_request(
            command,
            "timeline_thumbnails",
            params,
            timeout_s=max(120.0, min(420.0, float(max_thumbs) * 4.0)),
            on_event=on_progress,
        )
        if not isinstance(result, dict):
            return None
        files = result.get("files", [])
        if not isinstance(files, list):
            return None
        paths = [Path(str(p)) for p in files]
        return [p for p in paths if p.exists()] or None
    except Exception:
        return None


def native_timeline_drag_constraints(
    clips: list[dict[str, Any]],
    *,
    dragged_index: int | None = None,
    dragged_clip_id: Any | None = None,
    desired_timeline_in_ms: int,
    snap_ms: int = 200,
    extra_snap_targets: list[int] | tuple[int, ...] | None = None,
) -> dict[str, Any] | None:
    """Resolve timeline drag snapping/collision through the Rust worker.

    The return shape mirrors ``timeline_model.DragConstraintResult``. Missing or
    older workers return ``None`` so callers can keep the established Python
    path as the source of truth until native parity is proven.
    """
    command = discover_native_worker_command()
    if command is None:
        return None
    params: dict[str, Any] = {
        "clips": list(clips or []),
        "desired_timeline_in_ms": int(desired_timeline_in_ms),
        "snap_ms": max(0, int(snap_ms)),
        "extra_snap_targets": [int(v) for v in (extra_snap_targets or [])],
    }
    if dragged_index is not None:
        params["dragged_index"] = int(dragged_index)
    elif dragged_clip_id is not None:
        params["dragged_clip_id"] = dragged_clip_id
    else:
        return None
    try:
        result = _native_worker_request(
            command,
            "timeline_drag_constraints",
            params,
            timeout_s=5.0,
        )
        return dict(result) if isinstance(result, dict) else None
    except Exception:
        return None


def native_timeline_gaps(
    clips: list[dict[str, Any]],
    *,
    min_gap_ms: int = 1,
) -> dict[str, Any] | None:
    """Return timeline gaps through the Rust worker, or ``None`` on fallback."""
    command = discover_native_worker_command()
    if command is None:
        return None
    params: dict[str, Any] = {
        "clips": list(clips or []),
        "min_gap_ms": max(1, int(min_gap_ms)),
    }
    try:
        result = _native_worker_request(command, "timeline_gaps", params, timeout_s=5.0)
        return dict(result) if isinstance(result, dict) else None
    except Exception:
        return None


def native_timeline_trim_plan(
    clips: list[dict[str, Any]],
    *,
    clip_index: int | None = None,
    clip_id: Any | None = None,
    mode: str = "precision_trim",
    **params: Any,
) -> dict[str, Any] | None:
    """Return a video-only trim plan through the Rust worker, or ``None``.

    Python remains responsible for validation, linked-audio offsets, and undo
    application. The worker only computes the pure clip-window and following
    clip-shift plan.
    """
    command = discover_native_worker_command()
    if command is None:
        return None
    payload: dict[str, Any] = {"clips": list(clips or []), "mode": str(mode or "precision_trim")}
    if clip_index is not None:
        payload["clip_index"] = int(clip_index)
    elif clip_id is not None:
        payload["clip_id"] = clip_id
    else:
        return None
    for key, value in params.items():
        if value is not None:
            payload[key] = value
    try:
        result = _native_worker_request(command, "timeline_trim_plan", payload, timeout_s=5.0)
        return dict(result) if isinstance(result, dict) else None
    except Exception:
        return None


def native_audio_waveform(
    path: Path | str,
    *,
    ffmpeg_path: str | None = None,
    sample_rate: int = 8000,
    buckets_per_sec: int = 40,
):
    command = discover_native_worker_command()
    if command is None:
        return None
    params: dict[str, Any] = {
        "path": str(path),
        "sample_rate": int(sample_rate),
        "buckets_per_sec": int(buckets_per_sec),
    }
    if ffmpeg_path:
        params["ffmpeg_path"] = str(ffmpeg_path)
    try:
        result = _native_worker_request(command, "audio_waveform", params, timeout_s=120.0)
        if not isinstance(result, dict):
            return None
        left = result.get("left", [])
        right = result.get("right", [])
        if not isinstance(left, list) or not isinstance(right, list):
            return None
        import numpy as np

        n = min(len(left), len(right))
        if n <= 0:
            return None
        return np.stack([
            np.asarray(left[:n], dtype=np.float32),
            np.asarray(right[:n], dtype=np.float32),
        ]).astype(np.float32)
    except Exception:
        return None


def native_audio_spectrum(
    path: Path | str,
    *,
    ffmpeg_path: str | None = None,
    sample_rate: int = 44100,
    samples: int = 8192,
    bins: int = 64,
):
    command = discover_native_worker_command()
    if command is None:
        return None
    params: dict[str, Any] = {
        "path": str(path),
        "sample_rate": int(sample_rate),
        "samples": int(samples),
        "bins": int(bins),
    }
    if ffmpeg_path:
        params["ffmpeg_path"] = str(ffmpeg_path)
    try:
        result = _native_worker_request(command, "audio_spectrum", params, timeout_s=120.0)
        if not isinstance(result, dict):
            return None
        values = result.get("bins", [])
        if not isinstance(values, list) or not values:
            return None
        import numpy as np

        return np.asarray(values, dtype=np.float32)
    except Exception:
        return None


def native_validate_golden_fixture(
    path: Path | str,
    *,
    expected_sha256: str | None = None,
    min_size: int = 1,
) -> dict[str, Any] | None:
    command = discover_native_worker_command()
    if command is None:
        return None
    try:
        contract = NativeWorkerFileContract.input_file(path, role="golden_fixture")
        _validate_file_contract(contract)
        params: dict[str, Any] = {
            "path": str(path),
            "min_size": int(min_size),
            "files": [contract.to_dict()],
        }
        if expected_sha256:
            params["expected_sha256"] = str(expected_sha256)
        result = _native_worker_request(
            command,
            "validate_golden_fixture",
            params,
            timeout_s=30.0,
        )
        return result if isinstance(result, dict) else None
    except Exception:
        return None


def close_shared_native_worker() -> None:
    """Stop the app-wide native worker process, if one is currently open."""
    global _SHARED_WORKER_CLIENT, _SHARED_WORKER_COMMAND
    with _SHARED_WORKER_LOCK:
        client = _SHARED_WORKER_CLIENT
        _SHARED_WORKER_CLIENT = None
        _SHARED_WORKER_COMMAND = None
    if client is not None:
        client.close()


def _shared_native_worker_enabled() -> bool:
    value = str(os.environ.get(_SHARED_WORKER_ENV, "1")).strip().lower()
    return value not in _SHARED_WORKER_DISABLED


def _native_worker_request(
    command: list[str | Path],
    method: str,
    params: dict[str, Any] | None,
    *,
    timeout_s: float,
    on_event: Callable[[NativeWorkerProgressEvent], None] | None = None,
) -> Any:
    if not _shared_native_worker_enabled():
        with NativeWorkerClient(command, timeout_s=timeout_s) as client:
            return client.request_with_events(method, params, on_event=on_event)

    command_key = tuple(str(part) for part in command)
    with _SHARED_WORKER_LOCK:
        global _SHARED_WORKER_CLIENT, _SHARED_WORKER_COMMAND
        if _SHARED_WORKER_CLIENT is None or _SHARED_WORKER_COMMAND != command_key:
            old_client = _SHARED_WORKER_CLIENT
            _SHARED_WORKER_CLIENT = None
            _SHARED_WORKER_COMMAND = None
            if old_client is not None:
                old_client.close()
            _SHARED_WORKER_CLIENT = NativeWorkerClient(list(command_key), timeout_s=timeout_s)
            _SHARED_WORKER_COMMAND = command_key
        client = _SHARED_WORKER_CLIENT
        if client is None:
            raise NativeWorkerError("native worker did not start")
        old_timeout = client._timeout_s
        client._timeout_s = float(timeout_s)
        try:
            return client.request_with_events(method, params, on_event=on_event)
        except Exception:
            if _SHARED_WORKER_CLIENT is client:
                _SHARED_WORKER_CLIENT = None
                _SHARED_WORKER_COMMAND = None
            client.close()
            raise
        finally:
            if _SHARED_WORKER_CLIENT is client:
                client._timeout_s = old_timeout


atexit.register(close_shared_native_worker)


def _command_from_env(value: str) -> list[str]:
    if os.path.exists(value):
        return [value]
    import shlex

    return shlex.split(value, posix=(sys.platform != "win32"))


def _validate_file_contract(contract: NativeWorkerFileContract) -> None:
    path = Path(contract.path)
    if contract.must_exist and not path.exists():
        raise NativeWorkerError(
            f"native worker {contract.role} does not exist: {path}",
            code="file_missing",
            details={"path": str(path), "role": contract.role},
        )
    if contract.kind == "directory":
        path.mkdir(parents=True, exist_ok=True)


def _read_available_stderr(proc: subprocess.Popen[str]) -> str:
    if proc.stderr is None:
        return ""
    try:
        return proc.stderr.read()[:2000]
    except Exception:
        return ""


def _readline_with_timeout(stream, timeout_s: float) -> str:
    out: "queue.Queue[str]" = queue.Queue(maxsize=1)

    def _reader() -> None:
        try:
            out.put(stream.readline())
        except Exception:
            out.put("")

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    try:
        return out.get(timeout=max(0.1, float(timeout_s)))
    except queue.Empty as exc:
        raise NativeWorkerError("native worker response timed out") from exc

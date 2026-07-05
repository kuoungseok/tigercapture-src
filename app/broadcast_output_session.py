"""Runtime session for Program Output recording and RTMP streaming."""
from __future__ import annotations

from dataclasses import dataclass
import subprocess
import threading
import time
from typing import Any, Callable, Mapping

import numpy as np

from app.broadcast_output import (
    OUTPUT_RTMP,
    LiveTargetProfile,
    build_ffmpeg_broadcast_command,
    live_target_preflight,
    live_target_preset,
    live_target_to_output_profile,
)
from app.broadcast_scene import BroadcastCanvas


PopenFactory = Callable[..., Any]


@dataclass
class BroadcastOutputSessionStatus:
    state: str = "idle"
    target_id: str = ""
    output_kind: str = ""
    command: list[str] | None = None
    frames_written: int = 0
    bytes_written: int = 0
    started_at: float = 0.0
    stopped_at: float = 0.0
    last_frame_at: float = 0.0
    last_write_ms: float = 0.0
    max_write_ms: float = 0.0
    backpressure_count: int = 0
    write_error_count: int = 0
    retry_count: int = 0
    max_retries: int = 0
    auto_reconnect: bool = False
    last_exit_code: int | None = None
    last_reconnect_at: float = 0.0
    recovery_action: str = ""
    last_error: str = ""
    stderr_tail: str = ""
    platform_error_kind: str = ""
    platform_error_message: str = ""
    manual_output: bool = False

    def to_dict(self) -> dict[str, Any]:
        now = time.time()
        elapsed = max(0.0, (self.stopped_at or now) - self.started_at) if self.started_at else 0.0
        return {
            "schema": "tigerstudio.broadcast.output_session_status.v1",
            "state": self.state,
            "target_id": self.target_id,
            "output_kind": self.output_kind,
            "command": list(self.command or []),
            "frames_written": int(self.frames_written),
            "bytes_written": int(self.bytes_written),
            "started_at": float(self.started_at),
            "stopped_at": float(self.stopped_at),
            "elapsed_seconds": float(elapsed),
            "estimated_fps": float(self.frames_written / elapsed) if elapsed > 0 else 0.0,
            "last_frame_at": float(self.last_frame_at),
            "last_write_ms": float(self.last_write_ms),
            "max_write_ms": float(self.max_write_ms),
            "backpressure_count": int(self.backpressure_count),
            "write_error_count": int(self.write_error_count),
            "retry_count": int(self.retry_count),
            "max_retries": int(self.max_retries),
            "auto_reconnect": bool(self.auto_reconnect),
            "last_exit_code": self.last_exit_code,
            "last_reconnect_at": float(self.last_reconnect_at),
            "recovery_action": self.recovery_action,
            "last_error": self.last_error,
            "stderr_tail": self.stderr_tail,
            "platform_error_kind": self.platform_error_kind,
            "platform_error_message": self.platform_error_message,
            "manual_output": bool(self.manual_output),
            "active": self.state in {"running", "manual_output"},
            "health": self._health(),
        }

    def _health(self) -> str:
        if self.state == "error":
            return "error"
        if self.state == "reconnecting":
            return "reconnecting"
        if self.backpressure_count > 0 or self.write_error_count > 0 or self.retry_count > 0:
            return "degraded"
        if self.state in {"running", "manual_output"}:
            return "ok"
        return "idle"


class BroadcastOutputSession:
    """Start/stop an FFmpeg stdin session fed by Program Output RGB frames.

    The session is UI-neutral. It does not capture frames by itself; callers feed
    already-composited Program Output frames through `write_frame`.
    """

    def __init__(
        self,
        target: LiveTargetProfile | Mapping[str, Any],
        canvas: BroadcastCanvas | Mapping[str, Any],
        *,
        ffmpeg_exe: str | None = None,
        popen_factory: PopenFactory | None = None,
        auto_reconnect: bool | None = None,
        max_retries: int | None = None,
    ) -> None:
        target_payload = dict(target) if isinstance(target, Mapping) else {}
        self.target = target if isinstance(target, LiveTargetProfile) else LiveTargetProfile.from_mapping(target)
        self.canvas = canvas if isinstance(canvas, BroadcastCanvas) else BroadcastCanvas.from_mapping(canvas)
        self.ffmpeg_exe = ffmpeg_exe
        self._popen_factory = popen_factory or subprocess.Popen
        self._process: Any | None = None
        preset = live_target_preset(self.target.target_id)
        default_auto_reconnect = preset.output_kind == OUTPUT_RTMP
        if auto_reconnect is None:
            auto_reconnect = bool(target_payload.get("auto_reconnect", getattr(self.target, "auto_reconnect", default_auto_reconnect)))
        if max_retries is None:
            max_retries = int(target_payload.get("max_retries", getattr(self.target, "max_retries", 3 if auto_reconnect else 0)) or 0)
        self._status = BroadcastOutputSessionStatus(
            state="idle",
            target_id=self.target.target_id,
            output_kind=preset.output_kind,
            auto_reconnect=bool(auto_reconnect),
            max_retries=max(0, int(max_retries)),
        )
        self._preflight: dict[str, Any] = {}
        self._command: list[str] = []
        self._stderr_lock = threading.Lock()
        self._stderr_thread: threading.Thread | None = None

    def preflight(self) -> dict[str, Any]:
        self._preflight = live_target_preflight(self.target, self.canvas, ffmpeg_exe=self.ffmpeg_exe)
        self._command = list(self._preflight.get("command") or [])
        self._status.command = list(self._command)
        return dict(self._preflight)

    def start(self) -> dict[str, Any]:
        if self._status.state in {"running", "manual_output"}:
            return self.status()
        diag = self.preflight()
        if not bool(diag.get("ok")):
            self._status.state = "error"
            self._status.last_error = "; ".join(str(item) for item in (diag.get("errors") or []))
            return self.status()

        preset = live_target_preset(self.target.target_id)
        if not self._command:
            self._status.state = "manual_output"
            self._status.manual_output = True
            self._status.started_at = time.time()
            return self.status()

        self._status.stderr_tail = ""
        self._status.platform_error_kind = ""
        self._status.platform_error_message = ""
        if not self._open_process():
            return self.status()

        self._status.state = "running"
        self._status.manual_output = False
        self._status.output_kind = preset.output_kind
        self._status.started_at = time.time()
        self._status.stopped_at = 0.0
        self._status.last_error = ""
        self._status.recovery_action = ""
        return self.status()

    def write_frame(self, frame: Any) -> dict[str, Any]:
        if self._status.state != "running":
            return self.status()
        try:
            payload = rgb24_frame_bytes(frame, width=self.canvas.width, height=self.canvas.height)
        except Exception as exc:
            self._status.write_error_count += 1
            self._status.state = "error"
            self._status.last_error = str(exc)
            self._status.recovery_action = "drop_frame"
            return self.status()
        if not self._ensure_process_ready():
            return self.status()
        try:
            self._write_payload(payload)
        except Exception as exc:
            self._status.write_error_count += 1
            if self._attempt_reconnect(f"frame write failed: {exc}"):
                try:
                    self._write_payload(payload)
                except Exception as retry_exc:
                    self._status.write_error_count += 1
                    self._status.state = "error"
                    self._set_failure(str(retry_exc), recovery_action="stop_and_check_output_target")
            else:
                self._status.state = "error"
                self._set_failure(str(exc), recovery_action="stop_and_check_output_target")
        return self.status()

    def stop(self, *, timeout_s: float = 3.0) -> dict[str, Any]:
        self._shutdown_process(timeout_s=timeout_s)
        self._process = None
        self._status.state = "stopped"
        self._status.stopped_at = time.time()
        return self.status()

    def status(self) -> dict[str, Any]:
        data = self._status.to_dict()
        if self._preflight:
            data["preflight_ok"] = bool(self._preflight.get("ok"))
            data["warnings"] = list(self._preflight.get("warnings") or [])
            data["errors"] = list(self._preflight.get("errors") or [])
        else:
            data["preflight_ok"] = False
            data["warnings"] = []
            data["errors"] = []
        try:
            from app.broadcast_troubleshooting import build_live_target_troubleshooting

            data["troubleshooting"] = build_live_target_troubleshooting(self.target, data)
        except Exception:
            data["troubleshooting"] = {}
        return data

    def _open_process(self) -> bool:
        actual_profile = live_target_to_output_profile(self.target)
        actual_command = build_ffmpeg_broadcast_command(actual_profile, self.canvas, ffmpeg_exe=self.ffmpeg_exe)
        try:
            self._process = self._popen_factory(
                actual_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._start_stderr_reader()
            return True
        except Exception as exc:
            self._process = None
            self._status.state = "error"
            self._set_failure(str(exc), recovery_action="check_ffmpeg_or_output_target")
            return False

    def _ensure_process_ready(self) -> bool:
        proc = self._process
        if proc is None:
            return self._attempt_reconnect("output process is missing")
        if hasattr(proc, "poll"):
            exit_code = proc.poll()
            if exit_code is not None:
                self._drain_stderr_if_done()
                try:
                    self._status.last_exit_code = int(exit_code)
                except Exception:
                    self._status.last_exit_code = None
                return self._attempt_reconnect(f"output process exited: {exit_code}")
        stdin = getattr(proc, "stdin", None)
        if stdin is None:
            return self._attempt_reconnect("output process stdin is unavailable")
        return True

    def _attempt_reconnect(self, reason: str) -> bool:
        self._set_failure(str(reason or "output process failed"))
        if not self._status.auto_reconnect:
            self._status.state = "error"
            self._status.recovery_action = "stop_and_check_output_target"
            return False
        if int(self._status.retry_count) >= int(self._status.max_retries):
            self._status.state = "error"
            self._status.recovery_action = "retry_limit_reached"
            self._set_failure(self._status.last_error, recovery_action="retry_limit_reached")
            return False
        self._shutdown_process(timeout_s=0.5)
        self._status.state = "reconnecting"
        self._status.retry_count += 1
        self._status.last_reconnect_at = time.time()
        if not self._open_process():
            self._status.recovery_action = "reconnect_failed"
            return False
        self._status.state = "running"
        self._status.recovery_action = "reconnected"
        return True

    def _write_payload(self, payload: bytes) -> None:
        proc = self._process
        stdin = getattr(proc, "stdin", None) if proc is not None else None
        if stdin is None:
            raise RuntimeError("output process stdin is unavailable")
        started = time.perf_counter()
        stdin.write(payload)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._status.frames_written += 1
        self._status.bytes_written += len(payload)
        self._status.last_frame_at = time.time()
        self._status.last_write_ms = elapsed_ms
        self._status.max_write_ms = max(float(self._status.max_write_ms), float(elapsed_ms))
        if elapsed_ms > (1000.0 / max(1.0, float(self.canvas.fps))) * 2.0:
            self._status.backpressure_count += 1

    def _close_process_stdin(self) -> None:
        proc = self._process
        try:
            stdin = getattr(proc, "stdin", None) if proc is not None else None
            if stdin is not None:
                stdin.close()
        except Exception:
            pass

    def _shutdown_process(self, *, timeout_s: float = 1.0) -> None:
        proc = self._process
        if proc is None:
            return
        self._close_process_stdin()
        try:
            if hasattr(proc, "poll") and proc.poll() is not None:
                self._drain_stderr_if_done()
                return
        except Exception:
            pass
        try:
            proc.wait(timeout=max(0.1, float(timeout_s)))
            return
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=0.5)
            return
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass

    def _start_stderr_reader(self) -> None:
        proc = self._process
        stderr = getattr(proc, "stderr", None) if proc is not None else None
        if stderr is None:
            return

        def _reader() -> None:
            while True:
                try:
                    line = stderr.readline()
                except Exception:
                    break
                if not line:
                    break
                self._append_stderr(line)

        thread = threading.Thread(target=_reader, name="BroadcastOutputSession.stderr", daemon=True)
        self._stderr_thread = thread
        thread.start()

    def _append_stderr(self, line: bytes | str) -> None:
        if isinstance(line, bytes):
            text = line.decode("utf-8", errors="replace")
        else:
            text = str(line)
        if not text:
            return
        text = self._redact_stderr(text)
        with self._stderr_lock:
            tail = (self._status.stderr_tail or "") + text
            self._status.stderr_tail = tail[-4000:]

    def _drain_stderr_if_done(self) -> None:
        proc = self._process
        if proc is None:
            return
        try:
            if hasattr(proc, "poll") and proc.poll() is None:
                return
        except Exception:
            return
        stderr = getattr(proc, "stderr", None)
        if stderr is None:
            return
        try:
            rest = stderr.read()
        except Exception:
            return
        if rest:
            self._append_stderr(rest)

    def _set_failure(self, reason: str, *, recovery_action: str = "") -> None:
        stderr_tail = self._status.stderr_tail or ""
        kind, message = classify_broadcast_ffmpeg_error(stderr_tail, fallback=str(reason or "output failed"))
        self._status.last_error = message
        self._status.platform_error_kind = kind
        self._status.platform_error_message = message
        if recovery_action:
            self._status.recovery_action = recovery_action

    def _redact_stderr(self, text: str) -> str:
        value = str(text or "")
        secret = str(getattr(self.target, "stream_key", "") or "")
        if secret:
            value = value.replace(secret, "<stream_key>")
        return value


def classify_broadcast_ffmpeg_error(stderr_text: str, *, fallback: str = "") -> tuple[str, str]:
    """Map common FFmpeg/RTMP stderr tails to operator-facing messages."""
    text = str(stderr_text or "")
    folded = text.casefold()
    fallback_text = str(fallback or "Live output failed")
    if not folded:
        return "unknown", fallback_text
    if any(token in folded for token in ("401", "403", "unauthorized", "forbidden", "authentication failed", "auth failed")):
        return (
            "platform_auth",
            "Platform rejected the stream. Check the stream key, account permissions, and whether the live event is active.",
        )
    if any(token in folded for token in ("invalid stream key", "stream key", "invalid key")):
        return (
            "stream_key",
            "The stream key appears to be invalid. Re-enter the platform-issued stream key for this session.",
        )
    if any(token in folded for token in ("connection refused", "actively refused")):
        return (
            "connection_refused",
            "The live server refused the connection. Check the RTMP/RTMPS server URL and whether the service is accepting ingest.",
        )
    if any(token in folded for token in ("timed out", "timeout", "i/o error", "network is unreachable", "no route to host")):
        return (
            "network",
            "Network connection to the live server failed or timed out. Check connectivity and the selected ingest server.",
        )
    if any(token in folded for token in ("server returned", "http error", "error 404", "404 not found")):
        return (
            "server_url",
            "The live server URL looks wrong or the platform endpoint is unavailable. Check the RTMP/RTMPS URL.",
        )
    if any(token in folded for token in ("broken pipe", "connection reset", "reset by peer", "end of file")):
        return (
            "stream_closed",
            "The platform closed the stream connection. Check stream key status, platform dashboard errors, and network stability.",
        )
    if any(token in folded for token in ("unknown encoder", "encoder not found", "invalid argument")):
        return (
            "ffmpeg_config",
            "FFmpeg rejected the output settings. Check encoder, bitrate, audio source, and target format settings.",
        )
    tail = " ".join(text.strip().split())
    if tail:
        return "ffmpeg", tail[-500:]
    return "unknown", fallback_text


def rgb24_frame_bytes(frame: Any, *, width: int, height: int) -> bytes:
    """Return an RGB24 byte payload resized to the broadcast canvas if needed."""
    expected = int(width) * int(height) * 3
    if isinstance(frame, (bytes, bytearray, memoryview)):
        payload = bytes(frame)
        if len(payload) != expected:
            raise ValueError(f"rgb24 payload size mismatch: expected {expected}, got {len(payload)}")
        return payload

    arr = _frame_to_rgb_array(frame)
    if arr.shape[1] != int(width) or arr.shape[0] != int(height):
        arr = _resize_rgb_array(arr, int(width), int(height))
    return np.ascontiguousarray(arr).tobytes()


def _frame_to_rgb_array(frame: Any) -> np.ndarray:
    try:
        if hasattr(frame, "convert") and hasattr(frame, "size"):
            return np.asarray(frame.convert("RGB"), dtype=np.uint8)
    except Exception:
        pass
    arr = np.asarray(frame)
    if arr.ndim == 2:
        arr = np.repeat(arr[:, :, None], 3, axis=2)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("frame must be RGB/RGBA array-like data")
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(arr[:, :, :3])


def _resize_rgb_array(arr: np.ndarray, width: int, height: int) -> np.ndarray:
    try:
        from PIL import Image

        image = Image.fromarray(np.ascontiguousarray(arr[:, :, :3]), "RGB")
        return np.asarray(image.resize((int(width), int(height)), Image.Resampling.BILINEAR), dtype=np.uint8)
    except Exception as exc:
        raise ValueError(
            f"frame size {arr.shape[1]}x{arr.shape[0]} does not match broadcast canvas {width}x{height}"
        ) from exc

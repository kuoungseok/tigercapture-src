"""Runtime session for optional Program Output virtual-camera device output."""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Mapping

import numpy as np

from app.broadcast_output_session import rgb24_frame_bytes
from app.broadcast_scene import BroadcastCanvas


VIRTUAL_CAMERA_DEVICE_SESSION_SCHEMA = "tigerstudio.broadcast.virtual_camera_device_session.v1"

CameraFactory = Callable[..., Any]


@dataclass
class BroadcastVirtualCameraDeviceStatus:
    state: str = "idle"
    backend: str = "pyvirtualcam"
    device: str = ""
    frames_written: int = 0
    bytes_written: int = 0
    started_at: float = 0.0
    stopped_at: float = 0.0
    last_frame_at: float = 0.0
    last_write_ms: float = 0.0
    max_write_ms: float = 0.0
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        now = time.time()
        elapsed = max(0.0, (self.stopped_at or now) - self.started_at) if self.started_at else 0.0
        return {
            "schema": VIRTUAL_CAMERA_DEVICE_SESSION_SCHEMA,
            "state": self.state,
            "backend": self.backend,
            "device": self.device,
            "frames_written": int(self.frames_written),
            "bytes_written": int(self.bytes_written),
            "started_at": float(self.started_at),
            "stopped_at": float(self.stopped_at),
            "elapsed_seconds": float(elapsed),
            "estimated_fps": float(self.frames_written / elapsed) if elapsed > 0 else 0.0,
            "last_frame_at": float(self.last_frame_at),
            "last_write_ms": float(self.last_write_ms),
            "max_write_ms": float(self.max_write_ms),
            "last_error": self.last_error,
            "active": self.state == "running",
            "health": "error" if self.state == "error" else ("ok" if self.state == "running" else "idle"),
        }


class BroadcastVirtualCameraDeviceSession:
    """Feed already-composited Program Output frames to an installed camera backend.

    This session never installs a driver. By default it lazy-imports
    ``pyvirtualcam`` only when ``start()`` is called. Tests can inject a
    ``camera_factory``.
    """

    def __init__(
        self,
        payload: Mapping[str, Any] | None,
        canvas: BroadcastCanvas | Mapping[str, Any],
        *,
        camera_factory: CameraFactory | None = None,
    ) -> None:
        self.payload = dict(payload or {})
        self.canvas = canvas if isinstance(canvas, BroadcastCanvas) else BroadcastCanvas.from_mapping(canvas)
        self._camera_factory = camera_factory
        self._camera: Any | None = None
        self._status = BroadcastVirtualCameraDeviceStatus(
            device=str(self.payload.get("device") or self.payload.get("device_name") or ""),
        )

    def preflight(self) -> dict[str, Any]:
        available = self._camera_factory is not None
        if not available:
            try:
                import pyvirtualcam  # type: ignore  # noqa: F401

                available = True
            except Exception:
                available = False
        return {
            "schema": "tigerstudio.broadcast.virtual_camera_device_preflight.v1",
            "ok": bool(available),
            "backend": "pyvirtualcam",
            "device": self._status.device,
            "width": int(self.canvas.width),
            "height": int(self.canvas.height),
            "fps": float(self.canvas.fps),
            "install_policy": "user_approved_only",
            "errors": [] if available else ["pyvirtualcam_unavailable"],
            "warnings": [] if available else ["Use Program Output window share until a virtual-camera backend is installed."],
        }

    def start(self) -> dict[str, Any]:
        if self._status.state == "running":
            return self.status()
        preflight = self.preflight()
        if not bool(preflight.get("ok")):
            self._status.state = "error"
            self._status.last_error = "; ".join(str(item) for item in preflight.get("errors") or [])
            return self.status()
        try:
            factory = self._camera_factory or _load_pyvirtualcam_camera_factory()
            kwargs = {
                "width": int(self.canvas.width),
                "height": int(self.canvas.height),
                "fps": float(self.canvas.fps),
            }
            if self._status.device:
                kwargs["device"] = self._status.device
            try:
                kwargs["print_fps"] = False
                self._camera = factory(**kwargs)
            except TypeError:
                kwargs.pop("print_fps", None)
                self._camera = factory(**kwargs)
            self._status.state = "running"
            self._status.started_at = time.time()
            self._status.stopped_at = 0.0
            self._status.last_error = ""
        except Exception as exc:
            self._camera = None
            self._status.state = "error"
            self._status.last_error = str(exc)
        return self.status()

    def write_frame(self, frame: Any) -> dict[str, Any]:
        if self._status.state != "running" or self._camera is None:
            return self.status()
        try:
            payload = rgb24_frame_bytes(frame, width=self.canvas.width, height=self.canvas.height)
            arr = np.frombuffer(payload, dtype=np.uint8).reshape((int(self.canvas.height), int(self.canvas.width), 3))
            started = time.perf_counter()
            self._camera.send(np.ascontiguousarray(arr))
            sleep_until_next_frame = getattr(self._camera, "sleep_until_next_frame", None)
            if callable(sleep_until_next_frame):
                sleep_until_next_frame()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self._status.frames_written += 1
            self._status.bytes_written += len(payload)
            self._status.last_frame_at = time.time()
            self._status.last_write_ms = elapsed_ms
            self._status.max_write_ms = max(float(self._status.max_write_ms), float(elapsed_ms))
        except Exception as exc:
            self._status.state = "error"
            self._status.last_error = str(exc)
        return self.status()

    def stop(self) -> dict[str, Any]:
        camera = self._camera
        self._camera = None
        try:
            close = getattr(camera, "close", None)
            if callable(close):
                close()
        except Exception:
            pass
        self._status.state = "stopped"
        self._status.stopped_at = time.time()
        return self.status()

    def status(self) -> dict[str, Any]:
        return self._status.to_dict()


def _load_pyvirtualcam_camera_factory() -> CameraFactory:
    import pyvirtualcam  # type: ignore

    return pyvirtualcam.Camera

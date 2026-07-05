"""Drive VSeeFace's bundled OpenSeeFace tracker from a video file.

This module is UI-neutral. It does not embed VSeeFace; it only feeds raw RGB
frames into the external ``facetracker.exe`` process and records diagnostics.
"""
from __future__ import annotations

from pathlib import Path
import socket
import subprocess
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FACETRACKER = (
    ROOT
    / "debugCapture"
    / "vseeface"
    / "VSeeFace"
    / "VSeeFace_Data"
    / "StreamingAssets"
    / "Binary"
    / "facetracker.exe"
)


def run_video_source(
    *,
    video: Path,
    facetracker: Path = DEFAULT_FACETRACKER,
    host: str = "127.0.0.1",
    port: int = 39540,
    width: int = 640,
    height: int = 360,
    fps: float = 24.0,
    duration_seconds: float = 5.0,
    model: int = 3,
    detection_threshold: float = 0.35,
    try_hard: bool = False,
    crop: tuple[float, float, float, float] | None = None,
    realtime: bool = False,
    shutdown_timeout: float = 2.0,
    probe_udp: bool = False,
    log_data: Path | None = None,
    log_output: Path | None = None,
) -> dict:
    """Feed ``video`` frames to facetracker and return a diagnostics report."""
    video = video.resolve()
    facetracker = facetracker.resolve()
    log_data = (log_data or ROOT / "debugCapture" / "openseeface_video_source_data.csv").resolve()
    log_output = (log_output or ROOT / "debugCapture" / "openseeface_video_source_output.txt").resolve()
    width = max(1, int(width))
    height = max(1, int(height))
    fps = max(1.0, float(fps))
    duration_seconds = max(0.1, float(duration_seconds))
    detection_threshold = max(0.0, min(1.0, float(detection_threshold)))
    shutdown_timeout = max(0.1, float(shutdown_timeout))
    report = {
        "schema": "tigerstudio.vtuber.openseeface_video_source.v1",
        "ok": False,
        "video": str(video),
        "facetracker": str(facetracker),
        "endpoint": {"host": host, "port": int(port)},
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": duration_seconds,
        "detection_threshold": detection_threshold,
        "try_hard": bool(try_hard),
        "crop": list(crop) if crop else None,
        "frames_written": 0,
        "udp_packets": 0,
        "udp_bytes": 0,
        "log_data": str(log_data),
        "log_output": str(log_output),
        "tracking_rows": 0,
        "errors": [],
        "warnings": [],
    }
    if not video.is_file():
        report["errors"].append("video_missing")
        return report
    if not facetracker.is_file():
        report["errors"].append("facetracker_missing")
        return report
    try:
        import cv2  # type: ignore
    except Exception as exc:
        report["errors"].append(f"opencv_unavailable:{exc}")
        return report

    listener: _UdpProbe | None = None
    if probe_udp:
        listener = _UdpProbe(host, int(port))
        try:
            listener.start()
        except OSError as exc:
            report["errors"].append(f"udp_probe_bind_failed:{exc}")
            listener = None

    command = build_facetracker_command(
        facetracker=facetracker,
        host=host,
        port=port,
        width=width,
        height=height,
        fps=fps,
        model=model,
        detection_threshold=detection_threshold,
        try_hard=try_hard,
        log_data=log_data,
        log_output=log_output,
    )
    log_data.parent.mkdir(parents=True, exist_ok=True)
    log_output.parent.mkdir(parents=True, exist_ok=True)
    for log_path in (log_data, log_output):
        try:
            log_path.unlink()
        except FileNotFoundError:
            pass

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        report["errors"].append("opencv_video_open_failed")
        if listener:
            listener.stop()
        return report

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        cwd=str(facetracker.parent),
    )
    output = b""
    max_frames = max(1, int(round(duration_seconds * fps)))
    frame_period = 1.0 / fps
    start = time.monotonic()
    try:
        for _ in range(max_frames):
            ok, frame = cap.read()
            if not ok:
                break
            if crop:
                frame = _crop_frame(frame, crop)
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if process.stdin is None:
                break
            try:
                process.stdin.write(rgb.tobytes())
            except BrokenPipeError:
                report["errors"].append("facetracker_broken_pipe")
                break
            report["frames_written"] += 1
            if realtime:
                target = start + report["frames_written"] * frame_period
                delay = target - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
        if process.stdin is not None:
            try:
                process.stdin.close()
            except BrokenPipeError:
                if "facetracker_broken_pipe" not in report["errors"]:
                    report["errors"].append("facetracker_broken_pipe")
        try:
            process.wait(timeout=shutdown_timeout)
            output = _read_tail_bytes(log_output)
        except subprocess.TimeoutExpired:
            _kill_process_tree(process.pid)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            output = _read_tail_bytes(log_output)
            report["warnings"].append("facetracker_stopped_after_feed")
    finally:
        cap.release()
        if listener:
            listener.stop()

    report["facetracker_returncode"] = process.returncode
    report["facetracker_output_tail"] = output.decode("utf-8", errors="replace")[-2000:] if output else ""
    if listener:
        report["udp_packets"] = listener.packets
        report["udp_bytes"] = listener.bytes_total
    report["tracking_rows"] = _count_tracking_rows(log_data)
    report["ok"] = (
        report["frames_written"] > 0
        and report["tracking_rows"] > 0
        and not any(str(err).endswith("_failed") for err in report["errors"])
    )
    return report


def build_facetracker_command(
    *,
    facetracker: Path,
    host: str,
    port: int,
    width: int,
    height: int,
    fps: float,
    model: int,
    detection_threshold: float,
    try_hard: bool,
    log_data: Path,
    log_output: Path,
) -> list[str]:
    return [
        str(facetracker),
        "--raw-rgb",
        "1",
        "--width",
        str(int(width)),
        "--height",
        str(int(height)),
        "--fps",
        str(max(1, int(round(float(fps))))),
        "--ip",
        str(host),
        "--port",
        str(int(port)),
        "--model",
        str(int(model)),
        "--detection-threshold",
        str(float(detection_threshold)),
        "--try-hard",
        "1" if try_hard else "0",
        "--silent",
        "0",
        "--log-data",
        str(log_data),
        "--log-output",
        str(log_output),
    ]


def parse_crop(value: str) -> tuple[float, float, float, float] | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = [float(part.strip()) for part in text.split(",")]
    if len(parts) != 4:
        raise ValueError("crop must be x,y,w,h")
    x, y, w, h = parts
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    w = max(0.01, min(1.0 - x, w))
    h = max(0.01, min(1.0 - y, h))
    return x, y, w, h


def _crop_frame(frame, crop: tuple[float, float, float, float]):
    frame_height, frame_width = frame.shape[:2]
    x, y, w, h = crop
    left = int(frame_width * x)
    top = int(frame_height * y)
    right = max(left + 1, int(frame_width * (x + w)))
    bottom = max(top + 1, int(frame_height * (y + h)))
    return frame[top:bottom, left:right]


def _count_tracking_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        line_count = sum(1 for _line in path.open("r", encoding="utf-8", errors="replace"))
    except OSError:
        return 0
    return max(0, line_count - 1)


def _read_tail_bytes(path: Path, limit: int = 4096) -> bytes:
    if not path.is_file():
        return b""
    data = path.read_bytes()
    return data[-limit:]


def _kill_process_tree(pid: int) -> None:
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True, text=True, timeout=10, check=False)
    else:
        try:
            import os
            import signal

            os.kill(int(pid), signal.SIGKILL)
        except OSError:
            pass


class _UdpProbe:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.packets = 0
        self.bytes_total = 0
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.settimeout(0.2)
        self._sock = sock
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._sock:
            self._sock.close()

    def _run(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                data, _addr = self._sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            self.packets += 1
            self.bytes_total += len(data)

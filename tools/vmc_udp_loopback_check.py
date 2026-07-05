"""Loopback-check the video-to-VMC bridge without launching VSeeFace.

This starts a local UDP listener, extracts motion from a face video, sends the
generated VMC/OSC packets to that listener, and writes a small JSON report.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.video_face_driver import FaceMotionTuning, VideoFaceMotionExtractor, VideoFaceMotionResult, apply_motion_tuning
from app.vtuber.vmc_protocol import (
    VMC_DEFAULT_HOST,
    VMC_VSEEFACE_RECEIVER_PORT,
    VmcEndpoint,
    build_vmc_messages_from_face_frame,
    parse_osc_message,
    send_vmc_messages,
    summarize_vmc_messages,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Loopback-check VMC/OSC UDP packets generated from a face video.")
    parser.add_argument("--video", required=True, help="Face video file to analyze.")
    parser.add_argument("--host", default=VMC_DEFAULT_HOST, help="UDP host to bind/send.")
    parser.add_argument("--port", type=int, default=VMC_VSEEFACE_RECEIVER_PORT, help="UDP port to bind/send.")
    parser.add_argument("--fps", type=float, default=15.0, help="Maximum extracted/sent motion FPS.")
    parser.add_argument("--backend", choices=["auto", "mediapipe_tasks", "mediapipe", "opencv"], default="auto")
    parser.add_argument("--face-landmarker-model", default="")
    parser.add_argument("--duration-seconds", type=float, default=3.0)
    parser.add_argument("--calibrate-seconds", type=float, default=0.8)
    parser.add_argument("--smoothing", type=float, default=0.35)
    parser.add_argument("--no-blink-calibration", action="store_true", help="Disable neutral blink baseline calibration.")
    parser.add_argument("--calibrate-mouth", action="store_true", help="Subtract neutral mouth baseline before sending mouth blendshapes.")
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "vmc_udp_loopback_check.json"))
    args = parser.parse_args(argv)

    report = run_loopback_check(
        video=args.video,
        host=args.host,
        port=args.port,
        fps=args.fps,
        backend=args.backend,
        face_landmarker_model=args.face_landmarker_model or None,
        duration_seconds=args.duration_seconds,
        calibrate_seconds=args.calibrate_seconds,
        smoothing=args.smoothing,
        calibrate_blinks=not bool(args.no_blink_calibration),
        calibrate_mouth=bool(args.calibrate_mouth),
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": report["ok"],
        "frame_count": report["frame_count"],
        "sent_packets": report["sent_packets"],
        "received_packets": report["received_packets"],
        "selected_backend": report["diagnostics"].get("selected_backend"),
        "report": str(out),
    }, ensure_ascii=False))
    return 0 if report["ok"] else 2


def run_loopback_check(
    *,
    video: str,
    host: str = VMC_DEFAULT_HOST,
    port: int = VMC_VSEEFACE_RECEIVER_PORT,
    fps: float = 15.0,
    backend: str = "auto",
    face_landmarker_model: str | None = None,
    duration_seconds: float = 3.0,
    calibrate_seconds: float = 0.8,
    smoothing: float = 0.35,
    calibrate_blinks: bool = True,
    calibrate_mouth: bool = False,
) -> dict:
    endpoint = VmcEndpoint(host=host, port=int(port))
    listener = _UdpCapture(endpoint)
    listener.start()
    if listener.bind_error:
        return {
            "schema": "tigerstudio.vtuber.vmc_udp_loopback.v1",
            "ok": False,
            "video": str(video),
            "endpoint": endpoint.to_dict(),
            "frame_count": 0,
            "sent_packets": 0,
            "received_packets": 0,
            "received_bytes": 0,
            "sample_packet_hex": "",
            "decoded_summary": summarize_vmc_messages([]),
            "decode_errors": [],
            "diagnostics": {"errors": ["udp_loopback_bind_failed"], "bind_error": listener.bind_error},
            "errors": ["udp_loopback_bind_failed"],
        }
    time.sleep(0.05)

    extractor = VideoFaceMotionExtractor(
        max_fps=fps,
        backend=backend,
        face_landmarker_model=face_landmarker_model,
    )
    result = extractor.extract(video, duration_seconds=duration_seconds)
    tuning = FaceMotionTuning(
        smoothing=smoothing,
        calibrate_ms=max(0, int(float(calibrate_seconds) * 1000.0)),
        calibrate_blinks=bool(calibrate_blinks),
        calibrate_mouth=bool(calibrate_mouth),
    )
    if result.frames:
        diagnostics = dict(result.diagnostics)
        diagnostics["tuning"] = tuning.to_dict()
        result = VideoFaceMotionResult(result.ok, apply_motion_tuning(result.frames, tuning), diagnostics)

    sent_packets = 0
    if result.ok:
        for frame in result.frames:
            sent_packets += send_vmc_messages(build_vmc_messages_from_face_frame(frame), endpoint)

    time.sleep(0.25)
    listener.stop()

    report = {
        "schema": "tigerstudio.vtuber.vmc_udp_loopback.v1",
        "ok": bool(result.ok and sent_packets > 0 and listener.packet_count > 0),
        "video": str(video),
        "endpoint": endpoint.to_dict(),
        "frame_count": len(result.frames),
        "sent_packets": sent_packets,
        "received_packets": listener.packet_count,
        "received_bytes": listener.byte_count,
        "sample_packet_hex": listener.sample_packet_hex,
        "decoded_summary": summarize_vmc_messages(listener.decoded_messages),
        "decode_errors": listener.decode_errors[:10],
        "diagnostics": result.diagnostics,
        "errors": [] if result.ok else list(result.diagnostics.get("errors") or []),
    }
    if sent_packets and not listener.packet_count:
        report["errors"].append("udp_loopback_no_packets_received")
    if listener.decode_errors:
        report["errors"].append("udp_loopback_decode_errors")
    return report


class _UdpCapture:
    def __init__(self, endpoint: VmcEndpoint) -> None:
        self._endpoint = endpoint
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self.bind_error = ""
        self.packet_count = 0
        self.byte_count = 0
        self.sample_packet_hex = ""
        self.decoded_messages = []
        self.decode_errors: list[str] = []

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="vmc-udp-loopback", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=1.0)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            try:
                sock.bind((self._endpoint.host, self._endpoint.port))
            except OSError as exc:
                self.bind_error = str(exc)
                self._ready.set()
                return
            self._ready.set()
            sock.settimeout(0.05)
            while not self._stop.is_set():
                try:
                    data, _address = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                self.packet_count += 1
                self.byte_count += len(data)
                if not self.sample_packet_hex:
                    self.sample_packet_hex = data[:32].hex()
                try:
                    self.decoded_messages.append(parse_osc_message(data))
                except Exception as exc:
                    self.decode_errors.append(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())

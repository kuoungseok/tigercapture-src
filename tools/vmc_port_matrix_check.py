"""Check the video-to-VMC bridge against common VSeeFace UDP ports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vmc_protocol import VMC_DEFAULT_HOST, VMC_VSEEFACE_RECEIVER_PORT, VMC_VSEEFACE_SENDER_PORT
from tools.vmc_udp_loopback_check import run_loopback_check


MATRIX_SCHEMA = "tigerstudio.vtuber.vmc_port_matrix.v1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run VMC/OSC loopback checks on multiple VSeeFace UDP ports.")
    parser.add_argument("--video", required=True, help="Face video file to analyze.")
    parser.add_argument("--host", default=VMC_DEFAULT_HOST, help="UDP host to bind/send.")
    parser.add_argument("--ports", default=f"{VMC_VSEEFACE_RECEIVER_PORT},{VMC_VSEEFACE_SENDER_PORT}")
    parser.add_argument("--fps", type=float, default=15.0, help="Maximum extracted/sent motion FPS.")
    parser.add_argument("--backend", choices=["auto", "mediapipe_tasks", "mediapipe", "opencv"], default="auto")
    parser.add_argument("--face-landmarker-model", default="")
    parser.add_argument("--duration-seconds", type=float, default=3.0)
    parser.add_argument("--calibrate-seconds", type=float, default=0.8)
    parser.add_argument("--smoothing", type=float, default=0.35)
    parser.add_argument("--no-blink-calibration", action="store_true", help="Disable neutral blink baseline calibration.")
    parser.add_argument("--calibrate-mouth", action="store_true", help="Subtract neutral mouth baseline before sending mouth blendshapes.")
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "vmc_port_matrix_check.json"))
    args = parser.parse_args(argv)

    matrix = run_port_matrix_check(
        video=args.video,
        host=args.host,
        ports=parse_ports(args.ports),
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
    out.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": matrix["ok"],
        "ports": matrix["ports"],
        "results": matrix["results"],
        "report": str(out),
    }, ensure_ascii=False))
    return 0 if matrix["ok"] else 2


def parse_ports(value: str) -> list[int]:
    ports: list[int] = []
    for raw in str(value).split(","):
        raw = raw.strip()
        if not raw:
            continue
        port = int(raw)
        if port < 1 or port > 65535:
            raise ValueError(f"UDP port out of range: {port}")
        if port not in ports:
            ports.append(port)
    if not ports:
        raise ValueError("at least one UDP port is required")
    return ports


def run_port_matrix_check(
    *,
    video: str,
    host: str = VMC_DEFAULT_HOST,
    ports: list[int] | tuple[int, ...] = (VMC_VSEEFACE_RECEIVER_PORT, VMC_VSEEFACE_SENDER_PORT),
    fps: float = 15.0,
    backend: str = "auto",
    face_landmarker_model: str | None = None,
    duration_seconds: float = 3.0,
    calibrate_seconds: float = 0.8,
    smoothing: float = 0.35,
    calibrate_blinks: bool = True,
    calibrate_mouth: bool = False,
) -> dict:
    reports = []
    for port in ports:
        reports.append(
            run_loopback_check(
                video=video,
                host=host,
                port=int(port),
                fps=fps,
                backend=backend,
                face_landmarker_model=face_landmarker_model,
                duration_seconds=duration_seconds,
                calibrate_seconds=calibrate_seconds,
                smoothing=smoothing,
                calibrate_blinks=calibrate_blinks,
                calibrate_mouth=calibrate_mouth,
            )
        )

    return {
        "schema": MATRIX_SCHEMA,
        "ok": all(bool(report.get("ok")) for report in reports),
        "video": str(video),
        "host": host,
        "ports": [int(port) for port in ports],
        "results": [summarize_report(report) for report in reports],
        "reports": reports,
        "errors": [
            f"port_{report.get('endpoint', {}).get('port')}_failed"
            for report in reports
            if not report.get("ok")
        ],
    }


def summarize_report(report: dict) -> dict:
    decoded = report.get("decoded_summary") if isinstance(report.get("decoded_summary"), dict) else {}
    bones = decoded.get("bones") if isinstance(decoded.get("bones"), dict) else {}
    blends = decoded.get("blends") if isinstance(decoded.get("blends"), dict) else {}
    endpoint = report.get("endpoint") if isinstance(report.get("endpoint"), dict) else {}
    return {
        "port": endpoint.get("port"),
        "ok": bool(report.get("ok")),
        "frame_count": int(report.get("frame_count") or 0),
        "sent_packets": int(report.get("sent_packets") or 0),
        "received_packets": int(report.get("received_packets") or 0),
        "decoded_packets": int(decoded.get("message_count") or 0),
        "head_bone": "Head" in bones,
        "mouth_a": blends.get("A"),
        "backend": report.get("diagnostics", {}).get("selected_backend"),
        "errors": list(report.get("errors") or []),
    }


if __name__ == "__main__":
    raise SystemExit(main())

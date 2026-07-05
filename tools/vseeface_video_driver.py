"""Drive VSeeFace from a face video through VMC/OSC.

Example:
    python tools/vseeface_video_driver.py --video C:/temp/face.mp4 --dry-run
    python tools/vseeface_video_driver.py --video C:/temp/face.mp4 --send
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
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
    send_vmc_messages,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send face-video motion to VSeeFace through VMC/OSC.")
    parser.add_argument("--video", required=True, help="Face video file to analyze.")
    parser.add_argument("--host", default=VMC_DEFAULT_HOST, help="VSeeFace VMC receiver host.")
    parser.add_argument("--port", type=int, default=VMC_VSEEFACE_RECEIVER_PORT, help="VSeeFace VMC receiver port.")
    parser.add_argument("--fps", type=float, default=15.0, help="Maximum extracted/sent motion FPS.")
    parser.add_argument("--backend", choices=["auto", "mediapipe_tasks", "mediapipe", "opencv"], default="auto", help="Face tracking backend.")
    parser.add_argument("--face-landmarker-model", default="", help="Optional MediaPipe Face Landmarker .task model path.")
    parser.add_argument("--duration-seconds", type=float, default=None, help="Optional maximum input duration.")
    parser.add_argument("--max-frames", type=int, default=None, help="Optional maximum sampled frames.")
    parser.add_argument("--calibrate-seconds", type=float, default=0.8, help="Seconds used as neutral pose calibration.")
    parser.add_argument("--smoothing", type=float, default=0.35, help="Motion smoothing amount, 0 disables smoothing.")
    parser.add_argument("--yaw-scale", type=float, default=1.0, help="Yaw sensitivity multiplier.")
    parser.add_argument("--pitch-scale", type=float, default=1.0, help="Pitch sensitivity multiplier.")
    parser.add_argument("--roll-scale", type=float, default=1.0, help="Roll sensitivity multiplier.")
    parser.add_argument("--mouth-scale", type=float, default=1.0, help="Mouth-open sensitivity multiplier.")
    parser.add_argument("--blink-scale", type=float, default=1.0, help="Blink sensitivity multiplier.")
    parser.add_argument("--no-blink-calibration", action="store_true", help="Disable neutral blink baseline calibration.")
    parser.add_argument("--calibrate-mouth", action="store_true", help="Subtract neutral mouth baseline before sending mouth blendshapes.")
    parser.add_argument("--send", action="store_true", help="Send UDP packets to VSeeFace. Without this, only a dry-run report is written.")
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "vtuber_video_driver_report.json"), help="JSON report path.")
    args = parser.parse_args(argv)

    extractor = VideoFaceMotionExtractor(
        max_fps=args.fps,
        backend=args.backend,
        face_landmarker_model=args.face_landmarker_model or None,
    )
    result = extractor.extract(args.video, max_frames=args.max_frames, duration_seconds=args.duration_seconds)
    tuning = FaceMotionTuning(
        yaw_scale=args.yaw_scale,
        pitch_scale=args.pitch_scale,
        roll_scale=args.roll_scale,
        mouth_scale=args.mouth_scale,
        blink_scale=args.blink_scale,
        smoothing=args.smoothing,
        calibrate_ms=max(0, int(float(args.calibrate_seconds) * 1000.0)),
        calibrate_mouth=bool(args.calibrate_mouth),
        calibrate_blinks=not bool(args.no_blink_calibration),
    )
    if result.frames:
        diagnostics = dict(result.diagnostics)
        diagnostics["tuning"] = tuning.to_dict()
        result = VideoFaceMotionResult(result.ok, apply_motion_tuning(result.frames, tuning), diagnostics)
    endpoint = VmcEndpoint(host=args.host, port=args.port)
    report = _build_report(args, endpoint, result)

    if args.send and result.ok:
        report["sent_packets"] = _send_frames_realtime(result.frames, endpoint)
    elif args.send:
        report["sent_packets"] = 0
        report["errors"] = list(report.get("errors") or []) + ["send_skipped_no_motion_frames"]
    else:
        report["sent_packets"] = 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": bool(report["ok"]),
        "send": bool(args.send),
        "frame_count": int(report["frame_count"]),
        "sent_packets": int(report["sent_packets"]),
        "report": str(out),
        "endpoint": endpoint.to_dict(),
        "selected_backend": report["diagnostics"].get("selected_backend"),
        "face_landmarker_model": report["diagnostics"].get("face_landmarker_model"),
    }, ensure_ascii=False))
    return 0 if report["ok"] else 2


def _send_frames_realtime(frames, endpoint: VmcEndpoint) -> int:
    if not frames:
        return 0
    packet_count = 0
    start_clock = time.perf_counter()
    start_ms = frames[0].time_ms
    for frame in frames:
        target_elapsed = max(0.0, (frame.time_ms - start_ms) / 1000.0)
        sleep_for = target_elapsed - (time.perf_counter() - start_clock)
        if sleep_for > 0:
            time.sleep(sleep_for)
        packet_count += send_vmc_messages(build_vmc_messages_from_face_frame(frame), endpoint)
    return packet_count


def _build_report(args, endpoint: VmcEndpoint, result) -> dict:
    first = result.frames[0].to_dict() if result.frames else None
    last = result.frames[-1].to_dict() if result.frames else None
    sample_messages = [
        message.to_dict()
        for message in (build_vmc_messages_from_face_frame(result.frames[0]) if result.frames else [])
    ]
    return {
        "schema": "tigerstudio.vtuber.video_face_driver.run.v1",
        "ok": bool(result.ok),
        "video": str(args.video),
        "dry_run": not bool(args.send),
        "send": bool(args.send),
        "endpoint": endpoint.to_dict(),
        "frame_count": len(result.frames),
        "first_frame": first,
        "last_frame": last,
        "sample_messages": sample_messages,
        "diagnostics": result.diagnostics,
        "errors": list(result.diagnostics.get("errors") or []),
        "setup": [
            "Open VSeeFace and load a VRM0 avatar.",
            "Enable the VMC protocol receiver in VSeeFace.",
            f"Set the VSeeFace receiver port to {endpoint.port}.",
            "Run this tool again with --send to stream the extracted motion.",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())

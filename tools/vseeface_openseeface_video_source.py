"""CLI wrapper for feeding video into VSeeFace's bundled OpenSeeFace tracker."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.openseeface_video_source import DEFAULT_FACETRACKER, parse_crop, run_video_source



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drive VSeeFace OpenSeeFace tracking from a video file.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--facetracker", default=str(DEFAULT_FACETRACKER))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=39540)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--fps", type=float, default=24.0)
    parser.add_argument("--duration-seconds", type=float, default=5.0)
    parser.add_argument("--model", type=int, default=3)
    parser.add_argument("--detection-threshold", type=float, default=0.35)
    parser.add_argument("--try-hard", action="store_true")
    parser.add_argument("--crop", default="", help="Optional normalized crop: x,y,w,h")
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--shutdown-timeout", type=float, default=2.0)
    parser.add_argument("--probe-udp", action="store_true", help="Bind the same UDP port and count packets for smoke tests.")
    parser.add_argument("--log-data", default=str(ROOT / "debugCapture" / "openseeface_video_source_data.csv"))
    parser.add_argument("--log-output", default=str(ROOT / "debugCapture" / "openseeface_video_source_output.txt"))
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "openseeface_video_source_report.json"))
    args = parser.parse_args(argv)

    report = run_video_source(
        video=Path(args.video),
        facetracker=Path(args.facetracker),
        host=args.host,
        port=args.port,
        width=args.width,
        height=args.height,
        fps=args.fps,
        duration_seconds=args.duration_seconds,
        model=args.model,
        detection_threshold=args.detection_threshold,
        try_hard=bool(args.try_hard),
        crop=parse_crop(args.crop),
        realtime=bool(args.realtime),
        shutdown_timeout=args.shutdown_timeout,
        probe_udp=bool(args.probe_udp),
        log_data=Path(args.log_data),
        log_output=Path(args.log_output),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "frames_written": report["frames_written"],
                "udp_packets": report["udp_packets"],
                "out": str(out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    from app.sdr_hdr_upmap import (
        SDRHDRUpmapProfile,
        sdr_to_hdr_upmap_report,
        write_sdr_to_hdr_upmap_report,
    )

    parser = argparse.ArgumentParser(
        description="Convert an SDR video to an LTX-style scene-linear HDR EXR sequence."
    )
    parser.add_argument("--input", required=True, help="SDR source video path.")
    parser.add_argument("--out-dir", required=True, help="Directory for EXR frames.")
    parser.add_argument("--out", default="", help="Optional JSON report path.")
    parser.add_argument("--run", action="store_true", help="Execute ffmpeg. Default is dry-run.")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--fps", type=float, default=0.0)
    parser.add_argument("--peak-nits", type=int, default=1000)
    parser.add_argument("--exposure-stops", type=float, default=0.0)
    parser.add_argument("--highlight-boost", type=float, default=1.35)
    parser.add_argument("--saturation-boost", type=float, default=1.08)
    parser.add_argument("--curve-gamma", type=float, default=0.85)
    parser.add_argument("--timeout-s", type=int, default=300)
    args = parser.parse_args(argv)

    profile = SDRHDRUpmapProfile(
        peak_nits=args.peak_nits,
        exposure_stops=args.exposure_stops,
        highlight_boost=args.highlight_boost,
        saturation_boost=args.saturation_boost,
        curve_gamma=args.curve_gamma,
        fps=args.fps,
        max_frames=args.max_frames,
    )
    report = sdr_to_hdr_upmap_report(
        args.input,
        args.out_dir,
        profile,
        run=bool(args.run),
        timeout_s=max(10, int(args.timeout_s)),
    )
    if args.out:
        write_sdr_to_hdr_upmap_report(args.out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

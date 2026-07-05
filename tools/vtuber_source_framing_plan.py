"""Write a source-video VTuber framing plan JSON report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.openseeface_motion import load_openseeface_frame_size_csv, load_openseeface_motion_csv  # noqa: E402
from app.vtuber.source_framing_plan import build_source_framing_plan  # noqa: E402
from tools.render_milica_vrm_source_framing_preview import _parse_frame_size  # noqa: E402
from tools.render_milica_vrm_trump_mapping import DEFAULT_CSV  # noqa: E402


DEFAULT_OUT = ROOT / "debugCapture" / "vtuber_source_framing_plan.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a render-free VTuber source-framing plan.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--video", default="")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--preset", choices=("bust_up", "half_body", "full_body"), default="bust_up")
    parser.add_argument("--slots", default="neutral,head,mouth")
    parser.add_argument("--source-frame-size", default="")
    parser.add_argument("--smoothing", type=float, default=0.35)
    parser.add_argument("--subject-detect-every", type=int, default=3)
    parser.add_argument("--subject-detect-scope", choices=("selected", "sequence"), default="selected")
    parser.add_argument("--user-pan-x", type=float, default=0.0)
    parser.add_argument("--user-pan-y", type=float, default=0.0)
    parser.add_argument("--user-pan-z", type=float, default=0.0)
    parser.add_argument("--user-zoom-delta", type=float, default=0.0)
    parser.add_argument("--user-zoom-scale", type=float, default=1.0)
    parser.add_argument("--user-camera-z-delta", type=float, default=0.0)
    parser.add_argument("--user-lower-occlusion-y-delta", type=float, default=0.0)
    args = parser.parse_args(argv)

    csv_path = Path(args.csv)
    frames = load_openseeface_motion_csv(csv_path)
    if not frames:
        raise SystemExit(f"No OpenSeeFace frames loaded: {csv_path}")
    frame_size = _parse_frame_size(args.source_frame_size) or load_openseeface_frame_size_csv(csv_path) or (640, 360)
    report = build_source_framing_plan(
        frames,
        frame_size,
        preset=args.preset,
        video_path=Path(args.video) if args.video else None,
        slots=args.slots,
        smoothing=float(args.smoothing),
        subject_detect_every=max(1, int(args.subject_detect_every)),
        subject_detect_scope=args.subject_detect_scope,
        user_offset={
            "pan_x": float(args.user_pan_x),
            "pan_y": float(args.user_pan_y),
            "pan_z": float(args.user_pan_z),
            "zoom_delta": float(args.user_zoom_delta),
            "zoom_scale": float(args.user_zoom_scale),
            "camera_z_delta": float(args.user_camera_z_delta),
            "lower_occlusion_y_delta": float(args.user_lower_occlusion_y_delta),
        },
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": bool(report.get("ok")), "out": str(out), "selected_indices": report.get("selected_indices")}, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

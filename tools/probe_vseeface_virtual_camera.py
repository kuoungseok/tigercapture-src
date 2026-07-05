"""Probe VSeeFaceCamera/DirectShow camera capture with OpenCV."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.virtual_camera_probe import probe_virtual_camera_frames  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe virtual camera frames for VSeeFace capture.")
    parser.add_argument("--max-index", type=int, default=8)
    parser.add_argument("--frames-per-camera", type=int, default=8)
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "virtual_camera_probe"))
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "vseeface_virtual_camera_probe.json"))
    args = parser.parse_args(argv)

    report = probe_virtual_camera_frames(
        max_index=args.max_index,
        frames_per_camera=args.frames_per_camera,
        out_dir=Path(args.out_dir),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "selected": report["selected"], "out": str(out)}, ensure_ascii=False))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

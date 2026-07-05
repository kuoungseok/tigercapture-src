"""Inspect non-window capture backends for the VSeeFace sidecar."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vseeface_capture_diagnostics import inspect_capture_backends  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect VSeeFace Spout2/virtual-camera capture backend readiness.")
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "vseeface_capture_backend_preflight.json"))
    args = parser.parse_args(argv)

    report = inspect_capture_backends(ROOT)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "decision": report.get("decision")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

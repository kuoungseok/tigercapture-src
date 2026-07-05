"""Build the VTuber/broadcast commercial-readiness report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_broadcast_release_readiness_qa(
    *,
    out: str | Path = "debugCapture/broadcast_release_readiness_qa.json",
) -> dict:
    from app.broadcast_release_readiness import build_broadcast_release_readiness_report

    report = build_broadcast_release_readiness_report(ROOT)
    out_path = ROOT / Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build VTuber/broadcast commercial-readiness report.")
    parser.add_argument("--out", default="debugCapture/broadcast_release_readiness_qa.json")
    parser.add_argument(
        "--allow-not-ready",
        action="store_true",
        help="Write the report but return 0 even when commercial_ready is false.",
    )
    args = parser.parse_args()
    report = run_broadcast_release_readiness_qa(out=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {ROOT / Path(args.out)}")
    return 0 if args.allow_not_ready or report.get("commercial_ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())

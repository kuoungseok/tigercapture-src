"""Build the six-area release-gap closure QA report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build Tiger Studio release-gap closure report.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out", default="debugCapture/release_gap_closure_qa.json")
    parser.add_argument("--strict", action="store_true", help="Return non-zero unless all six areas are release-ready.")
    args = parser.parse_args()

    from app.release_gap_closure import build_release_gap_closure_report

    root = Path(args.root)
    report = build_release_gap_closure_report(root)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    if args.strict and not report.get("release_ready"):
        return 1
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())


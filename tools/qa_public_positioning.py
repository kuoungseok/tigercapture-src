"""QA entry point for public release-positioning copy."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.release_positioning import DEFAULT_PUBLIC_COPY_PATHS, build_release_positioning_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit public copy for over-strong competitor/parity claims.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=ROOT / "debugCapture" / "public_positioning_qa.json")
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="Public markdown/text path to audit. May be supplied multiple times.",
    )
    args = parser.parse_args(argv)
    paths = tuple(args.paths or DEFAULT_PUBLIC_COPY_PATHS)
    report = build_release_positioning_report(args.root, paths=paths)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "summary": report["summary"], "out": str(args.out)}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

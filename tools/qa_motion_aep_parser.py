"""Inspect an AEP without launching After Effects or Motion Designer."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.aep import AepParseError, inspect_aep_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--tree", action="store_true", help="Include the full chunk tree")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = inspect_aep_file(args.input, include_tree=args.tree)
    except (AepParseError, OSError) as exc:
        report = {"ok": False, "source": str(args.input), "error": str(exc)}
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

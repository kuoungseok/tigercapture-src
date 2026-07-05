"""Relink missing media/model paths in a TigerCapture project.

Example:

    .venv\\Scripts\\python.exe tools\\relink_project_media.py project.tgp D:\\Footage D:\\Models
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("search_roots", nargs="*", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--health", action="store_true", help="Report missing/proxy/relink health without writing a project copy.")
    args = parser.parse_args()

    from app.media_relink import build_media_health_report, relink_project_file

    if args.health:
        doc = json.loads(args.project.read_text(encoding="utf-8"))
        report = build_media_health_report(doc, args.search_roots)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1

    if not args.search_roots:
        parser.error("search_roots are required unless --health is used")

    _out, report = relink_project_file(
        args.project,
        args.search_roots,
        out_path=args.out,
        in_place=args.in_place,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("changed", 0) >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

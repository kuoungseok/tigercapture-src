"""Prepare real Screen Studio cursor-sidecar intake templates."""
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
    parser = argparse.ArgumentParser(description="Prepare Screen Studio real-recording cursor sidecar templates.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/screenstudio_sidecar_intake_qa.json"))
    parser.add_argument("--real-manifest", type=Path, default=Path("qa_corpus/screenstudio_real_recordings/manifest.json"))
    parser.add_argument("--template-dir", type=Path, default=Path("debugCapture/screenstudio_sidecar_templates"))
    parser.add_argument("--write-templates", action="store_true", help="Write .cursor.template.json files.")
    parser.add_argument("--next-to-media", action="store_true", help="Write templates next to source media instead of template-dir.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing template files.")
    parser.add_argument("--max-templates", type=int, default=0, help="Limit templates written; 0 means no limit.")
    args = parser.parse_args()

    from app.screenstudio_sidecar_intake import build_screenstudio_sidecar_intake_report

    report = build_screenstudio_sidecar_intake_report(
        real_manifest_path=args.real_manifest,
        template_dir=args.template_dir,
        write_templates=bool(args.write_templates),
        next_to_media=bool(args.next_to_media),
        overwrite=bool(args.overwrite),
        max_templates=max(0, int(args.max_templates or 0)),
    )
    out_path = args.out
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

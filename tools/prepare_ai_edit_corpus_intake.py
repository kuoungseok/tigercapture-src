"""Prepare safe templates for real AI edit corpus cases."""
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

    parser = argparse.ArgumentParser(description="Prepare real AI edit corpus intake templates.")
    parser.add_argument("--manifest", default="", help="Optional qa_corpus/ai_editing_corpus/manifest.json path.")
    parser.add_argument("--out", default="debugCapture/ai_edit_corpus_intake_qa.json")
    parser.add_argument("--template-dir", default="qa_corpus/ai_editing_corpus/intake_templates")
    parser.add_argument("--target-min", type=int, default=20)
    parser.add_argument("--write-templates", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    from app.ai_edit_corpus_intake import build_ai_edit_corpus_intake_report

    report = build_ai_edit_corpus_intake_report(
        manifest_path=args.manifest or None,
        target_min=args.target_min,
        template_dir=args.template_dir,
        write_templates=bool(args.write_templates),
        overwrite=bool(args.overwrite),
    )
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Register all filled AI edit corpus templates in a directory."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _iter_templates(template_dir: Path, pattern: str, recursive: bool) -> list[Path]:
    if not template_dir.exists():
        return []
    iterator = template_dir.rglob(pattern) if recursive else template_dir.glob(pattern)
    return sorted(path for path in iterator if path.is_file())


def _is_filled_template(payload: Mapping[str, Any]) -> bool:
    case = payload.get("manifest_case")
    if not isinstance(case, Mapping):
        return False
    return bool(str(case.get("prompt") or "").strip() and str(case.get("transcript_path") or "").strip())


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Register filled AI edit real-case templates in bulk.")
    parser.add_argument("--template-dir", type=Path, default=Path("qa_corpus/ai_editing_corpus/intake_templates"))
    parser.add_argument("--pattern", default="*.template.json")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/ai_editing_corpus/manifest.json"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-copy-transcript", action="store_true")
    args = parser.parse_args()

    from app.ai_edit_corpus_registration import load_ai_edit_case_template, register_ai_edit_corpus_case_from_template

    rows: list[dict[str, Any]] = []
    for template_path in _iter_templates(args.template_dir, args.pattern, bool(args.recursive)):
        try:
            template = load_ai_edit_case_template(template_path)
            if not _is_filled_template(template):
                rows.append(
                    {
                        "template_path": str(template_path),
                        "state": "skipped_placeholder",
                        "registered": False,
                    }
                )
                continue
            report = register_ai_edit_corpus_case_from_template(
                template_path,
                manifest_path=args.manifest,
                copy_transcript=not bool(args.no_copy_transcript),
                overwrite=bool(args.overwrite),
            )
            rows.append(
                {
                    "template_path": str(template_path),
                    "state": "registered" if report.get("registered") else str(report.get("warning") or "not_registered"),
                    "registered": bool(report.get("registered")),
                    "case_id": str(report.get("case_id") or ""),
                    "validation": report.get("validation", {}),
                    "missing": list(report.get("missing") or []),
                    "report": report,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "template_path": str(template_path),
                    "state": "failed",
                    "registered": False,
                    "error": str(exc),
                }
            )

    summary = {
        "templates": len(rows),
        "registered": sum(1 for row in rows if row.get("registered")),
        "skipped_placeholder": sum(1 for row in rows if row.get("state") == "skipped_placeholder"),
        "already_exists": sum(1 for row in rows if row.get("state") == "case_already_exists"),
        "invalid": sum(1 for row in rows if row.get("state") == "case_requirements_missing"),
        "failed": sum(1 for row in rows if row.get("state") == "failed"),
    }
    result = {
        "ok": summary["failed"] == 0,
        "kind": "ai_edit_corpus_template_registration",
        "template_dir": str(args.template_dir),
        "summary": summary,
        "rows": rows,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

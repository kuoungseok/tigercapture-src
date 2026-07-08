"""Register validation evidence for a real NLE corpus project.

This writes redacted operator evidence to the real-project corpus manifest.
It does not inspect private media contents and it does not make generated
fixtures count as real corpus evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_REQUIRED_CHECKS = [
    "open_reopen",
    "scrub_sampling",
    "proxy_relink_health",
    "undo_recovery",
    "short_export",
]


def _parse_check_rows(values: list[str], *, all_passed: bool = False, include_nested: bool = False) -> list[dict[str, str]]:
    rows: dict[str, str] = {}
    if all_passed:
        for check_id in DEFAULT_REQUIRED_CHECKS:
            rows[check_id] = "passed"
        if include_nested:
            rows["nested_proxy_edge_cases"] = "passed"
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if "=" in text:
            check_id, status = text.split("=", 1)
        elif ":" in text:
            check_id, status = text.split(":", 1)
        else:
            raise ValueError(f"Invalid --check value {text!r}; use check_id=status")
        rows[check_id.strip()] = status.strip()
    return [{"id": check_id, "status": status} for check_id, status in rows.items()]


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=None, help="Registered project path.")
    parser.add_argument("--project-id", default="", help="Registered corpus project id.")
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/nle_real_projects/manifest.json"))
    parser.add_argument(
        "--check",
        action="append",
        default=[],
        help="Validation check result, e.g. open_reopen=passed or short_export=failed. Repeatable.",
    )
    parser.add_argument(
        "--all-passed",
        action="store_true",
        help="Mark the required validation checks as passed.",
    )
    parser.add_argument(
        "--include-nested",
        action="store_true",
        help="When used with --all-passed, also mark nested/proxy edge cases as passed.",
    )
    parser.add_argument("--operator", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--evidence-path", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from app.nle_real_corpus import (
        preview_nle_real_project_validation_evidence,
        register_nle_real_project_validation_evidence,
    )

    try:
        checks = _parse_check_rows(
            list(args.check or []),
            all_passed=bool(args.all_passed),
            include_nested=bool(args.include_nested),
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    if not checks:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "no_validation_checks",
                    "hint": "Use --all-passed or repeat --check check_id=status.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    fn = preview_nle_real_project_validation_evidence if args.dry_run else register_nle_real_project_validation_evidence
    result = fn(
        project_id=args.project_id,
        project_path=args.project,
        manifest_path=args.manifest,
        checks=checks,
        notes=args.notes,
        operator=args.operator,
        evidence_path=args.evidence_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

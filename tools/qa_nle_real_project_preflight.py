"""Write machine preflight diagnostics for registered real NLE projects."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_nle_real_project_preflight_qa(
    *,
    manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    from app.nle_real_corpus import build_nle_real_project_validation_preflight, load_manifest

    manifest = Path(manifest_path or ROOT / "qa_corpus" / "nle_real_projects" / "manifest.json")
    if not manifest.is_absolute():
        manifest = ROOT / manifest
    payload = load_manifest(manifest)
    projects = [row for row in list(payload.get("projects") or []) if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    for project in projects:
        result = build_nle_real_project_validation_preflight(
            project_id=str(project.get("id") or ""),
            project_path=str(project.get("path") or ""),
            manifest_path=manifest,
        )
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        rows.append(
            {
                "project_id": str(project.get("id") or ""),
                "label": str(project.get("label") or ""),
                "path": str(project.get("path") or ""),
                "ok": bool(result.get("ok")),
                "machine_preflight_passed": bool(summary.get("machine_preflight_passed")),
                "machine_blockers": list(summary.get("machine_blockers") or []),
                "operator_evidence_required": bool(summary.get("operator_evidence_required", True)),
                "preflight": result,
            }
        )
    passed = [row for row in rows if bool(row.get("machine_preflight_passed"))]
    blocked = [row for row in rows if not bool(row.get("machine_preflight_passed"))]
    return {
        "schema": "tigerstudio.nle.real_project_corpus.preflight_qa.v1",
        "ready": bool(projects) and not blocked,
        "manifest": str(manifest),
        "summary": {
            "registered_project_count": len(projects),
            "machine_preflight_passed_count": len(passed),
            "machine_preflight_blocked_count": len(blocked),
        },
        "projects": rows,
        "blockers": ["registered_project_count"] if not projects else [
            "machine_preflight_blockers"
        ] if blocked else [],
    }


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/nle_real_projects/manifest.json"))
    parser.add_argument("--out", type=Path, default=Path("debugCapture/nle_real_project_preflight_qa.json"))
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when preflight is not ready.")
    args = parser.parse_args(argv)

    report = run_nle_real_project_preflight_qa(manifest_path=args.manifest)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print(
        "NLE real project preflight: "
        f"{'ready' if report.get('ready') else 'not ready'}; "
        f"registered={summary.get('registered_project_count', 0)}; "
        f"passed={summary.get('machine_preflight_passed_count', 0)}; "
        f"blocked={summary.get('machine_preflight_blocked_count', 0)}; "
        f"blockers={', '.join(report.get('blockers') or []) or 'none'}"
    )
    print(f"report: {out}")
    return 1 if args.strict and not report.get("ready") else 0


if __name__ == "__main__":
    raise SystemExit(main())

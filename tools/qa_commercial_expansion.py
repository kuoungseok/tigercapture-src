"""Build the commercial expansion QA report.

This report tracks the ten product areas that sit beyond the already closed
TODO list: beta feedback bundles, preview frame server UX, parity lock,
one-click editing, preset marketplace health, audio/color depth, project
snapshots, plugin manifests, and release productization.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_project(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build commercial expansion QA report.")
    parser.add_argument("--project", default="", help="Optional .tgp project used for parity/color/audio checks.")
    parser.add_argument("--out", default="debugCapture/commercial_expansion_qa.json")
    parser.add_argument("--write-feedback-bundle", action="store_true", help="Also create a lightweight beta feedback bundle.")
    parser.add_argument("--snapshot-project", action="store_true", help="Also create a project snapshot when --project is supplied.")
    args = parser.parse_args()

    project_path = Path(args.project) if args.project else None
    project_doc = _load_project(project_path) if project_path else None

    from app.commercial_expansion import (
        build_commercial_expansion_report,
        create_project_snapshot,
        export_beta_feedback_bundle,
    )

    report = build_commercial_expansion_report(project_doc=project_doc, root=ROOT)
    side_effects: dict[str, Any] = {}
    if args.write_feedback_bundle:
        side_effects["feedback_bundle"] = export_beta_feedback_bundle(project_path=project_path, root=ROOT)
    if args.snapshot_project and project_path is not None:
        side_effects["project_snapshot"] = create_project_snapshot(project_path, root=ROOT, label="qa-commercial")
    if side_effects:
        report["side_effects"] = side_effects

    out_path = ROOT / args.out
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

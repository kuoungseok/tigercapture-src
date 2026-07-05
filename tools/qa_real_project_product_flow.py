#!/usr/bin/env python
"""QA product flow over real/local project files plus a render smoke artifact."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _default_project_roots() -> list[Path]:
    return [
        ROOT / "qa_corpus" / "projects",
        ROOT / "qa_corpus" / "product_qa_corpus",
        ROOT / "debugCapture" / "projects",
    ]


def run_real_project_product_flow_qa(
    out_path: str | Path | None = None,
    *,
    roots: list[str | Path] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    from tools.qa_preset_application_corpus import build_report, discover_project_files
    from tools.qa_screenstudio_render_result_smoke import run_screenstudio_render_result_smoke

    out = Path(out_path or "debugCapture/real_project_product_flow_qa.json")
    search_roots = [Path(root) for root in (roots or _default_project_roots())]
    projects: list[Path] = []
    for root in search_roots:
        for path in discover_project_files(root, limit=max(0, int(limit) - len(projects))):
            if path not in projects:
                projects.append(path)
            if len(projects) >= int(limit):
                break
        if len(projects) >= int(limit):
            break
    preset_report = build_report(projects)
    render_report = run_screenstudio_render_result_smoke(
        out.parent / "real_project_render_smoke_report.json",
        video_path=out.parent / "real_project_render_smoke.mp4",
    )
    project_rows = list(preset_report.get("projects") or [])
    parity_ready = sum(1 for row in project_rows if dict(row.get("export_parity") or {}).get("ok"))
    template_first = sum(1 for row in project_rows if row.get("template_first"))
    checks = {
        "project_discovery_ok": len(project_rows) > 0,
        "preset_plans_export_baked": parity_ready == len(project_rows) if project_rows else False,
        "template_first_plans": template_first == len(project_rows) if project_rows else False,
        "render_smoke_ok": bool(render_report.get("ok")),
    }
    report = {
        "ok": all(checks.values()),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "real_project_product_flow",
        "checks": checks,
        "summary": {
            "roots": [str(root) for root in search_roots],
            "projects": len(project_rows),
            "preset_parity_ready": parity_ready,
            "template_first": template_first,
            "render_frames": int((render_report.get("summary") or {}).get("frames", 0) or 0),
        },
        "projects": project_rows,
        "render_smoke": render_report,
        "next_actions": [] if all(checks.values()) else [
            "Add at least one representative .tgp project under qa_corpus/projects.",
            "Ensure one-click preset plans start with a template and all preset kinds map to export-baked targets.",
            "Run tools/qa_screenstudio_render_result_smoke.py if render-smoke generation fails.",
        ],
    }
    _write_json(out, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="debugCapture/real_project_product_flow_qa.json")
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    report = run_real_project_product_flow_qa(args.out, roots=args.root or None, limit=args.limit)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_corpus(manifest_path: Path, output: Path) -> dict:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_figma_plugin_runtime import (
        apply_figma_plugin_result,
        run_figma_plugin_script,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_root = (ROOT / manifest["source"]["local_root"]).resolve()
    cases = []
    for item in manifest["cases"]:
        source_path = (source_root / item["source"]).resolve()
        source_path.relative_to(source_root)
        source = source_path.read_text(encoding="utf-8")
        runtime = run_figma_plugin_script(source, create_ui_document(390, 844), timeout_ms=2000)
        document, applied = apply_figma_plugin_result(
            create_ui_document(390, 844), runtime
        )
        matching = [row for row in document["objects"] if row["kind"] == item["expected_kind"]]
        passed = len(matching) == int(item["expected_count"])
        cases.append({
            "id": item["id"], "source_path": str(source_path),
            "expected_kind": item["expected_kind"],
            "expected_count": item["expected_count"],
            "actual_count": len(matching), "object_count": len(document["objects"]),
            "passed": passed,
            "apply_summary": {
                "applied": bool(applied.get("applied")),
                "created_count": len(applied.get("created_object_ids", [])),
                "selection_count": len(applied.get("selection", [])),
                "notice_count": len(applied.get("notices", [])),
                "error": str(applied.get("error", "")),
            },
        })
    report = {
        "schema": "tigercapture.painter.figma_plugin_official_corpus_report.v1",
        "source": manifest["source"], "case_count": len(cases),
        "passed_count": sum(1 for row in cases if row["passed"]),
        "passed": bool(cases) and all(row["passed"] for row in cases),
        "cases": cases,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default=str(ROOT / "qa_corpus" / "painter_ui_figma_plugins" / "official_samples.json"),
    )
    parser.add_argument(
        "--output", default=str(ROOT / "debugCapture" / "painter_ui_figma_plugin_official_corpus")
    )
    args = parser.parse_args()
    report = run_corpus(Path(args.manifest), Path(args.output))
    summary = {
        "schema": report["schema"],
        "passed": report["passed"],
        "case_count": report["case_count"],
        "passed_count": report["passed_count"],
        "cases": [
            {
                "id": row["id"],
                "expected_count": row["expected_count"],
                "actual_count": row["actual_count"],
                "passed": row["passed"],
            }
            for row in report["cases"]
        ],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

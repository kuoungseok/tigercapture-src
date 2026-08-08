from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_corpus(manifest_path: Path, output: Path) -> dict:
    from app.painter_ui_figma_plugin_ui_session import (
        PainterFigmaPluginUISession,
        preflight_figma_plugin_ui_source,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_root = (ROOT / manifest["source"]["local_root"]).resolve()
    cases = []
    for item in manifest["cases"]:
        source_path = (source_root / item["source"]).resolve()
        ui_path = (source_root / item["ui"]).resolve()
        source_path.relative_to(source_root)
        ui_path.relative_to(source_root)
        source = source_path.read_text(encoding="utf-8")
        html = ui_path.read_text(encoding="utf-8")
        preflight = preflight_figma_plugin_ui_source(source, html)
        actual = "blocked_document_api"
        evidence: dict = {"errors": list(preflight["errors"])}
        if preflight["ok"]:
            actual = "supported_message_ui"
            with PainterFigmaPluginUISession(source, html, plugin_name=item["id"]) as session:
                if item.get("drop_payload") == "first_svg_file":
                    match = re.search(
                        r'<span class="icon"[^>]*>\s*(<svg.*?</svg>)\s*</span>',
                        html,
                        re.DOTALL,
                    )
                    if match is None:
                        raise ValueError("Official icon sample has no SVG fixture")
                    state = session.post_plugin_drop({
                        "clientX": 140,
                        "clientY": 96,
                        "files": [{
                            "name": "content.svg",
                            "type": "image/svg+xml",
                            "text": match.group(1),
                        }],
                        "dropMetadata": {"parentingStrategy": "page"},
                    })
                else:
                    state = session.post_ui_message(item.get("ui_message", "official-corpus"))
                deadline = time.monotonic() + 1.5
                pushes = []
                while time.monotonic() < deadline and not pushes:
                    pushes = session.poll_events()
                    time.sleep(0.02)
                messages = list(state.get("messages") or [])
                for event in pushes:
                    messages.extend(event.get("messages") or [])
                node_count = len(state.get("nodes") or [])
                evidence = {
                    "width": session.ready["ui"]["width"],
                    "height": session.ready["ui"]["height"],
                    "message_count": len(messages),
                    "response_prefix": str(messages[0]).split(":", 1)[0] if messages else "",
                    "node_count": node_count,
                }
                if item["expected"] == "supported_message_ui":
                    if not messages or not str(messages[0]).startswith("code.js:"):
                        actual = "runtime_mismatch"
                elif item["expected"] == "supported_document_ui":
                    actual = "supported_document_ui"
                    if node_count != int(item.get("expected_node_count", -1)):
                        actual = "runtime_mismatch"
                elif item["expected"] == "supported_drop_svg_ui":
                    actual = "supported_drop_svg_ui"
                    nodes = list(state.get("nodes") or [])
                    frame = next((row for row in nodes if row.get("type") == "FRAME"), None)
                    vectors = [row for row in nodes if row.get("type") == "VECTOR"]
                    evidence["node_types"] = [row.get("type") for row in nodes]
                    evidence["vector_parent_ids"] = [row.get("parentId") for row in vectors]
                    if (
                        node_count != int(item.get("expected_node_count", -1))
                        or frame is None
                        or not vectors
                        or any(row.get("parentId") != frame.get("id") for row in vectors)
                    ):
                        actual = "runtime_mismatch"
        cases.append({
            "id": item["id"],
            "expected": item["expected"],
            "actual": actual,
            "passed": actual == item["expected"],
            "evidence": evidence,
        })
    report = {
        "schema": "tigercapture.painter.figma_plugin_official_ui_corpus_report.v1",
        "source": manifest["source"],
        "case_count": len(cases),
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
        default=str(ROOT / "qa_corpus" / "painter_ui_figma_plugins" / "official_ui_samples.json"),
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "debugCapture" / "painter_ui_figma_plugin_official_ui_corpus"),
    )
    args = parser.parse_args()
    report = run_corpus(Path(args.manifest), Path(args.output))
    print(json.dumps({
        "schema": report["schema"], "passed": report["passed"],
        "case_count": report["case_count"], "passed_count": report["passed_count"],
        "cases": [{"id": row["id"], "expected": row["expected"], "actual": row["actual"], "passed": row["passed"]} for row in report["cases"]],
    }, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

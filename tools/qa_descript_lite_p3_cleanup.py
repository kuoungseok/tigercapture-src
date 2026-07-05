"""QA for Descript-lite one-click retake/mistake cleanup."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = ROOT / "debugCapture" / "descript_lite_p3_cleanup_qa.json"


def _sample_document():
    from app.ai_edit_plan import TranscriptDocument, TranscriptSegment

    return TranscriptDocument(
        id="p3_cleanup_doc",
        source_media_id="clip_cleanup",
        language="en-ko",
        segments=(
            TranscriptSegment(id="seg_001", start_ms=1000, end_ms=2600, text="we need to export the timeline"),
            TranscriptSegment(id="seg_002", start_ms=3200, end_ms=5200, text="we need to export the timeline"),
            TranscriptSegment(id="seg_003", start_ms=7000, end_ms=8700, text="wait wait let me try again"),
            TranscriptSegment(id="seg_004", start_ms=9000, end_ms=11000, text="now the export is correct"),
        ),
    )


def build_descript_lite_p3_cleanup_report() -> dict:
    from app.ai_text_editing import clean_tutorial
    from app.retake_detection import (
        detect_mistake_candidates,
        detect_retake_candidates,
        plan_remove_mistakes,
        plan_remove_retakes,
    )

    document = _sample_document()
    retakes = detect_retake_candidates(document)
    mistakes = detect_mistake_candidates(document)
    retake_plan = plan_remove_retakes(document)
    mistake_plan = plan_remove_mistakes(document)
    clean_plan = clean_tutorial(document)
    clean_sources = {operation.source for operation in clean_plan.operations}
    checks = {
        "detects_retake_candidates": len(retakes) == 1 and retakes[0].segment_id == "seg_001",
        "detects_mistake_candidates": len(mistakes) == 1 and mistakes[0].segment_id == "seg_003",
        "retake_plan_materializable": retake_plan.operations and all(operation.type == "delete_time_range" for operation in retake_plan.operations),
        "mistake_plan_materializable": mistake_plan.operations and all(operation.type == "delete_time_range" for operation in mistake_plan.operations),
        "clean_tutorial_includes_p3_cleanup": {"retake_detection", "mistake_detection"} <= clean_sources,
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "kind": "descript_lite_p3_cleanup",
        "ok": not failures,
        "score": int(round(100 * (len(checks) - len(failures)) / max(1, len(checks)))),
        "checks": checks,
        "failures": failures,
        "summary": {
            "retake_candidates": len(retakes),
            "mistake_candidates": len(mistakes),
            "retake_operations": len(retake_plan.operations),
            "mistake_operations": len(mistake_plan.operations),
            "clean_tutorial_operations": len(clean_plan.operations),
        },
        "artifacts": {
            "retakes": [row.to_dict() for row in retakes],
            "mistakes": [row.to_dict() for row in mistakes],
            "retake_plan": retake_plan.to_dict(),
            "mistake_plan": mistake_plan.to_dict(),
            "clean_tutorial": clean_plan.to_dict(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Descript-lite P3 cleanup QA report.")
    parser.add_argument("--out", default=str(DEFAULT_REPORT), help="Output JSON report path.")
    args = parser.parse_args()

    report = build_descript_lite_p3_cleanup_report()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "score": report["score"], "report": str(out)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

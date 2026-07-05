"""Build a deterministic QA report for AI text and one-click edit planning."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SRT_SAMPLE = """1
00:00:01,000 --> 00:00:03,000
Um today we explain materials.

2
00:00:04,000 --> 00:00:06,000
어 이제 base color를 연결합니다.
"""

VTT_SAMPLE = """WEBVTT

intro
00:00:01.000 --> 00:00:02.500
Hello <b>world</b>

00:00:03.000 --> 00:00:04.000
Product demo beat
"""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _malformed_plan_is_rejected() -> bool:
    from app.ai_edit_plan import EditPlanValidationError, validate_edit_plan_json

    bad_payloads = [
        {
            "id": "bad_direct_code",
            "intent": "bad",
            "summary": "bad",
            "operations": [{"type": "delete_time_range", "target": "project", "params": {"python": "print(1)"}}],
        },
        {
            "id": "bad_unknown_type",
            "intent": "bad",
            "summary": "bad",
            "operations": [{"type": "execute_shell", "target": "project"}],
        },
        {
            "id": "bad_project_mutation",
            "intent": "bad",
            "summary": "bad",
            "operations": [{"type": "delete_time_range", "target": "project", "metadata": {"project_mutation": True}}],
        },
    ]
    for payload in bad_payloads:
        try:
            validate_edit_plan_json(json.dumps(payload, ensure_ascii=False))
        except EditPlanValidationError:
            continue
        return False
    return True


def _recipe_cards_reference_operations(*plans) -> bool:
    for plan in plans:
        operation_ids = {operation.id for operation in plan.operations}
        if not operation_ids or not plan.review_cards:
            return False
        for card in plan.review_cards:
            if not card.operation_ids:
                return False
            if not set(card.operation_ids) <= operation_ids:
                return False
    return True


def build_ai_text_editing_report() -> dict[str, Any]:
    from app.ai_edit_plan import validate_edit_plan_json
    from app.ai_text_editing import (
        clean_tutorial_recipe,
        detect_filler_ranges,
        parse_srt_text,
        parse_vtt_text,
        plan_remove_silences,
        plan_text_range_cut,
        plan_transcript_to_captions,
        product_demo_recipe,
        shorts_recipe,
        text_range_to_time_range,
    )

    srt_doc = parse_srt_text(SRT_SAMPLE, document_id="qa_srt", language="en")
    vtt_doc = parse_vtt_text(VTT_SAMPLE, document_id="qa_vtt", language="en")
    mapped_range = text_range_to_time_range(srt_doc, "seg_001", 0, 2)
    text_cut_plan = plan_text_range_cut(srt_doc, segment_id="seg_001", start_char=0, end_char=2)
    fillers = detect_filler_ranges(srt_doc)
    silence_plan = plan_remove_silences(
        [{"start_ms": 3000, "end_ms": 4200}, {"start_ms": 7000, "end_ms": 7300}],
        min_duration_ms=700,
    )
    caption_plan = plan_transcript_to_captions(srt_doc)
    clean_plan = clean_tutorial_recipe(srt_doc, silence_intervals=[{"start_ms": 3000, "end_ms": 4200}])
    shorts_plan = shorts_recipe(srt_doc)
    product_plan = product_demo_recipe(srt_doc)
    stable_once = clean_plan.to_stable_json()
    stable_twice = clean_plan.to_stable_json()
    restored = validate_edit_plan_json(stable_once)

    checks = {
        "srt_import": len(srt_doc.segments) == 2 and srt_doc.segments[0].start_ms == 1000,
        "vtt_import": len(vtt_doc.segments) == 2 and vtt_doc.segments[0].text == "Hello world",
        "text_range_mapping": mapped_range[0] >= 1000 and mapped_range[1] <= 3000 and mapped_range[0] < mapped_range[1],
        "text_cut_plan": text_cut_plan.operations[0].type == "ripple_cut_text_range",
        "filler_detection": len(fillers) >= 3,
        "silence_plan": len(silence_plan.operations) == 1 and silence_plan.operations[0].start_ms == 3000,
        "caption_plan": caption_plan.operations and caption_plan.operations[0].type == "create_subtitles",
        "recipe_plan_validation": all(
            plan.requires_review and plan.review_cards and plan.operations
            for plan in (clean_plan, shorts_plan, product_plan)
        )
        and _recipe_cards_reference_operations(clean_plan, shorts_plan, product_plan),
        "malformed_plan_rejection": _malformed_plan_is_rejected(),
        "deterministic_serialization": stable_once == stable_twice == restored.to_stable_json(),
    }
    failures = [name for name, passed in checks.items() if not passed]
    score = int(round(100 * (len(checks) - len(failures)) / max(1, len(checks))))
    return {
        "ok": not failures,
        "score": score,
        "summary": {
            "srt_segments": len(srt_doc.segments),
            "vtt_segments": len(vtt_doc.segments),
            "filler_ranges": len(fillers),
            "silence_operations": len(silence_plan.operations),
            "caption_operations": len(caption_plan.operations),
            "recipe_operations": len(clean_plan.operations) + len(shorts_plan.operations) + len(product_plan.operations),
            "stable_json_bytes": len(stable_once.encode("utf-8")),
        },
        "checks": checks,
        "failures": failures,
        "transcripts": {
            "srt": srt_doc.to_dict(),
            "vtt": vtt_doc.to_dict(),
        },
        "plans": {
            "text_cut": text_cut_plan.to_dict(),
            "silence": silence_plan.to_dict(),
            "captions": caption_plan.to_dict(),
            "clean_tutorial": clean_plan.to_dict(),
            "shorts": shorts_plan.to_dict(),
            "product_demo": product_plan.to_dict(),
        },
        "filler_ranges": fillers,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build AI text editing QA report.")
    parser.add_argument("--out", default="debugCapture/ai_text_editing_qa.json")
    args = parser.parse_args()

    report = build_ai_text_editing_report()
    out_path = ROOT / args.out
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

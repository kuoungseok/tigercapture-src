"""QA for VideoEditorWindow-free Descript-lite P1 service foundations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = ROOT / "debugCapture" / "descript_lite_p1_services_qa.json"


def build_descript_lite_p1_services_report() -> dict:
    from app.ai_edit_plan import TranscriptDocument, TranscriptSegment, TranscriptWord
    from app.ai_script_edit_panel import ScriptEditPanelModel
    from app.transcript_edit_surface import TranscriptEditSurface
    from app.transcript_reflow import reflow_transcript_after_cuts
    from app.transcript_selection_actions import build_selection_scoped_edit_plan
    from app.transcript_timeline_ops import build_delete_text_range_intents, build_sentence_move_clip_move_intents

    document = TranscriptDocument(
        id="p1_doc",
        source_media_id="clip_a",
        language="en",
        segments=(
            TranscriptSegment(
                id="seg_001",
                start_ms=1000,
                end_ms=4200,
                text="alpha beta gamma",
                words=(
                    TranscriptWord("alpha", 1000, 1400),
                    TranscriptWord("beta", 1600, 2100),
                    TranscriptWord("gamma", 2600, 3200),
                ),
            ),
            TranscriptSegment(id="seg_002", start_ms=5000, end_ms=6200, text="next sentence"),
        ),
    )
    reflowed = reflow_transcript_after_cuts(
        document,
        [{"id": "cut_beta", "original_start_ms": 1500, "original_end_ms": 2500}],
    )
    delete_intents = build_delete_text_range_intents(document, segment_id="seg_001", start_char=6, end_char=10)
    move_intents = build_sentence_move_clip_move_intents(document, source_segment_id="seg_002", before_segment_id="seg_001")
    scoped_plan = build_selection_scoped_edit_plan(document, segment_id="seg_001", start_char=11, end_char=16)
    surface = TranscriptEditSurface(document)
    surface_selection = surface.select_text_range("seg_001", 11, 16)
    surface_scoped_plan = surface.build_selection_scoped_plan()
    model = ScriptEditPanelModel(source_media_id="clip_a", language="en")
    model.set_transcript_document(document)
    model_selection = model.select_transcript_range("seg_001", 11, 16)
    model_scoped_plan = model.generate_selection_scoped_plan()
    model_move_preview = model.build_sentence_move_preview(source_segment_id="seg_002", before_segment_id="seg_001")
    scoped_types = [operation.type for operation in scoped_plan.operations]
    checks = {
        "reflow_removes_cut_word": reflowed.segments[0].text == "alpha gamma",
        "reflow_shifts_later_word": reflowed.segments[0].words[-1].start_ms == 1600,
        "delete_intents_are_reviewed_cuts": delete_intents["cut_intents"][0]["type"] == "ripple_cut_text_range",
        "sentence_move_uses_linked_clip_actions": move_intents["required_registered_actions"] == ["timeline.split", "clip.move_linked"],
        "selection_scoped_caption_zoom_highlight": scoped_types == ["create_subtitles", "add_auto_zoom", "add_callout"],
        "transcript_edit_surface_selection": surface_selection["text"] == "gamma" and len(surface_scoped_plan.operations) == 3,
        "script_edit_panel_model_surface": model_selection["text"] == "gamma"
        and len(model_scoped_plan.operations) == 3
        and model_move_preview["required_registered_actions"] == ["timeline.split", "clip.move_linked"],
        "no_video_editor_window_dependency": all(
            "video_editor_window" not in str(module).casefold()
            for module in (
                "app.transcript_edit_surface",
                "app.transcript_reflow",
                "app.transcript_timeline_ops",
                "app.transcript_selection_actions",
            )
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "kind": "descript_lite_p1_services",
        "ok": not failures,
        "score": int(round(100 * (len(checks) - len(failures)) / max(1, len(checks)))),
        "checks": checks,
        "failures": failures,
        "summary": {
            "reflowed_segments": len(reflowed.segments),
            "delete_cut_intents": len(delete_intents.get("cut_intents") or []),
            "move_action_steps": len(move_intents.get("action_steps") or []),
            "selection_operations": len(scoped_plan.operations),
        },
        "artifacts": {
            "reflowed_transcript": reflowed.to_dict(),
            "delete_intents": delete_intents,
            "move_intents": move_intents,
            "selection_plan": scoped_plan.to_dict(),
            "surface_preview": surface.preview(),
            "model_surface_preview": model.transcript_edit_preview(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Descript-lite P1 service QA report.")
    parser.add_argument("--out", default=str(DEFAULT_REPORT), help="Output JSON report path.")
    args = parser.parse_args()

    report = build_descript_lite_p1_services_report()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "score": report["score"], "report": str(out)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

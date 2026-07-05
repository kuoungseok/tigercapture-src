"""QA report for the local LTX-style storyboard planner."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _default_project() -> dict[str, Any]:
    return {
        "duration_s": 184,
        "screen_recording": True,
        "has_audio": True,
        "dialogue": True,
        "creator_prompt": "Make this screen recording feel like a polished vertical tutorial.",
        "transcript_segments": [
            {"id": "seg_001", "start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make the first result look good."},
            {"id": "seg_002", "start_ms": 64000, "end_ms": 84000, "text": "Watch how the app keeps the important button in frame."},
            {"id": "seg_003", "start_ms": 125000, "end_ms": 151000, "text": "The final export is already formatted for Shorts."},
        ],
    }


def _default_media() -> list[dict[str, Any]]:
    return [
        {
            "id": "screen-demo-1",
            "name": "screen tutorial recording.mp4",
            "kind": "video",
            "tags": ["screen-recording", "tutorial"],
            "object_tags": ["cursor", "button", "timeline"],
            "people": ["host"],
        }
    ]


def run_ltx_storyboard_qa(*, out: str | Path | None = None) -> dict[str, Any]:
    from app.ai_edit_plan import validate_edit_plan_json
    from app.ltx_storyboard import ltx_storyboard_provider_state, ltx_storyboard_report

    report = ltx_storyboard_report(
        "Plan a polished Screen Studio style vertical tutorial with shot cards, cursor zooms, captions, and a clear ending.",
        _default_project(),
        _default_media(),
        aspect_ratio="9:16",
    )
    storyboard = report.get("storyboard") if isinstance(report.get("storyboard"), dict) else {}
    edit_plan_payload = report.get("edit_plan") if isinstance(report.get("edit_plan"), dict) else {}
    apply_payload = report.get("apply_payload") if isinstance(report.get("apply_payload"), dict) else {}
    variations = report.get("variations") if isinstance(report.get("variations"), dict) else {}
    template_recommendations = report.get("template_recommendations") if isinstance(report.get("template_recommendations"), dict) else {}
    effect_materialization = report.get("effect_materialization") if isinstance(report.get("effect_materialization"), dict) else {}
    effect_counts = effect_materialization.get("counts") if isinstance(effect_materialization.get("counts"), dict) else {}
    shots = storyboard.get("shot_cards") if isinstance(storyboard.get("shot_cards"), list) else []
    operations = edit_plan_payload.get("operations") if isinstance(edit_plan_payload.get("operations"), list) else []
    review_cards = edit_plan_payload.get("review_cards") if isinstance(edit_plan_payload.get("review_cards"), list) else []
    try:
        validated_plan = validate_edit_plan_json(json.dumps(edit_plan_payload, ensure_ascii=False))
        edit_plan_valid = True
        validated_operation_count = len(validated_plan.operations)
    except Exception:
        edit_plan_valid = False
        validated_operation_count = 0
    checks = {
        "storyboard_report_ok": bool(report.get("ok")),
        "shot_cards_ready": len(shots) >= 4,
        "camera_metadata": all(row.get("camera_angle") and row.get("camera_motion") for row in shots),
        "transition_metadata": all(row.get("transition_hint") for row in shots),
        "source_or_placeholder": all("source_media_id" in row and "source_query" in row for row in shots),
        "review_first_edit_plan": bool(edit_plan_payload.get("requires_review")) and edit_plan_valid,
        "shot_review_cards": len(review_cards) == len(shots),
        "timeline_operations": len(operations) >= len(shots) * 2,
        "apply_payload_markers": len(apply_payload.get("timeline_markers") if isinstance(apply_payload.get("timeline_markers"), list) else []) >= len(shots),
        "apply_payload_sidecars": len(apply_payload.get("sidecars") if isinstance(apply_payload.get("sidecars"), list) else []) >= 1,
        "effect_materialization": bool(effect_materialization.get("ready")),
        "effect_zoom_windows": int(effect_counts.get("zoom_windows", 0) or 0) >= 1,
        "effect_callouts": int(effect_counts.get("callouts", 0) or 0) >= 1,
        "retake_variations": int(variations.get("variation_count", 0) or 0) >= 3,
        "template_recommendations": int(template_recommendations.get("card_count", 0) or 0) >= 3,
        "provider_contract": "configured" in ltx_storyboard_provider_state(),
        "honest_claim": storyboard.get("claim_level") == "ltx_inspired_local_shot_cards_not_ltx_cloud_parity",
    }
    payload = {
        "ok": all(checks.values()),
        "checks": checks,
        "summary": {
            "shot_cards": len(shots),
            "operations": len(operations),
            "validated_operations": validated_operation_count,
            "review_cards": len(review_cards),
            "apply_markers": len(apply_payload.get("timeline_markers") if isinstance(apply_payload.get("timeline_markers"), list) else []),
            "apply_sidecars": len(apply_payload.get("sidecars") if isinstance(apply_payload.get("sidecars"), list) else []),
            "effect_zoom_windows": int(effect_counts.get("zoom_windows", 0) or 0),
            "effect_callouts": int(effect_counts.get("callouts", 0) or 0),
            "variations": int(variations.get("variation_count", 0) or 0),
            "template_recommendations": int(template_recommendations.get("card_count", 0) or 0),
            "intent": storyboard.get("intent"),
            "claim_level": storyboard.get("claim_level"),
            "real_ltx_cloud": False,
        },
        "report": report,
    }
    if out is not None:
        _write_json(Path(out), payload)
    return payload


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate the LTX-style storyboard feature.")
    parser.add_argument("--out", default="debugCapture/ltx_storyboard_qa.json")
    args = parser.parse_args()
    report = run_ltx_storyboard_qa(out=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {Path(args.out).resolve()}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

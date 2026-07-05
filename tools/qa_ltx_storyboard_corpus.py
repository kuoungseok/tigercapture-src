"""Corpus QA for LTX-style local storyboard planning."""
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


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "id": "screen_tutorial",
            "prompt": "Storyboard this screen recording as a polished tutorial with cursor zooms and shot cards.",
            "expected_intent": "screen_tutorial",
            "summary": {
                "duration_s": 182,
                "screen_recording": True,
                "dialogue": True,
                "has_audio": True,
                "transcript_segments": [
                    {"id": "seg_001", "start_ms": 0, "end_ms": 12000, "text": "Start by opening the media panel."},
                    {"id": "seg_002", "start_ms": 21000, "end_ms": 36000, "text": "Drag the clip to the timeline and zoom on the important button."},
                    {"id": "seg_003", "start_ms": 61000, "end_ms": 76000, "text": "Export this as a clean vertical tutorial."},
                ],
            },
            "media": [{"id": "screen-001", "name": "screen-recording.mp4", "kind": "video", "tags": ["screen-recording"], "object_tags": ["cursor", "button"]}],
        },
        {
            "id": "gameplay_highlight",
            "prompt": "Create shot cards for a vertical gameplay highlight with impact zooms and replay detail.",
            "expected_intent": "gameplay_highlight",
            "summary": {"duration_s": 96, "has_audio": True, "needs_shorts": True},
            "media": [{"id": "game-001", "name": "boss fight.mp4", "kind": "video", "tags": ["gameplay"], "object_tags": ["player", "enemy"]}],
        },
        {
            "id": "product_demo",
            "prompt": "Make a product launch storyboard with feature proof, before after, and CTA.",
            "expected_intent": "product_demo",
            "summary": {"duration_s": 74, "dialogue": True, "creator_prompt": "product demo"},
            "media": [{"id": "product-001", "name": "app demo.mp4", "kind": "video", "tags": ["product"], "object_tags": ["phone", "dashboard"]}],
        },
        {
            "id": "dialogue_story",
            "prompt": "Plan this interview as chaptered shot cards with quote highlights.",
            "expected_intent": "dialogue_story",
            "summary": {
                "duration_s": 240,
                "dialogue": True,
                "transcript_segments": [
                    {"id": "seg_001", "start_ms": 5000, "end_ms": 18000, "text": "The key lesson is to keep the first action simple."},
                    {"id": "seg_002", "start_ms": 47000, "end_ms": 66000, "text": "Then show the result instead of explaining every setting."},
                ],
            },
            "media": [{"id": "talk-001", "name": "interview.mp4", "kind": "video", "people": ["host", "guest"]}],
        },
        {
            "id": "korean_storyboard",
            "prompt": "이 영상을 콘티와 샷카드로 나눠서 숏폼 튜토리얼처럼 만들어줘.",
            "expected_intent": "screen_tutorial",
            "summary": {"duration_s": 58, "screen_recording": True, "dialogue": True},
            "media": [{"id": "kr-001", "name": "korean tutorial.mp4", "kind": "video", "tags": ["tutorial"], "object_tags": ["cursor"]}],
        },
    ]


def run_ltx_storyboard_corpus_qa(*, out: str | Path | None = None) -> dict[str, Any]:
    from app.ai_edit_plan import validate_edit_plan_json
    from app.ltx_storyboard import ltx_storyboard_report, prompt_requests_storyboard

    rows: list[dict[str, Any]] = []
    for case in _cases():
        report = ltx_storyboard_report(case["prompt"], case["summary"], case["media"], aspect_ratio="9:16")
        storyboard = report.get("storyboard") if isinstance(report.get("storyboard"), dict) else {}
        edit_plan = report.get("edit_plan") if isinstance(report.get("edit_plan"), dict) else {}
        apply_payload = report.get("apply_payload") if isinstance(report.get("apply_payload"), dict) else {}
        effects = report.get("effect_materialization") if isinstance(report.get("effect_materialization"), dict) else {}
        effect_counts = effects.get("counts") if isinstance(effects.get("counts"), dict) else {}
        variations = report.get("variations") if isinstance(report.get("variations"), dict) else {}
        recs = report.get("template_recommendations") if isinstance(report.get("template_recommendations"), dict) else {}
        shots = storyboard.get("shot_cards") if isinstance(storyboard.get("shot_cards"), list) else []
        try:
            validate_edit_plan_json(json.dumps(edit_plan, ensure_ascii=False))
            edit_plan_valid = True
        except Exception:
            edit_plan_valid = False
        checks = {
            "prompt_routed": prompt_requests_storyboard(case["prompt"]),
            "report_ok": bool(report.get("ok")),
            "intent_matches": storyboard.get("intent") == case["expected_intent"],
            "shot_cards": len(shots) >= 4,
            "valid_edit_plan": edit_plan_valid,
            "timeline_markers": len(apply_payload.get("timeline_markers") if isinstance(apply_payload.get("timeline_markers"), list) else []) >= len(shots),
            "review_sidecars": len(apply_payload.get("sidecars") if isinstance(apply_payload.get("sidecars"), list) else []) >= 1,
            "effect_materialization": bool(effects.get("ready")),
            "effect_zoom_windows": int(effect_counts.get("zoom_windows", 0) or 0) >= 1,
            "effect_callouts": int(effect_counts.get("callouts", 0) or 0) >= 1,
            "variations": int(variations.get("variation_count", 0) or 0) >= 3,
            "template_recommendations": int(recs.get("card_count", 0) or 0) >= 3,
            "honest_claim": storyboard.get("claim_level") == "ltx_inspired_local_shot_cards_not_ltx_cloud_parity",
        }
        rows.append(
            {
                "id": case["id"],
                "ok": all(checks.values()),
                "checks": checks,
                "intent": storyboard.get("intent"),
                "shot_count": len(shots),
                "operation_count": len(edit_plan.get("operations") if isinstance(edit_plan.get("operations"), list) else []),
                "effect_zoom_windows": int(effect_counts.get("zoom_windows", 0) or 0),
                "effect_callouts": int(effect_counts.get("callouts", 0) or 0),
                "variation_count": int(variations.get("variation_count", 0) or 0),
                "template_recommendation_count": int(recs.get("card_count", 0) or 0),
            }
        )
    passed = sum(1 for row in rows if row["ok"])
    payload = {
        "ok": passed == len(rows),
        "case_count": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "rows": rows,
    }
    if out is not None:
        _write_json(Path(out), payload)
    return payload


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run LTX-style storyboard corpus QA.")
    parser.add_argument("--out", default="debugCapture/ltx_storyboard_corpus_qa.json")
    args = parser.parse_args()
    report = run_ltx_storyboard_corpus_qa(out=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {Path(args.out).resolve()}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

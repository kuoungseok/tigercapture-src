"""Build a CapCut-style quick-result QA report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _default_project() -> dict[str, Any]:
    return {
        "duration_s": 184,
        "shortform": False,
        "screen_recording": True,
        "has_audio": True,
        "dialogue": True,
        "transcript_segments": [
            {"start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make the first result look good."},
            {"start_ms": 64000, "end_ms": 84000, "text": "Watch how the app keeps the important button in frame."},
            {"start_ms": 125000, "end_ms": 151000, "text": "The final export is already formatted for Shorts."},
        ],
    }


def _media_items(media_doc: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("media_items", "media", "assets"):
        value = media_doc.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return [
        {
            "id": "screen-demo-1",
            "name": "product walkthrough recording.mp4",
            "kind": "video",
            "duration_s": 184,
            "object_tags": ["cursor", "app", "button"],
            "dialogue": ["This is the fastest way to prepare a polished demo."],
            "tags": ["screen-recording", "tutorial"],
        }
    ]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build CapCut-style quick-result QA report.")
    parser.add_argument("--project", default="", help="Optional .tgp/JSON project document.")
    parser.add_argument("--media", default="", help="Optional media metadata JSON list/document.")
    parser.add_argument("--out", default="debugCapture/capcut_quick_result_qa.json")
    args = parser.parse_args()

    project_doc = _load_json(Path(args.project)) if args.project else _default_project()
    media_doc = _load_json(Path(args.media)) if args.media else {}

    from app.capcut_quick_result import capcut_one_click_quality_model, capcut_quick_result_model
    from app.capcut_workflow import capcut_creator_apply_bundle

    bundle = capcut_creator_apply_bundle(project_doc, _media_items(media_doc))
    quick = capcut_quick_result_model(bundle)
    quality = capcut_one_click_quality_model(bundle)
    checks = {
        "quick_result_ready": bool(quick.get("ready")),
        "recommended_template_exists": bool((quick.get("recommendation") or {}).get("exists")),
        "quality_above_80": float(quality.get("score", 0) or 0) >= 80.0,
        "captions_ready": bool((quality.get("checks") or {}).get("caption_rows_ready")),
        "render_jobs_ready": bool((quality.get("checks") or {}).get("render_jobs_ready")),
        "publish_review_ready": bool((quality.get("checks") or {}).get("publish_review_ready")),
        "beginner_default_path_ready": bool((quick.get("summary") or {}).get("beginner_default_path_ready")),
        "visible_feedback_ready": int((quick.get("summary") or {}).get("visible_feedback_count", 0) or 0) >= 4,
    }
    report = {
        "kind": "capcut_quick_result",
        "ok": all(checks.values()),
        "score": round(100 * sum(1 for value in checks.values() if value) / max(1, len(checks)), 2),
        "checks": checks,
        "summary": {
            **dict(quick.get("summary", {}) or {}),
            "quality_score": quality.get("score", 0),
            "quality_ok": bool(quality.get("ok")),
        },
        "quick_result": quick,
        "quality": quality,
    }
    out_path = ROOT / args.out
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

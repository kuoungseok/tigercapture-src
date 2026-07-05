"""Build a CapCut-style creator workflow QA report."""
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


def _default_media_fixture() -> list[dict[str, Any]]:
    return [
        {
            "id": "screen-demo-1",
            "name": "product walkthrough recording.mp4",
            "kind": "video",
            "duration_s": 184,
            "object_tags": ["cursor", "app", "button"],
            "people": ["host"],
            "dialogue": ["This is the fastest way to prepare a polished demo."],
            "tags": ["screen-recording", "tutorial"],
        },
        {
            "id": "gameplay-clip-1",
            "name": "gameplay win moment.mp4",
            "kind": "video",
            "duration_s": 42,
            "object_tags": ["character", "snow", "horse"],
            "people": [],
            "dialogue": ["Watch this perfect timing."],
            "tags": ["gameplay", "short-form"],
        },
    ]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build CapCut-style creator workflow QA report.")
    parser.add_argument("--project", default="", help="Optional .tgp/JSON project document.")
    parser.add_argument("--media", default="", help="Optional media metadata JSON list/document.")
    parser.add_argument("--out", default="debugCapture/capcut_creator_workflow_qa.json")
    args = parser.parse_args()

    project_doc = _load_json(Path(args.project)) if args.project else {
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
    media_doc = _load_json(Path(args.media)) if args.media else {}
    media_items: list[dict[str, Any]]
    if isinstance(media_doc.get("media_items"), list):
        media_items = media_doc["media_items"]
    elif isinstance(media_doc.get("media"), list):
        media_items = media_doc["media"]
    else:
        media_items = _default_media_fixture()

    from app.capcut_workflow import capcut_creator_workflow_report

    report = capcut_creator_workflow_report(project_doc, media_items)
    out_path = ROOT / args.out
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

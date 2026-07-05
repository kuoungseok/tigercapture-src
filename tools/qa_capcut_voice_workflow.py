"""Build a CapCut-style captions/voice workflow QA report."""
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
            {"start_ms": 64000, "end_ms": 84000, "text": "Watch how captions and voice cleanup stay reviewable."},
            {"start_ms": 125000, "end_ms": 151000, "text": "Optional voice providers stay off until configured."},
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

    parser = argparse.ArgumentParser(description="Build CapCut-style captions/voice workflow QA report.")
    parser.add_argument("--project", default="", help="Optional .tgp/JSON project document.")
    parser.add_argument("--media", default="", help="Optional media metadata JSON list/document.")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--out", default="debugCapture/capcut_voice_workflow_qa.json")
    args = parser.parse_args()

    project_doc = _load_json(Path(args.project)) if args.project else _default_project()
    media_doc = _load_json(Path(args.media)) if args.media else {}

    from app.capcut_voice import capcut_voice_manifest, capcut_voice_workflow_model, voice_provider_contracts
    from app.capcut_workflow import capcut_creator_apply_bundle

    bundle = capcut_creator_apply_bundle(project_doc, _media_items(media_doc))
    workflow = capcut_voice_workflow_model(bundle, language=args.language)
    manifest = capcut_voice_manifest(bundle, language=args.language)
    providers = voice_provider_contracts()
    checks = {
        "workflow_ready": bool(workflow.get("ready")),
        "workflow_score_above_85": float(workflow.get("score", 0) or 0) >= 85.0,
        "caption_rows_ready": bool((workflow.get("checks") or {}).get("caption_rows_ready")),
        "voice_cleanup_ready": bool((workflow.get("checks") or {}).get("voice_cleanup_ready")),
        "provider_contracts_present": len(providers) >= 8,
        "configured_local_providers": int(workflow.get("configured_provider_count", 0) or 0) >= 5,
        "tts_slot_is_explicitly_unconfigured": any(
            row.get("id") == "system_tts_slot" and not row.get("configured") and row.get("status") == "needs_setup"
            for row in providers
            if isinstance(row, dict)
        ),
        "cloud_voice_not_default": int(manifest.get("network_provider_count", 0) or 0) == 0,
    }
    report = {
        "kind": "capcut_voice_workflow",
        "ok": all(checks.values()),
        "score": round(100 * sum(1 for value in checks.values() if value) / max(1, len(checks)), 2),
        "checks": checks,
        "summary": {
            **dict(workflow.get("summary", {}) or {}),
            "workflow_score": workflow.get("score", 0),
            "provider_count": int(workflow.get("provider_count", 0) or 0),
            "configured_provider_count": int(workflow.get("configured_provider_count", 0) or 0),
            "manifest_operations": len(manifest.get("operations", []) or []),
        },
        "workflow": workflow,
        "manifest": manifest,
    }
    out_path = ROOT / args.out
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

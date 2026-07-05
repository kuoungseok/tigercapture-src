"""Build a CapCut-style publish review QA report."""
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


def _default_media() -> list[dict[str, Any]]:
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


def _media_items(media_doc: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("media_items", "media", "assets"):
        value = media_doc.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return _default_media()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build CapCut-style publish review QA report.")
    parser.add_argument("--project", default="", help="Optional .tgp/JSON project document.")
    parser.add_argument("--media", default="", help="Optional media metadata JSON list/document.")
    parser.add_argument("--out", default="debugCapture/capcut_publish_review_qa.json")
    parser.add_argument("--package-dir", default="")
    args = parser.parse_args()

    project_doc = _load_json(Path(args.project)) if args.project else _default_project()
    media_doc = _load_json(Path(args.media)) if args.media else {}

    from app.capcut_publish import capcut_publish_manifest, capcut_publish_review_model, capcut_write_quick_upload_package
    from app.capcut_workflow import capcut_creator_apply_bundle

    bundle = capcut_creator_apply_bundle(project_doc, _media_items(media_doc))
    export_paths = ["exports/capcut_shorts/demo_short_01.mp4"]
    review = capcut_publish_review_model(bundle, export_paths=export_paths)
    manifest = capcut_publish_manifest(bundle, export_paths=export_paths)
    out_path = ROOT / args.out
    package_dir = Path(args.package_dir) if args.package_dir else out_path.with_name(out_path.stem + "_package")
    if not package_dir.is_absolute():
        package_dir = ROOT / package_dir
    package_result = capcut_write_quick_upload_package(bundle, package_dir, export_paths=export_paths)
    checks = {
        "review_ready": bool(review.get("ready")),
        "copy_ready": bool((review.get("summary") or {}).get("copy_ready")),
        "providers_present": int(review.get("provider_count", 0) or 0) >= 12,
        "configured_local_providers": int(review.get("configured_provider_count", 0) or 0) >= 8,
        "quick_uploads_ready": int(review.get("ready_quick_upload_count", 0) or 0) >= 3,
        "api_upload_slots_explicit": int(review.get("api_upload_provider_count", 0) or 0) >= 3,
        "manifest_ready": bool(manifest.get("ready")),
        "network_upload_not_default": any(
            row.get("id") == "share_link_provider" and not row.get("configured") and row.get("requires_network")
            for row in review.get("providers", [])
            if isinstance(row, dict)
        ),
        "direct_api_upload_not_default": all(
            not row.get("configured")
            for row in review.get("providers", [])
            if isinstance(row, dict) and row.get("kind") == "api_upload"
        ),
        "quick_upload_package_written": bool(package_result.get("ok") and package_result.get("file_count", 0) >= 10),
        "quick_upload_package_has_platform_text": all(
            any(row.get("name") == name for row in package_result.get("files", []) or [])
            for name in ("tiktok_post.txt", "instagram_post.txt", "x_post.txt")
        ),
        "quick_upload_package_no_upload": not bool(package_result.get("upload_attempted")),
    }
    report = {
        "kind": "capcut_publish_review",
        "ok": all(checks.values()),
        "score": round(100 * sum(1 for value in checks.values() if value) / max(1, len(checks)), 2),
        "checks": checks,
        "summary": {
            **dict(review.get("summary", {}) or {}),
            "provider_count": int(review.get("provider_count", 0) or 0),
            "configured_provider_count": int(review.get("configured_provider_count", 0) or 0),
            "quick_upload_count": int(review.get("quick_upload_count", 0) or 0),
            "ready_quick_upload_count": int(review.get("ready_quick_upload_count", 0) or 0),
            "api_upload_provider_count": int(review.get("api_upload_provider_count", 0) or 0),
            "manifest_exports": len(manifest.get("export_paths", []) or []),
            "quick_upload_package_written": bool(package_result.get("ok")),
            "quick_upload_package_file_count": int(package_result.get("file_count", 0) or 0),
            "quick_upload_package_path": str(package_result.get("path", "")),
        },
        "review": review,
        "manifest": manifest,
        "quick_upload_package": package_result,
    }
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

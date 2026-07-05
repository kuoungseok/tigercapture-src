"""Build a CapCut-style cloud/share handoff QA report."""
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
        "transcript_segments": [
            {"start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make a polished demo."},
            {"start_ms": 64000, "end_ms": 84000, "text": "Keep the important button in frame."},
            {"start_ms": 125000, "end_ms": 151000, "text": "Export the result for Shorts."},
        ],
    }


def _default_media() -> list[dict[str, Any]]:
    return [
        {
            "id": "screen-demo-1",
            "name": "product walkthrough recording.mp4",
            "path": "media/product walkthrough recording.mp4",
            "kind": "video",
            "duration_s": 184,
            "object_tags": ["cursor", "app", "button"],
            "tags": ["screen-recording", "tutorial"],
        }
    ]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build CapCut cloud/share handoff QA report.")
    parser.add_argument("--out", default="debugCapture/capcut_cloud_handoff_qa.json")
    parser.add_argument("--package-dir", default="")
    args = parser.parse_args()

    from app.capcut_cloud_handoff import capcut_cloud_handoff_report, capcut_write_cloud_ready_package
    from app.capcut_collaboration import capcut_collab_handoff_manifest
    from app.capcut_workflow import capcut_creator_apply_bundle

    bundle = capcut_creator_apply_bundle(_default_project(), _default_media())
    manifest = capcut_collab_handoff_manifest(bundle, _default_media(), search_roots=["media", "exports"])
    report = capcut_cloud_handoff_report(manifest)
    out_path = ROOT / args.out
    package_dir = Path(args.package_dir) if args.package_dir else out_path.with_name(out_path.stem + "_package")
    if not package_dir.is_absolute():
        package_dir = ROOT / package_dir
    package_result = capcut_write_cloud_ready_package(manifest, package_dir)
    report["local_package_writer"] = package_result
    checks = report.setdefault("checks", {})
    checks["local_package_written"] = bool(package_result.get("ok") and package_result.get("file_count", 0) >= 6)
    checks["local_package_has_readme"] = any(row.get("name") == "README.txt" for row in package_result.get("files", []) or [])
    checks["local_package_no_upload"] = not bool(package_result.get("upload_attempted"))
    report["ok"] = all(bool(value) for value in checks.values())
    report["score"] = round(100 * sum(1 for value in checks.values() if value) / max(1, len(checks)), 2)
    summary = report.setdefault("summary", {})
    summary["local_package_written"] = bool(package_result.get("ok"))
    summary["local_package_file_count"] = int(package_result.get("file_count", 0) or 0)
    summary["local_package_path"] = str(package_result.get("path", ""))

    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

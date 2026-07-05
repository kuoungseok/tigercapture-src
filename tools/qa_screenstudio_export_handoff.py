from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT_DIR = ROOT / "debugCapture" / "screenstudio_export_handoff"


def _scenario_settings(starter: str, width: int, height: int, fps: float, **extra) -> dict[str, Any]:
    from app.screenstudio_polish import screenstudio_starter_defaults

    settings = {
        "starter_template_id": starter,
        "canvas_width": int(width),
        "canvas_height": int(height),
        "fps": float(fps),
        "screenstudio_polish": screenstudio_starter_defaults(starter),
    }
    settings.update(extra)
    return settings


def _run_scenario(row: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    from app.screenstudio_polish import (
        screenstudio_export_completion_summary,
        screenstudio_default_export_settings,
        screenstudio_build_share_link,
        screenstudio_share_manifest_path,
        screenstudio_write_local_share_manifest,
    )

    scenario_id = str(row["id"])
    settings = _scenario_settings(
        str(row["starter"]),
        int(row["width"]),
        int(row["height"]),
        float(row["fps"]),
        **dict(row.get("extra") or {}),
    )
    defaults = screenstudio_default_export_settings(settings)
    export_path = out_dir / f"{scenario_id}.{defaults.get('format_id') or 'mp4'}"
    export_path.write_bytes((f"fake export {scenario_id}\n").encode("utf-8") * 32)
    manifest_path = None
    failures: list[str] = []
    if defaults.get("share_package_ready"):
        manifest_path = screenstudio_write_local_share_manifest(export_path, defaults)
        if not manifest_path.exists():
            failures.append("manifest_missing")
    else:
        expected_path = screenstudio_share_manifest_path(export_path)
        if expected_path.exists():
            failures.append("unexpected_manifest")

    payload: dict[str, Any] = {}
    if manifest_path is not None and manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            failures.append("manifest_unreadable")
            payload = {}

    expected = dict(row.get("expected") or {})
    for key, expected_value in expected.items():
        actual = defaults.get(key)
        if actual != expected_value:
            failures.append(f"default_{key}_mismatch")
        if payload and key in payload and payload.get(key) != expected_value:
            failures.append(f"manifest_{key}_mismatch")

    if payload:
        if payload.get("kind") != "screenstudio_local_share_package":
            failures.append("manifest_kind_mismatch")
        if payload.get("file_name") != export_path.name:
            failures.append("manifest_file_name_mismatch")
        if int(payload.get("size_bytes", 0) or 0) <= 0:
            failures.append("manifest_size_missing")
        if list(payload.get("destinations") or []) != list(defaults.get("destinations") or []):
            failures.append("manifest_destinations_mismatch")
        if defaults.get("share_link_ready") and not payload.get("share_url"):
            failures.append("manifest_share_url_missing")

    completion = screenstudio_export_completion_summary(export_path, defaults)
    if completion.get("status") != "ready":
        failures.append("completion_not_ready")
    if completion.get("output_path") != str(export_path):
        failures.append("completion_output_mismatch")
    if defaults.get("share_package_ready") and not completion.get("share_manifest_exists"):
        failures.append("completion_manifest_missing")
    share_link = screenstudio_build_share_link(export_path, defaults) if defaults.get("share_link_ready") else {}
    if defaults.get("share_link_ready"):
        if not share_link.get("share_url"):
            failures.append("share_url_missing")
        if completion.get("share_url") != share_link.get("share_url"):
            failures.append("completion_share_url_mismatch")

    return {
        "id": scenario_id,
        "ok": not failures,
        "failures": failures,
        "export_path": str(export_path),
        "manifest_path": str(manifest_path) if manifest_path is not None else "",
        "intent_id": defaults.get("intent_id"),
        "format_id": defaults.get("format_id"),
        "quality_id": defaults.get("quality_id"),
        "clipboard_ready": bool(defaults.get("clipboard_ready")),
        "share_package_ready": bool(defaults.get("share_package_ready")),
        "share_link_ready": bool(defaults.get("share_link_ready")),
        "share_provider": str(defaults.get("share_provider") or ""),
        "share_provider_label": str(defaults.get("share_provider_label") or ""),
        "share_url": str(share_link.get("share_url") or ""),
        "handoff_label": str(defaults.get("handoff_label") or ""),
        "post_export_actions": list(defaults.get("post_export_actions") or []),
        "completion_status": str(completion.get("status") or ""),
        "completion_actions": list(completion.get("action_labels") or []),
        "completion_summary": str(completion.get("summary_line") or ""),
    }


def _run_default_result_scenario() -> dict[str, Any]:
    from app.screenstudio_polish import (
        CursorEvent,
        apply_screenstudio_polish_to_clip,
        screenstudio_default_golden_video_probe,
        screenstudio_default_result_beauty_score,
        screenstudio_default_export_result_readiness,
        screenstudio_starter_defaults,
    )

    settings = {
        "starter_template_id": "screen-recording-demo",
        "canvas_width": 1920,
        "canvas_height": 1080,
        "fps": 60.0,
        "screenstudio_polish": screenstudio_starter_defaults("screen-recording-demo"),
    }
    clip = SimpleNamespace(
        source_duration_ms=9000,
        effective_source_out_ms=9000,
        effective_length_ms=9000,
        zoom_actors=[],
        cursor_events=[
            CursorEvent(800, 0.26, 0.42, "move"),
            CursorEvent(1800, 0.70, 0.46, "click"),
            CursorEvent(2050, 0.70, 0.46, "release"),
            CursorEvent(5200, 0.38, 0.58, "click"),
        ],
        screenstudio_polish={},
    )
    added = apply_screenstudio_polish_to_clip(
        clip,
        frame_w=1920,
        frame_h=1080,
        cursor_events=clip.cursor_events,
        cursor_polish=settings["screenstudio_polish"]["cursor"],
        screen_polish=settings["screenstudio_polish"]["screen"],
        preset_id=settings["screenstudio_polish"]["preset_id"],
    )
    readiness = screenstudio_default_export_result_readiness(
        settings,
        cursor_metadata_count=1,
        polished_clip_count=1 if added > 0 else 0,
        auto_zoom_count=added,
    )
    golden_video = screenstudio_default_golden_video_probe(settings)
    beauty = screenstudio_default_result_beauty_score(
        settings,
        cursor_metadata_count=1,
        polished_clip_count=1 if added > 0 else 0,
        auto_zoom_count=added,
        golden_video_ready=bool(golden_video.get("ok")),
    )
    failures: list[str] = []
    if not readiness.get("ok"):
        failures.append("readiness_failed")
    if not beauty.get("ok"):
        failures.append("beauty_score_failed")
    if not golden_video.get("ok"):
        failures.append("golden_video_probe_failed")
    if int(beauty.get("score", 0) or 0) < int(beauty.get("threshold", 85) or 85):
        failures.append("beauty_score_below_threshold")
    if added <= 0:
        failures.append("auto_zoom_not_added")
    polish = dict(getattr(clip, "screenstudio_polish", {}) or {})
    if not polish.get("auto_zoom_actor_ids"):
        failures.append("clip_polish_missing_zoom_ids")
    if str(polish.get("preset_id") or "") != "screenstudio_ready":
        failures.append("clip_polish_preset_mismatch")
    return {
        "id": "default_record_edit_export",
        "ok": not failures,
        "failures": failures,
        "auto_zoom_added": int(added),
        "readiness": readiness,
        "beauty": beauty,
        "golden_video": golden_video,
        "clip_polish": {
            "preset_id": polish.get("preset_id"),
            "auto_zoom_actor_ids": list(polish.get("auto_zoom_actor_ids") or []),
        },
    }


def run_screenstudio_export_handoff_qa(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = [
        {
            "id": "web_demo",
            "starter": "screen-recording-demo",
            "width": 1920,
            "height": 1080,
            "fps": 60.0,
            "expected": {
                "intent_id": "web_demo",
                "format_id": "mp4",
                "quality_id": "high",
                "clipboard_ready": True,
                "share_package_ready": True,
                "share_link_ready": False,
                "handoff_label": "clipboard + local share",
            },
        },
        {
            "id": "social_vertical",
            "starter": "vertical-shorts",
            "width": 1080,
            "height": 1920,
            "fps": 60.0,
            "expected": {
                "intent_id": "social_vertical",
                "format_id": "mp4",
                "quality_id": "high",
                "clipboard_ready": True,
                "share_package_ready": True,
                "share_link_ready": False,
                "handoff_label": "clipboard + local share",
            },
        },
        {
            "id": "product_web",
            "starter": "product-demo",
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "expected": {
                "intent_id": "product_web",
                "format_id": "mp4",
                "quality_id": "high",
                "clipboard_ready": True,
                "share_package_ready": True,
                "share_link_ready": False,
                "handoff_label": "clipboard + local share",
            },
        },
        {
            "id": "editor_roundtrip",
            "starter": "actor-showcase",
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
            "expected": {
                "intent_id": "editor_roundtrip",
                "format_id": "mov",
                "quality_id": "best",
                "clipboard_ready": False,
                "share_package_ready": True,
                "share_link_ready": False,
                "handoff_label": "local package",
            },
        },
        {
            "id": "configured_share_link",
            "starter": "screen-recording-demo",
            "width": 1920,
            "height": 1080,
            "fps": 60.0,
            "extra": {"screenstudio_share_provider": "workspace-share"},
            "expected": {
                "intent_id": "web_demo",
                "format_id": "mp4",
                "quality_id": "high",
                "clipboard_ready": True,
                "share_package_ready": True,
                "share_link_ready": True,
                "share_provider": "workspace-share",
                "handoff_label": "share link",
            },
        },
    ]
    rows = [_run_scenario(row, out_dir) for row in scenarios]
    default_result = _run_default_result_scenario()
    failures = [
        {"id": row["id"], "failures": row["failures"]}
        for row in rows
        if not row.get("ok")
    ]
    if not default_result.get("ok"):
        failures.append({"id": default_result["id"], "failures": default_result["failures"]})
    return {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir),
        "summary": {
            "scenarios": len(rows),
            "passing": sum(1 for row in rows if row.get("ok")),
            "failing": len(failures),
            "clipboard_ready": sum(1 for row in rows if row.get("clipboard_ready")),
            "share_package_ready": sum(1 for row in rows if row.get("share_package_ready")),
            "share_link_ready": sum(1 for row in rows if row.get("share_link_ready")),
            "share_url_ready": sum(1 for row in rows if row.get("share_url")),
            "manifests": sum(1 for row in rows if row.get("manifest_path") and Path(str(row.get("manifest_path"))).exists()),
            "completion_ready": sum(1 for row in rows if row.get("completion_status") == "ready"),
            "default_result_ready": 1 if default_result.get("ok") else 0,
            "default_auto_zoom_added": int(default_result.get("auto_zoom_added", 0) or 0),
            "default_beauty_ready": 1 if (default_result.get("beauty") or {}).get("ok") else 0,
            "default_beauty_score": int((default_result.get("beauty") or {}).get("score", 0) or 0),
            "default_golden_video_ready": 1 if (default_result.get("golden_video") or {}).get("ok") else 0,
        },
        "rows": rows,
        "default_result": default_result,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Screen Studio export handoff QA.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/screenstudio_export_handoff_qa.json"))
    args = parser.parse_args()
    report = run_screenstudio_export_handoff_qa(out_dir=args.out_dir)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(out), "out_dir": report["out_dir"]}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Fast coverage gate for creator-facing polish.

This report intentionally cuts across the areas users notice first:
timeline preset affordances, preview realism, Screen Studio-style defaults,
CapCut-style quick creation, and long-project stability hooks.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _ensure_qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _pixmap_signature(pixmap) -> str:
    image = pixmap.toImage()
    width = max(1, image.width())
    height = max(1, image.height())
    samples: list[int] = []
    for y in (0, height // 4, height // 2, height * 3 // 4, height - 1):
        for x in (0, width // 4, width // 2, width * 3 // 4, width - 1):
            samples.append(int(image.pixel(x, y)) & 0xFFFFFFFF)
    return f"{width}x{height}:{sum(samples) & 0xFFFFFFFF:08x}:{samples[0]:08x}:{samples[-1]:08x}"


def _preset_preview_section() -> dict[str, Any]:
    _ensure_qapp()
    from app.video_editor_window import _render_preset_application_frame_preview

    scenarios = [
        {
            "id": "soft-denoise",
            "kind": "effect",
            "label": "Soft Denoise",
            "payload": {"video_filters": {"enabled": True, "blur": True, "denoise": True}},
            "tags": ("denoise", "soft"),
        },
        {
            "id": "key-glitch",
            "kind": "effect",
            "label": "Key Glitch",
            "payload": {
                "chroma_key": {"enabled": True},
                "video_filters": {"enabled": True, "glitch": True},
            },
            "tags": ("keying", "glitch"),
        },
        {
            "id": "white-hit",
            "kind": "transition",
            "label": "White Hit",
            "payload": {"transition_out_type": "fade_white", "transition_out_ms": 160},
            "tags": ("transition", "shortform"),
        },
        {
            "id": "title-pop",
            "kind": "title",
            "label": "Title Pop",
            "payload": {"text": "Launch Beat"},
            "tags": ("title", "screen-studio"),
        },
    ]
    samples: list[dict[str, Any]] = []
    signatures: list[str] = []
    for scenario in scenarios:
        pixmap = _render_preset_application_frame_preview(
            preset_id=str(scenario["id"]),
            kind=str(scenario["kind"]),
            label=str(scenario["label"]),
            payload=dict(scenario["payload"]),
            tags=tuple(scenario["tags"]),
            sample_pixmap=None,
        )
        signature = _pixmap_signature(pixmap)
        signatures.append(signature)
        samples.append({
            "id": scenario["id"],
            "kind": scenario["kind"],
            "null": bool(pixmap.isNull()),
            "signature": signature,
        })
    non_null = all(not row["null"] for row in samples)
    distinct = len(set(signatures)) == len(signatures)
    return {
        "ok": bool(non_null and distinct),
        "summary": f"{len(samples)} preview samples, distinct={distinct}",
        "checks": {
            "non_null_previews": non_null,
            "payloads_render_distinctly": distinct,
        },
        "samples": samples,
    }


def _screenstudio_section() -> dict[str, Any]:
    from app.screenstudio_polish import (
        screenstudio_audio_defaults,
        screenstudio_default_result_beauty_score,
        screenstudio_simple_mode_profile,
        screenstudio_starter_defaults,
    )

    settings = {
        "starter_template_id": "screen-recording-demo",
        "screenstudio_simple_mode": True,
        "screenstudio_polish": screenstudio_starter_defaults("screen-recording-demo"),
        "screenstudio_audio_defaults": screenstudio_audio_defaults("screen-recording-demo"),
        "screenstudio_audio_defaults_ready": True,
        "screenstudio_clipboard_ready": True,
        "screenstudio_share_link_ready": True,
        "screenstudio_golden_video_ready": True,
        "canvas_width": 1920,
        "canvas_height": 1080,
    }
    beauty = screenstudio_default_result_beauty_score(
        settings,
        cursor_metadata_count=3,
        polished_clip_count=3,
        auto_zoom_count=3,
        golden_video_ready=True,
    )
    simple = screenstudio_simple_mode_profile(settings)
    checks = dict(beauty.get("checks") or {})
    ok = bool(beauty.get("ok")) and int(beauty.get("score", 0) or 0) >= 95 and int(simple.get("score", 0) or 0) >= 100
    return {
        "ok": ok,
        "summary": f"beauty {beauty.get('score', 0)}/100, simple {simple.get('score', 0)}/100",
        "checks": checks,
        "beauty": beauty,
        "simple": simple,
    }


def _capcut_section() -> dict[str, Any]:
    from app.capcut_workflow import capcut_creator_workflow_report

    report = capcut_creator_workflow_report(
        {
            "duration_s": 184,
            "shortform": False,
            "screen_recording": True,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [
                {"start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make this screen recording look good."},
                {"start_ms": 64000, "end_ms": 84000, "text": "Watch how the cursor focus keeps the important button in frame."},
                {"start_ms": 125000, "end_ms": 151000, "text": "The final export is already formatted for short clips."},
            ],
            "subject_detections": [
                {"t_ms": 2000, "x_norm": 0.42, "y_norm": 0.48, "confidence": 0.92},
                {"t_ms": 32000, "x_norm": 0.62, "y_norm": 0.46, "confidence": 0.90},
            ],
        },
        [
            {
                "id": "screen-demo-1",
                "name": "product walkthrough recording.mp4",
                "kind": "video",
                "duration_s": 184,
                "object_tags": ["cursor", "button", "app"],
                "people": ["host"],
                "dialogue": ["fastest way to make this screen recording look good"],
                "tags": ["screen-recording", "tutorial"],
            }
        ],
    )
    summary = dict(report.get("summary") or {})
    ok = (
        bool(report.get("ok"))
        and int(report.get("score", 0) or 0) >= 95
        and int(summary.get("edit_recipe_steps", 0) or 0) >= 6
        and int(summary.get("publish_handoff_actions", 0) or 0) >= 5
        and bool(summary.get("review_panel_ready"))
        and bool(summary.get("publish_package_ready"))
        and bool(summary.get("quick_create_ready"))
    )
    return {
        "ok": ok,
        "summary": (
            f"score {report.get('score', 0)}/100, "
            f"recipe {summary.get('edit_recipe_steps', 0)}, "
            f"handoff {summary.get('publish_handoff_actions', 0)}"
        ),
        "capcut_summary": summary,
    }


def _timeline_feedback_section() -> dict[str, Any]:
    from app.preset_library import EditorPreset
    from app.preset_feedback import (
        preset_discoverability_cards,
        preset_drop_feedback_model,
        preset_preview_ab_model,
        preset_timeline_strip_rows,
        timeline_interaction_feedback_model,
    )
    from app.video_editor_window import VideoEditorWindow

    effect = EditorPreset(id="effect-feedback", kind="effect", name="Punchy Clean")
    effect_text = VideoEditorWindow._workflow_apply_summary_text(
        effect,
        [{"kind": "effect", "status": "will_apply"}],
    )
    empty_text = VideoEditorWindow._workflow_apply_summary_text(effect, [])
    source = (ROOT / "app" / "video_editor_window.py").read_text(encoding="utf-8")
    workflow_source = (ROOT / "app" / "video_editor_preset_workflows.py").read_text(encoding="utf-8")
    finish_start = source.find("def _finish_workflow_preset_application")
    finish_end = source.find("def _apply_workflow_preset", finish_start)
    finish_block = source[finish_start:finish_end] if finish_start >= 0 and finish_end > finish_start else ""
    workflow_finish_start = workflow_source.find("def _finish_workflow_preset_application")
    workflow_finish_end = workflow_source.find("def _on_workflow_preset_dropped", workflow_finish_start)
    workflow_finish_block = (
        workflow_source[workflow_finish_start:workflow_finish_end]
        if workflow_finish_start >= 0 and workflow_finish_end > workflow_finish_start
        else ""
    )
    strip_rows = preset_timeline_strip_rows(
        effect,
        [{"kind": "effect", "status": "applied", "start_ms": 1000, "duration_ms": 1800}],
        clip_start_ms=0,
        clip_end_ms=5000,
    )
    preview_ab = preset_preview_ab_model(effect, before_signature="a", after_signature="b")
    snap_feedback = timeline_interaction_feedback_model("snap", snap_ms=1000, target_ms=2000, mode="trim", selected_count=1)
    checks = {
        "non_template_summary": "Preset applied" in effect_text and "FX" in effect_text,
        "empty_effect_summary_not_template": "Effect applied" in empty_text,
        "toast_not_template_only": 'kind == "template"' not in finish_block,
        "timeline_burst_still_present": "flash_timeline_burst" in (finish_block + workflow_finish_block),
        "drop_chip_has_reason": "Needs target" in preset_drop_feedback_model(effect, can_drop=False, reason="Select a video clip")["chip"],
        "discoverability_cards": len(preset_discoverability_cards()) >= 4,
        "timeline_strip_model": bool(strip_rows) and strip_rows[0]["badge"] == "FX",
        "preview_ab_model": preview_ab["changed"] is True and preview_ab["split_mode"] == "wipe_ab",
        "interaction_feedback_model": snap_feedback["chip"] == "Snapped" and "snap" in snap_feedback["detail"],
    }
    return {
        "ok": all(checks.values()),
        "summary": f"{sum(1 for value in checks.values() if value)}/{len(checks)} preset feedback checks",
        "checks": checks,
        "samples": {
            "effect_text": effect_text,
            "empty_text": empty_text,
            "strip": strip_rows[0] if strip_rows else {},
            "preview_ab": preview_ab,
            "snap_feedback": snap_feedback,
        },
    }


def _product_polish_next_section() -> dict[str, Any]:
    from app.product_polish import product_polish_readiness_report

    report = product_polish_readiness_report()
    summary = dict(report.get("summary") or {})
    checks = {
        "ten_areas": int(summary.get("areas", 0) or 0) >= 10,
        "all_areas_passing": int(summary.get("passing", 0) or 0) == int(summary.get("areas", 0) or 0),
        "export_targets": int(summary.get("export_targets", 0) or 0) >= 5,
        "caption_rows": int(summary.get("capcut_caption_rows", 0) or 0) >= 3,
        "dashboard_productized": any(
            isinstance(area, dict) and area.get("id") == "qa_dashboard_productization" and area.get("ok")
            for area in list(report.get("areas", []) or [])
        ),
    }
    return {
        "ok": all(checks.values()),
        "summary": (
            f"{int(summary.get('passing', 0) or 0)}/"
            f"{int(summary.get('areas', 0) or 0)} areas, "
            f"score {int(report.get('score', 0) or 0)}/100"
        ),
        "checks": checks,
        "report_summary": summary,
    }


def _render_smoke_section() -> dict[str, Any]:
    from tools.qa_screenstudio_render_result_smoke import run_screenstudio_render_result_smoke

    report = run_screenstudio_render_result_smoke(
        ROOT / "debugCapture" / "creator_polish_render_smoke" / "screenstudio_render_result_smoke_report.json",
    )
    checks = dict(report.get("checks") or {})
    return {
        "ok": bool(report.get("ok")),
        "summary": (
            f"{int((report.get('summary') or {}).get('frames', 0) or 0)} frame(s), "
            f"{int((report.get('summary') or {}).get('cursor_pixels', 0) or 0)} cursor pixels"
        ),
        "checks": checks,
        "report": report,
    }


def _stability_section() -> dict[str, Any]:
    from app.qa_dashboard import QADashboardDialog, REPORT_SPECS

    kinds = {kind for _, _, kind in REPORT_SPECS}
    productization_text = (ROOT / "tools" / "qa_productization_loop.py").read_text(encoding="utf-8")
    command = QADashboardDialog._command_for_row({
        "kind": "creator_polish_coverage",
        "path": str(ROOT / "debugCapture" / "creator_polish_coverage_qa.json"),
    })
    checks = {
        "dashboard_row": "creator_polish_coverage" in kinds,
        "dashboard_runner": bool(command) and "qa_creator_polish_coverage.py" in " ".join(command),
        "timeline_preset_visibility": "timeline_preset_visibility" in kinds,
        "long_project_stress": "long_project_stress" in kinds,
        "crash_report": "crash_report" in kinds,
        "relink_module": (ROOT / "app" / "media_relink.py").exists(),
        "proxy_tests": (ROOT / "tests" / "test_chroma_proxy.py").exists(),
        "recovery_tool": (ROOT / "tools" / "repair_project.py").exists() and (ROOT / "app" / "recovery_dialog.py").exists(),
        "productization_runner": "qa_creator_polish_coverage.py" in productization_text,
    }
    ok = all(checks.values())
    return {
        "ok": ok,
        "summary": f"{sum(1 for value in checks.values() if value)}/{len(checks)} hooks ready",
        "checks": checks,
    }


def run_creator_polish_coverage_qa(out_path: str | Path | None = None) -> dict[str, Any]:
    sections = {
        "preset_preview": _preset_preview_section(),
        "timeline_feedback": _timeline_feedback_section(),
        "product_polish_next": _product_polish_next_section(),
        "screenstudio_defaults": _screenstudio_section(),
        "capcut_quick_create": _capcut_section(),
        "render_result_smoke": _render_smoke_section(),
        "stability_hooks": _stability_section(),
    }
    passing = sum(1 for section in sections.values() if section.get("ok"))
    score = int(round(passing / max(1, len(sections)) * 100))
    report = {
        "ok": passing == len(sections),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "sections": len(sections),
            "passing_sections": passing,
            "score": score,
        },
        "sections": sections,
    }
    if out_path is not None:
        _write_json(Path(out_path), report)
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate creator-facing polish coverage.")
    parser.add_argument("--out", default="debugCapture/creator_polish_coverage_qa.json")
    args = parser.parse_args()
    out_path = ROOT / args.out
    report = run_creator_polish_coverage_qa(out_path)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

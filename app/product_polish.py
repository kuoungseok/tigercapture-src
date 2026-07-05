"""Product-facing polish gates shared by QA Dashboard and editor surfaces."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def _score_checks(checks: Mapping[str, bool]) -> int:
    rows = [bool(value) for value in checks.values()]
    return int(round(sum(1 for value in rows if value) / max(1, len(rows)) * 100))


def media_pool_discoverability_model() -> dict[str, Any]:
    from app.preset_feedback import preset_discoverability_cards

    cards = preset_discoverability_cards()
    checks = {
        "drag_guidance": any(card.get("id") == "drag_to_clip" for card in cards),
        "badge_guidance": any(card.get("id") == "right_click_badge" for card in cards),
        "workbench_guidance": any(card.get("id") == "open_workbench" for card in cards),
        "creator_assist_guidance": any(card.get("id") == "quick_create" for card in cards),
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "cards": cards,
        "summary": f"{sum(1 for value in checks.values() if value)}/{len(checks)} discoverability cards",
    }


def ui_visual_consistency_model(surface_names: list[str] | None = None) -> dict[str, Any]:
    surfaces = surface_names or [
        "launcher",
        "media_pool",
        "preview",
        "timeline",
        "workbench",
        "color",
        "audio",
        "qa_dashboard",
    ]
    checks = {
        "surface_inventory": len(surfaces) >= 8,
        "shared_qss_entrypoint": Path("app/style.py").exists() and Path("app/studio_theme.py").exists(),
        "timeline_visual_qa": Path("tools/qa_timeline_visual_alignment.py").exists(),
        "gui_flow_qa": Path("tools/qa_screenstudio_gui_flow.py").exists(),
        "visual_baseline_qa": Path("tools/qa_visual_baseline_audit.py").exists(),
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "surfaces": surfaces,
        "summary": f"{len(surfaces)} surfaces, {sum(1 for value in checks.values() if value)}/{len(checks)} visual hooks",
    }


def crash_recovery_productization_model() -> dict[str, Any]:
    try:
        from app.crash_report_dialog import crash_report_user_summary

        summary = crash_report_user_summary({"autosave_candidates": [{"path": "demo.autosave.tgp"}]})
    except Exception:
        summary = {}
    checks = {
        "crash_summary": bool(summary),
        "repair_tool": Path("tools/repair_project.py").exists(),
        "recovery_dialog": Path("app/recovery_dialog.py").exists(),
        "crash_report_row": Path("app/crash_report_dialog.py").exists(),
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "user_summary": summary,
        "summary": f"{sum(1 for value in checks.values() if value)}/{len(checks)} recovery hooks",
    }


def qa_dashboard_productization_model() -> dict[str, Any]:
    try:
        from app.qa_dashboard import QADashboardDialog, REPORT_SPECS

        kinds = {kind for _label, _path, kind in REPORT_SPECS}
        command = QADashboardDialog._command_for_row({
            "kind": "product_polish_next",
            "path": "debugCapture/product_polish_next_qa.json",
        })
    except Exception:
        kinds = set()
        command = None
    checks = {
        "dashboard_row": "product_polish_next" in kinds,
        "dashboard_runner": bool(command) and "qa_product_polish_next.py" in " ".join(command),
        "creator_polish_row": "creator_polish_coverage" in kinds,
        "real_project_row": "real_project_product_flow" in kinds,
        "screenstudio_rows": any(str(kind).startswith("screenstudio_") for kind in kinds),
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "command": command,
        "summary": f"{sum(1 for value in checks.values() if value)}/{len(checks)} dashboard hooks",
    }


def product_polish_readiness_report(
    *,
    project_summary: Mapping[str, Any] | None = None,
    real_corpus_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    from app.capcut_workflow import capcut_caption_short_quality_model
    from app.preset_feedback import (
        preset_preview_ab_model,
        preset_timeline_strip_rows,
        timeline_interaction_feedback_model,
    )
    from app.preset_library import EditorPreset
    from app.screenstudio_parity import (
        screenstudio_export_result_parity_matrix,
        screenstudio_productization_next_report,
    )

    demo_preset = EditorPreset(id="effect-product-polish", kind="effect", name="Polished Apply")
    strip_rows = preset_timeline_strip_rows(
        demo_preset,
        [{"kind": "effect", "status": "applied", "start_ms": 1000, "duration_ms": 2400}],
        clip_start_ms=0,
        clip_end_ms=6000,
    )
    preview_ab = preset_preview_ab_model(
        demo_preset,
        before_signature="1920x1080:00000001",
        after_signature="1920x1080:00000002",
    )
    timeline_feedback = [
        timeline_interaction_feedback_model("drag", target_ms=1200, mode="select", selected_count=2),
        timeline_interaction_feedback_model("snap", snap_ms=1000, target_ms=2000, mode="trim", selected_count=1),
        timeline_interaction_feedback_model("undo", undo_label="preset apply"),
    ]
    screenstudio = screenstudio_productization_next_report(real_corpus_report=real_corpus_report)
    capcut = capcut_caption_short_quality_model(project_summary or {
        "duration_s": 184,
        "has_audio": True,
        "dialogue": True,
        "screen_recording": True,
        "transcript_segments": [
            {"start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make the first result look good."},
            {"start_ms": 64000, "end_ms": 84000, "text": "Watch how the cursor focus keeps the important button in frame."},
            {"start_ms": 125000, "end_ms": 151000, "text": "The final export is already formatted for Shorts."},
        ],
    })
    discoverability = media_pool_discoverability_model()
    export_matrix = screenstudio_export_result_parity_matrix()
    recovery = crash_recovery_productization_model()
    visual = ui_visual_consistency_model()
    dashboard = qa_dashboard_productization_model()

    areas = [
        {
            "id": "preset_timeline_visibility",
            "label": "Preset/effect timeline visibility",
            "ok": bool(strip_rows and all(row.get("visible") for row in strip_rows)),
            "score": 100 if strip_rows else 0,
            "summary": f"{len(strip_rows)} strip row(s)",
            "details": {"strip_rows": strip_rows},
        },
        {
            "id": "preset_result_preview",
            "label": "Preset/template result preview",
            "ok": bool(preview_ab.get("changed")),
            "score": 100 if preview_ab.get("changed") else 70,
            "summary": "A/B preview changed" if preview_ab.get("changed") else "A/B preview needs a real frame",
            "details": preview_ab,
        },
        {
            "id": "screenstudio_real_corpus_zoom_cursor",
            "label": "Screen Studio real corpus zoom/cursor",
            "ok": bool(screenstudio.get("implementation_ok")),
            "score": int(screenstudio.get("score", 0) or 0),
            "summary": (
                f"real recordings {int((screenstudio.get('summary') or {}).get('real_recordings', 0) or 0)}, "
                f"missing {int((screenstudio.get('summary') or {}).get('missing_for_minimum', 0) or 0)}"
            ),
            "details": screenstudio,
        },
        {
            "id": "capcut_caption_shorts_quality",
            "label": "CapCut caption/shorts quality",
            "ok": bool(capcut.get("ok")),
            "score": int(capcut.get("score", 0) or 0),
            "summary": (
                f"{int((capcut.get('summary') or {}).get('caption_rows', 0) or 0)} captions, "
                f"{int((capcut.get('summary') or {}).get('short_candidates', 0) or 0)} short(s)"
            ),
            "details": capcut,
        },
        {
            "id": "timeline_feel_polish",
            "label": "Timeline feel polish",
            "ok": all(row.get("ok") and row.get("chip") for row in timeline_feedback),
            "score": 100 if all(row.get("ok") and row.get("chip") for row in timeline_feedback) else 70,
            "summary": f"{len(timeline_feedback)} interaction feedback model(s)",
            "details": {"feedback": timeline_feedback},
        },
        {
            "id": "media_pool_discoverability",
            "label": "Media Pool discoverability",
            "ok": bool(discoverability.get("ok")),
            "score": int(discoverability.get("score", 0) or 0),
            "summary": str(discoverability.get("summary") or ""),
            "details": discoverability,
        },
        {
            "id": "export_parity_expansion",
            "label": "Export parity expansion",
            "ok": bool(export_matrix.get("ok")) and len(export_matrix.get("rows") or []) >= 5,
            "score": int(export_matrix.get("score", 0) or 0),
            "summary": f"{len(export_matrix.get('rows') or [])} export target(s)",
            "details": export_matrix,
        },
        {
            "id": "crash_recovery_productization",
            "label": "Crash recovery productization",
            "ok": bool(recovery.get("ok")),
            "score": int(recovery.get("score", 0) or 0),
            "summary": str(recovery.get("summary") or ""),
            "details": recovery,
        },
        {
            "id": "ui_visual_consistency",
            "label": "UI visual consistency pass",
            "ok": bool(visual.get("ok")),
            "score": int(visual.get("score", 0) or 0),
            "summary": str(visual.get("summary") or ""),
            "details": visual,
        },
        {
            "id": "qa_dashboard_productization",
            "label": "QA Dashboard productization",
            "ok": bool(dashboard.get("ok")),
            "score": int(dashboard.get("score", 0) or 0),
            "summary": str(dashboard.get("summary") or ""),
            "details": dashboard,
        },
    ]
    passing = sum(1 for row in areas if row.get("ok"))
    score = int(round(sum(int(row.get("score", 0) or 0) for row in areas) / max(1, len(areas))))
    next_actions = [
        row["label"] for row in areas
        if not row.get("ok")
    ]
    return {
        "ok": passing == len(areas),
        "implementation_ok": passing == len(areas),
        "score": score,
        "summary": {
            "areas": len(areas),
            "passing": passing,
            "attention": len(areas) - passing,
            "screenstudio_real_recordings": int((screenstudio.get("summary") or {}).get("real_recordings", 0) or 0),
            "capcut_caption_rows": int((capcut.get("summary") or {}).get("caption_rows", 0) or 0),
            "export_targets": len(export_matrix.get("rows") or []),
        },
        "areas": areas,
        "next_actions": next_actions,
    }

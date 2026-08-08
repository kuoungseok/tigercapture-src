"""In-app QA dashboard for product-level regression reports."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.release_evidence_sprint import (
    release_evidence_action_targets,
    release_evidence_next_ai_case_target,
    release_evidence_next_items,
    release_evidence_next_screenstudio_capture_target,
    release_evidence_progress,
)
from app.review_automation.dev_gate import review_automation_dev_enabled
from app.review_automation.paths import (
    DEFAULT_REVIEW_OUTPUT_DIR,
    DEFAULT_REVIEW_QA_REPORT,
    DEFAULT_REVIEW_REPORT,
    DEFAULT_REVIEW_SAMPLE_REPORT,
    DEFAULT_REVIEW_SAMPLE_ROOT,
)
from app.subprocess_utils import hidden_subprocess_kwargs


HISTORY_PATH = Path("debugCapture/qa_dashboard_history.json")
REVIEW_AUTOMATION_KINDS: tuple[str, ...] = (
    "review_sample_resources",
    "review_automation",
    "review_automation_qa",
)
EVIDENCE_REFRESH_KINDS: tuple[str, ...] = (
    "screenstudio_real_corpus",
    "ai_edit_corpus_quality",
    "broadcast_platform_e2e",
    "broadcast_release_readiness",
    "release_evidence_sprint",
    "release_gap_closure",
    "final_product_readiness",
)


def _report_spec_path(path: str | Path) -> str:
    raw = Path(path)
    if not raw.is_absolute():
        return raw.as_posix()
    try:
        return raw.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except Exception:
        return str(raw)


REPORT_SPECS: tuple[tuple[str, str, str], ...] = (
    ("Final Product Readiness", "debugCapture/final_product_readiness_qa.json", "final_product_readiness"),
    ("Broadcast Release Readiness", "debugCapture/broadcast_release_readiness_qa.json", "broadcast_release_readiness"),
    ("Broadcast Platform E2E", "debugCapture/broadcast_platform_e2e_qa.json", "broadcast_platform_e2e"),
    ("Productization Loop", "debugCapture/productization_loop_qa.json", "productization"),
    ("Creator Polish Coverage", "debugCapture/creator_polish_coverage_qa.json", "creator_polish_coverage"),
    ("Product Polish Next", "debugCapture/product_polish_next_qa.json", "product_polish_next"),
    ("Professional Pipeline Next", "debugCapture/professional_pipeline_next_qa.json", "professional_pipeline_next"),
    ("Professional Runtime Next", "debugCapture/professional_runtime_next_qa.json", "professional_runtime_next"),
    ("Real Project Product Flow", "debugCapture/real_project_product_flow_qa.json", "real_project_product_flow"),
    ("Commercial Expansion", "debugCapture/commercial_expansion_qa.json", "commercial_expansion"),
    ("Public Positioning", "debugCapture/public_positioning_qa.json", "public_positioning"),
    ("CapCut Creator Workflow", "debugCapture/capcut_creator_workflow_qa.json", "capcut_creator_workflow"),
    ("CapCut Parity Next", "debugCapture/capcut_parity_next_qa.json", "capcut_parity_next"),
    ("CapCut Publish Review", "debugCapture/capcut_publish_review_qa.json", "capcut_publish_review"),
    ("CapCut Quick Result", "debugCapture/capcut_quick_result_qa.json", "capcut_quick_result"),
    ("CapCut Voice Workflow", "debugCapture/capcut_voice_workflow_qa.json", "capcut_voice_workflow"),
    ("Voice Lab Sidecar", "debugCapture/voice_lab_sidecar_qa.json", "voice_lab_sidecar"),
    ("CapCut Prompt Edit", "debugCapture/capcut_prompt_edit_qa.json", "capcut_prompt_edit"),
    ("CapCut Collab Handoff", "debugCapture/capcut_collab_handoff_qa.json", "capcut_collab_handoff"),
    ("CapCut Cloud Handoff", "debugCapture/capcut_cloud_handoff_qa.json", "capcut_cloud_handoff"),
    ("Creator Asset Packs", "debugCapture/creator_asset_packs_qa.json", "creator_asset_packs"),
    ("Localization Audit", "debugCapture/localization_audit_qa.json", "localization_audit"),
    ("Review Sample Resources", _report_spec_path(DEFAULT_REVIEW_SAMPLE_REPORT), "review_sample_resources"),
    ("Review Automation", _report_spec_path(DEFAULT_REVIEW_REPORT), "review_automation"),
    ("Review Automation QA", _report_spec_path(DEFAULT_REVIEW_QA_REPORT), "review_automation_qa"),
    ("Local ML Backend", "debugCapture/local_ml_backend_qa.json", "local_ml_backend"),
    ("AI Edit Corpus Quality", "debugCapture/ai_edit_corpus_quality_qa.json", "ai_edit_corpus_quality"),
    ("AI Edit Corpus Intake", "debugCapture/ai_edit_corpus_intake_qa.json", "ai_edit_corpus_intake"),
    ("Preset Application", "debugCapture/preset_application_corpus_auto.json", "preset_application"),
    ("Preset Application UI", "debugCapture/preset_application_corpus_ui.json", "preset_application"),
    ("Color/Audio Accuracy", "debugCapture/color_audio_accuracy_qa.json", "color_audio"),
    ("Timeline Fuzzer", "debugCapture/timeline_fuzzer_qa.json", "timeline_fuzzer"),
    ("Timeline Alignment", "debugCapture/timeline_alignment_qa.json", "timeline_alignment"),
    ("Timeline Visual Alignment", "debugCapture/timeline_visual_alignment_qa/timeline_visual_alignment_report.json", "timeline_visual_alignment"),
    ("Timeline Drag Feedback", "debugCapture/timeline_drag_feedback_qa/timeline_drag_feedback_report.json", "timeline_drag_feedback"),
    ("Timeline Edit Gestures", "debugCapture/timeline_edit_gestures_qa/timeline_edit_gestures_report.json", "timeline_edit_gestures"),
    ("Timeline Hover Affordance", "debugCapture/timeline_hover_affordance_qa/timeline_hover_affordance_report.json", "timeline_hover_affordance"),
    ("Timeline Preset Visibility", "debugCapture/timeline_preset_visibility_qa/timeline_preset_visibility_report.json", "timeline_preset_visibility"),
    ("NLE Readiness", "debugCapture/nle_readiness_qa.json", "nle_readiness"),
    ("Creative Layer Readiness", "debugCapture/creative_layer_readiness_qa.json", "creative_layer_readiness"),
    ("Long Project Stress", "debugCapture/long_project_stress_qa.json", "long_project_stress"),
    ("Actor Lane Workflow", "debugCapture/actor_lane_workflow_qa.json", "actor_workflow"),
    ("Actor Loading UX", "debugCapture/actor_loading_ux_qa.json", "actor_loading_ux"),
    ("Actor Overnight QA", "debugCapture/actor_overnight_qa.json", "actor_overnight_qa"),
    ("Node Graph Fuzzer", "debugCapture/node_graph_fuzzer_qa.json", "node_graph_fuzzer"),
    ("Node Graph UI Fuzzer", "debugCapture/node_graph_ui_fuzzer_qa.json", "node_graph_ui_fuzzer"),
    ("Actor Corpus", "debugCapture/actor_corpus_status.json", "actor_status"),
    ("Actor Mass Compat", "debugCapture/actor_mass_compat_qa.json", "actor_mass_compat"),
    ("Actor Render QA", "debugCapture/actor_render_qa.json", "actor_render"),
    ("Project QA / Professional Readiness", "debugCapture/project_qa_report.json", "project_qa"),
    ("Editor E2E Smoke", "debugCapture/editor_e2e_smoke_report.json", "editor_e2e_smoke"),
    ("Editor Export Bake", "debugCapture/editor_export_bake_qa.json", "editor_export_bake"),
    ("GPU Preview Pixel Collision", "debugCapture/gpu_preview_pixel_collision_qa.json", "gpu_preview_pixel_collision"),
    ("AR/PBR Export Bake", "debugCapture/ar_pbr_export_bake_qa.json", "ar_pbr_export_bake"),
    ("GPU Export Parity Matrix", "debugCapture/gpu_export_parity_matrix_qa.json", "gpu_export_parity_matrix"),
    ("AR/PBR Attachment Stability", "debugCapture/ar_pbr_attachment_stability_qa.json", "ar_pbr_attachment_stability"),
    ("Visual Regression", "debugCapture/visual_regression/visual_regression_report.json", "visual"),
    ("Visual Baseline Audit", "debugCapture/visual_baseline_audit.json", "visual_baseline"),
    ("UI Visual Baseline Refresh", "debugCapture/ui_visual_baseline_refresh.json", "ui_visual_baseline_refresh"),
    ("Micro Interactions", "debugCapture/micro_interactions_qa.json", "micro_interactions"),
    ("Screen Studio Auto Polish", "debugCapture/screenstudio_auto_polish_qa.json", "screenstudio_auto_polish"),
    ("Screen Studio Naturalness", "debugCapture/screenstudio_naturalness_qa.json", "screenstudio_naturalness"),
    ("Screen Studio Export Handoff", "debugCapture/screenstudio_export_handoff_qa.json", "screenstudio_export_handoff"),
    ("Screen Studio Parity Gap", "debugCapture/screenstudio_parity_gap_qa.json", "screenstudio_parity_gap"),
    ("Screen Studio Real Corpus", "debugCapture/screenstudio_real_recording_corpus_qa.json", "screenstudio_real_corpus"),
    ("Screen Studio Sidecar Intake", "debugCapture/screenstudio_sidecar_intake_qa.json", "screenstudio_sidecar_intake"),
    ("Screen Studio Productization", "debugCapture/screenstudio_productization_next_qa.json", "screenstudio_productization_next"),
    ("Screen Studio Manual Zoom", "debugCapture/screenstudio_manual_zoom_qa.json", "screenstudio_manual_zoom"),
    ("Screen Studio Render Smoke", "debugCapture/screenstudio_render_result_smoke/screenstudio_render_result_smoke_report.json", "screenstudio_render_smoke"),
    ("Screen Studio Visual Polish", "debugCapture/screenstudio_visual_polish/screenstudio_visual_polish_report.json", "screenstudio_visual_polish"),
    ("Screen Studio App Flow", "debugCapture/screenstudio_app_flow/screenstudio_app_flow_report.json", "screenstudio_app_flow"),
    ("Screen Studio GUI Flow", "debugCapture/screenstudio_gui_flow/screenstudio_gui_flow_report.json", "screenstudio_gui_flow"),
    ("Release Gap Closure", "debugCapture/release_gap_closure_qa.json", "release_gap_closure"),
    ("Release Evidence Sprint", "debugCapture/release_evidence_sprint_qa.json", "release_evidence_sprint"),
    ("Latest Crash Report", "runtime_logs/crash_report_latest.json", "crash_report"),
)

if not review_automation_dev_enabled():
    REPORT_SPECS = tuple(row for row in REPORT_SPECS if row[2] not in REVIEW_AUTOMATION_KINDS)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _mtime(path: Path) -> str:
    try:
        import datetime as _dt

        return _dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "-"


def _latest_matching(pattern: str) -> Path | None:
    root = Path("debugCapture")
    if not root.exists():
        return None
    rows = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return rows[0] if rows else None


def _resolve_report_path(raw_path: str) -> Path | None:
    path = Path(raw_path)
    if str(raw_path).replace("\\", "/").startswith("runtime_logs/"):
        try:
            from app.paths import runtime_log_dir

            runtime_path = runtime_log_dir() / path.name
            return runtime_path if runtime_path.exists() else None
        except Exception:
            return None
    if path.exists():
        return path
    if path.name in {"visual_regression_report.json", "layout_report.json"}:
        return _latest_matching(f"**/{path.name}")
    return None


def _summary_for(kind: str, report: dict[str, Any]) -> tuple[bool, str, list[str]]:
    if not report:
        return False, "missing", ["No report file found."]
    ok = bool(report.get("ok", True))
    lines: list[str] = []
    if kind == "preset_application":
        projects = list(report.get("projects", []) or [])
        parity_ok = sum(1 for row in projects if dict(row.get("export_parity", {}) or {}).get("ok"))
        summary = f"{len(projects)} projects, export parity {parity_ok}/{len(projects)}"
        for row in projects[:6]:
            parity = dict(row.get("export_parity", {}) or {})
            lines.append(
                f"- {Path(str(row.get('path', ''))).name}: "
                f"{len(row.get('plan_ids', []) or [])} preset(s), "
                f"targets={', '.join(parity.get('bake_targets', []) or []) or 'none'}"
            )
        return ok, summary, lines
    if kind == "creator_polish_coverage":
        summary = report.get("summary", {}) or {}
        sections = report.get("sections", {}) or {}
        if isinstance(sections, dict):
            for name, section in sections.items():
                if not isinstance(section, dict):
                    continue
                mark = "OK" if section.get("ok") else "ATTN"
                lines.append(f"[{mark}] {name}: {section.get('summary', '')}")
        return ok, (
            f"{int(summary.get('passing_sections', 0) or 0)}/"
            f"{int(summary.get('sections', 0) or 0)} sections, "
            f"score {int(summary.get('score', 0) or 0)}/100"
        ), lines
    if kind == "product_polish_next":
        summary = report.get("summary", {}) or {}
        for area in list(report.get("areas", []) or [])[:10]:
            if not isinstance(area, dict):
                continue
            mark = "OK" if area.get("ok") else "ATTN"
            lines.append(
                f"[{mark}] {area.get('label', area.get('id', 'area'))}: "
                f"{area.get('score', 0)}/100 - {area.get('summary', '')}"
            )
        for action in list(report.get("next_actions", []) or [])[:6]:
            lines.append(f"- Next: {action}")
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"passing {int(summary.get('passing', 0) or 0)}/"
            f"{int(summary.get('areas', 0) or 0)}, "
            f"exports {int(summary.get('export_targets', 0) or 0)}"
        ), lines
    if kind == "professional_pipeline_next":
        summary = report.get("summary", {}) or {}
        for name, passed in (report.get("checks", {}) or {}).items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        parity = report.get("parity", {}) or {}
        category_scores = parity.get("category_scores", {}) if isinstance(parity, dict) else {}
        if isinstance(category_scores, dict):
            lines.append(
                "- parity: "
                + ", ".join(f"{key}={value}" for key, value in sorted(category_scores.items()))
            )
        return ok, (
            f"color {int(summary.get('color_score', 0) or 0)}, "
            f"audio {int(summary.get('audio_score', 0) or 0)}, "
            f"vfx {int(summary.get('vfx_score', 0) or 0)}, "
            f"pro-deliver {int(summary.get('professional_deliver_jobs', 0) or 0)}, "
            f"ml {int(summary.get('local_ml_features', 0) or 0)}, "
            f"stress {int(summary.get('audio_stress_tracks', 0) or 0)}, "
            f"hw {int(summary.get('hardware_devices', 0) or 0)}"
        ), lines
    if kind == "professional_runtime_next":
        summary = report.get("summary", {}) or {}
        for name, passed in (report.get("checks", {}) or {}).items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        return ok, (
            f"delta {float(summary.get('color_delta', 0.0) or 0.0):.2f}, "
            f"mask {float(summary.get('mask_coverage', 0.0) or 0.0):.3f}, "
            f"vfx {int(summary.get('vfx_nodes', 0) or 0)}, "
            f"ml {int(summary.get('local_ml_detections', 0) or 0)}, "
            f"stress {int(summary.get('audio_stress_tracks', 0) or 0)}"
        ), lines
    if kind == "real_project_product_flow":
        summary = report.get("summary", {}) or {}
        for name, passed in (report.get("checks", {}) or {}).items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        for row in list(report.get("projects", []) or [])[:6]:
            if isinstance(row, dict):
                lines.append(
                    f"- {Path(str(row.get('path', ''))).name}: "
                    f"{len(row.get('plan_ids', []) or [])} preset(s), "
                    f"parity={'OK' if dict(row.get('export_parity') or {}).get('ok') else 'ATTN'}"
                )
        for action in list(report.get("next_actions", []) or [])[:4]:
            lines.append(f"- Next: {action}")
        return ok, (
            f"{int(summary.get('projects', 0) or 0)} project(s), "
            f"parity {int(summary.get('preset_parity_ready', 0) or 0)}, "
            f"render {int(summary.get('render_frames', 0) or 0)} frame(s)"
        ), lines
    if kind == "color_audio":
        summary = report.get("summary", {}) or {}
        lines.append(f"Checks: {int(summary.get('checks', 0) or 0)}")
        lines.append(f"Failures: {int(summary.get('failures', 0) or 0)}")
        sections = summary.get("sections", {}) or {}
        if isinstance(sections, dict):
            for name, section in sections.items():
                if isinstance(section, dict):
                    lines.append(f"- {name}: {section.get('checks', 0)} check(s), {section.get('failures', 0)} failure(s)")
        return ok, f"{summary.get('checks', 0)} checks, {summary.get('failures', 0)} failures", lines
    if kind == "timeline_fuzzer":
        summary = report.get("summary", {}) or {}
        lines.extend(str(v) for v in report.get("failures", [])[:8])
        return ok, f"{summary.get('iterations', 0)} iterations, {summary.get('failures', 0)} failures", lines
    if kind == "nle_readiness":
        readiness = report.get("report", {}) or {}
        for row in list(readiness.get("rows", []) or [])[:10]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"[{str(row.get('status', '')).upper()}] {row.get('label', row.get('id'))}: "
                f"{row.get('score', 0)}/100"
            )
        for action in list(readiness.get("next_actions", []) or [])[:6]:
            lines.append(f"- Next: {action}")
        return ok, (
            f"score {readiness.get('score', 0)}/100, "
            f"professional claim={'allowed' if readiness.get('professional_nle_claim_ok') else 'blocked'}, "
            f"blockers {len(readiness.get('blockers', []) or [])}"
        ), lines
    if kind == "creative_layer_readiness":
        readiness = report.get("report", {}) or {}
        for row in list(readiness.get("rows", []) or [])[:10]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"[{str(row.get('status', '')).upper()}] {row.get('label', row.get('id'))}: "
                f"{row.get('score', 0)}/100"
            )
        for action in list(readiness.get("next_actions", []) or [])[:6]:
            lines.append(f"- Next: {action}")
        return ok, (
            f"score {readiness.get('score', 0)}/100, "
            f"creative-suite claim={'allowed' if readiness.get('full_creative_suite_claim_ok') else 'blocked'}, "
            f"blockers {len(readiness.get('blockers', []) or [])}"
        ), lines
    if kind == "timeline_alignment":
        summary = report.get("summary", {}) or {}
        for row in list(report.get("rows", []) or [])[:8]:
            if isinstance(row, dict):
                lines.append(f"- {row.get('ms')} ms drift={row.get('drift')}")
        return ok, f"max drift {summary.get('max_abs_drift_px', 0)} px", lines
    if kind == "timeline_visual_alignment":
        summary = report.get("summary", {}) or {}
        lines.append(f"Screenshot: {summary.get('screenshot', '')}")
        lines.append(f"Measured: {report.get('measured', {})}")
        lines.append(f"Drift: {report.get('drift', {})}")
        return ok, f"visual max drift {summary.get('max_abs_drift_px', 0)} px", lines
    if kind == "long_project_stress":
        summary = report.get("summary", {}) or {}
        for name, passed in (report.get("checks", {}) or {}).items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        return ok, (
            f"{summary.get('duration_ms', 0)} ms, "
            f"V/A clips {summary.get('video_clips', 0)}/{summary.get('audio_clips', 0)}, "
            f"recovery={summary.get('recovery_level', '-')}"
        ), lines
    if kind == "actor_workflow":
        summary = report.get("summary", {}) or {}
        for row in list(report.get("rows", []) or [])[:8]:
            if isinstance(row, dict):
                lines.append(
                    f"- {row.get('kind')}: double-click={row.get('double_click_fired')} "
                    f"hit={row.get('hit_test_ok')} playhead_x={row.get('playhead_x')}"
                )
        return ok, f"{summary.get('rows', 0)} lane(s), {summary.get('failures', 0)} failures", lines
    if kind == "actor_loading_ux":
        areas = report.get("areas", {}) or {}
        for key, desc in areas.items():
            lines.append(f"- {key}: {desc}")
        issues = report.get("issues", []) or []
        for issue in issues[:8]:
            if isinstance(issue, dict):
                lines.append(f"! {issue.get('area', '-')}: {issue.get('code', 'issue')}")
        return ok, f"{len(issues)} loading UX issue(s)", lines
    if kind == "actor_overnight_qa":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        for name, passed in checks.items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        for row in list(report.get("failures", []) or [])[:8]:
            if isinstance(row, dict):
                lines.append(f"! {row.get('kind', '-')}: {Path(str(row.get('path', ''))).name} {row.get('status', '-')}")
        return ok, (
            f"planned {summary.get('planned_candidates', 0)}, "
            f"rendered {summary.get('rendered', 0)}, failures {summary.get('failures', 0)}"
        ), lines
    if kind in {"node_graph_fuzzer", "node_graph_ui_fuzzer"}:
        summary = report.get("summary", {}) or {}
        lines.extend(str(v) for v in report.get("failures", [])[:8])
        return ok, f"{summary.get('iterations', 0)} iterations, {summary.get('failures', 0)} failures", lines
    if kind in {"actor_status", "actor_render", "actor_mass_compat"}:
        summary = report.get("summary", {}) or {}
        if isinstance(summary, dict):
            for key, value in summary.items():
                if isinstance(value, (str, int, float, bool)):
                    lines.append(f"- {key}: {value}")
                elif isinstance(value, dict):
                    lines.append(f"- {key}: " + ", ".join(f"{k}={v}" for k, v in list(value.items())[:6]))
        issues = report.get("issues", []) or []
        for issue in issues[:8]:
            if isinstance(issue, dict):
                lines.append(f"! {issue.get('code', 'issue')}: {issue.get('message', '')}")
        return ok, f"{len(issues)} issue(s)", lines
    if kind == "project_qa":
        projects = list(report.get("projects", []) or [])
        readiness_summary = report.get("professional_readiness_summary", {}) or {}
        if not projects and isinstance(report.get("professional_readiness"), dict):
            projects = [report]
        for row in projects[:8]:
            if not isinstance(row, dict):
                continue
            readiness = row.get("professional_readiness", {}) or {}
            sections = readiness.get("sections", {}) or {}
            parity = sections.get("resolve_post_pipeline_parity", {}) if isinstance(sections, dict) else {}
            lines.append(
                f"- {Path(str(row.get('project', report.get('project', 'project')))).name}: "
                f"readiness={int(readiness.get('score', 0) or 0)}, "
                f"resolve-parity={int(parity.get('score', 0) or 0)}"
            )
            if isinstance(parity, dict):
                category_scores = parity.get("category_scores", {}) or {}
                if isinstance(category_scores, dict):
                    compact = ", ".join(f"{key}={int(value or 0)}" for key, value in list(category_scores.items())[:6])
                    if compact:
                        lines.append(f"  parity: {compact}")
                top_actions = [str(v) for v in parity.get("top_actions", []) or [] if str(v)]
                for action in top_actions[:3]:
                    lines.append(f"  next: {action}")
                depth_cards = [
                    card for card in list(parity.get("professional_depth_cards", []) or [])
                    if isinstance(card, dict)
                ]
                for card in depth_cards[:3]:
                    lines.append(
                        "  depth: "
                        f"{card.get('competitor', card.get('id', 'workflow'))} "
                        f"{int(card.get('score', 0) or 0)} "
                        f"{card.get('current_level', '')}"
                    )
                vfx_graph_qa = parity.get("vfx_graph_qa")
                if isinstance(vfx_graph_qa, dict) and vfx_graph_qa:
                    lines.append(
                        "  vfx-graph: "
                        f"{'OK' if vfx_graph_qa.get('ok') else 'Review'} "
                        f"graphs={int(vfx_graph_qa.get('graph_count', 0) or 0)} "
                        f"nodes={int(vfx_graph_qa.get('node_count', 0) or 0)} "
                        f"warnings={len(list(vfx_graph_qa.get('warnings', []) or []))}"
                    )
        resolve = readiness_summary.get("resolve_parity", {}) if isinstance(readiness_summary, dict) else {}
        if isinstance(resolve, dict) and resolve:
            lines.append(f"- Resolve parity avg: {resolve.get('avg_score', 0)} min: {resolve.get('min_score', 0)}")
            category_min = resolve.get("category_min_scores", {}) or {}
            if isinstance(category_min, dict):
                lines.append(
                    "- Resolve category mins: "
                    + ", ".join(f"{key}={value}" for key, value in sorted(category_min.items()))
                )
        project_count = int(report.get("project_count", len(projects)) or len(projects))
        avg = readiness_summary.get("avg_score", 0) if isinstance(readiness_summary, dict) else 0
        parity_avg = resolve.get("avg_score", 0) if isinstance(resolve, dict) else 0
        return ok, f"{project_count} project(s), readiness avg {avg}, resolve parity avg {parity_avg}", lines
    if kind == "editor_e2e_smoke":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        metrics = report.get("metrics", {}) or {}
        for name, passed in list(checks.items())[:12]:
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        import_metrics = metrics.get("import_editor", {}) if isinstance(metrics, dict) else {}
        actor_metrics = metrics.get("loaded_actor_project", {}) if isinstance(metrics, dict) else {}
        if isinstance(import_metrics, dict):
            lines.append(
                "- import flow: "
                f"tracks={import_metrics.get('tracks', 0)}, "
                f"media={import_metrics.get('media_pool_items', 0)}, "
                f"preview={dict(import_metrics.get('preview_rgb', {}) or {}).get('non_dark_ratio', '-')}"
            )
        if isinstance(actor_metrics, dict):
            lines.append(
                "- actor project: "
                f"spine={actor_metrics.get('spine_tracks', 0)}, "
                f"live2d={actor_metrics.get('live2d_tracks', 0)}, "
                f"preview={dict(actor_metrics.get('preview_rgb', {}) or {}).get('non_dark_ratio', '-')}"
            )
        return ok, (
            f"{int(summary.get('passing', 0) or 0)}/"
            f"{int(summary.get('checks', 0) or 0)} checks, "
            f"{int(summary.get('screenshots', 0) or 0)} screenshot(s)"
        ), lines
    if kind == "editor_export_bake":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        diff = report.get("diff", {}) or {}
        processed_probe = report.get("processed_probe", {}) or {}
        for name, passed in list(checks.items())[:12]:
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        if isinstance(diff, dict):
            lines.append(
                "- output diff: "
                f"mean={diff.get('mean_abs_diff', 0)}, "
                f"changed={diff.get('changed_pixel_ratio', 0)}"
            )
        if isinstance(processed_probe, dict):
            lines.append(
                "- processed frame: "
                f"{processed_probe.get('width', 0)}x{processed_probe.get('height', 0)}, "
                f"pink={processed_probe.get('pink_pixels', 0)}, "
                f"dark={processed_probe.get('dark_ui_pixels', 0)}"
            )
        return ok, (
            f"{int(summary.get('passing', 0) or 0)}/"
            f"{int(summary.get('checks', 0) or 0)} checks, "
            f"diff {summary.get('mean_abs_diff', 0)}, "
            f"changed {summary.get('changed_pixel_ratio', 0)}"
        ), lines
    if kind == "gpu_export_parity_matrix":
        summary = report.get("summary", {}) or {}
        for row in list(report.get("matrix", []) or [])[:10]:
            if not isinstance(row, dict):
                continue
            mark = "OK" if row.get("ok") else "GAP"
            lines.append(
                f"[{mark}] {row.get('feature', '-')}: "
                f"preview={row.get('preview')}, export={row.get('export')}"
            )
        for gap in list(report.get("coverage_gaps", []) or [])[:6]:
            if isinstance(gap, dict):
                lines.append(f"- gap: {gap.get('feature', '-')} - {gap.get('note', '')}")
        return ok, (
            f"{int(summary.get('passing', 0) or 0)}/"
            f"{int(summary.get('features', 0) or 0)} features, "
            f"gaps {int(summary.get('coverage_gaps', 0) or 0)}, "
            f"blocking {int(summary.get('blocking_failures', 0) or 0)}, "
            f"release_ready={bool(report.get('release_ready'))}"
        ), lines
    if kind == "ar_pbr_export_bake":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        for name, passed in list(checks.items())[:12]:
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        diagnostics = report.get("diagnostics", {}) or {}
        if isinstance(diagnostics, dict):
            lines.append(
                "- renderer: "
                f"{diagnostics.get('mode', '-')}, "
                f"tracks={diagnostics.get('rendered_track_count', 0)}, "
                f"fallback={bool(diagnostics.get('fallback'))}"
            )
            lines.append(
                "- textures: "
                f"maps={diagnostics.get('texture_map_count', 0)}, "
                f"materials={diagnostics.get('texture_material_count', 0)}, "
                f"tinted={diagnostics.get('texture_tinted_triangle_count', 0)}, "
                f"sampled={diagnostics.get('texture_sampled_triangle_count', 0)}"
            )
        return ok, (
            f"{int(summary.get('passing', 0) or 0)}/"
            f"{int(summary.get('checks', 0) or 0)} checks, "
            f"diff {summary.get('mean_abs_diff', 0)}, "
            f"changed {summary.get('changed_pixel_ratio', 0)}, "
            f"ar pixels {int(summary.get('orange_pixels', 0) or 0)}, "
            f"texture maps {int(summary.get('texture_map_count', 0) or 0)}, "
            f"sampled {int(summary.get('texture_sampled_triangle_count', 0) or 0)}"
        ), lines
    if kind == "ar_pbr_attachment_stability":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        for name, passed in list(checks.items())[:10]:
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        for row in list(report.get("frames", []) or [])[:4]:
            if isinstance(row, dict):
                lines.append(
                    "- frame "
                    f"{row.get('time_ms', 0)}ms: "
                    f"center error={row.get('center_error_px', '-')}, "
                    f"tri={row.get('triangle_count', 0)}, "
                    f"shadow={row.get('shadow_triangle_count', 0)}, "
                    f"reflection={row.get('reflection_triangle_count', 0)}"
                )
        occlusion = report.get("occlusion_probe", {}) or {}
        if isinstance(occlusion, dict):
            lines.append(
                "- occlusion: "
                f"visible={occlusion.get('visible_triangle_count', 0)}, "
                f"occluded={occlusion.get('occluded_triangle_count', 0)}"
            )
        affine = report.get("tracking_transform_probe", {}) or {}
        if isinstance(affine, dict):
            lines.append(
                "- affine tracking: "
                f"scale={affine.get('scale_ratio', '-')}, "
                f"rotation={affine.get('rotation_delta_deg', '-')}deg, "
                f"{'OK' if affine.get('ok') else 'FAIL'}"
            )
        return ok, (
            f"{int(summary.get('frame_count', 0) or 0)} frame(s), "
            f"max drift {summary.get('max_center_error_px', 0)}px, "
            f"tri {int(summary.get('triangle_count', 0) or 0)}, "
            f"occ {int(summary.get('occluded_triangle_count', 0) or 0)}, "
            f"scale {summary.get('tracked_scale_ratio', '-')}, "
            f"rot {summary.get('tracked_rotation_delta_deg', '-')}deg"
        ), lines
    if kind == "visual":
        failures = list(report.get("failures", []) or report.get("issues", []) or [])
        lines.extend(json.dumps(row, ensure_ascii=False, default=str) for row in failures[:6])
        return ok, f"{len(failures)} visual issue(s)", lines
    if kind == "final_product_readiness":
        summary = report.get("summary", {}) or {}
        for area in list(report.get("areas", []) or [])[:10]:
            if not isinstance(area, dict):
                continue
            level = str(area.get("level") or "attention").upper()
            lines.append(
                f"[{level}] {area.get('label', area.get('id'))}: "
                f"{area.get('score', 0)}/100 - {area.get('summary', '')}"
            )
        for action in list(report.get("next_actions", []) or [])[:8]:
            lines.append(f"- Next: {action}")
        ready = bool(report.get("release_ready"))
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"ready {int(summary.get('ready', 0) or 0)}/{int(summary.get('areas', 0) or 0)}, "
            f"attention {int(summary.get('attention', 0) or 0)}, "
            f"release={'ready' if ready else 'attention'}"
        ), lines
    if kind == "ai_edit_corpus_quality":
        summary = report.get("summary", {}) or {}
        provider = report.get("provider", {}) or {}
        for blocker in list(report.get("claim_blockers", []) or [])[:8]:
            lines.append(f"- Claim blocker: {blocker}")
        lines.append(
            f"- Safe MVP: {'OK' if report.get('safe_mvp_ready') else 'Review'}; "
            f"smart AI claim: {'ready' if report.get('smart_edit_claim_ready') else 'blocked'}"
        )
        lines.append(
            f"- Provider: {provider.get('effective', provider.get('selected', '-'))}, "
            f"direct {int(provider.get('corpus_direct_successes', 0) or 0)}/"
            f"{int(provider.get('corpus_attempts', 0) or 0)}, "
            f"fallbacks {int(provider.get('corpus_fallbacks', 0) or 0)}, "
            f"calls {int(provider.get('corpus_provider_calls', 0) or 0)}"
        )
        if provider.get("provider_timeout_seconds") or provider.get("provider_retries"):
            lines.append(
                f"- Provider run: timeout {int(provider.get('provider_timeout_seconds', 0) or 0)}s, "
                f"retries {int(provider.get('provider_retries', 0) or 0)}"
            )
        for row in list(report.get("cases", []) or [])[:8]:
            if not isinstance(row, dict):
                continue
            failures = ", ".join(str(item) for item in list(row.get("failures", []) or [])[:3])
            lines.append(
                f"- {row.get('id', 'case')}: score {row.get('score', 0)}, "
                f"{row.get('language', '-')}/{row.get('scenario', '-')}"
                + (f" failures={failures}" if failures else "")
            )
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"cases {int(summary.get('cases', 0) or 0)}, "
            f"real {int(summary.get('real_cases', 0) or 0)}/"
            f"{int(summary.get('min_real_cases', 20) or 20)}, "
            f"provider direct {int(provider.get('corpus_direct_successes', 0) or 0)}/"
            f"{int(provider.get('corpus_attempts', 0) or 0)}"
        ), lines
    if kind in {
        "visual_baseline",
        "micro_interactions",
        "ui_visual_baseline_refresh",
        "screenstudio_auto_polish",
        "screenstudio_naturalness",
        "screenstudio_export_handoff",
        "screenstudio_parity_gap",
        "screenstudio_real_corpus",
        "screenstudio_productization_next",
        "screenstudio_manual_zoom",
        "screenstudio_render_smoke",
        "screenstudio_visual_polish",
        "screenstudio_app_flow",
        "screenstudio_gui_flow",
    }:
        summary = report.get("summary", {}) or {}
        for name, passed in (report.get("checks", {}) or {}).items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        failures = list(report.get("failures", []) or [])
        if isinstance(summary, dict) and kind == "ui_visual_baseline_refresh":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
        if isinstance(summary, dict) and kind == "screenstudio_auto_polish":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            for sample in list(report.get("samples", []) or [])[:8]:
                if isinstance(sample, dict):
                    lines.append(
                        f"- {sample.get('id')}: {sample.get('event_count')} events, "
                        f"{sample.get('auto_zoom_count')} zoom, {sample.get('readiness')}%"
                    )
            return ok, (
                f"{int(summary.get('passing', 0) or 0)}/{int(summary.get('samples', 0) or 0)} samples, "
                f"{int(summary.get('zoom_candidates', 0) or 0)} zoom candidate(s)"
            ), lines
        if isinstance(summary, dict) and kind == "screenstudio_naturalness":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            for sample in list(report.get("samples", []) or [])[:8]:
                if isinstance(sample, dict):
                    lines.append(
                        f"- {sample.get('id')}: score {sample.get('score')}, "
                        f"loop={'OK' if dict(sample.get('loop') or {}).get('ok') else 'FAIL'}, "
                        f"zoom={sample.get('auto_zoom_count')}"
                    )
            for row in list(report.get("export_intents", []) or [])[:6]:
                if isinstance(row, dict):
                    lines.append(
                        f"- export {row.get('starter')}: {row.get('intent_id')} "
                        f"{row.get('format_id')}/{row.get('quality_id')} {row.get('fps')}fps"
                    )
            return ok, (
                f"score {float(summary.get('avg_score', 0.0) or 0.0):.1f}, "
                f"{int(summary.get('passing', 0) or 0)}/{int(summary.get('samples', 0) or 0)} samples"
            ), lines
        if isinstance(summary, dict) and kind == "screenstudio_export_handoff":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            for row in list(report.get("rows", []) or [])[:8]:
                if isinstance(row, dict):
                    lines.append(
                        f"- {row.get('id')}: {row.get('intent_id')} "
                        f"{row.get('format_id')}/{row.get('quality_id')} "
                        f"{row.get('handoff_label')}"
                    )
            return ok, (
                f"{int(summary.get('passing', 0) or 0)}/{int(summary.get('scenarios', 0) or 0)} scenarios, "
                f"{int(summary.get('manifests', 0) or 0)} manifest(s)"
            ), lines
        if isinstance(summary, dict) and kind == "screenstudio_parity_gap":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            for area in list(report.get("areas", []) or [])[:8]:
                if isinstance(area, dict):
                    mark = "OK" if area.get("ok") else "ATTN"
                    lines.append(f"[{mark}] {area.get('label', area.get('id'))}: {area.get('score', 0)}/100")
            for action in list(report.get("next_actions", []) or [])[:6]:
                lines.append(f"- Next: {action}")
            return ok, (
                f"score {report.get('score', 0)}/100, "
                f"real corpus {int(summary.get('real_recordings', 0) or 0)}/"
                f"{int(summary.get('real_recording_target_min', 20) or 20)}"
            ), lines
        if isinstance(summary, dict) and kind == "screenstudio_real_corpus":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            for row in list(report.get("rows", []) or [])[:8]:
                if isinstance(row, dict):
                    warnings = ", ".join(str(item) for item in list(row.get("warnings", []) or [])[:2])
                    lines.append(
                        f"- {Path(str(row.get('path', ''))).name}: "
                        f"probe={'OK' if row.get('video_probe_ok') else 'ATTN'}, "
                        f"sidecar={'OK' if row.get('cursor_sidecar_ok') else 'ATTN'}, "
                        f"clicks={int(row.get('click_event_count', 0) or 0)}, "
                        f"zoom={int(row.get('auto_zoom_count', 0) or 0)}"
                        + (f" ({warnings})" if warnings else "")
                    )
            blockers = list(report.get("replacement_claim_blockers", []) or [])
            if blockers:
                lines.append("- Replacement claim: blocked by " + ", ".join(str(item) for item in blockers[:4]))
            else:
                lines.append("- Replacement claim: ready")
            for action in list(report.get("next_actions", []) or [])[:6]:
                lines.append(f"- Next: {action}")
            return ok, (
                f"{int(summary.get('valid_files', 0) or 0)}/"
                f"{int(summary.get('target_min', 20) or 20)} valid, "
                f"probe {int(summary.get('video_probe_ok', 0) or 0)}, "
                f"sidecar {int(summary.get('cursor_sidecar_ready', 0) or 0)}, "
                f"interaction {int(summary.get('interaction_ready', 0) or 0)}"
            ), lines
        if isinstance(summary, dict) and kind == "screenstudio_sidecar_intake":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            for row in list(report.get("rows", []) or [])[:8]:
                if isinstance(row, dict):
                    missing = ", ".join(str(item) for item in list(row.get("missing_requirements", []) or [])[:5])
                    lines.append(
                        f"- {Path(str(row.get('path', ''))).name}: "
                        f"{row.get('state', 'needs_work')} "
                        f"template={Path(str(row.get('template_path', ''))).name}"
                        + (f" missing={missing}" if missing else "")
                    )
            for action in list(report.get("next_actions", []) or [])[:4]:
                lines.append(f"- Next: {action}")
            return ok, (
                f"{int(summary.get('ready', 0) or 0)}/"
                f"{int(summary.get('recordings', 0) or 0)} ready, "
                f"templates {int(summary.get('templates_written', 0) or 0)}, "
                f"needs sidecar {int(summary.get('needs_sidecar', 0) or 0)}"
            ), lines
        if isinstance(summary, dict) and kind == "ai_edit_corpus_intake":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            for row in list(report.get("rows", []) or [])[:8]:
                if isinstance(row, dict):
                    missing = ", ".join(str(item) for item in list(row.get("missing_requirements", []) or [])[:4])
                    lines.append(
                        f"- {row.get('case_id', 'case')}: "
                        f"{row.get('state', 'needs_work')} "
                        f"{row.get('language', '-')}/{row.get('scenario', '-')}"
                        + (f" missing={missing}" if missing else "")
                    )
            for action in list(report.get("next_actions", []) or [])[:4]:
                lines.append(f"- Next: {action}")
            return ok, (
                f"{int(summary.get('ready_real_cases', 0) or 0)}/"
                f"{int(summary.get('target_min', 20) or 20)} ready real cases, "
                f"templates {int(summary.get('templates_written', 0) or 0)}, "
                f"missing {int(summary.get('missing_real_cases', 0) or 0)}"
            ), lines
        if isinstance(summary, dict) and kind == "screenstudio_productization_next":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            for area in list(report.get("areas", []) or [])[:8]:
                if isinstance(area, dict):
                    mark = "OK" if area.get("ok") else "ATTN"
                    lines.append(f"[{mark}] {area.get('id')}: {area.get('score', 0)}/100")
            for action in list(report.get("next_actions", []) or [])[:6]:
                lines.append(f"- Next: {action}")
            return ok, (
                f"score {report.get('score', 0)}/100, "
                f"missing real recordings {int(summary.get('missing_for_minimum', 0) or 0)}, "
                f"export targets {int(summary.get('export_targets', 0) or 0)}"
            ), lines
        if isinstance(summary, dict) and kind == "screenstudio_manual_zoom":
            for name, passed in (report.get("checks", {}) or {}).items():
                lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
            policy = report.get("policy", {}) or {}
            if isinstance(policy, dict):
                lines.append(f"- snap_threshold_ms: {policy.get('snap_threshold_ms')}")
                lines.append(f"- min_duration_ms: {policy.get('min_duration_ms')}")
            return ok, f"score {report.get('score', 0)}/100", lines
        if isinstance(summary, dict) and kind == "screenstudio_render_smoke":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            video_path = report.get("video_path")
            if video_path:
                lines.append(f"- video: {video_path}")
            return ok, (
                f"{int(summary.get('frames', 0) or 0)} frame(s), "
                f"{int(summary.get('size_bytes', 0) or 0)} bytes"
            ), lines
        if isinstance(summary, dict) and kind == "screenstudio_gui_flow":
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            contact_sheet = report.get("contact_sheet")
            if contact_sheet:
                lines.append(f"- contact_sheet: {contact_sheet}")
            artifacts = report.get("artifacts", {}) or {}
            if isinstance(artifacts, dict):
                for key, value in list(artifacts.items())[:8]:
                    lines.append(f"- {key}: {value}")
            return ok, (
                f"{int(summary.get('passing', 0) or 0)}/{int(summary.get('checks', 0) or 0)} checks, "
                f"{int(summary.get('screenshots', 0) or 0)} screenshot(s)"
            ), lines
        if isinstance(summary, dict) and kind in {"screenstudio_visual_polish", "screenstudio_app_flow"}:
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
            contact_sheet = report.get("contact_sheet")
            if contact_sheet:
                lines.append(f"- contact_sheet: {contact_sheet}")
            for sample in list(report.get("samples", []) or [])[:8]:
                if isinstance(sample, dict):
                    lines.append(
                        f"- {sample.get('id')}: changed {float(sample.get('changed_ratio', 0.0) or 0.0):.1%}, "
                        f"{sample.get('auto_zoom_count')} zoom"
                    )
            return ok, (
                f"{int(summary.get('passing', 0) or 0)}/{int(summary.get('samples', 0) or 0)} samples, "
                f"{float(summary.get('avg_changed_ratio', 0.0) or 0.0):.1%} avg visual change"
            ), lines
        return ok, f"{len(failures)} issue(s), {len(report.get('checks', {}) or {})} check(s)", lines
    if kind == "productization":
        summary = report.get("summary", {}) or {}
        areas = list(report.get("areas", []) or [])
        passing = int(summary.get("passing", 0) or 0)
        attention = int(summary.get("attention", 0) or 0)
        for area in areas[:10]:
            if not isinstance(area, dict):
                continue
            mark = "OK" if area.get("ok") else "ATTN"
            lines.append(f"[{mark}] {area.get('label', area.get('id', 'area'))}: {area.get('summary', '')}")
        for action in list(report.get("next_actions", []) or [])[:6]:
            lines.append(f"- Next: {action}")
        return ok, f"score {report.get('score', 0)}/100, passing {passing}, attention {attention}", lines
    if kind == "commercial_expansion":
        summary = report.get("summary", {}) or {}
        areas = list(report.get("areas", []) or [])
        passing = int(summary.get("passing", 0) or 0)
        attention = int(summary.get("attention", 0) or 0)
        for area in areas[:10]:
            if not isinstance(area, dict):
                continue
            mark = "OK" if area.get("ok") else "ATTN"
            lines.append(f"[{mark}] {area.get('label', area.get('id', 'area'))}: {area.get('summary', '')}")
        for action in list(report.get("next_actions", []) or [])[:6]:
            lines.append(f"- Next: {action}")
        return ok, f"score {report.get('score', 0)}/100, passing {passing}, attention {attention}", lines
    if kind == "public_positioning":
        summary = report.get("summary", {}) or {}
        for row in list(report.get("checks", []) or [])[:10]:
            if isinstance(row, dict):
                mark = "OK" if row.get("ok") else "FAIL"
                location = f"{row.get('file', '')}:{row.get('line')}" if row.get("line") else str(row.get("file", ""))
                lines.append(f"[{mark}] {location} {row.get('summary', '')}")
        for action in list(report.get("next_actions", []) or [])[:6]:
            lines.append(f"- Next: {action}")
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"passing {int(summary.get('passing', 0) or 0)}/"
            f"{int(summary.get('checks', 0) or 0)}, "
            f"failing {int(summary.get('failing', 0) or 0)}"
        ), lines
    if kind == "capcut_creator_workflow":
        summary = report.get("summary", {}) or {}
        areas = list(report.get("areas", []) or [])
        for area in areas[:10]:
            if not isinstance(area, dict):
                continue
            mark = "OK" if area.get("ok") else "ATTN"
            lines.append(f"[{mark}] {area.get('label', area.get('id', 'area'))}: {area.get('score', 0)}/100")
        lines.append(f"- Edit recipe steps: {int(summary.get('edit_recipe_steps', 0) or 0)}")
        lines.append(f"- Publish variants: {int(summary.get('publish_variants', 0) or 0)}")
        lines.append(f"- Review panel cards: {int(summary.get('review_panel_cards', 0) or 0)}")
        lines.append(f"- Publish handoff actions: {int(summary.get('publish_handoff_actions', 0) or 0)}")
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"{int(summary.get('recommendation_steps', 0) or 0)} recommendation step(s), "
            f"{int(summary.get('edit_recipe_steps', 0) or 0)} recipe step(s), "
            f"{int(summary.get('review_panel_cards', 0) or 0)} panel card(s), "
            f"{int(summary.get('applied_subtitles', 0) or 0)} subtitle(s), "
            f"{int(summary.get('materialized_render_queue_jobs', summary.get('applied_render_jobs', 0)) or 0)} render job(s), "
            f"{int(summary.get('hook_candidates', 0) or 0)} hook(s), "
            f"{int(summary.get('caption_beats', 0) or 0)} beat(s), "
            f"publish={'ready' if bool(summary.get('publish_package_ready')) else 'attention'}"
        ), lines
    if kind == "capcut_parity_next":
        summary = report.get("summary", {}) or {}
        gaps = list(report.get("largest_gaps", []) or report.get("areas", []) or [])
        for area in gaps[:7]:
            if not isinstance(area, dict):
                continue
            mark = "OK" if area.get("ok") else "GAP"
            lines.append(
                f"[{mark}] {area.get('label', area.get('id', 'area'))}: "
                f"{area.get('score', 0)}/{area.get('target_score', 90)}"
            )
        for action in list(report.get("next_actions", []) or [])[:6]:
            lines.append(f"- Next: {action}")
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"{int(summary.get('capcut_builtin_presets', 0) or 0)} CapCut preset(s), "
            f"{int(summary.get('capcut_builtin_templates', 0) or 0)} template(s), "
            f"largest gap={summary.get('largest_gap', '-')}, "
            f"parity={'ready' if report.get('parity_ready') else 'not ready'}"
        ), lines
    if kind == "capcut_publish_review":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        for name, passed in checks.items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        for warning in list(((report.get("review", {}) or {}).get("warnings", []) or []))[:5]:
            lines.append(f"- Warning: {warning}")
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"{int(summary.get('ready_platforms', 0) or 0)} ready platform(s), "
            f"{int(summary.get('ready_quick_upload_count', 0) or 0)} quick upload(s), "
            f"{int(summary.get('quick_upload_package_file_count', 0) or 0)} package file(s), "
            f"{int(summary.get('provider_count', 0) or 0)} provider(s), "
            f"{int(summary.get('configured_provider_count', 0) or 0)} configured"
        ), lines
    if kind == "capcut_quick_result":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        for name, passed in checks.items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        recommendation = ((report.get("quick_result", {}) or {}).get("recommendation", {}) or {})
        if recommendation:
            lines.append(f"- Template: {recommendation.get('id', '')} ({recommendation.get('label', '')})")
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"quality {summary.get('quality_score', 0)}, "
            f"{int(summary.get('ready_actions', 0) or 0)} ready action(s), "
            f"template={'ready' if summary.get('template_exists') else 'missing'}"
        ), lines
    if kind == "capcut_voice_workflow":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        for name, passed in checks.items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"workflow {summary.get('workflow_score', 0)}, "
            f"{int(summary.get('subtitle_rows', 0) or 0)} caption row(s), "
            f"{int(summary.get('configured_provider_count', 0) or 0)}/"
            f"{int(summary.get('provider_count', 0) or 0)} provider(s)"
        ), lines
    if kind == "voice_lab_sidecar":
        server = report.get("server", {}) or {}
        view = report.get("view", {}) or {}
        status = server.get("status", {}) if isinstance(server.get("status"), dict) else {}
        root = status.get("root", {}) if isinstance(status.get("root"), dict) else {}
        model_names = list(root.get("model_names", []) or [])
        endpoint = str(server.get("endpoint") or status.get("endpoint") or view.get("endpoint") or "")
        failures = [str(value) for value in list(report.get("failures", []) or []) if str(value)]
        lines.append(f"- provider: {'OK' if bool(view.get('ready')) else 'NEEDS SETUP'}")
        lines.append(
            "- server: "
            f"{'ready' if bool(server.get('ready')) else 'offline'}"
            f", running={bool(server.get('running'))}, started={bool(server.get('started'))}"
        )
        if endpoint:
            lines.append(f"- endpoint: {endpoint}")
        if model_names:
            lines.append(f"- models: {', '.join(str(name) for name in model_names[:8])}")
        for failure in failures[:6]:
            lines.append(f"! {failure}")
        message = str(report.get("user_message") or "").strip()
        if message:
            for line in message.splitlines()[:4]:
                if line.strip():
                    lines.append(f"- {line.strip()}")
        return ok, (
            f"{'ready' if bool(report.get('ready')) else 'offline'}, "
            f"{len(model_names)} model(s), "
            f"endpoint {endpoint or '-'}"
        ), lines
    if kind == "capcut_prompt_edit":
        summary = report.get("summary", {}) or {}
        for case in list(report.get("cases", []) or [])[:6]:
            if isinstance(case, dict):
                lines.append(
                    f"- {case.get('id')}: {'OK' if case.get('ok') else 'FAIL'} "
                    f"{int(case.get('matched', 0) or 0)}/{int(case.get('expected_count', 0) or 0)} operation(s)"
                )
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"{int(summary.get('passing_cases', 0) or 0)}/"
            f"{int(summary.get('cases', 0) or 0)} cases, "
            f"{int(summary.get('matched_operations', 0) or 0)}/"
            f"{int(summary.get('expected_operations', 0) or 0)} operation(s)"
        ), lines
    if kind == "capcut_collab_handoff":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        for name, passed in checks.items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"review {summary.get('review_score', 0)}, "
            f"{int(summary.get('media_count', 0) or 0)} media item(s), "
            f"{int(summary.get('configured_provider_count', 0) or 0)}/"
            f"{int(summary.get('provider_count', 0) or 0)} provider(s)"
        ), lines
    if kind == "capcut_cloud_handoff":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        for name, passed in checks.items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"{int(summary.get('provider_count', 0) or 0)} provider(s), "
            f"{int(summary.get('local_package_file_count', 0) or 0)} package file(s), "
            f"dry-run={'ready' if summary.get('configured_dry_run_ready') else 'not ready'}, "
            f"default={'safe' if summary.get('default_safe_by_default') else 'check'}"
        ), lines
    if kind == "creator_asset_packs":
        summary = report.get("summary", {}) or {}
        targets = report.get("targets", {}) or {}
        for name, target in list(targets.items())[:8]:
            if isinstance(target, dict):
                lines.append(
                    f"- {name}: {int(target.get('count', 0) or 0)}/"
                    f"{int(target.get('target', 0) or 0)}"
                )
        for issue in list(report.get("issues", []) or [])[:6]:
            if isinstance(issue, dict):
                lines.append(f"- Issue: {issue.get('message', '')}")
        return ok, (
            f"score {report.get('score', 0)}/100, "
            f"{int(summary.get('assets', 0) or 0)} asset(s), "
            f"{int(summary.get('kinds', 0) or 0)} kind(s), "
            f"{int(summary.get('licenses', 0) or 0)} license group(s)"
        ), lines
    if kind == "localization_audit":
        summary = report.get("summary", {}) or {}
        for row in list(report.get("languages", []) or [])[:8]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('lang')}: keys={row.get('keys', 0)} "
                f"missing={len(row.get('missing_from_reference', []) or [])} "
                f"suspicious={len(row.get('suspicious', []) or [])} "
                f"placeholders={len(row.get('placeholder_mismatches', []) or [])}"
            )
        return ok, (
            f"{int(summary.get('languages', 0) or 0)} language(s), "
            f"{int(summary.get('total_keys', 0) or 0)} total key(s), "
            f"missing {int(summary.get('missing_keys', 0) or 0)}, "
            f"suspicious {int(summary.get('suspicious_strings', 0) or 0)}, "
            f"placeholder mismatch {int(summary.get('placeholder_mismatches', 0) or 0)}"
        ), lines
    if kind == "review_sample_resources":
        resources = list(report.get("resources", []) or [])
        for resource in resources[:10]:
            if not isinstance(resource, dict):
                continue
            mark = "OK" if resource.get("ready") else "MISS"
            sidecars = list(resource.get("sidecars", []) or [])
            missing_sidecars = [
                str(sidecar.get("path", ""))
                for sidecar in sidecars
                if isinstance(sidecar, dict) and not sidecar.get("exists")
            ]
            suffix = f" missing sidecar={Path(missing_sidecars[0]).name}" if missing_sidecars else ""
            lines.append(
                f"[{mark}] {resource.get('id', 'sample')}: "
                f"{resource.get('role', '-')}/{resource.get('kind', '-')} "
                f"{Path(str(resource.get('path', ''))).name}{suffix}"
            )
        missing_required = int(report.get("missing_required_count", 0) or 0)
        ready_count = int(report.get("ready_count", 0) or 0)
        resource_count = int(report.get("resource_count", len(resources)) or 0)
        return ok, (
            f"{ready_count}/{resource_count} ready, "
            f"missing required {missing_required}, "
            f"manifest={'ready' if report.get('manifest_exists') else 'missing'}"
        ), lines
    if kind == "review_automation":
        summary = report.get("summary", {}) or {}
        for feature in list(report.get("features", []) or [])[:8]:
            if not isinstance(feature, dict):
                continue
            status = str(feature.get("status") or "unknown").replace("_", " ")
            lines.append(f"- {feature.get('title', feature.get('id', 'feature'))}: {status}")
        outputs = report.get("outputs", {}) or {}
        if isinstance(outputs, dict):
            for name, value in outputs.items():
                lines.append(f"- {name}: {value}")
        for warning in list(report.get("warnings", []) or [])[:6]:
            lines.append(f"- Warning: {warning}")
        return ok, (
            f"{int(summary.get('evidence_ready', 0) or 0)}/"
            f"{int(summary.get('features', 0) or 0)} evidence-ready, "
            f"{int(summary.get('ready_artifacts', 0) or 0)}/"
            f"{int(summary.get('artifacts', 0) or 0)} artifacts, "
            f"stale={'yes' if report.get('stale') else 'no'}"
        ), lines
    if kind == "review_automation_qa":
        summary = report.get("summary", {}) or {}
        for failure in list(report.get("failures", []) or [])[:8]:
            lines.append(f"- Failure: {failure}")
        for warning in list(report.get("warnings", []) or [])[:6]:
            lines.append(f"- Warning: {warning}")
        return ok, (
            f"{int(summary.get('html_pages', 0) or 0)} page(s), "
            f"{int(summary.get('html_refs', 0) or 0)} link/ref(s), "
            f"{int(summary.get('slides', 0) or 0)} slide(s), "
            f"missing artifacts {int(summary.get('missing_artifacts', 0) or 0)}"
        ), lines
    if kind == "local_ml_backend":
        summary = report.get("summary", {}) or {}
        checks = report.get("checks", {}) or {}
        status = report.get("status", {}) or {}
        capabilities = status.get("capabilities", {}) if isinstance(status, dict) else {}
        for name, passed in checks.items():
            lines.append(f"- {name}: {'OK' if passed else 'FAIL'}")
        if isinstance(capabilities, dict):
            for name, cap in capabilities.items():
                if isinstance(cap, dict):
                    state = "available" if cap.get("available") else "missing"
                    backend = cap.get("backend") or cap.get("method") or cap.get("kind") or ""
                    lines.append(f"- {name}: {state} {backend}".rstrip())
        return ok, (
            f"{summary.get('mode', 'local')} mode, "
            f"cloud={'on' if summary.get('cloud_enabled') else 'off'}, "
            f"{int(summary.get('detections', 0) or 0)} detection(s), "
            f"bundle={'ready' if summary.get('capcut_bundle_ok') else 'attention'}"
        ), lines
    if kind == "release_gap_closure":
        summary = report.get("summary", {}) or {}
        for area in list(report.get("areas", []) or [])[:8]:
            if not isinstance(area, dict):
                continue
            mark = "OK" if area.get("ok") else "BLOCK"
            lines.append(
                f"[{mark}] {area.get('label', area.get('id', 'area'))}: "
                f"{int(area.get('score', 0) or 0)}/100 - {area.get('summary', '')}"
            )
            for blocker in list(area.get("blockers", []) or [])[:3]:
                lines.append(f"  blocker: {blocker}")
        for action in list(report.get("next_actions", []) or [])[:8]:
            lines.append(f"- Next: {action}")
        ready = bool(report.get("release_ready"))
        return ok, (
            f"score {int(report.get('score', 0) or 0)}/100, "
            f"ready {int(summary.get('ready', 0) or 0)}/"
            f"{int(summary.get('areas', 0) or 0)}, "
            f"blocked {int(summary.get('blocked', 0) or 0)}, "
            f"release={'ready' if ready else 'blocked'}"
        ), lines
    if kind == "release_evidence_sprint":
        summary = report.get("summary", {}) or {}
        scripts = report.get("scripts", {}) or {}
        progress = report.get("progress") if isinstance(report.get("progress"), dict) else release_evidence_progress(report)
        screen_progress = dict(progress.get("screenstudio") or {})
        ai_progress = dict(progress.get("ai") or {})
        lines.append(
            f"- Progress: {int(progress.get('overall_percent', 0) or 0)}% "
            f"({'ready' if progress.get('ready') else 'needs real evidence'})"
        )
        lines.append(
            "- ScreenStudio interactions: "
            f"{int(screen_progress.get('interaction_ready', 0) or 0)}/"
            f"{int(screen_progress.get('target', 0) or 0)} ready, "
            f"{int(screen_progress.get('sidecar_ready', 0) or 0)} sidecar(s), "
            f"{int(screen_progress.get('needed', 0) or 0)} needed"
        )
        lines.append(
            "- AI real cases: "
            f"{int(ai_progress.get('real_cases', 0) or 0)}/"
            f"{int(ai_progress.get('target', 0) or 0)} ready, "
            f"{int(ai_progress.get('needed', 0) or 0)} needed"
        )
        for blocker in list(progress.get("blockers", []) or [])[:4]:
            lines.append(f"- Blocker: {blocker}")
        requirements = dict(screen_progress.get("requirements") or {})
        if requirements:
            lines.append("- ScreenStudio proof requirements:")
            for key in ("cursor_sidecar", "click", "drag", "hotkey", "auto_zoom"):
                req = dict(requirements.get(key) or {})
                if not req:
                    continue
                lines.append(
                    f"  {req.get('label', key)}: "
                    f"{int(req.get('ready', 0) or 0)}/"
                    f"{int(req.get('target', 0) or 0)} ready, "
                    f"{int(req.get('needed', 0) or 0)} needed"
                )
        if isinstance(summary, dict):
            for key, value in summary.items():
                lines.append(f"- {key}: {value}")
        if isinstance(scripts, dict):
            for key, value in scripts.items():
                lines.append(f"- script {key}: {value}")
        playbook = report.get("playbook")
        if playbook:
            lines.append(f"- playbook: {playbook}")
        for row in list(((report.get("screenstudio", {}) or {}).get("selected_rows", []) or []))[:6]:
            if isinstance(row, dict):
                missing = ", ".join(str(item) for item in list(row.get("missing_requirements", []) or [])[:4])
                lines.append(f"- ScreenStudio {row.get('slot_id', '-')}: {missing or 'ready'}")
        work_queue = list(report.get("work_queue") or release_evidence_next_items(report, limit=6))
        for item in work_queue[:6]:
            if isinstance(item, dict):
                lines.append(f"- Next work: {item.get('summary', item.get('kind', 'evidence'))}")
        for row in list(((report.get("ai", {}) or {}).get("selected_rows", []) or []))[:6]:
            if isinstance(row, dict):
                lines.append(f"- AI case {row.get('case_id', '-')}: {row.get('state', 'needs_work')}")
        return ok, (
            f"progress {int(progress.get('overall_percent', 0) or 0)}%, "
            f"screen interactions {int(screen_progress.get('interaction_ready', 0) or 0)}/"
            f"{int(screen_progress.get('target', 0) or 0)}, "
            f"AI real cases {int(ai_progress.get('real_cases', 0) or 0)}/"
            f"{int(ai_progress.get('target', 0) or 0)}, "
            f"claim proof={'ready' if report.get('claim_unblocked_by_sprint') else 'needs real capture'}"
        ), lines
    if kind == "crash_report":
        exc = report.get("exception", {}) or {}
        actions = list(report.get("recent_actions", []) or [])
        for action in actions[-12:]:
            if isinstance(action, dict):
                lines.append(f"- {action.get('at')} {action.get('event')}: {action.get('data')}")
        summary = f"{exc.get('type', 'unknown')}: {exc.get('message', '')}" if exc else "No crash"
        return False, summary, lines
    return ok, "ok" if ok else "failed", [json.dumps(report.get("summary", report), ensure_ascii=False, indent=2, default=str)[:3000]]


def build_qa_dashboard_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, raw_path, kind in REPORT_SPECS:
        path = _resolve_report_path(raw_path)
        report = _load_json(path) if path is not None else {}
        ok, summary, lines = _summary_for(kind, report)
        rows.append({
            "label": label,
            "kind": kind,
            "path": str(path or raw_path),
            "exists": path is not None and path.exists(),
            "mtime": _mtime(path) if path is not None and path.exists() else "-",
            "ok": ok,
            "summary": summary,
            "lines": lines,
        })
    return rows


def _load_history(path: Path = HISTORY_PATH) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("runs", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _append_history(rows: list[dict[str, Any]], *, path: Path = HISTORY_PATH, label: str = "refresh") -> None:
    try:
        runs = _load_history(path)
        runs.append({
            "at": datetime.now().isoformat(timespec="seconds"),
            "label": label,
            "available": sum(1 for row in rows if row.get("exists")),
            "passing": sum(1 for row in rows if row.get("exists") and row.get("ok")),
            "failing": sum(1 for row in rows if row.get("exists") and not row.get("ok")),
            "rows": [
                {
                    "kind": row.get("kind"),
                    "exists": bool(row.get("exists")),
                    "ok": bool(row.get("ok")),
                    "summary": row.get("summary"),
                }
                for row in rows
            ],
        })
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"runs": runs[-60:]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _render_dashboard_trend(rows: list[dict[str, Any]], history: list[dict[str, Any]] | None = None) -> QPixmap:
    pix = QPixmap(720, 64)
    pix.fill(QColor("#0A0D16"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
    painter.setBrush(QColor(16, 20, 34, 245))
    painter.drawRoundedRect(pix.rect().adjusted(1, 1, -2, -2), 14, 14)
    history = list(history or [])
    if history:
        graph_rect_y = 18
        graph_h = 30
        recent = history[-24:]
        step = max(4, (pix.width() - 36) // max(1, len(recent) - 1))
        painter.setPen(QPen(QColor("#6F5CFF"), 2))
        last = None
        for idx, run in enumerate(recent):
            total = max(1, int(run.get("available", 0) or len(rows) or 1))
            passing = int(run.get("passing", 0) or 0)
            x = 18 + idx * step
            y = graph_rect_y + graph_h - int(graph_h * passing / total)
            if last is not None:
                painter.drawLine(last[0], last[1], x, y)
            last = (x, y)
        painter.setPen(QColor("#A7ADC2"))
        painter.drawText(18, 13, "QA trend: line=passing reports over time")
        painter.end()
        return pix

    if not rows:
        painter.end()
        return pix
    w = max(18, (pix.width() - 38) // max(1, len(rows)))
    for idx, row in enumerate(rows):
        x = 18 + idx * w
        exists = bool(row.get("exists"))
        ok = bool(row.get("ok"))
        color = QColor("#78F29B") if exists and ok else (QColor("#FF7A59") if exists else QColor("#4B5269"))
        height = 36 if exists and ok else (24 if exists else 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(x, 44 - height, max(10, w - 7), height, 5, 5)
        painter.setPen(QColor(255, 255, 255, 120))
        painter.drawText(x, 55, max(10, w - 7), 8, Qt.AlignmentFlag.AlignCenter, str(idx + 1))
    painter.setPen(QColor("#A7ADC2"))
    painter.drawText(18, 13, "QA trend: green=passing, orange=failing, gray=missing")
    painter.end()
    return pix


class QADashboardDialog(QDialog):
    """Small report browser for QA trend, broken areas, and baseline status."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("QA Dashboard")
        self.resize(900, 560)
        self._rows: list[dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)
        self._trend = QLabel("")
        self._trend.setFixedHeight(64)
        root.addWidget(self._trend)

        body = QHBoxLayout()
        self._list = QListWidget()
        body.addWidget(self._list, 1)
        right = QVBoxLayout()
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        right.addWidget(self._detail, 1)
        self._preview = QLabel("")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setFixedHeight(132)
        self._preview.setStyleSheet("background:#0B0D16;border:1px solid #30384F;border-radius:12px;color:#A7ADC2;")
        right.addWidget(self._preview)
        body.addLayout(right, 2)
        root.addLayout(body, 1)

        buttons = QDialogButtonBox()
        self._refresh_btn = QPushButton("Refresh")
        self._run_btn = QPushButton("Run Selected QA")
        self._run_all_btn = QPushButton("Run Fast QA")
        self._approve_baseline_btn = QPushButton("Approve Visual Baseline")
        self._evidence_btn = QPushButton("Evidence Actions")
        self._open_folder_btn = QPushButton("Open Report Folder")
        close_btn = QPushButton("Close")
        self._refresh_btn.clicked.connect(self.refresh)
        self._run_btn.clicked.connect(self._run_selected_qa)
        self._run_all_btn.clicked.connect(self._run_all_fast_qa)
        self._approve_baseline_btn.clicked.connect(self._approve_visual_baseline)
        self._evidence_btn.clicked.connect(self._open_evidence_actions)
        self._open_folder_btn.clicked.connect(self._open_selected_folder)
        close_btn.clicked.connect(self.accept)
        buttons.addButton(self._refresh_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._run_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._run_all_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._approve_baseline_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._evidence_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._open_folder_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(close_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(buttons)

        self._list.itemSelectionChanged.connect(self._refresh_detail)
        self.refresh()

    def refresh(self) -> None:
        self._rows = build_qa_dashboard_rows()
        _append_history(self._rows, label="refresh")
        self._list.clear()
        ok_count = 0
        existing = 0
        for idx, row in enumerate(self._rows):
            if row.get("exists"):
                existing += 1
            if row.get("exists") and row.get("ok"):
                ok_count += 1
            prefix = "OK" if row.get("exists") and row.get("ok") else ("MISS" if not row.get("exists") else "FAIL")
            item = QListWidgetItem(f"[{prefix}] {row.get('label')}  {row.get('summary')}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setToolTip(str(row.get("path", "")))
            self._list.addItem(item)
        self._summary.setText(f"QA reports: {existing}/{len(self._rows)} available | passing {ok_count}/{existing or 1}")
        self._trend.setPixmap(_render_dashboard_trend(self._rows, _load_history()))
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._refresh_detail()

    def _selected_row(self) -> dict[str, Any] | None:
        item = self._list.currentItem()
        if item is None:
            return None
        try:
            return self._rows[int(item.data(Qt.ItemDataRole.UserRole))]
        except Exception:
            return None

    def _refresh_detail(self) -> None:
        row = self._selected_row()
        if not row:
            self._detail.setPlainText("")
            self._run_btn.setEnabled(False)
            self._approve_baseline_btn.setEnabled(False)
            self._evidence_btn.setEnabled(False)
            return
        lines = [
            f"{row.get('label')}",
            f"Status: {'OK' if row.get('ok') and row.get('exists') else ('Missing' if not row.get('exists') else 'Needs attention')}",
            f"Updated: {row.get('mtime')}",
            f"Path: {row.get('path')}",
            "",
            str(row.get("summary", "")),
            "",
        ]
        lines.extend(str(line) for line in row.get("lines", []) or [])
        self._detail.setPlainText("\n".join(lines))
        self._run_btn.setEnabled(self._command_for_row(row) is not None)
        self._approve_baseline_btn.setEnabled(str(row.get("kind") or "") == "visual")
        self._evidence_btn.setEnabled(str(row.get("kind") or "") == "release_evidence_sprint")
        self._refresh_preview(row)

    def _refresh_preview(self, row: dict[str, Any]) -> None:
        self._preview.setPixmap(QPixmap())
        self._preview.setText("")
        kind = str(row.get("kind") or "")
        if kind.startswith("screenstudio_"):
            report_path = Path(str(row.get("path") or ""))
            report = _load_json(report_path) if report_path.exists() else {}
            candidates: list[Path] = []
            contact_sheet = report.get("contact_sheet") if isinstance(report, dict) else None
            if contact_sheet:
                candidates.append(Path(str(contact_sheet)))
            artifacts = report.get("artifacts", {}) if isinstance(report, dict) else {}
            if isinstance(artifacts, dict):
                candidates.extend(Path(str(value)) for value in artifacts.values() if str(value).lower().endswith(".png"))
            folder = report_path.parent
            if folder.exists():
                candidates.extend(sorted(folder.glob("*contact_sheet*.png")))
                candidates.extend(sorted(folder.glob("*.png")))
            for candidate in candidates:
                pix = QPixmap(str(candidate))
                if pix.isNull():
                    continue
                self._preview.setPixmap(pix.scaled(
                    self._preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
                return
            self._preview.setText("Screen Studio QA thumbnail appears here after the report runs.")
            return
        if kind == "editor_e2e_smoke":
            report_path = Path(str(row.get("path") or ""))
            report = _load_json(report_path) if report_path.exists() else {}
            candidates: list[Path] = []
            contact_sheet = report.get("contact_sheet") if isinstance(report, dict) else None
            if contact_sheet:
                candidates.append(Path(str(contact_sheet)))
            artifacts = report.get("artifacts", {}) if isinstance(report, dict) else {}
            if isinstance(artifacts, dict):
                candidates.extend(
                    Path(str(value))
                    for value in artifacts.values()
                    if str(value).lower().endswith(".png")
                )
            folder = report_path.parent / "editor_e2e_smoke"
            if folder.exists():
                candidates.extend(sorted(folder.glob("*contact_sheet*.png")))
                candidates.extend(sorted(folder.glob("*.png")))
            for candidate in candidates:
                pix = QPixmap(str(candidate))
                if pix.isNull():
                    continue
                self._preview.setPixmap(pix.scaled(
                    self._preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
                return
            self._preview.setText("Editor E2E smoke screenshots appear here after the report runs.")
            return
        if kind == "editor_export_bake":
            report_path = Path(str(row.get("path") or ""))
            report = _load_json(report_path) if report_path.exists() else {}
            candidates: list[Path] = []
            outputs = report.get("outputs", {}) if isinstance(report, dict) else {}
            if isinstance(outputs, dict):
                processed_frame = outputs.get("processed_frame")
                baseline_frame = outputs.get("baseline_frame")
                if processed_frame:
                    candidates.append(Path(str(processed_frame)))
                if baseline_frame:
                    candidates.append(Path(str(baseline_frame)))
            folder = report_path.parent / "editor_export_bake_qa"
            if folder.exists():
                candidates.extend(sorted(folder.glob("*processed*.jpg")))
                candidates.extend(sorted(folder.glob("*.jpg")))
                candidates.extend(sorted(folder.glob("*.png")))
            for candidate in candidates:
                pix = QPixmap(str(candidate))
                if pix.isNull():
                    continue
                self._preview.setPixmap(pix.scaled(
                    self._preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
                return
            self._preview.setText("Editor export-bake frame appears here after the report runs.")
            return
        if kind == "gpu_preview_pixel_collision":
            report_path = Path(str(row.get("path") or ""))
            report = _load_json(report_path) if report_path.exists() else {}
            candidates: list[Path] = []
            shot = report.get("screenshot") if isinstance(report, dict) else None
            if shot:
                candidates.append(Path(str(shot)))
            candidates.append(Path("debugCapture/gpu_preview_pixel_collision.png"))
            for candidate in candidates:
                pix = QPixmap(str(candidate))
                if pix.isNull():
                    continue
                self._preview.setPixmap(pix.scaled(
                    self._preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
                return
            self._preview.setText("GPU preview pixel collision screenshot appears here after the report runs.")
            return
        if kind != "visual":
            self._preview.setText("Baseline diff thumbnail appears here for visual QA reports.")
            return
        folder = Path(str(row.get("path") or "")).parent
        images = sorted(folder.glob("*.png")) if folder.exists() else []
        if not images:
            self._preview.setText("No visual capture thumbnail found.")
            return
        pix = QPixmap(str(images[0]))
        if pix.isNull():
            self._preview.setText("Thumbnail unreadable.")
            return
        self._preview.setPixmap(pix.scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    @staticmethod
    def _command_for_row(row: dict[str, Any] | None) -> list[str] | None:
        if not row:
            return None
        kind = str(row.get("kind") or "")
        if kind in REVIEW_AUTOMATION_KINDS and not review_automation_dev_enabled():
            return None
        path = Path(str(row.get("path") or ""))
        python = sys.executable or "python"
        if kind == "timeline_fuzzer":
            return [python, "tools/qa_timeline_fuzzer.py", "--iterations", "400", "--seed", "42", "--out", str(path)]
        if kind == "timeline_alignment":
            return [python, "tools/qa_timeline_alignment.py", "--out", str(path)]
        if kind == "timeline_visual_alignment":
            return [python, "tools/qa_timeline_visual_alignment.py", "--out", "debugCapture/timeline_visual_alignment_qa"]
        if kind == "timeline_drag_feedback":
            return [python, "tools/qa_timeline_drag_feedback.py", "--out", "debugCapture/timeline_drag_feedback_qa"]
        if kind == "timeline_edit_gestures":
            return [python, "tools/qa_timeline_edit_gestures.py", "--out", "debugCapture/timeline_edit_gestures_qa"]
        if kind == "timeline_hover_affordance":
            return [python, "tools/qa_timeline_hover_affordance.py", "--out", "debugCapture/timeline_hover_affordance_qa"]
        if kind == "timeline_preset_visibility":
            return [python, "tools/qa_timeline_preset_visibility.py", "--out", "debugCapture/timeline_preset_visibility_qa"]
        if kind == "long_project_stress":
            return [python, "tools/qa_long_project_stress.py", "--out", str(path)]
        if kind == "actor_workflow":
            return [python, "tools/qa_actor_lane_workflow.py", "--include-samples", "--out", str(path)]
        if kind == "actor_loading_ux":
            return [python, "tools/qa_actor_loading_ux.py", "--out", str(path)]
        if kind == "actor_overnight_qa":
            return [python, "tools/qa_actor_overnight.py", "--out", str(path), "--limit", "24"]
        if kind == "node_graph_fuzzer":
            return [python, "tools/qa_node_graph_fuzzer.py", "--iterations", "400", "--seed", "42", "--out", str(path)]
        if kind == "node_graph_ui_fuzzer":
            return [python, "tools/qa_node_graph_ui_fuzzer.py", "--iterations", "240", "--seed", "42", "--out", str(path)]
        if kind == "color_audio":
            return [python, "tools/qa_color_audio_accuracy.py", "--out", str(path)]
        if kind == "preset_application":
            return [python, "tools/qa_preset_application_corpus.py", "--output", str(path)]
        if kind == "project_qa":
            return [python, "tools/qa_project_audit.py", "--synthetic", "--out", str(path)]
        if kind == "editor_e2e_smoke":
            return [
                python,
                "tools/qa_editor_e2e_smoke.py",
                "--out-dir",
                "debugCapture/editor_e2e_smoke",
                "--report",
                str(path),
            ]
        if kind == "editor_export_bake":
            return [
                python,
                "tools/qa_editor_export_bake.py",
                "--out-dir",
                "debugCapture/editor_export_bake_qa",
                "--report",
                str(path),
            ]
        if kind == "gpu_preview_pixel_collision":
            return [
                python,
                "tools/qa_gpu_preview_pixel_collision.py",
                "--out",
                str(path),
                "--screenshot",
                "debugCapture/gpu_preview_pixel_collision.png",
            ]
        if kind == "gpu_export_parity_matrix":
            return [python, "tools/qa_gpu_export_parity_matrix.py", "--out", str(path)]
        if kind == "ar_pbr_export_bake":
            return [python, "tools/qa_ar_pbr_export_bake.py", "--out", str(path)]
        if kind == "ar_pbr_attachment_stability":
            return [python, "tools/qa_ar_pbr_attachment_stability.py", "--out", str(path)]
        if kind == "nle_readiness":
            return [python, "tools/qa_nle_readiness.py", "--out", str(path)]
        if kind == "creative_layer_readiness":
            return [python, "tools/qa_creative_layer_readiness.py", "--out", str(path)]
        if kind == "final_product_readiness":
            return [python, "tools/qa_final_product_readiness.py", "--out", str(path)]
        if kind == "broadcast_release_readiness":
            return [python, "tools/qa_broadcast_release_readiness.py", "--out", str(path), "--allow-not-ready"]
        if kind == "broadcast_platform_e2e":
            return [python, "tools/qa_broadcast_platform_e2e.py", "--out", str(path), "--allow-pending-platform"]
        if kind == "productization":
            return [python, "tools/qa_productization_loop.py", "--out", str(path)]
        if kind == "creator_polish_coverage":
            return [python, "tools/qa_creator_polish_coverage.py", "--out", str(path)]
        if kind == "product_polish_next":
            return [python, "tools/qa_product_polish_next.py", "--out", str(path)]
        if kind == "professional_pipeline_next":
            return [python, "tools/qa_professional_pipeline_next.py", "--out", str(path)]
        if kind == "professional_runtime_next":
            return [python, "tools/qa_professional_runtime_next.py", "--out", str(path)]
        if kind == "real_project_product_flow":
            return [python, "tools/qa_real_project_product_flow.py", "--out", str(path)]
        if kind == "commercial_expansion":
            return [python, "tools/qa_commercial_expansion.py", "--out", str(path)]
        if kind == "public_positioning":
            return [python, "tools/qa_public_positioning.py", "--out", str(path)]
        if kind == "capcut_creator_workflow":
            return [python, "tools/qa_capcut_creator_workflow.py", "--out", str(path)]
        if kind == "capcut_parity_next":
            return [python, "tools/qa_capcut_parity_next.py", "--out", str(path)]
        if kind == "capcut_publish_review":
            return [python, "tools/qa_capcut_publish_review.py", "--out", str(path)]
        if kind == "capcut_quick_result":
            return [python, "tools/qa_capcut_quick_result.py", "--out", str(path)]
        if kind == "capcut_voice_workflow":
            return [python, "tools/qa_capcut_voice_workflow.py", "--out", str(path)]
        if kind == "voice_lab_sidecar":
            return [
                python,
                "tools/qa_tts_voice_lab.py",
                "--out",
                str(path),
                "--auto-start",
                "--wait-timeout",
                "120",
            ]
        if kind == "capcut_prompt_edit":
            return [python, "tools/qa_capcut_prompt_edit.py", "--out", str(path)]
        if kind == "capcut_collab_handoff":
            return [python, "tools/qa_capcut_collab_handoff.py", "--out", str(path)]
        if kind == "capcut_cloud_handoff":
            return [python, "tools/qa_capcut_cloud_handoff.py", "--out", str(path)]
        if kind == "creator_asset_packs":
            return [python, "tools/qa_creator_asset_packs.py", "--out", str(path)]
        if kind == "localization_audit":
            return [python, "tools/qa_localization_audit.py", "--strict", "--out", str(path)]
        if kind == "review_sample_resources":
            return [
                python,
                "tools/prepare_review_sample_resources.py",
                "--out-root",
                str(DEFAULT_REVIEW_SAMPLE_ROOT),
                "--report-out",
                str(path),
            ]
        if kind == "review_automation":
            return [
                python,
                "tools/generate_review_assets.py",
                "--out-dir",
                str(DEFAULT_REVIEW_OUTPUT_DIR),
                "--report",
                str(path),
                "--sample-root",
                str(DEFAULT_REVIEW_SAMPLE_ROOT),
                "--sample-report",
                str(DEFAULT_REVIEW_SAMPLE_REPORT),
            ]
        if kind == "review_automation_qa":
            return [python, "tools/qa_review_automation.py", "--report", str(DEFAULT_REVIEW_REPORT), "--out", str(path)]
        if kind == "local_ml_backend":
            return [python, "tools/qa_local_ml_backend.py", "--out", str(path)]
        if kind == "ai_edit_corpus_quality":
            return [python, "tools/qa_ai_edit_corpus_quality.py", "--out", str(path)]
        if kind == "ai_edit_corpus_intake":
            return [python, "tools/prepare_ai_edit_corpus_intake.py", "--out", str(path), "--write-templates"]
        if kind == "visual":
            return [python, "tools/qa_visual_regression.py", "--out", "debugCapture/visual_regression"]
        if kind == "visual_baseline":
            return [python, "tools/qa_visual_baseline_audit.py", "--out", str(path)]
        if kind == "ui_visual_baseline_refresh":
            return [python, "tools/qa_ui_visual_baseline_refresh.py", "--out", str(path)]
        if kind == "micro_interactions":
            return [python, "tools/qa_micro_interactions.py", "--out", str(path)]
        if kind == "screenstudio_auto_polish":
            return [python, "tools/qa_screenstudio_auto_polish.py", "--out", str(path)]
        if kind == "screenstudio_naturalness":
            return [python, "tools/qa_screenstudio_naturalness.py", "--out", str(path)]
        if kind == "screenstudio_export_handoff":
            return [python, "tools/qa_screenstudio_export_handoff.py", "--out", str(path)]
        if kind == "screenstudio_parity_gap":
            return [python, "tools/qa_screenstudio_parity_gap.py", "--out", str(path)]
        if kind == "screenstudio_real_corpus":
            return [python, "tools/qa_screenstudio_real_recording_corpus.py", "--out", str(path)]
        if kind == "screenstudio_sidecar_intake":
            return [python, "tools/prepare_screenstudio_sidecar_intake.py", "--out", str(path), "--write-templates"]
        if kind == "screenstudio_productization_next":
            return [python, "tools/qa_screenstudio_productization_next.py", "--out", str(path)]
        if kind == "screenstudio_manual_zoom":
            return [python, "tools/qa_screenstudio_manual_zoom.py", "--out", str(path)]
        if kind == "screenstudio_render_smoke":
            return [python, "tools/qa_screenstudio_render_result_smoke.py", "--out", str(path)]
        if kind == "screenstudio_visual_polish":
            return [
                python,
                "tools/qa_screenstudio_visual_polish.py",
                "--out-dir",
                str(path.parent),
                "--report",
                str(path),
            ]
        if kind == "screenstudio_app_flow":
            return [
                python,
                "tools/qa_screenstudio_app_flow.py",
                "--out-dir",
                str(path.parent),
                "--report",
                str(path),
            ]
        if kind == "screenstudio_gui_flow":
            return [
                python,
                "tools/qa_screenstudio_gui_flow.py",
                "--out-dir",
                str(path.parent),
                "--report",
                str(path),
            ]
        if kind == "release_gap_closure":
            return [python, "tools/qa_release_gap_closure.py", "--out", str(path)]
        if kind == "release_evidence_sprint":
            return [
                python,
                "tools/prepare_release_evidence_sprint.py",
                "--out",
                str(path),
                "--write-files",
            ]
        if kind == "actor_mass_compat":
            return [python, "tools/qa_actor_mass_compat.py", "--out", str(path)]
        if kind == "actor_status" and Path("qa_corpus/actor_corpus_manifest.json").exists():
            return [
                python,
                "tools/actor_corpus_regression.py",
                "--manifest",
                "qa_corpus/actor_corpus_manifest.json",
                "--no-render",
                "--summary-only",
                "--status-out",
                str(path),
            ]
        return None

    @classmethod
    def _fast_qa_commands(cls) -> list[list[str]]:
        rows = build_qa_dashboard_rows()
        commands: list[list[str]] = []
        seen: set[tuple[str, ...]] = set()
        python = sys.executable or "python"
        bootstrap = [python, "tools/build_qa_corpus.py"]
        commands.append(bootstrap)
        seen.add(tuple(bootstrap))
        for row in rows:
            if row.get("kind") in {"crash_report", "actor_render"}:
                continue
            cmd = cls._command_for_row(row)
            if not cmd:
                continue
            key = tuple(cmd)
            if key not in seen:
                seen.add(key)
                commands.append(cmd)
        return commands

    @classmethod
    def _evidence_refresh_commands(
        cls,
        rows: list[dict[str, Any]] | None = None,
    ) -> list[tuple[str, str, list[str]]]:
        source_rows = rows if rows is not None else build_qa_dashboard_rows()
        commands: list[tuple[str, str, list[str]]] = []
        for kind in EVIDENCE_REFRESH_KINDS:
            row = next((item for item in source_rows if str(item.get("kind") or "") == kind), None)
            cmd = cls._command_for_row(row)
            if not row or not cmd:
                continue
            commands.append((kind, str(row.get("label") or kind), cmd))
        return commands

    def _run_selected_qa(self) -> None:
        row = self._selected_row()
        cmd = self._command_for_row(row)
        if not cmd:
            QMessageBox.information(self, "QA Dashboard", "This report does not have a safe one-click runner yet.")
            return
        self._detail.setPlainText("Running QA...\n\n" + " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                cwd=Path.cwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=240,
                check=False,
                **hidden_subprocess_kwargs(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "QA Dashboard", f"QA run failed: {exc}")
            return
        output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
        self.refresh()
        if proc.returncode != 0:
            QMessageBox.warning(self, "QA Dashboard", f"QA returned {proc.returncode}.\n\n{output[-1800:]}")
        else:
            QMessageBox.information(self, "QA Dashboard", "QA completed.")
        _append_history(build_qa_dashboard_rows(), label=str(row.get("kind", "selected")))

    def _run_all_fast_qa(self) -> None:
        commands = self._fast_qa_commands()
        if not commands:
            QMessageBox.information(self, "QA Dashboard", "No safe fast-QA commands are available.")
            return
        logs: list[str] = []
        ok = True
        for idx, cmd in enumerate(commands, start=1):
            self._detail.setPlainText(
                f"Running fast QA {idx}/{len(commands)}...\n\n" + "\n".join(logs[-6:]) + "\n\n" + " ".join(cmd)
            )
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=Path.cwd(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                    check=False,
                    **hidden_subprocess_kwargs(),
                )
            except Exception as exc:
                ok = False
                logs.append(f"FAIL {' '.join(cmd)}\n{exc!r}")
                continue
            if proc.returncode != 0:
                ok = False
            tail = "\n".join(part for part in (proc.stdout[-900:], proc.stderr[-900:]) if part)
            logs.append(f"{'OK' if proc.returncode == 0 else 'FAIL'} {' '.join(cmd)}\n{tail}")
        self.refresh()
        _append_history(self._rows, label="run_all")
        msg = "Fast QA completed." if ok else "Fast QA completed with failures."
        QMessageBox.information(self, "QA Dashboard", msg + "\n\n" + "\n\n".join(logs[-4:])[-2500:])

    def _approve_visual_baseline(self) -> None:
        try:
            from tools.qa_visual_baseline_manager import approve_latest_visual_baseline

            report = approve_latest_visual_baseline()
        except Exception as exc:
            QMessageBox.warning(self, "QA Dashboard", f"Baseline approval failed: {exc}")
            return
        if not report.get("ok"):
            QMessageBox.warning(self, "QA Dashboard", str(report.get("error", "Baseline approval failed.")))
            return
        QMessageBox.information(
            self,
            "QA Dashboard",
            f"Visual baseline approved:\n{report.get('baseline')}\nImages: {report.get('screenshot_count', 0)}",
        )
        self.refresh()

    def _ensure_release_evidence_report(self, row: dict[str, Any]) -> dict[str, Any] | None:
        path = Path(str(row.get("path") or "debugCapture/release_evidence_sprint_qa.json"))
        report = _load_json(path) if path.exists() else {}
        targets = release_evidence_action_targets(report, root=Path.cwd()) if report else {}
        scripts_ready = bool(targets) and all(
            bool(targets.get(key, {}).get("exists"))
            for key in (
                "screenstudio_sidecar_capture",
                "ai_real_case_registration",
                "broadcast_platform_registration",
                "playbook",
            )
        )
        if scripts_ready:
            return report

        cmd = self._command_for_row(row)
        if not cmd:
            QMessageBox.information(
                self,
                "Release Evidence Sprint",
                "This report needs to be generated before evidence actions are available.",
            )
            return None
        self._detail.setPlainText("Preparing release evidence scripts...\n\n" + " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                cwd=Path.cwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=240,
                check=False,
                **hidden_subprocess_kwargs(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Release Evidence Sprint", f"Could not prepare scripts: {exc}")
            return None
        if proc.returncode != 0:
            output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
            QMessageBox.warning(
                self,
                "Release Evidence Sprint",
                f"Script preparation failed with code {proc.returncode}.\n\n{output[-1800:]}",
            )
            return None
        self.refresh()
        report = _load_json(path) if path.exists() else {}
        return report or None

    def _open_evidence_actions(self) -> None:
        row = self._selected_row()
        if not row or str(row.get("kind") or "") != "release_evidence_sprint":
            QMessageBox.information(
                self,
                "Release Evidence Sprint",
                "Select the Release Evidence Sprint report first.",
            )
            return
        report = self._ensure_release_evidence_report(row)
        if not report:
            return
        targets = release_evidence_action_targets(report, root=Path.cwd())
        progress = report.get("progress") if isinstance(report.get("progress"), dict) else release_evidence_progress(report)
        screen_progress = dict(progress.get("screenstudio") or {})
        ai_progress = dict(progress.get("ai") or {})
        requirements = dict(screen_progress.get("requirements") or {})
        proof_lines: list[str] = []
        for key in ("cursor_sidecar", "click", "drag", "hotkey", "auto_zoom"):
            req = dict(requirements.get(key) or {})
            if not req:
                continue
            proof_lines.append(
                f"- {req.get('label', key)}: "
                f"{int(req.get('ready', 0) or 0)}/"
                f"{int(req.get('target', 0) or 0)} ready "
                f"({int(req.get('needed', 0) or 0)} needed)"
            )
        work_queue = list(report.get("work_queue") or release_evidence_next_items(report, limit=3))
        queue_lines = [
            f"- {item.get('summary', item.get('kind', 'evidence'))}"
            for item in work_queue[:3]
            if isinstance(item, dict)
        ]
        box = QMessageBox(self)
        box.setWindowTitle("Release Evidence Sprint")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"Collect real release evidence ({int(progress.get('overall_percent', 0) or 0)}%)")
        box.setInformativeText(
            "Open the capture or registration tools from here. These actions do not create fake pass data.\n\n"
            f"Screen Studio interactions: {int(screen_progress.get('interaction_ready', 0) or 0)}/"
            f"{int(screen_progress.get('target', 0) or 0)} ready "
            f"({int(screen_progress.get('needed', 0) or 0)} needed)\n"
            f"Cursor sidecars present: {int(screen_progress.get('sidecar_ready', 0) or 0)}\n"
            f"AI real cases: {int(ai_progress.get('real_cases', 0) or 0)}/"
            f"{int(ai_progress.get('target', 0) or 0)} ready "
            f"({int(ai_progress.get('needed', 0) or 0)} needed)"
            + ("\n\nRequired Screen Studio proof:\n" + "\n".join(proof_lines) if proof_lines else "")
            + ("\n\nNext work:\n" + "\n".join(queue_lines) if queue_lines else "")
        )
        screen_btn = box.addButton("Record Cursor Sidecars", QMessageBox.ButtonRole.ActionRole)
        next_slot_btn = box.addButton("Record Next Slot", QMessageBox.ButtonRole.ActionRole)
        ai_btn = box.addButton("Register AI Cases", QMessageBox.ButtonRole.ActionRole)
        next_ai_btn = box.addButton("Register Next AI Case", QMessageBox.ButtonRole.ActionRole)
        broadcast_btn = box.addButton("Register Broadcast Evidence", QMessageBox.ButtonRole.ActionRole)
        refresh_btn = box.addButton("Refresh Evidence Status", QMessageBox.ButtonRole.ActionRole)
        screen_qa_btn = box.addButton("Run Cursor QA", QMessageBox.ButtonRole.ActionRole)
        ai_qa_btn = box.addButton("Run AI QA", QMessageBox.ButtonRole.ActionRole)
        gate_btn = box.addButton("Run Release Gate", QMessageBox.ButtonRole.ActionRole)
        playbook_btn = box.addButton("Open Playbook", QMessageBox.ButtonRole.ActionRole)
        folder_btn = box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is screen_btn:
            self._launch_evidence_target(targets["screenstudio_sidecar_capture"])
        elif clicked is next_slot_btn:
            self._launch_next_screenstudio_slot(report)
        elif clicked is ai_btn:
            self._launch_evidence_target(targets["ai_real_case_registration"])
        elif clicked is next_ai_btn:
            self._launch_next_ai_case(report)
        elif clicked is broadcast_btn:
            self._launch_evidence_target(targets["broadcast_platform_registration"])
        elif clicked is refresh_btn:
            self._run_evidence_refresh()
        elif clicked is screen_qa_btn:
            self._run_evidence_followup("screenstudio_real_corpus")
        elif clicked is ai_qa_btn:
            self._run_evidence_followup("ai_edit_corpus_quality")
        elif clicked is gate_btn:
            self._run_evidence_followup("release_gap_closure")
        elif clicked is playbook_btn:
            self._launch_evidence_target(targets["playbook"])
        elif clicked is folder_btn:
            self._launch_evidence_target(targets["folder"])

    def _launch_next_screenstudio_slot(self, report: dict[str, Any]) -> None:
        target = release_evidence_next_screenstudio_capture_target(report, root=Path.cwd(), write_file=True)
        if not target.get("ok"):
            QMessageBox.information(
                self,
                "Release Evidence Sprint",
                "No Screen Studio interaction slot is waiting for capture.",
            )
            return
        self._launch_evidence_target(target)

    def _launch_next_ai_case(self, report: dict[str, Any]) -> None:
        target = release_evidence_next_ai_case_target(report, root=Path.cwd(), write_file=True)
        if not target.get("ok"):
            QMessageBox.information(
                self,
                "Release Evidence Sprint",
                "No AI real-case template is waiting for registration.",
            )
            return
        self._launch_evidence_target(target)

    def _row_for_kind(self, kind: str) -> dict[str, Any] | None:
        for row in self._rows:
            if str(row.get("kind") or "") == kind:
                return row
        return None

    def _run_evidence_refresh(self) -> None:
        commands = self._evidence_refresh_commands(self._rows)
        if not commands:
            QMessageBox.information(self, "Release Evidence Sprint", "No evidence refresh commands are available.")
            return
        logs: list[str] = []
        ok = True
        for idx, (kind, label, cmd) in enumerate(commands, start=1):
            self._detail.setPlainText(
                f"Refreshing evidence status {idx}/{len(commands)}: {label}\n\n"
                + "\n\n".join(logs[-3:])
                + "\n\n"
                + " ".join(cmd)
            )
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=Path.cwd(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=360,
                    check=False,
                    **hidden_subprocess_kwargs(),
                )
            except Exception as exc:
                ok = False
                logs.append(f"FAIL {label} ({kind})\n{exc!r}")
                continue
            tail = "\n".join(part for part in (proc.stdout[-900:], proc.stderr[-900:]) if part)
            if proc.returncode != 0:
                ok = False
            logs.append(f"{'OK' if proc.returncode == 0 else 'FAIL'} {label} ({kind})\n{tail}")
        self.refresh()
        _append_history(self._rows, label="evidence_refresh")
        title = "Evidence status refreshed." if ok else "Evidence status refreshed with failures."
        QMessageBox.information(self, "Release Evidence Sprint", title + "\n\n" + "\n\n".join(logs[-4:])[-2600:])

    def _run_evidence_followup(self, kind: str) -> None:
        row = self._row_for_kind(kind)
        cmd = self._command_for_row(row)
        if not row or not cmd:
            QMessageBox.information(self, "Release Evidence Sprint", f"No runnable QA row found for {kind}.")
            return
        self._detail.setPlainText("Running evidence follow-up QA...\n\n" + " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                cwd=Path.cwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                check=False,
                **hidden_subprocess_kwargs(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Release Evidence Sprint", f"Follow-up QA failed: {exc}")
            return
        output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
        self.refresh()
        if proc.returncode != 0:
            QMessageBox.warning(
                self,
                "Release Evidence Sprint",
                f"{row.get('label', kind)} returned {proc.returncode}.\n\n{output[-1800:]}",
            )
            return
        QMessageBox.information(self, "Release Evidence Sprint", f"{row.get('label', kind)} completed.")

    def _launch_evidence_target(self, target: dict[str, Any]) -> None:
        path = Path(str(target.get("path") or ""))
        if not path.exists():
            QMessageBox.warning(
                self,
                "Release Evidence Sprint",
                f"Target is missing. Run Selected QA first.\n\n{path}",
            )
            return
        kind = str(target.get("kind") or "")
        if kind == "powershell":
            self._launch_visible_powershell(path)
            return
        self._open_path(path)

    def _launch_visible_powershell(self, script: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(
                    [
                        "powershell.exe",
                        "-NoLogo",
                        "-NoExit",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(script),
                    ],
                    cwd=Path.cwd(),
                )
            else:
                subprocess.Popen(["sh", str(script)], cwd=Path.cwd())
        except Exception as exc:
            QMessageBox.warning(self, "Release Evidence Sprint", f"Could not open terminal: {exc}")
            return
        QMessageBox.information(
            self,
            "Release Evidence Sprint",
            "A visible terminal was opened. Follow its prompts, then rerun the matching QA report.",
        )

    def _open_path(self, path: Path) -> None:
        try:
            import os

            os.startfile(str(path))
        except Exception as exc:
            QMessageBox.warning(self, "QA Dashboard", f"Could not open path:\n{path}\n\n{exc}")

    def _open_selected_folder(self) -> None:
        row = self._selected_row()
        if not row:
            return
        path = Path(str(row.get("path", "")))
        folder = path.parent if path.suffix else path
        if not folder.exists():
            folder = Path("debugCapture")
        try:
            self._open_path(folder)
        except Exception:
            pass

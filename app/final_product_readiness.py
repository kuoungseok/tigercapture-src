"""Final product-readiness gate for commercial editing polish.

This module is intentionally Qt-free. It reads the existing QA artifacts and
turns the broad product backlog into concrete release-readiness areas:
practical editing flow, real corpus coverage, preview/GPU performance,
Color/Audio accuracy, professional runtime parity, timeline feel,
preset/template quality, Screen Studio interaction evidence, VTuber/broadcast
readiness, crash recovery, and release packaging.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.release_evidence_sprint import (
    release_evidence_action_targets,
    release_evidence_next_items,
    release_evidence_progress,
)


PREVIEW_ADVISORY_STAGE_LABELS = {"preview.refresh.render"}
PREVIEW_BLOCKING_STAGE_PREFIXES = ("preview.stage.",)


AREA_SPECS: tuple[tuple[str, str], ...] = (
    ("practical_editing_flow", "실사용 편집 플로우"),
    ("real_project_corpus", "실제 프로젝트 corpus"),
    ("screenstudio_interaction_corpus", "Screen Studio interaction corpus"),
    ("preview_gpu_performance", "Preview/GPU 성능"),
    ("preview_scrub_claims", "Preview scrub/seek claim"),
    ("ai_edit_claim_quality", "AI edit claim quality"),
    ("color_audio_accuracy", "Color/Audio 정확도"),
    ("professional_runtime_parity", "Professional runtime parity"),
    ("vtuber_broadcast_readiness", "VTuber/Broadcast readiness"),
    ("timeline_polish", "타임라인 조작감"),
    ("preset_template_quality", "프리셋/템플릿 품질"),
    ("crash_recovery_project_repair", "Crash recovery / project repair"),
    ("release_packaging", "릴리즈 패키징"),
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest(root: Path, *patterns: str) -> Path | None:
    rows: list[Path] = []
    for pattern in patterns:
        rows.extend(path for path in root.glob(pattern) if path.is_file())
    rows.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return rows[0] if rows else None


def _preferred_artifact(root: Path, canonical: str, *fallback_patterns: str) -> Path | None:
    """Return the canonical QA artifact before falling back to experimental runs."""
    path = root / canonical
    if path.is_file():
        return path
    return _latest(root, *fallback_patterns)


def _release_evidence_sprint_snapshot(root: Path, *, kinds: set[str] | None = None) -> dict[str, Any]:
    """Return the generated evidence sprint state without treating it as proof."""

    path = root / "debugCapture" / "release_evidence_sprint_qa.json"
    report = _load_json(path)
    if not report:
        return {"reported": False, "report_path": str(path)}
    progress = report.get("progress") if isinstance(report.get("progress"), dict) else release_evidence_progress(report)
    targets = release_evidence_action_targets(report, root=root)
    cached_queue = list(report.get("work_queue") or [])
    queue = cached_queue or release_evidence_next_items(report, limit=8)
    if kinds:
        queue = [
            dict(item)
            for item in queue
            if isinstance(item, dict) and str(item.get("kind") or "") in kinds
        ]
        if not queue and cached_queue:
            queue = [
                dict(item)
                for item in release_evidence_next_items(report, limit=0)
                if isinstance(item, dict) and str(item.get("kind") or "") in kinds
            ]
    return {
        "reported": True,
        "report_path": str(path),
        "overall_percent": int(progress.get("overall_percent", 0) or 0),
        "ready": bool(progress.get("ready")),
        "blockers": list(progress.get("blockers") or []),
        "progress": progress,
        "action_targets": targets,
        "work_queue": queue[:6],
    }


def _release_evidence_automation_snapshot(root: Path) -> dict[str, Any]:
    """Return the safe automation/evidence-corpus state for release handoff."""

    path = root / "debugCapture" / "release_evidence_automation_qa.json"
    report = _load_json(path)
    if not report:
        return {"reported": False, "report_path": str(path)}
    automated = report.get("automated_corpus") if isinstance(report.get("automated_corpus"), dict) else {}
    return {
        "reported": True,
        "report_path": str(path),
        "automation_ready": bool(report.get("automation_ready")),
        "blockers": list(report.get("blockers") or []),
        "summary": dict(report.get("summary") or {}) if isinstance(report.get("summary"), dict) else {},
        "automated_corpus": dict(automated),
    }


def _score(ok: bool, partial: bool = False) -> int:
    if ok:
        return 100
    return 75 if partial else 45


def _area(
    area_id: str,
    *,
    score: int,
    summary: str,
    actions: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score = max(0, min(100, int(score)))
    if score >= 90:
        level = "ready"
    elif score >= 70:
        level = "attention"
    else:
        level = "blocked"
    label = dict(AREA_SPECS).get(area_id, area_id)
    return {
        "id": area_id,
        "label": label,
        "score": score,
        "level": level,
        "release_blocking": score < 90,
        "summary": summary,
        "actions": list(actions or []),
        "evidence": dict(evidence or {}),
    }


def _summary_counts(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("summary", {})
    return value if isinstance(value, dict) else {}


def _float_metric(payload: dict[str, Any], key: str, default: float) -> float:
    if key not in payload:
        return float(default)
    value = payload.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _int_metric(payload: dict[str, Any], key: str, default: int = 0) -> int:
    if key not in payload:
        return int(default)
    try:
        return int(float(payload.get(key) or 0))
    except Exception:
        return int(default)


def _practical_editing_flow(root: Path) -> dict[str, Any]:
    app_flow = _load_json(root / "debugCapture" / "screenstudio_app_flow" / "screenstudio_app_flow_report.json")
    gui_flow = _load_json(root / "debugCapture" / "screenstudio_gui_flow" / "screenstudio_gui_flow_report.json")
    preset_app = _load_json(root / "debugCapture" / "preset_application_corpus_auto.json")
    app_ok = bool(app_flow.get("ok"))
    gui_ok = bool(gui_flow.get("ok"))
    projects = len(preset_app.get("projects", []) or [])
    partial = app_ok or gui_ok or projects > 0
    score = 100 if app_ok and gui_ok and projects > 0 else (80 if partial else 50)
    actions: list[str] = []
    if not app_ok:
        actions.append("Run tools/qa_screenstudio_app_flow.py and inspect import/timeline/export flow.")
    if not gui_ok:
        actions.append("Run tools/qa_screenstudio_gui_flow.py and inspect launcher/editor/dashboard screenshots.")
    if projects <= 0:
        actions.append("Run tools/qa_preset_application_corpus.py so preset drag/click/export paths have project coverage.")
    return _area(
        "practical_editing_flow",
        score=score,
        summary=f"app_flow={'ok' if app_ok else 'attention'}, gui_flow={'ok' if gui_ok else 'attention'}, preset projects={projects}.",
        actions=actions,
        evidence={
            "screenstudio_app_flow": bool(app_flow),
            "screenstudio_gui_flow": bool(gui_flow),
            "preset_application_projects": projects,
        },
    )


def _real_project_corpus(root: Path) -> dict[str, Any]:
    manifest = _load_json(root / "qa_corpus" / "product_qa_corpus_manifest.json")
    project_qa = _load_json(root / "debugCapture" / "project_qa_report.json")
    real = _load_json(root / "debugCapture" / "screenstudio_real_recording_corpus_qa.json")
    groups = len(manifest.get("sample_groups", []) or [])
    fixture_projects = len(list((root / "qa_corpus" / "projects").glob("*.tgp"))) if (root / "qa_corpus" / "projects").exists() else 0
    qa_projects = int(project_qa.get("project_count", len(project_qa.get("projects", []) or [])) or 0)
    real_summary = _summary_counts(real)
    real_valid = int(real_summary.get("valid_files", 0) or 0)
    target = int(real_summary.get("target_min", 20) or 20)
    score = min(100, int((min(fixture_projects, 5) / 5) * 35 + (min(qa_projects, 5) / 5) * 30 + (min(real_valid, target) / max(1, target)) * 35))
    actions: list[str] = []
    if fixture_projects < 5:
        actions.append("Add at least 5 real or fixture .tgp projects under qa_corpus/projects.")
    if qa_projects < 5:
        actions.append("Run tools/qa_project_audit.py across the project corpus.")
    if real_valid < target:
        actions.append("Register 20-50 real screen recordings with tools/register_screenstudio_real_recording.py --scan-root <recordings-folder>.")
    return _area(
        "real_project_corpus",
        score=score,
        summary=f"fixture projects={fixture_projects}, audited projects={qa_projects}, real recordings={real_valid}/{target}, groups={groups}.",
        actions=actions,
        evidence={
            "sample_groups": groups,
            "fixture_projects": fixture_projects,
            "audited_projects": qa_projects,
            "real_recordings": real_valid,
            "real_recording_target": target,
        },
    )


def _screenstudio_interaction_corpus(root: Path) -> dict[str, Any]:
    path = root / "debugCapture" / "screenstudio_real_recording_corpus_qa.json"
    report = _load_json(path)
    intake = _load_json(root / "debugCapture" / "screenstudio_sidecar_intake_qa.json")
    sprint = _release_evidence_sprint_snapshot(root, kinds={"screenstudio_interaction_evidence"})
    automation = _release_evidence_automation_snapshot(root)
    summary = _summary_counts(report)
    intake_summary = _summary_counts(intake)
    target = max(1, _int_metric(summary, "target_min", 20))
    valid_files = _int_metric(summary, "valid_files")
    video_probe_ok = _int_metric(summary, "video_probe_ok")
    cursor_sidecar_ready = _int_metric(summary, "cursor_sidecar_ready")
    click_ready = _int_metric(summary, "click_ready")
    drag_ready = _int_metric(summary, "drag_ready")
    hotkey_ready = _int_metric(summary, "hotkey_ready")
    auto_zoom_ready = _int_metric(summary, "auto_zoom_ready")
    interaction_ready = _int_metric(
        summary,
        "interaction_ready",
        _int_metric(summary, "full_interaction_ready"),
    )
    sidecar_intake_templates = _int_metric(intake_summary, "templates_written")
    sidecar_intake_needs_sidecar = _int_metric(intake_summary, "needs_sidecar")
    probe_available = bool(summary.get("probe_available"))
    real_world_ready = bool(report.get("real_world_ready") or summary.get("real_world_ready"))
    replacement_claim_ready = bool(report.get("replacement_claim_ready") or summary.get("replacement_claim_ready"))
    blockers = list(report.get("replacement_claim_blockers") or [])

    actions: list[str] = []
    if not report:
        actions.append("Run tools/qa_screenstudio_real_recording_corpus.py after registering real screen recordings.")
        actions.append("Register 20-50 real screen recordings with cursor/click/drag/hotkey/auto-zoom sidecars.")
    if valid_files < target:
        actions.append(f"Add {target - valid_files} more valid real screen recordings for Screen Studio parity QA.")
    if probe_available and video_probe_ok < target:
        actions.append(f"Replace or re-encode {target - video_probe_ok} recordings that do not pass frame probing.")
    if cursor_sidecar_ready < target:
        actions.append(f"Attach cursor sidecars to {target - cursor_sidecar_ready} more recordings.")
        actions.append(
            "Run tools/prepare_screenstudio_sidecar_intake.py --write-templates to create per-recording "
            ".cursor.template.json checklists before capturing real sidecars."
        )
        actions.append(
            "Use tools/record_screenstudio_cursor_sidecar.py --from-template <filled.cursor.template.json> "
            "--register to write counted .cursor.json sidecars after reviewing real interaction events."
        )
        actions.append(
            "Or run tools/promote_screenstudio_sidecar_templates.py --register after filling multiple templates."
        )
    if click_ready < target:
        actions.append(f"Capture click/down/release events in {target - click_ready} more sidecars.")
    if drag_ready < target:
        actions.append(f"Capture drag spans in {target - drag_ready} more sidecars.")
    if hotkey_ready < target:
        actions.append(f"Capture hotkey events in {target - hotkey_ready} more sidecars.")
    if auto_zoom_ready < target:
        actions.append(f"Validate auto-zoom windows in {target - auto_zoom_ready} more sidecars.")
    if interaction_ready < target:
        actions.append(f"Make {target - interaction_ready} more recordings fully interaction-ready.")
    if not real_world_ready:
        actions.append("Do not market this as a Screen Studio replacement until the real interaction corpus is ready.")
    elif not replacement_claim_ready:
        actions.append("Keep Screen Studio replacement claims disabled until replacement_claim_ready is true.")

    ratios = [
        valid_files / target,
        (video_probe_ok / target if probe_available else 1.0),
        cursor_sidecar_ready / target,
        click_ready / target,
        drag_ready / target,
        hotkey_ready / target,
        auto_zoom_ready / target,
        interaction_ready / target,
    ]
    score = int(round(sum(min(1.0, max(0.0, ratio)) for ratio in ratios) / len(ratios) * 100))
    if not report:
        score = 45
    elif not real_world_ready:
        score = min(score, 69)
    elif not replacement_claim_ready:
        score = min(score, 85)

    return _area(
        "screenstudio_interaction_corpus",
        score=score,
        summary=(
            f"valid={valid_files}/{target}, sidecars={cursor_sidecar_ready}/{target}, "
            f"click/drag/hotkey/zoom={click_ready}/{drag_ready}/{hotkey_ready}/{auto_zoom_ready}, "
            f"interaction_ready={interaction_ready}/{target}, replacement_claim={replacement_claim_ready}."
        ),
        actions=actions,
        evidence={
            "report_path": str(path) if path.is_file() else "",
            "target_min": target,
            "valid_files": valid_files,
            "video_probe_ok": video_probe_ok,
            "probe_available": probe_available,
            "cursor_sidecar_ready": cursor_sidecar_ready,
            "click_ready": click_ready,
            "drag_ready": drag_ready,
            "hotkey_ready": hotkey_ready,
            "auto_zoom_ready": auto_zoom_ready,
            "interaction_ready": interaction_ready,
            "sidecar_intake_templates": sidecar_intake_templates,
            "sidecar_intake_needs_sidecar": sidecar_intake_needs_sidecar,
            "sidecar_intake_reported": bool(intake),
            "sidecar_capture_tool": "tools/record_screenstudio_cursor_sidecar.py",
            "release_evidence_sprint": sprint,
            "release_evidence_automation": automation,
            "real_world_ready": real_world_ready,
            "replacement_claim_ready": replacement_claim_ready,
            "replacement_claim_blockers": blockers,
        },
    )


def _preview_gpu_performance(root: Path) -> dict[str, Any]:
    path = _preferred_artifact(
        root,
        "debugCapture/preview_perf_report.json",
        "debugCapture/preview_perf*.json",
        "debugCapture/**/preview_perf*.json",
    )
    report = _load_json(path) if path else {}
    native_candidates = report.get("native_gpu_candidates", []) if isinstance(report, dict) else []
    render_rows = list(report.get("preview_render", []) or []) if isinstance(report, dict) else []
    stage_rows = report.get("preview_stage_summary", report.get("stage_summary", [])) if isinstance(report, dict) else []
    slow_blocking: list[str] = []
    slow_advisory: list[str] = []

    def _classify_slow(name: str, avg: float, p95: float, *, advisory: bool = False) -> None:
        text = f"{name} avg={avg:.2f} p95={p95:.2f}"
        if advisory:
            slow_advisory.append(text)
            return
        if name in PREVIEW_ADVISORY_STAGE_LABELS:
            slow_advisory.append(text)
            return
        if name.startswith(PREVIEW_BLOCKING_STAGE_PREFIXES):
            slow_blocking.append(text)
            return
        slow_advisory.append(text)

    if isinstance(stage_rows, dict):
        rows_iter = stage_rows.items()
    else:
        rows_iter = enumerate(stage_rows if isinstance(stage_rows, list) else [])
    for key, value in rows_iter:
        row = value if isinstance(value, dict) else {}
        name = str(row.get("stage") or row.get("name") or key)
        avg = float(row.get("avg_ms", row.get("mean_ms", 0.0)) or 0.0)
        p95 = float(row.get("p95_ms", 0.0) or 0.0)
        if avg > 16.0 or p95 > 33.0:
            _classify_slow(name, avg, p95)
    for render in render_rows:
        if not isinstance(render, dict):
            continue
        project_name = Path(str(render.get("project") or "")).name or "preview_project"
        context_summaries = render.get("stage_summary_by_context") or {}
        has_context_summaries = isinstance(context_summaries, dict) and bool(context_summaries)
        playback_summary = render.get("playback_frame_summary", {}) or {}
        playback_count = int(playback_summary.get("count", 0) or 0) if isinstance(playback_summary, dict) else 0
        frame_summary = playback_summary if playback_count > 0 else (render.get("frame_summary", {}) or {})
        if isinstance(frame_summary, dict):
            avg = float(frame_summary.get("avg_ms", 0.0) or 0.0)
            p95 = float(frame_summary.get("p95_ms", 0.0) or 0.0)
            if avg > 33.0 or p95 > 50.0:
                target = slow_blocking if playback_count > 0 else slow_advisory
                target.append(f"{project_name} frame avg={avg:.2f} p95={p95:.2f}")
        if has_context_summaries:
            playback_stages = list(context_summaries.get("playback") or [])
            for row in playback_stages:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("label") or row.get("stage") or "preview_stage")
                avg = float(row.get("avg_ms", row.get("mean_ms", 0.0)) or 0.0)
                p95 = float(row.get("p95_ms", 0.0) or 0.0)
                if avg > 16.0 or p95 > 33.0:
                    _classify_slow(name, avg, p95)
            for context, rows in context_summaries.items():
                if context == "playback":
                    continue
                for row in list(rows or []):
                    if not isinstance(row, dict):
                        continue
                    name = str(row.get("label") or row.get("stage") or "preview_stage")
                    avg = float(row.get("avg_ms", row.get("mean_ms", 0.0)) or 0.0)
                    p95 = float(row.get("p95_ms", 0.0) or 0.0)
                    if avg > 16.0 or p95 > 33.0:
                        _classify_slow(f"{context}.{name}", avg, p95, advisory=True)
        else:
            for row in list(render.get("stage_summary", []) or []):
                if not isinstance(row, dict):
                    continue
                name = str(row.get("label") or row.get("stage") or "preview_stage")
                avg = float(row.get("avg_ms", row.get("mean_ms", 0.0)) or 0.0)
                p95 = float(row.get("p95_ms", 0.0) or 0.0)
                if avg > 16.0 or p95 > 33.0:
                    _classify_slow(name, avg, p95)
    has_context_report = any(
        isinstance(row, dict) and isinstance(row.get("stage_summary_by_context"), dict)
        for row in render_rows
    )
    if isinstance(native_candidates, list):
        for row in native_candidates:
            if not isinstance(row, dict):
                continue
            name = str(row.get("label") or row.get("stage") or row.get("candidate") or "native_candidate")
            avg = float(row.get("avg_ms", row.get("mean_ms", 0.0)) or 0.0)
            p95 = float(row.get("p95_ms", 0.0) or 0.0)
            if avg > 16.0 or p95 > 33.0:
                _classify_slow(
                    name,
                    avg,
                    p95,
                    advisory=has_context_report and str(row.get("context") or "") != "playback",
                )
    slow_blocking = list(dict.fromkeys(slow_blocking))
    slow_advisory = list(dict.fromkeys(slow_advisory))
    has_render_samples = any(bool(row.get("ok", True)) for row in render_rows if isinstance(row, dict))
    if report and has_render_samples and not slow_blocking:
        score = 100
    elif report and has_render_samples:
        score = 82 if len(slow_blocking) <= 3 else 78
    elif report:
        score = 68
    else:
        score = 55
    actions = []
    if not report:
        actions.append("Run tools/qa_preview_perf.py to measure decode/proxy/filter/actor stages.")
    elif not has_render_samples:
        actions.append("Run tools/qa_preview_perf.py with render samples; skip-render reports cannot release-gate preview playback.")
    if slow_blocking:
        actions.append("Move slow preview stages to frame server, shader/native filter paths, or actor GPU compositor.")
    if slow_advisory:
        actions.append("Inspect preview warm-up/seek advisory stages separately from steady playback bottlenecks.")
    if native_candidates:
        actions.append("Prioritize native/GPU candidates reported by preview perf QA.")
    return _area(
        "preview_gpu_performance",
        score=score,
        summary=(
            f"preview perf report={'yes' if report else 'no'}, "
            f"render samples={len(render_rows)}, "
            f"blocking slow={len(slow_blocking)}, advisory slow={len(slow_advisory)}, "
            f"native candidates={len(native_candidates) if isinstance(native_candidates, list) else 0}."
        ),
        actions=actions,
        evidence={
            "report_path": str(path or ""),
            "render_samples": len(render_rows),
            "slow_stages": slow_blocking[:8],
            "advisory_slow_stages": slow_advisory[:8],
            "native_gpu_candidates": native_candidates[:8] if isinstance(native_candidates, list) else [],
        },
    )


def _preview_scrub_claims(root: Path) -> dict[str, Any]:
    path = _preferred_artifact(
        root,
        "debugCapture/preview_scrub_readiness_qa.json",
        "debugCapture/preview_scrub_readiness*.json",
        "debugCapture/**/preview_scrub_readiness*.json",
    )
    report = _load_json(path) if path else {}
    summary = _summary_counts(report)
    current_ready = bool(report.get("current_corpus_scrub_ready"))
    release_ready = bool(report.get("release_scrub_claim_ready"))
    blockers = list(report.get("release_blockers") or [])
    coverage = report.get("coverage") if isinstance(report.get("coverage"), dict) else {}
    missing_coverage = list(summary.get("missing_release_coverage") or [])
    projects = _int_metric(summary, "projects", 0)
    ready_projects = _int_metric(summary, "ready_projects", 0)
    warning_projects = _int_metric(summary, "warning_projects", 0)
    blocked_projects = _int_metric(summary, "blocked_projects", 0)
    raw_score = _int_metric(report, "score", 0)
    if release_ready:
        score = 100
    elif current_ready:
        score = min(86, max(75, raw_score))
    elif report:
        score = min(68, max(45, raw_score))
    else:
        score = 45
    actions = []
    if not report:
        actions.append("Run tools/qa_preview_scrub_readiness.py --auto-hires to gate real scrub/seek smoothness.")
    if blocked_projects:
        actions.append("Fix blocked scrub projects before claiming smooth scrubbing.")
    if missing_coverage:
        actions.append("Add missing scrub QA coverage for: " + ", ".join(missing_coverage[:8]) + ".")
    if blockers and "score_below_release_threshold" in blockers:
        actions.append("Reduce seek/decode hotspots until preview scrub readiness score is at least 85.")
    return _area(
        "preview_scrub_claims",
        score=score,
        summary=(
            f"scrub report={'yes' if report else 'no'}, projects={projects}, "
            f"ready={ready_projects}, warnings={warning_projects}, blocked={blocked_projects}, "
            f"release claim={release_ready}."
        ),
        actions=actions,
        evidence={
            "report_path": str(path or ""),
            "score": raw_score,
            "current_corpus_scrub_ready": current_ready,
            "release_scrub_claim_ready": release_ready,
            "release_blockers": blockers,
            "coverage": coverage,
            "missing_release_coverage": missing_coverage,
            "worst_projects": list(report.get("worst_projects") or [])[:5],
            "top_seek_hotspots": list(report.get("top_seek_hotspots") or [])[:8],
        },
    )


def _ai_edit_claim_quality(root: Path) -> dict[str, Any]:
    path = _preferred_artifact(
        root,
        "debugCapture/ai_edit_corpus_quality_qa.json",
        "debugCapture/ai_edit_corpus_quality*.json",
        "debugCapture/**/ai_edit_corpus_quality*.json",
    )
    report = _load_json(path) if path else {}
    intake = _load_json(root / "debugCapture" / "ai_edit_corpus_intake_qa.json")
    sprint = _release_evidence_sprint_snapshot(root, kinds={"ai_real_edit_case"})
    automation = _release_evidence_automation_snapshot(root)
    summary = _summary_counts(report)
    intake_summary = _summary_counts(intake)
    provider = report.get("provider") if isinstance(report.get("provider"), dict) else {}
    safe_mvp_ready = bool(report.get("safe_mvp_ready"))
    smart_claim_ready = bool(report.get("smart_edit_claim_ready"))
    claim_blockers = list(report.get("claim_blockers") or [])
    cases = _int_metric(summary, "cases", 0)
    real_cases = _int_metric(summary, "real_cases", 0)
    min_real_cases = _int_metric(summary, "min_real_cases", 20)
    intake_templates = _int_metric(intake_summary, "templates_written")
    intake_missing_real_cases = _int_metric(intake_summary, "missing_real_cases")
    failures = _int_metric(summary, "failures", 0)
    raw_score = _int_metric(report, "score", 0)
    if smart_claim_ready:
        score = 100
    elif safe_mvp_ready:
        score = min(86, max(75, raw_score))
    elif report:
        score = min(68, max(45, raw_score))
    else:
        score = 45
    actions = []
    if not report:
        actions.append("Run tools/qa_ai_edit_corpus_quality.py --use-provider before claiming smart AI editing.")
    if not provider.get("direct_generation_ready") and "provider_execution_fallbacks_present" not in claim_blockers:
        actions.append("Wire or repair a local LLM, Claude, or Codex executor/direct generator, then exercise it on the AI edit corpus.")
        if provider.get("executor_wired"):
            actions.append("Rerun tools/qa_ai_edit_corpus_quality.py --use-provider after clearing or repairing the provider's last executor failure.")
    if real_cases < min_real_cases:
        actions.append(f"Add real AI edit corpus cases: {real_cases}/{min_real_cases} recorded projects covered.")
        actions.append("Run tools/prepare_ai_edit_corpus_intake.py --write-templates to create real-case intake templates.")
        actions.append(
            "Fill each AI intake template, then use tools/register_ai_edit_corpus_case.py "
            "--from-template <filled.template.json> to add reviewed real cases to the AI corpus manifest."
        )
        actions.append("Or run tools/register_ai_edit_corpus_templates.py after filling multiple AI intake templates.")
    if failures:
        actions.append("Fix failing AI edit corpus cases before marketing AI-assisted editing quality.")
    if "provider_execution_failed_on_corpus" in claim_blockers:
        actions.append("Run provider corpus QA again after fixing the selected AI provider command, login, or endpoint.")
    if "provider_execution_fallbacks_present" in claim_blockers:
        actions.append(
            "Rerun provider corpus QA with --provider-timeout 240 --provider-retries 1 and tune until all AI cases avoid fallback."
        )
    if "coverage_categories_missing" in claim_blockers:
        actions.append("Cover Korean, English, tutorial, shortform, product, and long-form AI edit scenarios.")
    return _area(
        "ai_edit_claim_quality",
        score=score,
        summary=(
            f"AI corpus report={'yes' if report else 'no'}, cases={cases}, real={real_cases}/{min_real_cases}, "
            f"safe MVP={safe_mvp_ready}, smart claim={smart_claim_ready}."
        ),
        actions=actions,
        evidence={
            "report_path": str(path or ""),
            "score": raw_score,
            "safe_mvp_ready": safe_mvp_ready,
            "smart_edit_claim_ready": smart_claim_ready,
            "claim_blockers": claim_blockers,
            "provider": provider,
            "real_cases": real_cases,
            "min_real_cases": min_real_cases,
            "ai_intake_templates": intake_templates,
            "ai_intake_missing_real_cases": intake_missing_real_cases,
            "ai_intake_reported": bool(intake),
            "ai_case_registration_tool": "tools/register_ai_edit_corpus_case.py",
            "release_evidence_sprint": sprint,
            "release_evidence_automation": automation,
            "failures": list(report.get("failures") or [])[:8],
            "missing_categories": list(summary.get("missing_categories") or []),
        },
    )


def _color_audio_accuracy(root: Path) -> dict[str, Any]:
    report = _load_json(root / "debugCapture" / "color_audio_accuracy_qa.json")
    summary = _summary_counts(report)
    checks = int(summary.get("checks", 0) or 0)
    failures = int(summary.get("failures", 0) or 0)
    samples = summary.get("sample_sources", {}) if isinstance(summary, dict) else {}
    real_samples = 0
    if isinstance(samples, dict):
        real_samples = len(samples.get("video", []) or []) + len(samples.get("audio", []) or [])
    ok = bool(report.get("ok")) and checks >= 16 and failures == 0 and real_samples >= 2
    partial = bool(report.get("ok")) and checks >= 16 and failures == 0
    actions: list[str] = []
    if not report:
        actions.append("Run tools/qa_color_audio_accuracy.py.")
    if real_samples < 2:
        actions.append("Add real video/audio samples to qa_corpus/color_audio_samples and rerun accuracy QA.")
    if failures:
        actions.append("Fix failing scopes/LUT/loudness/dialogue-cleanup checks before release.")
    return _area(
        "color_audio_accuracy",
        score=_score(ok, partial),
        summary=f"checks={checks}, failures={failures}, real samples={real_samples}.",
        actions=actions,
        evidence={"checks": checks, "failures": failures, "real_samples": real_samples},
    )


def _professional_runtime_parity(root: Path) -> dict[str, Any]:
    runtime_path = root / "debugCapture" / "professional_runtime_next_qa.json"
    pipeline_path = root / "debugCapture" / "professional_pipeline_next_qa.json"
    runtime = _load_json(runtime_path)
    pipeline = _load_json(pipeline_path)
    if not runtime:
        try:
            from app.professional_runtime import professional_runtime_verification_report

            runtime = professional_runtime_verification_report(out_dir=root / "debugCapture")
        except Exception:
            runtime = {}
    runtime_summary = _summary_counts(runtime)
    runtime_checks = runtime.get("checks", {}) if isinstance(runtime, dict) else {}
    color_delta = _float_metric(runtime_summary, "color_delta", 0.0)
    mask_coverage = _float_metric(runtime_summary, "mask_coverage", 0.0)
    vfx_nodes = int(runtime_summary.get("vfx_nodes", 0) or 0)
    local_ml_detections = int(runtime_summary.get("local_ml_detections", 0) or 0)
    audio_tracks = int(runtime_summary.get("audio_stress_tracks", 0) or 0)
    runtime_ok = (
        bool(runtime.get("ok"))
        and all(bool(value) for value in runtime_checks.values())
        and color_delta >= 1.0
        and mask_coverage > 0.0
        and vfx_nodes >= 10
        and local_ml_detections >= 1
        and audio_tracks >= 2000
    )
    pipeline_summary = _summary_counts(pipeline)
    pipeline_ok = (
        bool(pipeline.get("ok"))
        and int(pipeline_summary.get("color_score", 0) or 0) >= 90
        and int(pipeline_summary.get("audio_score", 0) or 0) >= 90
        and int(pipeline_summary.get("vfx_score", 0) or 0) >= 90
        and int(pipeline_summary.get("professional_deliver_jobs", 0) or 0) >= 3
    )
    if runtime_ok and pipeline_ok:
        score = 100
    elif runtime_ok:
        score = 86
    elif pipeline_ok:
        score = 74
    else:
        score = 55
    actions: list[str] = []
    if not runtime_ok:
        actions.append("Run tools/qa_professional_runtime_next.py and fix frame/graph/ML/audio runtime failures.")
    if not pipeline_ok:
        actions.append("Run tools/qa_professional_pipeline_next.py and inspect Color/Fairlight/Fusion/Deliver parity payloads.")
    return _area(
        "professional_runtime_parity",
        score=score,
        summary=(
            f"runtime={'ok' if runtime_ok else 'attention'}, "
            f"pipeline={'ok' if pipeline_ok else 'attention'}, "
            f"delta={color_delta:.2f}, mask={mask_coverage:.3f}, "
            f"vfx nodes={vfx_nodes}, local ML detections={local_ml_detections}, "
            f"audio stress={audio_tracks}."
        ),
        actions=actions,
        evidence={
            "runtime_report": str(runtime_path) if runtime_path.exists() else "",
            "pipeline_report": str(pipeline_path) if pipeline_path.exists() else "",
            "runtime_checks": dict(runtime_checks) if isinstance(runtime_checks, dict) else {},
            "runtime_summary": dict(runtime_summary),
            "pipeline_summary": dict(pipeline_summary),
        },
    )


def _timeline_polish(root: Path) -> dict[str, Any]:
    fuzzer = _load_json(root / "debugCapture" / "timeline_fuzzer_qa.json")
    align = _load_json(root / "debugCapture" / "timeline_alignment_qa.json")
    visual = _load_json(root / "debugCapture" / "timeline_visual_alignment_qa" / "timeline_visual_alignment_report.json")
    move_guard = _load_json(root / "debugCapture" / "window_move_guard_qa.json")
    fsum = _summary_counts(fuzzer)
    iterations = int(fsum.get("iterations", 0) or 0)
    failures = int(fsum.get("failures", 0) or 0)
    drift = _float_metric(_summary_counts(align), "max_abs_drift_px", 999.0) if align else 999.0
    visual_drift = _float_metric(_summary_counts(visual), "max_abs_drift_px", 999.0) if visual else 999.0
    move_guard_ok = bool(move_guard.get("ok"))
    move_summary = _summary_counts(move_guard)
    ok = (
        bool(fuzzer.get("ok"))
        and bool(align.get("ok"))
        and bool(visual.get("ok"))
        and move_guard_ok
        and failures == 0
        and iterations >= 400
        and drift <= 1.0
        and visual_drift <= 2.0
    )
    partial = bool(fuzzer.get("ok")) or bool(align.get("ok")) or bool(visual.get("ok")) or move_guard_ok
    actions: list[str] = []
    if iterations < 400 or failures:
        actions.append("Run tools/qa_timeline_fuzzer.py --iterations 400 and fix any edit invariant failures.")
    if not align or drift > 1.0:
        actions.append("Run tools/qa_timeline_alignment.py and keep ruler/clip/playhead drift within 1px.")
    if not visual or visual_drift > 2.0:
        actions.append("Run tools/qa_timeline_visual_alignment.py after timeline UI changes.")
    if not move_guard_ok:
        actions.append("Run tools/qa_window_move_guard.py after editor chrome/timer changes.")
    return _area(
        "timeline_polish",
        score=_score(ok, partial),
        summary=(
            f"fuzzer iterations={iterations}, failures={failures}, drift={drift:g}px, "
            f"visual drift={visual_drift:g}px, move guard={'ok' if move_guard_ok else 'attention'}."
        ),
        actions=actions,
        evidence={
            "iterations": iterations,
            "failures": failures,
            "drift_px": drift,
            "visual_drift_px": visual_drift,
            "window_move_guard_ok": move_guard_ok,
            "window_move_guard_summary": dict(move_summary),
        },
    )


def _preset_template_quality(root: Path) -> dict[str, Any]:
    preset_app = _load_json(root / "debugCapture" / "preset_application_corpus_auto.json")
    try:
        from app.preset_library import preset_ecosystem_report, preset_pack_marketplace_report, presets_by_kind

        ecosystem = preset_ecosystem_report()
        marketplace = preset_pack_marketplace_report()
        templates = presets_by_kind("template")
    except Exception:
        ecosystem = {}
        marketplace = {}
        templates = []
    projects = len(preset_app.get("projects", []) or [])
    ecosystem_score = int(ecosystem.get("score", 0) or 0)
    issue_packs = int(marketplace.get("issue_packs", 0) or 0)
    template_count = len(templates)
    ok = projects > 0 and ecosystem_score >= 90 and issue_packs == 0 and template_count >= 30
    partial = ecosystem_score >= 75 or template_count >= 15
    actions: list[str] = []
    if projects <= 0:
        actions.append("Run preset application corpus QA against real/fixture projects.")
    if ecosystem_score < 90 or issue_packs:
        actions.append("Open Preset Pack Manager and repair duplicate/missing/broken preset packs.")
    if template_count < 30:
        actions.append("Expand practical Screen Studio/CapCut template presets until at least 30 are available.")
    return _area(
        "preset_template_quality",
        score=_score(ok, partial),
        summary=f"preset projects={projects}, ecosystem score={ecosystem_score}, issue packs={issue_packs}, templates={template_count}.",
        actions=actions,
        evidence={
            "preset_application_projects": projects,
            "ecosystem_score": ecosystem_score,
            "issue_packs": issue_packs,
            "template_count": template_count,
        },
    )


def _crash_recovery_project_repair(root: Path) -> dict[str, Any]:
    repair_tool = (root / "tools" / "repair_project.py").exists()
    recovery_dialog = (root / "app" / "recovery_dialog.py").exists()
    crash_reporter = (root / "app" / "crash_reporter.py").exists()
    stress = _load_json(root / "debugCapture" / "long_project_stress_qa.json")
    stress_ok = bool(stress.get("ok")) if stress else False
    try:
        from tools.repair_project import _candidate_paths_from_roots, audit_recovery_candidates

        candidates = _candidate_paths_from_roots([root / "qa_corpus" / "projects"])
        recovery = audit_recovery_candidates(candidates) if candidates else {}
    except Exception:
        candidates = []
        recovery = {}
    candidate_count = len(candidates)
    recovery_ready = bool((recovery.get("product_summary") or {}).get("best_path")) if recovery else repair_tool and recovery_dialog
    score = 100 if repair_tool and recovery_dialog and crash_reporter and stress_ok and recovery_ready else 78 if repair_tool and recovery_dialog and crash_reporter else 45
    actions: list[str] = []
    if not stress_ok:
        actions.append("Run tools/qa_long_project_stress.py and verify recovery fixture health.")
    if candidate_count <= 0:
        actions.append("Keep autosave/recovery fixture projects in QA corpus for repair drills.")
    if not (repair_tool and recovery_dialog and crash_reporter):
        actions.append("Restore crash reporter, recovery dialog, and repair_project tooling.")
    return _area(
        "crash_recovery_project_repair",
        score=score,
        summary=f"tooling={'ok' if repair_tool and recovery_dialog and crash_reporter else 'missing'}, stress={'ok' if stress_ok else 'attention'}, recovery candidates={candidate_count}.",
        actions=actions,
        evidence={
            "repair_tool": repair_tool,
            "recovery_dialog": recovery_dialog,
            "crash_reporter": crash_reporter,
            "long_project_stress_ok": stress_ok,
            "recovery_candidates": candidate_count,
        },
    )


def _release_packaging(root: Path) -> dict[str, Any]:
    packaging_files = [
        root / "TigerCapture.spec",
        root / "mac" / "TigerCapture-mac.spec",
        root / "installer.iss",
        root / "installer.nsi",
        root / "build.ps1",
    ]
    existing = [path for path in packaging_files if path.exists()]
    startup = _load_json(root / "debugCapture" / "startup_flow_qa.json")
    gui = _load_json(root / "debugCapture" / "screenstudio_gui_flow" / "screenstudio_gui_flow_report.json")
    flicker = _load_json(root / "debugCapture" / "visible_windows_trace.json")
    startup_ok = bool(startup.get("ok")) if startup else bool(gui.get("ok"))
    flicker_rows = flicker.get("visible_console_like_rows", None)
    flicker_ok = flicker_rows in (None, 0)
    ok = len(existing) >= 5 and startup_ok and flicker_ok
    score = 100 if ok else 80 if len(existing) >= 5 else 55
    actions: list[str] = []
    if len(existing) < 5:
        actions.append("Restore Windows/mac packaging specs, installer scripts, and build.ps1.")
    if not startup_ok:
        actions.append("Run launcher/startup GUI-flow QA before packaging.")
    if not flicker_ok:
        actions.append("Run visible-window startup trace and remove any remaining transient top-level windows.")
    return _area(
        "release_packaging",
        score=score,
        summary=f"packaging files={len(existing)}/5, startup={'ok' if startup_ok else 'attention'}, flicker={'ok' if flicker_ok else 'attention'}.",
        actions=actions,
        evidence={
            "packaging_files": [str(path) for path in existing],
            "startup_ok": startup_ok,
            "visible_console_like_rows": flicker_rows,
        },
    )


def _vtuber_broadcast_readiness(root: Path) -> dict[str, Any]:
    sprint = _release_evidence_sprint_snapshot(root, kinds={"broadcast_platform_evidence"})
    automation = _release_evidence_automation_snapshot(root)
    try:
        from app.broadcast_release_readiness import build_broadcast_release_readiness_report

        report = build_broadcast_release_readiness_report(root)
    except Exception as exc:
        return _area(
            "vtuber_broadcast_readiness",
            score=45,
            summary=f"Broadcast readiness report failed: {exc}",
            actions=["Run tools/qa_broadcast_release_readiness.py --allow-not-ready and inspect the failure."],
            evidence={"report_error": str(exc)},
        )
    alpha_ready = bool(report.get("alpha_ready"))
    commercial_ready = bool(report.get("commercial_ready"))
    raw_score = int(report.get("score", 0) or 0)
    score = 100 if commercial_ready else (85 if alpha_ready else min(65, raw_score))
    actions = list(report.get("next_actions") or [])
    if not actions and not commercial_ready:
        actions.append("Attach redacted RTMP and Discord/video-call platform evidence.")
    summary = (
        f"broadcast score={raw_score}/100, alpha={'ready' if alpha_ready else 'blocked'}, "
        f"commercial={'ready' if commercial_ready else 'blocked'}."
    )
    return _area(
        "vtuber_broadcast_readiness",
        score=score,
        summary=summary,
        actions=actions,
        evidence={
            "broadcast_score": raw_score,
            "alpha_ready": alpha_ready,
            "commercial_ready": commercial_ready,
            "sale_ready": bool(report.get("sale_ready")),
            "sale_blockers": list(report.get("sale_blockers") or []),
            "report_path": str(root / "debugCapture" / "broadcast_release_readiness_qa.json"),
            "release_evidence_sprint": sprint,
            "release_evidence_automation": automation,
        },
    )


def build_final_product_readiness_report(root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    areas = [
        _practical_editing_flow(root_path),
        _real_project_corpus(root_path),
        _screenstudio_interaction_corpus(root_path),
        _preview_gpu_performance(root_path),
        _preview_scrub_claims(root_path),
        _ai_edit_claim_quality(root_path),
        _color_audio_accuracy(root_path),
        _professional_runtime_parity(root_path),
        _vtuber_broadcast_readiness(root_path),
        _timeline_polish(root_path),
        _preset_template_quality(root_path),
        _crash_recovery_project_repair(root_path),
        _release_packaging(root_path),
    ]
    attention = [row for row in areas if row["score"] < 90]
    blocked = [row for row in areas if row["score"] < 70]
    release_blocking = [row for row in areas if row.get("release_blocking")]
    screenstudio_claim_ready = all(
        bool(row.get("evidence", {}).get("replacement_claim_ready"))
        for row in areas
        if row.get("id") == "screenstudio_interaction_corpus"
    )
    preview_scrub_claim_ready = all(
        bool(row.get("evidence", {}).get("release_scrub_claim_ready"))
        for row in areas
        if row.get("id") == "preview_scrub_claims"
    )
    smart_ai_edit_claim_ready = all(
        bool(row.get("evidence", {}).get("smart_edit_claim_ready"))
        for row in areas
        if row.get("id") == "ai_edit_claim_quality"
    )
    broadcast_commercial_ready = all(
        bool(row.get("evidence", {}).get("commercial_ready"))
        for row in areas
        if row.get("id") == "vtuber_broadcast_readiness"
    )
    commercial_claims_ready = bool(
        screenstudio_claim_ready
        and preview_scrub_claim_ready
        and smart_ai_edit_claim_ready
        and broadcast_commercial_ready
    )
    score = int(round(sum(int(row["score"]) for row in areas) / max(1, len(areas))))
    release_ready = not release_blocking
    claim_blockers = [
        {
            "area": row["id"],
            "label": row["label"],
            "summary": row["summary"],
            "actions": row.get("actions", []),
        }
        for row in areas
        if row["id"] in {
            "screenstudio_interaction_corpus",
            "preview_scrub_claims",
            "ai_edit_claim_quality",
            "vtuber_broadcast_readiness",
        }
        and row.get("release_blocking")
    ]
    return {
        "ok": True,
        "release_ready": release_ready,
        "screenstudio_replacement_claim_ready": screenstudio_claim_ready,
        "preview_scrub_claim_ready": preview_scrub_claim_ready,
        "smart_ai_edit_claim_ready": smart_ai_edit_claim_ready,
        "broadcast_commercial_ready": broadcast_commercial_ready,
        "commercial_claims_ready": commercial_claims_ready,
        "score": score,
        "summary": {
            "areas": len(areas),
            "ready": len(areas) - len(attention),
            "attention": len(attention),
            "blocked": len(blocked),
            "release_blocking": len(release_blocking),
            "release_ready": release_ready,
            "screenstudio_replacement_claim_ready": screenstudio_claim_ready,
            "preview_scrub_claim_ready": preview_scrub_claim_ready,
            "smart_ai_edit_claim_ready": smart_ai_edit_claim_ready,
            "broadcast_commercial_ready": broadcast_commercial_ready,
            "commercial_claims_ready": commercial_claims_ready,
        },
        "areas": areas,
        "claim_blockers": claim_blockers,
        "next_actions": [action for row in release_blocking for action in row.get("actions", [])][:16],
    }

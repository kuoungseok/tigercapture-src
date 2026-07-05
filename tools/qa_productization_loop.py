"""Build a productization QA report across the editor's commercial polish areas.

This is intentionally a fast coordinator by default. It reads the latest
product reports and lightweight app state, then produces one JSON file that
answers whether the Screen Studio-style UI loop, presets, render queue, media
pool, Color/Audio, actor QA, recovery, and starter templates are ready enough
for a real editing pass.

Use from the repository root:

    .venv\\Scripts\\python.exe tools\\qa_productization_loop.py --out debugCapture\\productization_loop_qa.json

Pass ``--run-fast-qa`` to refresh the cheap deterministic reports first. Pass
``--run-ui-layout`` only for an explicit UI screenshot pass.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


AREAS: tuple[tuple[str, str, str], ...] = (
    ("ui_visual_qa_loop", "실사용 UI 비주얼 QA 루프", "tools/qa_ui_layout.py + visual regression reports"),
    ("creator_polish_coverage", "Creator polish coverage", "tools/qa_creator_polish_coverage.py"),
    ("commercial_expansion_package", "상용 확장 패키지", "tools/qa_commercial_expansion.py + app.commercial_expansion"),
    ("capcut_creator_workflow", "CapCut식 크리에이터 워크플로우", "tools/qa_capcut_creator_workflow.py + app.capcut_workflow"),
    ("local_ml_backend", "Local ML backend", "tools/qa_local_ml_backend.py + app.local_ml"),
    ("preset_preview_realism", "프리셋 미리보기 실제화", "Preview Apply + preset application corpus"),
    ("preset_pack_management", "템플릿/프리셋 팩 관리 제품화", "Preset Pack Manager + marketplace report"),
    ("qa_dashboard_productization", "QA Dashboard 제품화", "app.qa_dashboard + this consolidated report"),
    ("render_queue_ux", "Render Queue 최종 제품화", "RenderQueueStore diagnostics/history"),
    ("media_pool_long_project", "Media Pool 장기 프로젝트 관리", "media health/proxy/relink corpus state"),
    ("color_audio_accuracy", "Color/Audio 실제 샘플 corpus", "tools/qa_color_audio_accuracy.py"),
    ("professional_runtime_parity", "Professional runtime parity", "tools/qa_professional_runtime_next.py + tools/qa_professional_pipeline_next.py"),
    ("screenstudio_parity_gap", "Screen Studio parity gap", "tools/qa_screenstudio_parity_gap.py + app.screenstudio_parity"),
    ("actor_compatibility_ui", "Live2D/Spine 호환성 화면", "actor status/render reports + golden baselines"),
    ("actor_loading_ux", "Live2D/Spine 로딩 UX", "tools/qa_actor_loading_ux.py + editor progress/cancel/recovery"),
    ("actor_overnight_qa", "Live2D/Spine 장시간 격리 QA", "tools/qa_actor_overnight.py + isolated process probes"),
    ("crash_recovery_repair", "Crash Recovery / Project Repair 마법사", "tools/repair_project.py + Recovery dialog"),
    ("starter_templates", "새 프로젝트/템플릿 시작 화면", "NewProjectDialog starter templates + template presets"),
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _run(cmd: list[str], *, timeout: int = 180) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return {
        "cmd": cmd,
        "returncode": int(proc.returncode),
        "stdout_tail": proc.stdout[-1800:],
        "stderr_tail": proc.stderr[-1800:],
        "ok": proc.returncode == 0,
    }


def _latest_visual_report() -> Path | None:
    root = ROOT / "debugCapture"
    if not root.exists():
        return None
    reports = sorted(
        list(root.glob("**/visual_regression_report.json")) + list(root.glob("**/layout_report.json")),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    return reports[0] if reports else None


def _status(ok: bool, summary: str, *, score: int | None = None, actions: list[str] | None = None, artifacts: list[str] | None = None) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "score": int(score if score is not None else (100 if ok else 50)),
        "summary": summary,
        "actions": actions or [],
        "artifacts": artifacts or [],
    }


def _ui_visual_status() -> dict[str, Any]:
    report_path = _latest_visual_report()
    baseline_audit = _load_json(ROOT / "debugCapture" / "visual_baseline_audit.json")
    micro = _load_json(ROOT / "debugCapture" / "micro_interactions_qa.json")
    if report_path is None:
        return _status(
            False,
            "No UI layout or visual regression report found.",
            score=35,
            actions=["Run tools/qa_ui_layout.py or tools/qa_visual_regression.py after UI polish."],
        )
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if isinstance(payload, list):
        ok = all(bool(row.get("ok")) for row in payload if isinstance(row, dict))
        count = sum(1 for row in payload if isinstance(row, dict))
    else:
        report = payload if isinstance(payload, dict) else {}
        ok = bool(report.get("ok", True))
        count = len(report.get("captures", []) or report.get("failures", []) or report.get("issues", []) or [])
    baseline_ok = bool(baseline_audit.get("ok")) if baseline_audit else False
    micro_ok = bool(micro.get("ok")) if micro else False
    full_ok = ok and baseline_ok and micro_ok
    summary_bits = [
        f"Latest visual/layout report: {report_path.name} ({count} row(s))",
        f"baseline={'ok' if baseline_ok else 'missing/attention'}",
        f"micro={'ok' if micro_ok else 'missing/attention'}",
    ]
    actions: list[str] = []
    if not ok:
        actions.append("Open Visual QA Viewer and compare failing screenshots against baseline.")
    if not baseline_ok:
        actions.append("Run tools/qa_visual_regression.py and approve the visual baseline.")
    if not micro_ok:
        actions.append("Run tools/qa_micro_interactions.py after icon/toolbar changes.")
    return _status(
        full_ok,
        "; ".join(summary_bits) + ".",
        score=100 if full_ok else (80 if ok else 60),
        actions=actions,
        artifacts=[str(report_path)],
    )


def _commercial_expansion_status() -> dict[str, Any]:
    path = ROOT / "debugCapture" / "commercial_expansion_qa.json"
    report = _load_json(path)
    if not report:
        try:
            from app.commercial_expansion import build_commercial_expansion_report

            report = build_commercial_expansion_report(root=ROOT)
        except Exception as exc:
            return _status(
                False,
                f"Commercial expansion report failed to build: {exc}",
                score=45,
                actions=["Run tools/qa_commercial_expansion.py and inspect the failure."],
            )
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    passing = int(summary.get("passing", 0) or 0)
    areas = int(summary.get("areas", 0) or 0)
    attention = int(summary.get("attention", 0) or 0)
    ok = bool(report.get("ok")) and areas >= 10 and attention == 0
    return _status(
        ok,
        f"Commercial expansion score {report.get('score', 0)}/100; passing {passing}/{areas}, attention {attention}.",
        score=int(report.get("score", 0) or 0),
        actions=[] if ok else list(report.get("next_actions", []) or ["Run tools/qa_commercial_expansion.py."]),
        artifacts=[str(path)] if path.exists() else [],
    )


def _creator_polish_coverage_status() -> dict[str, Any]:
    path = ROOT / "debugCapture" / "creator_polish_coverage_qa.json"
    report = _load_json(path)
    if not report:
        try:
            from tools.qa_creator_polish_coverage import run_creator_polish_coverage_qa

            report = run_creator_polish_coverage_qa()
        except Exception as exc:
            return _status(
                False,
                f"Creator polish coverage report failed to build: {exc}",
                score=45,
                actions=["Run tools/qa_creator_polish_coverage.py and inspect the failure."],
            )
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    sections = int(summary.get("sections", 0) or 0)
    passing = int(summary.get("passing_sections", 0) or 0)
    ok = bool(report.get("ok")) and sections >= 4 and passing == sections
    return _status(
        ok,
        f"Creator polish coverage {passing}/{sections}; score {summary.get('score', 0)}/100.",
        score=int(summary.get("score", 0) or (100 if ok else 60)),
        actions=[] if ok else ["Run tools/qa_creator_polish_coverage.py and inspect preset/Screen Studio/CapCut/stability sections."],
        artifacts=[str(path)] if path.exists() else [],
    )


def _capcut_creator_status() -> dict[str, Any]:
    path = ROOT / "debugCapture" / "capcut_creator_workflow_qa.json"
    report = _load_json(path)
    if not report:
        try:
            from app.capcut_workflow import capcut_creator_workflow_report

            report = capcut_creator_workflow_report({"duration_s": 180, "has_audio": True, "dialogue": True})
        except Exception as exc:
            return _status(
                False,
                f"CapCut creator workflow failed to build: {exc}",
                score=45,
                actions=["Run tools/qa_capcut_creator_workflow.py and inspect the failure."],
            )
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    areas = int(summary.get("areas", 0) or 0)
    steps = int(summary.get("recommendation_steps", 0) or 0)
    applied_subtitles = int(summary.get("applied_subtitles", 0) or 0)
    applied_jobs = int(summary.get("applied_render_jobs", 0) or 0)
    materialized_jobs = int(summary.get("materialized_render_queue_jobs", 0) or 0)
    hooks = int(summary.get("hook_candidates", 0) or 0)
    beats = int(summary.get("caption_beats", 0) or 0)
    recipe_steps = int(summary.get("edit_recipe_steps", 0) or 0)
    publish_variants = int(summary.get("publish_variants", 0) or 0)
    review_panel_cards = int(summary.get("review_panel_cards", 0) or 0)
    publish_handoff_actions = int(summary.get("publish_handoff_actions", 0) or 0)
    review_panel_ready = bool(summary.get("review_panel_ready", False))
    publish_handoff_ready = bool(summary.get("publish_handoff_ready", False))
    publish_ready = bool(summary.get("publish_package_ready", False))
    apply_ok = bool((report.get("apply_simulation") or {}).get("ok"))
    ok = (
        bool(report.get("ok"))
        and areas >= 10
        and steps >= 5
        and apply_ok
        and applied_jobs >= 1
        and materialized_jobs >= 1
        and hooks >= 1
        and beats >= 1
        and recipe_steps >= 6
        and publish_variants >= 3
        and review_panel_ready
        and review_panel_cards >= 7
        and publish_handoff_ready
        and publish_handoff_actions >= 5
        and publish_ready
    )
    return _status(
        ok,
        (
            f"CapCut workflow score {report.get('score', 0)}/100; "
            f"{steps} recommendation step(s), {areas} area(s), "
            f"apply subtitles={applied_subtitles}, staged jobs={applied_jobs}, "
            f"queue jobs={materialized_jobs}, hooks={hooks}, caption beats={beats}, "
            f"recipe steps={recipe_steps}, variants={publish_variants}, "
            f"panel cards={review_panel_cards}, handoff actions={publish_handoff_actions}, "
            f"publish={'ready' if publish_ready else 'attention'}."
        ),
        score=int(float(report.get("score", 0) or 0)),
        actions=[] if ok else ["Run tools/qa_capcut_creator_workflow.py and inspect weak creator/apply areas."],
        artifacts=[str(path)] if path.exists() else [],
    )


def _local_ml_backend_status() -> dict[str, Any]:
    path = ROOT / "debugCapture" / "local_ml_backend_qa.json"
    report = _load_json(path)
    if not report:
        try:
            from tools.qa_local_ml_backend import build_local_ml_backend_report

            report = build_local_ml_backend_report()
        except Exception as exc:
            return _status(
                False,
                f"Local ML backend QA failed to build: {exc}",
                score=45,
                actions=["Run tools/qa_local_ml_backend.py and inspect local model/runtime status."],
            )
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    checks = report.get("checks", {}) if isinstance(report, dict) else {}
    detections = int(summary.get("detections", 0) or 0)
    cloud_off = summary.get("cloud_enabled") is False and bool(checks.get("cloud_disabled", False))
    bundle_ok = bool(summary.get("capcut_bundle_ok"))
    visual_ok = bool(checks.get("visual_analysis")) and detections >= 1
    ok = bool(report.get("ok")) and cloud_off and visual_ok and bundle_ok
    return _status(
        ok,
        (
            f"Local ML mode={summary.get('mode', 'local')}; "
            f"cloud={'off' if cloud_off else 'attention'}, "
            f"detections={detections}, "
            f"CapCut bundle={'ready' if bundle_ok else 'attention'}."
        ),
        score=int(report.get("score", 0) or (100 if ok else 60)),
        actions=[] if ok else ["Run tools/qa_local_ml_backend.py and check missing local runtimes/models."],
        artifacts=[str(path)] if path.exists() else [],
    )


def _preset_statuses() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from app.preset_library import (
        one_click_preset_plan,
        preset_ecosystem_report,
        preset_pack_marketplace_report,
        presets_by_kind,
        search_presets,
    )

    ecosystem = preset_ecosystem_report()
    marketplace = preset_pack_marketplace_report()
    templates = presets_by_kind("template")
    screenstudio_hits = (
        search_presets("screenstudio cursor", kind="template")
        + search_presets("product launch", kind="template")
        + search_presets("gaming highlight", kind="template")
    )
    plan = one_click_preset_plan({
        "video_count": 1,
        "audio_count": 1,
        "shortform": True,
        "vertical": True,
        "product": True,
        "gameplay": True,
        "tutorial": True,
    })
    preview_ok = bool(screenstudio_hits) and bool(plan) and plan[0].kind == "template"
    pack_ok = bool(ecosystem.get("ok")) and int(ecosystem.get("score", 0) or 0) >= 90
    packs = list(marketplace.get("packs", []) or [])
    return (
        _status(
            preview_ok,
            f"{len(templates)} template presets, {len(plan)} one-click plan step(s), {len(screenstudio_hits)} Screen Studio-style hit(s).",
            score=100 if preview_ok else 65,
            actions=[] if preview_ok else ["Expand template-specific Preview Apply scenes and one-click plans."],
        ),
        _status(
            pack_ok,
            f"Preset ecosystem score {ecosystem.get('score', 0)}/100; marketplace packs {len(packs)}.",
            score=int(ecosystem.get("score", 0) or 0),
            actions=[] if pack_ok else ["Open Preset Pack Manager and resolve invalid rows, duplicates, or missing template refs."],
        ),
        _status(
            len(templates) >= 30,
            f"Starter/template library contains {len(templates)} template presets.",
            score=100 if len(templates) >= 30 else 70,
            actions=[] if len(templates) >= 30 else ["Add more starter templates for screen recording, shorts, gameplay, and product demos."],
        ),
    )


def _qa_dashboard_status() -> dict[str, Any]:
    try:
        from app.qa_dashboard import build_qa_dashboard_rows

        rows = build_qa_dashboard_rows()
    except Exception as exc:
        return _status(False, f"QA Dashboard rows failed to build: {exc}", score=40)
    available = sum(1 for row in rows if row.get("exists"))
    passing = sum(1 for row in rows if row.get("exists") and row.get("ok"))
    ok = available >= max(3, len(rows) // 2) and passing >= max(1, available - 1)
    return _status(
        ok,
        f"QA Dashboard reports available {available}/{len(rows)}, passing {passing}/{available or 1}.",
        score=100 if ok else 65,
        actions=[] if ok else ["Run QA Dashboard safe reports until recent report coverage is at least half of tracked areas."],
    )


def _render_queue_status() -> dict[str, Any]:
    from app.render_queue import RenderQueueStore, render_queue_product_diagnostics

    store = RenderQueueStore()
    jobs = list(store.jobs)
    failed = [job for job in jobs if job.status == "error"]
    diagnostics_ready = all(bool(render_queue_product_diagnostics(job).get("actions")) for job in failed)
    ok = not failed or diagnostics_ready
    return _status(
        ok,
        f"Render queue jobs {len(jobs)}, failed {len(failed)}, diagnostic actions {'ready' if diagnostics_ready or not failed else 'missing'}.",
        score=100 if ok else 70,
        actions=[] if ok else ["Open Render Queue > Resolve for failed jobs and save/copy diagnostics."],
    )


def _media_pool_status() -> dict[str, Any]:
    manifest = _load_json(ROOT / "qa_corpus" / "product_qa_corpus_manifest.json")
    stress = _load_json(ROOT / "debugCapture" / "long_project_stress_qa.json")
    groups = list(manifest.get("sample_groups", []) or [])
    project_files = sorted((ROOT / "qa_corpus" / "projects").glob("*.tgp")) if (ROOT / "qa_corpus" / "projects").exists() else []
    stress_summary = stress.get("summary", {}) if isinstance(stress, dict) else {}
    stress_ok = bool(stress.get("ok")) if stress else False
    ok = len(groups) >= 6 and len(project_files) >= 6 and stress_ok
    return _status(
        ok,
        (
            f"Product corpus groups {len(groups)}, project fixtures {len(project_files)}, "
            f"long clips V/A {stress_summary.get('video_clips', 0)}/{stress_summary.get('audio_clips', 0)}."
        ),
        score=100 if ok else 60,
        actions=[] if ok else ["Run tools/build_qa_corpus.py and tools/qa_long_project_stress.py."],
        artifacts=[str(ROOT / "qa_corpus" / "product_qa_corpus_manifest.json")] if groups else [],
    )


def _color_audio_status() -> dict[str, Any]:
    path = ROOT / "debugCapture" / "color_audio_accuracy_qa.json"
    report = _load_json(path)
    summary = report.get("summary", {}) if report else {}
    failures = int(summary.get("failures", 0) or 0)
    checks = int(summary.get("checks", 0) or 0)
    samples = summary.get("sample_sources", {}) if isinstance(summary, dict) else {}
    sample_count = len(samples.get("video", []) or []) + len(samples.get("audio", []) or []) if isinstance(samples, dict) else 0
    ok = bool(report.get("ok")) and checks >= 16 and sample_count >= 2
    return _status(
        ok,
        f"Color/Audio checks {checks}, failures {failures}, real samples {sample_count}.",
        score=100 if ok else (80 if bool(report.get("ok")) and checks >= 16 else 60),
        actions=[] if ok else ["Run tools/build_qa_corpus.py, then tools/qa_color_audio_accuracy.py so qa_corpus/color_audio_samples is included."],
        artifacts=[str(path)] if path.exists() else [],
    )


def _professional_runtime_status() -> dict[str, Any]:
    runtime_path = ROOT / "debugCapture" / "professional_runtime_next_qa.json"
    pipeline_path = ROOT / "debugCapture" / "professional_pipeline_next_qa.json"
    runtime = _load_json(runtime_path)
    pipeline = _load_json(pipeline_path)
    if not runtime:
        try:
            from app.professional_runtime import professional_runtime_verification_report

            runtime = professional_runtime_verification_report(out_dir=ROOT / "debugCapture")
        except Exception as exc:
            return _status(
                False,
                f"Professional runtime QA failed to build: {exc}",
                score=45,
                actions=["Run tools/qa_professional_runtime_next.py and inspect the execution failure."],
            )
    runtime_summary = runtime.get("summary", {}) if isinstance(runtime, dict) else {}
    runtime_checks = runtime.get("checks", {}) if isinstance(runtime, dict) else {}
    color_delta = float(runtime_summary.get("color_delta", 0.0) or 0.0)
    mask_coverage = float(runtime_summary.get("mask_coverage", 0.0) or 0.0)
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
    pipeline_summary = pipeline.get("summary", {}) if isinstance(pipeline, dict) else {}
    pipeline_ok = (
        bool(pipeline.get("ok"))
        and int(pipeline_summary.get("color_score", 0) or 0) >= 90
        and int(pipeline_summary.get("audio_score", 0) or 0) >= 90
        and int(pipeline_summary.get("vfx_score", 0) or 0) >= 90
        and int(pipeline_summary.get("professional_deliver_jobs", 0) or 0) >= 3
    )
    ok = runtime_ok and pipeline_ok
    score = 100 if ok else (86 if runtime_ok else 74 if pipeline_ok else 55)
    actions: list[str] = []
    if not runtime_ok:
        actions.append("Run tools/qa_professional_runtime_next.py and fix frame/graph/ML/audio runtime failures.")
    if not pipeline_ok:
        actions.append("Run tools/qa_professional_pipeline_next.py and inspect Color/Fairlight/Fusion/Deliver parity payloads.")
    return _status(
        ok,
        (
            f"Runtime {'ready' if runtime_ok else 'attention'}; "
            f"pipeline {'ready' if pipeline_ok else 'attention'}; "
            f"delta {color_delta:.2f}, mask {mask_coverage:.3f}, "
            f"vfx {vfx_nodes}, ml {local_ml_detections}, audio tracks {audio_tracks}."
        ),
        score=score,
        actions=actions,
        artifacts=[str(path) for path in (runtime_path, pipeline_path) if path.exists()],
    )


def _screenstudio_parity_gap_status() -> dict[str, Any]:
    path = ROOT / "debugCapture" / "screenstudio_parity_gap_qa.json"
    report = _load_json(path)
    if not report:
        try:
            from app.screenstudio_parity import screenstudio_parity_gap_report

            report = screenstudio_parity_gap_report()
        except Exception as exc:
            return _status(
                False,
                f"Screen Studio parity gap report failed to build: {exc}",
                score=45,
                actions=["Run tools/qa_screenstudio_parity_gap.py and inspect the failure."],
            )
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    areas = int(summary.get("areas", 0) or 0)
    passing = int(summary.get("passing", 0) or 0)
    real = int(summary.get("real_recordings", 0) or 0)
    target = int(summary.get("real_recording_target_min", 20) or 20)
    ok = bool(report.get("implementation_ok", report.get("ok"))) and areas >= 4 and passing >= 4
    return _status(
        ok,
        f"Screen Studio parity contracts {passing}/{areas}; real recording corpus {real}/{target}.",
        score=int(report.get("score", 0) or (100 if ok else 60)),
        actions=list(report.get("next_actions", []) or ([] if ok else ["Run tools/qa_screenstudio_parity_gap.py."])),
        artifacts=[str(path)] if path.exists() else [],
    )


def _actor_status() -> dict[str, Any]:
    status = _load_json(ROOT / "debugCapture" / "actor_corpus_status.json")
    render = _load_json(ROOT / "debugCapture" / "actor_render_qa.json")
    mass = _load_json(ROOT / "debugCapture" / "actor_mass_compat_qa.json")
    golden = list((ROOT / "qa_corpus" / "actor_golden").glob("*.png")) if (ROOT / "qa_corpus" / "actor_golden").exists() else []
    status_ok = bool(status.get("ok", True)) if status else bool(golden)
    render_ok = bool(render.get("ok", True)) if render else bool(golden)
    mass_ok = bool(mass.get("ok")) if mass else False
    mass_summary = mass.get("summary", {}) if isinstance(mass, dict) else {}
    ok = status_ok and render_ok and len(golden) >= 20 and mass_ok
    return _status(
        ok,
        (
            f"Actor golden baselines {len(golden)}, status report {'yes' if status else 'no'}, "
            f"render report {'yes' if render else 'no'}, mass coverage "
            f"{mass_summary.get('total', 0)} models/{mass_summary.get('stress', 0)} stress."
        ),
        score=100 if ok else 70,
        actions=[] if ok else ["Run actor corpus status/render QA and tools/qa_actor_mass_compat.py."],
    )


def _actor_loading_ux_status() -> dict[str, Any]:
    path = ROOT / "debugCapture" / "actor_loading_ux_qa.json"
    report = _load_json(path)
    if not report:
        try:
            from tools.qa_actor_loading_ux import run_actor_loading_ux_qa

            report = run_actor_loading_ux_qa()
        except Exception as exc:
            return _status(
                False,
                f"Actor loading UX QA failed to run: {exc}",
                score=45,
                actions=["Run tools/qa_actor_loading_ux.py and inspect the widget contract failure."],
            )
    issues = list(report.get("issues", []) or [])
    ok = bool(report.get("ok")) and not issues
    return _status(
        ok,
        f"Actor loading UX issues {len(issues)}; Live2D/Spine progress/cancel/recovery contract {'ok' if ok else 'attention'}.",
        score=100 if ok else 65,
        actions=[] if ok else ["Run tools/qa_actor_loading_ux.py and fix missing progress/cancel/recovery wiring."],
        artifacts=[str(path)] if path.exists() else [],
    )


def _actor_overnight_status() -> dict[str, Any]:
    path = ROOT / "debugCapture" / "actor_overnight_qa.json"
    report = _load_json(path)
    if not report:
        try:
            from tools.qa_actor_overnight import run_actor_overnight_qa

            report = run_actor_overnight_qa(render=False, limit=24)
        except Exception as exc:
            return _status(
                False,
                f"Actor overnight QA failed to plan: {exc}",
                score=45,
                actions=["Run tools/qa_actor_overnight.py and inspect manifest/status coverage."],
            )
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    checks = report.get("checks", {}) if isinstance(report, dict) else {}
    ok = bool(report.get("ok")) and int(summary.get("planned_candidates", 0) or 0) > 0
    return _status(
        ok,
        (
            f"Actor overnight plan {summary.get('planned_candidates', 0)} candidate(s), "
            f"rendered {summary.get('rendered', 0)}, failures {summary.get('failures', 0)}."
        ),
        score=100 if ok else 65,
        actions=[] if ok else ["Refresh actor corpus status and run tools/qa_actor_overnight.py."],
        artifacts=[str(path)] if path.exists() else [],
    )


def _recovery_status() -> dict[str, Any]:
    try:
        from tools.repair_project import _candidate_paths_from_roots, audit_recovery_candidates

        paths = _candidate_paths_from_roots([ROOT / "qa_corpus" / "projects"])
        if not paths:
            tooling_ready = (ROOT / "tools" / "repair_project.py").exists() and (ROOT / "app" / "recovery_dialog.py").exists()
            return _status(
                tooling_ready,
                "Recovery tooling is installed; no autosave/recovery candidate is currently present in the QA corpus.",
                score=90 if tooling_ready else 45,
                actions=["Create or keep real autosave snapshots in QA corpus for end-to-end recovery drills."] if tooling_ready else ["Restore repair_project.py and Recovery dialog."],
            )
        report = audit_recovery_candidates(paths)
        product = report.get("product_summary", {}) or {}
        count = len(product.get("candidates", []) or [])
        ok = count > 0 and product.get("best_path") is not None
        return _status(
            ok,
            f"Recovery candidates {count}, best status {dict(product.get('best_health', {}) or {}).get('level', '-')}.",
            score=100 if ok else 60,
            actions=[] if ok else ["Keep autosave/recovery snapshots around real project fixtures and run repair_project --list-recovery."],
        )
    except Exception as exc:
        return _status(False, f"Recovery audit failed: {exc}", score=45)


def build_productization_report() -> dict[str, Any]:
    preset_preview, pack_management, starter_templates = _preset_statuses()
    areas = {
        "ui_visual_qa_loop": _ui_visual_status(),
        "creator_polish_coverage": _creator_polish_coverage_status(),
        "commercial_expansion_package": _commercial_expansion_status(),
        "capcut_creator_workflow": _capcut_creator_status(),
        "local_ml_backend": _local_ml_backend_status(),
        "preset_preview_realism": preset_preview,
        "preset_pack_management": pack_management,
        "qa_dashboard_productization": _qa_dashboard_status(),
        "render_queue_ux": _render_queue_status(),
        "media_pool_long_project": _media_pool_status(),
        "color_audio_accuracy": _color_audio_status(),
        "professional_runtime_parity": _professional_runtime_status(),
        "screenstudio_parity_gap": _screenstudio_parity_gap_status(),
        "actor_compatibility_ui": _actor_status(),
        "actor_loading_ux": _actor_loading_ux_status(),
        "actor_overnight_qa": _actor_overnight_status(),
        "crash_recovery_repair": _recovery_status(),
        "starter_templates": starter_templates,
    }
    ordered = []
    for area_id, label, evidence in AREAS:
        row = dict(areas.get(area_id) or _status(False, "Area missing from report."))
        row.update({"id": area_id, "label": label, "evidence": evidence})
        ordered.append(row)
    score = int(round(sum(int(row.get("score", 0) or 0) for row in ordered) / max(1, len(ordered))))
    failures = [row for row in ordered if not row.get("ok")]
    return {
        "ok": not failures,
        "score": score,
        "summary": {
            "areas": len(ordered),
            "passing": len(ordered) - len(failures),
            "attention": len(failures),
        },
        "areas": ordered,
        "next_actions": [action for row in failures for action in row.get("actions", [])][:12],
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build a consolidated productization QA report.")
    parser.add_argument("--out", default="debugCapture/productization_loop_qa.json")
    parser.add_argument("--run-fast-qa", action="store_true", help="Refresh deterministic fast QA reports first.")
    parser.add_argument("--run-ui-layout", action="store_true", help="Run offscreen UI screenshot QA before building the report.")
    args = parser.parse_args()

    run_results: list[dict[str, Any]] = []
    python = sys.executable or "python"
    if args.run_fast_qa:
        run_results.append(_run([python, "tools/build_qa_corpus.py"]))
        run_results.append(_run([python, "tools/qa_creator_polish_coverage.py", "--out", "debugCapture/creator_polish_coverage_qa.json"]))
        run_results.append(_run([python, "tools/qa_commercial_expansion.py", "--out", "debugCapture/commercial_expansion_qa.json"]))
        run_results.append(_run([python, "tools/qa_capcut_creator_workflow.py", "--out", "debugCapture/capcut_creator_workflow_qa.json"]))
        run_results.append(_run([python, "tools/qa_local_ml_backend.py", "--out", "debugCapture/local_ml_backend_qa.json"]))
        run_results.append(_run([python, "tools/qa_color_audio_accuracy.py", "--out", "debugCapture/color_audio_accuracy_qa.json"]))
        run_results.append(_run([python, "tools/qa_professional_pipeline_next.py", "--out", "debugCapture/professional_pipeline_next_qa.json"]))
        run_results.append(_run([python, "tools/qa_professional_runtime_next.py", "--out", "debugCapture/professional_runtime_next_qa.json"]))
        run_results.append(_run([python, "tools/qa_screenstudio_parity_gap.py", "--out", "debugCapture/screenstudio_parity_gap_qa.json"]))
        run_results.append(_run([python, "tools/qa_long_project_stress.py", "--out", "debugCapture/long_project_stress_qa.json"]))
        run_results.append(_run([python, "tools/qa_micro_interactions.py", "--out", "debugCapture/micro_interactions_qa.json"]))
        run_results.append(_run([python, "tools/qa_actor_loading_ux.py", "--out", "debugCapture/actor_loading_ux_qa.json"]))
        run_results.append(_run([python, "tools/qa_actor_overnight.py", "--out", "debugCapture/actor_overnight_qa.json", "--limit", "24"]))
        run_results.append(_run([python, "tools/qa_actor_mass_compat.py", "--out", "debugCapture/actor_mass_compat_qa.json"]))
        run_results.append(_run([python, "tools/qa_visual_regression.py", "--out", "debugCapture/visual_regression"]))
        run_results.append(_run([python, "tools/qa_visual_baseline_audit.py", "--out", "debugCapture/visual_baseline_audit.json"]))
        run_results.append(_run([python, "tools/qa_timeline_fuzzer.py", "--iterations", "400", "--seed", "42", "--out", "debugCapture/timeline_fuzzer_qa.json"]))
        run_results.append(_run([python, "tools/qa_timeline_alignment.py", "--out", "debugCapture/timeline_alignment_qa.json"]))
        run_results.append(_run([python, "tools/qa_timeline_visual_alignment.py", "--out", "debugCapture/timeline_visual_alignment_qa"]))
        run_results.append(_run([python, "tools/qa_timeline_drag_feedback.py", "--out", "debugCapture/timeline_drag_feedback_qa"]))
        run_results.append(_run([python, "tools/qa_timeline_edit_gestures.py", "--out", "debugCapture/timeline_edit_gestures_qa"]))
        run_results.append(_run([python, "tools/qa_timeline_hover_affordance.py", "--out", "debugCapture/timeline_hover_affordance_qa"]))
        run_results.append(_run([python, "tools/qa_timeline_preset_visibility.py", "--out", "debugCapture/timeline_preset_visibility_qa"]))
        run_results.append(_run([python, "tools/qa_actor_lane_workflow.py", "--include-samples", "--out", "debugCapture/actor_lane_workflow_qa.json"]))
        run_results.append(_run([python, "tools/qa_node_graph_fuzzer.py", "--iterations", "400", "--seed", "42", "--out", "debugCapture/node_graph_fuzzer_qa.json"]))
        run_results.append(_run([python, "tools/qa_node_graph_ui_fuzzer.py", "--iterations", "240", "--seed", "42", "--out", "debugCapture/node_graph_ui_fuzzer_qa.json"]))
        run_results.append(_run([python, "tools/qa_preset_application_corpus.py", "--output", "debugCapture/preset_application_corpus_auto.json"]))
    if args.run_ui_layout:
        run_results.append(_run([python, "tools/qa_ui_layout.py", "--out", "debugCapture/ui_qa"], timeout=240))

    report = build_productization_report()
    if run_results:
        report["run_results"] = run_results
        report["ok"] = bool(report.get("ok")) and all(row.get("ok") for row in run_results)
    out_path = ROOT / args.out
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

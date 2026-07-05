"""Conservative NLE readiness diagnostics.

This module is intentionally claim-oriented: it records which professional NLE
surfaces have real implementation evidence and which ones must still be sold as
partial workflow foundations.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


NLE_READINESS_SCHEMA = "tigerstudio.nle_readiness.v1"


def build_nle_readiness_report(
    snapshot: Mapping[str, Any] | None = None,
    *,
    action_count: int = 0,
) -> dict[str, Any]:
    """Return a product-positioning-safe professional NLE readiness report."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), Mapping) else {}
    video_tracks = list(snapshot.get("video_tracks") or [])
    audio_tracks = list(snapshot.get("audio_tracks") or [])
    media_pool = list(snapshot.get("media_pool") or [])
    project_duration_ms = _int(snapshot.get("duration_ms"), 0)
    evidence = snapshot.get("nle_evidence") if isinstance(snapshot.get("nle_evidence"), Mapping) else {}
    evidence_rows = evidence.get("rows") if isinstance(evidence.get("rows"), Mapping) else {}
    evidence_level = str(evidence.get("evidence_level") or "")
    real_world_corpus = bool(evidence.get("real_world_corpus", False))

    def _evidence_row(row_id: str) -> Mapping[str, Any]:
        row = evidence_rows.get(row_id) if isinstance(evidence_rows, Mapping) else None
        return row if isinstance(row, Mapping) else {}

    def _evidence_ok(row_id: str) -> bool:
        return bool(_evidence_row(row_id).get("ok"))

    def _evidence_text(row_id: str) -> str:
        row = _evidence_row(row_id)
        if not row:
            return "no evidence report attached"
        level = str(row.get("evidence_level") or evidence_level or "project_snapshot")
        return f"evidence={level}, ok={bool(row.get('ok'))}"

    has_timeline = bool(video_tracks or audio_tracks)
    has_media_pool = bool(media_pool)
    has_project = bool(has_timeline or has_media_pool)
    video_clip_count = _int(summary.get("video_clip_count"), 0)
    audio_clip_count = _int(summary.get("audio_clip_count"), 0)
    long_project_row = _evidence_row("long_large_project_validation")
    long_project_stress_ok = bool(long_project_row.get("long_project_stress_ok"))
    real_project_corpus_ready = bool(long_project_row.get("real_project_corpus_ready") or real_world_corpus)
    multicam_row = _evidence_row("multicam")
    multicam_workbench_ready = bool(multicam_row.get("sync_plan_ready") and multicam_row.get("switcher_workbench_ready"))
    multicam_angle_bins_ready = bool(multicam_row.get("angle_bins_ready"))
    project_bin_row = _evidence_row("conform_relink_project_bin")
    project_bin_batch_ready = bool(project_bin_row.get("batch_plan_ready"))
    project_bin_conform_ready = bool(project_bin_row.get("conform_report_ready"))
    source_record_row = _evidence_row("source_record_monitor_3_point")
    source_decision_preview_ready = bool(source_record_row.get("edit_decision_preview_ready"))
    source_patch_matrix_ready = bool(source_record_row.get("patch_matrix_ready"))
    undo_row = _evidence_row("undo_edge_case_qa")
    timeline_fuzzer_ready = bool(undo_row.get("timeline_fuzzer_ready"))
    undo_health_ready = bool(undo_row.get("undo_health_ready"))
    proxy_row = _evidence_row("proxy_media_management")
    proxy_plan_ready = bool(proxy_row.get("proxy_plan_ready"))
    proxy_health_ready = bool(proxy_row.get("proxy_health_ready"))

    rows = [
        {
            "id": "core_nle_actions",
            "label": "Core NLE edit action surface",
            "status": "ready" if action_count >= 70 else "partial",
            "score": 86 if action_count >= 70 else 72,
            "evidence": [
                "registered Python actions cover split, trim, ripple/delete, lift/extract, track targets, gaps, clipboard insert/overwrite, and 3-point edit primitives",
                f"registered_action_count={max(0, int(action_count or 0))}",
            ],
            "remaining": ["Continue undo/fuzzer coverage whenever timeline behavior changes."],
        },
        {
            "id": "source_record_monitor_3_point",
            "label": "Source/Record monitor and 3-point editing",
            "status": "partial_verified" if _evidence_ok("source_record_monitor_3_point") else "partial",
            "score": 84 if source_decision_preview_ready and source_patch_matrix_ready and _evidence_ok("source_record_monitor_3_point") else (81 if source_decision_preview_ready and _evidence_ok("source_record_monitor_3_point") else (78 if _evidence_ok("source_record_monitor_3_point") else 62)),
            "evidence": [
                "source_record.workbench, source_record.edit_decision_preview, and source_record.patch_matrix view models plus source_monitor and record_monitor actions exist",
                "timeline.three_point_insert and timeline.three_point_overwrite exist",
                f"edit_decision_preview_ready={source_decision_preview_ready}",
                f"patch_matrix_ready={source_patch_matrix_ready}",
                _evidence_text("source_record_monitor_3_point"),
            ],
            "remaining": [
                "Dedicated Source monitor / Record monitor visual UI still needs polish.",
                "J/K/L transport feel, mark-in/out hotkeys, and source patching feedback need real-user review.",
            ],
        },
        {
            "id": "multicam",
            "label": "Multicam workflow",
            "status": "partial_verified" if _evidence_ok("multicam") else "missing",
            "score": 80 if multicam_workbench_ready and multicam_angle_bins_ready and _evidence_ok("multicam") else (76 if multicam_workbench_ready and _evidence_ok("multicam") else (72 if _evidence_ok("multicam") else 18)),
            "evidence": [
                "Multicam group detection, angle bins, sync plan, active-angle switch plan, switcher workbench, and export handoff actions exist.",
                "Full live multicam switcher UI is still not a Premiere/Resolve equivalent.",
                f"angle_bins_ready={multicam_angle_bins_ready}",
                f"angle_gap_count={_int(multicam_row.get('angle_gap_count'), 0)}",
                f"sync_plan_ready={bool(multicam_row.get('sync_plan_ready'))}",
                f"switcher_workbench_ready={bool(multicam_row.get('switcher_workbench_ready'))}",
                _evidence_text("multicam"),
            ],
            "remaining": ["Add waveform-derived sync, live switching UI polish, and real footage export parity QA."],
        },
        {
            "id": "proxy_media_management",
            "label": "Proxy/media management",
            "status": "partial_verified" if _evidence_ok("proxy_media_management") else ("partial" if has_media_pool else "needs_project"),
            "score": 82 if proxy_plan_ready and proxy_health_ready and _evidence_ok("proxy_media_management") else (78 if proxy_plan_ready and _evidence_ok("proxy_media_management") else (72 if _evidence_ok("proxy_media_management") else (55 if has_media_pool else 42))),
            "evidence": [
                "Media pool/proxy/relink foundations plus project_bin.proxy_plan and project_bin.proxy_health exist",
                f"media_pool_count={len(media_pool)}",
                f"proxy_plan_ready={proxy_plan_ready}",
                f"proxy_health_ready={proxy_health_ready}",
                _evidence_text("proxy_media_management"),
            ],
            "remaining": [
                "Background regenerate apply, proxy conflict handling, and stale proxy warning polish need more product depth.",
            ],
        },
        {
            "id": "conform_relink_project_bin",
            "label": "Conform, relink, and project bin workflow",
            "status": "partial_verified" if _evidence_ok("conform_relink_project_bin") else ("partial" if has_project else "needs_project"),
            "score": 80 if project_bin_batch_ready and project_bin_conform_ready and _evidence_ok("conform_relink_project_bin") else (77 if project_bin_batch_ready and _evidence_ok("conform_relink_project_bin") else (74 if _evidence_ok("conform_relink_project_bin") else (48 if has_project else 36))),
            "evidence": [
                "project_bin.workbench, project_bin.batch_plan, and project_bin.conform_report expose bin, proxy, offline-media, relink, and conform readiness state",
                f"video_clip_count={video_clip_count}",
                f"audio_clip_count={audio_clip_count}",
                f"batch_plan_ready={project_bin_batch_ready}",
                f"conform_report_ready={project_bin_conform_ready}",
                _evidence_text("conform_relink_project_bin"),
            ],
            "remaining": [
                "Premiere/Resolve-style bin panels, metadata editing, conform dialogs, offline-media browser, and reviewed batch apply need dedicated visual UI.",
            ],
        },
        {
            "id": "undo_edge_case_qa",
            "label": "Undo and edge-case QA",
            "status": "partial_verified" if _evidence_ok("undo_edge_case_qa") else "partial",
            "score": 82 if timeline_fuzzer_ready and undo_health_ready and _evidence_ok("undo_edge_case_qa") else (78 if timeline_fuzzer_ready and _evidence_ok("undo_edge_case_qa") else (72 if _evidence_ok("undo_edge_case_qa") else 58)),
            "evidence": [
                "Timeline fuzzer, undo health matrix, undo stack exercise, and action tests exist",
                "Destructive action gates require explicit confirmation",
                f"timeline_fuzzer_ready={timeline_fuzzer_ready}",
                f"undo_health_ready={undo_health_ready}",
                _evidence_text("undo_edge_case_qa"),
            ],
            "remaining": [
                "Run longer real-project randomized edit sessions and assert undo/redo state after every mutation.",
            ],
        },
        {
            "id": "long_large_project_validation",
            "label": "Long and large project validation",
            "status": "partial_verified" if _evidence_ok("long_large_project_validation") else ("partial" if project_duration_ms >= 60_000 else "needs_corpus"),
            "score": 84 if real_project_corpus_ready else (78 if long_project_stress_ok else (72 if _evidence_ok("long_large_project_validation") else (44 if project_duration_ms >= 60_000 else 30))),
            "evidence": [
                f"current_snapshot_duration_ms={project_duration_ms}",
                f"long_project_stress_ok={long_project_stress_ok}",
                f"real_project_corpus_ready={real_project_corpus_ready}",
                _evidence_text("long_large_project_validation"),
            ],
            "remaining": [
                "Run 30-120 minute real user projects, not only generated QA fixtures, through scrub, export, reopen, relink, and recovery QA.",
            ],
        },
    ]

    score = int(round(sum(_int(row.get("score"), 0) for row in rows) / max(1, len(rows))))
    blockers = [
        row["id"]
        for row in rows
        if str(row.get("status")) in {"missing", "needs_project", "needs_corpus"} or _int(row.get("score"), 0) < 50
    ]
    claim_blockers: list[str] = []
    if not real_world_corpus:
        claim_blockers.append("real_world_long_project_corpus")
    if _int(next((row.get("score") for row in rows if row.get("id") == "multicam"), 0), 0) < 70:
        claim_blockers.append("multicam_full_ui_export_parity")
    return {
        "schema": NLE_READINESS_SCHEMA,
        "score": score,
        "professional_nle_claim_ok": False,
        "safe_positioning": "core NLE workflow/action surface; not a Premiere/Resolve-grade professional NLE yet",
        "evidence_level": evidence_level or "project_snapshot",
        "real_world_corpus": real_world_corpus,
        "rows": rows,
        "blockers": blockers + [item for item in claim_blockers if item not in blockers],
        "next_actions": [
            "Polish the dedicated Source/Record monitor UI on top of the registered 3-point actions.",
            "Add real user long-project corpus runs before any full professional NLE claim.",
            "Deepen conform/relink project-bin UI and real footage multicam switching.",
            "Keep exposing this report in health/release QA so marketing copy cannot outpace implementation evidence.",
        ],
    }


def format_nle_readiness_summary(report: Mapping[str, Any]) -> str:
    score = _int(report.get("score"), 0)
    claim = bool(report.get("professional_nle_claim_ok"))
    blockers = ", ".join(str(row) for row in list(report.get("blockers") or [])[:5])
    return (
        f"NLE readiness {score}/100. "
        f"Professional NLE claim: {'allowed' if claim else 'not allowed'}. "
        f"Blockers: {blockers or 'none'}."
    )

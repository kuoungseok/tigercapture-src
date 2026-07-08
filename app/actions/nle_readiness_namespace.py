"""NLE readiness and real-project corpus action registration."""
from __future__ import annotations

from typing import Any

from app.actions.result import ok_result
from app.actions.schema import ActionSpec, schema_object


def register_nle_readiness_actions(registry: Any) -> None:
    """Register conservative NLE claim gates and evidence actions."""

    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "timeline.professional_nle_readiness",
            "Return conservative professional NLE readiness diagnostics and claim blockers.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "timeline.professional_nle_readiness",
            adapter.professional_nle_readiness(
                action_count=len(registry._handlers),
                action_ids=tuple(registry._handlers.keys()),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.nle_target_gap",
            "Return a target-score gap board that explains which NLE rows and real-corpus blockers prevent a requested score.",
            "timeline",
            params_schema=schema_object({"target_score": {"type": "integer"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.nle_target_gap",
            adapter.nle_target_gap(
                target_score=int(params.get("target_score") or 95),
                action_count=len(registry._handlers),
                action_ids=tuple(registry._handlers.keys()),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.nle_evidence",
            "Return evidence used by NLE readiness scoring without mutating the project.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "timeline.nle_evidence",
            adapter.nle_evidence(action_ids=tuple(registry._handlers.keys())),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.status",
            "Return real long-project corpus registration and readiness status.",
            "nle",
            params_schema=schema_object({"manifest_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.status",
            adapter.nle_real_corpus_status(manifest_path=str(params.get("manifest_path") or "")),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.discover",
            "Discover project-like files that can be registered as real NLE long-project corpus evidence.",
            "nle",
            params_schema=schema_object(
                {
                    "search_roots": {"type": "array"},
                    "manifest_path": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "max_depth": {"type": "integer"},
                    "allow_generated": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.discover",
            adapter.nle_real_corpus_discover(
                search_roots=[
                    str(row)
                    for row in list(params.get("search_roots") or [])
                    if str(row or "").strip()
                ],
                manifest_path=str(params.get("manifest_path") or ""),
                max_results=int(params.get("max_results") or 40),
                max_depth=int(params.get("max_depth") or 5),
                allow_generated=bool(params.get("allow_generated")),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.intake_board",
            "Return a UI-ready board for finding, reviewing, and registering real NLE long-project corpus projects.",
            "nle",
            params_schema=schema_object(
                {
                    "search_roots": {"type": "array"},
                    "manifest_path": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "max_depth": {"type": "integer"},
                    "allow_generated": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.intake_board",
            adapter.nle_real_corpus_intake_board(
                search_roots=[
                    str(row)
                    for row in list(params.get("search_roots") or [])
                    if str(row or "").strip()
                ],
                manifest_path=str(params.get("manifest_path") or ""),
                max_results=int(params.get("max_results") or 20),
                max_depth=int(params.get("max_depth") or 5),
                allow_generated=bool(params.get("allow_generated")),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.collection_kit",
            "Return a guided real-project corpus collection kit without treating generated fixtures as professional NLE evidence.",
            "nle",
            params_schema=schema_object(
                {
                    "search_roots": {"type": "array"},
                    "manifest_path": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "max_depth": {"type": "integer"},
                    "allow_generated": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.collection_kit",
            adapter.nle_real_corpus_collection_kit(
                search_roots=[
                    str(row)
                    for row in list(params.get("search_roots") or [])
                    if str(row or "").strip()
                ],
                manifest_path=str(params.get("manifest_path") or ""),
                max_results=int(params.get("max_results") or 20),
                max_depth=int(params.get("max_depth") or 5),
                allow_generated=bool(params.get("allow_generated")),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.gate_board",
            "Return one UI-ready claim gate board for real long-project NLE corpus blockers, discovery, registration, validation, and rerun commands.",
            "nle",
            params_schema=schema_object(
                {
                    "search_roots": {"type": "array"},
                    "manifest_path": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "max_depth": {"type": "integer"},
                    "allow_generated": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.gate_board",
            adapter.nle_real_corpus_gate_board(
                search_roots=[
                    str(row)
                    for row in list(params.get("search_roots") or [])
                    if str(row or "").strip()
                ],
                manifest_path=str(params.get("manifest_path") or ""),
                max_results=int(params.get("max_results") or 20),
                max_depth=int(params.get("max_depth") or 5),
                allow_generated=bool(params.get("allow_generated")),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.workbench",
            "Return the single UI-ready workbench for real NLE corpus discovery, preflight, evidence, and claim-gate next actions.",
            "nle",
            params_schema=schema_object(
                {
                    "search_roots": {"type": "array"},
                    "manifest_path": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "max_depth": {"type": "integer"},
                    "allow_generated": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.workbench",
            adapter.nle_real_corpus_workbench(
                search_roots=[
                    str(row)
                    for row in list(params.get("search_roots") or [])
                    if str(row or "").strip()
                ],
                manifest_path=str(params.get("manifest_path") or ""),
                max_results=int(params.get("max_results") or 20),
                max_depth=int(params.get("max_depth") or 5),
                allow_generated=bool(params.get("allow_generated")),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.validation_plan",
            "Return a UI-ready validation plan for registered real long-project NLE corpus projects.",
            "nle",
            params_schema=schema_object({"manifest_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.validation_plan",
            adapter.nle_real_corpus_validation_plan(manifest_path=str(params.get("manifest_path") or "")),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.validation_packet",
            "Return a project-specific operator packet with real NLE validation checks, redaction rules, and evidence registration templates.",
            "nle",
            params_schema=schema_object(
                {
                    "project_id": {"type": "string"},
                    "project_path": {"type": "string"},
                    "manifest_path": {"type": "string"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.validation_packet",
            adapter.nle_real_corpus_validation_packet(
                project_id=str(params.get("project_id") or ""),
                project_path=str(params.get("project_path") or ""),
                manifest_path=str(params.get("manifest_path") or ""),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.validation_preflight",
            "Return machine preflight checks before operator real-project NLE validation evidence is recorded.",
            "nle",
            params_schema=schema_object(
                {
                    "project_id": {"type": "string"},
                    "project_path": {"type": "string"},
                    "manifest_path": {"type": "string"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.validation_preflight",
            adapter.nle_real_corpus_validation_preflight(
                project_id=str(params.get("project_id") or ""),
                project_path=str(params.get("project_path") or ""),
                manifest_path=str(params.get("manifest_path") or ""),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.validation_report",
            "Return registered real-project validation evidence status for open/scrub/proxy/undo/export checks.",
            "nle",
            params_schema=schema_object({"manifest_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.validation_report",
            adapter.nle_real_corpus_validation_report(manifest_path=str(params.get("manifest_path") or "")),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.validation_evidence.register",
            "Register redacted validation evidence for a real NLE corpus project.",
            "nle",
            params_schema=schema_object(
                {
                    "project_id": {"type": "string"},
                    "project_path": {"type": "string"},
                    "manifest_path": {"type": "string"},
                    "checks": {"type": "array"},
                    "notes": {"type": "string"},
                    "operator": {"type": "string"},
                    "evidence_path": {"type": "string"},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=False,
            supports_dry_run=True,
            undo_label="Register NLE real project validation evidence",
        ),
        lambda params, dry: ok_result(
            "nle.real_corpus.validation_evidence.register",
            adapter.nle_real_corpus_preview_validation_evidence(
                project_id=str(params.get("project_id") or ""),
                project_path=str(params.get("project_path") or ""),
                manifest_path=str(params.get("manifest_path") or ""),
                checks=params.get("checks") if isinstance(params.get("checks"), (list, dict)) else (),
                notes=str(params.get("notes") or ""),
                operator=str(params.get("operator") or ""),
                evidence_path=str(params.get("evidence_path") or ""),
            )
            if dry
            else adapter.nle_real_corpus_register_validation_evidence(
                project_id=str(params.get("project_id") or ""),
                project_path=str(params.get("project_path") or ""),
                manifest_path=str(params.get("manifest_path") or ""),
                checks=params.get("checks") if isinstance(params.get("checks"), (list, dict)) else (),
                notes=str(params.get("notes") or ""),
                operator=str(params.get("operator") or ""),
                evidence_path=str(params.get("evidence_path") or ""),
            ),
            dry_run=bool(dry),
            changed=not bool(dry),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.register",
            "Register the current or specified real project as NLE long-project corpus evidence.",
            "nle",
            params_schema=schema_object(
                {
                    "project_path": {"type": "string"},
                    "manifest_path": {"type": "string"},
                    "label": {"type": "string"},
                    "notes": {"type": "string"},
                    "allow_generated": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=False,
            supports_dry_run=True,
            undo_label="Register NLE real project corpus evidence",
        ),
        lambda params, dry: ok_result(
            "nle.real_corpus.register",
            adapter.nle_real_corpus_preview_register(
                project_path=str(params.get("project_path") or ""),
                manifest_path=str(params.get("manifest_path") or ""),
                label=str(params.get("label") or ""),
                notes=str(params.get("notes") or ""),
                allow_generated=bool(params.get("allow_generated")),
            )
            if dry
            else adapter.nle_real_corpus_register(
                project_path=str(params.get("project_path") or ""),
                manifest_path=str(params.get("manifest_path") or ""),
                label=str(params.get("label") or ""),
                notes=str(params.get("notes") or ""),
                allow_generated=bool(params.get("allow_generated")),
            ),
            dry_run=bool(dry),
            changed=not bool(dry),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.nle_fuzzer.status",
            "Return timeline fuzzer readiness for undo and edge-case NLE QA.",
            "timeline",
            params_schema=schema_object({"report_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.nle_fuzzer.status",
            adapter.nle_timeline_stress_status(report_path=str(params.get("report_path") or "")),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.core_action_coverage",
            "Return grouped core NLE action coverage for edit, project-bin, multicam, storyline, and undo surfaces.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "timeline.core_action_coverage",
            adapter.nle_core_action_coverage(action_ids=tuple(registry._handlers.keys())),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.nle_core_safety_matrix",
            "Return the NLE dry-run, destructive-confirm, undo, and real-corpus claim-gate safety matrix.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "timeline.nle_core_safety_matrix",
            adapter.nle_core_safety_matrix(action_ids=tuple(registry._handlers.keys())),
        ),
    )
    registry.register(
        ActionSpec(
            "source_record.usability_board",
            "Return Source/Record monitor usability cards for dual monitor layout, patching, keyboard overlay, and review-before-apply.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "source_record.usability_board",
            adapter.source_record_usability_board(action_ids=tuple(registry._handlers.keys())),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.export_parity_board",
            "Return multicam export parity readiness for angle bins, sync quality, waveform offsets, live switch dashboard, and export handoff.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "timeline.multicam.export_parity_board",
            adapter.multicam_export_parity_board(action_ids=tuple(registry._handlers.keys())),
        ),
    )
    registry.register(
        ActionSpec(
            "project_bin.proxy_apply_review_board",
            "Return proxy regenerate/apply review status, stale proxy warnings, and safe background job controls.",
            "project",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "project_bin.proxy_apply_review_board",
            adapter.proxy_apply_review_board(),
        ),
    )
    registry.register(
        ActionSpec(
            "project_bin.conform_apply_review_board",
            "Return conform/relink apply review status for offline media, timeline clips, and reviewed batch apply.",
            "project",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "project_bin.conform_apply_review_board",
            adapter.conform_apply_review_board(),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.undo_long_session_plan",
            "Return a real-project long-session undo validation plan using review, recovery, stability, and real corpus gates.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "timeline.undo_long_session_plan",
            adapter.undo_long_session_plan(action_ids=tuple(registry._handlers.keys())),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.storyline_gesture_polish_board",
            "Return Final Cut-style storyline gesture polish for anchors, role filters, drag cues, and audition visuals.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "timeline.storyline_gesture_polish_board",
            adapter.storyline_gesture_polish_board(action_ids=tuple(registry._handlers.keys())),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.undo_health",
            "Return UI-ready undo/redo and edge-case health matrix from timeline fuzzer evidence.",
            "timeline",
            params_schema=schema_object({"report_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.undo_health",
            adapter.nle_undo_health(report_path=str(params.get("report_path") or "")),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.undo_review_board",
            "Return a product-facing undo and edge-case QA review board with operation coverage, risk cards, blockers, and rerun commands.",
            "timeline",
            params_schema=schema_object({"report_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.undo_review_board",
            adapter.nle_undo_review_board(report_path=str(params.get("report_path") or "")),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.undo_recovery_playbook",
            "Return a UI-ready undo failure recovery playbook with rerun, triage, and reproduction-step commands.",
            "timeline",
            params_schema=schema_object({"report_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.undo_recovery_playbook",
            adapter.nle_undo_recovery_playbook(report_path=str(params.get("report_path") or "")),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.undo_stability_dashboard",
            "Return one UI-ready dashboard for undo fuzzer health, operation coverage, risk cards, and recovery commands.",
            "timeline",
            params_schema=schema_object({"report_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.undo_stability_dashboard",
            adapter.nle_undo_stability_dashboard(report_path=str(params.get("report_path") or "")),
        ),
    )


__all__ = ["register_nle_readiness_actions"]

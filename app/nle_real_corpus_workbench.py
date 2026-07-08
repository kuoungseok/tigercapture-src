"""UI-ready workbench for real NLE corpus evidence collection."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.nle_real_corpus import (
    DEFAULT_MANIFEST_PATH,
    build_nle_real_project_corpus_report,
    build_nle_real_project_gate_board,
    build_nle_real_project_validation_preflight,
    build_nle_real_project_validation_report,
    discover_nle_real_project_candidates,
    load_manifest,
)


NLE_REAL_CORPUS_WORKBENCH_SCHEMA = "tigerstudio.nle.real_project_corpus.workbench.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _manifest_path(path: str | Path | None) -> Path:
    row = Path(path or DEFAULT_MANIFEST_PATH)
    return row if row.is_absolute() else Path(__file__).resolve().parents[1] / row


def _candidate_row(candidate: Mapping[str, Any]) -> dict[str, Any]:
    metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), Mapping) else {}
    return {
        "path": str(candidate.get("path") or ""),
        "label": str(candidate.get("label") or ""),
        "would_register": bool(candidate.get("would_register")),
        "warnings": list(candidate.get("warnings") or []),
        "duration_ms": _int(metrics.get("duration_ms"), 0),
        "video_clips": _int(metrics.get("video_clips"), 0),
        "audio_clips": _int(metrics.get("audio_clips"), 0),
        "missing_media_count": _int(metrics.get("missing_media_count"), 0),
    }


def _preflight_row(project: Mapping[str, Any], *, manifest: Path) -> dict[str, Any]:
    preflight = build_nle_real_project_validation_preflight(
        project_id=str(project.get("id") or ""),
        project_path=str(project.get("path") or ""),
        manifest_path=manifest,
    )
    summary = preflight.get("summary") if isinstance(preflight.get("summary"), Mapping) else {}
    machine_checks = [row for row in list(preflight.get("machine_checks") or []) if isinstance(row, Mapping)]
    return {
        "id": str(project.get("id") or ""),
        "label": str(project.get("label") or ""),
        "path": str(project.get("path") or ""),
        "valid": bool(project.get("valid")),
        "validation_ready": bool(project.get("validation_ready")),
        "machine_preflight_passed": bool(summary.get("machine_preflight_passed")),
        "machine_blockers": list(summary.get("machine_blockers") or []),
        "operator_evidence_required": bool(summary.get("operator_evidence_required", True)),
        "blocked_checks": [
            {
                "id": str(row.get("id") or ""),
                "label": str(row.get("label") or ""),
                "status": str(row.get("status") or ""),
            }
            for row in machine_checks
            if str(row.get("status") or "") == "blocked"
        ],
        "primary_action": {
            "id": "nle.real_corpus.validation_preflight",
            "params": {
                "project_id": str(project.get("id") or ""),
                "project_path": str(project.get("path") or ""),
                "manifest_path": str(manifest),
            },
        },
    }


def _primary_step(
    *,
    registerable_count: int,
    valid_project_count: int,
    preflight_ready_count: int,
    validation_ready_count: int,
    min_projects: int,
) -> dict[str, Any]:
    if valid_project_count < min_projects and registerable_count > 0:
        return {
            "id": "register_candidates",
            "label": "Register candidate real projects",
            "action_id": "nle.real_corpus.register",
            "tone": "action",
        }
    if valid_project_count < min_projects:
        return {
            "id": "find_projects",
            "label": "Find saved real Tiger Studio projects",
            "action_id": "nle.real_corpus.discover",
            "tone": "blocked",
        }
    if preflight_ready_count < min_projects:
        return {
            "id": "fix_preflight",
            "label": "Fix machine preflight blockers",
            "action_id": "nle.real_corpus.validation_preflight",
            "tone": "warning",
        }
    if validation_ready_count < min_projects:
        return {
            "id": "record_validation_evidence",
            "label": "Run operator checks and register evidence",
            "action_id": "nle.real_corpus.validation_packet",
            "tone": "action",
        }
    return {
        "id": "rerun_readiness",
        "label": "Rerun NLE readiness",
        "command": ".\\.venv\\Scripts\\python.exe tools\\qa_nle_readiness.py --out debugCapture\\nle_readiness_qa.json",
        "tone": "ready",
    }


def build_nle_real_project_workbench(
    search_roots: Sequence[str | Path] | None = None,
    *,
    manifest_path: str | Path | None = None,
    max_results: int = 20,
    max_depth: int = 5,
    allow_generated: bool = False,
) -> dict[str, Any]:
    """Return the single product workbench for real NLE evidence collection."""

    manifest = _manifest_path(manifest_path)
    corpus = build_nle_real_project_corpus_report(manifest_path=manifest)
    discovery = discover_nle_real_project_candidates(
        search_roots=search_roots,
        manifest_path=manifest,
        max_results=max(1, int(max_results)),
        max_depth=max(0, int(max_depth)),
        allow_generated=bool(allow_generated),
    )
    validation = build_nle_real_project_validation_report(manifest_path=manifest)
    gate = build_nle_real_project_gate_board(
        search_roots=search_roots,
        manifest_path=manifest,
        max_results=max(1, int(max_results)),
        max_depth=max(0, int(max_depth)),
        allow_generated=bool(allow_generated),
    )
    summary = corpus.get("summary") if isinstance(corpus.get("summary"), Mapping) else {}
    thresholds = corpus.get("thresholds") if isinstance(corpus.get("thresholds"), Mapping) else {}
    candidates = [row for row in list(discovery.get("candidates") or []) if isinstance(row, Mapping)]
    registerable = [_candidate_row(row) for row in candidates if bool(row.get("would_register"))]
    rejected = [_candidate_row(row) for row in candidates if not bool(row.get("would_register"))]
    projects = [
        row
        for row in list(corpus.get("projects") or [])
        if isinstance(row, Mapping)
    ]
    preflight_rows = [_preflight_row(row, manifest=manifest) for row in projects]
    preflight_ready = [row for row in preflight_rows if bool(row.get("machine_preflight_passed"))]
    preflight_blocked = [row for row in preflight_rows if bool(row.get("valid")) and not bool(row.get("machine_preflight_passed"))]
    validation_projects = [
        row
        for row in list(validation.get("projects") or [])
        if isinstance(row, Mapping)
    ]
    validation_missing = [
        row
        for row in validation_projects
        if bool(row.get("valid_for_corpus")) and not bool(row.get("validation_ready"))
    ]
    min_projects = max(1, _int(thresholds.get("min_projects"), 3))
    valid_project_count = _int(summary.get("valid_project_count"), 0)
    preflight_ready_count = _int(summary.get("preflight_ready_count"), len(preflight_ready))
    validation_ready_count = _int(summary.get("validation_ready_count"), 0)
    primary_step = _primary_step(
        registerable_count=len(registerable),
        valid_project_count=valid_project_count,
        preflight_ready_count=preflight_ready_count,
        validation_ready_count=validation_ready_count,
        min_projects=min_projects,
    )
    return {
        "schema": NLE_REAL_CORPUS_WORKBENCH_SCHEMA,
        "ready": True,
        "claim_ready": bool(corpus.get("claim_ready")),
        "manifest": str(manifest),
        "primary_step": primary_step,
        "summary": {
            "registered_project_count": _int(summary.get("registered_project_count"), 0),
            "valid_project_count": valid_project_count,
            "preflight_ready_count": preflight_ready_count,
            "preflight_blocked_count": _int(summary.get("preflight_blocked_count"), len(preflight_blocked)),
            "validation_ready_count": validation_ready_count,
            "validation_missing_count": _int(summary.get("validation_missing_count"), len(validation_missing)),
            "min_projects": min_projects,
            "blockers": list(corpus.get("blockers") or []),
        },
        "cards": [
            {
                "id": "valid_projects",
                "label": "Valid real projects",
                "current": valid_project_count,
                "required": min_projects,
                "tone": "ready" if valid_project_count >= min_projects else "blocked",
            },
            {
                "id": "preflight_ready",
                "label": "Machine preflight ready",
                "current": preflight_ready_count,
                "required": min_projects,
                "tone": "ready" if preflight_ready_count >= min_projects else "warning",
            },
            {
                "id": "validation_ready",
                "label": "Operator validation ready",
                "current": validation_ready_count,
                "required": min_projects,
                "tone": "ready" if validation_ready_count >= min_projects else "warning",
            },
        ],
        "sections": [
            {
                "id": "registerable_candidates",
                "title": "Registerable candidates",
                "status": "ready" if registerable else "empty",
                "rows": registerable[:10],
            },
            {
                "id": "preflight_blocked",
                "title": "Preflight blockers",
                "status": "warning" if preflight_blocked else "ok",
                "rows": preflight_blocked[:10],
            },
            {
                "id": "preflight_ready",
                "title": "Preflight ready projects",
                "status": "ready" if preflight_ready else "empty",
                "rows": preflight_ready[:10],
            },
            {
                "id": "validation_missing",
                "title": "Needs operator evidence",
                "status": "warning" if validation_missing else "ok",
                "rows": validation_missing[:10],
            },
            {
                "id": "rejected_candidates",
                "title": "Rejected candidates",
                "status": "warning" if rejected else "ok",
                "rows": rejected[:10],
            },
        ],
        "commands": {
            "discover_enabled": True,
            "register_candidates_enabled": bool(registerable),
            "open_gate_board_enabled": True,
            "open_validation_preflight_enabled": bool(projects),
            "open_validation_packet_enabled": bool(validation_missing),
            "register_validation_evidence_enabled": bool(preflight_ready),
            "run_real_corpus_qa_enabled": True,
            "run_preflight_qa_enabled": True,
            "run_nle_readiness_enabled": True,
        },
        "action_sequence": [
            {
                "id": "nle.real_corpus.discover",
                "params": {
                    "search_roots": [str(row) for row in (search_roots or ())],
                    "manifest_path": str(manifest),
                    "max_results": max(1, int(max_results)),
                    "max_depth": max(0, int(max_depth)),
                    "allow_generated": bool(allow_generated),
                },
            },
            {"id": "nle.real_corpus.gate_board", "params": {"manifest_path": str(manifest)}},
            {"id": "nle.real_corpus.validation_preflight", "params": {"manifest_path": str(manifest)}},
            {"id": "nle.real_corpus.validation_packet", "params": {"manifest_path": str(manifest)}},
            {"id": "nle.real_corpus.validation_report", "params": {"manifest_path": str(manifest)}},
            {"id": "timeline.nle_target_gap", "params": {"target_score": 95}},
        ],
        "qa_commands": [
            ".\\.venv\\Scripts\\python.exe tools\\qa_nle_real_project_corpus.py",
            ".\\.venv\\Scripts\\python.exe tools\\qa_nle_real_project_preflight.py",
            ".\\.venv\\Scripts\\python.exe tools\\qa_nle_readiness.py --out debugCapture\\nle_readiness_qa.json",
            ".\\.venv\\Scripts\\python.exe tools\\qa_nle_target_gap.py --target-score 95 --out debugCapture\\nle_target_gap_qa.json",
        ],
        "gate_board": {
            "claim_ready": bool(gate.get("claim_ready")),
            "professional_nle_claim_blocked": bool(gate.get("professional_nle_claim_blocked")),
            "summary": dict(gate.get("summary") or {}),
        },
    }


__all__ = ["NLE_REAL_CORPUS_WORKBENCH_SCHEMA", "build_nle_real_project_workbench"]

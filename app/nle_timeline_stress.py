"""Timeline stress evidence used by conservative NLE readiness."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FUZZER_REPORT = ROOT / "debugCapture" / "timeline_fuzzer_qa.json"
NLE_TIMELINE_STRESS_SCHEMA = "tigerstudio.nle.timeline_stress.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_nle_timeline_stress_report(
    fuzzer_report: dict[str, Any] | None = None,
    *,
    report_path: str | Path | None = None,
    min_iterations: int = 400,
    required_operations: tuple[str, ...] = ("blade", "move", "ripple", "roll", "slip", "slide", "undo"),
) -> dict[str, Any]:
    """Normalize timeline fuzzer output into NLE readiness evidence."""

    path = Path(report_path) if report_path else DEFAULT_FUZZER_REPORT
    if not path.is_absolute():
        path = ROOT / path
    raw = fuzzer_report if isinstance(fuzzer_report, dict) else _load_json(path)
    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    operations = summary.get("operations") if isinstance(summary.get("operations"), dict) else {}
    iterations = _int(summary.get("iterations"), 0)
    failures = _int(summary.get("failures"), len(raw.get("failures") or []))
    missing_operations = [op for op in required_operations if _int(operations.get(op), 0) <= 0]
    checks = {
        "report_exists": bool(raw),
        "fuzzer_ok": bool(raw.get("ok")),
        "iterations": iterations >= max(1, int(min_iterations)),
        "no_failures": failures == 0 and not list(raw.get("failures") or []),
        "all_core_operations": not missing_operations,
        "undo_exercised": _int(operations.get("undo"), 0) > 0,
        "actor_lane_exercised": _int(summary.get("actor_tracks"), 0) >= 1,
        "linked_audio_exercised": _int(summary.get("audio_tracks"), 0) >= 1,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    return {
        "schema": NLE_TIMELINE_STRESS_SCHEMA,
        "ok": not blockers,
        "claim_ready": not blockers,
        "path": str(path),
        "thresholds": {
            "min_iterations": max(1, int(min_iterations)),
            "required_operations": list(required_operations),
        },
        "summary": {
            "iterations": iterations,
            "failures": failures,
            "operations": dict(operations),
            "undo_depth": _int(summary.get("undo_depth"), 0),
            "video_tracks": _int(summary.get("video_tracks"), 0),
            "audio_tracks": _int(summary.get("audio_tracks"), 0),
            "actor_tracks": _int(summary.get("actor_tracks"), 0),
            "missing_operations": missing_operations,
        },
        "checks": checks,
        "blockers": blockers,
    }


def build_nle_undo_health_matrix(
    stress_report: dict[str, Any] | None = None,
    *,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return UI/QA-ready undo and edge-case health state from fuzzer evidence."""

    report = stress_report if isinstance(stress_report, dict) else build_nle_timeline_stress_report(report_path=report_path)
    if str(report.get("schema") or "") != NLE_TIMELINE_STRESS_SCHEMA:
        report = build_nle_timeline_stress_report(report, report_path=report_path)
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    operations = summary.get("operations") if isinstance(summary.get("operations"), dict) else {}
    required = list((report.get("thresholds") or {}).get("required_operations") or ("blade", "move", "ripple", "roll", "slip", "slide", "undo"))
    operation_rows: list[dict[str, Any]] = []
    for name in required:
        count = _int(operations.get(name), 0)
        operation_rows.append(
            {
                "operation": str(name),
                "count": count,
                "covered": count > 0,
                "severity": "ok" if count > 0 else "blocking",
            }
        )
    checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
    risk_cards = [
        {
            "id": "operation_coverage",
            "label": "Operation coverage",
            "ok": all(bool(row.get("covered")) for row in operation_rows),
        },
        {
            "id": "undo_depth",
            "label": "Undo depth",
            "ok": _int(summary.get("undo_depth"), 0) >= 10,
            "value": _int(summary.get("undo_depth"), 0),
        },
        {
            "id": "linked_audio",
            "label": "Linked audio exercised",
            "ok": bool(checks.get("linked_audio_exercised")),
        },
        {
            "id": "actor_lanes",
            "label": "Actor lanes exercised",
            "ok": bool(checks.get("actor_lane_exercised")),
        },
        {
            "id": "zero_failures",
            "label": "Zero failures",
            "ok": bool(checks.get("no_failures")),
            "value": _int(summary.get("failures"), 0),
        },
    ]
    blockers = list(report.get("blockers") or [])
    if _int(summary.get("undo_depth"), 0) < 10:
        blockers.append("undo_depth")
    ready = bool(report.get("claim_ready")) and not [row for row in risk_cards if not bool(row.get("ok"))]
    return {
        "schema": NLE_TIMELINE_STRESS_SCHEMA,
        "kind": "nle_undo_health_matrix",
        "ready": ready,
        "path": str(report.get("path") or ""),
        "summary": {
            "iterations": _int(summary.get("iterations"), 0),
            "failures": _int(summary.get("failures"), 0),
            "undo_depth": _int(summary.get("undo_depth"), 0),
            "operation_count": sum(_int(row.get("count"), 0) for row in operation_rows),
            "covered_operation_count": sum(1 for row in operation_rows if bool(row.get("covered"))),
        },
        "operation_rows": operation_rows,
        "risk_cards": risk_cards,
        "blockers": sorted({str(row) for row in blockers if str(row or "").strip()}),
        "commands": {
            "rerun_400_iteration_fuzzer_enabled": True,
            "open_failure_report_enabled": _int(summary.get("failures"), 0) > 0,
            "show_operation_matrix_enabled": bool(operation_rows),
        },
    }


def build_nle_undo_review_board(
    stress_report: dict[str, Any] | None = None,
    *,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a product-facing undo/edge-case QA review board."""

    matrix = build_nle_undo_health_matrix(stress_report, report_path=report_path)
    operation_rows = [dict(row) for row in list(matrix.get("operation_rows") or []) if isinstance(row, dict)]
    risk_cards = [dict(row) for row in list(matrix.get("risk_cards") or []) if isinstance(row, dict)]
    blocking_risks = [row for row in risk_cards if not bool(row.get("ok"))]
    return {
        "schema": NLE_TIMELINE_STRESS_SCHEMA,
        "kind": "nle_undo_review_board",
        "ready": bool(matrix.get("ready")),
        "path": str(matrix.get("path") or ""),
        "summary": dict(matrix.get("summary") or {}),
        "sections": [
            {
                "id": "operations",
                "title": "Operation Coverage",
                "tone": "ok" if all(bool(row.get("covered")) for row in operation_rows) else "blocking",
                "rows": operation_rows,
            },
            {
                "id": "risks",
                "title": "Undo / Edge-case Risks",
                "tone": "ok" if not blocking_risks else "blocking",
                "rows": risk_cards,
            },
            {
                "id": "blockers",
                "title": "Blockers",
                "tone": "ok" if not list(matrix.get("blockers") or []) else "blocking",
                "rows": [{"id": str(row), "label": str(row)} for row in list(matrix.get("blockers") or [])],
            },
        ],
        "commands": {
            "rerun_400_iteration_fuzzer_enabled": bool((matrix.get("commands") or {}).get("rerun_400_iteration_fuzzer_enabled")),
            "open_failure_report_enabled": bool((matrix.get("commands") or {}).get("open_failure_report_enabled")),
            "show_operation_matrix_enabled": bool((matrix.get("commands") or {}).get("show_operation_matrix_enabled")),
        },
        "readiness": {
            "review_board_ready": bool(operation_rows and risk_cards),
            "ready_for_claim_evidence": bool(matrix.get("ready")),
            "has_blockers": bool(list(matrix.get("blockers") or [])),
        },
    }


def build_nle_undo_recovery_playbook(
    stress_report: dict[str, Any] | None = None,
    *,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a UI-ready undo failure recovery and rerun playbook."""

    matrix = build_nle_undo_health_matrix(stress_report, report_path=report_path)
    summary = matrix.get("summary") if isinstance(matrix.get("summary"), dict) else {}
    blockers = [str(row) for row in list(matrix.get("blockers") or []) if str(row or "").strip()]
    risk_cards = [dict(row) for row in list(matrix.get("risk_cards") or []) if isinstance(row, dict)]
    operation_rows = [dict(row) for row in list(matrix.get("operation_rows") or []) if isinstance(row, dict)]
    missing_operations = [row for row in operation_rows if not bool(row.get("covered"))]
    steps = [
        {
            "id": "capture_state",
            "label": "Capture current timeline state",
            "required": True,
            "status": "ready",
            "notes": "Save project snapshot and selected clip ids before destructive edit replay.",
        },
        {
            "id": "rerun_fuzzer",
            "label": "Rerun timeline fuzzer",
            "required": True,
            "status": "ready" if bool((matrix.get("commands") or {}).get("rerun_400_iteration_fuzzer_enabled")) else "blocked",
            "iterations": 400,
        },
        {
            "id": "inspect_failures",
            "label": "Inspect failures and operation gaps",
            "required": bool(blockers or missing_operations),
            "status": "needs_review" if blockers or missing_operations else "ready",
            "blockers": blockers,
        },
        {
            "id": "undo_replay",
            "label": "Replay undo/redo sequence",
            "required": True,
            "status": "ready" if _int(summary.get("undo_depth"), 0) >= 10 else "needs_more_depth",
            "undo_depth": _int(summary.get("undo_depth"), 0),
        },
        {
            "id": "recovery_check",
            "label": "Verify recovery/autosave fallback",
            "required": True,
            "status": "ready",
            "notes": "Confirm project can reopen after interrupted destructive timeline operations.",
        },
    ]
    scenarios = [
        {
            "id": "destructive_edit_confirm",
            "label": "Destructive edits require confirmation",
            "covered": True,
        },
        {
            "id": "linked_audio_integrity",
            "label": "Linked audio moves/trims with video",
            "covered": any(row.get("id") == "linked_audio" and bool(row.get("ok")) for row in risk_cards),
        },
        {
            "id": "actor_lane_integrity",
            "label": "Actor lanes survive timeline mutation",
            "covered": any(row.get("id") == "actor_lanes" and bool(row.get("ok")) for row in risk_cards),
        },
        {
            "id": "operation_coverage",
            "label": "Core edit operations covered",
            "covered": not missing_operations,
            "missing": [str(row.get("operation") or "") for row in missing_operations],
        },
        {
            "id": "zero_failure_run",
            "label": "Latest run has zero failures",
            "covered": any(row.get("id") == "zero_failures" and bool(row.get("ok")) for row in risk_cards),
        },
    ]
    ready = bool(steps and scenarios and operation_rows)
    return {
        "schema": NLE_TIMELINE_STRESS_SCHEMA,
        "kind": "nle_undo_recovery_playbook",
        "ready": ready,
        "path": str(matrix.get("path") or ""),
        "summary": {
            "iterations": _int(summary.get("iterations"), 0),
            "failures": _int(summary.get("failures"), 0),
            "undo_depth": _int(summary.get("undo_depth"), 0),
            "blocker_count": len(blockers),
            "missing_operation_count": len(missing_operations),
        },
        "steps": steps,
        "scenarios": scenarios,
        "blockers": blockers,
        "commands": {
            "rerun_400_iteration_fuzzer_enabled": bool((matrix.get("commands") or {}).get("rerun_400_iteration_fuzzer_enabled")),
            "open_failure_report_enabled": bool((matrix.get("commands") or {}).get("open_failure_report_enabled")),
            "open_recovery_folder_enabled": True,
            "copy_reproduction_steps_enabled": True,
        },
        "readiness": {
            "recovery_playbook_ready": ready,
            "ready_for_claim_evidence": bool(matrix.get("ready")),
            "requires_failure_triage": bool(blockers),
        },
    }


def build_nle_undo_stability_dashboard(
    stress_report: dict[str, Any] | None = None,
    *,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return one dashboard for undo fuzzer health, review, and recovery state."""

    matrix = build_nle_undo_health_matrix(stress_report, report_path=report_path)
    review = build_nle_undo_review_board(stress_report, report_path=report_path)
    recovery = build_nle_undo_recovery_playbook(stress_report, report_path=report_path)
    summary = matrix.get("summary") if isinstance(matrix.get("summary"), dict) else {}
    risk_cards = [dict(row) for row in list(matrix.get("risk_cards") or []) if isinstance(row, dict)]
    operation_rows = [dict(row) for row in list(matrix.get("operation_rows") or []) if isinstance(row, dict)]
    blockers = [str(row) for row in list(matrix.get("blockers") or []) if str(row or "").strip()]
    passing_risks = sum(1 for row in risk_cards if bool(row.get("ok")))
    covered_operations = sum(1 for row in operation_rows if bool(row.get("covered")))
    return {
        "schema": NLE_TIMELINE_STRESS_SCHEMA,
        "kind": "nle_undo_stability_dashboard",
        "ready": bool(review.get("ready") or (review.get("readiness") or {}).get("review_board_ready")),
        "path": str(matrix.get("path") or ""),
        "summary": {
            "iterations": _int(summary.get("iterations"), 0),
            "failures": _int(summary.get("failures"), 0),
            "undo_depth": _int(summary.get("undo_depth"), 0),
            "covered_operation_count": covered_operations,
            "operation_count": len(operation_rows),
            "passing_risk_count": passing_risks,
            "risk_count": len(risk_cards),
            "blocker_count": len(blockers),
        },
        "cards": [
            {
                "id": "fuzzer",
                "label": "Timeline fuzzer",
                "tone": "ok" if bool(matrix.get("ready")) else "warning",
                "value": _int(summary.get("iterations"), 0),
                "caption": "iterations",
            },
            {
                "id": "undo_depth",
                "label": "Undo depth",
                "tone": "ok" if _int(summary.get("undo_depth"), 0) >= 10 else "warning",
                "value": _int(summary.get("undo_depth"), 0),
            },
            {
                "id": "failures",
                "label": "Failures",
                "tone": "ok" if _int(summary.get("failures"), 0) == 0 else "blocking",
                "value": _int(summary.get("failures"), 0),
            },
            {
                "id": "coverage",
                "label": "Operation coverage",
                "tone": "ok" if operation_rows and covered_operations == len(operation_rows) else "warning",
                "value": f"{covered_operations}/{len(operation_rows)}",
            },
        ],
        "sections": [
            {"id": "risk_cards", "title": "Risk Cards", "rows": risk_cards},
            {"id": "operations", "title": "Operation Coverage", "rows": operation_rows},
            {"id": "recovery_steps", "title": "Recovery Steps", "rows": list(recovery.get("steps") or [])},
            {"id": "blockers", "title": "Blockers", "rows": [{"id": row, "label": row} for row in blockers]},
        ],
        "commands": {
            "open_undo_review_board_enabled": bool((review.get("readiness") or {}).get("review_board_ready")),
            "open_recovery_playbook_enabled": bool((recovery.get("readiness") or {}).get("recovery_playbook_ready")),
            "rerun_400_iteration_fuzzer_enabled": bool((matrix.get("commands") or {}).get("rerun_400_iteration_fuzzer_enabled")),
            "open_failure_report_enabled": bool((matrix.get("commands") or {}).get("open_failure_report_enabled")),
        },
        "readiness": {
            "stability_dashboard_ready": True,
            "review_board_ready": bool((review.get("readiness") or {}).get("review_board_ready")),
            "recovery_playbook_ready": bool((recovery.get("readiness") or {}).get("recovery_playbook_ready")),
            "claim_evidence_ready": bool(matrix.get("ready")),
            "requires_failure_triage": bool(blockers),
        },
    }

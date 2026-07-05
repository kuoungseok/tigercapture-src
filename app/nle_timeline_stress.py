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

"""Aggregate repeated Painter soak measurements without inventing pass limits."""
from __future__ import annotations

import statistics
from typing import Any, Iterable, Mapping


def _distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    rows = [float(value) for value in values]
    if not rows:
        return {"count": 0, "min": None, "max": None, "median": None, "mad": None}
    median = statistics.median(rows)
    return {
        "count": len(rows),
        "min": min(rows),
        "max": max(rows),
        "median": median,
        "mad": statistics.median(abs(value - median) for value in rows),
    }


def build_soak_baseline(reports: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(report) for report in reports]
    if len(rows) < 3:
        raise ValueError("at least three completed soak measurements are required")
    for report in rows:
        if report.get("schema") != "tigerstudio.painter.native-soak-measurement.v1":
            raise ValueError("unsupported Painter soak report schema")
        if not report.get("measurement_completed"):
            raise ValueError("incomplete Painter soak measurement cannot enter a baseline")
        workload = report.get("workload") or {}
        if (workload.get("cycle_operations"), workload.get("strokes_per_cycle")) != (120, 100):
            raise ValueError("Painter soak workload configuration differs")

    resource_names = tuple((rows[0].get("summary") or {}).get("resources", {}).keys())
    resources: dict[str, Any] = {}
    for name in resource_names:
        resources[name] = {
            "delta": _distribution(
                report["summary"]["resources"][name]["delta"] for report in rows
            ),
            "linear_slope_per_hour": _distribution(
                report["summary"]["resources"][name]["linear_slope_per_hour"]
                for report in rows
            ),
        }
    latency_names = ("p50", "p95", "p99", "max")
    return {
        "schema": "tigerstudio.painter.native-soak-baseline.v1",
        "classification": "repeated_native_measurement_baseline_not_acceptance_threshold",
        "run_count": len(rows),
        "run_ids": [str(report.get("run_id") or "") for report in rows],
        "duration_seconds": _distribution(report["measured_duration_seconds"] for report in rows),
        "operation_count": _distribution(report["workload"]["operation_count"] for report in rows),
        "cycle_count": _distribution(report["workload"]["cycle_count"] for report in rows),
        "resources": resources,
        "operation_latency_ms": {
            name: _distribution(report["summary"]["operation_latency_ms"][name] for report in rows)
            for name in latency_names
        },
        "release_claim_passed": False,
        "limitations": [
            "Observed min/max/median/MAD describe these runs; they are not acceptance thresholds.",
            "Short calibration runs cannot establish long-session stability.",
        ],
    }


__all__ = ["build_soak_baseline"]

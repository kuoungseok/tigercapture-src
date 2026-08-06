"""Aggregate three accepted two-hour Painter runs without a leak threshold."""
from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.painter_evidence_contract import evidence_record
from app.painter_runtime_metrics import linear_slope_per_hour
from app.painter_soak_acceptance import RESOURCE_KEYS, evaluate_long_soak


REPORT_SCHEMA = "tigerstudio.painter.three-run-soak-envelope.v3"
REQUIRED_RUNS = 3
RETENTION_RESOURCE_KEYS = ("private_usage_bytes",)
RESIDENCY_OBSERVATION_KEYS = ("working_set_bytes",)
WINDOWS_MEMORY_SEMANTICS = {
    "working_set_bytes": {
        "meaning": "currently_resident_physical_pages_including_shared_and_private_data",
        "acceptance_role": "observational_non_blocking",
        "source": "https://learn.microsoft.com/en-us/windows/win32/procthread/process-working-set",
    },
    "private_usage_bytes": {
        "meaning": "process_private_commit_charge",
        "acceptance_role": "retained_private_commit_blocking",
        "source": "https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex",
    },
}


def _distribution(values: Iterable[float]) -> dict[str, float]:
    rows = [float(value) for value in values]
    median = statistics.median(rows)
    return {
        "min": min(rows),
        "max": max(rows),
        "median": median,
        "mad": statistics.median(abs(value - median) for value in rows),
    }


def _retention_review(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Describe late-run retained growth without inventing a byte threshold."""

    samples = [dict(row) for row in payload.get("samples") or ()]
    duration = max(float(row.get("elapsed_seconds") or 0.0) for row in samples)
    windows: list[float] = []
    for index in range(4):
        lower = duration * index / 4.0
        upper = duration * (index + 1) / 4.0
        values = [
            float(row[key])
            for row in samples
            if row.get(key) is not None
            and float(row.get("elapsed_seconds") or 0.0) >= lower
            and (
                float(row.get("elapsed_seconds") or 0.0) < upper
                or (index == 3 and float(row.get("elapsed_seconds") or 0.0) <= upper)
            )
        ]
        windows.append(statistics.median(values))
    late_samples = [
        row
        for row in samples
        if float(row.get("elapsed_seconds") or 0.0) >= duration / 2.0
    ]
    late_slope = linear_slope_per_hour(late_samples, key)
    last_three_windows_increase = windows[1] < windows[2] < windows[3]
    positive_late_growth = bool(
        late_slope is not None
        and late_slope > 0.0
        and last_three_windows_increase
    )
    return {
        "quarter_medians": windows,
        "late_half_linear_slope_per_hour": late_slope,
        "last_three_quarter_medians_strictly_increase": last_three_windows_increase,
        "positive_late_growth": positive_late_growth,
        "magnitude_threshold_used": False,
    }


def evaluate_three_run_envelope(
    reports: Iterable[tuple[str | Path, Mapping[str, Any]]],
) -> dict[str, Any]:
    rows = [(Path(path).resolve(), dict(payload)) for path, payload in reports]
    failures: list[str] = []
    run_reviews = []
    run_ids = []
    for path, payload in rows:
        review = evaluate_long_soak(payload, raw_report_path=path)
        run_reviews.append({"path": str(path), "run_id": payload.get("run_id"), "passed": review["passed"], "failures": review["failures"]})
        run_ids.append(str(payload.get("run_id") or ""))
    if len(rows) < REQUIRED_RUNS:
        failures.append("fewer than three completed two-hour runs were supplied")
    if len(set(run_ids)) != len(run_ids) or any(not run_id for run_id in run_ids):
        failures.append("raw soak run identifiers are missing or not distinct")
    if any(not review["passed"] for review in run_reviews):
        failures.append("one or more raw two-hour runs failed scoped acceptance")

    resource_envelope: dict[str, Any] = {}
    retention_reviews: dict[str, list[dict[str, Any]]] = {}
    if not failures:
        for key in RESOURCE_KEYS:
            resource_envelope[key] = {
                field: _distribution(payload["summary"]["resources"][key][field] for _path, payload in rows)
                for field in ("delta", "linear_slope_per_hour")
            }
        resource_envelope["operation_latency_ms"] = {
            field: _distribution(payload["summary"]["operation_latency_ms"][field] for _path, payload in rows)
            for field in ("p50", "p95", "p99")
        }
        for key in (*RETENTION_RESOURCE_KEYS, *RESIDENCY_OBSERVATION_KEYS):
            retention_reviews[key] = [
                {
                    "run_id": str(payload.get("run_id") or ""),
                    **_retention_review(payload, key),
                }
                for _path, payload in rows
            ]
            if key in RETENTION_RESOURCE_KEYS:
                growing_runs = [
                    review["run_id"]
                    for review in retention_reviews[key]
                    if review["positive_late_growth"]
                ]
                if growing_runs:
                    failures.append(
                        "one or more bounded runs show unresolved positive late-run "
                        f"retention: {key} ({', '.join(growing_runs)})"
                    )

    passed = not failures
    provenance = evidence_record(
        "native-painter-three-run-two-hour-envelope",
        "native_runtime",
        passed=passed,
        producer="tools/qa_painter_soak_series_acceptance.py",
        claims=("three_run_two_hour_resource_envelope",),
        artifacts=(path for path, _payload in rows),
        limitations=(
            "The envelope describes three native two-hour cyclic runs using min/max/median/MAD.",
            "It does not claim leak freedom, universal performance, or an acceptance threshold.",
        ),
    )
    return {
        "schema": REPORT_SCHEMA,
        "passed": passed,
        "classification": "measured_three_run_envelope" if passed else "evidence_incomplete",
        "required_runs": REQUIRED_RUNS,
        "run_count": len(rows),
        "runs": run_reviews,
        "failures": failures,
        "resource_envelope": resource_envelope,
        "retention_reviews": retention_reviews,
        "retention_acceptance_contract": {
            "rule": "reject_when_any_run_has_positive_late_half_slope_and_strictly_increasing_last_three_quarter_medians",
            "blocking_resources": list(RETENTION_RESOURCE_KEYS),
            "observational_non_blocking_resources": list(RESIDENCY_OBSERVATION_KEYS),
            "magnitude_threshold_used": False,
            "reason": "private commit is the Windows process-owned retained allocation signal; working set is reported separately because it is current physical residency and includes shared pages",
            "windows_memory_semantics": WINDOWS_MEMORY_SEMANTICS,
        },
        "claims": {"leak_free": False, "universal_performance": False, "acceptance_threshold": False},
        "provenance": [provenance],
    }


__all__ = [
    "REPORT_SCHEMA",
    "REQUIRED_RUNS",
    "RESIDENCY_OBSERVATION_KEYS",
    "RETENTION_RESOURCE_KEYS",
    "WINDOWS_MEMORY_SEMANTICS",
    "evaluate_three_run_envelope",
]

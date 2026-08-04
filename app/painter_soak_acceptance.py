"""Validate a completed native Painter soak without inventing leak thresholds."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from app.painter_evidence_contract import evidence_record
from app.painter_runtime_metrics import linear_slope_per_hour


RAW_SCHEMA = "tigerstudio.painter.native-soak-measurement.v1"
REPORT_SCHEMA = "tigerstudio.painter.long-soak-acceptance.v1"
MINIMUM_DURATION_SECONDS = 7200.0
MINIMUM_SAMPLE_COUNT = 1000
RESOURCE_KEYS = (
    "working_set_bytes",
    "private_usage_bytes",
    "process_handle_count",
    "gdi_objects",
    "user_objects",
)


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def evaluate_long_soak(raw: Mapping[str, Any], *, raw_report_path: str | Path) -> dict[str, Any]:
    """Accept only the scoped fact that one 2-hour cyclic native run survived."""
    failures: list[str] = []
    requested = float(raw.get("requested_duration_seconds") or 0.0)
    measured = float(raw.get("measured_duration_seconds") or 0.0)
    samples = list(raw.get("samples") or ())
    summary = dict(raw.get("summary") or {})
    workload = dict(raw.get("workload") or {})

    if raw.get("schema") != RAW_SCHEMA:
        failures.append("unsupported raw soak schema")
    if raw.get("native_environment") is not True:
        failures.append("run was not measured in a native Qt environment")
    if raw.get("measurement_completed") is not True:
        failures.append("raw measurement did not complete")
    if requested < MINIMUM_DURATION_SECONDS or measured < MINIMUM_DURATION_SECONDS:
        failures.append("measured native duration is below 7200 seconds")
    if raw.get("operation_errors"):
        failures.append("Painter workload reported operation errors")
    if int(workload.get("operation_count") or 0) <= 0 or int(workload.get("cycle_count") or 0) <= 0:
        failures.append("cyclic Painter workload did not execute")
    if len(samples) < MINIMUM_SAMPLE_COUNT:
        failures.append("resource sample coverage is insufficient for the 2-hour run")

    elapsed = [float(row.get("elapsed_seconds")) for row in samples if _finite_number(row.get("elapsed_seconds"))]
    if len(elapsed) != len(samples) or any(right < left for left, right in zip(elapsed, elapsed[1:])):
        failures.append("resource sample elapsed times are missing or non-monotonic")
    elif samples:
        if elapsed[0] > 10.0:
            failures.append("resource sampling did not begin near workload start")
        if elapsed[-1] < MINIMUM_DURATION_SECONDS or abs(elapsed[-1] - measured) > 10.0:
            failures.append("final resource sample does not cover the measured duration")

    if int(summary.get("sample_count") or 0) != len(samples):
        failures.append("summary sample count does not match raw samples")
    if not _finite_number(summary.get("duration_seconds")) or float(summary.get("duration_seconds") or 0) < MINIMUM_DURATION_SECONDS:
        failures.append("summary duration is incomplete")
    resources = dict(summary.get("resources") or {})
    for key in RESOURCE_KEYS:
        row = dict(resources.get(key) or {})
        if not all(_finite_number(row.get(field)) for field in ("first", "last", "min", "max", "delta", "linear_slope_per_hour")):
            failures.append(f"actual Windows resource summary is incomplete: {key}")
        if any(sample.get("available") is not True or not _finite_number(sample.get(key)) for sample in samples):
            failures.append(f"actual Windows resource samples are incomplete: {key}")
            continue
        values = [float(sample[key]) for sample in samples]
        derived = {
            "first": values[0],
            "last": values[-1],
            "min": min(values),
            "max": max(values),
            "delta": values[-1] - values[0],
            "linear_slope_per_hour": linear_slope_per_hour(samples, key),
        }
        for field, expected in derived.items():
            if not _finite_number(row.get(field)) or not _finite_number(expected) or not math.isclose(
                float(row[field]), float(expected), rel_tol=1e-9, abs_tol=1e-6
            ):
                failures.append(
                    f"resource summary does not match raw samples: {key}.{field}"
                )

    latency = dict(summary.get("operation_latency_ms") or {})
    if int(latency.get("count") or 0) <= 0 or not all(
        _finite_number(latency.get(key)) for key in ("min", "max", "p50", "p95", "p99")
    ):
        failures.append("operation latency measurements are incomplete")

    passed = not failures
    provenance = evidence_record(
        "native-painter-two-hour-survival",
        "native_runtime",
        passed=passed,
        producer="tools/qa_painter_long_soak_acceptance.py",
        claims=("single_native_two_hour_survival",),
        artifacts=(raw_report_path,),
        limitations=(
            "This proves one native cyclic Painter workload survived for at least two measured hours without operation errors.",
            "It does not claim leak freedom, universal hardware performance, or a latency threshold.",
        ),
    )
    return {
        "schema": REPORT_SCHEMA,
        "passed": passed,
        "classification": "scoped_release_evidence" if passed else "evidence_incomplete",
        "raw_schema": raw.get("schema"),
        "raw_report": str(Path(raw_report_path).resolve()),
        "facts": {
            "requested_duration_seconds": requested,
            "measured_duration_seconds": measured,
            "sample_count": len(samples),
            "operation_count": int(workload.get("operation_count") or 0),
            "cycle_count": int(workload.get("cycle_count") or 0),
            "operation_error_count": len(raw.get("operation_errors") or ()),
        },
        "failures": failures,
        "claims": {
            "single_native_two_hour_workload_survived": passed,
            "leak_free": False,
            "universal_performance": False,
            "latency_threshold": False,
        },
        "provenance": [provenance],
    }


__all__ = [
    "MINIMUM_DURATION_SECONDS",
    "MINIMUM_SAMPLE_COUNT",
    "RAW_SCHEMA",
    "REPORT_SCHEMA",
    "RESOURCE_KEYS",
    "evaluate_long_soak",
]

from __future__ import annotations

import pytest


def _report(run_id: str, offset: float) -> dict:
    resources = {
        name: {"delta": offset + 1.0, "linear_slope_per_hour": offset + 2.0}
        for name in (
            "working_set_bytes",
            "private_usage_bytes",
            "process_handle_count",
            "gdi_objects",
            "user_objects",
        )
    }
    return {
        "schema": "tigerstudio.painter.native-soak-measurement.v1",
        "run_id": run_id,
        "measured_duration_seconds": 30.0 + offset,
        "measurement_completed": True,
        "workload": {
            "cycle_operations": 120,
            "strokes_per_cycle": 100,
            "operation_count": 300 + offset,
            "cycle_count": 2,
        },
        "summary": {
            "resources": resources,
            "operation_latency_ms": {
                "p50": 10.0 + offset,
                "p95": 20.0 + offset,
                "p99": 30.0 + offset,
                "max": 40.0 + offset,
            },
        },
    }


def test_soak_baseline_reports_observed_distribution_without_passing_claim() -> None:
    from app.painter_soak_baseline import build_soak_baseline

    baseline = build_soak_baseline([_report("a", 0), _report("b", 2), _report("c", 4)])
    assert baseline["run_count"] == 3
    assert baseline["operation_latency_ms"]["p95"] == {
        "count": 3,
        "min": 20.0,
        "max": 24.0,
        "median": 22.0,
        "mad": 2.0,
    }
    assert baseline["release_claim_passed"] is False
    assert "threshold" in baseline["classification"]


def test_soak_baseline_rejects_insufficient_or_incomplete_measurements() -> None:
    from app.painter_soak_baseline import build_soak_baseline

    with pytest.raises(ValueError, match="three"):
        build_soak_baseline([_report("a", 0)])
    broken = _report("b", 0)
    broken["measurement_completed"] = False
    with pytest.raises(ValueError, match="incomplete"):
        build_soak_baseline([_report("a", 0), broken, _report("c", 0)])

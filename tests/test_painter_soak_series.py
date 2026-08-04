from __future__ import annotations

import json
from pathlib import Path


RESOURCE_KEYS = ("working_set_bytes", "private_usage_bytes", "process_handle_count", "gdi_objects", "user_objects")


def _raw(run_id: str, offset: int = 0, *, growing: bool = False) -> dict:
    samples = [
        {
            "elapsed_seconds": 7200.0 * index / 999,
            "available": True,
            **{
                key: 1000 + offset + (index if growing else 0)
                for key in RESOURCE_KEYS
            },
        }
        for index in range(1000)
    ]
    delta = 999.0 if growing else 0.0
    slope = 499.5 if growing else 0.0
    return {
        "schema": "tigerstudio.painter.native-soak-measurement.v1",
        "run_id": run_id,
        "requested_duration_seconds": 7200.0,
        "measured_duration_seconds": 7200.0,
        "native_environment": True,
        "measurement_completed": True,
        "operation_errors": [],
        "workload": {"operation_count": 10000, "cycle_count": 80},
        "samples": samples,
        "summary": {
            "sample_count": 1000,
            "duration_seconds": 7200.0,
            "resources": {
                key: {
                    "first": 1000.0 + offset,
                    "last": 1000.0 + offset + delta,
                    "min": 1000.0 + offset,
                    "max": 1000.0 + offset + delta,
                    "delta": delta,
                    "linear_slope_per_hour": slope,
                }
                for key in RESOURCE_KEYS
            },
            "operation_latency_ms": {"count": 10000, "min": 1.0, "max": 5.0, "p50": 2.0 + offset, "p95": 4.0 + offset, "p99": 4.5 + offset},
        },
    }


def _rows(tmp_path: Path, count: int = 3, *, growing: bool = False):
    rows = []
    for index in range(count):
        path = tmp_path / f"raw-{index}.json"
        payload = _raw(f"run-{index}", index, growing=growing)
        path.write_text(json.dumps(payload), encoding="utf-8")
        rows.append((path, payload))
    return rows


def test_three_run_envelope_reports_distribution_without_leak_claim(tmp_path: Path) -> None:
    from app.painter_soak_series import evaluate_three_run_envelope

    report = evaluate_three_run_envelope(_rows(tmp_path))
    assert report["passed"] is True
    assert report["run_count"] == 3
    assert report["resource_envelope"]["working_set_bytes"]["delta"] == {
        "min": 0.0, "max": 0.0, "median": 0.0, "mad": 0.0,
    }
    assert report["claims"] == {"leak_free": False, "universal_performance": False, "acceptance_threshold": False}
    assert report["provenance"][0]["claims"] == ["three_run_two_hour_resource_envelope"]


def test_three_run_envelope_rejects_any_unresolved_positive_late_retention(tmp_path: Path) -> None:
    from app.painter_soak_series import evaluate_three_run_envelope

    report = evaluate_three_run_envelope(_rows(tmp_path, growing=True))
    assert report["passed"] is False
    assert any("positive late-run retention" in row for row in report["failures"])
    assert report["retention_acceptance_contract"]["magnitude_threshold_used"] is False

    rows = _rows(tmp_path)
    growing_path = tmp_path / "one-growing.json"
    growing = _raw("one-growing", growing=True)
    growing_path.write_text(json.dumps(growing), encoding="utf-8")
    mixed = evaluate_three_run_envelope([rows[0], rows[1], (growing_path, growing)])
    assert mixed["passed"] is False
    assert "one-growing" in " ".join(mixed["failures"])


def test_three_run_envelope_rejects_too_few_or_duplicate_runs(tmp_path: Path) -> None:
    from app.painter_soak_series import evaluate_three_run_envelope

    rows = _rows(tmp_path, 2)
    report = evaluate_three_run_envelope(rows)
    assert report["passed"] is False
    assert any("fewer than three" in row for row in report["failures"])
    third_path = tmp_path / "duplicate.json"
    third_path.write_text(json.dumps(rows[0][1]), encoding="utf-8")
    report = evaluate_three_run_envelope([*rows, (third_path, rows[0][1])])
    assert report["passed"] is False
    assert any("not distinct" in row for row in report["failures"])

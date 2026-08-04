from __future__ import annotations

import json
from pathlib import Path


def _raw_report() -> dict:
    resource_keys = ("working_set_bytes", "private_usage_bytes", "process_handle_count", "gdi_objects", "user_objects")
    samples = []
    for index in range(1000):
        elapsed = 7200.0 * index / 999
        samples.append({
            "elapsed_seconds": elapsed,
            "available": True,
            **{key: 1000 + index for key in resource_keys},
        })
    return {
        "schema": "tigerstudio.painter.native-soak-measurement.v1",
        "requested_duration_seconds": 7200.0,
        "measured_duration_seconds": 7200.0,
        "native_environment": True,
        "measurement_completed": True,
        "operation_errors": [],
        "workload": {"operation_count": 10000, "cycle_count": 80},
        "samples": samples,
        "summary": {
            "sample_count": len(samples),
            "duration_seconds": 7200.0,
            "resources": {
                key: {
                    "first": 1000.0,
                    "last": 1999.0,
                    "min": 1000.0,
                    "max": 1999.0,
                    "delta": 999.0,
                    "linear_slope_per_hour": 499.5,
                }
                for key in resource_keys
            },
            "operation_latency_ms": {"count": 10000, "min": 1.0, "max": 5.0, "p50": 2.0, "p95": 4.0, "p99": 4.5},
        },
    }


def test_accepts_only_scoped_two_hour_survival_claim(tmp_path: Path) -> None:
    from app.painter_soak_acceptance import evaluate_long_soak

    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps(_raw_report()), encoding="utf-8")
    report = evaluate_long_soak(_raw_report(), raw_report_path=raw_path)
    assert report["passed"] is True
    assert report["claims"] == {
        "single_native_two_hour_workload_survived": True,
        "leak_free": False,
        "universal_performance": False,
        "latency_threshold": False,
    }
    assert report["provenance"][0]["claims"] == ["single_native_two_hour_survival"]


def test_rejects_short_sparse_or_error_run(tmp_path: Path) -> None:
    from app.painter_soak_acceptance import evaluate_long_soak

    raw = _raw_report()
    raw["measured_duration_seconds"] = 60.0
    raw["samples"] = raw["samples"][:10]
    raw["summary"]["sample_count"] = 10
    raw["summary"]["duration_seconds"] = 60.0
    raw["operation_errors"] = [{"message": "failure"}]
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    report = evaluate_long_soak(raw, raw_report_path=raw_path)
    assert report["passed"] is False
    assert any("below 7200" in row for row in report["failures"])
    assert any("operation errors" in row for row in report["failures"])
    assert any("sample coverage" in row for row in report["failures"])


def test_rejects_missing_actual_windows_resource_measurement(tmp_path: Path) -> None:
    from app.painter_soak_acceptance import evaluate_long_soak

    raw = _raw_report()
    raw["samples"][500]["available"] = False
    raw["summary"]["resources"]["gdi_objects"]["last"] = None
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    report = evaluate_long_soak(raw, raw_report_path=raw_path)
    assert report["passed"] is False
    assert any("gdi_objects" in row for row in report["failures"])


def test_rejects_resource_summary_that_does_not_match_raw_samples(tmp_path: Path) -> None:
    from app.painter_soak_acceptance import evaluate_long_soak

    raw = _raw_report()
    raw["summary"]["resources"]["private_usage_bytes"]["delta"] = 0.0
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    report = evaluate_long_soak(raw, raw_report_path=raw_path)
    assert report["passed"] is False
    assert any(
        "private_usage_bytes.delta" in row for row in report["failures"]
    )

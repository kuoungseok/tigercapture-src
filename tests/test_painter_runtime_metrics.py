from __future__ import annotations


def test_percentiles_are_interpolated_from_observations() -> None:
    from app.painter_runtime_metrics import percentile

    assert percentile([], 95) is None
    assert percentile([1, 2, 3, 4, 5], 50) == 3.0
    assert percentile([0, 10], 95) == 9.5


def test_resource_slope_uses_elapsed_time_not_sample_index() -> None:
    import pytest
    from app.painter_runtime_metrics import linear_slope_per_hour

    rows = [
        {"elapsed_seconds": 0.0, "private_usage_bytes": 100.0},
        {"elapsed_seconds": 2.0, "private_usage_bytes": 104.0},
        {"elapsed_seconds": 5.0, "private_usage_bytes": 110.0},
    ]
    assert linear_slope_per_hour(rows, "private_usage_bytes") == pytest.approx(7200.0)


def test_summary_reports_raw_deltas_without_inventing_a_pass_threshold() -> None:
    import pytest
    from app.painter_runtime_metrics import summarize_runtime_samples

    rows = [
        {"elapsed_seconds": 0.0, "working_set_bytes": 100, "private_usage_bytes": 80,
         "process_handle_count": 20, "gdi_objects": 4, "user_objects": 5},
        {"elapsed_seconds": 10.0, "working_set_bytes": 120, "private_usage_bytes": 85,
         "process_handle_count": 21, "gdi_objects": 4, "user_objects": 5},
    ]
    report = summarize_runtime_samples(rows, [1.0, 2.0, 8.0])
    assert report["resources"]["working_set_bytes"]["delta"] == 20.0
    assert report["operation_latency_ms"]["p95"] == pytest.approx(7.4)
    assert "passed" not in report

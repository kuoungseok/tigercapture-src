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


def test_latency_reservoir_is_bounded_and_reproducible() -> None:
    from app.painter_runtime_metrics import BoundedLatencySampler

    first = BoundedLatencySampler(capacity=8, seed=0)
    second = BoundedLatencySampler(capacity=8, seed=0)
    for value in range(1000):
        first.add(value)
        second.add(value)

    assert first.values() == second.values()
    assert len(first.values()) == 8
    assert first.report() == {
        "method": "deterministic_algorithm_r_reservoir",
        "method_reference": "https://doi.org/10.1145/3147.3165",
        "capacity_basis": "DKW-Massart_two_sided_CDF_bound",
        "capacity_basis_reference": "https://doi.org/10.1214/aop/1176990746",
        "rank_error_bound": 0.02,
        "confidence": 0.99,
        "capacity": 8,
        "observation_count": 1000,
        "retained_sample_count": 8,
        "seed": 0,
    }


def test_default_latency_reservoir_capacity_is_derived_from_declared_bound() -> None:
    import math

    from app.painter_runtime_metrics import (
        LATENCY_CONFIDENCE,
        LATENCY_RANK_ERROR_BOUND,
        LATENCY_RESERVOIR_CAPACITY,
    )

    expected = math.ceil(
        math.log(2.0 / (1.0 - LATENCY_CONFIDENCE))
        / (2.0 * LATENCY_RANK_ERROR_BOUND**2)
    )
    assert LATENCY_RESERVOIR_CAPACITY == expected == 6623


def test_latency_reservoir_rejects_non_integer_and_boolean_capacity() -> None:
    import pytest

    from app.painter_runtime_metrics import BoundedLatencySampler

    with pytest.raises(TypeError):
        BoundedLatencySampler(capacity=8.5)
    with pytest.raises(ValueError):
        BoundedLatencySampler(capacity=True)
    with pytest.raises(ValueError):
        BoundedLatencySampler(capacity=0)


def test_windows_resource_sampling_reuses_ctypes_pointer_type() -> None:
    import ctypes
    import sys

    if sys.platform != "win32":
        return

    from app.painter_runtime_metrics import windows_process_resources

    windows_process_resources()
    before = len(ctypes._pointer_type_cache)
    for _ in range(25):
        assert windows_process_resources()["available"] is True
    assert len(ctypes._pointer_type_cache) == before

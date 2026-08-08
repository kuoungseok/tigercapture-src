"""Measured Windows process resources for Painter soak evidence."""
from __future__ import annotations

import ctypes
import functools
import math
import operator
import os
import random
import statistics
import sys
import time
from typing import Any, Iterable, Mapping


LATENCY_RANK_ERROR_BOUND = 0.02
LATENCY_CONFIDENCE = 0.99
LATENCY_RESERVOIR_CAPACITY = math.ceil(
    math.log(2.0 / (1.0 - LATENCY_CONFIDENCE))
    / (2.0 * LATENCY_RANK_ERROR_BOUND**2)
)


if sys.platform == "win32":
    from ctypes import wintypes

    class _PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]


@functools.lru_cache(maxsize=1)
def _windows_resource_api() -> tuple[Any, Any, Any, Any]:
    """Bind the Windows resource API once.

    ctypes caches pointer types by their target class. Defining the counter
    structure inside every sample permanently retained one class and pointer
    type per sample, which made the measurement process look like Painter was
    leaking memory.
    """

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESS_MEMORY_COUNTERS_EX),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    kernel32.GetProcessHandleCount.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetProcessHandleCount.restype = wintypes.BOOL
    user32.GetGuiResources.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    user32.GetGuiResources.restype = wintypes.DWORD
    return kernel32, psapi, user32, kernel32.GetCurrentProcess()


class BoundedLatencySampler:
    """Deterministic Algorithm-R reservoir for whole-run latency percentiles."""

    def __init__(
        self,
        capacity: int = LATENCY_RESERVOIR_CAPACITY,
        *,
        seed: int = 0,
    ) -> None:
        if isinstance(capacity, bool):
            raise ValueError("latency sampler capacity must be positive")
        try:
            validated_capacity = operator.index(capacity)
        except TypeError as exc:
            raise TypeError("latency sampler capacity must be an integer") from exc
        if validated_capacity <= 0:
            raise ValueError("latency sampler capacity must be positive")
        self.capacity = validated_capacity
        self.observation_count = 0
        self._values: list[float] = []
        self.seed = int(seed)
        self._random = random.Random(seed)

    def add(self, value: float) -> None:
        self.observation_count += 1
        if len(self._values) < self.capacity:
            self._values.append(float(value))
            return
        replacement = self._random.randrange(self.observation_count)
        if replacement < self.capacity:
            self._values[replacement] = float(value)

    def values(self) -> tuple[float, ...]:
        return tuple(self._values)

    def report(self) -> dict[str, Any]:
        return {
            "method": "deterministic_algorithm_r_reservoir",
            "method_reference": "https://doi.org/10.1145/3147.3165",
            "capacity_basis": "DKW-Massart_two_sided_CDF_bound",
            "capacity_basis_reference": "https://doi.org/10.1214/aop/1176990746",
            "rank_error_bound": LATENCY_RANK_ERROR_BOUND,
            "confidence": LATENCY_CONFIDENCE,
            "capacity": self.capacity,
            "observation_count": self.observation_count,
            "retained_sample_count": len(self._values),
            "seed": self.seed,
        }


def windows_process_resources() -> dict[str, Any]:
    if sys.platform != "win32":
        return {"available": False, "reason": "windows_only"}
    kernel32, psapi, user32, process = _windows_resource_api()
    counters = _PROCESS_MEMORY_COUNTERS_EX()
    counters.cb = ctypes.sizeof(counters)
    memory_ok = bool(
        psapi.GetProcessMemoryInfo(
            process,
            ctypes.byref(counters),
            ctypes.sizeof(counters),
        )
    )
    handle_count = wintypes.DWORD()
    handle_ok = bool(kernel32.GetProcessHandleCount(process, ctypes.byref(handle_count)))
    gdi = int(user32.GetGuiResources(process, 0))
    user = int(user32.GetGuiResources(process, 1))
    return {
        "available": bool(memory_ok and handle_ok),
        "pid": os.getpid(),
        "working_set_bytes": int(counters.WorkingSetSize) if memory_ok else None,
        "peak_working_set_bytes": int(counters.PeakWorkingSetSize) if memory_ok else None,
        "private_usage_bytes": int(counters.PrivateUsage) if memory_ok else None,
        "page_fault_count": int(counters.PageFaultCount) if memory_ok else None,
        "process_handle_count": int(handle_count.value) if handle_ok else None,
        "gdi_objects": gdi,
        "user_objects": user,
        "last_error": int(ctypes.get_last_error()) if not (memory_ok and handle_ok) else 0,
    }


def resource_sample(*, elapsed_seconds: float, operation_count: int, cycle_count: int) -> dict[str, Any]:
    return {
        "elapsed_seconds": float(elapsed_seconds),
        "captured_monotonic_ns": time.perf_counter_ns(),
        "operation_count": int(operation_count),
        "cycle_count": int(cycle_count),
        **windows_process_resources(),
    }


def percentile(values: Iterable[float], percent: float) -> float | None:
    rows = sorted(float(value) for value in values)
    if not rows:
        return None
    position = max(0.0, min(1.0, float(percent) / 100.0)) * (len(rows) - 1)
    left = int(math.floor(position))
    right = min(len(rows) - 1, left + 1)
    blend = position - left
    return rows[left] * (1.0 - blend) + rows[right] * blend


def linear_slope_per_hour(samples: Iterable[Mapping[str, Any]], key: str) -> float | None:
    points = [
        (float(row["elapsed_seconds"]), float(row[key]))
        for row in samples
        if row.get(key) is not None
    ]
    if len(points) < 2:
        return None
    xs = [row[0] for row in points]
    ys = [row[1] for row in points]
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator <= 0.0:
        return 0.0
    per_second = sum(
        (x - mean_x) * (y - mean_y) for x, y in points
    ) / denominator
    return per_second * 3600.0


def summarize_runtime_samples(
    samples: Iterable[Mapping[str, Any]],
    operation_latencies_ms: Iterable[float],
) -> dict[str, Any]:
    rows = [dict(row) for row in samples]
    latencies = [float(value) for value in operation_latencies_ms]
    resource_keys = (
        "working_set_bytes",
        "private_usage_bytes",
        "process_handle_count",
        "gdi_objects",
        "user_objects",
    )
    resources = {}
    for key in resource_keys:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        resources[key] = {
            "first": values[0] if values else None,
            "last": values[-1] if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "delta": values[-1] - values[0] if values else None,
            "linear_slope_per_hour": linear_slope_per_hour(rows, key),
        }
    return {
        "sample_count": len(rows),
        "duration_seconds": float(rows[-1]["elapsed_seconds"]) if rows else 0.0,
        "resources": resources,
        "operation_latency_ms": {
            "count": len(latencies),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
        },
    }


__all__ = [
    "BoundedLatencySampler",
    "LATENCY_CONFIDENCE",
    "LATENCY_RANK_ERROR_BOUND",
    "LATENCY_RESERVOIR_CAPACITY",
    "linear_slope_per_hour",
    "percentile",
    "resource_sample",
    "summarize_runtime_samples",
    "windows_process_resources",
]

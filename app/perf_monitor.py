"""Low-overhead performance logging helpers.

Disabled by default. Set ``TIGERCAPTURE_PERF=1`` to log slow calls to stderr.
This keeps profiling code available in normal builds without changing runtime
behavior for users who did not opt in.
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager


def perf_enabled() -> bool:
    value = os.environ.get("TIGERCAPTURE_PERF", "")
    return value.lower() in {"1", "true", "yes", "on"}


def slow_threshold_ms(default: float = 24.0) -> float:
    try:
        return max(1.0, float(os.environ.get("TIGERCAPTURE_PERF_SLOW_MS", default)))
    except Exception:
        return float(default)


def stage_threshold_ms(default: float = 4.0) -> float:
    try:
        return max(0.1, float(os.environ.get("TIGERCAPTURE_PERF_STAGE_MS", default)))
    except Exception:
        return float(default)


def log_perf(label: str, elapsed_ms: float, *, detail: str = "", threshold_ms: float | None = None) -> None:
    if not perf_enabled():
        return
    threshold = slow_threshold_ms() if threshold_ms is None else float(threshold_ms)
    if elapsed_ms < threshold:
        return
    suffix = f" {detail}" if detail else ""
    try:
        print(f"[perf] {label}: {elapsed_ms:.1f} ms{suffix}", file=sys.stderr, flush=True)
    except Exception:
        pass


@contextmanager
def perf_span(label: str, *, detail: str = "", threshold_ms: float | None = None):
    if not perf_enabled():
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        log_perf(
            label,
            (time.perf_counter() - start) * 1000.0,
            detail=detail,
            threshold_ms=threshold_ms,
        )

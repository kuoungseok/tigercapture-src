"""Deterministic render and repeated-template performance acceptance gate."""
from __future__ import annotations

from collections import Counter, defaultdict
import gc
from hashlib import sha256
import math
import statistics
import tracemalloc
from typing import Any, Iterable

from PySide6.QtGui import QImage

from .export_renderer import MotionExportRenderer
from .schema import MotionComposition
from .templates import apply_template_to_composition


PERFORMANCE_GATE_SCHEMA = "tigerstudio.motion.performance_gate.v1"


def _image_hash(image: QImage) -> str:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    payload = bytes(converted.constBits())
    return sha256(payload).hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return float(ordered[index])


def stress_template_switches(
    composition: MotionComposition,
    template_ids: Iterable[str],
    *,
    iterations: int = 20,
    variant: str = "",
    max_retained_bytes: int = 16 * 1024 * 1024,
) -> dict[str, Any]:
    ids = [str(value) for value in template_ids if str(value)]
    if not ids:
        return {
            "ok": True,
            "skipped": True,
            "reason": "no_template_ids",
            "iterations": 0,
        }
    iterations = max(1, int(iterations))
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()
    gc.collect()
    before_current, _ = tracemalloc.get_traced_memory()
    candidate = MotionComposition.from_dict(composition.to_dict())
    layer_counts: list[int] = []
    for index in range(iterations):
        candidate = apply_template_to_composition(
            candidate,
            ids[index % len(ids)],
            variant=variant,
            replace_existing=True,
        )
        layer_counts.append(len(candidate.layers))
    gc.collect()
    after_current, peak = tracemalloc.get_traced_memory()
    if not was_tracing:
        tracemalloc.stop()
    baseline_count = max(layer_counts[: min(len(ids), len(layer_counts))], default=0)
    later_max = max(layer_counts[len(ids):], default=baseline_count)
    retained_bytes = max(0, int(after_current - before_current))
    layer_growth = max(0, int(later_max - baseline_count))
    return {
        "ok": layer_growth == 0 and retained_bytes <= max_retained_bytes,
        "skipped": False,
        "iterations": iterations,
        "template_ids": ids,
        "baseline_max_layers": baseline_count,
        "later_max_layers": later_max,
        "layer_growth": layer_growth,
        "retained_bytes": retained_bytes,
        "peak_traced_bytes": int(peak),
        "max_retained_bytes": int(max_retained_bytes),
    }


def run_motion_performance_gate(
    composition: MotionComposition,
    *,
    sample_times_ms: Iterable[float] | None = None,
    iterations: int = 3,
    width: int | None = None,
    height: int | None = None,
    max_p95_ms: float = 0.0,
    require_gpu: bool = False,
    cache_max_bytes: int = 64 * 1024 * 1024,
    template_ids: Iterable[str] = (),
    template_switch_iterations: int = 0,
) -> dict[str, Any]:
    times = [float(value) for value in (sample_times_ms or ())]
    if not times:
        times = [0.0, composition.duration_ms * 0.5, max(0.0, composition.duration_ms - 1.0)]
    iterations = max(1, int(iterations))
    renderer = MotionExportRenderer(cache_capacity=max(1, len(times)), cache_max_bytes=cache_max_bytes)
    timings: list[float] = []
    hashes_by_time: dict[str, list[str]] = defaultdict(list)
    backends: Counter[str] = Counter()
    fallback_reasons: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    for iteration in range(iterations):
        for time_ms in times:
            frame = renderer.render_frame(
                composition,
                time_ms,
                width=width,
                height=height,
                use_cache=False,
            )
            report = dict(renderer.last_render_report)
            frame_hash = _image_hash(frame)
            elapsed_ms = float(report.get("frame_render_ms") or 0.0)
            backend = str(report.get("backend") or "unknown")
            reason = str(report.get("reason") or "")
            timings.append(elapsed_ms)
            hashes_by_time[f"{time_ms:.3f}"].append(frame_hash)
            backends[backend] += 1
            if report.get("gpu_fallback") or "fallback" in backend:
                fallback_reasons[reason or "unspecified"] += 1
            samples.append({
                "iteration": iteration,
                "time_ms": time_ms,
                "hash": frame_hash,
                "backend": backend,
                "fallback_reason": reason,
                "frame_render_ms": elapsed_ms,
            })
    deterministic = all(len(set(rows)) == 1 for rows in hashes_by_time.values())
    renderer.render_frame(composition, times[0], width=width, height=height, use_cache=True)
    renderer.render_frame(composition, times[0], width=width, height=height, use_cache=True)
    cache_report = dict(renderer.last_render_report)
    cache = renderer.cache.diagnostics()
    p95_ms = _percentile(timings, 0.95)
    gpu_ok = not require_gpu or all(
        "gpu" in backend.lower() or "opengl" in backend.lower()
        for backend in backends
    )
    timing_ok = max_p95_ms <= 0.0 or p95_ms <= max_p95_ms
    cache_ok = cache["current_bytes"] <= cache["max_bytes"] and bool(cache_report.get("cache_hit"))
    template_stress = stress_template_switches(
        composition,
        template_ids,
        iterations=template_switch_iterations,
    ) if template_switch_iterations > 0 else {
        "ok": True, "skipped": True, "reason": "template_switch_iterations_disabled", "iterations": 0,
    }
    checks = {
        "deterministic_frames": deterministic,
        "timing_budget": timing_ok,
        "gpu_requirement": gpu_ok,
        "cache_budget_and_hit": cache_ok,
        "template_switch_stability": bool(template_stress["ok"]),
    }
    return {
        "schema": PERFORMANCE_GATE_SCHEMA,
        "ok": all(checks.values()),
        "composition_id": composition.id,
        "composition_revision": composition.revision,
        "checks": checks,
        "sample_times_ms": times,
        "iterations": iterations,
        "render_count": len(samples),
        "timing": {
            "mean_ms": round(statistics.fmean(timings), 3) if timings else 0.0,
            "p50_ms": round(_percentile(timings, 0.5), 3),
            "p95_ms": round(p95_ms, 3),
            "max_ms": round(max(timings, default=0.0), 3),
            "max_p95_ms": float(max_p95_ms),
        },
        "backend_counts": dict(backends),
        "fallback_reason_counts": dict(fallback_reasons),
        "frame_hashes": {key: rows[0] for key, rows in hashes_by_time.items()},
        "cache": cache,
        "template_switch_stress": template_stress,
        "samples": samples,
    }


__all__ = [
    "PERFORMANCE_GATE_SCHEMA",
    "run_motion_performance_gate",
    "stress_template_switches",
]

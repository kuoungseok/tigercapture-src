"""Deterministic geometry helpers for retained Painter brush styles.

The retained style renderer is an authored Tiger model.  These helpers make
its sampling and pseudo-random inputs explicit; they do not claim physical
media simulation or pixel parity with another brush engine.
"""
from __future__ import annotations

import hashlib
import math
import operator
from typing import Iterable

from app.painter_brush_dynamics import PAINTER_DYNAMIC_DAB_BUDGET


UINT64_MAX = (1 << 64) - 1
LEGACY_BRUSH_PATH_SAMPLE_BUDGET = PAINTER_DYNAMIC_DAB_BUDGET

LEGACY_BRUSH_GEOMETRY_CONTRACT: dict[str, object] = {
    "model": "tiger_authored_retained_brush_geometry_v1",
    "path_sampling": "uniform_cumulative_document_pixel_travel",
    "sample_budget": LEGACY_BRUSH_PATH_SAMPLE_BUDGET,
    "budget_behavior": "uniform_full_path_resampling_with_explicit_diagnostic",
    "random_source": "blake2b_uint64",
    "physical_media_claim": False,
    "external_brush_engine_parity_claim": False,
}


def stable_style_seed(style: str) -> int:
    """Return a process-independent uint64 seed for a style identifier."""
    digest = hashlib.blake2b(
        str(style or "").encode("utf-8"),
        digest_size=8,
        person=b"TigerSty",
    ).digest()
    return int.from_bytes(digest, "little", signed=False)


def deterministic_unit(seed: int, index: int, channel: int = 0) -> float:
    """Return a deterministic value in the closed normalized uint64 domain."""
    payload = b"".join(
        int(value & UINT64_MAX).to_bytes(8, "little", signed=False)
        for value in (seed, index, channel)
    )
    digest = hashlib.blake2b(
        payload,
        digest_size=8,
        person=b"TigerLgc",
    ).digest()
    return int.from_bytes(digest, "little", signed=False) / UINT64_MAX


def sample_polyline_uniform(
    points: Iterable[tuple[float, float]],
    step_px: float,
    *,
    sample_budget: int = LEGACY_BRUSH_PATH_SAMPLE_BUDGET,
) -> tuple[list[tuple[float, float, float, int]], dict[str, object]]:
    """Sample a polyline by cumulative pixel travel with a bounded workload.

    When the requested spacing exceeds the shared Painter sample budget, the
    whole path is resampled uniformly.  This avoids silently truncating the
    tail or imposing an unrelated minimum-pixel spacing.
    """
    source: list[tuple[float, float]] = []
    for x, y in points:
        point = (float(x), float(y))
        if not all(math.isfinite(value) for value in point):
            raise ValueError("polyline points must be finite")
        source.append(point)
    if isinstance(step_px, bool) or not math.isfinite(step_px) or step_px <= 0.0:
        raise ValueError("step_px must be finite and positive")
    if isinstance(sample_budget, bool):
        raise TypeError("sample_budget must be an integer of at least 2")
    try:
        budget = operator.index(sample_budget)
    except TypeError as exc:
        raise TypeError("sample_budget must be an integer of at least 2") from exc
    if budget < 2:
        raise ValueError("sample_budget must be an integer of at least 2")
    if not source:
        return [], {
            "policy": "uniform_full_path_resampling_v1",
            "requested_spacing_px": float(step_px),
            "effective_spacing_px": float(step_px),
            "estimated_samples": 0,
            "rendered_samples": 0,
            "sample_budget": budget,
            "degraded": False,
        }
    if len(source) == 1:
        return [(source[0][0], source[0][1], 0.0, 0)], {
            "policy": "uniform_full_path_resampling_v1",
            "requested_spacing_px": float(step_px),
            "effective_spacing_px": float(step_px),
            "estimated_samples": 1,
            "rendered_samples": 1,
            "sample_budget": budget,
            "degraded": False,
        }

    segments: list[tuple[float, float, float, float, float, float]] = []
    cumulative = [0.0]
    for (ax, ay), (bx, by) in zip(source, source[1:]):
        dx = bx - ax
        dy = by - ay
        length = math.hypot(dx, dy)
        if length <= 0.0:
            continue
        segments.append((ax, ay, dx, dy, length, math.atan2(dy, dx)))
        cumulative.append(cumulative[-1] + length)

    total_distance = cumulative[-1]
    if not segments:
        return [(source[-1][0], source[-1][1], 0.0, 0)], {
            "policy": "uniform_full_path_resampling_v1",
            "requested_spacing_px": float(step_px),
            "effective_spacing_px": float(step_px),
            "estimated_samples": 1,
            "rendered_samples": 1,
            "sample_budget": budget,
            "degraded": False,
        }

    estimated = int(math.ceil(total_distance / step_px)) + 1
    rendered = min(estimated, budget)
    degraded = estimated > budget
    effective_spacing = (
        total_distance / float(rendered - 1) if degraded else float(step_px)
    )
    distances = [effective_spacing * index for index in range(rendered - 1)]
    distances.append(total_distance)

    samples: list[tuple[float, float, float, int]] = []
    segment_index = 0
    for sample_index, distance in enumerate(distances):
        while (
            segment_index + 1 < len(cumulative) - 1
            and distance > cumulative[segment_index + 1]
        ):
            segment_index += 1
        ax, ay, dx, dy, length, angle = segments[segment_index]
        local_distance = min(length, max(0.0, distance - cumulative[segment_index]))
        amount = local_distance / length
        samples.append((ax + dx * amount, ay + dy * amount, angle, sample_index))

    return samples, {
        "policy": "uniform_full_path_resampling_v1",
        "requested_spacing_px": float(step_px),
        "effective_spacing_px": float(effective_spacing),
        "estimated_samples": estimated,
        "rendered_samples": rendered,
        "sample_budget": budget,
        "degraded": degraded,
    }

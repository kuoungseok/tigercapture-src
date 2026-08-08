"""Comparable, reviewable choreography candidates for layered-image motion."""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .motion_choreography import MotionChoreographyPlan, plan_motion_choreography


CHOREOGRAPHY_DIRECTOR_SCHEMA = "tigerstudio.motion.choreography_director.v1"


def infer_shot_grammar(prompt: str) -> str:
    text = str(prompt or "").casefold()
    for grammar, tokens in (
        ("headline_burst", ("headline", "news", "article", "기사", "헤드라인")),
        ("product_orbit", ("product", "orbit", "launch", "제품", "오비트")),
        ("puppet_greeting", ("greeting", "wave", "hello", "인사", "손흔")),
        ("editorial_cutout", ("collage", "cutout", "paper", "오려", "콜라주")),
    ):
        if any(token in text for token in tokens):
            return grammar
    return "layered_reveal"


def _metrics(plan: MotionChoreographyPlan) -> dict[str, Any]:
    cues = [
        item for item in plan.layers
        if not item.lock_to_background and not item.lock_to_parent
    ]
    signatures = [(
        round(item.end_offset_ratio[0], 3),
        round(item.end_offset_ratio[1], 3),
        round(item.end_rotation, 2),
    ) for item in cues]
    repeated = len(signatures) - len(set(signatures))
    event_times = sorted({value for item in cues for value in (item.start_ms, item.settle_ms)})
    max_concurrent = max((
        sum(item.start_ms <= time_ms < item.settle_ms for item in cues)
        for time_ms in event_times
    ), default=0)
    peak_travel = max((math.hypot(*item.end_offset_ratio) for item in cues), default=0.0)
    peak_rotation = max((abs(item.end_rotation) for item in cues), default=0.0)
    readability = max(
        0.0,
        100.0 - max(0, max_concurrent - 2) * 11.0 - peak_rotation * 4.0 - peak_travel * 180.0,
    )
    complexity = len(cues) * 1.5 + max_concurrent * 2.0 + peak_rotation * 0.8
    return {
        "layer_count": len(cues),
        "repeated_signature_count": repeated,
        "repetition_ratio": round(repeated / max(1, len(cues)), 4),
        "max_simultaneous_motion": max_concurrent,
        "peak_travel_ratio": round(peak_travel, 5),
        "peak_rotation_degrees": round(peak_rotation, 3),
        "readability_score": round(readability, 3),
        "complexity_cost": round(complexity, 3),
    }


def plan_choreography_candidates(
    elements: Iterable[Any],
    *,
    duration_ms: int,
    max_camera_travel_ratio: float,
    prompt: str = "",
    motion_style: str = "",
    audio_hits_ms: Sequence[int] = (),
    max_simultaneous_motion: int = 3,
) -> dict[str, Any]:
    rows = list(elements)
    grammar = infer_shot_grammar(prompt)
    candidates: list[dict[str, Any]] = []
    for variant in ("clean", "dynamic", "collage"):
        plan = plan_motion_choreography(
            rows,
            duration_ms=duration_ms,
            max_camera_travel_ratio=max_camera_travel_ratio,
            requested_variant=variant,
            prompt=prompt,
            motion_style=motion_style,
            audio_hits_ms=audio_hits_ms,
            max_simultaneous_motion=max_simultaneous_motion,
        )
        metrics = _metrics(plan)
        score = (
            metrics["readability_score"]
            - metrics["complexity_cost"] * 0.7
            - metrics["repetition_ratio"] * 20.0
        )
        candidates.append({
            "id": f"{grammar}_{variant}",
            "variant": variant,
            "shot_grammar": grammar,
            "plan": plan.to_dict(),
            "metrics": metrics,
            "score": round(score, 3),
        })
    ranked = sorted(candidates, key=lambda item: (-float(item["score"]), item["variant"]))
    return {
        "schema": CHOREOGRAPHY_DIRECTOR_SCHEMA,
        "shot_grammar": grammar,
        "max_simultaneous_motion": max(1, int(max_simultaneous_motion)),
        "recommended_candidate_id": ranked[0]["id"],
        "candidates": candidates,
        "ranking": [item["id"] for item in ranked],
        "review_required": True,
    }


def select_choreography_candidate(
    director_plan: Mapping[str, Any],
    candidate_id: str,
    *,
    approved: bool,
) -> dict[str, Any]:
    if not approved:
        raise ValueError("choreography candidate requires explicit approval")
    if str(director_plan.get("schema") or "") != CHOREOGRAPHY_DIRECTOR_SCHEMA:
        raise ValueError("unsupported choreography director plan schema")
    candidate = next((
        dict(item)
        for item in director_plan.get("candidates", [])
        if isinstance(item, Mapping) and str(item.get("id") or "") == str(candidate_id)
    ), None)
    if candidate is None:
        raise KeyError(f"unknown choreography candidate: {candidate_id}")
    return candidate


__all__ = [
    "CHOREOGRAPHY_DIRECTOR_SCHEMA",
    "infer_shot_grammar",
    "plan_choreography_candidates",
    "select_choreography_candidate",
]

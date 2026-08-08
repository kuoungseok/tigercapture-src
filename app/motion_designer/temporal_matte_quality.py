"""Temporal quality gate for propagated Motion Designer mattes."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence


TEMPORAL_MATTE_QUALITY_SCHEMA = "tigerstudio.motion.temporal_matte_quality.v1"


def _load_mask(path: str | Path):
    import cv2
    import numpy as np

    image = cv2.imread(str(Path(path)), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"matte frame not found: {path}")
    return np.asarray(image >= 128, dtype=np.uint8)


def _centroid(mask) -> tuple[float, float]:
    import numpy as np

    ys, xs = np.nonzero(mask)
    if not len(xs):
        return 0.0, 0.0
    return float(xs.mean()), float(ys.mean())


def analyze_temporal_matte_sequence(
    mask_paths: Sequence[str | Path],
    *,
    times_ms: Sequence[int] = (),
    confidences: Sequence[float] = (),
    thin_structure: bool = False,
) -> dict[str, Any]:
    """Load mask files and detect temporal matte instability."""
    paths = [str(Path(item)) for item in mask_paths]
    if len(paths) < 2:
        raise ValueError("temporal matte validation requires at least two mask frames")
    masks = [_load_mask(path) for path in paths]
    return analyze_temporal_matte_frames(
        masks,
        times_ms=times_ms,
        confidences=confidences,
        thin_structure=thin_structure,
    )


def analyze_temporal_matte_frames(
    frames: Sequence[Any],
    *,
    times_ms: Sequence[int] = (),
    confidences: Sequence[float] = (),
    thin_structure: bool = False,
) -> dict[str, Any]:
    """Detect matte pop, drift, flicker, and the first unsafe propagation frame."""
    import cv2
    import numpy as np

    masks = []
    for frame in frames:
        values = np.asarray(frame)
        threshold = 0 if values.size and float(values.max()) <= 1.0 else 127
        masks.append(np.asarray(values > threshold, dtype=np.uint8))
    if len(masks) < 2:
        raise ValueError("temporal matte validation requires at least two mask frames")
    shape = masks[0].shape
    if any(mask.shape != shape for mask in masks[1:]):
        raise ValueError("all temporal matte frames must have the same dimensions")
    frame_times = [int(value) for value in times_ms]
    if frame_times and len(frame_times) != len(masks):
        raise ValueError("times_ms must match mask_paths length")
    if not frame_times:
        frame_times = list(range(len(masks)))
    frame_confidences = [max(0.0, min(1.0, float(value))) for value in confidences]
    if frame_confidences and len(frame_confidences) != len(masks):
        raise ValueError("confidences must match mask_paths length")
    if not frame_confidences:
        frame_confidences = [1.0] * len(masks)

    height, width = shape
    pixels = float(max(1, width * height))
    diagonal = max(1.0, float((width * width + height * height) ** 0.5))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    transitions: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    stop_at_ms: int | None = None

    for index, (left, right) in enumerate(zip(masks, masks[1:]), start=1):
        left_area = int(np.count_nonzero(left))
        right_area = int(np.count_nonzero(right))
        union = int(np.count_nonzero(left | right))
        intersection = int(np.count_nonzero(left & right))
        iou = float(intersection) / float(max(1, union))
        area_change = abs(right_area - left_area) / float(max(1, left_area))
        left_center = _centroid(left)
        right_center = _centroid(right)
        centroid_step = (
            (right_center[0] - left_center[0]) ** 2
            + (right_center[1] - left_center[1]) ** 2
        ) ** 0.5 / diagonal
        left_edge = cv2.morphologyEx(left, cv2.MORPH_GRADIENT, kernel) > 0
        right_edge = cv2.morphologyEx(right, cv2.MORPH_GRADIENT, kernel) > 0
        edge_union = int(np.count_nonzero(left_edge | right_edge))
        edge_intersection = int(np.count_nonzero(left_edge & right_edge))
        boundary_iou = float(edge_intersection) / float(max(1, edge_union))
        xor_ratio = float(np.count_nonzero(left ^ right)) / pixels
        confidence = min(frame_confidences[index - 1], frame_confidences[index])

        low_confidence = confidence < 0.35
        severe = (
            right_area == 0
            or iou < 0.35
            or area_change > 0.55
            or (centroid_step > 0.15 and low_confidence)
            or confidence < 0.10
        )
        review = severe or (
            iou < 0.65
            or area_change > 0.25
            or (centroid_step > 0.06 and low_confidence)
            or boundary_iou < (0.30 if thin_structure else 0.45)
            or confidence < 0.35
        )
        state = "stop" if severe else "review" if review else "stable"
        time_ms = frame_times[index]
        if severe and stop_at_ms is None:
            stop_at_ms = time_ms
        if review:
            codes: list[str] = []
            if right_area == 0:
                codes.append("matte_disappeared")
            if iou < (0.35 if severe else 0.65):
                codes.append("mask_pop")
            if area_change > (0.55 if severe else 0.25):
                codes.append("area_flicker")
            if centroid_step > (0.15 if severe else 0.06) and low_confidence:
                codes.append("centroid_drift")
            if boundary_iou < (0.30 if thin_structure else 0.45):
                codes.append("boundary_flicker")
            if confidence < 0.35:
                codes.append("low_tracking_confidence")
            issues.append({
                "time_ms": time_ms,
                "severity": "error" if severe else "warning",
                "codes": list(dict.fromkeys(codes)),
                "message": (
                    "Propagation must stop and a correction key is required."
                    if severe
                    else "Review this matte transition and add a correction key if visible."
                ),
            })
        transitions.append({
            "from_ms": frame_times[index - 1],
            "to_ms": time_ms,
            "state": state,
            "iou": iou,
            "boundary_iou": boundary_iou,
            "area_change_ratio": area_change,
            "centroid_step_ratio": centroid_step,
            "xor_ratio": xor_ratio,
            "confidence": confidence,
        })

    status = "stop_required" if stop_at_ms is not None else "review" if issues else "stable"
    return {
        "schema": TEMPORAL_MATTE_QUALITY_SCHEMA,
        "status": status,
        "stable": status == "stable",
        "can_propagate": stop_at_ms is None,
        "auto_stop_at_ms": stop_at_ms,
        "frame_count": len(masks),
        "thin_structure": bool(thin_structure),
        "issues": issues,
        "correction_times_ms": list(dict.fromkeys(
            int(item["time_ms"]) for item in issues
        )),
        "transitions": transitions,
    }


def finalize_tracked_motion_mask(
    mask: Any,
    *,
    width: int,
    height: int,
    tracking: Any,
) -> Any:
    """Attach temporal evidence and stop an unsafe propagated mask cache."""
    from .mask_adapter import TRACKING_METADATA_KEY, render_mask_alpha
    from .mask_tracking import MotionTrackSample, MotionTrackingCache
    from .schema import MotionMaskRef

    cache = tracking if isinstance(tracking, MotionTrackingCache) else MotionTrackingCache.from_dict(tracking)
    original_samples = cache.metadata.get("untrimmed_samples")
    if isinstance(original_samples, list) and len(original_samples) >= 2:
        cache.samples = [
            MotionTrackSample.from_dict(item)
            for item in original_samples
            if isinstance(item, dict)
        ]
    if len(cache.samples) < 2:
        return cache
    candidate = MotionMaskRef.from_dict(mask.to_dict())
    candidate.metadata[TRACKING_METADATA_KEY] = cache.to_dict()
    times = [int(item.time_ms) for item in cache.samples]
    frames = [
        render_mask_alpha(candidate, max(1, int(width)), max(1, int(height)), time_ms)
        for time_ms in times
    ]
    report = analyze_temporal_matte_frames(
        frames,
        times_ms=times,
        confidences=[float(item.confidence) for item in cache.samples],
        thin_structure=bool(mask.metadata.get("thin_structure", False)),
    )
    report["source"] = "rendered_propagated_motion_mask"
    cache.metadata["temporal_matte_quality"] = report
    stop_at_ms = report.get("auto_stop_at_ms")
    if stop_at_ms is not None:
        safe_samples = [
            item for item in cache.samples
            if int(item.time_ms) < int(stop_at_ms)
        ]
        cache.metadata["untrimmed_samples"] = [
            item.to_dict() for item in cache.samples
        ]
        cache.metadata["untrimmed_sample_count"] = len(cache.samples)
        cache.metadata["terminated_reason"] = "temporal_matte_quality_gate"
        cache.metadata["actual_end_ms"] = int(stop_at_ms)
        if len(safe_samples) >= 2:
            cache.samples = safe_samples
        else:
            cache.enabled = False
    else:
        cache.metadata.pop("untrimmed_samples", None)
        cache.metadata.pop("untrimmed_sample_count", None)
        if cache.metadata.get("terminated_reason") == "temporal_matte_quality_gate":
            cache.metadata["terminated_reason"] = ""
        cache.enabled = True
    return cache


__all__ = [
    "TEMPORAL_MATTE_QUALITY_SCHEMA",
    "analyze_temporal_matte_frames",
    "analyze_temporal_matte_sequence",
    "finalize_tracked_motion_mask",
]

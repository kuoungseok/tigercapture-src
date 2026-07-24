"""Mask integrity analysis and conservative repair for image motion layers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


RIGID_MOTION_MIN_MASK_FILL_RATIO = 0.38


@dataclass(slots=True)
class MaskIntegrityReport:
    bbox: tuple[int, int, int, int]
    area: int
    area_ratio: float
    mask_fill_ratio: float
    connected_components: int
    hole_count: int
    largest_hole_ratio: float
    touches_frame: bool
    sparse_or_hollow: bool
    confidence: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bbox": list(self.bbox),
            "area": int(self.area),
            "area_ratio": float(self.area_ratio),
            "mask_fill_ratio": float(self.mask_fill_ratio),
            "connected_components": int(self.connected_components),
            "hole_count": int(self.hole_count),
            "largest_hole_ratio": float(self.largest_hole_ratio),
            "touches_frame": bool(self.touches_frame),
            "sparse_or_hollow": bool(self.sparse_or_hollow),
            "confidence": float(self.confidence),
            "warnings": list(self.warnings),
        }


def analyze_mask_integrity(mask) -> MaskIntegrityReport:
    import cv2
    import numpy as np

    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    height, width = binary.shape[:2]
    total = float(max(1, height * width))
    area = int(np.count_nonzero(binary))
    points = cv2.findNonZero(binary)
    if points is None:
        bbox = (0, 0, 1, 1)
        fill_ratio = 0.0
    else:
        bbox = tuple(int(value) for value in cv2.boundingRect(points))
        fill_ratio = float(area) / float(max(1, bbox[2] * bbox[3]))

    component_count, _, stats, _ = cv2.connectedComponentsWithStats(
        binary,
        connectivity=8,
    )
    meaningful_components = sum(
        1 for row in stats[1:] if int(row[cv2.CC_STAT_AREA]) >= max(8, int(total * 0.0005))
    )
    contours, hierarchy = cv2.findContours(
        binary,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    hole_areas: list[float] = []
    if hierarchy is not None and len(hierarchy):
        for index, contour in enumerate(contours):
            parent = int(hierarchy[0][index][3])
            if parent >= 0:
                hole_areas.append(abs(float(cv2.contourArea(contour))))
    largest_hole_ratio = max(hole_areas, default=0.0) / float(max(1, bbox[2] * bbox[3]))
    touches_frame = bool(
        np.any(binary[0, :])
        or np.any(binary[-1, :])
        or np.any(binary[:, 0])
        or np.any(binary[:, -1])
    )
    sparse_or_hollow = bool(
        fill_ratio < RIGID_MOTION_MIN_MASK_FILL_RATIO
        or largest_hole_ratio > 0.28
    )
    warnings: list[str] = []
    if area <= 0:
        warnings.append("Mask is empty.")
    if meaningful_components > 1:
        warnings.append("Mask contains multiple disconnected components.")
    if sparse_or_hollow:
        warnings.append("Mask is sparse or hollow; independent motion can break object integrity.")
    if touches_frame:
        warnings.append("Mask touches the canvas boundary; camera travel may expose missing pixels.")
    confidence = 1.0
    confidence -= min(0.45, max(0, meaningful_components - 1) * 0.12)
    confidence -= 0.3 if sparse_or_hollow else 0.0
    confidence -= 0.1 if touches_frame else 0.0
    return MaskIntegrityReport(
        bbox=bbox,
        area=area,
        area_ratio=float(area) / total,
        mask_fill_ratio=fill_ratio,
        connected_components=meaningful_components,
        hole_count=len(hole_areas),
        largest_hole_ratio=largest_hole_ratio,
        touches_frame=touches_frame,
        sparse_or_hollow=sparse_or_hollow,
        confidence=max(0.0, min(1.0, confidence)),
        warnings=warnings,
    )


def motion_lock_required(report: MaskIntegrityReport, *, role: str) -> tuple[bool, str]:
    if str(role) != "primary_subject":
        return False, ""
    if report.sparse_or_hollow:
        return True, "sparse_or_hollow_primary_mask"
    if report.connected_components > 1:
        return True, "fragmented_primary_mask"
    return False, ""


def merge_masks(masks: Iterable[Any]):
    import cv2
    import numpy as np

    rows = [np.where(mask > 0, 255, 0).astype(np.uint8) for mask in masks]
    if not rows:
        raise ValueError("at least one mask is required")
    merged = np.zeros(rows[0].shape, dtype=np.uint8)
    for row in rows:
        if row.shape != merged.shape:
            raise ValueError("all masks must have the same size")
        merged = cv2.bitwise_or(merged, row)
    return merged


def split_mask(mask, *, axis: str, position: float) -> tuple[Any, Any]:
    import numpy as np

    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    height, width = binary.shape[:2]
    normalized_axis = str(axis or "vertical").strip().casefold()
    normalized_position = max(0.02, min(0.98, float(position)))
    left = binary.copy()
    right = binary.copy()
    if normalized_axis == "vertical":
        cut = max(1, min(width - 1, int(round(width * normalized_position))))
        left[:, cut:] = 0
        right[:, :cut] = 0
    elif normalized_axis == "horizontal":
        cut = max(1, min(height - 1, int(round(height * normalized_position))))
        left[cut:, :] = 0
        right[:cut, :] = 0
    else:
        raise ValueError("split axis must be vertical or horizontal")
    return left, right


__all__ = [
    "MaskIntegrityReport",
    "RIGID_MOTION_MIN_MASK_FILL_RATIO",
    "analyze_mask_integrity",
    "merge_masks",
    "motion_lock_required",
    "split_mask",
]

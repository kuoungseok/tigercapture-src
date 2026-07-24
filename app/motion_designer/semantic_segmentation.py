"""Qt-free semantic segmentation providers for layered image motion."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, Sequence


SEGMENTATION_MODES = ("auto", "basic", "sam")


class SemanticSegmentationProvider(Protocol):
    """Common contract for replaceable local or consented cloud providers."""

    provider_id: str

    def available(self) -> bool:
        ...

    def segment(
        self,
        rgb: Any,
        alpha: Any,
        *,
        max_elements: int,
        point_hints: Iterable[tuple[float, float]] = (),
    ) -> "SemanticSegmentationResult":
        ...


@dataclass(slots=True)
class SegmentationCandidate:
    mask: Any
    bbox: tuple[int, int, int, int]
    area: int
    score: float
    confidence: float
    semantic_label: str = "subject"
    metadata: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "bbox": list(self.bbox),
            "area": int(self.area),
            "score": float(self.score),
            "confidence": float(self.confidence),
            "semantic_label": self.semantic_label,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class SemanticSegmentationResult:
    requested_mode: str
    provider: str
    candidates: list[SegmentationCandidate]
    foreground_mask: Any
    confidence: float
    transparent_source: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "requested_mode": self.requested_mode,
            "provider": self.provider,
            "confidence": float(self.confidence),
            "transparent_source": bool(self.transparent_source),
            "candidate_count": len(self.candidates),
            "candidates": [item.summary() for item in self.candidates],
            "diagnostics": dict(self.diagnostics),
        }


def clean_binary_mask(mask):
    import cv2
    import numpy as np

    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    minimum = max(3, int(round(min(binary.shape[:2]) * 0.006)))
    if minimum % 2 == 0:
        minimum += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (minimum, minimum))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)


def component_records(mask, *, max_elements: int) -> list[dict[str, Any]]:
    import cv2
    import numpy as np

    h, w = mask.shape[:2]
    labels_count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        clean_binary_mask(mask),
        connectivity=8,
    )
    minimum_area = max(24, int(round(h * w * 0.006)))
    records: list[dict[str, Any]] = []
    for label in range(1, labels_count):
        x, y, width, height, area = [int(value) for value in stats[label]]
        if area < minimum_area:
            continue
        cx, cy = [float(value) for value in centroids[label]]
        center_distance = (
            (cx / max(1, w) - 0.5) ** 2
            + (cy / max(1, h) - 0.5) ** 2
        ) ** 0.5
        score = float(area) * max(0.55, 1.15 - center_distance)
        records.append({
            "label": label,
            "bbox": (x, y, width, height),
            "area": area,
            "score": score,
            "centroid": (cx, cy),
            "mask_fill_ratio": float(area) / float(max(1, width * height)),
            "mask": np.where(labels == label, 255, 0).astype(np.uint8),
        })
    records.sort(key=lambda item: (-float(item["score"]), -int(item["area"])))
    return records[:max(1, int(max_elements))]


def _border_distance_mask(rgb):
    import cv2
    import numpy as np

    h, w = rgb.shape[:2]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    border_width = max(2, min(h, w) // 32)
    border_pixels = np.concatenate(
        (
            lab[:border_width].reshape(-1, 3),
            lab[-border_width:].reshape(-1, 3),
            lab[:, :border_width].reshape(-1, 3),
            lab[:, -border_width:].reshape(-1, 3),
        ),
        axis=0,
    )
    background = np.median(border_pixels, axis=0)
    distance = np.linalg.norm(lab - background[None, None, :], axis=2)
    border_distance = np.linalg.norm(border_pixels - background[None, :], axis=1)
    threshold = max(11.0, float(np.percentile(border_distance, 92.0)) * 1.65)
    return np.where(distance >= threshold, 255, 0).astype(np.uint8), distance, threshold


def _basic_foreground(rgb, alpha):
    import cv2
    import numpy as np

    h, w = rgb.shape[:2]
    alpha_coverage = float(np.count_nonzero(alpha > 12)) / float(max(1, h * w))
    alpha_varies = int(alpha.min()) < 250 and 0.001 < alpha_coverage < 0.995
    if alpha_varies:
        mask = clean_binary_mask(np.where(alpha > 12, 255, 0).astype(np.uint8))
        return mask, {
            "provider": "source_alpha",
            "confidence": 0.98,
            "transparent_source": True,
        }

    distance_mask, distance, threshold = _border_distance_mask(rgb)
    gc_mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
    border = max(2, min(h, w) // 36)
    gc_mask[:border, :] = cv2.GC_BGD
    gc_mask[-border:, :] = cv2.GC_BGD
    gc_mask[:, :border] = cv2.GC_BGD
    gc_mask[:, -border:] = cv2.GC_BGD
    gc_mask[distance >= threshold] = cv2.GC_PR_FGD

    yy, xx = np.ogrid[:h, :w]
    center = (
        ((xx - w * 0.5) / max(1.0, w * 0.42)) ** 2
        + ((yy - h * 0.5) / max(1.0, h * 0.44)) ** 2
    )
    gc_mask[(center <= 1.0) & (distance >= threshold * 0.72)] = cv2.GC_FGD
    if not np.any(gc_mask == cv2.GC_FGD):
        gc_mask[int(h * 0.25):int(h * 0.75), int(w * 0.25):int(w * 0.75)] = cv2.GC_PR_FGD
        gc_mask[h // 2, w // 2] = cv2.GC_FGD

    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(
            cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
            gc_mask,
            None,
            background_model,
            foreground_model,
            4,
            cv2.GC_INIT_WITH_MASK,
        )
        mask = np.where(
            (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD),
            255,
            0,
        ).astype(np.uint8)
        provider = "grabcut_border_seed"
    except Exception:
        mask = distance_mask
        provider = "border_color_distance"

    mask = clean_binary_mask(mask)
    coverage = float(np.count_nonzero(mask)) / float(max(1, h * w))
    if coverage < 0.015 or coverage > 0.93:
        mask = clean_binary_mask(distance_mask)
        coverage = float(np.count_nonzero(mask)) / float(max(1, h * w))
        provider = "border_color_distance"
    confidence = max(0.25, min(0.9, 1.0 - abs(coverage - 0.38)))
    return mask, {
        "provider": provider,
        "confidence": confidence,
        "coverage": coverage,
        "transparent_source": False,
        "border_threshold": threshold,
    }


def _mask_iou(left, right) -> float:
    import numpy as np

    left_on = left > 0
    right_on = right > 0
    union = int(np.count_nonzero(left_on | right_on))
    if union <= 0:
        return 0.0
    return float(np.count_nonzero(left_on & right_on)) / float(union)


def _sam_candidates(
    rgb,
    seeds: Sequence[tuple[float, float]],
    *,
    max_elements: int,
) -> tuple[list[SegmentationCandidate], str]:
    try:
        from app.sam_segment import is_sam_available, sam_masks_from_points
    except Exception:
        return [], "unavailable"
    if not is_sam_available():
        return [], "unavailable"
    results = sam_masks_from_points(rgb, seeds)
    if not results:
        return [], "failed"

    h, w = rgb.shape[:2]
    total = float(max(1, h * w))
    accepted: list[SegmentationCandidate] = []
    for mask, confidence, seed in results:
        cleaned = clean_binary_mask(mask)
        records = component_records(cleaned, max_elements=1)
        if not records:
            continue
        record = records[0]
        coverage = float(record["area"]) / total
        if coverage < 0.006 or coverage > 0.92:
            continue
        if any(_mask_iou(record["mask"], item.mask) >= 0.88 for item in accepted):
            continue
        accepted.append(SegmentationCandidate(
            mask=record["mask"],
            bbox=record["bbox"],
            area=int(record["area"]),
            score=float(record["score"]) * max(0.2, float(confidence)),
            confidence=max(0.0, min(1.0, float(confidence))),
            semantic_label="subject",
            metadata={
                "provider": "local_sam",
                "seed": [float(seed[0]), float(seed[1])],
                "mask_fill_ratio": float(record["mask_fill_ratio"]),
            },
        ))
    accepted.sort(key=lambda item: (-item.score, -item.area))
    return accepted[:max(1, int(max_elements))], "local_sam" if accepted else "failed"


def segment_image(
    rgb,
    alpha,
    *,
    mode: str = "auto",
    max_elements: int = 5,
    point_hints: Iterable[tuple[float, float]] = (),
) -> SemanticSegmentationResult:
    """Segment one fitted RGB canvas into candidate editable instances."""
    import cv2
    import numpy as np

    requested = str(mode or "auto").strip().casefold()
    if requested not in SEGMENTATION_MODES:
        raise ValueError(f"unsupported image segmentation mode: {mode}")
    if getattr(rgb, "ndim", 0) != 3 or rgb.shape[2] != 3:
        raise ValueError("semantic segmentation expects an RGB HxWx3 array")
    if getattr(alpha, "shape", None) != rgb.shape[:2]:
        raise ValueError("semantic segmentation alpha size must match RGB")
    max_elements = max(1, min(12, int(max_elements)))

    basic_mask, basic = _basic_foreground(rgb, alpha)
    basic_records = component_records(basic_mask, max_elements=max_elements)
    basic_candidates = [
        SegmentationCandidate(
            mask=record["mask"],
            bbox=record["bbox"],
            area=int(record["area"]),
            score=float(record["score"]),
            confidence=float(basic.get("confidence", 0.5)),
            semantic_label="subject",
            metadata={
                "provider": str(basic.get("provider") or "basic"),
                "mask_fill_ratio": float(record["mask_fill_ratio"]),
            },
        )
        for record in basic_records
    ]

    provider = str(basic.get("provider") or "basic")
    candidates = basic_candidates
    sam_state = "not_requested"
    if requested in {"auto", "sam"} and not bool(basic.get("transparent_source")):
        seeds = [
            (
                float(record["centroid"][0]) / max(1, rgb.shape[1] - 1),
                float(record["centroid"][1]) / max(1, rgb.shape[0] - 1),
            )
            for record in basic_records
        ]
        seeds.extend(
            (max(0.0, min(1.0, float(x))), max(0.0, min(1.0, float(y))))
            for x, y in point_hints
        )
        if not seeds:
            seeds = [(0.5, 0.5)]
        sam_rows, sam_state = _sam_candidates(
            rgb,
            seeds[:max_elements],
            max_elements=max_elements,
        )
        if sam_rows:
            candidates = sam_rows
            provider = "local_sam"

    foreground = np.zeros(rgb.shape[:2], dtype=np.uint8)
    for item in candidates:
        foreground = cv2.bitwise_or(foreground, item.mask)
    if not candidates:
        foreground = basic_mask

    confidence = (
        float(sum(item.confidence for item in candidates)) / len(candidates)
        if candidates
        else float(basic.get("confidence", 0.0))
    )
    warnings: list[str] = []
    if requested == "sam" and provider != "local_sam":
        warnings.append("SAM was requested but unavailable; Basic Local segmentation was used.")
    return SemanticSegmentationResult(
        requested_mode=requested,
        provider=provider,
        candidates=candidates,
        foreground_mask=foreground,
        confidence=confidence,
        transparent_source=bool(basic.get("transparent_source")),
        diagnostics={
            "sam_state": sam_state,
            "basic_provider": str(basic.get("provider") or ""),
            "basic_coverage": float(
                basic.get(
                    "coverage",
                    np.count_nonzero(basic_mask) / float(max(1, basic_mask.size)),
                )
            ),
            "warnings": warnings,
        },
    )


class BasicLocalSegmentationProvider:
    provider_id = "local_basic"

    @staticmethod
    def available() -> bool:
        return True

    def segment(
        self,
        rgb: Any,
        alpha: Any,
        *,
        max_elements: int,
        point_hints: Iterable[tuple[float, float]] = (),
    ) -> SemanticSegmentationResult:
        del point_hints
        return segment_image(
            rgb,
            alpha,
            mode="basic",
            max_elements=max_elements,
        )


class SamSegmentationProvider:
    provider_id = "local_sam"

    @staticmethod
    def available() -> bool:
        try:
            from app.sam_segment import is_sam_available

            return bool(is_sam_available())
        except Exception:
            return False

    def segment(
        self,
        rgb: Any,
        alpha: Any,
        *,
        max_elements: int,
        point_hints: Iterable[tuple[float, float]] = (),
    ) -> SemanticSegmentationResult:
        return segment_image(
            rgb,
            alpha,
            mode="sam",
            max_elements=max_elements,
            point_hints=point_hints,
        )


def segmentation_capabilities() -> dict[str, dict[str, Any]]:
    sam = SamSegmentationProvider()
    return {
        "source_alpha": {
            "available": True,
            "automatic": True,
            "point_hints": False,
        },
        BasicLocalSegmentationProvider.provider_id: {
            "available": True,
            "automatic": True,
            "point_hints": False,
        },
        sam.provider_id: {
            "available": sam.available(),
            "automatic": True,
            "point_hints": True,
        },
    }


__all__ = [
    "SEGMENTATION_MODES",
    "BasicLocalSegmentationProvider",
    "SamSegmentationProvider",
    "SegmentationCandidate",
    "SemanticSegmentationProvider",
    "SemanticSegmentationResult",
    "clean_binary_mask",
    "component_records",
    "segmentation_capabilities",
    "segment_image",
]

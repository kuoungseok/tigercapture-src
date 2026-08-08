"""Qt-free semantic segmentation providers for layered image motion."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, Sequence


SEGMENTATION_MODES = ("auto", "birefnet", "sam2", "basic", "sam")


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
        object_hints: Iterable[Mapping[str, Any] | Sequence[Any]] = (),
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
    alpha: Any = None

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


@dataclass(frozen=True, slots=True)
class ObjectSegmentationHint:
    id: str
    label: str
    bbox: tuple[float, float, float, float]
    parent_id: str = ""
    part: str = ""
    pivot: tuple[float, float] | None = None
    rigid: bool = False
    foreground_points: tuple[tuple[float, float], ...] = ()
    background_points: tuple[tuple[float, float], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "label": self.label,
            "bbox": list(self.bbox),
            "parent_id": self.parent_id,
            "part": self.part,
            "rigid": bool(self.rigid),
        }
        if self.pivot is not None:
            data["pivot"] = [float(self.pivot[0]), float(self.pivot[1])]
        if self.foreground_points:
            data["foreground_points"] = [
                [float(point[0]), float(point[1])]
                for point in self.foreground_points
            ]
        if self.background_points:
            data["background_points"] = [
                [float(point[0]), float(point[1])]
                for point in self.background_points
            ]
        return data


def _normalize_points(value: Any) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    points: list[tuple[float, float]] = []
    for item in value:
        if (
            isinstance(item, Sequence)
            and not isinstance(item, (str, bytes))
            and len(item) >= 2
        ):
            points.append((float(item[0]), float(item[1])))
    return tuple(points)


def normalize_object_hints(
    values: Iterable[Mapping[str, Any] | Sequence[Any]],
) -> list[ObjectSegmentationHint]:
    hints: list[ObjectSegmentationHint] = []
    for index, value in enumerate(values):
        if isinstance(value, Mapping):
            raw_bbox = value.get("bbox")
            identifier = str(value.get("id") or f"object_{index + 1:02d}")
            label = str(value.get("label") or value.get("role") or "subject")
            parent_id = str(value.get("parent_id") or "")
            part = str(value.get("part") or "")
            raw_pivot = value.get("pivot")
            pivot = (
                (float(raw_pivot[0]), float(raw_pivot[1]))
                if isinstance(raw_pivot, Sequence)
                and not isinstance(raw_pivot, (str, bytes))
                and len(raw_pivot) >= 2
                else None
            )
            rigid = bool(value.get("rigid", bool(parent_id)))
            foreground_points = _normalize_points(
                value.get("foreground_points")
                or value.get("positive_points")
                or ()
            )
            background_points = _normalize_points(
                value.get("background_points")
                or value.get("negative_points")
                or ()
            )
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            raw_bbox = value
            identifier = f"object_{index + 1:02d}"
            label = "subject"
            parent_id = ""
            part = ""
            pivot = None
            rigid = False
            foreground_points = ()
            background_points = ()
        else:
            continue
        if not isinstance(raw_bbox, Sequence) or isinstance(raw_bbox, (str, bytes)):
            continue
        bbox = [float(item) for item in list(raw_bbox)[:4]]
        if len(bbox) != 4 or bbox[2] <= 0.0 or bbox[3] <= 0.0:
            continue
        hints.append(ObjectSegmentationHint(
            id=identifier,
            label=label,
            bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
            parent_id=parent_id,
            part=part,
            pivot=pivot,
            rigid=rigid,
            foreground_points=foreground_points,
            background_points=background_points,
        ))
    return hints


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


def mask_record(mask, *, clean: bool = True) -> dict[str, Any] | None:
    """Describe one complete object mask without dropping disconnected parts."""
    import numpy as np

    binary = clean_binary_mask(mask) if clean else np.where(mask > 0, 255, 0).astype(np.uint8)
    ys, xs = np.nonzero(binary)
    if not len(xs):
        return None
    left = int(xs.min())
    top = int(ys.min())
    right = int(xs.max()) + 1
    bottom = int(ys.max()) + 1
    width = max(1, right - left)
    height = max(1, bottom - top)
    area = int(len(xs))
    cx = float(xs.mean())
    cy = float(ys.mean())
    canvas_height, canvas_width = binary.shape[:2]
    center_distance = (
        (cx / max(1, canvas_width) - 0.5) ** 2
        + (cy / max(1, canvas_height) - 0.5) ** 2
    ) ** 0.5
    return {
        "label": 1,
        "bbox": (left, top, width, height),
        "area": area,
        "score": float(area) * max(0.55, 1.15 - center_distance),
        "centroid": (cx, cy),
        "mask_fill_ratio": float(area) / float(max(1, width * height)),
        "mask": binary,
    }


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


def _pixel_bbox(
    bbox: tuple[float, float, float, float],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x, y, box_width, box_height = bbox
    if max(abs(x), abs(y), abs(box_width), abs(box_height)) <= 1.0:
        x *= width
        y *= height
        box_width *= width
        box_height *= height
    left = max(0, min(width - 2, int(round(x))))
    top = max(0, min(height - 2, int(round(y))))
    right = max(left + 2, min(width, int(round(x + box_width))))
    bottom = max(top + 2, min(height, int(round(y + box_height))))
    return left, top, right - left, bottom - top


def _pixel_point(
    point: tuple[float, float],
    width: int,
    height: int,
) -> tuple[int, int]:
    x, y = point
    if max(abs(x), abs(y)) <= 1.0:
        x *= max(1, width - 1)
        y *= max(1, height - 1)
    return (
        max(0, min(width - 1, int(round(x)))),
        max(0, min(height - 1, int(round(y)))),
    )


def _grabcut_candidates_from_hints(
    rgb,
    hints: Sequence[ObjectSegmentationHint],
    *,
    max_elements: int,
) -> list[SegmentationCandidate]:
    import cv2
    import numpy as np

    height, width = rgb.shape[:2]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    accepted: list[SegmentationCandidate] = []
    for hint in hints[:max_elements]:
        rect = _pixel_bbox(hint.bbox, width, height)
        mask_state = np.zeros((height, width), dtype=np.uint8)
        background_model = np.zeros((1, 65), np.float64)
        foreground_model = np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(
                bgr,
                mask_state,
                rect,
                background_model,
                foreground_model,
                6,
                cv2.GC_INIT_WITH_RECT,
            )
            foreground_seeds = [
                _pixel_point(point, width, height)
                for point in hint.foreground_points
            ]
            background_seeds = [
                _pixel_point(point, width, height)
                for point in hint.background_points
            ]
            seed_radius = max(
                2,
                int(round(min(rect[2], rect[3]) * 0.014)),
            )
            if foreground_seeds or background_seeds:
                for x, y in background_seeds:
                    cv2.circle(
                        mask_state,
                        (x, y),
                        seed_radius,
                        int(cv2.GC_BGD),
                        thickness=-1,
                    )
                for x, y in foreground_seeds:
                    cv2.circle(
                        mask_state,
                        (x, y),
                        seed_radius,
                        int(cv2.GC_FGD),
                        thickness=-1,
                    )
                cv2.grabCut(
                    bgr,
                    mask_state,
                    None,
                    background_model,
                    foreground_model,
                    4,
                    cv2.GC_INIT_WITH_MASK,
                )
        except Exception:
            continue
        mask = np.where(
            (mask_state == cv2.GC_FGD) | (mask_state == cv2.GC_PR_FGD),
            255,
            0,
        ).astype(np.uint8)
        cleaned_mask = clean_binary_mask(mask)
        for x, y in background_seeds:
            cv2.circle(cleaned_mask, (x, y), seed_radius, 0, thickness=-1)
        for x, y in foreground_seeds:
            cv2.circle(cleaned_mask, (x, y), seed_radius, 255, thickness=-1)
        record = mask_record(cleaned_mask, clean=False)
        if record is None:
            continue
        coverage = float(record["area"]) / float(max(1, rect[2] * rect[3]))
        if coverage < 0.02 or coverage > 1.15:
            continue
        if any(_mask_iou(record["mask"], item.mask) >= 0.88 for item in accepted):
            continue
        confidence = max(0.48, min(0.92, 0.72 + min(coverage, 0.7) * 0.2))
        accepted.append(SegmentationCandidate(
            mask=record["mask"],
            bbox=record["bbox"],
            area=int(record["area"]),
            score=float(record["score"]) * confidence,
            confidence=confidence,
            semantic_label=hint.label,
            metadata={
                "provider": "grabcut_box_hints",
                "object_hint_id": hint.id,
                "object_hint_bbox": list(hint.bbox),
                "pixel_hint_bbox": list(rect),
                "mask_fill_ratio": float(record["mask_fill_ratio"]),
                "parent_id": hint.parent_id,
                "part": hint.part,
                "pivot": list(hint.pivot) if hint.pivot is not None else [],
                "rigid": bool(hint.rigid),
                "foreground_points": [
                    list(point) for point in hint.foreground_points
                ],
                "background_points": [
                    list(point) for point in hint.background_points
                ],
            },
        ))
    accepted.sort(key=lambda item: (-item.score, -item.area))
    return accepted[:max_elements]


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
    object_hints: Iterable[Mapping[str, Any] | Sequence[Any]] = (),
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
    normalized_object_hints = normalize_object_hints(object_hints)

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

    guided_candidates = _grabcut_candidates_from_hints(
        rgb,
        normalized_object_hints,
        max_elements=max_elements,
    ) if normalized_object_hints else []
    provider = (
        "grabcut_box_hints"
        if guided_candidates
        else str(basic.get("provider") or "basic")
    )
    candidates = guided_candidates or basic_candidates
    modern_state = "not_requested"
    if requested in {"auto", "birefnet", "sam2"} and not bool(basic.get("transparent_source")):
        try:
            from .segmentation_setup import (
                BIREFNET_PROVIDER_ID,
                SAM2_PROVIDER_ID,
                segmentation_provider_status,
            )

            birefnet_ready = bool(
                segmentation_provider_status(BIREFNET_PROVIDER_ID)["available"]
            )
            sam2_ready = bool(
                segmentation_provider_status(SAM2_PROVIDER_ID)["available"]
            )
        except Exception:
            birefnet_ready = False
            sam2_ready = False
        if requested == "sam2" or (requested == "auto" and normalized_object_hints and sam2_ready):
            if sam2_ready:
                try:
                    from .modern_segmentation import sam2_masks_from_hints

                    sam2_hints = normalized_object_hints or [
                        {"id": "subject", "label": "subject", "bbox": [0.02, 0.02, 0.96, 0.96]}
                    ]
                    rows = sam2_masks_from_hints(
                        rgb,
                        [item.to_dict() if hasattr(item, "to_dict") else item for item in sam2_hints],
                    )
                    modern_candidates: list[SegmentationCandidate] = []
                    for mask, score, metadata in rows[:max_elements]:
                        record = mask_record(mask, clean=False)
                        if record is None:
                            continue
                        modern_candidates.append(SegmentationCandidate(
                            mask=record["mask"],
                            bbox=record["bbox"],
                            area=int(record["area"]),
                            score=float(record["score"]) * max(0.2, float(score)),
                            confidence=max(0.0, min(1.0, float(score))),
                            semantic_label=str(metadata.get("label") or "subject"),
                            metadata={
                                "provider": "local_sam2",
                                "object_hint_id": str(metadata.get("id") or ""),
                                "parent_id": str(metadata.get("parent_id") or ""),
                                "part": str(metadata.get("part") or ""),
                                "rigid": bool(metadata.get("rigid", False)),
                            },
                        ))
                    if modern_candidates:
                        candidates = modern_candidates
                        provider = "local_sam2"
                        modern_state = "ready"
                except Exception as exc:
                    modern_state = f"sam2_failed:{exc}"
            else:
                modern_state = "sam2_not_installed"
        if provider != "local_sam2" and requested in {"auto", "birefnet"}:
            if birefnet_ready:
                try:
                    from .modern_segmentation import birefnet_alpha

                    soft_alpha = birefnet_alpha(rgb)
                    mask = np.where(soft_alpha >= 96, 255, 0).astype(np.uint8)
                    record = mask_record(mask, clean=False)
                    if record is not None:
                        candidates = [SegmentationCandidate(
                            mask=record["mask"],
                            bbox=record["bbox"],
                            area=int(record["area"]),
                            score=float(record["score"]),
                            confidence=0.94,
                            semantic_label="subject",
                            metadata={"provider": "local_birefnet_matting"},
                            alpha=soft_alpha,
                        )]
                        provider = "local_birefnet_matting"
                        modern_state = "ready"
                except Exception as exc:
                    modern_state = f"birefnet_failed:{exc}"
            elif modern_state == "not_requested":
                modern_state = "birefnet_not_installed"

    sam_state = "not_requested"
    if requested == "sam" and not bool(basic.get("transparent_source")):
        seeds = [
            (
                max(0.0, min(1.0, float(item.bbox[0] + item.bbox[2] * 0.5))),
                max(0.0, min(1.0, float(item.bbox[1] + item.bbox[3] * 0.5))),
            )
            for item in normalized_object_hints
        ]
        seeds.extend(
            (
                float(record["centroid"][0]) / max(1, rgb.shape[1] - 1),
                float(record["centroid"][1]) / max(1, rgb.shape[0] - 1),
            )
            for record in basic_records
        )
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
    if requested in {"auto", "birefnet", "sam2"} and provider not in {
        "local_birefnet_matting",
        "local_sam2",
        "source_alpha",
    }:
        warnings.append(
            "Modern cutout AI is unavailable; a compatibility result was produced. "
            "The Motion UI must request model setup before normal Apply."
        )
    return SemanticSegmentationResult(
        requested_mode=requested,
        provider=provider,
        candidates=candidates,
        foreground_mask=foreground,
        confidence=confidence,
        transparent_source=bool(basic.get("transparent_source")),
        diagnostics={
            "sam_state": sam_state,
            "modern_state": modern_state,
            "legacy_fallback": bool(
                requested in {"auto", "birefnet", "sam2"}
                and provider not in {"local_birefnet_matting", "local_sam2", "source_alpha"}
            ),
            "basic_provider": str(basic.get("provider") or ""),
            "basic_coverage": float(
                basic.get(
                    "coverage",
                    np.count_nonzero(basic_mask) / float(max(1, basic_mask.size)),
                )
            ),
            "object_hint_count": len(normalized_object_hints),
            "guided_candidate_count": len(guided_candidates),
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
        object_hints: Iterable[Mapping[str, Any] | Sequence[Any]] = (),
    ) -> SemanticSegmentationResult:
        del point_hints
        return segment_image(
            rgb,
            alpha,
            mode="basic",
            max_elements=max_elements,
            object_hints=object_hints,
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
        object_hints: Iterable[Mapping[str, Any] | Sequence[Any]] = (),
    ) -> SemanticSegmentationResult:
        return segment_image(
            rgb,
            alpha,
            mode="sam",
            max_elements=max_elements,
            point_hints=point_hints,
            object_hints=object_hints,
        )


def segmentation_capabilities() -> dict[str, dict[str, Any]]:
    sam = SamSegmentationProvider()
    try:
        from .segmentation_setup import segmentation_setup_status

        modern = segmentation_setup_status()
    except Exception:
        modern = {}
    return {
        "source_alpha": {
            "available": True,
            "automatic": True,
            "point_hints": False,
            "box_hints": False,
        },
        BasicLocalSegmentationProvider.provider_id: {
            "available": True,
            "automatic": True,
            "point_hints": False,
            "box_hints": True,
            "legacy": True,
        },
        "local_birefnet_matting": {
            "available": bool(modern.get("automatic_cutout_ready")),
            "automatic": True,
            "soft_alpha": True,
            "point_hints": False,
            "box_hints": False,
        },
        "local_sam2": {
            "available": bool(modern.get("assisted_segmentation_ready")),
            "automatic": False,
            "soft_alpha": False,
            "point_hints": True,
            "box_hints": True,
        },
        sam.provider_id: {
            "available": sam.available(),
            "automatic": True,
            "point_hints": True,
            "box_hints": True,
        },
    }


__all__ = [
    "SEGMENTATION_MODES",
    "BasicLocalSegmentationProvider",
    "ObjectSegmentationHint",
    "SamSegmentationProvider",
    "SegmentationCandidate",
    "SemanticSegmentationProvider",
    "SemanticSegmentationResult",
    "clean_binary_mask",
    "component_records",
    "mask_record",
    "normalize_object_hints",
    "segmentation_capabilities",
    "segment_image",
]

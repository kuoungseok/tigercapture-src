"""Quality contract for Motion Designer foreground cutouts.

The contract rejects masks that technically exist but still contain an opaque
background plate. Softer risks such as bright edge spill or abrupt source-frame
cropping are reported for review without pretending semantic certainty.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CUTOUT_QUALITY_SCHEMA = "tigerstudio.motion.cutout_quality.v1"


@dataclass(frozen=True, slots=True)
class CutoutQualityIssue:
    code: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(slots=True)
class CutoutQualityReport:
    element_id: str
    accepted: bool
    status: str
    score: float
    metrics: dict[str, Any] = field(default_factory=dict)
    issues: list[CutoutQualityIssue] = field(default_factory=list)
    schema: str = CUTOUT_QUALITY_SCHEMA

    @property
    def blockers(self) -> list[CutoutQualityIssue]:
        return [item for item in self.issues if item.severity == "error"]

    @property
    def warnings(self) -> list[CutoutQualityIssue]:
        return [item for item in self.issues if item.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "element_id": self.element_id,
            "accepted": bool(self.accepted),
            "status": self.status,
            "score": float(self.score),
            "metrics": dict(self.metrics),
            "issues": [item.to_dict() for item in self.issues],
            "blockers": [item.code for item in self.blockers],
            "warnings": [item.code for item in self.warnings],
        }


def _edge_ratio(binary, edge: str, thickness: int) -> float:
    import numpy as np

    if edge == "top":
        values = binary[:thickness, :]
    elif edge == "bottom":
        values = binary[-thickness:, :]
    elif edge == "left":
        values = binary[:, :thickness]
    else:
        values = binary[:, -thickness:]
    return float(np.count_nonzero(values)) / float(max(1, values.size))


def analyze_cutout_rgba(
    rgba,
    *,
    element_id: str = "",
    role: str = "primary_subject",
    semantic_label: str = "subject",
    source_alpha: bool = False,
    intentional_internal_edges: bool = False,
) -> CutoutQualityReport:
    """Measure one full-canvas RGBA cutout and return a product gate report."""
    import cv2
    import numpy as np

    values = np.asarray(rgba, dtype=np.uint8)
    if values.ndim != 3 or values.shape[2] < 4:
        raise ValueError("cutout quality requires an RGBA image")
    rgb = values[:, :, :3]
    alpha = values[:, :, 3]
    height, width = alpha.shape
    pixels = float(max(1, alpha.size))
    visible = alpha > 8
    opaque = alpha >= 247
    soft = (alpha > 8) & (alpha < 247)
    transparent = alpha <= 8
    visible_count = int(np.count_nonzero(visible))
    coverage = visible_count / pixels
    transparent_ratio = float(np.count_nonzero(transparent)) / pixels
    opaque_ratio = float(np.count_nonzero(opaque)) / pixels
    soft_ratio = float(np.count_nonzero(soft)) / pixels

    ys, xs = np.nonzero(visible)
    if len(xs):
        left, right = int(xs.min()), int(xs.max()) + 1
        top, bottom = int(ys.min()), int(ys.max()) + 1
        bbox_area_ratio = float((right - left) * (bottom - top)) / pixels
        bbox_fill_ratio = float(visible_count) / float(
            max(1, (right - left) * (bottom - top))
        )
    else:
        left = top = right = bottom = 0
        bbox_area_ratio = 0.0
        bbox_fill_ratio = 0.0

    edge_thickness = max(1, int(round(min(width, height) * 0.008)))
    edge_contact = {
        edge: _edge_ratio(visible, edge, edge_thickness)
        for edge in ("top", "right", "bottom", "left")
    }
    contacted_edges = [
        edge
        for edge, ratio in edge_contact.items()
        if ratio >= (0.10 if edge in {"top", "bottom"} else 0.16)
    ]

    boundary = np.zeros_like(visible)
    halo_ratio = 0.0
    boundary_pixel_ratio = 0.0
    low_contrast_boundary_ratio = 0.0
    largest_low_contrast_component_ratio = 0.0
    median_boundary_contrast = 0.0
    if visible_count:
        binary = np.where(visible, 255, 0).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        eroded = cv2.erode(binary, kernel, iterations=1) > 0
        boundary = visible & ~eroded
        boundary |= soft
        boundary_count = int(np.count_nonzero(boundary))
        boundary_pixel_ratio = boundary_count / pixels
        if boundary_count:
            hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
            bright_neutral = (hsv[:, :, 2] >= 218) & (hsv[:, :, 1] <= 48)
            halo_ratio = float(np.count_nonzero(boundary & bright_neutral)) / float(
                boundary_count
            )
            contrast_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (3, 3),
            )
            contrast_boundary = visible & ~(
                cv2.erode(binary, contrast_kernel, iterations=1) > 0
            )
            lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
            gradient_squared = np.zeros(alpha.shape, dtype=np.float32)
            for channel in range(3):
                gradient_x = cv2.Sobel(
                    lab[:, :, channel],
                    cv2.CV_32F,
                    1,
                    0,
                    ksize=3,
                )
                gradient_y = cv2.Sobel(
                    lab[:, :, channel],
                    cv2.CV_32F,
                    0,
                    1,
                    ksize=3,
                )
                gradient_squared += gradient_x * gradient_x + gradient_y * gradient_y
            gradient = np.sqrt(gradient_squared)
            upper_region = np.indices(alpha.shape)[0] < int(round(height * 0.65))
            upper_boundary = contrast_boundary & upper_region
            upper_values = gradient[upper_boundary]
            if upper_values.size:
                low_contrast = upper_boundary & (gradient < 30.0)
                low_contrast_boundary_ratio = float(np.count_nonzero(low_contrast)) / float(
                    upper_values.size
                )
                median_boundary_contrast = float(np.median(upper_values))
                low_component_count, _low_labels, low_stats, _low_centroids = (
                    cv2.connectedComponentsWithStats(
                        low_contrast.astype(np.uint8),
                        connectivity=8,
                    )
                )
                if low_component_count > 1:
                    largest_low_contrast_component_ratio = float(
                        max(
                            int(low_stats[index, cv2.CC_STAT_AREA])
                            for index in range(1, low_component_count)
                        )
                    ) / float(upper_values.size)

    components = 0
    small_fragment_ratio = 0.0
    if visible_count:
        labels_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
            np.where(visible, 255, 0).astype(np.uint8),
            connectivity=8,
        )
        areas = sorted(
            (int(stats[index, cv2.CC_STAT_AREA]) for index in range(1, labels_count)),
            reverse=True,
        )
        components = len(areas)
        if areas:
            small_fragment_ratio = float(sum(areas[1:])) / float(max(1, sum(areas)))

    issues: list[CutoutQualityIssue] = []
    if coverage <= 0.002:
        issues.append(CutoutQualityIssue(
            "empty_or_nearly_empty_cutout",
            "error",
            "The extracted subject contains almost no visible pixels.",
        ))
    if transparent_ratio < 0.005:
        issues.append(CutoutQualityIssue(
            "opaque_background_plate",
            "error",
            "The cutout has no meaningful transparent background.",
        ))
    if coverage > 0.92 and bbox_area_ratio > 0.96 and bbox_fill_ratio > 0.90:
        issues.append(CutoutQualityIssue(
            "foreground_covers_frame",
            "error",
            "The foreground mask covers nearly the full frame and likely retained the background.",
        ))
    connected_background_boundary = (
        low_contrast_boundary_ratio >= 0.34
        and largest_low_contrast_component_ratio >= 0.18
    )
    if connected_background_boundary and intentional_internal_edges:
        issues.append(CutoutQualityIssue(
            "intentional_internal_boundary",
            "warning",
            "This split/merged layer has low-contrast internal edges; review the group reconstruction.",
        ))
    elif connected_background_boundary:
        issues.append(CutoutQualityIssue(
            "background_connected_to_subject",
            "error",
            "The alpha boundary crosses visually continuous background regions instead of following the subject.",
        ))
    elif low_contrast_boundary_ratio >= 0.20:
        issues.append(CutoutQualityIssue(
            "weak_subject_boundary",
            "warning",
            "A substantial part of the alpha boundary has little image contrast; inspect for retained background.",
        ))
    if (
        boundary_pixel_ratio >= 0.002
        and halo_ratio >= 0.58
        and not (source_alpha and soft_ratio < 0.001)
    ):
        issues.append(CutoutQualityIssue(
            "bright_edge_spill",
            "warning",
            "A large share of the cutout boundary is bright and neutral; inspect for a white halo.",
        ))
    if len(contacted_edges) >= 3:
        issues.append(CutoutQualityIssue(
            "subject_clipped_by_source_frame",
            "warning",
            "The subject touches three or more source-frame edges and may be visibly cropped.",
        ))
    elif "top" in contacted_edges and (
        "left" in contacted_edges or "right" in contacted_edges
    ):
        issues.append(CutoutQualityIssue(
            "upper_subject_crop_risk",
            "warning",
            "The upper subject meets multiple source edges; inspect hair, headwear, and shoulders.",
        ))
    if small_fragment_ratio > 0.08:
        issues.append(CutoutQualityIssue(
            "detached_mask_fragments",
            "warning",
            "Detached foreground fragments occupy a meaningful part of the cutout.",
        ))

    blockers = [item for item in issues if item.severity == "error"]
    warnings = [item for item in issues if item.severity == "warning"]
    score = max(0.0, 100.0 - len(blockers) * 55.0 - len(warnings) * 12.0)
    accepted = not blockers
    status = "failed" if blockers else "review" if warnings else "passed"
    return CutoutQualityReport(
        element_id=str(element_id),
        accepted=accepted,
        status=status,
        score=score,
        metrics={
            "width": int(width),
            "height": int(height),
            "coverage": coverage,
            "transparent_ratio": transparent_ratio,
            "opaque_ratio": opaque_ratio,
            "soft_alpha_ratio": soft_ratio,
            "bbox": [left, top, max(0, right - left), max(0, bottom - top)],
            "bbox_area_ratio": bbox_area_ratio,
            "bbox_fill_ratio": bbox_fill_ratio,
            "edge_contact": edge_contact,
            "contacted_edges": contacted_edges,
            "boundary_pixel_ratio": boundary_pixel_ratio,
            "bright_neutral_boundary_ratio": halo_ratio,
            "low_contrast_boundary_ratio": low_contrast_boundary_ratio,
            "largest_low_contrast_boundary_component_ratio": (
                largest_low_contrast_component_ratio
            ),
            "median_boundary_contrast": median_boundary_contrast,
            "connected_component_count": components,
            "detached_fragment_ratio": small_fragment_ratio,
            "role": str(role),
            "semantic_label": str(semantic_label),
            "source_alpha": bool(source_alpha),
            "intentional_internal_edges": bool(intentional_internal_edges),
        },
        issues=issues,
    )


def evaluate_decomposition_cutout_quality(result: Any) -> dict[str, Any]:
    """Evaluate and attach the shared cutout-quality contract to a result."""
    import numpy as np
    from PIL import Image

    diagnostics = dict(getattr(result, "diagnostics", {}) or {})
    source_alpha = bool(diagnostics.get("transparent_source"))
    reports: list[CutoutQualityReport] = []
    for element in list(getattr(result, "elements", []) or []):
        if str(getattr(element, "role", "")) == "text":
            continue
        path = Path(str(getattr(element, "rgba_path", "") or ""))
        if not path.is_file():
            continue
        with Image.open(path) as opened:
            rgba = np.asarray(opened.convert("RGBA"), dtype=np.uint8)
        metadata = dict(getattr(element, "metadata", {}) or {})
        report = analyze_cutout_rgba(
            rgba,
            element_id=str(getattr(element, "id", "") or ""),
            role=str(getattr(element, "role", "") or ""),
            semantic_label=str(metadata.get("semantic_label") or "subject"),
            source_alpha=source_alpha,
            intentional_internal_edges=bool(
                metadata.get("split_from") or metadata.get("merged_from")
            ),
        )
        metadata["cutout_quality"] = report.to_dict()
        element.metadata = metadata
        reports.append(report)

    blockers = [
        {
            "element_id": report.element_id,
            **issue.to_dict(),
        }
        for report in reports
        for issue in report.blockers
    ]
    warnings = [
        {
            "element_id": report.element_id,
            **issue.to_dict(),
        }
        for report in reports
        for issue in report.warnings
    ]
    accepted = bool(reports) and not blockers
    status = "failed" if blockers else "review" if warnings else "passed"
    aggregate = {
        "schema": CUTOUT_QUALITY_SCHEMA,
        "accepted": accepted,
        "status": status,
        "requires_review": bool(warnings),
        "score": min((report.score for report in reports), default=0.0),
        "element_count": len(reports),
        "blockers": blockers,
        "warnings": warnings,
        "elements": [report.to_dict() for report in reports],
    }
    diagnostics["cutout_quality"] = aggregate
    diagnostics["cutout_quality_accepted"] = accepted
    result.diagnostics = diagnostics
    return aggregate


def require_accepted_cutout_quality(
    result: Any,
    *,
    allow_override: bool = False,
) -> dict[str, Any]:
    report = evaluate_decomposition_cutout_quality(result)
    if not report["accepted"] and not allow_override:
        codes = [
            str(item.get("code") or "quality_failure")
            for item in report.get("blockers", [])
        ]
        raise ValueError(
            "Cutout quality gate rejected this decomposition: "
            + ", ".join(dict.fromkeys(codes))
            + ". Refine the mask or explicitly approve a quality override."
        )
    return report


__all__ = [
    "CUTOUT_QUALITY_SCHEMA",
    "CutoutQualityIssue",
    "CutoutQualityReport",
    "analyze_cutout_rgba",
    "evaluate_decomposition_cutout_quality",
    "require_accepted_cutout_quality",
]

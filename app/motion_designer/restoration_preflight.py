"""Background-restoration exposure gate for layered camera moves."""
from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any


RESTORATION_PREFLIGHT_SCHEMA = "tigerstudio.motion.restoration_preflight.v1"


def _load_binary_mask(path: str | Path):
    import cv2
    import numpy as np

    source = Path(path).expanduser().resolve(strict=True)
    image = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"unable to read restoration mask: {source}")
    if image.ndim == 3:
        image = image[:, :, 3] if image.shape[2] >= 4 else cv2.cvtColor(
            image[:, :, :3], cv2.COLOR_BGR2GRAY
        )
    return np.where(image > 0, 1, 0).astype(np.uint8)


def _risk_heatmap(mask, *, confidence: float, grid_size: int) -> list[list[float]]:
    import cv2
    import numpy as np

    height, width = mask.shape[:2]
    reduced = cv2.resize(
        mask.astype(np.float32),
        (grid_size, grid_size),
        interpolation=cv2.INTER_AREA,
    )
    uncertainty = 1.0 - confidence
    risk = np.clip(reduced * (0.35 + uncertainty * 0.65), 0.0, 1.0)
    return [[round(float(value), 4) for value in row] for row in risk]


def _assess_mask(
    mask,
    *,
    mask_path: str,
    confidence: float,
    max_camera_travel_ratio: float,
    camera_dx_ratio: float = 0.0,
    camera_dy_ratio: float = 0.0,
    grid_size: int = 8,
) -> dict[str, Any]:
    """Assess restored-pixel exposure before a layered camera move."""
    if not 2 <= int(grid_size) <= 32:
        raise ValueError("grid_size must be between 2 and 32")
    confidence = max(0.0, min(1.0, float(confidence)))
    allowed = max(0.0, float(max_camera_travel_ratio))
    dx = float(camera_dx_ratio)
    dy = float(camera_dy_ratio)
    requested = math.hypot(dx, dy)
    coverage = float(mask.mean())
    heatmap = _risk_heatmap(mask, confidence=confidence, grid_size=int(grid_size))
    peak_risk = max((max(row) for row in heatmap), default=0.0)
    travel_excess = max(0.0, requested - allowed)

    issues: list[dict[str, Any]] = []
    if requested > allowed + 1e-9:
        issues.append({
            "code": "camera_travel_exceeds_restoration_limit",
            "severity": "error",
            "message": "The planned camera move can expose unreliable restored pixels.",
            "action": {
                "action_id": "motion.ai.background.replace",
                "params": {"reason": "camera_travel_exposure"},
            },
        })
    if confidence < 0.45 and coverage >= 0.08:
        issues.append({
            "code": "restoration_confidence_too_low",
            "severity": "error",
            "message": "The restored area needs a reviewed clean plate before camera travel.",
            "action": {
                "action_id": "motion.ai.background.replace",
                "params": {"reason": "low_restoration_confidence"},
            },
        })
    elif confidence < 0.65 or peak_risk >= 0.72:
        issues.append({
            "code": "restoration_visual_review_required",
            "severity": "warning",
            "message": "Inspect the highlighted restoration cells before export.",
            "action": {
                "action_id": "motion.ai.layer.readiness.inspect",
                "params": {},
            },
        })

    severities = {str(item["severity"]) for item in issues}
    status = "blocked" if "error" in severities else "review" if issues else "safe"
    safe_scale = 1.0 if requested <= allowed or requested <= 1e-12 else allowed / requested
    safe_dx = dx * safe_scale
    safe_dy = dy * safe_scale
    return {
        "schema": RESTORATION_PREFLIGHT_SCHEMA,
        "status": status,
        "can_render": status != "blocked",
        "restoration": {
            "mask_path": mask_path,
            "confidence": confidence,
            "coverage": round(coverage, 6),
            "heatmap_grid_size": int(grid_size),
            "risk_heatmap": heatmap,
            "peak_risk": round(peak_risk, 4),
        },
        "camera": {
            "requested": {"dx_ratio": dx, "dy_ratio": dy, "travel_ratio": requested},
            "allowed_travel_ratio": allowed,
            "travel_excess_ratio": travel_excess,
            "safe_path": {
                "dx_ratio": round(safe_dx, 6),
                "dy_ratio": round(safe_dy, 6),
                "travel_ratio": round(math.hypot(safe_dx, safe_dy), 6),
                "was_clamped": safe_scale < 1.0,
            },
        },
        "issues": issues,
    }


def assess_restoration_preflight(
    *,
    restoration_mask_path: str | Path,
    confidence: float,
    max_camera_travel_ratio: float,
    camera_dx_ratio: float = 0.0,
    camera_dy_ratio: float = 0.0,
    grid_size: int = 8,
) -> dict[str, Any]:
    source = Path(restoration_mask_path).expanduser().resolve(strict=True)
    return _assess_mask(
        _load_binary_mask(source),
        mask_path=str(source),
        confidence=confidence,
        max_camera_travel_ratio=max_camera_travel_ratio,
        camera_dx_ratio=camera_dx_ratio,
        camera_dy_ratio=camera_dy_ratio,
        grid_size=grid_size,
    )


def assess_decomposition_restoration_preflight(
    decomposition: Any,
    *,
    camera_dx_ratio: float = 0.0,
    camera_dy_ratio: float = 0.0,
    grid_size: int = 8,
) -> dict[str, Any]:
    """Run restoration preflight directly from a decomposition result."""
    import cv2
    import numpy as np

    diagnostics = dict(getattr(decomposition, "diagnostics", {}) or {})
    inpaint = diagnostics.get("inpaint")
    inpaint = dict(inpaint) if isinstance(inpaint, Mapping) else {}
    masks = []
    sources: list[str] = []
    for element in list(getattr(decomposition, "elements", []) or []):
        path = str(getattr(element, "mask_path", "") or "")
        if not path:
            continue
        item = _load_binary_mask(path)
        if masks and item.shape != masks[0].shape:
            item = cv2.resize(
                item,
                (masks[0].shape[1], masks[0].shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )
        masks.append(item)
        sources.append(str(Path(path).expanduser().resolve()))
    if not masks:
        raise ValueError("decomposition has no restoration masks")
    union = np.maximum.reduce(masks)
    report = _assess_mask(
        union,
        mask_path=";".join(sources),
        confidence=float(inpaint.get("confidence", 0.0) or 0.0),
        max_camera_travel_ratio=float(
            inpaint.get(
                "max_camera_travel_ratio",
                diagnostics.get("max_camera_travel_ratio", 0.0),
            )
            or 0.0
        ),
        camera_dx_ratio=camera_dx_ratio,
        camera_dy_ratio=camera_dy_ratio,
        grid_size=grid_size,
    )
    report["restoration"]["mask_sources"] = sources
    report["restoration"]["provider"] = str(inpaint.get("provider") or "unknown")
    return report


__all__ = [
    "RESTORATION_PREFLIGHT_SCHEMA",
    "assess_decomposition_restoration_preflight",
    "assess_restoration_preflight",
]

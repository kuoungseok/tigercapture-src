"""Production readiness gate for editable layered-image motion.

This module composes the existing cutout, reconstruction, inpaint, and
segmentation capability reports.  It does not perform segmentation itself;
its job is to prevent a technically generated decomposition from being
presented as production-ready without an explicit repair or fallback plan.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


LAYER_READINESS_SCHEMA = "tigerstudio.motion.layer_readiness.v1"


def _issue(
    code: str,
    severity: str,
    message: str,
    action_id: str,
    **params: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "repair": {
            "action_id": action_id,
            "params": params,
        },
    }


def _provider_is_legacy(segmentation: Mapping[str, Any]) -> bool:
    provider = str(segmentation.get("provider") or "").casefold()
    diagnostics = segmentation.get("diagnostics")
    return bool(
        (isinstance(diagnostics, Mapping) and diagnostics.get("legacy_fallback"))
        or provider in {"grabcut_border_seed", "border_color_distance", "local_basic"}
    )


def assess_layer_motion_readiness(
    result: Any,
    *,
    setup_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a machine-readable production gate and ordered repair plan."""
    from .cutout_quality import evaluate_decomposition_cutout_quality
    from .image_motion_validation import validate_decomposition_result

    diagnostics = dict(getattr(result, "diagnostics", {}) or {})
    cutout = evaluate_decomposition_cutout_quality(result)
    validation = validate_decomposition_result(result).to_dict()
    diagnostics = dict(getattr(result, "diagnostics", {}) or {})
    segmentation = diagnostics.get("segmentation")
    segmentation = dict(segmentation) if isinstance(segmentation, Mapping) else {}
    inpaint = diagnostics.get("inpaint")
    inpaint = dict(inpaint) if isinstance(inpaint, Mapping) else {}
    source_alpha = bool(diagnostics.get("transparent_source"))

    if setup_status is None:
        try:
            from .segmentation_setup import segmentation_setup_status

            setup_status = segmentation_setup_status()
        except Exception as exc:  # setup probing must not break project loading
            setup_status = {
                "available": False,
                "automatic_cutout_ready": False,
                "assisted_segmentation_ready": False,
                "probe_error": str(exc),
            }
    setup = dict(setup_status or {})
    issues: list[dict[str, Any]] = []

    for row in cutout.get("blockers", []):
        if isinstance(row, Mapping):
            issues.append(_issue(
                str(row.get("code") or "cutout_rejected"),
                "error",
                str(row.get("message") or "The foreground cutout was rejected."),
                "motion.ai.layer.mask.refine",
                element_id=str(row.get("element_id") or ""),
            ))
    for row in cutout.get("warnings", []):
        if isinstance(row, Mapping):
            issues.append(_issue(
                str(row.get("code") or "cutout_review"),
                "warning",
                str(row.get("message") or "The foreground cutout needs review."),
                "motion.ai.layer.mask.replace",
                element_id=str(row.get("element_id") or ""),
            ))

    for message in validation.get("errors", []):
        issues.append(_issue(
            "decomposition_integrity_failed",
            "error",
            str(message),
            "motion.ai.integrity.validate",
        ))
    for message in validation.get("warnings", []):
        issues.append(_issue(
            "reconstruction_review_required",
            "warning",
            str(message),
            "motion.ai.integrity.validate",
        ))

    legacy = _provider_is_legacy(segmentation)
    if legacy and not source_alpha:
        issues.append(_issue(
            "legacy_segmentation_fallback",
            "warning",
            "Legacy local segmentation was used; inspect the matte before independent motion.",
            "motion.ai.segmentation.setup.plan",
        ))
    if not source_alpha and not bool(setup.get("automatic_cutout_ready")):
        issues.append(_issue(
            "automatic_cutout_provider_missing",
            "info",
            "AI-quality automatic cutout is not installed; the local fallback remains available.",
            "motion.ai.segmentation.setup.plan",
        ))

    inpaint_confidence = float(inpaint.get("confidence", 0.0) or 0.0)
    inpaint_coverage = float(inpaint.get("coverage", 0.0) or 0.0)
    if not source_alpha and inpaint_confidence < 0.45:
        issues.append(_issue(
            "background_restoration_low_confidence",
            "error" if inpaint_coverage >= 0.18 else "warning",
            "The reconstructed background is not reliable enough for the planned camera travel.",
            "motion.ai.background.replace",
        ))
    elif not source_alpha and inpaint_confidence < 0.65:
        issues.append(_issue(
            "background_restoration_review_required",
            "warning",
            "The reconstructed background needs visual review before a wide camera move.",
            "motion.ai.background.replace",
        ))

    visual_elements = [
        item for item in list(getattr(result, "elements", []) or [])
        if str(getattr(item, "role", "")) != "text"
    ]
    if not visual_elements:
        issues.append(_issue(
            "no_editable_visual_layers",
            "error",
            "No stable editable visual layer was produced.",
            "motion.ai.reference.decompose",
        ))

    severities = {str(row.get("severity")) for row in issues}
    if "error" in severities:
        status = "repair_required"
    elif "warning" in severities:
        status = "review"
    else:
        status = "ready"
    if not visual_elements:
        status = "fallback_only"

    semantic_confidence = float(
        segmentation.get("confidence", diagnostics.get("segmentation_confidence", 0.0))
        or 0.0
    )
    reconstruction = dict(validation.get("metrics") or {})
    reconstruction_score = 100.0
    if reconstruction.get("available"):
        mae = float(reconstruction.get("mean_abs_error", 0.0) or 0.0)
        ssim = float(reconstruction.get("global_ssim", 1.0) or 1.0)
        reconstruction_score = max(0.0, min(100.0, ssim * 100.0 - max(0.0, mae - 3.0) * 2.0))
    overall_score = min(
        float(cutout.get("score", 0.0) or 0.0),
        reconstruction_score,
        100.0 if source_alpha else max(0.0, inpaint_confidence * 100.0),
    )

    ordered_repairs: list[dict[str, Any]] = []
    seen_actions: set[str] = set()
    for row in issues:
        repair = dict(row.get("repair") or {})
        action_id = str(repair.get("action_id") or "")
        if action_id and action_id not in seen_actions:
            seen_actions.add(action_id)
            ordered_repairs.append(repair)
    if status in {"repair_required", "fallback_only"}:
        ordered_repairs.append({
            "action_id": "motion.ai.choreography.plan",
            "params": {"variant": "clean", "single_layer_fallback": True},
            "condition": "Use only after the user accepts reduced editability.",
        })

    report = {
        "schema": LAYER_READINESS_SCHEMA,
        "status": status,
        "ready": status == "ready",
        "requires_review": status == "review",
        "can_compile": status in {"ready", "review"},
        "score": round(overall_score, 3),
        "scores": {
            "cutout": float(cutout.get("score", 0.0) or 0.0),
            "reconstruction": round(reconstruction_score, 3),
            "restoration": 100.0 if source_alpha else round(inpaint_confidence * 100.0, 3),
            "semantic_confidence": round(semantic_confidence * 100.0, 3),
        },
        "provider": {
            "selected": str(segmentation.get("provider") or diagnostics.get("segmentation_backend") or "unknown"),
            "legacy_fallback": legacy,
            "automatic_cutout_ready": bool(setup.get("automatic_cutout_ready")),
            "assisted_segmentation_ready": bool(setup.get("assisted_segmentation_ready")),
        },
        "restoration": {
            "provider": str(inpaint.get("provider") or "unknown"),
            "confidence": inpaint_confidence,
            "coverage": inpaint_coverage,
            "max_camera_travel_ratio": float(inpaint.get("max_camera_travel_ratio", 0.0) or 0.0),
        },
        "issues": issues,
        "repair_plan": ordered_repairs,
        "fallback": {
            "available": True,
            "mode": "single_layer_motion",
            "preserves_source_pixels": True,
            "editable_layer_motion": False,
        },
        "evidence": {
            "cutout_quality": cutout,
            "integrity": validation,
        },
    }
    diagnostics["layer_readiness"] = report
    result.diagnostics = diagnostics
    return report


__all__ = ["LAYER_READINESS_SCHEMA", "assess_layer_motion_readiness"]

"""Machine-readable visual reference acceptance for Motion Designer frames."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np
from PIL import Image


REFERENCE_GATE_SCHEMA = "tigerstudio.motion.reference_gate.v1"


def _rgba(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        array = value
    else:
        array = np.asarray(Image.open(Path(value)).convert("RGBA"), dtype=np.uint8)
    if array.ndim != 3 or array.shape[2] != 4:
        raise ValueError("reference gate requires an RGBA image")
    return np.asarray(array, dtype=np.uint8)


def _global_ssim(left: np.ndarray, right: np.ndarray) -> float:
    x = left[..., :3].astype(np.float64).mean(axis=2)
    y = right[..., :3].astype(np.float64).mean(axis=2)
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    mean_x, mean_y = float(x.mean()), float(y.mean())
    variance_x, variance_y = float(x.var()), float(y.var())
    covariance = float(((x - mean_x) * (y - mean_y)).mean())
    numerator = (2.0 * mean_x * mean_y + c1) * (2.0 * covariance + c2)
    denominator = (mean_x * mean_x + mean_y * mean_y + c1) * (variance_x + variance_y + c2)
    return 1.0 if denominator <= 1e-12 else max(-1.0, min(1.0, numerator / denominator))


def compare_reference_frame(
    actual: Any,
    reference: Any,
    *,
    reference_source: str = "",
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    actual_rgba = _rgba(actual)
    reference_rgba = _rgba(reference)
    limits = {
        "mean_abs_error": 2.0,
        "max_abs_error": 32,
        "alpha_mismatch_ratio": 0.001,
        "minimum_ssim": 0.98,
        **dict(thresholds or {}),
    }
    if actual_rgba.shape != reference_rgba.shape:
        return {
            "schema": REFERENCE_GATE_SCHEMA,
            "ok": False,
            "status": "dimension_mismatch",
            "actual_shape": list(actual_rgba.shape),
            "reference_shape": list(reference_rgba.shape),
            "reference_source": str(reference_source),
            "thresholds": limits,
        }
    difference = np.abs(actual_rgba.astype(np.int16) - reference_rgba.astype(np.int16))
    metrics = {
        "mean_abs_error": float(difference.mean()),
        "max_abs_error": int(difference.max(initial=0)),
        "alpha_mismatch_ratio": float(np.count_nonzero(difference[..., 3]) / difference[..., 3].size),
        "global_ssim": float(_global_ssim(actual_rgba, reference_rgba)),
    }
    checks = {
        "mean_abs_error": metrics["mean_abs_error"] <= float(limits["mean_abs_error"]),
        "max_abs_error": metrics["max_abs_error"] <= int(limits["max_abs_error"]),
        "alpha_mismatch_ratio": metrics["alpha_mismatch_ratio"] <= float(limits["alpha_mismatch_ratio"]),
        "minimum_ssim": metrics["global_ssim"] >= float(limits["minimum_ssim"]),
    }
    return {
        "schema": REFERENCE_GATE_SCHEMA,
        "ok": all(checks.values()),
        "status": "pass" if all(checks.values()) else "mismatch",
        "reference_source": str(reference_source),
        "metrics": metrics,
        "thresholds": limits,
        "checks": checks,
        "dimensions": [int(actual_rgba.shape[1]), int(actual_rgba.shape[0])],
    }


__all__ = ["REFERENCE_GATE_SCHEMA", "compare_reference_frame"]

"""Qt-free audio accuracy helpers used by meters and QA.

These are intentionally small reference calculations. They are not a complete
Fairlight replacement, but they give tests and diagnostics stable numbers for
LUFS-like level, true peak, stereo correlation, and target compliance.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np


def _as_float_pcm(pcm: Any) -> np.ndarray:
    arr = np.asarray(pcm, dtype=np.float32)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    if arr.ndim == 1:
        arr = arr[:, None]
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)


def rms_level(pcm: Any) -> float:
    arr = _as_float_pcm(pcm)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(arr, dtype=np.float32)) + 1e-12))


def integrated_lufs_approx(pcm: Any) -> float:
    """Simplified BS.1770-style loudness used for fast UI/QA diagnostics."""
    rms = max(rms_level(pcm), 1e-12)
    return float(20.0 * math.log10(rms) - 0.691)


def true_peak_dbfs(pcm: Any) -> float:
    arr = _as_float_pcm(pcm)
    if arr.size == 0:
        return -120.0
    peak = float(np.max(np.abs(arr)))
    if peak <= 1e-12:
        return -120.0
    return float(20.0 * math.log10(peak))


def stereo_correlation(pcm: Any) -> float:
    arr = _as_float_pcm(pcm)
    if arr.shape[1] < 2 or arr.shape[0] < 2:
        return 1.0
    left = arr[:, 0].astype(np.float64)
    right = arr[:, 1].astype(np.float64)
    left -= left.mean()
    right -= right.mean()
    denom = float(np.sqrt(np.sum(left * left) * np.sum(right * right)))
    if denom <= 1e-12:
        return 1.0
    return float(np.clip(np.sum(left * right) / denom, -1.0, 1.0))


def audio_signal_diagnostics(
    pcm: Any,
    *,
    target_lufs: float = -14.0,
    true_peak_limit_db: float = -1.0,
    tolerance_lufs: float = 1.0,
) -> dict[str, Any]:
    lufs = integrated_lufs_approx(pcm)
    peak = true_peak_dbfs(pcm)
    corr = stereo_correlation(pcm)
    warnings: list[str] = []
    if abs(lufs - float(target_lufs)) > float(tolerance_lufs):
        warnings.append("loudness outside target tolerance")
    if peak > float(true_peak_limit_db):
        warnings.append("true peak exceeds limit")
    if corr < -0.25:
        warnings.append("negative stereo correlation")
    return {
        "ok": not warnings,
        "integrated_lufs": lufs,
        "target_lufs": float(target_lufs),
        "true_peak_dbfs": peak,
        "true_peak_limit_db": float(true_peak_limit_db),
        "stereo_correlation": corr,
        "warnings": warnings,
    }

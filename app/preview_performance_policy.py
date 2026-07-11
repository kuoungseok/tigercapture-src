"""Preview decode policy for high-resolution or high-FPS sources.

This module is intentionally UI-free.  It answers a narrow question for the
preview engine: should this source be decoded at full size, downscaled for
monitoring, or routed through the automatic decoder benchmark/proxy path?
Final export must keep using the original media.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


PREVIEW_PERFORMANCE_POLICY_SCHEMA = "tigercapture.preview.performance_policy.v1"
PREVIEW_QUALITY_MODES = frozenset({"auto", "performance", "quality"})


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _default_preview_height(width: int, height: int, fps: float) -> int:
    pixels = max(0, int(width)) * max(0, int(height))
    high_fps = float(fps or 0.0) >= 55.0
    if pixels >= 7680 * 4320 or height >= 4320:
        return 540
    if pixels >= 3840 * 2160 or height >= 2160:
        return 540 if high_fps else 720
    if high_fps and (height >= 1440 or pixels >= 2560 * 1440):
        return 540
    if high_fps and height > 720:
        return 720
    if height > 1080:
        return 720
    return 0


def normalize_preview_quality_mode(mode: Any) -> str:
    value = str(mode or "auto").strip().casefold()
    if value in {"perf", "speed", "fast", "low"}:
        return "performance"
    if value in {"best", "full", "original", "high"}:
        return "quality"
    if value in PREVIEW_QUALITY_MODES:
        return value
    return "auto"


def preview_height_for_quality_mode(
    *,
    mode: Any = "auto",
    width: int = 0,
    height: int = 0,
    fps: float = 0.0,
    requested_preview_height: int | None = None,
) -> int:
    """Return a monitoring decode height for the preview quality mode.

    ``quality`` means "show original preview frames"; export is always original
    regardless of this setting. ``performance`` intentionally caps monitoring
    earlier so decode, filter, and texture-upload stages stay responsive.
    """
    if requested_preview_height is not None:
        return max(0, int(requested_preview_height))
    resolved = normalize_preview_quality_mode(mode)
    h = max(0, _int(height, 0))
    if resolved == "quality":
        return 0
    if resolved == "performance":
        if h > 720:
            return 540
        if h > 0:
            return min(h, 720)
        return 540
    return _default_preview_height(width, height, fps)


def preview_performance_policy_from_metadata(
    *,
    width: int = 0,
    height: int = 0,
    fps: float = 0.0,
    codec: str = "",
    path: str | Path = "",
    requested_preview_height: int | None = None,
    quality_mode: str = "auto",
) -> dict[str, Any]:
    """Return a deterministic preview performance policy from media metadata."""
    w = max(0, _int(width, 0))
    h = max(0, _int(height, 0))
    rate = max(0.0, _float(fps, 0.0))
    pixels = w * h
    high_resolution = pixels >= 3840 * 2160 or h >= 2160 or w >= 3840
    high_fps = rate >= 55.0
    qhd_plus = pixels >= 2560 * 1440 or h >= 1440
    heavy_codec = str(codec or "").strip().casefold() in {"av1", "hevc", "h265", "vp9"}
    resolved_quality_mode = normalize_preview_quality_mode(quality_mode)
    preview_height = preview_height_for_quality_mode(
        mode=resolved_quality_mode,
        width=w,
        height=h,
        fps=rate,
        requested_preview_height=requested_preview_height,
    )
    needs_monitoring_scale = preview_height > 0 and h > preview_height
    decoder_auto = bool(
        resolved_quality_mode != "quality"
        and (
            high_resolution
            or (high_fps and qhd_plus)
            or (heavy_codec and needs_monitoring_scale)
        )
    )
    needs_proxy = bool(high_resolution and high_fps) or pixels >= 7680 * 4320
    reasons: list[str] = []
    if high_resolution:
        reasons.append("high_resolution")
    if high_fps:
        reasons.append("high_fps")
    if heavy_codec:
        reasons.append(f"heavy_codec:{heavy_codec}")
    if needs_monitoring_scale:
        reasons.append(f"monitoring_scale:{preview_height}p")
    if needs_proxy:
        reasons.append("proxy_recommended")
    return {
        "schema": PREVIEW_PERFORMANCE_POLICY_SCHEMA,
        "path": str(path or ""),
        "width": w,
        "height": h,
        "fps": rate,
        "codec": str(codec or ""),
        "pixels": pixels,
        "quality_mode": resolved_quality_mode,
        "preview_height": preview_height,
        "decoder_auto": decoder_auto,
        "needs_monitoring_scale": needs_monitoring_scale,
        "needs_proxy": needs_proxy,
        "frame_drop_allowed": bool(resolved_quality_mode != "quality" and (high_resolution or high_fps)),
        "export_uses_original": True,
        "reasons": reasons,
    }


def preview_performance_policy_from_probe(
    probe: Mapping[str, Any] | None,
    *,
    path: str | Path = "",
    requested_preview_height: int | None = None,
    quality_mode: str = "auto",
) -> dict[str, Any]:
    """Build a policy from a generic probe mapping."""
    data = probe if isinstance(probe, Mapping) else {}
    return preview_performance_policy_from_metadata(
        width=_int(data.get("width") or data.get("w"), 0),
        height=_int(data.get("height") or data.get("h"), 0),
        fps=_float(data.get("fps") or data.get("frame_rate"), 0.0),
        codec=str(data.get("codec") or data.get("video_codec") or ""),
        path=path or str(data.get("path") or ""),
        requested_preview_height=requested_preview_height,
        quality_mode=quality_mode,
    )


__all__ = [
    "PREVIEW_PERFORMANCE_POLICY_SCHEMA",
    "PREVIEW_QUALITY_MODES",
    "normalize_preview_quality_mode",
    "preview_height_for_quality_mode",
    "preview_performance_policy_from_metadata",
    "preview_performance_policy_from_probe",
]

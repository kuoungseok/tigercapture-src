"""Depth refinement helpers for video/AR compositing.

The estimator output is useful as a raw relative depth signal, but it is too
soft/noisy for AR occlusion or for a viewer-facing "depth matte" display. This
module keeps the runtime dependency footprint small while adding the important
post stages:

- robust normalization with invalid edge-band masking
- RGB-guided edge-aware smoothing for compositing
- optional layered/quantized matte for diagnostic viewing
"""
from __future__ import annotations

from typing import Any, Mapping

from app.depth.providers import frame_to_rgb_array, resize_depth_to_frame


DEPTH_REFINEMENT_SCHEMA = "tigerstudio.depth.refinement.v1"


def refine_depth_for_compositing(
    depth_frame: Any,
    reference_frame: Any,
    *,
    foreground_mask: Any = None,
    settings: Mapping[str, Any] | None = None,
    return_diagnostics: bool = False,
):
    """Return a normalized, edge-aware depth map for occlusion/compositing.

    The returned map keeps the project convention used by AR/PBR:
    ``0 = near`` and ``1 = far``. The refinement is deliberately conservative:
    it smooths inside visual regions while avoiding strong RGB/depth edges, and
    it leaves invalid letterbox-like bands out of the normalization statistics.
    """
    import numpy as np

    settings = settings or {}
    rgb = frame_to_rgb_array(reference_frame)
    h, w = rgb.shape[:2]
    raw = resize_depth_to_frame(depth_frame, w, h)
    invalid_mask, invalid_diag = build_depth_invalid_mask(raw, rgb, settings=settings)
    depth, normalize_diag = robust_normalize_depth(raw, valid_mask=~invalid_mask, settings=settings)

    smooth_radius = _setting_int(settings, "edge_smooth_radius_px", 3, 0, 8)
    smooth_iterations = _setting_int(settings, "edge_smooth_iterations", 2, 0, 6)
    edge_strength = _setting_float(settings, "edge_strength", 18.0, 0.0, 80.0)
    depth_sigma = _setting_float(settings, "depth_sigma", 0.075, 0.005, 0.35)
    if smooth_radius > 0 and smooth_iterations > 0:
        depth = edge_aware_smooth_depth(
            depth,
            rgb,
            valid_mask=~invalid_mask,
            radius=smooth_radius,
            iterations=smooth_iterations,
            edge_strength=edge_strength,
            depth_sigma=depth_sigma,
        )

    if foreground_mask is not None:
        mask = _resize_mask(foreground_mask, w, h)
        # Pull foreground slightly forward so hands/face/object boundaries win
        # occlusion tests instead of flickering around equal depth values.
        foreground_bias = _setting_float(settings, "foreground_bias", 0.035, 0.0, 0.2)
        depth = np.where(mask > 0.5, np.maximum(0.0, depth - foreground_bias), depth)

    depth = np.where(invalid_mask, raw, depth)
    out = np.clip(depth, 0.0, 1.0).astype(np.float32)
    diagnostics = {
        "schema": DEPTH_REFINEMENT_SCHEMA,
        "ok": True,
        "mode": "edge_aware_compositing_depth",
        "width": int(w),
        "height": int(h),
        "edge_smooth_radius_px": int(smooth_radius),
        "edge_smooth_iterations": int(smooth_iterations),
        "edge_strength": float(edge_strength),
        "depth_sigma": float(depth_sigma),
        "invalid_mask": invalid_diag,
        "normalization": normalize_diag,
        "output_range": [float(np.nanmin(out)), float(np.nanmax(out))],
    }
    if return_diagnostics:
        return out, diagnostics
    return out


def layered_depth_matte_for_viewer(
    depth_frame: Any,
    reference_frame: Any | None = None,
    *,
    settings: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Return a viewer-friendly layered depth matte.

    This is intentionally separate from the occlusion depth. The layered matte
    is designed for inspection: large areas are flattened into stable depth
    bands while image/depth edges stay readable.
    """
    import numpy as np

    settings = settings or {}
    if reference_frame is not None:
        rgb = frame_to_rgb_array(reference_frame)
        h, w = rgb.shape[:2]
    else:
        raw_arr = np.asarray(depth_frame)
        if raw_arr.ndim < 2:
            raise ValueError("depth_frame must be a 2D depth-like frame")
        h, w = int(raw_arr.shape[0]), int(raw_arr.shape[1])
        rgb = None

    raw = resize_depth_to_frame(depth_frame, w, h)
    viewer_settings = dict(settings)
    # Viewer matte is a diagnostic object/readability view. A black studio
    # background around a subject is valid scene content, not an encoded
    # letterbox band, so keep only the conservative RGB letterbox detector here.
    viewer_settings.setdefault("invalid_uniform_edge_scan", False)
    invalid_mask, invalid_diag = build_depth_invalid_mask(raw, rgb, settings=viewer_settings)
    depth, normalize_diag = robust_normalize_depth(raw, valid_mask=~invalid_mask, settings=settings)
    if rgb is not None:
        depth = edge_aware_smooth_depth(
            depth,
            rgb,
            valid_mask=~invalid_mask,
            radius=_setting_int(settings, "viewer_smooth_radius_px", 4, 0, 10),
            iterations=_setting_int(settings, "viewer_smooth_iterations", 2, 0, 6),
            edge_strength=_setting_float(settings, "viewer_edge_strength", 24.0, 0.0, 100.0),
            depth_sigma=_setting_float(settings, "viewer_depth_sigma", 0.09, 0.005, 0.4),
        )
    foreground_diag = {"applied": False, "reason": "reference_frame_unavailable"}
    if rgb is not None and _setting_bool(settings, "viewer_foreground_prior", True):
        prior_depth, foreground_diag = _dark_background_foreground_depth_prior(
            depth,
            rgb,
            valid_mask=~invalid_mask,
            settings=settings,
        )
        if prior_depth is not None:
            depth = prior_depth
    layered = quantize_depth_layers(
        depth,
        valid_mask=~invalid_mask,
        layer_count=_setting_int(settings, "viewer_layer_count", 18, 4, 64),
        mix=_setting_float(settings, "viewer_layer_mix", 0.82, 0.0, 1.0),
    )
    if rgb is not None:
        layered = edge_aware_smooth_depth(
            layered,
            rgb,
            valid_mask=~invalid_mask,
            radius=_setting_int(settings, "viewer_layer_smooth_radius_px", 2, 0, 6),
            iterations=1,
            edge_strength=_setting_float(settings, "viewer_layer_edge_strength", 30.0, 0.0, 120.0),
            depth_sigma=_setting_float(settings, "viewer_layer_depth_sigma", 0.06, 0.005, 0.3),
        )
    layered = np.where(invalid_mask, raw, layered)
    out = np.clip(layered, 0.0, 1.0).astype(np.float32)
    diagnostics = {
        "schema": DEPTH_REFINEMENT_SCHEMA,
        "ok": True,
        "mode": "layered_depth_matte",
        "width": int(w),
        "height": int(h),
        "layer_count": _setting_int(settings, "viewer_layer_count", 18, 4, 64),
        "invalid_mask": invalid_diag,
        "normalization": normalize_diag,
        "output_range": [float(np.nanmin(out)), float(np.nanmax(out))],
        "reference_guided": bool(rgb is not None),
        "foreground_prior": foreground_diag,
    }
    return out, diagnostics


def robust_normalize_depth(
    depth_frame: Any,
    *,
    valid_mask: Any | None = None,
    settings: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    import numpy as np

    settings = settings or {}
    arr = np.asarray(depth_frame, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    if arr.ndim != 2:
        raise ValueError("depth_frame must be 2D")
    arr = np.nan_to_num(arr, nan=1.0, posinf=1.0, neginf=0.0)
    valid = np.isfinite(arr)
    if valid_mask is not None:
        mask = np.asarray(valid_mask, dtype=bool)
        if mask.shape == arr.shape:
            valid &= mask
    values = arr[valid]
    if values.size <= 0:
        return np.clip(arr, 0.0, 1.0).astype(np.float32), {
            "ok": False,
            "reason": "no_valid_depth_pixels",
            "low": 0.0,
            "high": 1.0,
        }
    low_pct = _setting_float(settings, "normalize_low_percentile", 1.0, 0.0, 20.0)
    high_pct = _setting_float(settings, "normalize_high_percentile", 99.0, 80.0, 100.0)
    lo = float(np.percentile(values, low_pct))
    hi = float(np.percentile(values, high_pct))
    if hi - lo < 1.0e-5:
        lo = float(np.min(values))
        hi = float(np.max(values))
    if hi - lo < 1.0e-5:
        out = np.zeros_like(arr, dtype=np.float32)
    else:
        out = (arr - lo) / (hi - lo)
    out = np.clip(out, 0.0, 1.0).astype(np.float32)
    if _setting_bool(settings, "invert_depth", False):
        out = 1.0 - out
    return out, {
        "ok": True,
        "low": float(lo),
        "high": float(hi),
        "low_percentile": float(low_pct),
        "high_percentile": float(high_pct),
        "valid_pixel_count": int(values.size),
    }


def build_depth_invalid_mask(
    depth_frame: Any,
    reference_rgb: Any | None = None,
    *,
    settings: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Detect obvious letterbox/border bands that should not steer depth."""
    import numpy as np

    settings = settings or {}
    depth = np.asarray(depth_frame, dtype=np.float32)
    if depth.ndim == 3:
        depth = depth[:, :, 0]
    h, w = depth.shape[:2]
    invalid = ~np.isfinite(depth)

    edge_scan_fraction = _setting_float(settings, "invalid_edge_scan_fraction", 0.18, 0.0, 0.45)
    uniform_std = _setting_float(settings, "invalid_uniform_std", 0.012, 0.0, 0.08)
    extreme_low = _setting_float(settings, "invalid_extreme_low", 0.015, 0.0, 0.25)
    extreme_high = _setting_float(settings, "invalid_extreme_high", 0.985, 0.75, 1.0)

    depth_candidate = _normalize_for_invalid_scan(depth)
    uniform_edge_scan = _setting_bool(settings, "invalid_uniform_edge_scan", True)
    row_sources = [depth_candidate] if uniform_edge_scan else []
    col_sources = [depth_candidate] if uniform_edge_scan else []
    video_letterbox = None
    video_bands = {"top": 0, "bottom": 0, "left": 0, "right": 0}
    if reference_rgb is not None:
        try:
            rgb_u8 = frame_to_rgb_array(reference_rgb)
            if rgb_u8.shape[:2] != depth_candidate.shape:
                from PIL import Image

                rgb_u8 = np.asarray(
                    Image.fromarray(rgb_u8.astype(np.uint8), "RGB").resize(
                        (w, h),
                        Image.Resampling.BILINEAR,
                    ),
                    dtype=np.uint8,
                )
            if _setting_bool(settings, "detect_video_letterbox", True):
                from app.video_letterbox import detect_letterbox_bands, letterbox_mask_from_detection

                video_letterbox = detect_letterbox_bands(rgb_u8, settings=settings)
                if bool(video_letterbox.get("ok")):
                    invalid |= letterbox_mask_from_detection(video_letterbox, (h, w))
                    video_bands = {
                        "top": int(video_letterbox.get("top", 0) or 0),
                        "bottom": int(video_letterbox.get("bottom", 0) or 0),
                        "left": int(video_letterbox.get("left", 0) or 0),
                        "right": int(video_letterbox.get("right", 0) or 0),
                    }
            rgb = rgb_u8.astype(np.float32) / 255.0
            luma = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
            if uniform_edge_scan and luma.shape == depth_candidate.shape:
                row_sources.append(luma)
                # Lateral depth gradients often reach extreme values at the
                # frame edge. Treat left/right bands as invalid only when the
                # RGB guide also looks like a uniform border.
                col_sources = [luma]
        except Exception:
            pass

    def row_invalid(y: int) -> bool:
        for source in row_sources:
            row = source[y, :]
            mean = float(np.mean(row))
            std = float(np.std(row))
            if std <= uniform_std and (mean <= extreme_low or mean >= extreme_high):
                return True
        return False

    def col_invalid(x: int) -> bool:
        for source in col_sources:
            col = source[:, x]
            mean = float(np.mean(col))
            std = float(np.std(col))
            if std <= uniform_std and (mean <= extreme_low or mean >= extreme_high):
                return True
        return False

    if uniform_edge_scan:
        max_rows = int(round(h * edge_scan_fraction))
        top = 0
        while top < max_rows and row_invalid(top):
            top += 1
        bottom = h
        while bottom > h - max_rows and bottom > top and row_invalid(bottom - 1):
            bottom -= 1
        max_cols = int(round(w * edge_scan_fraction))
        left = 0
        while left < max_cols and col_invalid(left):
            left += 1
        right = w
        while right > w - max_cols and right > left and col_invalid(right - 1):
            right -= 1
    else:
        top = 0
        bottom = h
        left = 0
        right = w

    top = max(top, video_bands["top"])
    bottom = min(bottom, h - video_bands["bottom"])
    left = max(left, video_bands["left"])
    right = min(right, w - video_bands["right"])

    if top > 0:
        invalid[:top, :] = True
    if bottom < h:
        invalid[bottom:, :] = True
    if left > 0:
        invalid[:, :left] = True
    if right < w:
        invalid[:, right:] = True
    return invalid.astype(bool), {
        "ok": True,
        "invalid_pixel_count": int(invalid.sum()),
        "top": int(top),
        "bottom": int(h - bottom),
        "left": int(left),
        "right": int(w - right),
        "video_letterbox": video_letterbox,
    }


def edge_aware_smooth_depth(
    depth_frame: Any,
    reference_rgb: Any,
    *,
    valid_mask: Any | None = None,
    radius: int = 3,
    iterations: int = 2,
    edge_strength: float = 18.0,
    depth_sigma: float = 0.075,
):
    import numpy as np

    depth = np.asarray(depth_frame, dtype=np.float32)
    if depth.ndim == 3:
        depth = depth[:, :, 0]
    rgb = frame_to_rgb_array(reference_rgb).astype(np.float32) / 255.0
    if rgb.shape[:2] != depth.shape:
        from PIL import Image

        rgb = np.asarray(
            Image.fromarray((rgb * 255.0).astype(np.uint8), "RGB").resize(
                (depth.shape[1], depth.shape[0]),
                Image.Resampling.BILINEAR,
            ),
            dtype=np.float32,
        ) / 255.0
    luma = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
    valid = np.ones(depth.shape, dtype=np.float32)
    if valid_mask is not None:
        mask = np.asarray(valid_mask, dtype=np.float32)
        if mask.shape == depth.shape:
            valid = np.clip(mask, 0.0, 1.0)

    out = np.clip(np.nan_to_num(depth, nan=1.0, posinf=1.0, neginf=0.0), 0.0, 1.0).astype(np.float32)
    offsets = _disk_offsets(max(0, int(radius)))
    if not offsets or int(iterations) <= 0:
        return out

    edge_strength = max(0.0, float(edge_strength))
    depth_sigma = max(1.0e-4, float(depth_sigma))
    for _ in range(max(1, int(iterations))):
        acc = out * valid
        weights = valid.copy()
        for dx, dy, spatial_w in offsets:
            shifted_depth = _shift_edge(out, dx, dy)
            shifted_luma = _shift_edge(luma, dx, dy)
            shifted_valid = _shift_edge(valid, dx, dy)
            guide_diff = np.abs(luma - shifted_luma)
            depth_diff = np.abs(out - shifted_depth)
            w = (
                np.exp(-guide_diff * edge_strength)
                * np.exp(-depth_diff / depth_sigma)
                * float(spatial_w)
                * shifted_valid
            )
            acc += shifted_depth * w
            weights += w
        out = np.where(weights > 1.0e-6, acc / np.maximum(weights, 1.0e-6), out)
        out = np.where(valid > 0.5, out, depth)
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def quantize_depth_layers(
    depth_frame: Any,
    *,
    valid_mask: Any | None = None,
    layer_count: int = 18,
    mix: float = 0.82,
):
    import numpy as np

    depth = np.asarray(depth_frame, dtype=np.float32)
    if depth.ndim == 3:
        depth = depth[:, :, 0]
    valid = np.isfinite(depth)
    if valid_mask is not None:
        mask = np.asarray(valid_mask, dtype=bool)
        if mask.shape == depth.shape:
            valid &= mask
    values = depth[valid]
    if values.size <= 0:
        return np.clip(depth, 0.0, 1.0).astype(np.float32)
    layer_count = max(2, int(layer_count))
    mix = max(0.0, min(1.0, float(mix)))
    edges = np.percentile(values, np.linspace(0.0, 100.0, layer_count + 1))
    edges = np.maximum.accumulate(edges)
    indices = np.searchsorted(edges[1:-1], depth, side="right")
    layered = depth.copy()
    for layer_index in range(layer_count):
        mask = valid & (indices == layer_index)
        if not np.any(mask):
            continue
        layered[mask] = float(np.median(depth[mask]))
    out = depth * (1.0 - mix) + layered * mix
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def _dark_background_foreground_depth_prior(
    depth_frame: Any,
    reference_rgb: Any,
    *,
    valid_mask: Any | None = None,
    settings: Mapping[str, Any] | None = None,
):
    """Flatten high-contrast dark-background subjects for viewer matte.

    Monocular or synthetic depth can confuse flower petals, product shots, and
    studio-object footage because internal texture contrast is stronger than
    true scene depth. For the diagnostic matte view, a reliable black/dark edge
    background is a stronger cue: the subject should read as one near object
    against a far background.
    """
    import numpy as np

    settings = settings or {}
    depth = np.asarray(depth_frame, dtype=np.float32)
    if depth.ndim == 3:
        depth = depth[:, :, 0]
    rgb = frame_to_rgb_array(reference_rgb)
    if rgb.shape[:2] != depth.shape:
        from PIL import Image

        rgb = np.asarray(
            Image.fromarray(rgb.astype(np.uint8), "RGB").resize(
                (depth.shape[1], depth.shape[0]),
                Image.Resampling.BILINEAR,
            ),
            dtype=np.uint8,
        )
    h, w = depth.shape[:2]
    valid = np.isfinite(depth)
    if valid_mask is not None:
        mask = np.asarray(valid_mask, dtype=bool)
        if mask.shape == depth.shape:
            valid &= mask
    if int(valid.sum()) <= max(16, int(h * w * 0.05)):
        return None, {"applied": False, "reason": "insufficient_valid_pixels"}

    rgbf = rgb.astype(np.float32) / 255.0
    luma = rgbf[..., 0] * 0.2126 + rgbf[..., 1] * 0.7152 + rgbf[..., 2] * 0.0722
    chroma = np.max(rgbf, axis=2) - np.min(rgbf, axis=2)
    edge_mask = _edge_band_mask(h, w, _setting_float(settings, "viewer_foreground_edge_fraction", 0.06, 0.02, 0.18))
    edge_valid = edge_mask & valid
    if int(edge_valid.sum()) <= max(8, int(h * w * 0.01)):
        return None, {"applied": False, "reason": "insufficient_edge_pixels"}

    edge_luma = luma[edge_valid]
    edge_chroma = chroma[edge_valid]
    edge_luma_p90 = float(np.percentile(edge_luma, 90.0))
    edge_luma_std = float(np.std(edge_luma))
    edge_chroma_p90 = float(np.percentile(edge_chroma, 90.0))
    valid_luma = luma[valid]
    valid_chroma = chroma[valid]
    dark_max = _setting_float(settings, "viewer_foreground_dark_edge_luma_max", 0.18, 0.02, 0.45)
    global_dark_max = _setting_float(settings, "viewer_foreground_global_dark_luma_max", 0.075, 0.0, 0.30)
    dark_pixels = valid & (luma <= global_dark_max)
    dark_fraction = float(np.mean(dark_pixels[valid])) if int(valid.sum()) else 0.0
    min_dark_fraction = _setting_float(settings, "viewer_foreground_min_dark_background_fraction", 0.16, 0.01, 0.80)
    edge_background_ok = edge_luma_p90 <= dark_max
    global_background_ok = dark_fraction >= min_dark_fraction
    if not edge_background_ok and not global_background_ok:
        return None, {
            "applied": False,
            "reason": "dark_background_not_reliable",
            "edge_luma_p90": edge_luma_p90,
            "edge_luma_std": edge_luma_std,
            "dark_fraction": dark_fraction,
        }
    if edge_background_ok:
        background_luma_p90 = edge_luma_p90
        background_chroma_p90 = edge_chroma_p90
        trigger = "edge_dark_background"
    else:
        dark_luma = luma[dark_pixels]
        dark_chroma = chroma[dark_pixels]
        background_luma_p90 = float(np.percentile(dark_luma, 90.0)) if dark_luma.size else float(np.percentile(valid_luma, 10.0))
        background_chroma_p90 = float(np.percentile(dark_chroma, 90.0)) if dark_chroma.size else float(np.percentile(valid_chroma, 10.0))
        trigger = "global_dark_background"

    luma_delta = _setting_float(settings, "viewer_foreground_luma_delta", 0.055, 0.005, 0.28)
    chroma_delta = _setting_float(settings, "viewer_foreground_chroma_delta", 0.055, 0.0, 0.28)
    min_luma = max(
        _setting_float(settings, "viewer_foreground_min_luma", 0.075, 0.0, 0.35),
        background_luma_p90 + luma_delta,
    )
    min_chroma = max(
        _setting_float(settings, "viewer_foreground_min_chroma", 0.16, 0.0, 0.65),
        background_chroma_p90 + chroma_delta,
    )
    candidate = valid & (
        (luma >= min_luma)
        | ((chroma >= min_chroma) & (luma >= background_luma_p90 + luma_delta * 0.32))
    )
    candidate = _max_filter_bool(candidate, _setting_int(settings, "viewer_foreground_expand_px", 1, 0, 8))
    soft = _box_blur_float(candidate.astype(np.float32), _setting_int(settings, "viewer_foreground_soft_radius_px", 2, 0, 12))
    foreground_fraction = float(np.mean(soft > 0.18))
    min_fraction = _setting_float(settings, "viewer_foreground_min_fraction", 0.015, 0.001, 0.30)
    max_fraction = _setting_float(settings, "viewer_foreground_max_fraction", 0.86, 0.10, 0.98)
    if foreground_fraction < min_fraction or foreground_fraction > max_fraction:
        return None, {
            "applied": False,
            "reason": "foreground_fraction_out_of_range",
            "foreground_fraction": foreground_fraction,
            "edge_luma_p90": edge_luma_p90,
            "dark_fraction": dark_fraction,
        }

    soft = np.clip(soft, 0.0, 1.0).astype(np.float32)
    foreground = soft > 0.22
    fg_values = depth[foreground & valid]
    bg_values = depth[(soft < 0.06) & valid]
    if fg_values.size <= 0:
        return None, {"applied": False, "reason": "no_foreground_depth_values"}
    fg_base = float(np.percentile(fg_values, 35.0))
    bg_base = float(np.percentile(bg_values, 88.0)) if bg_values.size else float(np.percentile(depth[valid], 88.0))
    min_separation = _setting_float(settings, "viewer_foreground_min_depth_separation", 0.42, 0.05, 0.85)
    if bg_base - fg_base < min_separation:
        fg_base = _setting_float(settings, "viewer_foreground_near_depth", 0.16, 0.0, 0.6)
        bg_base = _setting_float(settings, "viewer_foreground_far_depth", 0.92, 0.4, 1.0)

    fg_lo = float(np.percentile(fg_values, 8.0))
    fg_hi = float(np.percentile(fg_values, 92.0))
    span = max(1.0e-6, fg_hi - fg_lo)
    internal = np.clip((depth - fg_lo) / span, 0.0, 1.0)
    internal_range = _setting_float(settings, "viewer_foreground_internal_depth_range", 0.24, 0.0, 0.45)
    fg_depth = np.clip(fg_base + internal * internal_range, 0.0, 1.0)
    prior = bg_base * (1.0 - soft) + fg_depth * soft
    prior = np.where(valid, prior, depth)
    return np.clip(prior, 0.0, 1.0).astype(np.float32), {
        "applied": True,
        "mode": "dark_background_foreground_prior",
        "trigger": trigger,
        "foreground_fraction": foreground_fraction,
        "edge_luma_p90": edge_luma_p90,
        "edge_luma_std": edge_luma_std,
        "edge_chroma_p90": edge_chroma_p90,
        "background_luma_p90": background_luma_p90,
        "background_chroma_p90": background_chroma_p90,
        "dark_fraction": dark_fraction,
        "foreground_depth": float(fg_base),
        "background_depth": float(bg_base),
        "internal_depth_range": float(internal_range),
    }


def _resize_mask(mask_frame: Any, width: int, height: int):
    import numpy as np
    from PIL import Image

    mask = np.asarray(mask_frame, dtype=np.float32)
    if mask.ndim == 3:
        mask = mask[:, :, 0]
    if mask.shape != (int(height), int(width)):
        mask = np.asarray(
            Image.fromarray(mask.astype(np.float32), mode="F").resize(
                (int(width), int(height)),
                Image.Resampling.BILINEAR,
            ),
            dtype=np.float32,
        )
    if float(np.nanmax(mask)) > 1.5:
        mask = mask / 255.0
    return np.clip(np.nan_to_num(mask, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0)


def _normalize_for_invalid_scan(depth):
    import numpy as np

    arr = np.asarray(depth, dtype=np.float32)
    finite = arr[np.isfinite(arr)]
    if finite.size <= 0:
        return np.zeros(arr.shape, dtype=np.float32)
    lo = float(np.percentile(finite, 1.0))
    hi = float(np.percentile(finite, 99.0))
    if hi - lo < 1.0e-5:
        lo = float(np.min(finite))
        hi = float(np.max(finite))
    if hi - lo < 1.0e-5:
        return np.zeros(arr.shape, dtype=np.float32)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def _edge_band_mask(height: int, width: int, fraction: float):
    import numpy as np

    h = max(1, int(height))
    w = max(1, int(width))
    band_y = max(1, min(h // 2, int(round(h * max(0.0, float(fraction))))))
    band_x = max(1, min(w // 2, int(round(w * max(0.0, float(fraction))))))
    mask = np.zeros((h, w), dtype=bool)
    mask[:band_y, :] = True
    mask[h - band_y :, :] = True
    mask[:, :band_x] = True
    mask[:, w - band_x :] = True
    return mask


def _box_blur_float(values: Any, radius: int):
    import numpy as np

    src = np.asarray(values, dtype=np.float32)
    radius = max(0, int(radius))
    if radius <= 0:
        return src.copy()
    acc = src.copy()
    count = 1.0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            acc += _shift_edge(src, dx, dy).astype(np.float32)
            count += 1.0
    return np.clip(acc / max(1.0, count), 0.0, 1.0).astype(np.float32)


def _max_filter_bool(mask: Any, radius: int):
    import numpy as np

    src = np.asarray(mask, dtype=bool)
    radius = max(0, int(radius))
    if radius <= 0:
        return src.copy()
    out = src.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            out |= np.asarray(_shift_edge(src, dx, dy), dtype=bool)
    return out


def _disk_offsets(radius: int) -> list[tuple[int, int, float]]:
    if radius <= 0:
        return []
    offsets: list[tuple[int, int, float]] = []
    r2 = radius * radius
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            dist2 = dx * dx + dy * dy
            if dist2 > r2:
                continue
            spatial_w = 1.0 / (1.0 + dist2)
            offsets.append((dx, dy, spatial_w))
    return offsets


def _shift_edge(arr: Any, dx: int, dy: int):
    import numpy as np

    src = np.asarray(arr)
    h, w = src.shape[:2]
    pad = max(1, abs(int(dx)), abs(int(dy)))
    if src.ndim == 2:
        padded = np.pad(src, ((pad, pad), (pad, pad)), mode="edge")
        y0 = pad - int(dy)
        x0 = pad - int(dx)
        return padded[y0:y0 + h, x0:x0 + w]
    padded = np.pad(src, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    y0 = pad - int(dy)
    x0 = pad - int(dx)
    return padded[y0:y0 + h, x0:x0 + w, :]


def _setting_float(settings: Mapping[str, Any], key: str, default: float, low: float, high: float) -> float:
    try:
        value = float(settings.get(key, default))
    except Exception:
        value = float(default)
    return max(float(low), min(float(high), value))


def _setting_int(settings: Mapping[str, Any], key: str, default: int, low: int, high: int) -> int:
    try:
        value = int(round(float(settings.get(key, default))))
    except Exception:
        value = int(default)
    return max(int(low), min(int(high), value))


def _setting_bool(settings: Mapping[str, Any], key: str, default: bool) -> bool:
    if key not in settings:
        return bool(default)
    value = settings.get(key)
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(default)


__all__ = [
    "DEPTH_REFINEMENT_SCHEMA",
    "build_depth_invalid_mask",
    "edge_aware_smooth_depth",
    "layered_depth_matte_for_viewer",
    "quantize_depth_layers",
    "refine_depth_for_compositing",
    "robust_normalize_depth",
]

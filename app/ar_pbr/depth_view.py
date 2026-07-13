"""Viewer-friendly depth map conversion for AR/PBR preview frames."""
from __future__ import annotations

from typing import Any, Mapping

from app.ar_pbr.depth_occlusion import normalize_depth_frame


DEPTH_VIEW_SCHEMA = "tigerstudio.ar_pbr.depth_view.v1"


def normalize_depth_view_mode(mode: Any) -> str:
    text = str(mode or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if text in {"", "0", "false", "none", "normal", "off", "disabled"}:
        return "off"
    if text in {
        "1",
        "true",
        "on",
        "depth",
        "depth_map",
        "depth_only",
        "mono",
        "grayscale",
        "greyscale",
        "layered",
        "matte",
        "layered_depth",
        "depth_matte",
    }:
        return "matte"
    if text in {"distance", "distance_map", "distance_check", "range", "range_map", "gradient"}:
        return "distance"
    if text in {"plane", "floor", "road", "road_plane", "plane_candidates", "floor_plane"}:
        return "plane"
    if text in {"invert", "inverted", "raw", "far_white", "grayscale_inverted", "greyscale_inverted"}:
        return "inverted_grayscale"
    if text in {"heat", "false_color", "falsecolour", "false_colour", "turbo"}:
        return "heat"
    return "grayscale"


def _contrast_depth(arr):
    import numpy as np

    data = np.asarray(arr, dtype=np.float32)
    finite = data[np.isfinite(data)]
    if finite.size <= 0:
        return np.clip(data, 0.0, 1.0), 0.0, 1.0
    lo = float(np.percentile(finite, 2.0))
    hi = float(np.percentile(finite, 98.0))
    if hi - lo < 1e-5:
        lo = float(np.min(finite))
        hi = float(np.max(finite))
    if hi - lo < 1e-5:
        return np.zeros_like(data, dtype=np.float32), lo, hi
    return np.clip((data - lo) / (hi - lo), 0.0, 1.0), lo, hi


def depth_frame_to_rgb(
    depth_frame: Any,
    width: int,
    height: int,
    *,
    mode: str = "grayscale",
    reference_frame: Any | None = None,
    settings: Mapping[str, Any] | None = None,
) -> tuple[Any | None, dict[str, Any]]:
    """Convert a normalized depth frame to an RGB preview image.

    AR/PBR depth convention is near=0, far=1. The default viewer convention is
    near=white because it matches common depth-debug imagery and makes foreground
    object masks easier to inspect.
    """
    import numpy as np

    canonical_mode = normalize_depth_view_mode(mode)
    if canonical_mode == "off":
        return None, {
            "schema": DEPTH_VIEW_SCHEMA,
            "ok": True,
            "enabled": False,
            "mode": "off",
        }
    w = max(1, int(width or 1))
    h = max(1, int(height or 1))
    arr = normalize_depth_frame(depth_frame, w, h)
    if arr is None:
        return None, {
            "schema": DEPTH_VIEW_SCHEMA,
            "ok": False,
            "enabled": True,
            "mode": canonical_mode,
            "reason": "depth frame unavailable",
        }
    viewer_refinement = None
    view_depth = arr
    if reference_frame is not None and canonical_mode == "matte":
        view_depth, viewer_refinement = _layered_depth_for_viewer(arr, reference_frame, settings or {})
    elif reference_frame is not None and canonical_mode in {"distance", "plane"}:
        view_depth, viewer_refinement = _refined_distance_depth(arr, reference_frame, settings or {})
    contrasted, lo, hi = _contrast_depth(view_depth)
    near = 1.0 - contrasted
    if canonical_mode == "distance":
        rgb, distance_diag = _distance_view_rgb(contrasted)
        near_is_white = True
    elif canonical_mode == "plane":
        rgb, distance_diag = _plane_view_rgb(contrasted, reference_frame)
        near_is_white = True
    elif canonical_mode == "inverted_grayscale":
        gray = contrasted
        rgb = np.repeat((gray * 255.0).astype(np.uint8)[:, :, None], 3, axis=2)
        near_is_white = False
    elif canonical_mode == "heat":
        # Compact false-color ramp: far blue, middle violet/cyan, near warm.
        t = np.clip(near, 0.0, 1.0)
        r = np.clip(0.10 + 1.25 * t, 0.0, 1.0)
        g = np.clip(0.18 + 1.45 * (1.0 - abs(t - 0.55) * 1.85), 0.0, 1.0)
        b = np.clip(1.05 - 0.95 * t + 0.22 * (1.0 - abs(t - 0.35) * 2.2), 0.0, 1.0)
        rgb = (np.stack([r, g, b], axis=2) * 255.0).astype(np.uint8)
        near_is_white = False
    else:
        gray = near
        rgb = np.repeat((gray * 255.0).astype(np.uint8)[:, :, None], 3, axis=2)
        near_is_white = True
    diagnostics = {
        "schema": DEPTH_VIEW_SCHEMA,
        "ok": True,
        "enabled": True,
        "mode": canonical_mode,
        "width": int(w),
        "height": int(h),
        "near_is_white": bool(near_is_white),
        "input_depth_min": float(np.nanmin(arr)),
        "input_depth_max": float(np.nanmax(arr)),
        "display_depth_low": float(lo),
        "display_depth_high": float(hi),
    }
    if canonical_mode in {"distance", "plane"}:
        diagnostics.update(distance_diag)
    if viewer_refinement is not None:
        diagnostics["viewer_refinement"] = viewer_refinement
    return np.ascontiguousarray(rgb), diagnostics


def _layered_depth_for_viewer(arr, reference_frame: Any, settings: Mapping[str, Any]):
    try:
        from app.depth.refinement import layered_depth_matte_for_viewer

        return layered_depth_matte_for_viewer(arr, reference_frame, settings=settings)
    except Exception as exc:
        return arr, {
            "ok": False,
            "mode": "layered_depth_matte",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def _refined_distance_depth(arr, reference_frame: Any, settings: Mapping[str, Any]):
    try:
        from app.depth.refinement import refine_depth_for_compositing

        return refine_depth_for_compositing(
            arr,
            reference_frame,
            settings={
                "edge_smooth_radius_px": float(settings.get("distance_smooth_radius_px", 2) or 2),
                "edge_smooth_iterations": float(settings.get("distance_smooth_iterations", 1) or 1),
                "edge_strength": float(settings.get("distance_edge_strength", 18.0) or 18.0),
                "depth_sigma": float(settings.get("distance_depth_sigma", 0.085) or 0.085),
            },
            return_diagnostics=True,
        )
    except Exception as exc:
        return arr, {
            "ok": False,
            "mode": "edge_aware_compositing_depth",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def _distance_view_rgb(contrasted):
    import numpy as np

    depth = np.clip(np.asarray(contrasted, dtype=np.float32), 0.0, 1.0)
    near = 1.0 - depth
    # Neutral distance ramp with a slight cool tint in the far range so slopes
    # are easier to read than in plain grayscale.
    r = np.clip(near * 0.98 + 0.06, 0.0, 1.0)
    g = np.clip(near * 1.00 + 0.07, 0.0, 1.0)
    b = np.clip(near * 1.08 + depth * 0.12, 0.0, 1.0)
    rgb = (np.stack([r, g, b], axis=2) * 255.0).astype(np.uint8)
    contours = _depth_contour_mask(depth, levels=14)
    if contours.any():
        rgb[contours] = (58, 214, 255)
    return rgb, {
        "distance_view": {
            "enabled": True,
            "contour_levels": 14,
            "contour_pixel_count": int(contours.sum()),
            "purpose": "distance_gradient_check",
        }
    }


def _plane_view_rgb(contrasted, reference_frame: Any | None):
    import numpy as np

    depth = np.clip(np.asarray(contrasted, dtype=np.float32), 0.0, 1.0)
    base, distance_diag = _distance_view_rgb(depth)
    candidate, plane_diag = _road_plane_candidate_mask(depth, reference_frame)
    rgb = base.copy()
    if candidate.any():
        overlay = np.zeros_like(rgb)
        overlay[:, :, 0] = 42
        overlay[:, :, 1] = 232
        overlay[:, :, 2] = 148
        rgb[candidate] = (rgb[candidate].astype(np.float32) * 0.38 + overlay[candidate].astype(np.float32) * 0.62).astype(np.uint8)
    contours = _depth_contour_mask(depth, levels=10)
    edge = contours & candidate
    if edge.any():
        rgb[edge] = (255, 217, 94)
    return rgb, {
        **distance_diag,
        "plane_view": plane_diag,
    }


def _depth_contour_mask(depth, *, levels: int):
    import numpy as np

    d = np.clip(np.asarray(depth, dtype=np.float32), 0.0, 1.0)
    q = np.floor(d * max(2, int(levels))).astype(np.int16)
    mask = np.zeros(d.shape, dtype=bool)
    mask[:, 1:] |= q[:, 1:] != q[:, :-1]
    mask[1:, :] |= q[1:, :] != q[:-1, :]
    # Keep contours thin but visible in small preview panes.
    grown = mask.copy()
    grown[:, 1:] |= mask[:, :-1]
    return grown


def _road_plane_candidate_mask(depth, reference_frame: Any | None):
    import numpy as np

    d = np.clip(np.asarray(depth, dtype=np.float32), 0.0, 1.0)
    h, w = d.shape[:2]
    gy, gx = np.gradient(d)
    grad = np.abs(gx) + np.abs(gy)
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    lower = y >= 0.38
    smooth = grad <= max(0.018, float(np.percentile(grad, 58.0)))
    candidate = lower & smooth
    if reference_frame is not None:
        try:
            from app.depth.providers import frame_to_rgb_array

            rgb = frame_to_rgb_array(reference_frame).astype(np.float32) / 255.0
            luma = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
            ly, lx = np.gradient(luma)
            image_edge = (np.abs(lx) + np.abs(ly)) > max(0.06, float(np.percentile(np.abs(lx) + np.abs(ly), 78.0)))
            candidate &= ~image_edge
        except Exception:
            pass
    candidate = _majority_filter(candidate, radius=2)
    return candidate, {
        "enabled": True,
        "candidate_pixel_count": int(candidate.sum()),
        "candidate_ratio": float(candidate.mean()) if candidate.size else 0.0,
        "purpose": "road_or_floor_plane_candidate_check",
    }


def _majority_filter(mask, *, radius: int):
    import numpy as np

    src = np.asarray(mask, dtype=np.float32)
    if radius <= 0:
        return src > 0.5
    acc = src.copy()
    count = 1.0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            shifted = np.pad(src, ((radius, radius), (radius, radius)), mode="edge")
            y0 = radius - dy
            x0 = radius - dx
            acc += shifted[y0:y0 + src.shape[0], x0:x0 + src.shape[1]]
            count += 1.0
    return (acc / max(1.0, count)) > 0.42

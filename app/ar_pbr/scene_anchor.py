"""Scene-anchor analysis for AR/PBR preview placement.

This is a local, deterministic first pass: it estimates a depth frame from the
current preview, solves a road-like plane around the selected image point, and
stores enough camera/plane data on the track for the renderer to place the
asset on that surface.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def _as_vec3(value: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return default
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _frame_size(frame: Any) -> tuple[int, int]:
    try:
        import numpy as np

        arr = np.asarray(frame)
        h, w = arr.shape[:2]
        return max(1, int(w)), max(1, int(h))
    except Exception:
        return (1, 1)


def _rgb_array(frame: Any):
    import numpy as np

    arr = np.asarray(frame)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("frame must be RGB-like")
    arr = arr[:, :, :3]
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr


def _luma_u8(frame: Any):
    import numpy as np

    rgb = _rgb_array(frame).astype(np.float32)
    return np.clip(
        rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722,
        0,
        255,
    ).astype(np.uint8)


def _resize_nearest(src, size: int):
    import numpy as np

    arr = np.asarray(src)
    if arr.size == 0:
        return np.zeros((size, size), dtype=np.uint8)
    h, w = arr.shape[:2]
    ys = np.linspace(0, max(0, h - 1), int(size)).round().astype(np.int32)
    xs = np.linspace(0, max(0, w - 1), int(size)).round().astype(np.int32)
    return arr[ys][:, xs].astype(np.uint8)


def _template_payload_from_luma(luma: Any, image_point: tuple[float, float], *, size: int, radius_norm: float) -> dict[str, Any]:
    import numpy as np

    h, w = luma.shape[:2]
    cx = int(round(_clamp01(image_point[0]) * max(1, w - 1)))
    cy = int(round(_clamp01(image_point[1]) * max(1, h - 1)))
    radius = max(4, int(round(min(w, h) * max(0.01, float(radius_norm)))))
    padded = np.pad(luma, radius, mode="edge")
    patch = padded[cy:cy + radius * 2 + 1, cx:cx + radius * 2 + 1]
    templ = _resize_nearest(patch, int(size))
    return {
        "image_point": [float(image_point[0]), float(image_point[1])],
        "template_size": [int(size), int(size)],
        "template_luma": templ.reshape(-1).astype(int).tolist(),
        "std": float(np.std(templ)),
    }


def _extract_template(frame: Any, image_point: tuple[float, float], *, size: int = 24, radius_norm: float = 0.09) -> dict[str, Any]:
    import numpy as np

    luma = _luma_u8(frame)
    main = _template_payload_from_luma(luma, image_point, size=int(size), radius_norm=float(radius_norm))
    probe_templates: list[dict[str, Any]] = []
    probe_radius = max(0.018, min(0.06, float(radius_norm) * 0.42))
    for offset_x, offset_y in [(-0.045, 0.0), (0.045, 0.0), (0.0, -0.045), (0.0, 0.045)]:
        point = (_clamp01(image_point[0] + offset_x), _clamp01(image_point[1] + offset_y))
        probe = _template_payload_from_luma(luma, point, size=16, radius_norm=probe_radius)
        if float(probe.get("std", 0.0) or 0.0) >= 3.0:
            probe["offset_norm"] = [float(offset_x), float(offset_y)]
            probe_templates.append(probe)
    out = {
        "enabled": True,
        "image_point": [float(image_point[0]), float(image_point[1])],
        "template_size": [int(size), int(size)],
        "patch_radius_norm": float(radius_norm),
        "search_radius_norm": 0.22,
        "min_confidence": 0.18,
        "scale_tracking": True,
        "rotation_tracking": True,
        "scale_candidates": [0.82, 0.92, 1.0, 1.1, 1.22],
        "rotation_range_deg": 18.0,
        "rotation_step_deg": 9.0,
        "template_luma": main["template_luma"],
    }
    if probe_templates:
        out["probe_templates"] = probe_templates
    return out


def _tracking_template_array_from(payload: Mapping[str, Any]):
    import numpy as np

    raw = payload.get("template_luma")
    size = payload.get("template_size")
    if not isinstance(raw, (list, tuple)) or not isinstance(size, (list, tuple)) or len(size) < 2:
        return None
    w = max(1, int(size[0]))
    h = max(1, int(size[1]))
    if len(raw) < w * h:
        return None
    arr = np.asarray(raw[:w * h], dtype=np.uint8).reshape((h, w))
    return arr


def _tracking_template_array(tracking: Mapping[str, Any]):
    return _tracking_template_array_from(tracking)


def _tracking_point(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return (_clamp01(float(value[0])), _clamp01(float(value[1])))
        except Exception:
            pass
    return default


def _match_template_variant(
    luma: Any,
    template: Any,
    center_norm: tuple[float, float],
    tracking: Mapping[str, Any],
) -> tuple[tuple[float, float] | None, dict[str, Any]]:
    import numpy as np

    h, w = luma.shape[:2]
    cx = int(round(center_norm[0] * max(1, w - 1)))
    cy = int(round(center_norm[1] * max(1, h - 1)))
    search_radius = max(6, int(round(min(w, h) * float(tracking.get("search_radius_norm", 0.22) or 0.22))))
    patch_radius = max(4, int(round(min(w, h) * float(tracking.get("patch_radius_norm", 0.09) or 0.09))))
    x0 = max(0, cx - search_radius - patch_radius)
    y0 = max(0, cy - search_radius - patch_radius)
    x1 = min(w, cx + search_radius + patch_radius + 1)
    y1 = min(h, cy + search_radius + patch_radius + 1)
    search = luma[y0:y1, x0:x1]
    if search.shape[0] < template.shape[0] or search.shape[1] < template.shape[1]:
        return None, {"ok": False, "reason": "search_region_too_small"}
    try:
        import cv2

        use_sqdiff = float(np.std(template)) < 2.0
        base_h, base_w = template.shape[:2]
        raw_scales = tracking.get("scale_candidates")
        if isinstance(raw_scales, (list, tuple)) and raw_scales:
            scale_values = [max(0.35, min(3.0, float(value))) for value in raw_scales[:9]]
        elif bool(tracking.get("scale_tracking", True)):
            scale_values = [0.82, 0.92, 1.0, 1.1, 1.22]
        else:
            scale_values = [1.0]
        if not bool(tracking.get("scale_tracking", True)) and 1.0 not in scale_values:
            scale_values = [1.0]
        if bool(tracking.get("rotation_tracking", True)):
            rot_range = max(0.0, min(45.0, float(tracking.get("rotation_range_deg", 18.0) or 18.0)))
            rot_step = max(3.0, min(45.0, float(tracking.get("rotation_step_deg", 9.0) or 9.0)))
            steps = int(rot_range // rot_step)
            rotation_values = [round(idx * rot_step, 4) for idx in range(-steps, steps + 1)]
            if 0.0 not in rotation_values:
                rotation_values.append(0.0)
        else:
            rotation_values = [0.0]
        best: tuple[float, float, float, float, float, float, int, int] | None = None
        for scale in scale_values:
            cand_w = max(6, int(round(base_w * scale)))
            cand_h = max(6, int(round(base_h * scale)))
            if cand_w > search.shape[1] or cand_h > search.shape[0]:
                continue
            scaled = cv2.resize(template, (cand_w, cand_h), interpolation=cv2.INTER_LINEAR)
            for rotation in rotation_values:
                candidate = scaled
                if abs(rotation) > 1e-6:
                    matrix = cv2.getRotationMatrix2D((cand_w * 0.5, cand_h * 0.5), float(rotation), 1.0)
                    candidate = cv2.warpAffine(
                        scaled,
                        matrix,
                        (cand_w, cand_h),
                        flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REPLICATE,
                    )
                if use_sqdiff:
                    result = cv2.matchTemplate(search, candidate, cv2.TM_SQDIFF_NORMED)
                    min_val, _max_val, min_loc, _max_loc = cv2.minMaxLoc(result)
                    score = float(1.0 - min_val)
                    loc = min_loc
                else:
                    result = cv2.matchTemplate(search, candidate, cv2.TM_CCOEFF_NORMED)
                    _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
                    score = float(max_val)
                    loc = max_loc
                tie_break = abs(float(scale) - 1.0) * 0.002 + abs(float(rotation)) * 0.0002
                ranked = score - tie_break
                if best is None or ranked > best[0]:
                    px = x0 + int(loc[0]) + cand_w * 0.5
                    py = y0 + int(loc[1]) + cand_h * 0.5
                    best = (ranked, float(px), float(py), float(score), float(scale), float(rotation), cand_w, cand_h)
        if best is None:
            return None, {"ok": False, "reason": "no_template_variant_fits"}
        _ranked, px, py, confidence, best_scale, best_rotation, best_w, best_h = best
    except Exception:
        template_f = template.astype(np.float32)
        template_f -= float(template_f.mean())
        denom_t = float(np.sqrt((template_f * template_f).sum())) or 1.0
        best = (-2.0, cx, cy)
        step = max(1, min(template.shape) // 4)
        max_y = search.shape[0] - template.shape[0]
        max_x = search.shape[1] - template.shape[1]
        for yy in range(0, max_y + 1, step):
            for xx in range(0, max_x + 1, step):
                patch = search[yy:yy + template.shape[0], xx:xx + template.shape[1]].astype(np.float32)
                patch -= float(patch.mean())
                denom = denom_t * (float(np.sqrt((patch * patch).sum())) or 1.0)
                score = float((patch * template_f).sum() / denom)
                if score > best[0]:
                    best = (score, x0 + xx + template.shape[1] * 0.5, y0 + yy + template.shape[0] * 0.5)
        confidence, px, py = best
        best_scale = 1.0
        best_rotation = 0.0
        best_w = int(template.shape[1])
        best_h = int(template.shape[0])
    min_conf = float(tracking.get("min_confidence", 0.18) or 0.18)
    diagnostics = {
        "ok": confidence >= min_conf,
        "confidence": confidence,
        "min_confidence": min_conf,
        "pixel": [float(px), float(py)],
        "previous_pixel": [float(cx), float(cy)],
        "delta_px": [float(px - cx), float(py - cy)],
        "search_radius_px": search_radius,
        "scale": float(best_scale),
        "rotation_deg": float(best_rotation),
        "matched_template_size": [int(best_w), int(best_h)],
    }
    if confidence < min_conf:
        diagnostics["reason"] = "low_confidence"
        return None, diagnostics
    return (_clamp01(float(px) / max(1, w)), _clamp01(float(py) / max(1, h))), diagnostics


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) * 0.5)


def _angle_delta_degrees(base: float, current: float) -> float:
    import math

    delta = math.degrees(current - base)
    while delta > 180.0:
        delta -= 360.0
    while delta < -180.0:
        delta += 360.0
    return delta


def _multi_probe_affine(
    tracking: Mapping[str, Any],
    luma: Any,
    base_center: tuple[float, float],
    current_center: tuple[float, float],
) -> dict[str, Any]:
    import math

    probes = tracking.get("probe_templates")
    if not isinstance(probes, (list, tuple)):
        return {"ok": False, "probe_count": 0, "reason": "no_probe_templates"}
    h, w = luma.shape[:2]
    scales: list[float] = []
    rotations: list[float] = []
    rows: list[dict[str, Any]] = []
    for probe in probes[:8]:
        if not isinstance(probe, Mapping):
            continue
        template = _tracking_template_array_from(probe)
        if template is None:
            continue
        probe_point = _tracking_point(probe.get("image_point"), base_center)
        probe_tracking = dict(tracking)
        probe_tracking["patch_radius_norm"] = min(float(tracking.get("patch_radius_norm", 0.09) or 0.09), 0.05)
        probe_tracking["search_radius_norm"] = float(tracking.get("search_radius_norm", 0.22) or 0.22)
        matched, diag = _match_template_variant(luma, template, probe_point, probe_tracking)
        row = {"base": list(probe_point), "matched": list(matched) if matched else None, "diag": diag}
        rows.append(row)
        if matched is None or not diag.get("ok"):
            continue
        bx = (probe_point[0] - base_center[0]) * w
        by = (probe_point[1] - base_center[1]) * h
        mx = (matched[0] - current_center[0]) * w
        my = (matched[1] - current_center[1]) * h
        base_len = math.hypot(bx, by)
        match_len = math.hypot(mx, my)
        if base_len < 2.0 or match_len < 1.0:
            continue
        scales.append(max(0.35, min(3.0, match_len / base_len)))
        rotations.append(_angle_delta_degrees(math.atan2(by, bx), math.atan2(my, mx)))
    scale = _median(scales)
    rotation = _median(rotations)
    ok = scale is not None and rotation is not None and len(scales) >= 2
    return {
        "ok": ok,
        "probe_count": len(rows),
        "matched_probe_count": len(scales),
        "scale": scale,
        "rotation_deg": rotation,
        "probes": rows,
    }


def _track_template_position(frame: Any, placement: Mapping[str, Any]) -> tuple[tuple[float, float] | None, dict[str, Any]]:
    tracking = placement.get("tracking") if isinstance(placement.get("tracking"), Mapping) else {}
    if not tracking or not bool(tracking.get("enabled", False)):
        return None, {"ok": False, "reason": "tracking_disabled"}
    template = _tracking_template_array(tracking)
    if template is None:
        return None, {"ok": False, "reason": "missing_template"}
    luma = _luma_u8(frame)
    point = placement.get("image_point") or tracking.get("image_point") or [0.5, 0.62]
    x_norm, y_norm = _track_image_point({"placement": {"image_point": point}})
    matched, diagnostics = _match_template_variant(luma, template, (x_norm, y_norm), tracking)
    if matched is None or not diagnostics.get("ok"):
        return None, diagnostics
    affine = _multi_probe_affine(tracking, luma, (x_norm, y_norm), matched)
    diagnostics["multi_probe"] = affine
    if affine.get("ok"):
        if bool(tracking.get("scale_tracking", True)) and affine.get("scale") is not None:
            diagnostics["scale"] = float(affine["scale"])
        if bool(tracking.get("rotation_tracking", True)) and affine.get("rotation_deg") is not None:
            diagnostics["rotation_deg"] = max(-45.0, min(45.0, float(affine["rotation_deg"])))
    return matched, diagnostics


def _apply_tracking_transform(out: dict[str, Any], tracking_diag: Mapping[str, Any]) -> dict[str, Any]:
    placement = out.get("placement") if isinstance(out.get("placement"), Mapping) else {}
    tracking = placement.get("tracking") if isinstance(placement, Mapping) and isinstance(placement.get("tracking"), Mapping) else {}
    transform = deepcopy(out.get("transform") if isinstance(out.get("transform"), Mapping) else {})
    changed = False
    applied: dict[str, Any] = {"scale": False, "rotation": False}
    if bool(tracking_diag.get("ok")) and bool(tracking.get("scale_tracking", True)):
        try:
            ratio = max(0.35, min(3.0, float(tracking_diag.get("scale", 1.0) or 1.0)))
            base = _as_vec3(tracking.get("base_scale"), _as_vec3(transform.get("scale"), (1.0, 1.0, 1.0)))
            transform["scale"] = [max(0.0001, base[0] * ratio), max(0.0001, base[1] * ratio), max(0.0001, base[2] * ratio)]
            applied["scale"] = True
            changed = True
        except Exception:
            pass
    if bool(tracking_diag.get("ok")) and bool(tracking.get("rotation_tracking", True)):
        try:
            delta = max(-45.0, min(45.0, float(tracking_diag.get("rotation_deg", 0.0) or 0.0)))
            base = _as_vec3(tracking.get("base_rotation"), _as_vec3(transform.get("rotation"), (0.0, 0.0, 0.0)))
            transform["rotation"] = [base[0], base[1], base[2] + delta]
            applied["rotation"] = True
            changed = True
        except Exception:
            pass
    if changed:
        out["transform"] = transform
    return applied


def _slam_assist_payload(
    *,
    previous_point: tuple[float, float],
    tracked_point: tuple[float, float],
    tracking_diag: Mapping[str, Any],
    plane_diag: Mapping[str, Any],
    solution: Mapping[str, Any] | None,
    frame_size: tuple[int, int],
) -> dict[str, Any]:
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    dx_px = (float(tracked_point[0]) - float(previous_point[0])) * width
    dy_px = (float(tracked_point[1]) - float(previous_point[1])) * height
    try:
        confidence = max(0.0, min(1.0, float(tracking_diag.get("confidence", 0.0) or 0.0)))
    except Exception:
        confidence = 0.0
    try:
        scale = float(tracking_diag.get("scale", 1.0) or 1.0)
    except Exception:
        scale = 1.0
    try:
        rotation = float(tracking_diag.get("rotation_deg", 0.0) or 0.0)
    except Exception:
        rotation = 0.0
    plane_ok = bool(plane_diag.get("ok")) and solution is not None
    tracking_ok = bool(tracking_diag.get("ok"))
    assist_confidence = confidence * (1.0 if tracking_ok else 0.35)
    if plane_ok:
        assist_confidence = min(1.0, assist_confidence + 0.18)
    return {
        "ok": bool(plane_ok),
        "mode": "template_depth_plane_slam_assist",
        "limits": "2d_similarity_tracking_plus_depth_plane_not_full_slam",
        "translation_px": [float(dx_px), float(dy_px)],
        "translation_norm": [
            float(tracked_point[0] - previous_point[0]),
            float(tracked_point[1] - previous_point[1]),
        ],
        "scale": float(scale),
        "roll_deg": max(-45.0, min(45.0, float(rotation))),
        "tracking_confidence": float(confidence),
        "assist_confidence": float(max(0.0, min(1.0, assist_confidence))),
        "camera_solution_id": str((solution or {}).get("id") or ""),
        "plane_ok": bool(plane_ok),
        "tracking_ok": bool(tracking_ok),
    }


def _track_image_point(track: Mapping[str, Any], default: tuple[float, float] = (0.5, 0.62)) -> tuple[float, float]:
    placement = track.get("placement") if isinstance(track.get("placement"), Mapping) else {}
    point = placement.get("image_point") if isinstance(placement, Mapping) else None
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        try:
            return (_clamp01(float(point[0])), _clamp01(float(point[1])))
        except Exception:
            pass
    transform = track.get("transform") if isinstance(track.get("transform"), Mapping) else {}
    position = transform.get("position") if isinstance(transform, Mapping) else None
    if isinstance(position, (list, tuple)) and len(position) >= 2:
        try:
            return (
                _clamp01(0.5 + float(position[0]) / 4.0),
                _clamp01(0.5 - float(position[1]) / 4.0),
            )
        except Exception:
            pass
    return default


def road_plane_sample_points(
    image_point: tuple[float, float] | list[float],
    frame_size: tuple[int, int],
) -> list[list[float]]:
    """Return three stable pixel points around a road anchor."""
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    x = _clamp01(float(image_point[0])) * width
    y = _clamp01(float(image_point[1])) * height
    dx = max(12.0, width * 0.16)
    dy = max(8.0, height * 0.08)
    return [
        [max(0.0, min(width - 1.0, x)), max(0.0, min(height - 1.0, y))],
        [max(0.0, min(width - 1.0, x - dx)), max(0.0, min(height - 1.0, y + dy))],
        [max(0.0, min(width - 1.0, x + dx)), max(0.0, min(height - 1.0, y + dy))],
    ]


def _anchor_world_from_solution(
    image_point: tuple[float, float],
    camera_solution: Mapping[str, Any],
    frame_size: tuple[int, int],
) -> list[float]:
    from app.ar_pbr.placement import camera_ray_from_image_point, intersect_ray_plane

    width, height = frame_size
    px_point = (float(image_point[0]) * width, float(image_point[1]) * height)
    origin, direction = camera_ray_from_image_point(px_point, camera_solution, frame_size=frame_size)
    plane = camera_solution.get("plane") if isinstance(camera_solution, Mapping) else {}
    hit = intersect_ray_plane(origin, direction, plane if isinstance(plane, Mapping) else {})
    if hit is None:
        return [0.0, 0.0, 1.0]
    return [float(hit[0]), float(hit[1]), float(hit[2])]


def promote_track_to_scene_anchor(
    track: Mapping[str, Any],
    frame: Any,
    *,
    time_ms: int = 0,
    source_id: str = "",
    store_caches: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a track copy converted to a road-plane scene anchor."""
    from app.camera_solve.cache import store_camera_solution
    from app.camera_solve.solver import solve_road_plane_from_points
    from app.depth.cache import depth_source_id, store_depth_frame
    from app.depth.estimator import estimate_depth
    from app.depth.providers import select_depth_provider_id

    out = deepcopy(dict(track))
    width, height = _frame_size(frame)
    image_point = _track_image_point(out)
    provider_id = select_depth_provider_id()
    depth_id = depth_source_id(source_id or str(out.get("asset_path") or "preview"), backend=provider_id)
    depth, depth_diag = estimate_depth(
        frame,
        source_id=depth_id,
        time_ms=int(time_ms),
    )
    points = road_plane_sample_points(image_point, (width, height))
    solution, plane_diag = solve_road_plane_from_points(
        points,
        depth_frame=depth,
        frame_size=(width, height),
        source_id=source_id or str(out.get("asset_path") or "preview"),
        depth_source_id=depth_id,
        time_ms=int(time_ms),
    )
    diagnostics = {
        "ok": solution is not None,
        "mode": "road_plane_anchor",
        "track_id": str(out.get("id") or ""),
        "image_point": [float(image_point[0]), float(image_point[1])],
        "sample_points": points,
        "depth": depth_diag,
        "plane": plane_diag,
        "warnings": [],
    }
    if solution is None:
        diagnostics["warnings"].append("road plane solve failed")
        return out, diagnostics

    if store_caches:
        try:
            store_depth_frame(
                depth_id,
                int(time_ms),
                depth,
                diagnostics=depth_diag,
                source_path=source_id or str(out.get("asset_path") or "preview"),
                provider_id=provider_id,
            )
        except Exception as exc:
            diagnostics["warnings"].append(f"depth cache unavailable: {type(exc).__name__}")
        try:
            store_camera_solution(solution)
        except Exception as exc:
            diagnostics["warnings"].append(f"camera solution cache unavailable: {type(exc).__name__}")

    source_transform = dict(out.get("transform") if isinstance(out.get("transform"), Mapping) else {})
    tracking = _extract_template(frame, image_point)
    tracking["base_scale"] = list(_as_vec3(source_transform.get("scale"), (1.0, 1.0, 1.0)))
    tracking["base_rotation"] = list(_as_vec3(source_transform.get("rotation"), (0.0, 0.0, 0.0)))
    placement = dict(out.get("placement") if isinstance(out.get("placement"), Mapping) else {})
    placement.update({
        "mode": "road_plane_anchor",
        "coordinate_space": "normalized",
        "image_point": [float(image_point[0]), float(image_point[1])],
        "plane_solution_id": str(solution.get("id") or ""),
        "anchor_world": _anchor_world_from_solution(image_point, solution, (width, height)),
        "surface_normal": list((solution.get("plane") or {}).get("normal") or [0.0, 1.0, 0.0]),
        "surface_offset": float(placement.get("surface_offset", 0.0) or 0.0),
        "manual_offset": [0.0, 0.0, 0.0],
        "tracking": tracking,
    })
    out["placement"] = placement
    out["camera_solution_id"] = str(solution.get("id") or "")
    out["camera_solution"] = solution
    out["depth_source_id"] = depth_id
    transform = dict(out.get("transform") if isinstance(out.get("transform"), Mapping) else {})
    transform["position"] = [0.0, 0.0, 0.0]
    out["transform"] = transform
    diagnostics["camera_solution_id"] = out["camera_solution_id"]
    diagnostics["depth_source_id"] = depth_id
    diagnostics["anchor_world"] = placement["anchor_world"]
    return out, diagnostics


def update_scene_anchor_for_frame(
    track: Mapping[str, Any],
    frame: Any,
    *,
    time_ms: int = 0,
    source_id: str = "",
) -> tuple[dict[str, Any], Any, dict[str, Any] | None, dict[str, Any]]:
    """Return a runtime track copy whose anchor follows the current frame."""
    from app.camera_solve.solver import solve_road_plane_from_points
    from app.depth.estimator import estimate_depth

    out = deepcopy(dict(track))
    placement = dict(out.get("placement") if isinstance(out.get("placement"), Mapping) else {})
    mode = str(placement.get("mode") or "manual").casefold()
    if mode not in {"road_plane_anchor", "plane_anchor", "screen_plane", "scene_anchor"}:
        return out, None, None, {"ok": False, "reason": "not_scene_anchor", "mode": mode}
    width, height = _frame_size(frame)
    previous_point = _track_image_point(out)
    tracked_point, tracking_diag = _track_template_position(frame, placement)
    if tracked_point is None:
        tracked_point = previous_point
    depth_id = str(out.get("depth_source_id") or f"runtime_depth_{out.get('id', 'track')}")
    depth, depth_diag = estimate_depth(frame, source_id=depth_id, time_ms=int(time_ms))
    points = road_plane_sample_points(tracked_point, (width, height))
    solution, plane_diag = solve_road_plane_from_points(
        points,
        depth_frame=depth,
        frame_size=(width, height),
        source_id=source_id or str(out.get("asset_path") or "runtime"),
        depth_source_id=depth_id,
        time_ms=int(time_ms),
    )
    placement["mode"] = "road_plane_anchor"
    placement["coordinate_space"] = "normalized"
    placement["image_point"] = [float(tracked_point[0]), float(tracked_point[1])]
    placement.pop("anchor_world", None)
    out["placement"] = placement
    transform_tracking = _apply_tracking_transform(out, tracking_diag)
    if solution is not None:
        out["camera_solution"] = solution
        out["camera_solution_id"] = str(solution.get("id") or "")
    slam_assist = _slam_assist_payload(
        previous_point=previous_point,
        tracked_point=tracked_point,
        tracking_diag=tracking_diag,
        plane_diag=plane_diag,
        solution=solution,
        frame_size=(width, height),
    )
    out["camera_motion_hint"] = slam_assist
    diagnostics = {
        "ok": solution is not None,
        "mode": "road_plane_anchor_runtime",
        "track_id": str(out.get("id") or ""),
        "image_point": placement["image_point"],
        "tracking": tracking_diag,
        "transform_tracking": transform_tracking,
        "slam_assist": slam_assist,
        "depth": depth_diag,
        "plane": plane_diag,
    }
    return out, depth, solution, diagnostics

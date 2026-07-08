"""Internal VRM fallback renderer for VTuber Program Output.

This module is the local output path used when the optional VSeeFace sidecar
capture is unavailable or black.  Heavy renderer imports stay lazy so status UI
and project loading do not pay the cost unless a frame is actually requested.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from app.broadcast_scene import composite_broadcast_frame
from app.vtuber.vrm_renderer import (
    VRM_RENDER_PROFILE,
    VRM_RENDERER_FAMILY,
    VRM_RENDERER_GPU,
    load_vrm_avatar_descriptor,
    make_vrm_render_track,
    normalize_vrm_renderer,
    vrm_renderer_contract,
    vrm_renderer_warnings,
)


INTERNAL_VRM_FALLBACK_RENDER_SCHEMA = "tigerstudio.vtuber.internal_vrm_fallback_render.v1"

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VRM = ROOT / "external" / "assets" / "vtuber" / "booth_milica" / "Milica1.3free" / "Milica_v1.3.vrm"


def render_internal_vrm_fallback_frame(
    source: Mapping[str, Any] | None = None,
    *,
    time_ms: int = 0,
    width: int = 1280,
    height: int = 720,
    renderer: str = VRM_RENDERER_GPU,
) -> tuple[Any, dict[str, Any]]:
    """Render one transparent RGBA avatar frame for `internal_vrm_fallback`.

    The current production path can reuse generated descriptor/motion artifacts,
    but it must also build from the durable VRM asset and neutral motion when
    `debugCapture` has been cleaned. It intentionally does not call or require
    VSeeFace, a virtual camera, OBS, or Qt.
    """
    from PIL import Image

    source_data = dict(source or {})
    settings = dict(source_data.get("settings") if isinstance(source_data.get("settings"), Mapping) else source_data)
    vrm_path = _resolve_path(settings.get("avatar_vrm") or settings.get("vrm") or DEFAULT_VRM)
    descriptor_value = settings.get("descriptor_path") or settings.get("descriptor")
    motion_value = settings.get("motion_csv") or settings.get("openseeface_csv")
    descriptor_path = _resolve_path(descriptor_value) if descriptor_value else None
    motion_csv = _resolve_path(motion_value) if motion_value else None
    width = max(1, int(width))
    height = max(1, int(height))
    renderer_id = normalize_vrm_renderer(renderer)
    renderer_contract = vrm_renderer_contract(renderer)
    quality = internal_vrm_fallback_quality_policy(width=width, height=height, renderer=renderer_id, settings=settings)

    diagnostics: dict[str, Any] = {
        "schema": INTERNAL_VRM_FALLBACK_RENDER_SCHEMA,
        "ok": False,
        "source_id": str(source_data.get("id") or "internal_vrm_fallback"),
        "renderer": renderer_id,
        "requested_renderer": str(renderer or ""),
        "renderer_family": VRM_RENDERER_FAMILY,
        "render_profile": VRM_RENDER_PROFILE,
        "renderer_contract": renderer_contract,
        "pbr_renderer": False,
        "ar_pbr_preview": False,
        "program_output": True,
        "requires_vseeface": False,
        "requires_virtual_camera": False,
        "vrm": str(vrm_path),
        "descriptor": str(descriptor_path) if descriptor_path else "",
        "motion_csv": str(motion_csv) if motion_csv else "",
        "time_ms": int(time_ms),
        "size": [width, height],
        "quality": quality,
        "warnings": [*vrm_renderer_warnings(renderer), *list(quality.get("warnings") or [])],
        "errors": [],
    }
    missing = [str(vrm_path)] if not vrm_path.exists() else []
    for value, path in ((descriptor_value, descriptor_path), (motion_value, motion_csv)):
        if value and (path is None or not path.exists()):
            missing.append(str(_resolve_path(value)))
    if missing:
        diagnostics["errors"].append("missing_internal_vrm_fallback_asset")
        diagnostics["missing_assets"] = missing
        return Image.new("RGBA", (width, height), (0, 0, 0, 0)), diagnostics

    try:
        runtime = _load_cached_runtime(
            str(vrm_path.resolve()),
            str(descriptor_path.resolve()) if descriptor_path else "",
            str(motion_csv.resolve()) if motion_csv else "",
            str(settings.get("upper_body_mode") or "seated"),
        )
        module = runtime["module"]
        frames = runtime["frames"]
        frame = _select_motion_frame(frames, int(time_ms))
        descriptor = module._apply_face_morphs(runtime["base_descriptor"], runtime["morph_targets"], frame)
        preview_cap = int(settings.get("contact_preview_triangle_cap", 0) or 0)
        if preview_cap > 0:
            descriptor = _limit_descriptor_triangles_for_contact_preview(
                descriptor,
                max_triangles_per_geometry=preview_cap,
            )
        image, render_diag = _render_descriptor_frame(
            module,
            descriptor=descriptor,
            asset_path=vrm_path,
            time_ms=int(frame.time_ms),
            width=width,
            height=height,
            renderer=renderer_id,
            settings=settings,
        )
        image, fit_diag = _autofit_avatar_rgba(image, settings=settings)
        diagnostics.update(
            {
                "ok": bool(render_diag.get("ok", False)),
                "descriptor_source": str(runtime.get("descriptor_source") or "unknown"),
                "motion_source": str(runtime.get("motion_source") or "unknown"),
                "pose_source": str(runtime.get("motion_source") or "openseeface_motion_csv"),
                "selected_motion_time_ms": int(frame.time_ms),
                "selected_motion": {
                    "yaw_deg": float(getattr(frame, "yaw_deg", 0.0)),
                    "pitch_deg": float(getattr(frame, "pitch_deg", 0.0)),
                    "roll_deg": float(getattr(frame, "roll_deg", 0.0)),
                    "shoulder_roll_deg": float(getattr(frame, "shoulder_roll_deg", 0.0)),
                    "mouth_open": float(getattr(frame, "mouth_open", 0.0)),
                    "blink_l": float(getattr(frame, "blink_l", 0.0)),
                    "blink_r": float(getattr(frame, "blink_r", 0.0)),
                },
                "render": dict(render_diag),
                "fit": fit_diag,
            }
        )
        if not diagnostics["ok"]:
            diagnostics["errors"].extend(render_diag.get("errors") or ["internal_vrm_fallback_render_failed"])
        return image.convert("RGBA"), diagnostics
    except Exception as exc:
        diagnostics["errors"].append(f"internal_vrm_fallback_exception:{type(exc).__name__}:{exc}")
        return Image.new("RGBA", (width, height), (0, 0, 0, 0)), diagnostics


def _limit_descriptor_triangles_for_contact_preview(
    descriptor: dict[str, Any],
    *,
    max_triangles_per_geometry: int = 420,
) -> dict[str, Any]:
    """Legacy helper for non-product contact previews.

    Product/UI/AI-selected VRM routes use `vrm_mtoon_gpu`. This helper remains
    only for old diagnostics that explicitly manipulate descriptor density.
    """
    out = dict(descriptor)
    geometries: list[Any] = []
    cap = max(1, int(max_triangles_per_geometry or 420))
    total = 0
    source_total = 0
    for geometry in descriptor.get("geometries", []) or []:
        if not isinstance(geometry, dict):
            geometries.append(geometry)
            continue
        row = dict(geometry)
        triangles = row.get("triangles")
        if isinstance(triangles, list):
            source_total += int(len(triangles))
            if len(triangles) > cap:
                row["source_triangle_count"] = int(len(triangles))
                row["triangles"] = _sample_rows_evenly(triangles, cap)
                row["triangle_count"] = int(len(row["triangles"]))
            total += int(len(row.get("triangles") or []))
        geometries.append(row)
    out["geometries"] = geometries
    out["contact_preview_triangle_count"] = int(total)
    out["contact_preview_source_triangle_count"] = int(source_total)
    out["contact_preview_triangle_cap"] = int(cap)
    return out


def _sample_rows_evenly(rows: list[Any], target_count: int) -> list[Any]:
    if target_count <= 0 or len(rows) <= target_count:
        return list(rows)
    if target_count == 1:
        return [rows[len(rows) // 2]]
    last = len(rows) - 1
    out: list[Any] = []
    seen: set[int] = set()
    for i in range(target_count):
        idx = round(i * last / (target_count - 1))
        if idx in seen:
            continue
        out.append(rows[idx])
        seen.add(idx)
    return out


def internal_vrm_fallback_quality_policy(
    *,
    width: int,
    height: int,
    renderer: str = VRM_RENDERER_GPU,
    settings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    data = dict(settings or {})
    render_key = normalize_vrm_renderer(renderer)
    width = max(1, int(width))
    height = max(1, int(height))
    target_fps = max(1.0, float(data.get("target_fps", data.get("fps", 30.0)) or 30.0))
    pixel_count = int(width * height)
    warnings: list[str] = list(vrm_renderer_warnings(renderer))
    claim_blockers: list[str] = []
    if pixel_count < 1280 * 720:
        warnings.append("internal_vrm_fallback_resolution_below_720p")
        claim_blockers.append("render_resolution_below_720p")
    if render_key != VRM_RENDERER_GPU:
        warnings.append("internal_vrm_fallback_software_preview_renderer")
        claim_blockers.append("vrm_mtoon_gpu_renderer_not_selected")
    if target_fps < 24.0:
        warnings.append("internal_vrm_fallback_target_fps_below_24")
        claim_blockers.append("target_fps_below_24")
    return {
        "schema": "tigerstudio.vtuber.internal_vrm_fallback_quality.v1",
        "renderer": render_key,
        "renderer_family": VRM_RENDERER_FAMILY,
        "render_profile": VRM_RENDER_PROFILE,
        "pbr_renderer": False,
        "ar_pbr_preview": False,
        "software_renderer_available": False,
        "software_renderer_disabled": True,
        "profile": "broadcast_candidate" if not claim_blockers else "preview_safe",
        "broadcast_ready": not claim_blockers,
        "width": width,
        "height": height,
        "pixel_count": pixel_count,
        "target_fps": float(target_fps),
        "frame_budget_ms": 1000.0 / target_fps,
        "cache_enabled": True,
        "runtime_cache_max_entries": 4,
        "mesh_material_stability_check": "descriptor_cached_or_generated",
        "motion_cache": "openseeface_csv_or_idle",
        "warnings": warnings,
        "claim_blockers": claim_blockers,
    }


def composite_internal_vrm_fallback_program_frame(
    scene: Mapping[str, Any],
    fallback_frame: Any,
    *,
    vseeface_frame: Any | None = None,
    source_id: str = "internal_vrm_fallback",
) -> tuple[np.ndarray, dict[str, Any]]:
    """Composite Program Output with VSeeFace black-frame suppression intact."""
    frame_map: dict[str, Any] = {str(source_id or "internal_vrm_fallback"): fallback_frame}
    if vseeface_frame is not None:
        frame_map["vseeface"] = vseeface_frame
    return composite_broadcast_frame(scene, frame_map)


@lru_cache(maxsize=4)
def _load_cached_runtime(
    vrm_path: str,
    descriptor_path: str,
    motion_csv: str,
    upper_body_mode: str,
) -> dict[str, Any]:
    import importlib

    module = importlib.import_module("tools.render_milica_vrm_trump_mapping")
    vrm = Path(vrm_path)
    csv_path = Path(motion_csv) if str(motion_csv or "").strip() else None
    frames = tuple(module.load_openseeface_motion_csv(csv_path)) if csv_path and csv_path.is_file() else ()
    motion_source = "openseeface_motion_csv" if frames else "idle_internal_motion"
    if not frames:
        frames = _idle_motion_frames()
    descriptor_file = Path(descriptor_path) if str(descriptor_path or "").strip() else None
    if descriptor_file and descriptor_file.is_file():
        descriptor = module._load_descriptor(descriptor_file)
        descriptor_source = "descriptor_file"
    else:
        descriptor = _load_descriptor_from_vrm(vrm)
        descriptor_source = "vrm_import"
    morph_targets = module._load_vrm_morph_targets(vrm)
    texture_paths = module._expected_texture_paths(vrm)
    base_descriptor = module._attach_vrm_textures(descriptor, texture_paths)
    base_descriptor = module._attach_pose_animation(
        base_descriptor,
        frames,
        upper_body_mode=str(upper_body_mode or "seated"),
    )
    return {
        "module": module,
        "frames": frames,
        "morph_targets": morph_targets,
        "base_descriptor": base_descriptor,
        "descriptor_source": descriptor_source,
        "motion_source": motion_source,
    }


def _load_descriptor_from_vrm(vrm: Path) -> dict[str, Any]:
    descriptor, diagnostics = load_vrm_avatar_descriptor(vrm)
    if not isinstance(descriptor, dict) or not descriptor.get("geometries"):
        raise ValueError(f"Internal VRM fallback descriptor import failed: {diagnostics}")
    return descriptor


def _idle_motion_frames() -> tuple[Any, ...]:
    from app.vtuber.video_face_driver import idle_motion_frame

    return tuple(idle_motion_frame(time_ms) for time_ms in (0, 500, 1000, 1500))


def _render_descriptor_frame(
    module: Any,
    *,
    descriptor: dict[str, Any],
    asset_path: Path,
    time_ms: int,
    width: int,
    height: int,
    renderer: str,
    settings: Mapping[str, Any],
) -> tuple[Any, dict[str, Any]]:
    from PIL import Image

    base = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    camera = settings.get("camera") if isinstance(settings.get("camera"), Mapping) else {}
    placement = settings.get("placement") if isinstance(settings.get("placement"), Mapping) else {}
    track = make_vrm_render_track(
        track_id="internal_vrm_fallback",
        asset_path=asset_path,
        start_ms=0,
        end_ms=60_000,
        transform={
            "position": list(placement.get("position") or [0.0, -1.42, 0.0]),
            "rotation": list(placement.get("rotation") or [0.0, 180.0, 0.0]),
            "scale": list(placement.get("scale") or [5.10, 5.10, 5.10]),
        },
        animation={"auto_play": True, "loop": False, "speed": 1.0, "clip": "trump_openseeface_pose"},
        render={
            "renderer": renderer,
            "lighting": {
                "light_azimuth": 28.0,
                "light_elevation": 42.0,
                "direct_strength": 0.65,
                "ibl_exposure": 1.15,
                "shadow_strength": 0.42,
                "hdri_id": "studio_small_09",
            }
        },
    )
    render_settings = {
        "camera_z": float(camera.get("camera_z", 3.05) if isinstance(camera, Mapping) else 3.05),
        "preserve_scene_layout": True,
        "renderer_family": VRM_RENDERER_FAMILY,
        "render_profile": VRM_RENDER_PROFILE,
        "pbr_renderer": False,
        "ar_pbr_preview": False,
    }
    focal = float(placement.get("focal") or camera.get("focal_length_px") or max(width, height) * 0.92)
    intrinsics = {
        "fx": focal,
        "fy": focal,
        "cx": width * float(placement.get("center_x", 0.50) or 0.50),
        "cy": height * float(placement.get("center_y", 0.46) or 0.46),
    }
    renderer_id = normalize_vrm_renderer(renderer)
    if renderer_id == VRM_RENDERER_GPU:
        return module._render_full_gpu_panel(
            base,
            descriptor=descriptor,
            track=track,
            time_ms=int(time_ms),
            settings=render_settings,
            asset_path=asset_path,
        )
    return module._render_fast_vrm_contact(
        base,
        descriptor=descriptor,
        track=track,
        time_ms=int(time_ms),
        settings=render_settings,
        intrinsics=intrinsics,
    )


def _select_motion_frame(frames: tuple[Any, ...], time_ms: int) -> Any:
    if not frames:
        raise ValueError("No motion frames available")
    target = int(time_ms)
    return min(frames, key=lambda frame: abs(int(getattr(frame, "time_ms", 0)) - target))


def _autofit_avatar_rgba(image: Any, *, settings: Mapping[str, Any]) -> tuple[Any, dict[str, Any]]:
    from PIL import Image

    rgba = image.convert("RGBA")
    arr = np.asarray(rgba)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 8)
    diagnostics: dict[str, Any] = {"applied": False, "alpha_visible": bool(xs.size)}
    if not bool(xs.size):
        return rgba, diagnostics

    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    original_bbox = [x0, y0, x1, y1]
    bbox_w = max(1, x1 - x0)
    bbox_h = max(1, y1 - y0)
    placement = settings.get("placement") if isinstance(settings.get("placement"), Mapping) else {}
    camera = settings.get("camera") if isinstance(settings.get("camera"), Mapping) else {}
    framing = str(
        placement.get("framing")
        or settings.get("framing_preset")
        or camera.get("framing_preset")
        or "bust_up"
    ).casefold()
    crop_mode = str(placement.get("crop_mode") or _crop_mode_for_framing(framing)).casefold()
    if crop_mode in {"bust", "bust_up", "face_only", "head_and_shoulders"}:
        crop_ratio = max(0.35, min(1.0, float(placement.get("bust_crop_ratio", 0.58) or 0.58)))
        y1 = min(y1, y0 + max(1, int(round(bbox_h * crop_ratio))))
        bbox_h = max(1, y1 - y0)
    elif crop_mode in {"half", "half_body", "upper", "upper_body", "seated", "torso", "waist", "waist_up"}:
        crop_ratio = max(0.50, min(1.0, float(placement.get("half_body_crop_ratio", 0.82) or 0.82)))
        y1 = min(y1, y0 + max(1, int(round(bbox_h * crop_ratio))))
        bbox_h = max(1, y1 - y0)
    target_width = int(rgba.width * float(placement.get("target_width_ratio", 0.46) or 0.46))
    target_height = int(rgba.height * float(placement.get("target_height_ratio", 0.90) or 0.90))
    scale = min(target_width / bbox_w, target_height / bbox_h)
    scale = max(0.05, min(8.0, scale))
    center_x = float(placement.get("output_center_x", 0.56) or 0.56)
    bottom_y = float(placement.get("output_bottom_y", 0.98) or 0.98)

    crop = rgba.crop((x0, y0, x1, y1))
    new_size = (max(1, int(round(crop.width * scale))), max(1, int(round(crop.height * scale))))
    crop = crop.resize(new_size, Image.Resampling.LANCZOS)
    out = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    px = int(round(rgba.width * center_x - crop.width * 0.5))
    py = int(round(rgba.height * bottom_y - crop.height))
    out.alpha_composite(crop, (px, py))
    diagnostics.update(
        {
            "applied": True,
            "crop_mode": crop_mode,
            "original_bbox": original_bbox,
            "source_bbox": [x0, y0, x1, y1],
            "source_bbox_size": [bbox_w, bbox_h],
            "scale": float(scale),
            "output_position": [px, py],
            "output_size": [crop.width, crop.height],
        }
    )
    return out, diagnostics


def _crop_mode_for_framing(framing: str) -> str:
    text = str(framing or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if any(token in text for token in ("full_body", "fullbody", "head_to_toe", "standing")) or text == "full":
        return "full_body"
    if any(token in text for token in ("half_body", "upper_body", "waist", "torso", "seated")) or text in {"half", "upper"}:
        return "half_body"
    return "bust_up"


def _resolve_path(value: Any) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return ROOT / path

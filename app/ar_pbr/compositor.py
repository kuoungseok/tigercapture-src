"""Preview/export compositor contract for AR/PBR tracks.

This module is deliberately conservative. Without an enabled renderer it returns
the input frame unchanged. A deterministic synthetic renderer exists only to
exercise hook contracts before the native PBR backend lands.
"""
from __future__ import annotations

from typing import Any, Mapping

from app.ar_pbr.catcher import normalize_catcher_settings
from app.ar_pbr.depth_occlusion import apply_depth_occlusion_to_alpha, normalize_depth_frame
from app.ar_pbr.schema import normalize_ar_tracks, track_active_at, track_schema_diagnostics


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled", "synthetic", "software_pbr"}


def _renderer_name(settings: Mapping[str, Any]) -> str:
    return str(settings.get("renderer") or "").strip().casefold()


def _renderer_is_full_gpu(renderer: str) -> bool:
    return renderer in {
        "gpu",
        "opengl",
        "offscreen",
        "offscreen_gpu",
        "full_gpu",
        "native_gpu",
        "model_view_gpu",
        "full_model_view_gpu",
    }


def _renderer_is_packet(renderer: str) -> bool:
    return renderer in {
        "packet",
        "gpu_packet",
        "preview_packet",
        "packet_pbr",
    }


def _base_diagnostics(
    *,
    mode: str,
    time_ms: int,
    tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any,
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    active = [track for track in tracks if track_active_at(track, time_ms)]
    depth_shape = None
    try:
        depth_shape = tuple(int(v) for v in getattr(depth_frame, "shape", ())[:2])
    except Exception:
        depth_shape = None
    return {
        "ok": True,
        "mode": mode,
        "fallback": False,
        "time_ms": int(time_ms),
        "track_count": len(tracks),
        "active_track_count": len(active),
        "rendered_track_count": 0,
        "camera_solution_id": str((camera_solution or {}).get("id") or ""),
        "depth_available": depth_frame is not None,
        "depth_shape": list(depth_shape) if depth_shape else [],
        "settings": {
            "synthetic_renderer": bool(_truthy(settings.get("enable_synthetic_renderer")) or str(settings.get("renderer") or "") == "synthetic"),
            "software_pbr_renderer": str(settings.get("renderer") or "").casefold() in {"software_pbr", "software"},
            "full_gpu_renderer": _renderer_is_full_gpu(_renderer_name(settings)),
            "packet_renderer": _renderer_is_packet(_renderer_name(settings)),
            "quality": str(settings.get("quality") or "preview"),
        },
        "schema": track_schema_diagnostics(tracks),
        "warnings": [],
        "errors": [],
    }


def _noop(base_frame: Any, diagnostics: dict[str, Any], reason: str) -> tuple[Any, dict[str, Any]]:
    diagnostics["mode"] = "noop"
    diagnostics["fallback"] = True
    diagnostics["warnings"].append(reason)
    return base_frame, diagnostics


def _frame_to_pil_rgba(base_frame: Any):
    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:
        return None, "", f"missing image dependency: {type(exc).__name__}"

    if isinstance(base_frame, Image.Image):
        return base_frame.convert("RGBA"), "pil", ""
    try:
        arr = np.asarray(base_frame)
    except Exception:
        return None, "", "unsupported base_frame type"
    if arr.ndim != 3 or arr.shape[2] not in {3, 4}:
        return None, "", "base_frame must be HxWx3 or HxWx4"
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.shape[2] == 3:
        return Image.fromarray(arr, "RGB").convert("RGBA"), "numpy_rgb", ""
    return Image.fromarray(arr, "RGBA"), "numpy_rgba", ""


def _pil_to_original_kind(image, kind: str, original: Any):
    if kind == "pil":
        return image.convert("RGBA")
    try:
        import numpy as np
        arr = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        if kind == "numpy_rgb":
            return arr[:, :, :3].copy()
        return arr.copy()
    except Exception:
        return original


def _normalize_depth(depth_frame: Any, width: int, height: int):
    return normalize_depth_frame(depth_frame, width, height)


def _track_color(track: Mapping[str, Any], settings: Mapping[str, Any]) -> tuple[int, int, int, int]:
    raw = settings.get("synthetic_color")
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        vals = list(raw) + [255]
        return tuple(max(0, min(255, int(v))) for v in vals[:4])  # type: ignore[return-value]
    material = track.get("material") if isinstance(track.get("material"), Mapping) else {}
    color = material.get("base_color") if isinstance(material, Mapping) else None
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        vals = list(color) + [1.0]
        return tuple(max(0, min(255, int(round(float(v) * 255.0)))) for v in vals[:4])  # type: ignore[return-value]
    return (240, 112, 64, 230)


def _apply_color_match(color: tuple[int, int, int, int], track: Mapping[str, Any]) -> tuple[int, int, int, int]:
    match = track.get("color_match") if isinstance(track.get("color_match"), Mapping) else {}
    exposure = float(match.get("exposure", 0.0) or 0.0) if isinstance(match, Mapping) else 0.0
    contrast = float(match.get("contrast", 1.0) or 1.0) if isinstance(match, Mapping) else 1.0
    gain = 2.0 ** exposure
    rgb = []
    for value in color[:3]:
        x = ((float(value) / 255.0 - 0.5) * contrast + 0.5) * gain
        rgb.append(max(0, min(255, int(round(x * 255.0)))))
    return (rgb[0], rgb[1], rgb[2], color[3])


def _screen_rect(track: Mapping[str, Any], width: int, height: int) -> tuple[int, int, int, int, float]:
    transform = track.get("transform") if isinstance(track.get("transform"), Mapping) else {}
    pos = transform.get("position", [0.0, 0.0, 0.0]) if isinstance(transform, Mapping) else [0.0, 0.0, 0.0]
    scale = transform.get("scale", [1.0, 1.0, 1.0]) if isinstance(transform, Mapping) else [1.0, 1.0, 1.0]
    px = float(pos[0] if len(pos) > 0 else 0.0)
    py = float(pos[1] if len(pos) > 1 else 0.0)
    pz = float(pos[2] if len(pos) > 2 else 0.0)
    sx = max(0.05, float(scale[0] if len(scale) > 0 else 1.0))
    sy = max(0.05, float(scale[1] if len(scale) > 1 else 1.0))
    cx = int(round(width * (0.5 + px * 0.25)))
    cy = int(round(height * (0.5 - py * 0.25)))
    rw = max(2, int(round(min(width, height) * 0.22 * sx)))
    rh = max(2, int(round(min(width, height) * 0.22 * sy)))
    x0 = max(0, cx - rw // 2)
    y0 = max(0, cy - rh // 2)
    x1 = min(width, cx + rw // 2)
    y1 = min(height, cy + rh // 2)
    object_depth = max(0.0, min(1.0, 0.5 + pz * 0.1))
    return x0, y0, x1, y1, object_depth


def _render_synthetic(
    base_frame: Any,
    *,
    time_ms: int,
    tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any,
    settings: Mapping[str, Any],
    diagnostics: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    del camera_solution
    image, kind, error = _frame_to_pil_rgba(base_frame)
    if image is None:
        return _noop(base_frame, diagnostics, error or "unsupported frame")

    try:
        from PIL import Image, ImageDraw, ImageFilter
        import numpy as np
    except Exception as exc:
        return _noop(base_frame, diagnostics, f"missing synthetic renderer dependency: {type(exc).__name__}")

    width, height = image.size
    depth = _normalize_depth(depth_frame, width, height)
    active = [track for track in tracks if track_active_at(track, time_ms)]
    rendered = 0
    shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    object_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer, "RGBA")
    object_draw = ImageDraw.Draw(object_layer, "RGBA")

    for track in active:
        x0, y0, x1, y1, object_depth = _screen_rect(track, width, height)
        if x1 <= x0 or y1 <= y0:
            continue
        render = track.get("render") if isinstance(track.get("render"), Mapping) else {}
        lighting = render.get("lighting") if isinstance(render.get("lighting"), Mapping) else {}
        catcher = normalize_catcher_settings(lighting)
        shadow_catcher = catcher["shadow_catcher"]
        reflection_catcher = catcher["reflection_catcher"]
        if track.get("shadow_catcher"):
            shadow_h = max(2, int((y1 - y0) * 0.24))
            shadow_box = (
                x0,
                min(height - 1, y1 - shadow_h // 2),
                x1,
                min(height, y1 + shadow_h),
            )
            shadow_alpha = int(round(84 * float(shadow_catcher["opacity"])))
            matte_alpha = int(round(255 * float(shadow_catcher["matte_alpha"]) * 0.035))
            shadow_draw.ellipse(shadow_box, fill=(0, 0, 0, max(shadow_alpha, matte_alpha)))
        if track.get("reflection_catcher"):
            refl_h = max(1, (y1 - y0) // 2)
            reflection_alpha = int(round(108 * float(reflection_catcher["opacity"])))
            object_draw.rectangle(
                (x0, y1, x1, min(height, y1 + refl_h)),
                fill=(180, 180, 200, max(0, min(255, reflection_alpha))),
            )

        color = _apply_color_match(_track_color(track, settings), track)
        if track.get("occlusion") and depth is not None:
            mask = Image.new("L", image.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rectangle((x0, y0, x1, y1), fill=color[3])
            mask_arr = np.asarray(mask, dtype=np.uint8).copy()
            region = depth[y0:y1, x0:x1]
            if region.size:
                mask_arr[y0:y1, x0:x1], _diag = apply_depth_occlusion_to_alpha(
                    mask_arr[y0:y1, x0:x1],
                    region,
                    object_depth=object_depth,
                    settings=settings,
                )
            object_mask = Image.fromarray(mask_arr, "L")
            fill = Image.new("RGBA", image.size, color)
            object_layer.alpha_composite(Image.composite(fill, Image.new("RGBA", image.size, (0, 0, 0, 0)), object_mask))
        else:
            object_draw.rectangle((x0, y0, x1, y1), fill=color)
        rendered += 1

    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=max(0.0, float(settings.get("shadow_blur", 3.0) or 3.0))))
    image.alpha_composite(shadow_layer)
    image.alpha_composite(object_layer)
    diagnostics["rendered_track_count"] = rendered
    diagnostics["mode"] = "synthetic"
    diagnostics["synthetic_renderer"] = {
        "object": "placeholder_rect",
        "shadow_catcher": True,
        "depth_occlusion": depth is not None,
    }
    return _pil_to_original_kind(image, kind, base_frame), diagnostics


def _render_full_gpu_or_packet(
    base_frame: Any,
    *,
    time_ms: int,
    tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any,
    settings: Mapping[str, Any],
    diagnostics: dict[str, Any],
    quality: str,
) -> tuple[Any, dict[str, Any]]:
    try:
        from app.ar_pbr.export_packet_renderer import render_offscreen_gpu_export_frame

        out, render_diag = render_offscreen_gpu_export_frame(
            base_frame,
            time_ms=int(time_ms),
            ar_tracks=list(tracks or []),
            camera_solution=camera_solution,
            depth_frame=depth_frame,
            settings={**dict(settings), "quality": quality},
        )
        merged = dict(diagnostics)
        merged.update(dict(render_diag or {}))
        merged["quality"] = quality
        merged["requested_renderer"] = "full_gpu"
        if bool((render_diag or {}).get("fallback")):
            merged.setdefault("warnings", [])
            if "full GPU renderer fell back to packet renderer" not in merged["warnings"]:
                merged["warnings"].append("full GPU renderer fell back to packet renderer")
        return out, merged
    except Exception as exc:
        diagnostics["ok"] = False
        diagnostics["fallback"] = True
        diagnostics["mode"] = "full_model_view_gpu_export_service"
        diagnostics["requested_renderer"] = "full_gpu"
        diagnostics["errors"].append(f"{type(exc).__name__}: {exc}")
        return base_frame, diagnostics


def _render_packet(
    base_frame: Any,
    *,
    time_ms: int,
    tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any,
    settings: Mapping[str, Any],
    diagnostics: dict[str, Any],
    quality: str,
) -> tuple[Any, dict[str, Any]]:
    try:
        from app.ar_pbr.export_packet_renderer import render_gpu_packet_export_frame

        out, render_diag = render_gpu_packet_export_frame(
            base_frame,
            time_ms=int(time_ms),
            ar_tracks=list(tracks or []),
            camera_solution=camera_solution,
            depth_frame=depth_frame,
            settings={**dict(settings), "quality": quality},
        )
        merged = dict(diagnostics)
        merged.update(dict(render_diag or {}))
        merged["quality"] = quality
        merged["requested_renderer"] = "packet"
        return out, merged
    except Exception as exc:
        diagnostics["ok"] = False
        diagnostics["fallback"] = True
        diagnostics["mode"] = "gpu_packet_export"
        diagnostics["requested_renderer"] = "packet"
        diagnostics["errors"].append(f"{type(exc).__name__}: {exc}")
        return base_frame, diagnostics


def _composite_frame(
    base_frame: Any,
    *,
    time_ms: int,
    ar_tracks: list[dict[str, Any]],
    camera_solution: dict | None,
    depth_frame: Any = None,
    settings: dict | None = None,
    quality: str,
) -> tuple[Any, dict[str, Any]]:
    settings_map: Mapping[str, Any] = settings or {}
    tracks = normalize_ar_tracks(ar_tracks)
    diagnostics = _base_diagnostics(
        mode="noop",
        time_ms=int(time_ms),
        tracks=tracks,
        camera_solution=camera_solution,
        depth_frame=depth_frame,
        settings={**dict(settings_map), "quality": quality},
    )
    if not tracks:
        return _noop(base_frame, diagnostics, "no ar_pbr tracks")
    if not any(track_active_at(track, int(time_ms)) for track in tracks):
        return _noop(base_frame, diagnostics, "no active ar_pbr tracks")
    renderer = _renderer_name(settings_map)
    synthetic_enabled = _truthy(settings_map.get("enable_synthetic_renderer")) or renderer == "synthetic"
    software_enabled = renderer in {"software_pbr", "software"}
    full_gpu_enabled = _renderer_is_full_gpu(renderer)
    packet_enabled = _renderer_is_packet(renderer)
    if not (synthetic_enabled or software_enabled or full_gpu_enabled or packet_enabled):
        return _noop(base_frame, diagnostics, "native ar_pbr renderer unavailable")
    try:
        if full_gpu_enabled:
            return _render_full_gpu_or_packet(
                base_frame,
                time_ms=int(time_ms),
                tracks=tracks,
                camera_solution=camera_solution,
                depth_frame=depth_frame,
                settings=settings_map,
                diagnostics=diagnostics,
                quality=quality,
            )
        if packet_enabled:
            return _render_packet(
                base_frame,
                time_ms=int(time_ms),
                tracks=tracks,
                camera_solution=camera_solution,
                depth_frame=depth_frame,
                settings=settings_map,
                diagnostics=diagnostics,
                quality=quality,
            )
        if software_enabled:
            from app.ar_pbr.software_renderer import render_software_pbr_frame

            active_tracks = [track for track in tracks if track_active_at(track, int(time_ms))]
            return render_software_pbr_frame(
                base_frame,
                time_ms=int(time_ms),
                tracks=active_tracks,
                camera_solution=camera_solution,
                depth_frame=depth_frame,
                settings={**dict(settings_map), "quality": quality},
                diagnostics=diagnostics,
            )
        return _render_synthetic(
            base_frame,
            time_ms=int(time_ms),
            tracks=tracks,
            camera_solution=camera_solution,
            depth_frame=depth_frame,
            settings={**dict(settings_map), "quality": quality},
            diagnostics=diagnostics,
        )
    except Exception as exc:
        diagnostics["ok"] = False
        diagnostics["fallback"] = True
        diagnostics["errors"].append(f"{type(exc).__name__}: {exc}")
        return base_frame, diagnostics


def composite_preview_frame(
    base_frame: Any,
    time_ms: int,
    ar_tracks: list[dict],
    camera_solution: dict | None,
    depth_frame: Any = None,
    settings: dict | None = None,
) -> tuple[Any, dict]:
    """Return composited preview frame plus diagnostics."""
    return _composite_frame(
        base_frame,
        time_ms=time_ms,
        ar_tracks=ar_tracks,
        camera_solution=camera_solution,
        depth_frame=depth_frame,
        settings=settings,
        quality="preview",
    )


def composite_export_frame(
    base_frame: Any,
    time_ms: int,
    ar_tracks: list[dict],
    camera_solution: dict | None,
    depth_frame: Any = None,
    settings: dict | None = None,
) -> tuple[Any, dict]:
    """Return composited export frame plus diagnostics."""
    return _composite_frame(
        base_frame,
        time_ms=time_ms,
        ar_tracks=ar_tracks,
        camera_solution=camera_solution,
        depth_frame=depth_frame,
        settings=settings,
        quality="export",
    )

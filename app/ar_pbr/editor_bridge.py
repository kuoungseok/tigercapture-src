"""Thin AR/PBR helpers shared by the video editor window."""
from __future__ import annotations

from typing import Any


DEFAULT_LIGHTING_SETTINGS: dict[str, Any] = {
    "render_profile": "authored",
    "ibl_exposure": 1.1,
    "ibl_rotation": 0.0,
    "render_mode": "ibl_realtime",
    "show_environment_background": True,
    "environment_visibility": {
        "camera_visible": True,
        "reflection_visible": True,
        "diffuse_visible": True,
        "refraction_visible": True,
        "background_output": "environment",
    },
    "light_azimuth": 45.0,
    "light_elevation": 45.0,
    "direct_strength": 0.42,
    "shadow_strength": 0.45,
    "shadow_light_type": "directional",
    "shadow_filter": "pcf",
    "shadow_map_size": 1024,
    "shadow_pcf_radius": 1.35,
    "shadow_pcss_blocker_radius": 2.5,
    "shadow_bias": 0.002,
    "shadow_normal_bias": 0.002,
    "shadow_spot_inner_angle": 28.0,
    "shadow_spot_outer_angle": 45.0,
    "shadow_catcher_opacity": 0.72,
    "shadow_catcher_softness": 0.55,
    "shadow_catcher_matte_alpha": 0.0,
    "reflection_catcher_opacity": 0.35,
    "reflection_catcher_roughness": 0.5,
    "reflection_catcher_softness": 0.45,
    "contact_reflection_strength": 0.32,
    "contact_reflection_falloff": 0.58,
    "tone_mapping": "aces",
    "tone_exposure": 0.0,
    "tone_white_balance": 6500.0,
    "tone_gamma": 2.2,
    "self_shadow_strength": 0.45,
    "ground_height": -0.52,
    "surface_override_strength": 0.0,
    "surface_roughness": 0.45,
    "surface_metallic": 0.0,
    "surface_reflectance": 0.5,
    "clearcoat_strength": 0.0,
    "clearcoat_roughness": 0.12,
    "clearcoat_ior": 1.5,
}


def preview_registry(owner: Any) -> dict:
    registry = getattr(owner, "_ar_pbr_preview_window_registry", None)
    if not isinstance(registry, dict):
        registry = {}
        owner._ar_pbr_preview_window_registry = registry
    return registry


def reuse_preview_window(owner: Any, key: str):
    registry = preview_registry(owner)
    key = str(key)
    preview = registry.get(key)
    is_valid = getattr(owner, "_qt_object_valid", None)
    preview_valid = bool(is_valid(preview)) if callable(is_valid) else preview is not None
    if preview is not None and preview_valid:
        try:
            preview.show()
            preview.raise_()
            preview.activateWindow()
            return preview
        except Exception:
            pass
    registry.pop(key, None)
    return None


def remember_preview_window(owner: Any, key: str, preview: Any) -> None:
    registry = preview_registry(owner)
    key = str(key)
    registry[key] = preview
    windows = getattr(owner, "_ar_pbr_preview_windows", None)
    if windows is None:
        windows = []
        owner._ar_pbr_preview_windows = windows
    windows.append(preview)

    def _forget(*_args) -> None:
        registry.pop(key, None)
        try:
            windows.remove(preview)
        except ValueError:
            pass

    destroyed = getattr(preview, "destroyed", None)
    connect = getattr(destroyed, "connect", None)
    if callable(connect):
        connect(_forget)


def track_lighting_settings(track: dict) -> dict:
    try:
        from app.ar_pbr.schema import normalize_lighting_settings

        render = track.get("render") if isinstance(track, dict) else {}
        lighting = render.get("lighting") if isinstance(render, dict) else {}
        out = normalize_lighting_settings(lighting)
        profile = str(render.get("render_profile") or "authored").strip().casefold() if isinstance(render, dict) else "authored"
        out["render_profile"] = profile if profile in {"authored", "vrm_mtoon", "marmoset_pbr"} else "authored"
        return out
    except Exception:
        return dict(DEFAULT_LIGHTING_SETTINGS)


def apply_lighting_settings_to_track(track: dict, settings: dict) -> None:
    try:
        from app.ar_pbr.schema import normalize_lighting_settings

        lighting = normalize_lighting_settings(settings)
    except Exception:
        lighting = dict(settings or {})
    render = track.setdefault("render", {})
    if isinstance(render, dict):
        render["lighting"] = lighting
        profile = str((settings or {}).get("render_profile") or render.get("render_profile") or "authored").strip().casefold()
        render["render_profile"] = profile if profile in {"authored", "vrm_mtoon", "marmoset_pbr"} else "authored"
        render.setdefault("shadow_quality", "preview")
        render.setdefault("reflection_quality", "preview")
    try:
        track["shadow_catcher"] = float(lighting.get("shadow_strength", 0.0) or 0.0) > 0.001
    except Exception:
        pass


def sync_tracks_to_player(owner: Any) -> None:
    player = getattr(owner, "_player", None)
    if player is not None and hasattr(player, "set_ar_pbr_tracks"):
        player.set_ar_pbr_tracks(getattr(owner, "_ar_pbr_tracks", []) or [])


def active_tracks_at_playhead(owner: Any) -> list[dict]:
    tracks = getattr(owner, "_ar_pbr_tracks", []) or []
    if not tracks:
        return []
    try:
        time_ms = int(owner._player.position())
    except Exception:
        time_ms = 0
    try:
        from app.ar_pbr.schema import track_active_at

        return [track for track in tracks if track_active_at(track, time_ms)]
    except Exception:
        active: list[dict] = []
        for track in tracks:
            try:
                start_ms = int(track.get("start_ms", 0) or 0)
                end_ms = int(track.get("end_ms", start_ms + 1) or 0)
                if start_ms <= time_ms < end_ms:
                    active.append(track)
            except Exception:
                continue
        return active


def clamp01(value: float) -> float:
    from app.ar_pbr.gizmo import clamp01 as _clamp01

    return _clamp01(value)


def runtime_image_point_for_track(owner: Any, track_id: str) -> tuple[float, float] | None:
    from app.ar_pbr.editor_gizmo_bridge import runtime_image_point_for_track as _runtime_image_point_for_track

    return _runtime_image_point_for_track(owner, track_id)


def track_center_norm(owner: Any, track: dict) -> tuple[float, float]:
    from app.ar_pbr.gizmo import track_center_norm as _track_center_norm

    track_id = str(track.get("id") or "") if isinstance(track, dict) else ""
    drag = getattr(owner, "_ar_pbr_gizmo_drag", None)
    drag_track_id = str(drag.get("track_id") or "") if isinstance(drag, dict) else ""
    if track_id and drag_track_id != track_id:
        runtime_point = runtime_image_point_for_track(owner, track_id)
        if runtime_point is not None:
            return _track_center_norm(track, runtime_point)
    return _track_center_norm(track)


def set_track_center_norm(track: dict, x_norm: float, y_norm: float) -> None:
    from app.ar_pbr.gizmo import set_track_center_norm as _set_track_center_norm

    _set_track_center_norm(track, x_norm, y_norm)


def track_uniform_scale(track: dict) -> float:
    from app.ar_pbr.gizmo import track_uniform_scale as _track_uniform_scale

    return _track_uniform_scale(track)


def set_track_uniform_scale(track: dict, value: float) -> None:
    from app.ar_pbr.gizmo import set_track_uniform_scale as _set_track_uniform_scale

    _set_track_uniform_scale(track, value)


def track_scale_values(track: dict) -> list[float]:
    from app.ar_pbr.gizmo import track_scale_values as _track_scale_values

    return _track_scale_values(track)


def set_track_axis_scale(track: dict, axis: int, value: float) -> None:
    from app.ar_pbr.gizmo import set_track_axis_scale as _set_track_axis_scale

    _set_track_axis_scale(track, axis, value)


def track_position_z(track: dict) -> float:
    from app.ar_pbr.gizmo import track_position_z as _track_position_z

    return _track_position_z(track)


def set_track_position_z(track: dict, value: float) -> None:
    from app.ar_pbr.gizmo import set_track_position_z as _set_track_position_z

    _set_track_position_z(track, value)


def track_rotation_value(track: dict, axis: int) -> float:
    from app.ar_pbr.gizmo import track_rotation_value as _track_rotation_value

    return _track_rotation_value(track, axis)


def set_track_rotation_value(track: dict, axis: int, value: float) -> None:
    from app.ar_pbr.gizmo import set_track_rotation_value as _set_track_rotation_value

    _set_track_rotation_value(track, axis, value)


def track_yaw(track: dict) -> float:
    return track_rotation_value(track, 1)


def set_track_yaw(track: dict, value: float) -> None:
    set_track_rotation_value(track, 1, value)


def track_rotation_values(track: dict) -> list[float]:
    from app.ar_pbr.gizmo import track_rotation_values as _track_rotation_values

    return _track_rotation_values(track)


def rotate_vec3(vec: tuple[float, float, float], rotation_deg: list[float]) -> tuple[float, float, float]:
    from app.ar_pbr.gizmo import rotate_vec3 as _rotate_vec3

    return _rotate_vec3(vec, rotation_deg)


def project_gizmo_point3(vec: tuple[float, float, float]) -> tuple[float, float]:
    from app.ar_pbr.gizmo import project_gizmo_point3 as _project_gizmo_point3

    return _project_gizmo_point3(vec)


def project_gizmo_vec3(vec: tuple[float, float, float]) -> tuple[float, float]:
    from app.ar_pbr.gizmo import project_gizmo_vec3 as _project_gizmo_vec3

    return _project_gizmo_vec3(vec)


def project_gizmo_axis(
    axis: tuple[float, float, float],
    rotation_deg: list[float],
) -> tuple[tuple[float, float], float]:
    from app.ar_pbr.gizmo import project_gizmo_axis as _project_gizmo_axis

    return _project_gizmo_axis(axis, rotation_deg)


def gizmo_ring_points(
    axis_name: str,
    rotation_deg: list[float],
    cx: float,
    cy: float,
    radius: float,
    *,
    segments: int = 72,
) -> list[tuple[float, float]]:
    from app.ar_pbr.gizmo import gizmo_ring_points as _gizmo_ring_points

    return _gizmo_ring_points(axis_name, rotation_deg, cx, cy, radius, segments=segments)


def gizmo_geometry(owner: Any, track: dict, canvas_w: int, canvas_h: int) -> dict:
    from app.ar_pbr.gizmo import gizmo_geometry as _gizmo_geometry

    return _gizmo_geometry(track, canvas_w, canvas_h, center_norm=track_center_norm(owner, track))


def distance_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    from app.ar_pbr.gizmo import distance_to_segment as _distance_to_segment

    return _distance_to_segment(px, py, ax, ay, bx, by)


def ellipse_ring_hit(px: float, py: float, cx: float, cy: float, rx: float, ry: float, tol_px: float) -> bool:
    from app.ar_pbr.gizmo import ellipse_ring_hit as _ellipse_ring_hit

    return _ellipse_ring_hit(px, py, cx, cy, rx, ry, tol_px)


def distance_to_polyline(px: float, py: float, points: list[tuple[float, float]]) -> float:
    from app.ar_pbr.gizmo import distance_to_polyline as _distance_to_polyline

    return _distance_to_polyline(px, py, points)


def track_lighting_dict(track: dict) -> dict:
    from app.ar_pbr.gizmo import track_lighting_dict as _track_lighting_dict

    return _track_lighting_dict(track)


def axis_index(axis_name: str) -> int:
    from app.ar_pbr.gizmo import axis_index as _axis_index

    return _axis_index(axis_name)

"""Project-facing helpers for AR/PBR object placement."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ar_pbr.catcher import (
    DEFAULT_CONTACT_REFLECTION_FALLOFF,
    DEFAULT_CONTACT_REFLECTION_STRENGTH,
    DEFAULT_REFLECTION_CATCHER_OPACITY,
    DEFAULT_REFLECTION_CATCHER_ROUGHNESS,
    DEFAULT_REFLECTION_CATCHER_SOFTNESS,
    DEFAULT_SHADOW_CATCHER_MATTE_ALPHA,
    DEFAULT_SHADOW_CATCHER_OPACITY,
    DEFAULT_SHADOW_CATCHER_SOFTNESS,
)
from app.ar_pbr.depth_occlusion import (
    DEFAULT_DEPTH_EDGE_GLOW_COLOR,
    DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX,
    DEFAULT_DEPTH_EDGE_GLOW_STRENGTH,
)
from app.ar_pbr.schema import normalize_ar_track
from app.ar_pbr.shadow import DEFAULT_SHADOW_STRENGTH


DEFAULT_PREVIEW_DURATION_MS = 10_000
DEFAULT_PREVIEW_SCALE = 3.25


def is_ar_pbr_asset_path(path: str | Path) -> bool:
    try:
        from app.ar_pbr.schema import is_supported_asset_path

        return is_supported_asset_path(path)
    except Exception:
        return False


def transform_position_from_frame_point(
    x_norm: float,
    y_norm: float,
    *,
    z: float = 0.0,
) -> list[float]:
    """Map a normalized frame point to the compositor's screen transform.

    The current preview compositor interprets transform X/Y as quarter-frame
    offsets from center. Keeping this mapping here avoids duplicating that math
    in editor UI code.
    """
    x = max(0.0, min(1.0, float(x_norm)))
    y = max(0.0, min(1.0, float(y_norm)))
    return [
        (x - 0.5) * 4.0,
        (0.5 - y) * 4.0,
        float(z),
    ]


def create_preview_ar_track(
    asset_path: str | Path,
    *,
    track_id: str,
    start_ms: int,
    end_ms: int | None = None,
    duration_ms: int = DEFAULT_PREVIEW_DURATION_MS,
    image_point: tuple[float, float] | list[float] | None = None,
    scale: float = DEFAULT_PREVIEW_SCALE,
) -> dict[str, Any]:
    start = max(0, int(start_ms))
    if end_ms is None:
        end = start + max(1, int(duration_ms))
    else:
        end = max(start + 1, int(end_ms))
    if image_point is None:
        image_point = (0.5, 0.62)
    x_norm = max(0.0, min(1.0, float(image_point[0])))
    y_norm = max(0.0, min(1.0, float(image_point[1])))
    uniform_scale = max(0.0001, float(scale))
    return normalize_ar_track({
        "id": str(track_id),
        "type": "ar_pbr_object",
        "asset_path": str(Path(asset_path).expanduser().resolve()),
        "start_ms": start,
        "end_ms": end,
        "transform": {
            "position": transform_position_from_frame_point(x_norm, y_norm),
            "rotation": [0.0, 18.0, 0.0],
            "scale": [uniform_scale, uniform_scale, uniform_scale],
        },
        "placement": {
            "mode": "manual",
            "coordinate_space": "frame_normalized",
            "image_point": [x_norm, y_norm],
            "surface_offset": 0.0,
        },
        "animation": {
            "auto_play": True,
            "loop": True,
            "clip": "",
            "speed": 1.0,
            "start_offset_ms": 0.0,
        },
        "occlusion": False,
        "shadow_catcher": True,
        "reflection_catcher": False,
        "color_match": {
            "exposure": 0.0,
            "white_balance": 6500.0,
            "contrast": 1.0,
        },
        "render": {
            "shadow_quality": "preview",
            "reflection_quality": "preview",
            "lighting": {
                "hdri_id": "wide_street_01",
                "hdri_path": "",
                "ibl_exposure": 1.1,
                "ibl_rotation": 0.0,
                "light_azimuth": 45.0,
                "light_elevation": 45.0,
                "direct_strength": 0.42,
                "shadow_strength": DEFAULT_SHADOW_STRENGTH,
                "shadow_light_type": "directional",
                "shadow_filter": "pcf",
                "shadow_map_size": 1024,
                "shadow_pcf_radius": 1.35,
                "shadow_pcss_blocker_radius": 2.5,
                "shadow_bias": 0.002,
                "shadow_normal_bias": 0.002,
                "shadow_spot_inner_angle": 28.0,
                "shadow_spot_outer_angle": 45.0,
                "shadow_catcher_opacity": DEFAULT_SHADOW_CATCHER_OPACITY,
                "shadow_catcher_softness": DEFAULT_SHADOW_CATCHER_SOFTNESS,
                "shadow_catcher_matte_alpha": DEFAULT_SHADOW_CATCHER_MATTE_ALPHA,
                "reflection_catcher_opacity": DEFAULT_REFLECTION_CATCHER_OPACITY,
                "reflection_catcher_roughness": DEFAULT_REFLECTION_CATCHER_ROUGHNESS,
                "reflection_catcher_softness": DEFAULT_REFLECTION_CATCHER_SOFTNESS,
                "contact_reflection_strength": DEFAULT_CONTACT_REFLECTION_STRENGTH,
                "contact_reflection_falloff": DEFAULT_CONTACT_REFLECTION_FALLOFF,
                "tone_mapping": "aces",
                "tone_exposure": 0.0,
                "tone_white_balance": 6500.0,
                "tone_gamma": 2.2,
                "depth_edge_glow_enabled": False,
                "depth_edge_glow_strength": DEFAULT_DEPTH_EDGE_GLOW_STRENGTH,
                "depth_edge_glow_radius_px": DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX,
                "depth_edge_glow_color": list(DEFAULT_DEPTH_EDGE_GLOW_COLOR),
                "self_shadow_strength": 0.45,
                "ground_height": -0.52,
            },
        },
    })

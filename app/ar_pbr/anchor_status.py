"""Small UI-facing status helpers for AR/PBR placement anchoring."""
from __future__ import annotations

from typing import Any, Mapping


ANCHOR_PLACEMENT_MODES = frozenset({
    "road_plane_anchor",
    "plane_anchor",
    "screen_plane",
    "scene_anchor",
})


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def ar_pbr_anchor_status(track: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a compact display status for an AR/PBR object track.

    This intentionally reports track metadata only. It must not trigger depth
    estimation, scene solving, template matching, or renderer work.
    """

    data = _as_mapping(track)
    placement = _as_mapping(data.get("placement"))
    tracking = _as_mapping(placement.get("tracking"))
    mode = str(placement.get("mode") or "manual").strip().lower()
    is_anchored = mode in ANCHOR_PLACEMENT_MODES
    tracking_enabled = is_anchored and bool(tracking.get("enabled", False))

    if tracking_enabled:
        badge = "TRK"
        tone = "tracking"
        color = "#4DBE91"
        label = "Scene anchor tracking"
    elif is_anchored:
        badge = "ANCH"
        tone = "anchored"
        color = "#5CA9E6"
        label = "Depth/plane anchor"
    else:
        badge = "3D"
        tone = "manual"
        color = "#669EFF"
        label = "Manual 3D placement"

    return {
        "schema": "tigerstudio.ar_pbr.anchor_status.v1",
        "mode": mode,
        "anchored": is_anchored,
        "tracking_enabled": tracking_enabled,
        "badge": badge,
        "tone": tone,
        "color": color,
        "label": label,
    }


__all__ = ["ANCHOR_PLACEMENT_MODES", "ar_pbr_anchor_status"]

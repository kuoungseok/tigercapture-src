"""View-model contract for a VTuber broadcast studio workspace."""
from __future__ import annotations

from typing import Any, Mapping

from app.vtuber.performance_source import (
    PERFORMANCE_SOURCE_BADGE,
    PERFORMANCE_SOURCE_LABEL,
    program_output_contract,
)
from app.vtuber.vrm_renderer import (
    VRM_RENDER_PROFILE,
    VRM_RENDERER_FAMILY,
)


VTUBER_BROADCAST_STUDIO_SCHEMA = "tigerstudio.vtuber.broadcast_studio_layout.v1"


def build_vtuber_broadcast_studio_layout(
    *,
    source_name: str,
    avatar_name: str,
    avatar_target: Mapping[str, Any] | None = None,
    framing_control: Mapping[str, Any] | None = None,
    tracking: Mapping[str, Any] | None = None,
    capture_ready: bool | None = None,
    bridge_status: Mapping[str, Any] | None = None,
    timeline_tracks: list[Any] | None = None,
    time_ms: int = 0,
    program_contract: Mapping[str, Any] | None = None,
    live_target: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the studio view contract without depending on Qt or renderer state."""
    control = dict(framing_control or {})
    final_view = dict((control.get("final") or {}).get("model_view") or {})
    offset = dict(control.get("user_offset") or {})
    tracking_data = dict(tracking or {})
    contract = dict(program_contract or program_output_contract(timeline_tracks or [], int(time_ms)))
    background = dict(contract.get("program_background") or {})
    performance = dict(contract.get("performance_source") or {})
    bridge = _bridge_status_summary(bridge_status)
    target = _live_target_summary(live_target)
    avatar = _avatar_target_summary(avatar_target, avatar_name)
    performance_source_name = str(performance.get("clip_label") or source_name or PERFORMANCE_SOURCE_LABEL)
    avatar_renderer = _avatar_renderer_summary(avatar, bridge)
    return {
        "schema": VTUBER_BROADCAST_STUDIO_SCHEMA,
        "mode": "broadcast_studio",
        "source_name": performance_source_name,
        "performance_source_name": performance_source_name,
        "avatar_name": str(avatar_name or "Avatar"),
        "avatar_target": avatar,
        "capture_ready": capture_ready,
        "regions": [
            {
                "id": "program",
                "title": "Program Output",
                "role": "broadcast_output",
                "layout": "top",
                "sources": ["program_background", avatar_renderer["source_id"], "lower_occlusion"],
            },
            {
                "id": "source_tracking",
                "title": "Source Tracking",
                "role": "tracking_monitor",
                "layout": "bottom_left",
                "overlays": ["face_box", "subject_box", "confidence"],
                "source_role": "performance_source",
            },
            {
                "id": "avatar_mapping",
                "title": "Avatar Mapping",
                "role": "mapping_monitor",
                "layout": "bottom_center",
                "overlays": ["desk_line", "final_framing", "pose_state"],
                "renderer_family": avatar_renderer["family"],
                "render_profile": avatar_renderer["render_profile"],
            },
            {
                "id": "controls",
                "title": "Studio Controls",
                "role": "operator_controls",
                "layout": "bottom_right",
                "controls": [
                    _control("pan_x", "Horizontal", offset.get("pan_x", 0.0)),
                    _control("pan_y", "Vertical", offset.get("pan_y", 0.0)),
                    _control("zoom_scale", "Zoom", offset.get("zoom_scale", 1.0)),
                    _control("lower_occlusion_y_delta", "Desk line", offset.get("lower_occlusion_y_delta", 0.0)),
                    _toggle("lock_framing", "Lock framing", False),
                ],
            },
        ],
        "program": {
            "composition": "program_background_plus_avatar",
            "background": background,
            "performance_source_direct_output": False,
            "avatar_target": {
                "id": avatar["id"],
                "kind": avatar["kind"],
                "name": avatar["name"],
                "program_output": avatar["program_output"],
                "live_target_output": avatar["live_target_output"],
                "renderer_family": avatar["renderer_family"],
                "render_profile": avatar["render_profile"],
                "pbr_renderer": avatar["pbr_renderer"],
            },
            "model_view": final_view,
            "lower_occlusion_y": final_view.get("lower_occlusion_y"),
            "safe_output": True,
            "renderer": avatar_renderer["renderer"],
            "renderer_family": avatar_renderer["family"],
            "render_profile": avatar_renderer["render_profile"],
            "pbr_renderer": False,
            "ar_pbr_preview": False,
            "fallback": bridge["fallback"],
        },
        "performance_source": {
            "label": PERFORMANCE_SOURCE_LABEL,
            "badge": PERFORMANCE_SOURCE_BADGE,
            "active": bool(performance.get("active", False)),
            "name": performance_source_name,
            "source_path": str(performance.get("source_path") or ""),
            "program_output": False,
        },
        "tracking": {
            "confidence": tracking_data.get("confidence"),
            "face_box": tracking_data.get("face_box"),
            "subject_box": tracking_data.get("subject_box"),
            "subject_source": tracking_data.get("subject_source"),
        },
        "operator_actions": [
            {"id": "go_live", "label": _live_target_primary_action_label(target), "kind": "primary", "target_id": target["target_id"]},
            {"id": "record", "label": "Record", "kind": "secondary"},
            {"id": "reset_to_auto", "label": "Reset Auto", "kind": "secondary"},
            {"id": "lock_framing", "label": "Lock", "kind": "toggle"},
        ],
        "live_target": target,
        "bridge": bridge,
        "diagnostics": {
            "automatic_framing_preserved": bool(control.get("automatic")),
            "final_framing_available": bool(final_view),
            "program_contract_safe": bool(contract.get("safe_output", True)),
            "performance_source_excluded_from_program": True,
            "vseeface_optional": True,
            "internal_vrm_fallback_active": bridge["fallback"]["active"],
            "live_target_program_output_only": True,
            "live_target_consumes_project_player_program_output": True,
            "avatar_target_kind": avatar["kind"],
            "avatar_target_program_output": avatar["program_output"],
            "avatar_target_live_target_output": avatar["live_target_output"],
            "live2d_live_target_supported": avatar["kind"] == "live2d_actor_clip",
            "vrm_live_target_supported": avatar["kind"] == "vrm_vseeface_bridge",
            "vrm_renderer_family": avatar_renderer["family"],
            "vrm_render_profile": avatar_renderer["render_profile"],
            "ar_pbr_renderer_for_vrm": False,
        },
    }


def _avatar_target_summary(target: Mapping[str, Any] | None, avatar_name: str) -> dict[str, Any]:
    data = dict(target or {})
    name = str(data.get("name") or data.get("label") or avatar_name or "Avatar")
    label = str(data.get("label") or name)
    kind = str(data.get("kind") or "").strip()
    if not kind:
        lower_name = name.lower()
        if lower_name.endswith(".vrm"):
            kind = "vrm_vseeface_bridge"
        elif lower_name.endswith(".model3.json") or lower_name.endswith(".moc3"):
            kind = "live2d_actor_clip"
        else:
            kind = "avatar"
    target_id = str(data.get("id") or data.get("target_id") or kind)
    mapping_mode = str(data.get("mapping_mode") or "").strip()
    if not mapping_mode:
        if kind == "live2d_actor_clip":
            mapping_mode = "direct_key_baking"
        elif kind == "vrm_vseeface_bridge":
            mapping_mode = "pose_stream"
        elif kind == "none":
            mapping_mode = "none"
        else:
            mapping_mode = "avatar_composite"
    program_output = kind != "none"
    return {
        "id": target_id,
        "kind": kind,
        "name": name,
        "label": label,
        "path": str(data.get("path") or ""),
        "program_output": program_output,
        "live_target_output": program_output,
        "performance_source_direct_output": False,
        "mapping_mode": mapping_mode,
        "direct_key_baking": bool(data.get("direct_key_baking", kind == "live2d_actor_clip")),
        "pose_stream": bool(data.get("pose_stream", kind == "vrm_vseeface_bridge")),
        "renderer_family": VRM_RENDERER_FAMILY if kind == "vrm_vseeface_bridge" else str(data.get("renderer_family") or ""),
        "render_profile": VRM_RENDER_PROFILE if kind == "vrm_vseeface_bridge" else str(data.get("render_profile") or ""),
        "pbr_renderer": False,
    }


def _avatar_renderer_summary(avatar: Mapping[str, Any], bridge: Mapping[str, Any]) -> dict[str, str]:
    if avatar.get("kind") == "vrm_vseeface_bridge":
        if dict(bridge.get("fallback") or {}).get("active"):
            return {
                "renderer": "internal_vrm_fallback",
                "source_id": "internal_vrm_fallback",
                "family": VRM_RENDERER_FAMILY,
                "render_profile": VRM_RENDER_PROFILE,
            }
        return {
            "renderer": "vrm_mtoon_bridge",
            "source_id": "vrm_mtoon_avatar",
            "family": VRM_RENDERER_FAMILY,
            "render_profile": VRM_RENDER_PROFILE,
        }
    return {
        "renderer": "live2d_actor" if avatar.get("kind") == "live2d_actor_clip" else "avatar_composite",
        "source_id": "avatar_composite",
        "family": str(avatar.get("renderer_family") or ""),
        "render_profile": str(avatar.get("render_profile") or ""),
    }


def _bridge_status_summary(status: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(status or {})
    view = data.get("view") if isinstance(data.get("view"), Mapping) else {}
    capture = data.get("capture") if isinstance(data.get("capture"), Mapping) else {}
    fallback = view.get("fallback") if isinstance(view.get("fallback"), Mapping) else capture.get("fallback")
    fallback_data = dict(fallback if isinstance(fallback, Mapping) else {})
    active = bool(fallback_data.get("active")) or str(fallback_data.get("mode") or "") == "internal_vrm_renderer"
    ui = data.get("ui") if isinstance(data.get("ui"), Mapping) else {}
    return {
        "state": str(data.get("state") or ""),
        "capture_label": str(ui.get("label") or capture.get("status") or ""),
        "capture_ready": capture.get("ready"),
        "vseeface_optional": True,
        "fallback": {
            "active": active,
            "mode": str(fallback_data.get("mode") or ("internal_vrm_renderer" if active else "")),
            "source_id": str(fallback_data.get("source_id") or ("internal_vrm_fallback" if active else "")),
            "label": str(fallback_data.get("label") or ("Internal VRM fallback" if active else "")),
            "program_output": bool(fallback_data.get("program_output", active)),
        },
    }


def _live_target_summary(target: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(target or {})
    return {
        "target_id": str(data.get("target_id") or data.get("id") or "record_file"),
        "label": str(data.get("label") or "Local MP4"),
        "output_kind": str(data.get("output_kind") or data.get("kind") or "recording"),
        "program_output": True,
        "performance_source_direct_output": False,
        "stream_key_saved": False,
        "experimental": bool(data.get("experimental", False)),
    }


def _live_target_primary_action_label(target: Mapping[str, Any]) -> str:
    if str(target.get("output_kind") or "") == "recording":
        return "Start Local MP4"
    if str(target.get("output_kind") or "") in {"window_share", "virtual_camera"}:
        return "Prepare Output"
    return "Go Live"


def _control(control_id: str, label: str, value: Any) -> dict[str, Any]:
    return {"id": control_id, "label": label, "kind": "continuous", "value": value}


def _toggle(control_id: str, label: str, value: bool) -> dict[str, Any]:
    return {"id": control_id, "label": label, "kind": "toggle", "value": bool(value)}

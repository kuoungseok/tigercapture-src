"""AR/PBR preview and depth-view action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def ar_pbr_surface_properties_schema() -> dict[str, dict[str, Any]]:
    return {
        "render_profile": {"type": "string"},
        "hdri_id": {"type": "string"},
        "hdri_path": {"type": "string"},
        "ibl_exposure": {"type": "number"},
        "ibl_rotation": {"type": "number"},
        "surface_override_strength": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "surface_roughness": {"type": "number", "minimum": 0.04, "maximum": 1.0},
        "surface_metallic": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "surface_reflectance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "clearcoat_strength": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "clearcoat_roughness": {"type": "number", "minimum": 0.02, "maximum": 1.0},
        "clearcoat_ior": {"type": "number", "minimum": 1.0, "maximum": 2.5},
    }


def register_ar_pbr_preview_actions(registry: Any) -> None:
    registry.register_adapter_action(
        "ar_pbr.preview.diagnostics",
        "Return AR/PBR preview renderer, packet-cache, and GL VBO diagnostics.",
        "ar_pbr",
        "ar_pbr_preview_diagnostics",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR preview diagnostics would be returned",
    )
    registry.register_adapter_action(
        "ar_pbr.preview.view.get",
        "Return the open AR/PBR asset preview camera framing, including rotation, zoom, camera distance, and pan.",
        "ar_pbr",
        "ar_pbr_preview_view_get",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR preview camera view would be returned",
    )
    registry.register_adapter_action(
        "ar_pbr.preview.view.set",
        "Set the open AR/PBR asset preview camera framing, including zoom and camera distance.",
        "ar_pbr",
        "ar_pbr_preview_view_set",
        params_schema=schema_object({
            "zoom": {"type": "number"},
            "zoom_factor": {"type": "number"},
            "camera_z": {"type": "number"},
            "pitch": {"type": "number"},
            "yaw": {"type": "number"},
            "roll": {"type": "number"},
            "pan_x": {"type": "number"},
            "pan_y": {"type": "number"},
            "pan_z": {"type": "number"},
            "fit_first": {"type": "boolean"},
            "hide_environment_background": {"type": "boolean"},
        }),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR preview camera view would be reframed",
    )
    registry.register_adapter_action(
        "ar_pbr.preview.settings.get",
        "Return the open AR/PBR asset preview scene-lighting, AO/GI, tone, catcher, and depth settings.",
        "ar_pbr",
        "ar_pbr_preview_settings_get",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR preview scene settings would be returned",
    )
    registry.register_adapter_action(
        "ar_pbr.preview.depth_view.get",
        "Return the main video preview AR/PBR depth-map-only viewer mode.",
        "ar_pbr",
        "ar_pbr_preview_depth_view_get",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR preview depth-map viewer mode would be returned",
    )
    registry.register_adapter_action(
        "ar_pbr.preview.depth_view.set",
        "Set the main video preview to normal compositing or depth-map-only display.",
        "ar_pbr",
        "ar_pbr_preview_depth_view_set",
        params_schema=schema_object({
            "mode": {
                "type": "string",
                "enum": [
                    "off",
                    "matte",
                    "distance",
                    "plane",
                    "grayscale",
                    "heat",
                    "inverted_grayscale",
                    "depth",
                    "depth_map",
                ],
            },
            "refresh": {"type": "boolean"},
        }),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR preview depth-map viewer mode would be changed",
    )
    surface_properties = ar_pbr_surface_properties_schema()
    registry.register_adapter_action(
        "ar_pbr.preview.surface.get",
        "Return the open AR/PBR asset preview IBL, surface material override, and clearcoat settings.",
        "ar_pbr",
        "ar_pbr_preview_surface_get",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR preview surface settings would be returned",
    )
    registry.register_adapter_action(
        "ar_pbr.preview.surface.set",
        "Apply AR/PBR asset preview IBL, roughness, metallic, reflectance, and clearcoat settings.",
        "ar_pbr",
        "ar_pbr_preview_surface_set",
        params_schema=schema_object({
            **surface_properties,
            "activate": {"type": "boolean"},
            "show": {"type": "boolean"},
        }),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR preview surface settings would be applied",
    )
    registry.register_adapter_action(
        "ar_pbr.preview.settings.set",
        "Apply AR/PBR asset preview scene lighting, surface material, Hybrid GI, AO, tone mapping, shadow/reflection catcher, and depth settings.",
        "ar_pbr",
        "ar_pbr_preview_settings_set",
        params_schema=schema_object({
            **surface_properties,
            "show_environment_background": {"type": "boolean"},
            "light_azimuth": {"type": "number"},
            "light_elevation": {"type": "number"},
            "direct_strength": {"type": "number"},
            "shadow_strength": {"type": "number"},
            "shadow_pcf_radius": {"type": "number"},
            "shadow_softness": {"type": "number"},
            "self_shadow_strength": {"type": "number"},
            "ground_height": {"type": "number"},
            "shadow_catcher_opacity": {"type": "number"},
            "shadow_catcher_softness": {"type": "number"},
            "shadow_catcher_matte_alpha": {"type": "number"},
            "reflection_catcher_opacity": {"type": "number"},
            "reflection_catcher_roughness": {"type": "number"},
            "reflection_catcher_softness": {"type": "number"},
            "contact_reflection_strength": {"type": "number"},
            "contact_reflection_falloff": {"type": "number"},
            "tone_mapping": {"type": "string"},
            "tone_exposure": {"type": "number"},
            "tone_white_balance": {"type": "number"},
            "tone_gamma": {"type": "number"},
            "depth_edge_glow_enabled": {"type": "boolean"},
            "depth_edge_glow_strength": {"type": "number"},
            "depth_edge_glow_radius_px": {"type": "number"},
            "clearcoat": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "strength": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "roughness": {"type": "number", "minimum": 0.02, "maximum": 1.0},
                    "ior": {"type": "number", "minimum": 1.0, "maximum": 2.5},
                },
            },
            "surface": {
                "type": "object",
                "properties": {
                    "mix": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "roughness": {"type": "number", "minimum": 0.04, "maximum": 1.0},
                    "metallic": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "reflectance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
            },
            "ambient_occlusion_mode": {"type": "string"},
            "ao_strength": {"type": "number"},
            "ao_radius": {"type": "number"},
            "ao_distance": {"type": "number"},
            "hybrid_sample_count": {"type": "number"},
            "diffuse_gi_strength": {"type": "number"},
            "specular_gi_strength": {"type": "number"},
            "denoise_strength": {"type": "number"},
        }),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR preview scene settings would be applied",
    )

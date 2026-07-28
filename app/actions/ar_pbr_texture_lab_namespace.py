"""AR/PBR image texture-map lab action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object
from app.ar_pbr.texture_map_lab import (
    AO_ALGORITHMS,
    NORMAL_FORMATS,
    PACKED_LAYOUTS,
    PREVIEW_MODES,
    PREVIEW_SHAPES,
    SEPARATE_MAPS,
    TEXTURE_MAP_BACKENDS,
)


def texture_lab_settings_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "normal_strength": {"type": "number", "minimum": 0.0, "maximum": 12.0},
            "normal_radius_px": {"type": "number", "minimum": 0.0, "maximum": 24.0},
            "normal_format": {"type": "string", "enum": list(NORMAL_FORMATS)},
            "normal_filter": {"type": "string", "enum": ["sobel", "central_difference"]},
            "height_invert": {"type": "boolean"},
            "height_contrast": {"type": "number", "minimum": 0.1, "maximum": 4.0},
            "height_blur_px": {"type": "number", "minimum": 0.0, "maximum": 8.0},
            "edge_aware_smoothing": {"type": "boolean"},
            "edge_aware_sensitivity": {"type": "number", "minimum": 0.0, "maximum": 32.0},
            "ao_strength": {"type": "number", "minimum": 0.0, "maximum": 3.0},
            "ao_radius_px": {"type": "number", "minimum": 0.0, "maximum": 64.0},
            "ao_algorithm": {"type": "string", "enum": list(AO_ALGORITHMS)},
            "ao_samples": {"type": "integer", "minimum": 4, "maximum": 32},
            "ao_steps": {"type": "integer", "minimum": 2, "maximum": 24},
            "ao_height_scale": {"type": "number", "minimum": 0.1, "maximum": 64.0},
            "ao_multiscale": {"type": "boolean"},
            "cavity_strength": {"type": "number", "minimum": 0.0, "maximum": 2.0},
            "cavity_radius_px": {"type": "number", "minimum": 0.2, "maximum": 32.0},
            "curvature_strength": {"type": "number", "minimum": 0.0, "maximum": 8.0},
            "roughness_bias": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "roughness_contrast": {"type": "number", "minimum": 0.1, "maximum": 3.0},
            "roughness_detail": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "metallic_value": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "metallic_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.5},
            "metallic_softness": {"type": "number", "minimum": 0.001, "maximum": 0.5},
            "delight_enabled": {"type": "boolean"},
            "delight_strength": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "delight_radius_px": {"type": "number", "minimum": 1.0, "maximum": 256.0},
            "delight_contrast_preservation": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "substrate_enabled": {"type": "boolean"},
            "substrate_mode": {"type": "string", "enum": ["off", "slab"]},
            "substrate_reflectance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "f90_mask_strength": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "base_color_exposure": {"type": "number", "minimum": -3.0, "maximum": 3.0},
            "base_color_contrast": {"type": "number", "minimum": 0.1, "maximum": 3.0},
            "preview_light_azimuth": {"type": "number", "minimum": -360.0, "maximum": 360.0},
            "preview_light_elevation": {"type": "number", "minimum": 3.0, "maximum": 89.0},
            "preview_environment": {"type": "number", "minimum": 0.0, "maximum": 1.5},
            "preview_animate_light": {"type": "boolean"},
            "preview_parallax_enabled": {"type": "boolean"},
            "preview_parallax_strength": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "preview_parallax_depth": {"type": "number", "minimum": 0.0, "maximum": 0.25},
            "preview_parallax_steps": {"type": "integer", "minimum": 4, "maximum": 64},
        },
    }


def register_ar_pbr_texture_lab_actions(registry: Any) -> None:
    settings_schema = texture_lab_settings_schema()
    registry.register_adapter_action(
        "ar_pbr.texture_lab.open",
        "Open the AR/PBR image texture lab with plane preview, sliders, and export controls.",
        "ar_pbr",
        "ar_pbr_texture_lab_open",
        params_schema=schema_object({
            "image_path": {"type": "string"},
        }, required=("image_path",)),
        required=("image_path",),
        mutating=False,
        changed=False,
        requires_owner=True,
        async_kind="ui",
        dry_summary="AR/PBR texture lab window would open",
    )
    registry.register_adapter_action(
        "ar_pbr.texture_lab.preview",
        "Render an image-to-PBR material plane preview or individual texture-map preview.",
        "ar_pbr",
        "ar_pbr_texture_lab_preview",
        params_schema=schema_object({
            "image_path": {"type": "string"},
            "output_path": {"type": "string"},
            "preview_mode": {"type": "string", "enum": list(PREVIEW_MODES)},
            "preview_shape": {"type": "string", "enum": list(PREVIEW_SHAPES)},
            "width": {"type": "integer", "minimum": 64, "maximum": 8192},
            "height": {"type": "integer", "minimum": 64, "maximum": 8192},
            "settings": settings_schema,
            "backend": {"type": "string", "enum": list(TEXTURE_MAP_BACKENDS)},
            "allow_cpu": {
                "type": "boolean",
                "description": "Diagnostic only. Product preview/export defaults to GPU-required mode.",
            },
        }, required=("image_path",)),
        required=("image_path",),
        mutating=False,
        changed=False,
        requires_owner=False,
        dry_summary="AR/PBR texture-map plane preview would be rendered",
    )
    registry.register_adapter_action(
        "ar_pbr.texture_lab.backend_status",
        "Report Texture Lab CPU/GPU backend availability and the selected map-generation backend.",
        "ar_pbr",
        "ar_pbr_texture_lab_backend_status",
        params_schema=schema_object({
            "backend": {"type": "string", "enum": list(TEXTURE_MAP_BACKENDS)},
            "allow_cpu": {
                "type": "boolean",
                "description": "Diagnostic only. Product backend selection defaults to GPU-required mode.",
            },
        }),
        mutating=False,
        changed=False,
        requires_owner=False,
        dry_summary="Texture Lab backend status would be reported",
    )
    registry.register_adapter_action(
        "ar_pbr.texture_lab.export",
        "Export separate PBR maps plus optional ARM/ORM/channel-packed textures.",
        "ar_pbr",
        "ar_pbr_texture_lab_export",
        params_schema=schema_object({
            "image_path": {"type": "string"},
            "output_dir": {"type": "string"},
            "settings": settings_schema,
            "maps": {"type": "array", "items": {"type": "string", "enum": list(SEPARATE_MAPS)}},
            "packed_layouts": {"type": "array", "items": {"type": "string", "enum": list(PACKED_LAYOUTS)}},
            "max_size": {"type": "integer", "minimum": 64, "maximum": 16384},
            "backend": {"type": "string", "enum": list(TEXTURE_MAP_BACKENDS)},
            "allow_cpu": {
                "type": "boolean",
                "description": "Diagnostic only. Product export defaults to GPU-required mode.",
            },
        }, required=("image_path",)),
        required=("image_path",),
        mutating=True,
        changed=True,
        requires_owner=False,
        dry_summary="AR/PBR PBR maps and packed textures would be exported",
    )
    registry.register_adapter_action(
        "ar_pbr.texture_lab.substrate_plan",
        "Return Unreal Default Lit and Substrate wiring guidance for generated texture maps.",
        "ar_pbr",
        "ar_pbr_texture_lab_substrate_plan",
        params_schema=schema_object({
            "settings": settings_schema,
        }),
        mutating=False,
        changed=False,
        requires_owner=False,
        dry_summary="AR/PBR Substrate texture wiring plan would be returned",
    )

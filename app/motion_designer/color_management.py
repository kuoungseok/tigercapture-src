"""Qt-free color and alpha rules for Motion Designer compositing.

Motion source surfaces currently arrive as premultiplied sRGB RGBA.  This
module owns the conversion order used when those surfaces are placed over a
video frame: unpremultiply in the encoded space, decode to linear light,
premultiply in linear light, composite, and encode for display/output.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.color_management import ColorManagementSettings, validate_color_management


MOTION_COLOR_SCHEMA = "tigercapture.motion.color.v1"
MOTION_COLOR_METADATA_KEY = "color_management"

SUPPORTED_BLEND_SPACES = frozenset({"display-srgb", "linear-srgb"})
SUPPORTED_TONE_MAPS = frozenset({"none", "reinhard", "aces-fitted"})


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class MotionColorSettings:
    """Motion-specific color intent layered over project color settings."""

    schema: str = MOTION_COLOR_SCHEMA
    blend_space: str = "linear-srgb"
    source_space: str = "srgb"
    source_transfer: str = "srgb"
    display_transfer: str = "srgb"
    tone_map: str = "none"
    storage_alpha: str = "straight"
    composite_alpha: str = "premultiplied"
    premultiply_space: str = "linear"
    project: ColorManagementSettings = ColorManagementSettings(
        input_space="srgb",
        input_transfer="srgb",
        working_space="srgb",
        output_space="srgb",
        output_transfer="srgb",
        view_transform="srgb",
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, *, legacy: bool = False) -> "MotionColorSettings":
        values = _mapping(data)
        if not values and legacy:
            return cls(blend_space="display-srgb", premultiply_space="display")
        alpha = _mapping(values.get("alpha"))
        project_data = values.get("project")
        project = (
            project_data
            if isinstance(project_data, ColorManagementSettings)
            else ColorManagementSettings.from_dict(dict(_mapping(project_data)) or {
                "input_space": values.get("source_space", "srgb"),
                "input_transfer": values.get("source_transfer", "srgb"),
                "working_space": "srgb",
                "output_space": "srgb",
                "output_transfer": values.get("display_transfer", "srgb"),
                "view_transform": "srgb",
            })
        )
        blend_space = str(values.get("blend_space") or "linear-srgb").strip().lower().replace("_", "-")
        tone_map = str(values.get("tone_map") or "none").strip().lower().replace("_", "-")
        return cls(
            schema=str(values.get("schema") or MOTION_COLOR_SCHEMA),
            blend_space=blend_space,
            source_space=str(values.get("source_space") or "srgb").strip().lower(),
            source_transfer=str(values.get("source_transfer") or "srgb").strip().lower(),
            display_transfer=str(values.get("display_transfer") or "srgb").strip().lower(),
            tone_map=tone_map,
            storage_alpha=str(alpha.get("storage") or values.get("storage_alpha") or "straight").strip().lower(),
            composite_alpha=str(alpha.get("composite") or values.get("composite_alpha") or "premultiplied").strip().lower(),
            premultiply_space=str(alpha.get("premultiply_space") or values.get("premultiply_space") or "linear").strip().lower(),
            project=project,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "blend_space": self.blend_space,
            "source_space": self.source_space,
            "source_transfer": self.source_transfer,
            "display_transfer": self.display_transfer,
            "tone_map": self.tone_map,
            "alpha": {
                "storage": self.storage_alpha,
                "composite": self.composite_alpha,
                "premultiply_space": self.premultiply_space,
            },
            "project": self.project.to_dict(),
        }


def default_motion_metadata() -> dict[str, Any]:
    """Metadata assigned only to newly constructed Motion compositions."""
    return {MOTION_COLOR_METADATA_KEY: MotionColorSettings().to_dict()}


def settings_from_composition_metadata(metadata: Mapping[str, Any] | None) -> MotionColorSettings:
    values = _mapping(metadata)
    raw = values.get(MOTION_COLOR_METADATA_KEY)
    return MotionColorSettings.from_dict(
        raw if isinstance(raw, Mapping) else None,
        legacy=not isinstance(raw, Mapping),
    )


def validate_motion_color_settings(settings: MotionColorSettings | Mapping[str, Any] | None) -> dict[str, Any]:
    current = settings if isinstance(settings, MotionColorSettings) else MotionColorSettings.from_dict(settings)
    errors: list[str] = []
    warnings: list[str] = []
    if current.schema != MOTION_COLOR_SCHEMA:
        errors.append(f"Unsupported Motion color schema: {current.schema}")
    if current.blend_space not in SUPPORTED_BLEND_SPACES:
        errors.append(f"Unsupported Motion blend space: {current.blend_space}")
    if current.tone_map not in SUPPORTED_TONE_MAPS:
        errors.append(f"Unsupported Motion tone map: {current.tone_map}")
    if current.storage_alpha != "straight":
        errors.append("Motion file/image storage alpha must be straight")
    if current.composite_alpha != "premultiplied":
        errors.append("Motion compositor alpha must be premultiplied")
    expected_space = "linear" if current.blend_space == "linear-srgb" else "display"
    if current.premultiply_space != expected_space:
        errors.append(
            f"Alpha premultiply space must be {expected_space} for {current.blend_space} blending"
        )
    if current.blend_space == "display-srgb":
        warnings.append("Legacy display-space blending can darken translucent edges")
    if current.project.ocio_config_path:
        from app.color_ocio import build_ocio_plan

        ocio_plan = build_ocio_plan(current.project)
        if not ocio_plan.enabled:
            errors.extend(
                f"Motion OCIO: {warning}"
                for warning in (
                    ocio_plan.warnings
                    or ("configuration is unavailable",)
                )
            )
    elif current.project.working_space in {"acescg", "acescct"}:
        warnings.append(
            "Motion uses the deterministic ACES-fitted fallback until an OCIO config is selected"
        )
    project_report = validate_color_management(current.project, require_existing_luts=True)
    errors.extend(str(item) for item in project_report.get("errors", []))
    warnings.extend(str(item) for item in project_report.get("warnings", []))
    for name, slot in current.project.active_luts():
        if Path(slot.path).suffix.lower() != ".cube":
            errors.append(f"Motion {name} LUT must be a 3D .cube file: {slot.path}")
        elif Path(slot.path).is_file():
            try:
                from .color_runtime import load_cube_lut

                load_cube_lut(slot.path)
            except Exception as exc:
                errors.append(f"Motion {name} LUT is invalid: {exc}")
    return {
        "ok": not errors,
        "schema": current.schema,
        "settings": current.to_dict(),
        "errors": errors,
        "warnings": warnings,
        "internal_layer_blend": "qt-display-space",
        "final_video_composite": current.blend_space,
        "delivery_pipeline": {
            "order": [
                "input_lut",
                "tone_map",
                "creative_lut",
                "display_transform",
                "output_lut",
            ],
            "tone_maps": sorted(SUPPORTED_TONE_MAPS),
            "lut_format": "3d_cube",
            "openexr_bypass": True,
        },
    }


def srgb_to_linear(values):
    import numpy as np

    encoded = np.clip(np.asarray(values, dtype=np.float32), 0.0, 1.0)
    return np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(values):
    import numpy as np

    linear = np.clip(np.asarray(values, dtype=np.float32), 0.0, 1.0)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * (linear ** (1.0 / 2.4)) - 0.055)


def composite_premultiplied_srgb_over_srgb(base_rgb, overlay_rgba, *, opacity: float = 1.0):
    """Composite premultiplied uint8 sRGB RGBA over uint8 sRGB RGB in linear light."""
    import numpy as np

    base = np.asarray(base_rgb, dtype=np.uint8)
    overlay = np.asarray(overlay_rgba, dtype=np.uint8)
    if base.ndim != 3 or base.shape[-1] != 3:
        raise ValueError("base_rgb must have shape (height, width, 3)")
    if overlay.shape[:2] != base.shape[:2] or overlay.ndim != 3 or overlay.shape[-1] != 4:
        raise ValueError("overlay_rgba must match base_rgb and have four channels")
    layer_opacity = max(0.0, min(1.0, float(opacity)))
    source_alpha = overlay[..., 3:4].astype(np.float32) / 255.0
    effective_alpha = source_alpha * layer_opacity
    premultiplied_encoded = overlay[..., :3].astype(np.float32) / 255.0
    straight_encoded = np.divide(
        premultiplied_encoded,
        source_alpha,
        out=np.zeros_like(premultiplied_encoded),
        where=source_alpha > 1e-8,
    )
    source_linear_premultiplied = srgb_to_linear(straight_encoded) * effective_alpha
    base_linear = srgb_to_linear(base.astype(np.float32) / 255.0)
    result_linear = source_linear_premultiplied + base_linear * (1.0 - effective_alpha)
    return np.rint(linear_to_srgb(result_linear) * 255.0).clip(0, 255).astype(np.uint8)


def premultiplied_srgb_to_straight_rgba_u8(overlay_rgba):
    """Convert an internal premultiplied sRGB surface to straight-alpha storage bytes."""
    import numpy as np

    overlay = np.asarray(overlay_rgba, dtype=np.uint8)
    if overlay.ndim != 3 or overlay.shape[-1] != 4:
        raise ValueError("overlay_rgba must have shape (height, width, 4)")
    alpha = overlay[..., 3:4].astype(np.float32) / 255.0
    encoded = overlay[..., :3].astype(np.float32) / 255.0
    straight = np.divide(encoded, alpha, out=np.zeros_like(encoded), where=alpha > 1e-8)
    output = np.empty_like(overlay)
    output[..., :3] = np.rint(straight * 255.0).clip(0, 255).astype(np.uint8)
    output[..., 3] = overlay[..., 3]
    return output


def premultiplied_srgb_to_linear_gbrap_f32_bytes(overlay_rgba) -> bytes:
    """Return scene-linear planar GBRAP float32 bytes for FFmpeg/OpenEXR."""
    import numpy as np

    straight = premultiplied_srgb_to_straight_rgba_u8(overlay_rgba)
    rgb_linear = srgb_to_linear(straight[..., :3].astype(np.float32) / 255.0)
    alpha = straight[..., 3].astype(np.float32) / 255.0
    planes = (rgb_linear[..., 1], rgb_linear[..., 2], rgb_linear[..., 0], alpha)
    return b"".join(np.ascontiguousarray(plane, dtype="<f4").tobytes() for plane in planes)

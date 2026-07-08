"""Durable local AR/PBR sample asset paths.

These paths are intentionally outside ``debugCapture``. The debugCapture folder
is disposable scratch space, so tools and QA should not depend on it for sample
assets that must be available after cleanup.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLYHAVEN_SAMPLE_ROOT = ROOT / "sample_assets" / "pbr_blender_scenes" / "polyhaven"
POLYHAVEN_CAMERA_ROOT = POLYHAVEN_SAMPLE_ROOT / "models" / "Camera_01"
POLYHAVEN_MATERIAL_ROOT = POLYHAVEN_SAMPLE_ROOT / "materials"

DEFAULT_AR_PBR_FBX_SAMPLE = POLYHAVEN_CAMERA_ROOT / "Camera_01_1k.fbx"
DEFAULT_AR_PBR_GLTF_SAMPLE = POLYHAVEN_CAMERA_ROOT / "Camera_01_1k.gltf"
DEFAULT_AR_PBR_FLOOR_GLTF_SAMPLE = POLYHAVEN_MATERIAL_ROOT / "concrete_floor" / "concrete_floor_1k.gltf"


def default_ar_pbr_preview_asset() -> Path:
    """Return the preferred durable sample asset for AR/PBR previews and QA."""
    for candidate in (
        DEFAULT_AR_PBR_GLTF_SAMPLE,
        DEFAULT_AR_PBR_FBX_SAMPLE,
        DEFAULT_AR_PBR_FLOOR_GLTF_SAMPLE,
    ):
        if candidate.exists():
            return candidate
    return DEFAULT_AR_PBR_GLTF_SAMPLE


def default_ar_pbr_binary_fbx_asset() -> Path:
    """Return the durable binary FBX sample used by FBX parser regression tests."""
    return DEFAULT_AR_PBR_FBX_SAMPLE


def ar_pbr_support_matrix_samples() -> tuple[dict[str, object], ...]:
    """Return durable sample candidates for AR/PBR asset support QA."""
    return (
        {
            "id": "polyhaven_camera_gltf_pbr",
            "path": str(DEFAULT_AR_PBR_GLTF_SAMPLE.relative_to(ROOT)),
            "expected_levels": ["ready"],
            "expected_features": ["gltf_source", "pbr_materials", "texture_maps"],
            "required": True,
        },
        {
            "id": "polyhaven_camera_fbx_runtime_conversion",
            "path": str(DEFAULT_AR_PBR_FBX_SAMPLE.relative_to(ROOT)),
            "expected_levels": ["limited"],
            "expected_features": ["fbx_source", "pbr_materials"],
            "expected_issues": ["fbx_runtime_conversion_required"],
            "required": True,
        },
        {
            "id": "polyhaven_concrete_floor_gltf_pbr",
            "path": str(DEFAULT_AR_PBR_FLOOR_GLTF_SAMPLE.relative_to(ROOT)),
            "expected_levels": ["ready"],
            "expected_features": ["gltf_source", "pbr_materials", "texture_maps"],
            "required": True,
        },
    )

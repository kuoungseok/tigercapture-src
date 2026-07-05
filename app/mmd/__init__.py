"""MMD preview support for TigerCapture."""
from __future__ import annotations

from .gpu_preview import MMD_RENDER_TOON, build_mmd_render_item
from .animation import MMDPhysicsState, MMDPoseGeometry, evaluate_model_pose
from .diagnostics import analyze_mmd_model, format_mmd_performance_line, format_mmd_report
from .lighting import MMD_LIGHTING_PRESETS, resolve_mmd_lighting
from .loader import load_mmd_model
from .pmx import MMDModel, load_pmx
from .physics import (
    DecimatedPhysicsBackend,
    MMDPhysicsBackend,
    MMDPhysicsPoseDelta,
    NoPhysicsBackend,
    PyBulletPhysicsBackend,
    SPRING_PHYSICS_RESPONSE,
    SECONDARY_ROTATION_HINT_SCALE,
    SpringPhysicsBackend,
    configure_mmd_physics_backend,
    create_mmd_physics_backend,
    mmd_physics_backend_diagnostics,
)
from .regression_profiles import (
    evaluate_mmd_regression_profile,
    mmd_regression_profile,
    mmd_regression_profile_ids,
    mmd_regression_profile_model_path,
    mmd_regression_profile_motion_path,
)
from .vmd import VMDMotion, load_vmd, vmd_bezier_is_linear, vmd_bezier_max_linear_delta, vmd_bezier_value

__all__ = [
    "MMDModel",
    "MMDPhysicsBackend",
    "MMDPhysicsPoseDelta",
    "MMDPhysicsState",
    "MMDPoseGeometry",
    "MMD_RENDER_TOON",
    "MMD_LIGHTING_PRESETS",
    "VMDMotion",
    "DecimatedPhysicsBackend",
    "NoPhysicsBackend",
    "PyBulletPhysicsBackend",
    "SPRING_PHYSICS_RESPONSE",
    "SECONDARY_ROTATION_HINT_SCALE",
    "SpringPhysicsBackend",
    "analyze_mmd_model",
    "build_mmd_render_item",
    "configure_mmd_physics_backend",
    "create_mmd_physics_backend",
    "mmd_physics_backend_diagnostics",
    "evaluate_model_pose",
    "evaluate_mmd_regression_profile",
    "format_mmd_report",
    "format_mmd_performance_line",
    "mmd_regression_profile",
    "mmd_regression_profile_ids",
    "mmd_regression_profile_model_path",
    "mmd_regression_profile_motion_path",
    "resolve_mmd_lighting",
    "load_mmd_model",
    "load_pmx",
    "load_vmd",
    "vmd_bezier_is_linear",
    "vmd_bezier_max_linear_delta",
    "vmd_bezier_value",
]

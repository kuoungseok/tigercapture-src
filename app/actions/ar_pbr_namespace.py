"""AR/PBR automation action registrations.

This facade keeps ``register_ar_pbr_actions`` stable while preview/depth and
viewport-gizmo schemas live in focused modules.
"""
from __future__ import annotations

from typing import Any

from app.actions.ar_pbr_gizmo_namespace import register_ar_pbr_gizmo_actions
from app.actions.ar_pbr_preview_namespace import register_ar_pbr_preview_actions


def register_ar_pbr_actions(registry: Any) -> None:
    register_ar_pbr_preview_actions(registry)
    register_ar_pbr_gizmo_actions(registry)

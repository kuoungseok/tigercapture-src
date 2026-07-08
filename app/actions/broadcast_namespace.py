"""Broadcast and live-output Python action namespace registrations.

The public registration entry point stays here; implementation is split by
Live Target, evidence/readiness, and virtual-camera/OBS surfaces.
"""
from __future__ import annotations

from typing import Any

from app.actions.broadcast_evidence_namespace import register_broadcast_evidence_actions
from app.actions.broadcast_live_target_namespace import register_broadcast_live_target_actions
from app.actions.broadcast_virtual_camera_namespace import register_broadcast_virtual_camera_actions


def register_broadcast_actions(registry: Any) -> None:
    """Register broadcast/live target actions without growing the core registry."""
    register_broadcast_live_target_actions(registry)
    register_broadcast_evidence_actions(registry)
    register_broadcast_virtual_camera_actions(registry)

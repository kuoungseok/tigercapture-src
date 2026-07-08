"""NLE-related action registration helpers.

This module keeps public action IDs stable while moving high-growth action
namespaces out of the central registry file.
"""
from __future__ import annotations

from typing import Any

from app.actions.nle_auditions_namespace import register_audition_actions
from app.actions.nle_multicam_namespace import register_multicam_actions
from app.actions.nle_project_bin_namespace import register_project_bin_actions
from app.actions.nle_readiness_namespace import register_nle_readiness_actions as _register_nle_readiness_actions
from app.actions.nle_source_record_namespace import register_source_record_actions
from app.actions.nle_storyline_namespace import register_storyline_actions
from app.actions.nle_visual_namespace import register_visual_feedback_actions


def register_nle_readiness_actions(registry: Any) -> None:
    """Register readiness plus adjacent NLE polish actions for legacy callers."""

    _register_nle_readiness_actions(registry)
    register_storyline_actions(registry)
    register_visual_feedback_actions(registry)
    register_audition_actions(registry)


def register_nle_namespace_actions(registry: Any) -> None:
    """Register the NLE namespace in the same public-ID order as the old registry."""

    register_project_bin_actions(registry)
    register_nle_readiness_actions(registry)
    register_multicam_actions(registry)

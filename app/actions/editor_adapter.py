"""Adapter between registered Python actions and the current editor object.

The adapter is the only layer in the action system allowed to touch today's
editor internals while the large VideoEditorWindow monolith is being extracted.
External callers only see registered action ids and JSON schemas.
"""
from __future__ import annotations

from typing import Any

from app.ai_project_snapshot import build_project_snapshot_from_editor, minimal_project_snapshot
from app.actions.editor_adapter_core_helpers import CoreHelperMixin
from app.actions.editor_adapter_editing import EditingAdapterMixin
from app.actions.editor_adapter_nle import NleAdapterMixin
from app.actions.editor_adapter_timeline import TimelineAdapterMixin
from app.actions.editor_adapter_timeline_helpers import TimelineHelperMixin
from app.actions.editor_adapter_ui import UiAdapterMixin
from app.actions.editor_adapter_vtuber import VtuberBroadcastAdapterMixin
from app.actions.editor_adapter_object_helpers import ObjectHelperMixin
from app.actions.editor_adapter_mmd import MmdAdapterMixin
from app.actions.editor_adapter_music import MusicAdapterMixin
from app.actions.editor_adapter_ar_pbr import ArPbrAdapterMixin
from app.actions.editor_adapter_ppt import PptAdapterMixin
from app.actions.editor_adapter_tts import TtsAdapterMixin
from app.actions.editor_adapter_paint import PaintAdapterMixin
from app.actions.editor_adapter_motion import MotionAdapterMixin
from app.actions.editor_adapter_motion_rig import MotionRigAdapterMixin
from app.actions.editor_adapter_motion_puppet import MotionPuppetAdapterMixin
from app.actions.editor_adapter_motion_precomp import MotionPrecompAdapterMixin
from app.actions.editor_adapter_motion_time import MotionTimeAdapterMixin
from app.actions.editor_adapter_motion_advanced import MotionAdvancedAdapterMixin
from app.actions.editor_adapter_motion_tracking import MotionTrackingAdapterMixin
from app.actions.editor_adapter_motion_audio import MotionAudioAdapterMixin
from app.actions.editor_adapter_motion_ar_pbr import MotionArPbrAdapterMixin
from app.actions.editor_adapter_motion_actor import MotionActorAdapterMixin
from app.actions.editor_adapter_motion_mmd import MotionMMDAdapterMixin
from app.actions.editor_adapter_motion_vrm import MotionVRMAdapterMixin
from app.actions.editor_adapter_motion_expression import MotionExpressionAdapterMixin
from app.actions.editor_adapter_motion_particle import MotionParticleAdapterMixin
from app.actions.editor_adapter_motion_template import MotionTemplateAdapterMixin
from app.actions.editor_adapter_motion_broadcast import MotionBroadcastAdapterMixin
from app.actions.editor_adapter_motion_export import MotionExportAdapterMixin
from app.actions.editor_adapter_motion_umg import MotionUMGAdapterMixin
from app.actions.editor_adapter_motion_interchange import MotionInterchangeAdapterMixin
from app.actions.editor_adapter_motion_release import MotionReleaseAdapterMixin
from app.actions.editor_adapter_motion_relink import MotionRelinkAdapterMixin
from app.actions.editor_adapter_motion_recovery import MotionRecoveryAdapterMixin
from app.actions.editor_adapter_motion_plugin import MotionPluginAdapterMixin
from app.actions.editor_adapter_motion_ai_generation import MotionAIGenerationAdapterMixin
from app.actions.editor_adapter_motion_craft import MotionCraftAdapterMixin
from app.actions.editor_adapter_motion_lookdev import MotionLookdevAdapterMixin
from app.actions.editor_adapter_motion_glass import MotionGlassAdapterMixin
from app.actions.editor_adapter_motion_collage import MotionCollageAdapterMixin
from app.actions.editor_adapter_motion_story import MotionStoryAdapterMixin
from app.actions.editor_adapter_motion_stop_motion import MotionStopMotionAdapterMixin
from app.actions.editor_adapter_motion_style_director import MotionStyleDirectorAdapterMixin
from app.actions.editor_adapter_color import ColorManagementAdapterMixin


class EditorAdapter(
    ColorManagementAdapterMixin,
    MotionStyleDirectorAdapterMixin,
    MotionStopMotionAdapterMixin,
    MotionStoryAdapterMixin,
    MotionCollageAdapterMixin,
    MotionGlassAdapterMixin,
    MotionLookdevAdapterMixin,
    MotionCraftAdapterMixin,
    MotionUMGAdapterMixin,
    MotionAIGenerationAdapterMixin,
    MotionPluginAdapterMixin,
    MotionRecoveryAdapterMixin,
    MotionRelinkAdapterMixin,
    MotionReleaseAdapterMixin,
    MotionInterchangeAdapterMixin,
    MotionExportAdapterMixin,
    MotionBroadcastAdapterMixin,
    MotionTemplateAdapterMixin,
    MotionParticleAdapterMixin,
    MotionExpressionAdapterMixin,
    MotionVRMAdapterMixin,
    MotionMMDAdapterMixin,
    MotionActorAdapterMixin,
    MotionArPbrAdapterMixin,
    MotionAudioAdapterMixin,
    MotionTrackingAdapterMixin,
    MotionAdvancedAdapterMixin,
    MotionTimeAdapterMixin,
    MotionPrecompAdapterMixin,
    MotionPuppetAdapterMixin,
    MotionRigAdapterMixin,
    MotionAdapterMixin,
    EditingAdapterMixin,
    TimelineAdapterMixin,
    VtuberBroadcastAdapterMixin,
    MmdAdapterMixin,
    ArPbrAdapterMixin,
    PptAdapterMixin,
    PaintAdapterMixin,
    MusicAdapterMixin,
    TtsAdapterMixin,
    NleAdapterMixin,
    UiAdapterMixin,
    CoreHelperMixin,
    TimelineHelperMixin,
    ObjectHelperMixin,
):
    """Small stable wrapper over editor/model functionality."""

    def __init__(self, owner: Any | None = None) -> None:
        self.owner = owner

    @property
    def has_owner(self) -> bool:
        return self.owner is not None

    def snapshot(self, *, media_limit: int = 200) -> dict[str, Any]:
        if self.owner is None:
            return minimal_project_snapshot()
        method = getattr(self.owner, "_ai_project_snapshot", None)
        if callable(method):
            try:
                return dict(method() or {})
            except Exception:
                pass
        return build_project_snapshot_from_editor(self.owner, media_limit=max(0, int(media_limit or 200)))

    def app_status(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        return {
            "app": "Tiger Studio",
            "action_system": {
                "arbitrary_python": False,
                "arbitrary_shell": False,
                "registered_actions_only": True,
            },
            "project_summary": snapshot.get("summary", {}),
            "snapshot_hash": snapshot.get("snapshot_hash", ""),
            "current_position_ms": snapshot.get("current_position_ms", 0),
        }

    def media_summary(self, *, limit: int = 200) -> dict[str, Any]:
        snapshot = self.snapshot(media_limit=limit)
        items = list(snapshot.get("media_pool") or [])
        counts: dict[str, int] = {}
        for item in items:
            kind = str(item.get("kind") or "unknown")
            counts[kind] = counts.get(kind, 0) + 1
        return {
            "count": len(items),
            "kind_counts": counts,
            "items": items[: max(0, int(limit or 200))],
            "snapshot_hash": snapshot.get("snapshot_hash", ""),
        }

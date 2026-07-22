"""Delegate installer for the large VideoEditorWindow compatibility surface."""
from __future__ import annotations

from PySide6.QtCore import QTimer

from app.i18n import tr
from app import video_editor_context_menu_controller as _context_menu_controller
from app import video_editor_preview_recovery as _preview_recovery
from app.video_editor_delegates_core import install_core_delegates
from app.video_editor_delegates_ppt import install_ppt_delegates
from app.video_editor_delegates_timeline import install_timeline_delegates
from app.video_editor_delegates_audio_color import install_audio_color_delegates
from app.video_editor_delegates_creative import install_creative_delegates
from app.video_editor_delegates_actor import install_actor_delegates
from app.video_editor_delegates_ar_pbr import install_ar_pbr_delegates
from app.video_editor_delegates_media_preview_export import install_media_preview_export_delegates
from app.video_editor_delegates_ai import install_ai_delegates
from app.video_editor_delegates_motion import install_motion_delegates


def _window_refresh_preview_after_color_toggle(self) -> None:
    _preview_recovery.refresh_preview_after_color_toggle(
        self,
        schedule_restore=self._schedule_preview_transition_restore,
    )


def _window_schedule_preview_transition_restore(self, backup=None) -> None:
    _preview_recovery.schedule_preview_transition_restore(
        self,
        backup,
        single_shot=QTimer.singleShot,
    )


def _window_clip_badge_menu_model(self, clip, action: str) -> list[dict[str, object]]:
    return _context_menu_controller.build_clip_badge_menu_model(
        clip,
        action,
        translator=tr,
        has_active_fx=self._clip_has_active_fx(clip),
        has_disabled_fx=self._clip_has_disabled_fx(clip),
    )


def _window_run_clip_badge_menu_action(self, track, clip, badge_action: str, command: str) -> bool:
    return _context_menu_controller.dispatch_clip_badge_menu_action(
        self,
        track,
        clip,
        badge_action,
        command,
        translator=tr,
    )


def install_video_editor_window_delegates(VideoEditorWindow) -> None:
    install_core_delegates(VideoEditorWindow)
    install_ppt_delegates(VideoEditorWindow)
    install_timeline_delegates(VideoEditorWindow)
    install_audio_color_delegates(VideoEditorWindow)
    install_creative_delegates(VideoEditorWindow)
    install_actor_delegates(VideoEditorWindow)
    install_ar_pbr_delegates(VideoEditorWindow)
    install_media_preview_export_delegates(VideoEditorWindow)
    install_ai_delegates(VideoEditorWindow)
    install_motion_delegates(VideoEditorWindow)
    VideoEditorWindow._clip_badge_menu_model = _window_clip_badge_menu_model
    VideoEditorWindow._run_clip_badge_menu_action = _window_run_clip_badge_menu_action
    VideoEditorWindow._refresh_preview_after_color_toggle = _window_refresh_preview_after_color_toggle
    VideoEditorWindow._schedule_preview_transition_restore = _window_schedule_preview_transition_restore

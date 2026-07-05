"""Delegate installer for the large VideoEditorWindow compatibility surface."""
from __future__ import annotations

from PySide6.QtCore import QTimer

from app.i18n import tr
from app import video_editor_audio_workspace_workflow as _audio_workspace_workflow
from app import video_editor_context_menu_controller as _context_menu_controller
from app import video_editor_context_menu_workflow as _context_menu_workflow
from app import video_editor_drawing_workflow as _drawing_workflow
from app import video_editor_media_import_controller as _media_import_controller
from app import video_editor_player_bridge as _player_bridge
from app import video_editor_preview_recovery as _preview_recovery
from app import video_editor_proxy_controller as _proxy_controller
from app import video_editor_render_queue_bridge as _render_queue_bridge
from app import video_editor_startup_template_controller as _startup_template_controller
from app import video_editor_subtitle_workflow as _subtitle_workflow
from app import video_editor_timeline_diagnostics as _timeline_diagnostics
from app import video_editor_timeline_layout_workflow as _timeline_layout_workflow
from app import video_editor_thumbnail_controller as _thumbnail_controller
from app import video_editor_transport_workflow as _transport_workflow
from app import video_editor_typography_workflow as _typography_workflow
from app import video_editor_workflow_targeting as _workflow_targeting
from app import video_editor_mmd_workflow as _mmd_workflow
from app import video_editor_live2d_workflow as _live2d_workflow
from app import video_editor_input_workflow as _input_workflow
from app import video_editor_lifecycle_workflow as _lifecycle_workflow
from app import video_editor_localization_controller as _localization_controller
from app import video_editor_screenstudio_workflow as _screenstudio_workflow
from app import video_editor_preset_workflows as _preset_workflows
from app import video_editor_ai_workflow as _ai_workflow
from app import video_editor_broadcast_workflow as _broadcast_workflow
from app import video_editor_export_workflow as _export_workflow
from app import video_editor_node_mask_workflow as _node_mask_workflow
from app import video_editor_project_workflow as _project_workflow
from app import video_editor_quality_workflow as _quality_workflow
from app import video_editor_timeline_operations as _timeline_operations
from app import video_editor_timeline_view_workflow as _timeline_view_workflow
from app import video_editor_pip_workflow as _pip_workflow
from app import video_editor_clip_fx_workflow as _clip_fx_workflow
from app import video_editor_window_chrome_workflow as _window_chrome_workflow
from app import video_editor_history_workflow as _history_workflow
from app import video_editor_fade_workflow as _fade_workflow
from app import video_editor_popout_controller as _popout_controller
from app import video_editor_workbench_controller as _workbench_controller
from app import video_editor_preview_frame_workflow as _preview_frame_workflow
from app import video_editor_preview_placeholder as _preview_placeholder
from app import video_editor_preset_context as _preset_context
from app import video_editor_performance_source_workflow as _performance_source_workflow
from app import video_editor_render_chain_workflow as _render_chain_workflow
from app import video_editor_track_workflow as _track_workflow
from app import video_editor_actor_timeline_workflow as _actor_timeline_workflow
from app import video_editor_timeline_drag_workflow as _timeline_drag_workflow
from app import video_editor_visual_qa_workflow as _visual_qa_workflow
from app import video_editor_window_geometry_workflow as _window_geometry_workflow
from app import video_editor_color_panels as _color_panels
from app.ar_pbr import editor_bridge as _ar_pbr_editor_bridge
from app.ar_pbr import editor_gizmo_bridge as _ar_pbr_editor_gizmo_bridge
from app.video_editor_actor_workspaces import (
    insert_live2d_actor_lane as _insert_live2d_actor_lane_ui,
    insert_spine_actor_lane as _insert_spine_actor_lane_ui,
    open_live2d_clip_editor as _open_live2d_clip_editor_ui,
    open_spine_clip_editor as _open_spine_clip_editor_ui,
)
from app.video_editor_ai_command_controller import (
    build_ai_command_dock as _build_ai_command_dock_ui,
)
from app.video_editor_command_palette_controller import (
    _open_command_palette as _open_command_palette_controller,
)
from app.video_editor_export_snapshot import (
    snapshot_clip_effects_for_export as _snapshot_clip_effects_for_export_helper,
    snapshot_node_item_chain_for_export as _snapshot_node_item_chain_for_export_helper,
)
from app.video_editor_ui_builder import build_video_editor_ui as _build_video_editor_ui
from app.video_editor_ai_command_controller import (  # noqa: F401
    hide_ai_command_dock as _hide_ai_command_dock_ui,
    restore_ai_command_dock_from_popout as _restore_ai_command_dock_from_popout_ui,
    show_ai_command_dock as _show_ai_command_dock_ui,
    toggle_ai_command_dock as _toggle_ai_command_dock_ui,
    toggle_ai_command_popout as _toggle_ai_command_popout_ui,
)
from app.video_editor_command_palette_controller import (  # noqa: F401
    _compact_command_bar as _compact_command_bar_controller,
    _refresh_command_bar_responsive as _refresh_command_bar_responsive_controller,
)
from app.video_editor_section_chrome import (  # noqa: F401
    set_collapsible_host_open as _set_collapsible_host_open_chrome,
)
from app.ar_pbr import editor_window_workflow as _ar_pbr_window_workflow


def _window_refresh_preview_after_color_toggle(self) -> None:
    _preview_recovery.refresh_preview_after_color_toggle(
        self,
        schedule_restore=self._schedule_preview_transition_restore,
    )


def _window_schedule_preview_transition_restore(self, backup: QPixmap | None = None) -> None:
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
    VideoEditorWindow._build_ui = _build_video_editor_ui
    VideoEditorWindow._yield_startup_ui = _lifecycle_workflow._yield_startup_ui
    VideoEditorWindow._record_editor_action = _lifecycle_workflow._record_editor_action
    VideoEditorWindow.closeEvent = _lifecycle_workflow.closeEvent
    VideoEditorWindow.dropEvent = _timeline_layout_workflow.dropEvent
    VideoEditorWindow._update_tracks_host_width = _timeline_layout_workflow._update_tracks_host_width
    VideoEditorWindow._refresh_timeline_mixer_geometry = _timeline_layout_workflow._refresh_timeline_mixer_geometry
    VideoEditorWindow._make_section_header = staticmethod(_window_chrome_workflow._make_section_header)
    VideoEditorWindow._make_command_menu_button = _window_chrome_workflow._make_command_menu_button
    VideoEditorWindow._install_lazy_action_menu = _window_chrome_workflow._install_lazy_action_menu
    VideoEditorWindow._install_lazy_menu_builder = _window_chrome_workflow._install_lazy_menu_builder
    VideoEditorWindow._refresh_command_bar_responsive = _refresh_command_bar_responsive_controller
    VideoEditorWindow._compact_command_bar = _compact_command_bar_controller
    VideoEditorWindow._make_collapsible_section_header = _window_chrome_workflow._make_collapsible_section_header
    VideoEditorWindow._show_existing_button_menu = _window_chrome_workflow._show_existing_button_menu
    VideoEditorWindow._install_icon_pulse = _window_chrome_workflow._install_icon_pulse
    VideoEditorWindow._pulse_icon_button = _window_chrome_workflow._pulse_icon_button
    VideoEditorWindow._set_timeline_palette_collapsed = _window_chrome_workflow._set_timeline_palette_collapsed
    VideoEditorWindow._flash_status = _window_chrome_workflow._flash_status
    VideoEditorWindow._toggle_timeline_popout = _window_chrome_workflow._toggle_timeline_popout
    VideoEditorWindow._on_timeline_popout_closed = _window_chrome_workflow._on_timeline_popout_closed

    # Keep the historical VideoEditorWindow method surface while moving the
    # implementation into smaller owner/duck-typed controller modules.
    VideoEditorWindow._find_track = _track_workflow._find_track
    VideoEditorWindow._active_track = _track_workflow._active_track
    VideoEditorWindow._add_empty_track = _track_workflow._add_empty_track
    VideoEditorWindow._add_empty_audio_track = _track_workflow._add_empty_audio_track
    VideoEditorWindow._clear_active_selection = _track_workflow._clear_active_selection
    VideoEditorWindow._delete_audio_track = _track_workflow._delete_audio_track
    VideoEditorWindow._delete_active_track = _track_workflow._delete_active_track
    VideoEditorWindow._delete_track = _track_workflow._delete_track
    VideoEditorWindow._find_video_clip = _track_workflow._find_video_clip
    VideoEditorWindow._on_track_position_requested = _track_workflow._on_track_position_requested
    VideoEditorWindow._on_track_selection_changed = _track_workflow._on_track_selection_changed
    VideoEditorWindow._on_track_offset_changed = _track_workflow._on_track_offset_changed
    VideoEditorWindow._on_track_fades_changed = _track_workflow._on_track_fades_changed
    VideoEditorWindow._on_track_speed_changed = _track_workflow._on_track_speed_changed
    VideoEditorWindow._clear_selection_active_track = _track_workflow._clear_selection_active_track
    VideoEditorWindow._on_reset_active_track = _track_workflow._on_reset_active_track
    VideoEditorWindow._on_track_zoom_changed = _track_workflow._on_track_zoom_changed
    VideoEditorWindow._add_track_with_source = _track_workflow._add_track_with_source
    VideoEditorWindow._insert_track_widget = _track_workflow._insert_track_widget
    VideoEditorWindow._refresh_video_row_lane_indices = _track_workflow._refresh_video_row_lane_indices
    VideoEditorWindow._add_audio_track_with_source = _track_workflow._add_audio_track_with_source
    VideoEditorWindow._insert_audio_track_widget = _track_workflow._insert_audio_track_widget
    VideoEditorWindow._refresh_audio_row_lane_indices = _track_workflow._refresh_audio_row_lane_indices
    VideoEditorWindow._populate_video_track = _track_workflow._populate_video_track
    VideoEditorWindow._append_clip_to_track = _track_workflow._append_clip_to_track
    VideoEditorWindow._extract_audio_from_video = _track_workflow._extract_audio_from_video
    VideoEditorWindow._start_waveform_extraction = _track_workflow._start_waveform_extraction
    VideoEditorWindow._remove_clip_from_waveform_jobs = _track_workflow._remove_clip_from_waveform_jobs
    VideoEditorWindow._cancel_waveform_job = _track_workflow._cancel_waveform_job
    VideoEditorWindow._refresh_waveform_target_ui = _track_workflow._refresh_waveform_target_ui
    VideoEditorWindow._start_spectrum_extraction = _track_workflow._start_spectrum_extraction
    VideoEditorWindow._on_spectrum_ready = _track_workflow._on_spectrum_ready
    VideoEditorWindow._on_waveform_ready = _track_workflow._on_waveform_ready
    VideoEditorWindow._on_waveform_failed = _track_workflow._on_waveform_failed
    VideoEditorWindow._next_clip_id = _audio_workspace_workflow._next_clip_id
    VideoEditorWindow._find_audio_track = _audio_workspace_workflow._find_audio_track
    VideoEditorWindow._find_audio_clip = _audio_workspace_workflow._find_audio_clip
    VideoEditorWindow._on_audio_track_changed = _audio_workspace_workflow._on_audio_track_changed
    VideoEditorWindow._on_audio_mixer_visibility_changed = _audio_workspace_workflow._on_audio_mixer_visibility_changed
    VideoEditorWindow._on_mixer_pan_changed = _audio_workspace_workflow._on_mixer_pan_changed
    VideoEditorWindow._populate_audio_track = _audio_workspace_workflow._populate_audio_track
    VideoEditorWindow._on_audio_clip_selection_changed = _audio_workspace_workflow._on_audio_clip_selection_changed
    VideoEditorWindow._open_sound_editor = _audio_workspace_workflow._open_sound_editor
    VideoEditorWindow._open_advanced_sound_lab = _audio_workspace_workflow._open_advanced_sound_lab
    VideoEditorWindow._audio_workspace_candidate = _audio_workspace_workflow._audio_workspace_candidate
    VideoEditorWindow._refresh_audio_workspace_panel = _audio_workspace_workflow._refresh_audio_workspace_panel
    VideoEditorWindow._open_selected_audio_workspace = _audio_workspace_workflow._open_selected_audio_workspace
    VideoEditorWindow._toggle_audio_workspace_mixer = _audio_workspace_workflow._toggle_audio_workspace_mixer
    VideoEditorWindow._toggle_audio_workspace_scopes = _audio_workspace_workflow._toggle_audio_workspace_scopes
    VideoEditorWindow._on_audio_volume_changed = _audio_workspace_workflow._on_audio_volume_changed
    VideoEditorWindow._on_workbench_sound_editor_changed = _audio_workspace_workflow._on_workbench_sound_editor_changed
    VideoEditorWindow._on_audio_scopes_toggled = _audio_workspace_workflow._on_audio_scopes_toggled
    VideoEditorWindow._on_audio_mixer_toggled = _audio_workspace_workflow._on_audio_mixer_toggled
    VideoEditorWindow._on_mixer_fader_changed = _audio_workspace_workflow._on_mixer_fader_changed
    VideoEditorWindow._use_vrm_media_as_avatar_target = _performance_source_workflow._use_vrm_media_as_avatar_target
    VideoEditorWindow._media_pool_marks_performance_source = _performance_source_workflow._media_pool_marks_performance_source
    VideoEditorWindow._mark_vtuber_performance_source = staticmethod(_performance_source_workflow._mark_vtuber_performance_source)
    VideoEditorWindow._performance_source_paths_from_mime = _performance_source_workflow._performance_source_paths_from_mime
    VideoEditorWindow._timeline_media_paths_from_mime = _performance_source_workflow._timeline_media_paths_from_mime
    VideoEditorWindow._ensure_performance_source_track = _performance_source_workflow._ensure_performance_source_track
    VideoEditorWindow._add_performance_source_clip = _performance_source_workflow._add_performance_source_clip
    VideoEditorWindow._on_performance_source_dropped = _performance_source_workflow._on_performance_source_dropped
    VideoEditorWindow._on_ar_pbr_asset_dropped_on_video_row = _performance_source_workflow._on_ar_pbr_asset_dropped_on_video_row
    VideoEditorWindow._toggle_play = _transport_workflow._toggle_play
    VideoEditorWindow._stop_transport = _transport_workflow._stop_transport
    VideoEditorWindow._ensure_playback_rate_for_play = _transport_workflow._ensure_playback_rate_for_play
    VideoEditorWindow._on_jog_delta = _transport_workflow._on_jog_delta
    VideoEditorWindow._on_shuttle_speed_changed = _transport_workflow._on_shuttle_speed_changed
    VideoEditorWindow._next_jkl_rate = staticmethod(_transport_workflow._next_jkl_rate)
    VideoEditorWindow._jkl_reverse_jog_ms = staticmethod(_transport_workflow._jkl_reverse_jog_ms)
    VideoEditorWindow._set_transport_speed_label = _transport_workflow._set_transport_speed_label
    VideoEditorWindow._show_viewer_speed_menu = _transport_workflow._show_viewer_speed_menu
    VideoEditorWindow._set_viewer_playback_rate = _transport_workflow._set_viewer_playback_rate
    VideoEditorWindow._show_viewer_compare_menu = _transport_workflow._show_viewer_compare_menu
    VideoEditorWindow._set_viewer_compare_mode = _transport_workflow._set_viewer_compare_mode
    VideoEditorWindow._set_viewer_compare_labels_enabled = _transport_workflow._set_viewer_compare_labels_enabled
    VideoEditorWindow._sync_viewer_compare_button = _transport_workflow._sync_viewer_compare_button
    VideoEditorWindow._apply_jkl_transport = _transport_workflow._apply_jkl_transport
    VideoEditorWindow._step_timeline_frames = _transport_workflow._step_timeline_frames
    VideoEditorWindow._toggle_preview_popout = _transport_workflow._toggle_preview_popout
    VideoEditorWindow._on_preview_popout_closed = _transport_workflow._on_preview_popout_closed
    VideoEditorWindow._timeline_frame_ms = staticmethod(_transport_workflow._timeline_frame_ms)
    VideoEditorWindow._ms_to_timecode = staticmethod(_transport_workflow._ms_to_timecode)
    VideoEditorWindow._bounded_seek_position = staticmethod(_transport_workflow._bounded_seek_position)
    VideoEditorWindow._find_typography_actor = _typography_workflow._find_typography_actor
    VideoEditorWindow._update_text_clip_overlay = _typography_workflow._update_text_clip_overlay
    VideoEditorWindow._on_typography_actor_selected = _typography_workflow._on_typography_actor_selected
    VideoEditorWindow._on_typography_changed = _typography_workflow._on_typography_changed
    VideoEditorWindow._open_typography_editor = _typography_workflow._open_typography_editor
    VideoEditorWindow._show_typography_menu = _typography_workflow._show_typography_menu
    VideoEditorWindow._ensure_text_preview_label = _typography_workflow._ensure_text_preview_label
    VideoEditorWindow._delete_selected_typo_actor = _typography_workflow._delete_selected_typo_actor
    VideoEditorWindow._open_paint_dialog = _drawing_workflow._open_paint_dialog
    VideoEditorWindow._spawn_bubble_item = _drawing_workflow._spawn_bubble_item
    VideoEditorWindow._remove_bubble = _drawing_workflow._remove_bubble
    VideoEditorWindow._resync_bubbles_to_preview = _drawing_workflow._resync_bubbles_to_preview
    VideoEditorWindow._update_bubble_visibility = _drawing_workflow._update_bubble_visibility
    VideoEditorWindow._spawn_sticker_item = _drawing_workflow._spawn_sticker_item
    VideoEditorWindow._remove_sticker = _drawing_workflow._remove_sticker
    VideoEditorWindow._duplicate_sticker = _drawing_workflow._duplicate_sticker
    VideoEditorWindow._reorder_sticker = _drawing_workflow._reorder_sticker
    VideoEditorWindow._resync_stickers_to_preview = _drawing_workflow._resync_stickers_to_preview
    VideoEditorWindow._update_sticker_visibility = _drawing_workflow._update_sticker_visibility
    VideoEditorWindow._timeline_edge_proxy_clips = staticmethod(_timeline_diagnostics._timeline_edge_proxy_clips)
    VideoEditorWindow._timeline_edge_issue_summary = staticmethod(_timeline_diagnostics._timeline_edge_issue_summary)
    VideoEditorWindow._add_timeline_media_from_mime = _media_import_controller.add_timeline_media_from_mime
    VideoEditorWindow._on_media_pool_item_added = _media_import_controller.on_media_pool_item_added
    VideoEditorWindow._on_media_pool_selection_changed = _media_import_controller.on_media_pool_selection_changed
    VideoEditorWindow._on_media_dropped_on_video_row = _media_import_controller.on_media_dropped_on_video_row
    VideoEditorWindow._on_media_dropped_on_audio_row = _media_import_controller.on_media_dropped_on_audio_row
    VideoEditorWindow._on_audio_load_source_requested = _context_menu_workflow._on_audio_load_source_requested
    VideoEditorWindow._on_audio_row_context_menu = _context_menu_workflow._on_audio_row_context_menu
    VideoEditorWindow._on_audio_clip_context_menu = _context_menu_workflow._on_audio_clip_context_menu
    VideoEditorWindow._on_clip_badge_action_requested = _context_menu_workflow._on_clip_badge_action_requested
    VideoEditorWindow._on_clip_badge_context_menu = _context_menu_workflow._on_clip_badge_context_menu
    VideoEditorWindow._first_overlapping_actor_ms = staticmethod(_context_menu_workflow._first_overlapping_actor_ms)
    VideoEditorWindow._on_video_clip_context_menu = _context_menu_workflow._on_video_clip_context_menu
    VideoEditorWindow._extract_audio_from_video_selection = _context_menu_workflow._extract_audio_from_video_selection
    VideoEditorWindow._edit_nested_sequence_clip = _context_menu_workflow._edit_nested_sequence_clip
    VideoEditorWindow._open_clip_effects = _context_menu_workflow._open_clip_effects
    VideoEditorWindow._on_track_context_menu = _context_menu_workflow._on_track_context_menu
    VideoEditorWindow.eventFilter = _input_workflow.eventFilter
    VideoEditorWindow.keyPressEvent = _input_workflow.keyPressEvent
    VideoEditorWindow.dragEnterEvent = _input_workflow.dragEnterEvent
    VideoEditorWindow.dragMoveEvent = _input_workflow.dragMoveEvent
    VideoEditorWindow._show_preview_context_menu = _input_workflow._show_preview_context_menu
    VideoEditorWindow._preview_has_renderable_content = _input_workflow._preview_has_renderable_content
    VideoEditorWindow._ensure_preview_pixmap_for_paint = _input_workflow._ensure_preview_pixmap_for_paint
    VideoEditorWindow._escape_timeline_context = _input_workflow._escape_timeline_context
    
    VideoEditorWindow._clip_badge_menu_model = _window_clip_badge_menu_model
    VideoEditorWindow._run_clip_badge_menu_action = _window_run_clip_badge_menu_action
    
    VideoEditorWindow._update_subtitle_overlay = _subtitle_workflow.update_subtitle_overlay
    VideoEditorWindow._reposition_subtitle_overlay = _subtitle_workflow.reposition_subtitle_overlay
    VideoEditorWindow._on_subtitles_changed = _subtitle_workflow.on_subtitles_changed
    VideoEditorWindow._on_subtitle_lane_edit = _subtitle_workflow.on_subtitle_lane_edit
    VideoEditorWindow._generate_ai_subtitles = _subtitle_workflow.generate_ai_subtitles
    
    VideoEditorWindow._refresh_preview_after_color_toggle = _window_refresh_preview_after_color_toggle
    VideoEditorWindow._start_preview_transition_guard = _preview_recovery.start_preview_transition_guard
    VideoEditorWindow._schedule_preview_transition_restore = _window_schedule_preview_transition_restore
    VideoEditorWindow._preview_tab_guard_active = _preview_recovery.preview_tab_guard_active
    VideoEditorWindow._preview_black_recovery_active = _preview_recovery.preview_black_recovery_active
    VideoEditorWindow._pixmap_looks_like_blank_preview = staticmethod(_preview_recovery.pixmap_looks_like_blank_preview)
    VideoEditorWindow._rgb_looks_like_blank_preview = staticmethod(_preview_recovery.rgb_looks_like_blank_preview)
    VideoEditorWindow._pixmap_looks_like_black_frame = staticmethod(_preview_recovery.pixmap_looks_like_black_frame)
    VideoEditorWindow._preview_recovery_source = _preview_recovery.preview_recovery_source
    VideoEditorWindow._preview_recovery_rgb = _preview_recovery.preview_recovery_rgb
    VideoEditorWindow._remember_good_preview_pixmap = _preview_recovery.remember_good_preview_pixmap
    VideoEditorWindow._restore_preview_if_tab_switch_blank = _preview_recovery.restore_preview_if_tab_switch_blank
    
    VideoEditorWindow._collect_nested_audio_preview_clips = _player_bridge.collect_nested_audio_preview_clips
    VideoEditorWindow._on_player_error = _player_bridge._on_player_error
    VideoEditorWindow._on_media_status = _player_bridge._on_media_status
    VideoEditorWindow._sync_nested_audio_preview_track = _player_bridge.sync_nested_audio_preview_track
    VideoEditorWindow._sync_ar_pbr_tracks_to_player = _ar_pbr_editor_bridge.sync_tracks_to_player
    VideoEditorWindow._set_ar_pbr_track_center_norm = staticmethod(_ar_pbr_editor_bridge.set_track_center_norm)
    VideoEditorWindow._set_ar_pbr_track_uniform_scale = staticmethod(_ar_pbr_editor_bridge.set_track_uniform_scale)
    VideoEditorWindow._set_ar_pbr_track_axis_scale = staticmethod(_ar_pbr_editor_bridge.set_track_axis_scale)
    VideoEditorWindow._set_ar_pbr_track_position_z = staticmethod(_ar_pbr_editor_bridge.set_track_position_z)
    VideoEditorWindow._set_ar_pbr_track_rotation_value = staticmethod(_ar_pbr_editor_bridge.set_track_rotation_value)
    VideoEditorWindow._set_ar_pbr_track_yaw = staticmethod(_ar_pbr_editor_bridge.set_track_yaw)
    VideoEditorWindow._ar_pbr_project_gizmo_vec3 = staticmethod(_ar_pbr_editor_bridge.project_gizmo_vec3)
    VideoEditorWindow._ar_pbr_project_gizmo_axis = staticmethod(_ar_pbr_editor_bridge.project_gizmo_axis)
    VideoEditorWindow._ar_pbr_gizmo_ring_points = staticmethod(_ar_pbr_editor_bridge.gizmo_ring_points)
    VideoEditorWindow._ar_pbr_distance_to_polyline = staticmethod(_ar_pbr_editor_bridge.distance_to_polyline)
    VideoEditorWindow._sync_mmd_tracks_to_player = _mmd_workflow._sync_mmd_tracks_to_player
    VideoEditorWindow._refresh_player_tracks = _player_bridge.refresh_player_tracks
    VideoEditorWindow._on_playback_state_changed = _player_bridge.on_playback_state_changed
    VideoEditorWindow._on_position_changed = _player_bridge.on_position_changed
    VideoEditorWindow._update_audio_level_meters = _player_bridge.update_audio_level_meters
    VideoEditorWindow._on_duration_changed = _player_bridge.on_duration_changed
    
    VideoEditorWindow._stage_ai_script_render_jobs = _render_queue_bridge.stage_ai_script_render_jobs
    VideoEditorWindow._queue_creator_assist_exports = _render_queue_bridge.queue_creator_assist_exports
    VideoEditorWindow._stage_creator_assist_render_jobs = _render_queue_bridge.stage_creator_assist_render_jobs
    VideoEditorWindow._toggle_render_queue_popout = _render_queue_bridge.toggle_render_queue_popout
    
    VideoEditorWindow._startup_template_status = _startup_template_controller._startup_template_status
    VideoEditorWindow._refresh_startup_template_ui = _startup_template_controller._refresh_startup_template_ui
    VideoEditorWindow.show_startup_template_hint = _startup_template_controller.show_startup_template_hint
    VideoEditorWindow._startup_template_has_media_target = _startup_template_controller._startup_template_has_media_target
    VideoEditorWindow._startup_template_target_state = _startup_template_controller._startup_template_target_state
    VideoEditorWindow._startup_template_required_target_gap = _startup_template_controller._startup_template_required_target_gap
    VideoEditorWindow._startup_template_preset = _startup_template_controller._startup_template_preset
    VideoEditorWindow._try_apply_startup_template_if_ready = _startup_template_controller._try_apply_startup_template_if_ready
    
    VideoEditorWindow._retire_thumbnail_extractor = _thumbnail_controller.retire_thumbnail_extractor
    VideoEditorWindow._start_thumbnail_extraction = _thumbnail_controller.start_thumbnail_extraction
    VideoEditorWindow._on_thumb_count = _thumbnail_controller.on_thumb_count
    VideoEditorWindow._on_thumb_ready = _thumbnail_controller.on_thumb_ready
    VideoEditorWindow._on_extractor_done = _thumbnail_controller.on_extractor_done
    VideoEditorWindow._start_thumbnail_extraction_for_clip = _thumbnail_controller.start_thumbnail_extraction_for_clip
    VideoEditorWindow._on_clip_thumb_count = _thumbnail_controller.on_clip_thumb_count
    VideoEditorWindow._on_clip_thumb_ready = _thumbnail_controller.on_clip_thumb_ready
    VideoEditorWindow._on_clip_extractor_done = _thumbnail_controller.on_clip_extractor_done
    
    VideoEditorWindow._first_video_clip_candidate = _workflow_targeting.first_video_clip_candidate
    VideoEditorWindow._select_workflow_video_clip = _workflow_targeting.select_workflow_video_clip
    VideoEditorWindow._first_media_pool_path = _workflow_targeting.first_media_pool_path
    VideoEditorWindow._actor_model_candidate = _workflow_targeting.actor_model_candidate
    VideoEditorWindow._selected_video_clip = _workflow_targeting.selected_video_clip
    VideoEditorWindow._workflow_target_video_clip = _workflow_targeting.workflow_target_video_clip
    VideoEditorWindow._workflow_start_ms = _workflow_targeting.workflow_start_ms
    VideoEditorWindow._focus_preview_at_workflow_ms = _workflow_targeting.focus_preview_at_workflow_ms
    
    VideoEditorWindow._owner_original_source = staticmethod(_proxy_controller.owner_original_source)
    VideoEditorWindow._fresh_proxy_for = _proxy_controller.fresh_proxy_for
    VideoEditorWindow._apply_proxy_owner = staticmethod(_proxy_controller.apply_proxy_owner)
    VideoEditorWindow._active_proxy_source_path = _proxy_controller.active_proxy_source_path
    VideoEditorWindow._proxy_status_for_path = _proxy_controller.proxy_status_for_path
    VideoEditorWindow._refresh_proxy_status_ui = _proxy_controller.refresh_proxy_status_ui
    VideoEditorWindow._toggle_proxy_mode = _proxy_controller.toggle_proxy_mode
    VideoEditorWindow._start_proxy_generation = _proxy_controller.start_proxy_generation
    VideoEditorWindow._on_proxy_done = _proxy_controller.on_proxy_done
    VideoEditorWindow._on_proxy_failed = _proxy_controller.on_proxy_failed
    VideoEditorWindow._regenerate_proxy_for_active_source = _proxy_controller.regenerate_proxy_for_active_source
    VideoEditorWindow._delete_proxy_for_active_source = _proxy_controller.delete_proxy_for_active_source
    
    
    
    # Additional direct delegates: these used to be one-line methods on VideoEditorWindow.
    VideoEditorWindow._active_video_clips_for_storyboard = _live2d_workflow._active_video_clips_for_storyboard
    VideoEditorWindow._add_mmd_asset_to_timeline = _mmd_workflow._add_mmd_asset_to_timeline
    VideoEditorWindow._apply_ai_script_edit_plan = _ai_workflow._apply_ai_script_edit_plan
    VideoEditorWindow._apply_creator_assist_bundle = _screenstudio_workflow._apply_creator_assist_bundle
    VideoEditorWindow._apply_creator_assist_markers = _screenstudio_workflow._apply_creator_assist_markers
    VideoEditorWindow._apply_creator_assist_quick_create = _screenstudio_workflow._apply_creator_assist_quick_create
    VideoEditorWindow._apply_creator_assist_settings = _screenstudio_workflow._apply_creator_assist_settings
    VideoEditorWindow._apply_creator_assist_subtitles = _screenstudio_workflow._apply_creator_assist_subtitles
    VideoEditorWindow._apply_editor_preset_object = _preset_workflows._apply_editor_preset_object
    VideoEditorWindow._open_template_browser = _preset_workflows._open_template_browser
    VideoEditorWindow._apply_auto_preset_plan = _preset_workflows._apply_auto_preset_plan
    VideoEditorWindow._workflow_apply_summary_text = staticmethod(_preset_workflows._workflow_apply_summary_text)
    VideoEditorWindow._show_workflow_apply_summary_toast = _preset_workflows._show_workflow_apply_summary_toast
    VideoEditorWindow._apply_effect_preset_from_left_panel = _preset_workflows._apply_effect_preset_from_left_panel
    VideoEditorWindow._apply_effect_workflow_preset = _preset_workflows._apply_effect_workflow_preset
    VideoEditorWindow._apply_transition_workflow_preset = _preset_workflows._apply_transition_workflow_preset
    VideoEditorWindow._add_title_workflow_actor = _preset_workflows._add_title_workflow_actor
    VideoEditorWindow._add_caption_style_workflow_actor = _preset_workflows._add_caption_style_workflow_actor
    VideoEditorWindow._add_sticker_workflow_actor = _preset_workflows._add_sticker_workflow_actor
    VideoEditorWindow._add_motion_workflow_actor = _preset_workflows._add_motion_workflow_actor
    VideoEditorWindow._add_actor_workflow_preset = _preset_workflows._add_actor_workflow_preset
    VideoEditorWindow._apply_live2d_motion_storyboard = _live2d_workflow._apply_live2d_motion_storyboard
    VideoEditorWindow._apply_live2d_motion_storyboard_to_clip = _live2d_workflow._apply_live2d_motion_storyboard_to_clip
    VideoEditorWindow._apply_node_effect = staticmethod(_node_mask_workflow.apply_node_effect)
    VideoEditorWindow._apply_performance_source_to_selected_live2d = _live2d_workflow._apply_performance_source_to_selected_live2d
    VideoEditorWindow._apply_professional_ui_labels = _localization_controller._apply_professional_ui_labels
    VideoEditorWindow._apply_screenstudio_auto_polish = _screenstudio_workflow._apply_screenstudio_auto_polish
    VideoEditorWindow._apply_video_mocap_to_live2d = _live2d_workflow._apply_video_mocap_to_live2d
    VideoEditorWindow._ar_pbr_active_tracks_at_playhead = _ar_pbr_editor_bridge.active_tracks_at_playhead
    VideoEditorWindow._ar_pbr_clamp01 = staticmethod(_ar_pbr_editor_bridge.clamp01)
    VideoEditorWindow._ar_pbr_cursor_for_gizmo_mode = staticmethod(_ar_pbr_editor_gizmo_bridge.cursor_for_gizmo_mode)
    VideoEditorWindow._ar_pbr_distance_to_segment = staticmethod(_ar_pbr_editor_bridge.distance_to_segment)
    VideoEditorWindow._ar_pbr_ellipse_ring_hit = staticmethod(_ar_pbr_editor_bridge.ellipse_ring_hit)
    VideoEditorWindow._ar_pbr_gizmo_axis_index = staticmethod(_ar_pbr_editor_bridge.axis_index)
    VideoEditorWindow._ar_pbr_gizmo_geometry = _ar_pbr_editor_bridge.gizmo_geometry
    VideoEditorWindow._ar_pbr_gizmo_hit_test = _ar_pbr_editor_gizmo_bridge.gizmo_hit_test
    VideoEditorWindow._ar_pbr_gizmo_interaction_for_canvas = _ar_pbr_editor_gizmo_bridge.gizmo_interaction_for_canvas
    VideoEditorWindow._ar_pbr_gizmo_visible_track = _ar_pbr_editor_gizmo_bridge.gizmo_visible_track
    VideoEditorWindow._ar_pbr_preview_registry = _ar_pbr_editor_bridge.preview_registry
    VideoEditorWindow._ar_pbr_project_gizmo_point3 = staticmethod(_ar_pbr_editor_bridge.project_gizmo_point3)
    VideoEditorWindow._ar_pbr_rotate_vec3 = staticmethod(_ar_pbr_editor_bridge.rotate_vec3)
    VideoEditorWindow._ar_pbr_runtime_image_point_for_track = _ar_pbr_editor_gizmo_bridge.runtime_image_point_for_track
    VideoEditorWindow._ar_pbr_selected_track = _ar_pbr_editor_gizmo_bridge.selected_track
    VideoEditorWindow._ar_pbr_track_by_id = _ar_pbr_editor_gizmo_bridge.track_by_id
    VideoEditorWindow._ar_pbr_track_center_norm = _ar_pbr_editor_bridge.track_center_norm
    VideoEditorWindow._ar_pbr_track_lighting_dict = staticmethod(_ar_pbr_editor_bridge.track_lighting_dict)
    VideoEditorWindow._ar_pbr_track_position_z = staticmethod(_ar_pbr_editor_bridge.track_position_z)
    VideoEditorWindow._ar_pbr_track_rotation_value = staticmethod(_ar_pbr_editor_bridge.track_rotation_value)
    VideoEditorWindow._ar_pbr_track_rotation_values = staticmethod(_ar_pbr_editor_bridge.track_rotation_values)
    VideoEditorWindow._ar_pbr_track_scale_values = staticmethod(_ar_pbr_editor_bridge.track_scale_values)
    VideoEditorWindow._ar_pbr_track_uniform_scale = staticmethod(_ar_pbr_editor_bridge.track_uniform_scale)
    VideoEditorWindow._ar_pbr_track_yaw = staticmethod(_ar_pbr_editor_bridge.track_yaw)
    for _ar_window_name in (
        "_open_vrm_media_in_vtuber_studio",
        "_qt_object_valid",
        "_remember_ar_pbr_preview_window",
        "_schedule_ar_pbr_descriptor_prewarm",
        "_open_ar_pbr_asset_preview",
        "_ar_pbr_track_lighting_settings",
        "_apply_ar_pbr_lighting_settings_to_track",
        "_open_ar_pbr_track_model_view",
        "_ar_pbr_paths_from_mime",
        "_vrm_avatar_paths_from_mime",
        "_mmd_paths_from_mime",
        "_ar_pbr_lane_for_track",
        "_insert_ar_pbr_actor_lane",
        "_remove_ar_pbr_actor_lane",
        "_set_ar_pbr_row_selection",
        "_select_ar_pbr_track",
        "_rebuild_ar_pbr_actor_lanes",
        "_on_ar_pbr_lane_track_changed",
        "_refresh_ar_pbr_track_after_lane_change",
        "_delete_ar_pbr_track",
        "_refresh_preview_canvas_interaction_hook",
        "_refresh_preview_popout_overlay_hooks",
        "_preview_canvas_interaction",
        "_preview_popout_canvas_interaction",
        "_paint_preview_canvas_overlay",
        "_paint_comparison_canvas_overlay",
        "_refresh_ar_pbr_preview_after_gizmo_change",
        "_begin_ar_pbr_depth_interaction_cue",
        "_end_ar_pbr_depth_interaction_cue",
        "_ar_pbr_gizmo_interaction",
        "_paint_ar_pbr_gizmo_overlay",
        "_add_ar_pbr_asset_to_preview",
    ):
        setattr(VideoEditorWindow, _ar_window_name, getattr(_ar_pbr_window_workflow, _ar_window_name))
    VideoEditorWindow._autosave_path = _project_workflow._autosave_path
    VideoEditorWindow._analyze_creator_assist = _screenstudio_workflow._analyze_creator_assist
    VideoEditorWindow._audio_delivery_export_note = _quality_workflow._audio_delivery_export_note
    VideoEditorWindow._begin_preset_live_preview = _preset_workflows._begin_preset_live_preview
    VideoEditorWindow._browse_mmd_motion_for_track = _mmd_workflow._browse_mmd_motion_for_track
    VideoEditorWindow._build_ai_command_dock = _build_ai_command_dock_ui
    VideoEditorWindow._toggle_ai_command_dock = _toggle_ai_command_dock_ui
    VideoEditorWindow._show_ai_command_dock = _show_ai_command_dock_ui
    VideoEditorWindow._hide_ai_command_dock = _hide_ai_command_dock_ui
    VideoEditorWindow._toggle_ai_command_popout = _toggle_ai_command_popout_ui
    VideoEditorWindow._restore_ai_command_dock_from_popout = _restore_ai_command_dock_from_popout_ui
    for _ai_name in (
        "_open_ai_command_review_panel",
        "_prime_ai_review_panel",
        "_open_ai_script_review_dialog",
        "_current_ai_command_action_plan",
        "_ensure_python_action_registry",
        "_run_review_scenario",
        "_build_ai_command_action_plan_payload",
        "_format_ai_action_plan_text",
        "_open_ai_action_review_dialog",
        "_execute_ai_command_action_plan",
        "_clear_ai_action_review_dialog",
        "_clear_ai_review_dialog",
        "_ai_command_set_status",
        "_ai_command_append_chat",
        "_ai_command_selected_provider_name",
        "_on_ai_command_provider_changed",
        "_selected_ai_command_provider_id",
        "_open_ai_provider_setup_dialog",
        "_open_ai_provider_setup_for_id",
        "_refresh_ai_script_edit_provider_status",
        "_show_ai_provider_instructions",
        "_open_claude_provider_setup_dialog",
        "_open_claude_mcp_progress_dialog",
        "_claude_mcp_log",
        "_claude_mcp_state",
        "_start_claude_mcp_auto_connect",
        "_start_claude_mcp_status_check",
        "_start_claude_mcp_process",
        "_claude_mcp_read_output",
        "_claude_mcp_process_error",
        "_claude_mcp_process_finished",
        "_claude_mcp_finish_ui",
        "_claude_mcp_start_close_attention",
        "_claude_mcp_stop_close_attention",
        "_claude_mcp_cancel",
        "_open_qwen_provider_setup_dialog",
        "_start_default_free_ai_install",
        "_open_qwen_install_progress_dialog",
        "_qwen_install_log",
        "_qwen_install_state",
        "_qwen_install_cached_model_path",
        "_qwen_install_runner_candidates",
        "_qwen_install_find_runner",
        "_qwen_install_begin",
        "_qwen_install_start_winget",
        "_qwen_install_winget_finished",
        "_qwen_install_start_server_after_install",
        "_qwen_install_start_server",
        "_qwen_install_read_output",
        "_qwen_install_server_output",
        "_qwen_install_process_error",
        "_qwen_install_server_finished",
        "_shutdown_qwen_local_processes",
        "_qwen_install_probe_server",
        "_qwen_install_finish_ui",
        "_qwen_install_start_close_attention",
        "_qwen_install_stop_close_attention",
        "_qwen_install_cancel",
        "_save_qwen_endpoint_from_dialog",
        "_choose_qwen_model_path",
        "_ai_command_transcript_text",
        "_ai_command_prompt_only_plan",
        "_handle_ai_command_status_prompt",
        "_generate_ai_command_plan",
        "_ensure_ai_script_edit_panel",
        "_open_ai_script_edit_panel",
        "_ai_project_snapshot",
        "_log_ai_script_action",
        "_validate_ai_script_edit_plan",
        "_ensure_automation_registry",
        "automation_command_specs",
        "automation_execute_command",
        "automation_bridge_handle",
        "automation_mcp_handle",
        "_on_ai_script_edit_plan_generated",
        "_current_ai_script_edit_plan",
        "_apply_ai_script_edit_selected",
        "_apply_ai_script_edit_all",
        "_apply_ai_script_edit_cuts",
        "_apply_ai_script_subtitles",
        "_apply_ai_script_markers",
        "_ai_script_auto_zoom_sidecars",
        "_apply_ai_script_auto_suggestions",
        "_first_ai_script_video_start_ms",
        "_sync_ai_script_applied_cut_markers",
        "_store_ai_script_edit_payload",
    ):
        setattr(VideoEditorWindow, _ai_name, getattr(_ai_workflow, _ai_name))
    VideoEditorWindow._ai_command_format_srt_ms = staticmethod(_ai_workflow._ai_command_format_srt_ms)
    VideoEditorWindow._build_color_grading_panel = _color_panels._build_color_grading_panel
    VideoEditorWindow._build_color_inline_panel = _color_panels._build_color_inline_panel
    VideoEditorWindow._build_color_compact_palette_panel = _color_panels._build_color_compact_palette_panel
    VideoEditorWindow._build_color_reference_workbench_panel = _color_panels._build_color_reference_workbench_panel
    VideoEditorWindow.parent_widget_for_color = _color_panels.parent_widget_for_color
    VideoEditorWindow._toggle_color_popout = _color_panels._toggle_color_popout
    VideoEditorWindow._on_color_popout_closed = _color_panels._on_color_popout_closed
    VideoEditorWindow._on_color_page_closed = _color_panels._on_color_page_closed
    VideoEditorWindow._disable_color_power_window_overlay = _color_panels._disable_color_power_window_overlay
    VideoEditorWindow._show_color_dock_page = _color_panels._show_color_dock_page
    VideoEditorWindow._open_color_page = _color_panels._open_color_page
    VideoEditorWindow._switch_page = _color_panels._switch_page
    VideoEditorWindow._close_color_page = _color_panels._close_color_page
    VideoEditorWindow._on_color_page_grade_changed = _color_panels._on_color_page_grade_changed
    VideoEditorWindow._sync_color_power_window_overlay = _color_panels._sync_color_power_window_overlay
    VideoEditorWindow._on_color_power_window_dragged = _color_panels._on_color_power_window_dragged
    VideoEditorWindow._active_color_grade = _color_panels._active_color_grade
    VideoEditorWindow._set_color_preview_compare_mode = _color_panels._set_color_preview_compare_mode
    VideoEditorWindow._load_lut_file = _color_panels._load_lut_file
    VideoEditorWindow._on_lut_strength_changed = _color_panels._on_lut_strength_changed
    VideoEditorWindow._clear_lut = _color_panels._clear_lut
    VideoEditorWindow._on_color_slider_changed = _color_panels._on_color_slider_changed
    VideoEditorWindow._on_color_wheel_changed = _color_panels._on_color_wheel_changed
    VideoEditorWindow._reset_color_wheel_region = _color_panels._reset_color_wheel_region
    VideoEditorWindow._sync_both_color_panels_except = _color_panels._sync_both_color_panels_except
    VideoEditorWindow._on_color_luma_changed = _color_panels._on_color_luma_changed
    VideoEditorWindow._on_hue_curve_changed = _color_panels._on_hue_curve_changed
    VideoEditorWindow._on_color_reset = _color_panels._on_color_reset
    VideoEditorWindow._on_color_preset_picked = _color_panels._on_color_preset_picked
    VideoEditorWindow._on_professional_color_preset_picked = _color_panels._on_professional_color_preset_picked
    VideoEditorWindow._update_wheel_readouts = _color_panels._update_wheel_readouts
    VideoEditorWindow._refresh_color_preset_btn_label = _color_panels._refresh_color_preset_btn_label
    VideoEditorWindow._build_color_preset_menu = _color_panels._build_color_preset_menu
    VideoEditorWindow._build_language_menu = _localization_controller._build_language_menu
    VideoEditorWindow._build_node_item_chain = staticmethod(_node_mask_workflow.build_node_item_chain)
    VideoEditorWindow._claude_mcp_add_args = _ai_workflow._claude_mcp_add_args
    for _broadcast_name in (
        "_open_vtuber_broadcast_studio",
        "_broadcast_output_canvas",
        "_broadcast_output_session_status",
        "_start_broadcast_live_target",
        "_start_broadcast_audio_mixdown_if_needed",
        "_on_broadcast_audio_mixdown_progress",
        "_on_broadcast_audio_mixdown_finished",
        "_prepare_broadcast_live_target_audio",
        "_stop_broadcast_live_target",
        "_feed_broadcast_output_frame",
        "_update_vtuber_studio_live_session_status",
    ):
        setattr(VideoEditorWindow, _broadcast_name, getattr(_broadcast_workflow, _broadcast_name))
    VideoEditorWindow._cleanup_timeline_micro_edges = _timeline_operations._cleanup_timeline_micro_edges
    VideoEditorWindow._clip_audition_range = _timeline_operations._clip_audition_range
    VideoEditorWindow._is_text_focus = _timeline_view_workflow._is_text_focus
    VideoEditorWindow._clamp_timeline_zoom_px = staticmethod(_timeline_view_workflow._clamp_timeline_zoom_px)
    VideoEditorWindow._change_zoom = _timeline_view_workflow._change_zoom
    VideoEditorWindow._format_zoom = _timeline_view_workflow._format_zoom
    VideoEditorWindow._shortcut_zoom_in = _timeline_view_workflow._shortcut_zoom_in
    VideoEditorWindow._shortcut_zoom_out = _timeline_view_workflow._shortcut_zoom_out
    VideoEditorWindow._shortcut_zoom_fit = _timeline_view_workflow._shortcut_zoom_fit
    VideoEditorWindow._mark_in_at_playhead = _timeline_view_workflow._mark_in_at_playhead
    VideoEditorWindow._mark_out_at_playhead = _timeline_view_workflow._mark_out_at_playhead
    VideoEditorWindow._speed_at = staticmethod(_timeline_view_workflow._speed_at)
    VideoEditorWindow._timeline_nudge_step_ms = staticmethod(_timeline_view_workflow._timeline_nudge_step_ms)
    VideoEditorWindow._on_timeline_tool_action = _timeline_view_workflow._on_timeline_tool_action
    VideoEditorWindow._set_timeline_tool_mode = _timeline_view_workflow._set_timeline_tool_mode
    VideoEditorWindow._tick_blade_dash = _timeline_view_workflow._tick_blade_dash
    VideoEditorWindow._on_track_empty_area_clicked = _timeline_view_workflow._on_track_empty_area_clicked
    VideoEditorWindow._broadcast_clip_selection = _timeline_view_workflow._broadcast_clip_selection
    VideoEditorWindow._sync_media_pool_featured_to_selected_clip = _timeline_view_workflow._sync_media_pool_featured_to_selected_clip
    VideoEditorWindow._refresh_nested_group_counter = _timeline_view_workflow._refresh_nested_group_counter
    VideoEditorWindow._set_global_in = _timeline_view_workflow._set_global_in
    VideoEditorWindow._set_global_out = _timeline_view_workflow._set_global_out
    VideoEditorWindow._clear_global_markers = _timeline_view_workflow._clear_global_markers
    VideoEditorWindow._add_marker_at_playhead = _timeline_view_workflow._add_marker_at_playhead
    VideoEditorWindow._delete_timeline_marker = _timeline_view_workflow._delete_timeline_marker
    VideoEditorWindow._sync_markers_to_ruler = _timeline_view_workflow._sync_markers_to_ruler
    VideoEditorWindow._push_snap_targets_to_rows = _timeline_view_workflow._push_snap_targets_to_rows
    VideoEditorWindow._find_zoom_actor = _timeline_view_workflow._find_zoom_actor
    VideoEditorWindow._open_zoom_editor = _timeline_view_workflow._open_zoom_editor
    VideoEditorWindow._show_zoom_menu = _timeline_view_workflow._show_zoom_menu
    VideoEditorWindow._candidate_tracks_at = _timeline_view_workflow._candidate_tracks_at
    VideoEditorWindow._set_timeline_zoom_px = _timeline_view_workflow._set_timeline_zoom_px
    VideoEditorWindow._zoom_fit = _timeline_view_workflow._zoom_fit
    VideoEditorWindow._timeline_clip_bounds_for_review = staticmethod(_timeline_view_workflow._timeline_clip_bounds_for_review)
    VideoEditorWindow._selected_timeline_review_center_ms = _timeline_view_workflow._selected_timeline_review_center_ms
    VideoEditorWindow._apply_timeline_review_framing = _timeline_view_workflow._apply_timeline_review_framing
    VideoEditorWindow._timeline_scroll_for_visible_playhead = staticmethod(_timeline_view_workflow._timeline_scroll_for_visible_playhead)
    VideoEditorWindow._ensure_playhead_visible = _timeline_view_workflow._ensure_playhead_visible
    VideoEditorWindow._move_track = _timeline_view_workflow._move_track
    VideoEditorWindow._set_active_track = _timeline_view_workflow._set_active_track
    VideoEditorWindow._update_timeline_status = _timeline_view_workflow._update_timeline_status
    VideoEditorWindow._on_clip_clicked = _timeline_view_workflow._on_clip_clicked
    VideoEditorWindow._refresh_selection_row = _timeline_view_workflow._refresh_selection_row
    VideoEditorWindow._clip_param_active = staticmethod(_clip_fx_workflow._clip_param_active)
    VideoEditorWindow._clip_has_active_fx = _clip_fx_workflow._clip_has_active_fx
    VideoEditorWindow._clip_has_disabled_fx = _clip_fx_workflow._clip_has_disabled_fx
    VideoEditorWindow._clear_clip_fx = _clip_fx_workflow._clear_clip_fx
    VideoEditorWindow._set_clip_fx_enabled = _clip_fx_workflow._set_clip_fx_enabled
    VideoEditorWindow._target_clip_for_fx_action = _clip_fx_workflow._target_clip_for_fx_action
    VideoEditorWindow._clear_selected_clip_fx = _clip_fx_workflow._clear_selected_clip_fx
    VideoEditorWindow._toggle_selected_clip_fx_enabled = _clip_fx_workflow._toggle_selected_clip_fx_enabled
    VideoEditorWindow._open_selected_clip_fx = _clip_fx_workflow._open_selected_clip_fx
    VideoEditorWindow._effect_payload_from_clip = _clip_fx_workflow._effect_payload_from_clip
    VideoEditorWindow._refresh_pip_panel = _pip_workflow._refresh_pip_panel
    VideoEditorWindow._sync_pip_sliders_to_position = _pip_workflow._sync_pip_sliders_to_position
    VideoEditorWindow._on_pip_enable_toggled = _pip_workflow._on_pip_enable_toggled
    VideoEditorWindow._on_pip_slider_changed = _pip_workflow._on_pip_slider_changed
    VideoEditorWindow._refresh_pip_kf_list = _pip_workflow._refresh_pip_kf_list
    VideoEditorWindow._pip_add_keyframe = _pip_workflow._pip_add_keyframe
    VideoEditorWindow._pip_delete_keyframe = _pip_workflow._pip_delete_keyframe
    VideoEditorWindow._on_workbench_fade_in_changed = _fade_workflow._on_workbench_fade_in_changed
    VideoEditorWindow._on_workbench_fade_out_changed = _fade_workflow._on_workbench_fade_out_changed
    VideoEditorWindow._build_fade_card = _fade_workflow._build_fade_card
    VideoEditorWindow._set_video_track_leading_fade = _fade_workflow._set_video_track_leading_fade
    VideoEditorWindow._set_video_track_trailing_fade = _fade_workflow._set_video_track_trailing_fade
    VideoEditorWindow._on_workbench_volume_changed = _fade_workflow._on_workbench_volume_changed
    VideoEditorWindow._current_fade_multiplier = _fade_workflow._current_fade_multiplier
    VideoEditorWindow._clip_preview_frame_size = staticmethod(_screenstudio_workflow._clip_preview_frame_size)
    VideoEditorWindow._commit_color_preview_edit = _color_panels._commit_color_preview_edit
    VideoEditorWindow._compact_color_card_style = staticmethod(_color_panels._compact_color_card_style)
    VideoEditorWindow._color_audio_export_badge_note = _quality_workflow._color_audio_export_badge_note
    VideoEditorWindow._copy_creator_assist_publish_text = _screenstudio_workflow._copy_creator_assist_publish_text
    VideoEditorWindow._create_nested_group_from_selection = _timeline_operations._create_nested_group_from_selection
    VideoEditorWindow._creator_assist_local_media_path = _screenstudio_workflow._creator_assist_local_media_path
    VideoEditorWindow._creator_assist_media_items = _screenstudio_workflow._creator_assist_media_items
    VideoEditorWindow._creator_assist_merge_local_summary = staticmethod(_screenstudio_workflow._creator_assist_merge_local_summary)
    VideoEditorWindow._creator_assist_project_end_ms = _screenstudio_workflow._creator_assist_project_end_ms
    VideoEditorWindow._creator_assist_project_summary = _screenstudio_workflow._creator_assist_project_summary
    VideoEditorWindow._creator_assist_selected_options = _screenstudio_workflow._creator_assist_selected_options
    VideoEditorWindow._creator_deep_merge = staticmethod(_screenstudio_workflow._creator_deep_merge)
    VideoEditorWindow._current_preview_frame_idx = _node_mask_workflow.current_preview_frame_idx
    VideoEditorWindow._current_preview_rgb = _node_mask_workflow.current_preview_rgb
    VideoEditorWindow._current_project_name = _project_workflow._current_project_name
    VideoEditorWindow._default_mmd_motion_for_model = _mmd_workflow._default_mmd_motion_for_model
    VideoEditorWindow._delete_mmd_track = _mmd_workflow._delete_mmd_track
    VideoEditorWindow._do_autosave = _project_workflow._do_autosave
    VideoEditorWindow._do_autosave_legacy = _project_workflow._do_autosave_legacy
    VideoEditorWindow._draw_preview_placeholder = _preview_placeholder._draw_preview_placeholder
    VideoEditorWindow._set_preview_placeholder = _preview_placeholder._set_preview_placeholder
    VideoEditorWindow._clear_preview_placeholder = _preview_placeholder._clear_preview_placeholder
    VideoEditorWindow._preview_has_visual_content = _preview_placeholder._preview_has_visual_content
    VideoEditorWindow._refresh_visual_preview_after_timeline_change = _preview_placeholder._refresh_visual_preview_after_timeline_change
    VideoEditorWindow._update_preview_placeholder = _preview_placeholder._update_preview_placeholder
    VideoEditorWindow._import_media_from_empty_preview = _preview_placeholder._import_media_from_empty_preview
    VideoEditorWindow._active_renderable_clip_at_current_position = _preview_placeholder._active_renderable_clip_at_current_position
    VideoEditorWindow._register_change = _history_workflow._register_change
    VideoEditorWindow._on_undo = _history_workflow._on_undo
    VideoEditorWindow._on_redo = _history_workflow._on_redo
    VideoEditorWindow._show_history_feedback = _history_workflow._show_history_feedback
    VideoEditorWindow._apply_history_snapshot = _history_workflow._apply_history_snapshot
    VideoEditorWindow._preview_cpu_frame_consumers_active = _preview_frame_workflow._preview_cpu_frame_consumers_active
    VideoEditorWindow._refresh_preview_soft = _preview_frame_workflow._refresh_preview_soft
    VideoEditorWindow._preview_qimage_primary_active = _preview_frame_workflow._preview_qimage_primary_active
    VideoEditorWindow._refresh_preview_qimage_mode = _preview_frame_workflow._refresh_preview_qimage_mode
    VideoEditorWindow._latest_preview_qimage = _preview_frame_workflow._latest_preview_qimage
    VideoEditorWindow._qimage_from_preview_rgb = staticmethod(_preview_frame_workflow._qimage_from_preview_rgb)
    VideoEditorWindow._on_frame_ready = _preview_frame_workflow._on_frame_ready
    VideoEditorWindow._ensure_preview_gl = _preview_frame_workflow._ensure_preview_gl
    VideoEditorWindow._on_gpu_frame_ready = _preview_frame_workflow._on_gpu_frame_ready
    VideoEditorWindow._on_spine_gpu_overlay_failed = _preview_frame_workflow._on_spine_gpu_overlay_failed
    VideoEditorWindow._scale_preview_to_fit = _window_geometry_workflow._scale_preview_to_fit
    VideoEditorWindow._preview_frame_rect_in_label = _window_geometry_workflow._preview_frame_rect_in_label
    VideoEditorWindow._sync_overlay_to_video_rect = _window_geometry_workflow._sync_overlay_to_video_rect
    VideoEditorWindow._sync_preview_gl_geometry = _window_geometry_workflow._sync_preview_gl_geometry
    VideoEditorWindow._begin_window_move_guard = _window_geometry_workflow._begin_window_move_guard
    VideoEditorWindow._end_window_move_guard = _window_geometry_workflow._end_window_move_guard
    VideoEditorWindow.resizeEvent = _window_geometry_workflow.resizeEvent
    VideoEditorWindow.moveEvent = _window_geometry_workflow.moveEvent
    VideoEditorWindow._duplicate_mmd_track = _mmd_workflow._duplicate_mmd_track
    VideoEditorWindow._duplicate_selected_timeline_clips = _timeline_operations._duplicate_selected_timeline_clips
    VideoEditorWindow._timeline_edit_points_ms = _timeline_operations._timeline_edit_points_ms
    VideoEditorWindow._jump_to_timeline_edit_point = _timeline_operations._jump_to_timeline_edit_point
    VideoEditorWindow._clear_timeline_clip_selection = _timeline_operations._clear_timeline_clip_selection
    VideoEditorWindow._select_all_timeline_clips = _timeline_operations._select_all_timeline_clips
    VideoEditorWindow._timeline_duplicate_group_start_ms = staticmethod(_timeline_operations._timeline_duplicate_group_start_ms)
    VideoEditorWindow._timeline_paste_group_base_ms = staticmethod(_timeline_operations._timeline_paste_group_base_ms)
    VideoEditorWindow._prepare_pasted_timeline_clip = staticmethod(_timeline_operations._prepare_pasted_timeline_clip)
    VideoEditorWindow._copy_selected_timeline_clips = _timeline_operations._copy_selected_timeline_clips
    VideoEditorWindow._cut_selected_timeline_clips = _timeline_operations._cut_selected_timeline_clips
    VideoEditorWindow._set_selection_end_at_playhead = _timeline_operations._set_selection_end_at_playhead
    VideoEditorWindow._clear_selected_clip_transition = _timeline_operations._clear_selected_clip_transition
    VideoEditorWindow._clear_clip_transition = _timeline_operations._clear_clip_transition
    VideoEditorWindow._toggle_audio_link = _timeline_operations._toggle_audio_link
    VideoEditorWindow._cut_selection_in_track = _timeline_operations._cut_selection_in_track
    VideoEditorWindow._apply_speed_to_selection = _timeline_operations._apply_speed_to_selection
    VideoEditorWindow._track_has_blade_target = staticmethod(_timeline_operations._track_has_blade_target)
    VideoEditorWindow._blade_at_playhead = _timeline_operations._blade_at_playhead
    VideoEditorWindow._blade_track_at_ms = _timeline_operations._blade_track_at_ms
    VideoEditorWindow._selected_locked_video_track_id = _timeline_operations._selected_locked_video_track_id
    VideoEditorWindow._format_nudge_status = staticmethod(_timeline_operations._format_nudge_status)
    VideoEditorWindow._timeline_neighbor_edit_point = staticmethod(_timeline_operations._timeline_neighbor_edit_point)
    VideoEditorWindow._apply_transition_to_selected = _timeline_operations._apply_transition_to_selected
    VideoEditorWindow._ensure_creator_assist_panel = _screenstudio_workflow._ensure_creator_assist_panel
    VideoEditorWindow._capcut_feature_enabled = staticmethod(_screenstudio_workflow._capcut_feature_enabled)
    VideoEditorWindow._capcut_feature_disabled = staticmethod(_screenstudio_workflow._capcut_feature_disabled)
    VideoEditorWindow._capcut_disabled_reason = staticmethod(_screenstudio_workflow._capcut_disabled_reason)
    VideoEditorWindow._screenstudio_simple_mode_enabled = _screenstudio_workflow._screenstudio_simple_mode_enabled
    VideoEditorWindow._apply_screenstudio_simple_mode_ui = _screenstudio_workflow._apply_screenstudio_simple_mode_ui
    VideoEditorWindow._on_workspace_mode_selected = _screenstudio_workflow._on_workspace_mode_selected
    VideoEditorWindow._on_screenstudio_advanced_toggled = _screenstudio_workflow._on_screenstudio_advanced_toggled
    VideoEditorWindow._load_screenstudio_cursor_sidecar_for_clip = staticmethod(_screenstudio_workflow._load_screenstudio_cursor_sidecar_for_clip)
    VideoEditorWindow._screenstudio_default_polish_payload = _screenstudio_workflow._screenstudio_default_polish_payload
    VideoEditorWindow._screenstudio_cursor_for_handle = staticmethod(_screenstudio_workflow._screenstudio_cursor_for_handle)
    VideoEditorWindow._evaluate_node_chain_with_masks = staticmethod(_node_mask_workflow.evaluate_node_chain_with_masks)
    VideoEditorWindow._enter_grabcut_mode = _node_mask_workflow._enter_grabcut_mode
    VideoEditorWindow._enter_sam_mode = _node_mask_workflow._enter_sam_mode
    VideoEditorWindow._on_rotoscope_rect = _node_mask_workflow._on_rotoscope_rect
    VideoEditorWindow._on_sam_click = _node_mask_workflow._on_sam_click
    VideoEditorWindow._open_power_window_editor = _node_mask_workflow._open_power_window_editor
    VideoEditorWindow._on_power_window_click = _node_mask_workflow._on_power_window_click
    VideoEditorWindow._find_claude_cli = _ai_workflow._find_claude_cli
    VideoEditorWindow._find_first_video_clip_by_source_path = _screenstudio_workflow._find_first_video_clip_by_source_path
    VideoEditorWindow._find_mmd_track = _mmd_workflow._find_mmd_track
    VideoEditorWindow._finish_workflow_preset_application = _preset_workflows._finish_workflow_preset_application
    VideoEditorWindow._format_color_slider_label = _color_panels._format_color_slider_label
    VideoEditorWindow._frame_size_for_storyboard_clip = _screenstudio_workflow._frame_size_for_storyboard_clip
    VideoEditorWindow._has_recoverable_project_state = _project_workflow._has_recoverable_project_state
    VideoEditorWindow._import_screenstudio_srt_subtitles = _screenstudio_workflow._import_screenstudio_srt_subtitles
    VideoEditorWindow._insert_live2d_actor_lane = _insert_live2d_actor_lane_ui
    VideoEditorWindow._insert_mmd_actor_lane = _mmd_workflow._insert_mmd_actor_lane
    VideoEditorWindow._insert_spine_actor_lane = _insert_spine_actor_lane_ui
    VideoEditorWindow._open_live2d_viewer = _actor_timeline_workflow._open_live2d_viewer
    VideoEditorWindow._open_spine_editor = _actor_timeline_workflow._open_spine_editor
    VideoEditorWindow._focus_actor_clip_for_edit = _actor_timeline_workflow._focus_actor_clip_for_edit
    VideoEditorWindow._on_spine_clip_dclick = _actor_timeline_workflow._on_spine_clip_dclick
    VideoEditorWindow._on_live2d_clip_dclick = _actor_timeline_workflow._on_live2d_clip_dclick
    VideoEditorWindow._add_live2d_actor_at_playhead = _actor_timeline_workflow._add_live2d_actor_at_playhead
    VideoEditorWindow._add_live2d_actor_track = _actor_timeline_workflow._add_live2d_actor_track
    VideoEditorWindow._timeline_content_margin = _actor_timeline_workflow._timeline_content_margin
    VideoEditorWindow._tracks_host_drop_model = _actor_timeline_workflow._tracks_host_drop_model
    VideoEditorWindow._rebuild_spine_actor_lanes = _actor_timeline_workflow._rebuild_spine_actor_lanes
    VideoEditorWindow._add_spine_actor_track = _actor_timeline_workflow._add_spine_actor_track
    VideoEditorWindow._on_actor_clip_changed = _actor_timeline_workflow._on_actor_clip_changed
    VideoEditorWindow._add_spine_actor_at_playhead = _actor_timeline_workflow._add_spine_actor_at_playhead
    VideoEditorWindow._tracks_host_drop_spine = _actor_timeline_workflow._tracks_host_drop_spine
    VideoEditorWindow._rebuild_live2d_actor_lanes = _actor_timeline_workflow._rebuild_live2d_actor_lanes
    VideoEditorWindow._on_live2d_clip_changed = _actor_timeline_workflow._on_live2d_clip_changed
    VideoEditorWindow._export_track_zoom_actors_only = staticmethod(_actor_timeline_workflow._export_track_zoom_actors_only)
    VideoEditorWindow._has_live2d_actor_clips = _actor_timeline_workflow._has_live2d_actor_clips
    VideoEditorWindow._live2d_actor_extent_ms = _actor_timeline_workflow._live2d_actor_extent_ms
    VideoEditorWindow._apply_performance_source_to_selected_avatar = (
        _actor_timeline_workflow._apply_performance_source_to_selected_avatar
    )
    VideoEditorWindow._language_display_name = _localization_controller._language_display_name
    VideoEditorWindow._launch_claude_code_terminal = _ai_workflow._launch_claude_code_terminal
    VideoEditorWindow._live2d_owner_track_for_clip = _live2d_workflow._live2d_owner_track_for_clip
    VideoEditorWindow._load_lut_from_path = _color_panels._load_lut_from_path
    VideoEditorWindow._manage_preset_packs = _preset_workflows._manage_preset_packs
    VideoEditorWindow._manage_preset_preview_cache = _preset_workflows._manage_preset_preview_cache
    VideoEditorWindow._mask_toolbar_action = _node_mask_workflow.mask_toolbar_action
    VideoEditorWindow._mmd_lane_for_track = _mmd_workflow._mmd_lane_for_track
    VideoEditorWindow._mmd_media_pool_paths = _mmd_workflow._mmd_media_pool_paths
    VideoEditorWindow._mmd_track_for_motion_attach = _mmd_workflow._mmd_track_for_motion_attach
    VideoEditorWindow._normalized_mmd_playback_with = staticmethod(_mmd_workflow._normalized_mmd_playback_with)
    VideoEditorWindow._nudge_selected_clips = _timeline_operations._nudge_selected_clips
    VideoEditorWindow._on_cross_track_group_drag_delta = _timeline_drag_workflow._on_cross_track_group_drag_delta
    VideoEditorWindow._linked_move_block_message = _timeline_drag_workflow._linked_move_block_message
    VideoEditorWindow._validate_clip_drag_delta = _timeline_drag_workflow._validate_clip_drag_delta
    VideoEditorWindow._on_clip_drag_delta = _timeline_drag_workflow._on_clip_drag_delta
    VideoEditorWindow._on_batch_export = _export_workflow._on_batch_export
    VideoEditorWindow._on_export = _export_workflow._on_export
    VideoEditorWindow._on_export_live2d_only = _export_workflow._on_export_live2d_only
    VideoEditorWindow._refresh_export_button_tooltip = _export_workflow._refresh_export_button_tooltip
    VideoEditorWindow._refresh_quality_btn_label = _export_workflow._refresh_quality_btn_label
    VideoEditorWindow._build_quality_menu = _export_workflow._build_quality_menu
    VideoEditorWindow._on_quality_picked = _export_workflow._on_quality_picked
    VideoEditorWindow._refresh_format_btn_label = _export_workflow._refresh_format_btn_label
    VideoEditorWindow._build_format_menu = _export_workflow._build_format_menu
    VideoEditorWindow._on_format_picked = _export_workflow._on_format_picked
    VideoEditorWindow._refresh_resolution_btn_label = _export_workflow._refresh_resolution_btn_label
    VideoEditorWindow._build_resolution_menu = _export_workflow._build_resolution_menu
    VideoEditorWindow._on_resolution_picked = _export_workflow._on_resolution_picked
    VideoEditorWindow._refresh_fps_btn_label = _export_workflow._refresh_fps_btn_label
    VideoEditorWindow._build_fps_menu = _export_workflow._build_fps_menu
    VideoEditorWindow._on_fps_picked = _export_workflow._on_fps_picked
    VideoEditorWindow._on_language_picked = _localization_controller._on_language_picked
    VideoEditorWindow._on_live2d_clip_performance_source_mapping_requested = _live2d_workflow._on_live2d_clip_performance_source_mapping_requested
    VideoEditorWindow._on_live2d_clip_storyboard_requested = _live2d_workflow._on_live2d_clip_storyboard_requested
    VideoEditorWindow._on_live2d_clip_video_mocap_requested = _live2d_workflow._on_live2d_clip_video_mocap_requested
    VideoEditorWindow._on_media_pool_popout_closed = _popout_controller.on_media_pool_popout_closed
    VideoEditorWindow._on_mmd_lane_double_clicked = _mmd_workflow._on_mmd_lane_double_clicked
    VideoEditorWindow._on_mmd_lane_drop = _mmd_workflow._on_mmd_lane_drop
    VideoEditorWindow._on_mmd_lane_track_changed = _mmd_workflow._on_mmd_lane_track_changed
    VideoEditorWindow._on_new_project = _project_workflow._on_new_project
    VideoEditorWindow._on_node_graph_selection = _node_mask_workflow._on_node_graph_selection
    VideoEditorWindow._on_node_mask_request = _node_mask_workflow.on_node_mask_request
    VideoEditorWindow._on_open_project = _project_workflow._on_open_project
    VideoEditorWindow._on_relink_project_media = _project_workflow._on_relink_project_media
    VideoEditorWindow._on_save_project = _project_workflow._on_save_project
    VideoEditorWindow._on_section_popout_closed = _popout_controller.on_section_popout_closed
    VideoEditorWindow._on_subtitle_popout_closed = _popout_controller.on_subtitle_popout_closed
    VideoEditorWindow._on_workbench_popout_closed = _popout_controller.on_workbench_popout_closed
    VideoEditorWindow._on_workflow_preset_dropped = _preset_workflows._on_workflow_preset_dropped
    VideoEditorWindow._open_command_palette = _open_command_palette_controller
    VideoEditorWindow._open_auto_polish_for_media_path = _screenstudio_workflow._open_auto_polish_for_media_path
    VideoEditorWindow._open_actor_loading_manager = _quality_workflow._open_actor_loading_manager
    VideoEditorWindow._open_actor_qa_browser = _quality_workflow._open_actor_qa_browser
    VideoEditorWindow._open_creator_assist_panel = _screenstudio_workflow._open_creator_assist_panel
    VideoEditorWindow._open_crash_report = _quality_workflow._open_crash_report
    VideoEditorWindow._open_health_center = _quality_workflow._open_health_center
    VideoEditorWindow._open_local_llm_provider_setup_dialog = _ai_workflow._open_local_llm_provider_setup_dialog
    VideoEditorWindow._open_mmd_actor_editor = _mmd_workflow._open_mmd_actor_editor
    VideoEditorWindow._open_nested_sequence_for_edit = _timeline_operations._open_nested_sequence_for_edit
    VideoEditorWindow._open_precision_trim_dialog = _timeline_operations._open_precision_trim_dialog
    VideoEditorWindow._open_preset_application_preview = _preset_workflows._open_preset_application_preview
    VideoEditorWindow._open_screenstudio_polish_panel = _screenstudio_workflow._open_screenstudio_polish_panel
    VideoEditorWindow._open_selected_live2d_editor = _live2d_workflow._open_selected_live2d_editor
    VideoEditorWindow._open_selected_mmd_actor_editor = _mmd_workflow._open_selected_mmd_actor_editor
    VideoEditorWindow._open_template_composer = _preset_workflows._open_template_composer
    VideoEditorWindow._open_visual_qa_viewer = _visual_qa_workflow._open_visual_qa_viewer
    VideoEditorWindow._paste_timeline_clipboard = _timeline_operations._paste_timeline_clipboard
    VideoEditorWindow._preset_preview_frame = _preset_workflows._preset_preview_frame
    VideoEditorWindow._refresh_user_preset_panels = _preset_workflows._refresh_user_preset_panels
    VideoEditorWindow._clear_preset_overlay_preview = _preset_workflows._clear_preset_overlay_preview
    VideoEditorWindow._clear_preset_live_preview = _preset_workflows._clear_preset_live_preview
    VideoEditorWindow._save_selected_effect_preset = _preset_workflows._save_selected_effect_preset
    VideoEditorWindow._import_preset_pack = _preset_workflows._import_preset_pack
    VideoEditorWindow._export_user_preset_pack = _preset_workflows._export_user_preset_pack
    VideoEditorWindow._preset_undo_label = _preset_workflows._preset_undo_label
    VideoEditorWindow._workflow_apply_summary_rows = _preset_workflows._workflow_apply_summary_rows
    VideoEditorWindow._apply_workflow_preset = _preset_workflows._apply_workflow_preset
    VideoEditorWindow._apply_audio_workflow_preset = _preset_workflows._apply_audio_workflow_preset
    VideoEditorWindow._apply_color_workflow_preset = _preset_workflows._apply_color_workflow_preset
    VideoEditorWindow._preset_application_plan_rows = _preset_workflows._preset_application_plan_rows
    VideoEditorWindow._preset_apply_failure_message = _preset_context._preset_apply_failure_message
    VideoEditorWindow._preset_apply_failure_reason = _preset_context._preset_apply_failure_reason
    VideoEditorWindow._open_qa_dashboard = _quality_workflow._open_qa_dashboard
    VideoEditorWindow._preview_drop_frame_point = _ar_pbr_editor_gizmo_bridge.preview_drop_frame_point
    VideoEditorWindow._preview_creator_assist_short = _screenstudio_workflow._preview_creator_assist_short
    VideoEditorWindow._project_summary_for_presets = _preset_context._project_summary_for_presets
    VideoEditorWindow._promote_ar_pbr_track_to_scene_anchor = _ar_pbr_editor_gizmo_bridge.promote_track_to_scene_anchor
    VideoEditorWindow._proxy_thread_key = staticmethod(_proxy_controller._proxy_thread_key)
    VideoEditorWindow._pulse_compact_color_card = _color_panels._pulse_compact_color_card
    VideoEditorWindow._pulse_compact_color_cards = _color_panels._pulse_compact_color_cards
    VideoEditorWindow._quote_powershell_literal = _ai_workflow._quote_powershell_literal
    VideoEditorWindow._rebuild_mmd_actor_lanes = _mmd_workflow._rebuild_mmd_actor_lanes
    VideoEditorWindow._on_blur_params_changed = _render_chain_workflow._on_blur_params_changed
    VideoEditorWindow._on_effect_params_changed = _render_chain_workflow._on_effect_params_changed
    VideoEditorWindow._rebuild_active_chain = _render_chain_workflow._rebuild_active_chain
    VideoEditorWindow._tracking_cache_source_for_track = _render_chain_workflow._tracking_cache_source_for_track
    VideoEditorWindow._prewarm_tracking_caches_for_track = _render_chain_workflow._prewarm_tracking_caches_for_track
    VideoEditorWindow._on_tracking_cache_ready = _render_chain_workflow._on_tracking_cache_ready
    VideoEditorWindow._on_tracking_cache_failed = _render_chain_workflow._on_tracking_cache_failed
    VideoEditorWindow._retire_tracking_cache_worker = _render_chain_workflow._retire_tracking_cache_worker
    VideoEditorWindow._start_preview_prerender_for_track = _render_chain_workflow._start_preview_prerender_for_track
    VideoEditorWindow._cancel_preview_prerender_jobs = _render_chain_workflow._cancel_preview_prerender_jobs
    VideoEditorWindow._retire_preview_prerender_worker = _render_chain_workflow._retire_preview_prerender_worker
    VideoEditorWindow._recovery_dir = _project_workflow._recovery_dir
    VideoEditorWindow._refresh_ai_command_provider_status = _ai_workflow._refresh_ai_command_provider_status
    VideoEditorWindow._refresh_actor_qa_badges = _quality_workflow._refresh_actor_qa_badges
    VideoEditorWindow._refresh_collapsible_header_title = _localization_controller._refresh_collapsible_header_title
    VideoEditorWindow._refresh_color_target_badge = _color_panels._refresh_color_target_badge
    VideoEditorWindow._refresh_language_button = _localization_controller._refresh_language_button
    VideoEditorWindow._refresh_live2d_workbench_selection = _live2d_workflow._refresh_live2d_workbench_selection
    VideoEditorWindow._refresh_localized_ui = _localization_controller._refresh_localized_ui
    VideoEditorWindow._refresh_main_dock_splitter_roles = _popout_controller.refresh_main_dock_splitter_roles
    VideoEditorWindow._refresh_mmd_track_after_editor_change = _mmd_workflow._refresh_mmd_track_after_editor_change
    VideoEditorWindow._refresh_preview_for_mask_edit = _node_mask_workflow.refresh_preview_for_mask_edit
    VideoEditorWindow._refresh_top_project_breadcrumb = _localization_controller._refresh_top_project_breadcrumb
    VideoEditorWindow._refresh_window_title = _project_workflow._refresh_window_title
    VideoEditorWindow._refresh_workbench = _workbench_controller.refresh_workbench
    VideoEditorWindow._on_workbench_node_focused = _workbench_controller._on_workbench_node_focused
    VideoEditorWindow._remove_ai_script_preview_markers = _ai_workflow._remove_ai_script_preview_markers
    VideoEditorWindow._remove_mmd_actor_lane = _mmd_workflow._remove_mmd_actor_lane
    VideoEditorWindow._reuse_ar_pbr_preview_window = _ar_pbr_editor_bridge.reuse_preview_window
    VideoEditorWindow._ripple_delete_selected = _timeline_operations._ripple_delete_selected
    VideoEditorWindow._run_preset_fix_action = _preset_workflows._run_preset_fix_action
    VideoEditorWindow._same_media_path = staticmethod(_screenstudio_workflow._same_media_path)
    VideoEditorWindow._screenstudio_auto_polish_report = _screenstudio_workflow._screenstudio_auto_polish_report
    VideoEditorWindow._maybe_apply_default_screenstudio_polish_to_clip = _screenstudio_workflow._maybe_apply_default_screenstudio_polish_to_clip
    VideoEditorWindow._register_screenstudio_real_recording_candidate = _screenstudio_workflow._register_screenstudio_real_recording_candidate
    VideoEditorWindow._screenstudio_preview_candidate_rows = _screenstudio_workflow._screenstudio_preview_candidate_rows
    VideoEditorWindow._screenstudio_candidate_canvas_rects = _screenstudio_workflow._screenstudio_candidate_canvas_rects
    VideoEditorWindow._screenstudio_candidate_handle = staticmethod(_screenstudio_workflow._screenstudio_candidate_handle)
    VideoEditorWindow._screenstudio_candidate_hit_test = _screenstudio_workflow._screenstudio_candidate_hit_test
    VideoEditorWindow._screenstudio_candidate_drag_values = _screenstudio_workflow._screenstudio_candidate_drag_values
    VideoEditorWindow._paint_screenstudio_candidate_canvas_overlay = _screenstudio_workflow._paint_screenstudio_candidate_canvas_overlay
    VideoEditorWindow._paint_screenstudio_candidate_overlay = _screenstudio_workflow._paint_screenstudio_candidate_overlay
    VideoEditorWindow._screenstudio_candidate_interaction = _screenstudio_workflow._screenstudio_candidate_interaction
    VideoEditorWindow._screenstudio_export_badge_note = _screenstudio_workflow._screenstudio_export_badge_note
    VideoEditorWindow._screenstudio_export_defaults_for_current_project = _export_workflow._screenstudio_export_defaults_for_current_project
    VideoEditorWindow._screenstudio_local_zoom_overrides = staticmethod(_screenstudio_workflow._screenstudio_local_zoom_overrides)
    VideoEditorWindow._screenstudio_polish_targets = _screenstudio_workflow._screenstudio_polish_targets
    VideoEditorWindow._set_collapsible_host_open = _set_collapsible_host_open_chrome
    VideoEditorWindow._show_preset_application_corpus_report = _quality_workflow._show_preset_application_corpus_report
    VideoEditorWindow._show_preset_qa_report = _quality_workflow._show_preset_qa_report
    VideoEditorWindow._show_productization_loop_report = _quality_workflow._show_productization_loop_report
    VideoEditorWindow._show_upsell = _quality_workflow._show_upsell
    VideoEditorWindow._screenstudio_post_export_handoff_note = _export_workflow._screenstudio_post_export_handoff_note
    VideoEditorWindow._screenstudio_project_polish_payload = _screenstudio_workflow._screenstudio_project_polish_payload
    VideoEditorWindow._screenstudio_write_local_share_package = _export_workflow._screenstudio_write_local_share_package
    VideoEditorWindow._select_live2d_clip_in_lane = _live2d_workflow._select_live2d_clip_in_lane
    VideoEditorWindow._select_mmd_track = _mmd_workflow._select_mmd_track
    VideoEditorWindow._select_view_target_node = _node_mask_workflow.select_view_target_node
    VideoEditorWindow._selected_live2d_clip_for_mapping = _live2d_workflow._selected_live2d_clip_for_mapping
    VideoEditorWindow._set_color_reference_workspace_ratio = _color_panels._set_color_reference_workspace_ratio
    VideoEditorWindow._set_mmd_row_selection = _mmd_workflow._set_mmd_row_selection
    VideoEditorWindow._on_workbench_mmd_rotation_hint_changed = _mmd_workflow._on_workbench_mmd_rotation_hint_changed
    VideoEditorWindow._on_workbench_mmd_spring_response_changed = _mmd_workflow._on_workbench_mmd_spring_response_changed
    VideoEditorWindow._set_mmd_track_motion = _mmd_workflow._set_mmd_track_motion
    VideoEditorWindow._set_mmd_track_physics_enabled = _mmd_workflow._set_mmd_track_physics_enabled
    VideoEditorWindow._set_mmd_track_playback_value = _mmd_workflow._set_mmd_track_playback_value
    VideoEditorWindow._set_screenstudio_advanced_visible = _screenstudio_workflow._set_screenstudio_advanced_visible
    VideoEditorWindow._set_screenstudio_polish_payload = _screenstudio_workflow._set_screenstudio_polish_payload
    VideoEditorWindow._show_export_final_checklist = _export_workflow._show_export_final_checklist
    VideoEditorWindow._show_media_health = _project_workflow._show_media_health
    VideoEditorWindow._show_mmd_track_in_workbench = _mmd_workflow._show_mmd_track_in_workbench
    VideoEditorWindow._show_preset_overlay_preview = _preset_workflows._show_preset_overlay_preview
    VideoEditorWindow._show_recovery_candidates = _project_workflow._show_recovery_candidates
    VideoEditorWindow._show_screenstudio_export_complete_dialog = _screenstudio_workflow._show_screenstudio_export_complete_dialog
    VideoEditorWindow._snapshot_clip_effects_for_export = staticmethod(_snapshot_clip_effects_for_export_helper)
    VideoEditorWindow._snapshot_node_item_chain_for_export = staticmethod(_snapshot_node_item_chain_for_export_helper)
    VideoEditorWindow._export_zoom_actors_for_track = staticmethod(_render_chain_workflow._export_zoom_actors_for_track)
    VideoEditorWindow._split_audio_clip = _timeline_operations._split_audio_clip
    VideoEditorWindow._stage_creator_assist_storyboard_effects = _screenstudio_workflow._stage_creator_assist_storyboard_effects
    VideoEditorWindow._stage_creator_assist_storyboard_templates = _screenstudio_workflow._stage_creator_assist_storyboard_templates
    VideoEditorWindow._stage_storyboard_callout_actors = _screenstudio_workflow._stage_storyboard_callout_actors
    VideoEditorWindow._storyboard_callout_actor = staticmethod(_screenstudio_workflow._storyboard_callout_actor)
    VideoEditorWindow._storyboard_callout_position = staticmethod(_screenstudio_workflow._storyboard_callout_position)
    VideoEditorWindow._storyboard_project_window_for_track_actor = staticmethod(_screenstudio_workflow._storyboard_project_window_for_track_actor)
    VideoEditorWindow._storyboard_source_window_for_clip = staticmethod(_screenstudio_workflow._storyboard_source_window_for_clip)
    VideoEditorWindow._storyboard_template_aliases = staticmethod(_screenstudio_workflow._storyboard_template_aliases)
    VideoEditorWindow._storyboard_template_links_from_bundle = staticmethod(_screenstudio_workflow._storyboard_template_links_from_bundle)
    VideoEditorWindow._storyboard_template_target_for_ms = staticmethod(_screenstudio_workflow._storyboard_template_target_for_ms)
    VideoEditorWindow._storyboard_zoom_actor_for_clip = staticmethod(_screenstudio_workflow._storyboard_zoom_actor_for_clip)
    VideoEditorWindow._sync_ai_script_preview_markers = _ai_workflow._sync_ai_script_preview_markers
    VideoEditorWindow._sync_color_compare_buttons = _color_panels._sync_color_compare_buttons
    VideoEditorWindow._sync_color_inline_panel = _color_panels._sync_color_inline_panel
    VideoEditorWindow._sync_color_panel = _color_panels._sync_color_panel
    VideoEditorWindow._sync_storyboard_zoom_visual_actors = _screenstudio_workflow._sync_storyboard_zoom_visual_actors
    VideoEditorWindow._target_live2d_clip_for_mocap = _live2d_workflow._target_live2d_clip_for_mocap
    VideoEditorWindow._template_entry_condition_ok = _preset_context._template_entry_condition_ok
    VideoEditorWindow._toggle_media_pool_popout = _popout_controller.toggle_media_pool_popout
    VideoEditorWindow._make_side_dock_placeholder = _popout_controller.make_side_dock_placeholder_for_owner
    VideoEditorWindow._toggle_actor_library_popout = _popout_controller.toggle_actor_library_popout
    VideoEditorWindow._toggle_effects_library_popout = _popout_controller.toggle_effects_library_popout
    VideoEditorWindow._toggle_title_presets_popout = _popout_controller.toggle_title_presets_popout
    VideoEditorWindow._toggle_transitions_popout = _popout_controller.toggle_transitions_popout
    VideoEditorWindow._toggle_workflow_presets_popout = _popout_controller.toggle_workflow_presets_popout
    VideoEditorWindow._toggle_creator_assist_popout = _popout_controller.toggle_creator_assist_popout
    VideoEditorWindow._toggle_script_edit_popout = _popout_controller.toggle_script_edit_popout
    VideoEditorWindow._toggle_audio_workspace_popout = _popout_controller.toggle_audio_workspace_popout
    VideoEditorWindow._toggle_pip_popout = _popout_controller.toggle_pip_popout
    VideoEditorWindow._toggle_section_popout = _popout_controller.toggle_section_popout
    VideoEditorWindow._toggle_subtitle_popout = _popout_controller.toggle_subtitle_popout
    VideoEditorWindow._toggle_workbench_popout = _popout_controller.toggle_workbench_popout
    VideoEditorWindow._update_color_dock_visibility = _color_panels._update_color_dock_visibility
    VideoEditorWindow._write_claude_code_terminal_files = _ai_workflow._write_claude_code_terminal_files
    VideoEditorWindow._write_recovery_snapshot = _project_workflow._write_recovery_snapshot

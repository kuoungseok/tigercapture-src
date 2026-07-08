"""Ar Pbr VideoEditorWindow delegate bindings."""
from __future__ import annotations

from app.video_editor_delegate_binding import bind_imported_delegate_methods

from app.ar_pbr import editor_window_workflow as _ar_pbr_window_workflow


def _window_toggle_ar_pbr_depth_view(self, checked: bool = False) -> None:
    player = getattr(self, "_player", None)
    mode = "grayscale" if bool(checked) else "off"
    setter = getattr(player, "set_ar_pbr_depth_view_mode", None)
    if callable(setter):
        mode = setter(mode)
    elif player is not None:
        setattr(player, "_ar_pbr_depth_view_mode_value", mode)
        try:
            setattr(player, "_last_preview_frame_cache", None)
        except Exception:
            pass
    button = getattr(self, "viewer_depth_btn", None)
    if button is not None:
        try:
            button.blockSignals(True)
            button.setChecked(str(mode) != "off")
        finally:
            button.blockSignals(False)
    refresh = getattr(self, "_refresh_preview_qimage_mode", None)
    if callable(refresh):
        refresh()


_BINDINGS = (
    ('_sync_ar_pbr_tracks_to_player', 'app.ar_pbr.editor_bridge', 'sync_tracks_to_player', False),
    ('_set_ar_pbr_track_center_norm', 'app.ar_pbr.editor_bridge', 'set_track_center_norm', True),
    ('_set_ar_pbr_track_uniform_scale', 'app.ar_pbr.editor_bridge', 'set_track_uniform_scale', True),
    ('_set_ar_pbr_track_axis_scale', 'app.ar_pbr.editor_bridge', 'set_track_axis_scale', True),
    ('_set_ar_pbr_track_position_z', 'app.ar_pbr.editor_bridge', 'set_track_position_z', True),
    ('_set_ar_pbr_track_rotation_value', 'app.ar_pbr.editor_bridge', 'set_track_rotation_value', True),
    ('_set_ar_pbr_track_yaw', 'app.ar_pbr.editor_bridge', 'set_track_yaw', True),
    ('_ar_pbr_project_gizmo_vec3', 'app.ar_pbr.editor_bridge', 'project_gizmo_vec3', True),
    ('_ar_pbr_project_gizmo_axis', 'app.ar_pbr.editor_bridge', 'project_gizmo_axis', True),
    ('_ar_pbr_gizmo_ring_points', 'app.ar_pbr.editor_bridge', 'gizmo_ring_points', True),
    ('_ar_pbr_distance_to_polyline', 'app.ar_pbr.editor_bridge', 'distance_to_polyline', True),
    ('_ar_pbr_active_tracks_at_playhead', 'app.ar_pbr.editor_bridge', 'active_tracks_at_playhead', False),
    ('_ar_pbr_clamp01', 'app.ar_pbr.editor_bridge', 'clamp01', True),
    ('_ar_pbr_cursor_for_gizmo_mode', 'app.ar_pbr.editor_gizmo_bridge', 'cursor_for_gizmo_mode', True),
    ('_ar_pbr_distance_to_segment', 'app.ar_pbr.editor_bridge', 'distance_to_segment', True),
    ('_ar_pbr_ellipse_ring_hit', 'app.ar_pbr.editor_bridge', 'ellipse_ring_hit', True),
    ('_ar_pbr_gizmo_axis_index', 'app.ar_pbr.editor_bridge', 'axis_index', True),
    ('_ar_pbr_gizmo_geometry', 'app.ar_pbr.editor_bridge', 'gizmo_geometry', False),
    ('_ar_pbr_gizmo_hit_test', 'app.ar_pbr.editor_gizmo_bridge', 'gizmo_hit_test', False),
    ('_ar_pbr_gizmo_interaction_for_canvas', 'app.ar_pbr.editor_gizmo_bridge', 'gizmo_interaction_for_canvas', False),
    ('_ar_pbr_gizmo_visible_track', 'app.ar_pbr.editor_gizmo_bridge', 'gizmo_visible_track', False),
    ('_ar_pbr_preview_registry', 'app.ar_pbr.editor_bridge', 'preview_registry', False),
    ('_ar_pbr_project_gizmo_point3', 'app.ar_pbr.editor_bridge', 'project_gizmo_point3', True),
    ('_ar_pbr_rotate_vec3', 'app.ar_pbr.editor_bridge', 'rotate_vec3', True),
    ('_ar_pbr_runtime_image_point_for_track', 'app.ar_pbr.editor_gizmo_bridge', 'runtime_image_point_for_track', False),
    ('_ar_pbr_selected_track', 'app.ar_pbr.editor_gizmo_bridge', 'selected_track', False),
    ('_ar_pbr_track_by_id', 'app.ar_pbr.editor_gizmo_bridge', 'track_by_id', False),
    ('_ar_pbr_track_center_norm', 'app.ar_pbr.editor_bridge', 'track_center_norm', False),
    ('_ar_pbr_track_lighting_dict', 'app.ar_pbr.editor_bridge', 'track_lighting_dict', True),
    ('_ar_pbr_track_position_z', 'app.ar_pbr.editor_bridge', 'track_position_z', True),
    ('_ar_pbr_track_rotation_value', 'app.ar_pbr.editor_bridge', 'track_rotation_value', True),
    ('_ar_pbr_track_rotation_values', 'app.ar_pbr.editor_bridge', 'track_rotation_values', True),
    ('_ar_pbr_track_scale_values', 'app.ar_pbr.editor_bridge', 'track_scale_values', True),
    ('_ar_pbr_track_uniform_scale', 'app.ar_pbr.editor_bridge', 'track_uniform_scale', True),
    ('_ar_pbr_track_yaw', 'app.ar_pbr.editor_bridge', 'track_yaw', True),
    ('_preview_drop_frame_point', 'app.ar_pbr.editor_gizmo_bridge', 'preview_drop_frame_point', False),
    ('_promote_ar_pbr_track_to_scene_anchor', 'app.ar_pbr.editor_gizmo_bridge', 'promote_track_to_scene_anchor', False),
    ('_reuse_ar_pbr_preview_window', 'app.ar_pbr.editor_bridge', 'reuse_preview_window', False),
)

_WINDOW_WORKFLOW_NAMES = (
    '_open_vrm_media_in_vtuber_studio',
    '_qt_object_valid',
    '_remember_ar_pbr_preview_window',
    '_schedule_ar_pbr_descriptor_prewarm',
    '_open_ar_pbr_asset_preview',
    '_ar_pbr_track_lighting_settings',
    '_apply_ar_pbr_lighting_settings_to_track',
    '_open_ar_pbr_track_model_view',
    '_ar_pbr_paths_from_mime',
    '_vrm_avatar_paths_from_mime',
    '_mmd_paths_from_mime',
    '_ar_pbr_lane_for_track',
    '_insert_ar_pbr_actor_lane',
    '_remove_ar_pbr_actor_lane',
    '_set_ar_pbr_row_selection',
    '_select_ar_pbr_track',
    '_rebuild_ar_pbr_actor_lanes',
    '_on_ar_pbr_lane_track_changed',
    '_refresh_ar_pbr_track_after_lane_change',
    '_delete_ar_pbr_track',
    '_refresh_preview_canvas_interaction_hook',
    '_refresh_preview_popout_overlay_hooks',
    '_preview_canvas_interaction',
    '_preview_popout_canvas_interaction',
    '_paint_preview_canvas_overlay',
    '_paint_comparison_canvas_overlay',
    '_refresh_ar_pbr_preview_after_gizmo_change',
    '_begin_ar_pbr_depth_interaction_cue',
    '_end_ar_pbr_depth_interaction_cue',
    '_ar_pbr_gizmo_interaction',
    '_paint_ar_pbr_gizmo_overlay',
    '_add_ar_pbr_asset_to_preview',
)


def install_ar_pbr_delegates(VideoEditorWindow) -> None:
    bind_imported_delegate_methods(VideoEditorWindow, _BINDINGS)
    for name in _WINDOW_WORKFLOW_NAMES:
        setattr(VideoEditorWindow, name, getattr(_ar_pbr_window_workflow, name))
    VideoEditorWindow._toggle_ar_pbr_depth_view = _window_toggle_ar_pbr_depth_view

from __future__ import annotations

from app.video_editor_delegate_binding import bind_imported_delegate_methods

_BINDINGS = tuple((name, "app.video_editor_motion_workflow", name, False) for name in (
    "_sync_motion_state_to_player", "_motion_lane_for_clip", "_insert_motion_lane", "_rebuild_motion_lanes",
    "_on_motion_lane_changed", "_open_motion_designer", "_open_motion_designer_entry", "_on_motion_composition_changed",
    "_on_motion_lane_double_clicked", "_place_motion_clip", "_duplicate_motion_clip", "_delete_motion_clip",
))


def install_motion_delegates(VideoEditorWindow) -> None:
    bind_imported_delegate_methods(VideoEditorWindow, _BINDINGS)

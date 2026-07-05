from __future__ import annotations


def _on_workbench_node_focused(self, kind: str) -> None:
    if kind == "color":
        if self._color_popout is not None and self._color_popout.isVisible():
            self._color_popout.raise_()
            self._color_popout.activateWindow()
        else:
            self._show_color_dock_page()


def refresh_workbench(self) -> None:
    """Push the current editor selection into the Workbench inspector."""
    if not hasattr(self, "_workbench_panel"):
        return
    live2d_clip = self._selected_live2d_clip_for_mapping()
    live2d_track = self._live2d_owner_track_for_clip(live2d_clip) if live2d_clip is not None else None
    if live2d_clip is not None and live2d_track is not None and not getattr(self, "_selected_clips", None):
        self._workbench_panel.set_live2d_clip(live2d_track, live2d_clip)
        self._node_grade_target = None
        if hasattr(self, "_sync_color_panel"):
            self._sync_color_panel()
        return

    audio_clip_id = getattr(self, "_selected_audio_clip_id", None)
    if audio_clip_id is not None and not getattr(self, "_selected_clips", None):
        audio_track = self._find_audio_track(getattr(self, "_active_audio_track_id", None))
        if audio_track is not None:
            audio_clip = next(
                (
                    clip for clip in getattr(audio_track, "clips", []) or []
                    if getattr(clip, "id", None) == audio_clip_id
                ),
                None,
            )
            if audio_clip is not None:
                self._workbench_panel.set_audio_clip(audio_track, audio_clip)
                self._node_grade_target = None
                if hasattr(self, "_sync_color_panel"):
                    self._sync_color_panel()
                self._refresh_audio_workspace_panel()
                return

    if self._active_track_id is None:
        self._workbench_panel.clear()
        self._node_grade_target = None
        return

    track = self._find_track(self._active_track_id)
    selected_track, selected_clip = self._selected_video_clip()
    if selected_track is not track:
        selected_clip = None
    self._workbench_panel.set_video_track(track, selected_clip=selected_clip)

    primary = self._workbench_panel.primary_node()
    if primary is not None:
        self._node_grade_target = primary
    else:
        self._node_grade_target = None

    if hasattr(self, "_sync_color_panel"):
        self._sync_color_panel()
    self._rebuild_active_chain()

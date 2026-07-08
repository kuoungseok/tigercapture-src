from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import QMenu

from app.audio_tracks import is_audio_path, is_video_path
from app.effect_cards import SPINE_MIME_TYPE
from app.i18n import tr
from app import video_editor_timeline_operations as _timeline_operations
from app.video_editor_transport_workflow import _bounded_seek_position
from app.live2d.actor_lane_row import Live2DActorLaneRow
from app.spine_editor.actor_lane_row import SpineActorLaneRow


def _is_tracks_drop_surface(self, obj) -> bool:
    if obj is getattr(self, "_tracks_host", None):
        return True
    scroll = getattr(self, "_tracks_scroll", None)
    if scroll is None:
        return False
    try:
        return obj is scroll.viewport()
    except Exception:
        return False


def _tracks_drop_accepts_mime(self, mime) -> bool:
    return bool(
        Live2DActorLaneRow._accepts(mime)
        or SpineActorLaneRow._accepts(mime)
        or self._performance_source_paths_from_mime(mime)
        or self._mmd_paths_from_mime(mime)
        or self._ar_pbr_paths_from_mime(mime)
        or self._timeline_media_paths_from_mime(mime)
    )


def dragEnterEvent(self, event) -> None:
    md = event.mimeData()
    if self._vrm_avatar_paths_from_mime(md):
        event.acceptProposedAction()
        return
    if self._mmd_paths_from_mime(md):
        event.acceptProposedAction()
        return
    if md.hasUrls():
        for url in md.urls():
            path = Path(url.toLocalFile())
            if is_video_path(path) or is_audio_path(path):
                event.acceptProposedAction()
                return
    event.ignore()


def dragMoveEvent(self, event) -> None:
    self.dragEnterEvent(event)


def eventFilter(self, obj, event):
    # Live2D / Spine actor drag-and-drop onto the tracks host
    if _is_tracks_drop_surface(self, obj):
        if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if _tracks_drop_accepts_mime(self, event.mimeData()):
                event.acceptProposedAction()
                return True
        elif event.type() == QEvent.Type.Drop:
            mime = event.mimeData()
            drop_x = event.position().x()
            mmd_paths = self._mmd_paths_from_mime(mime)
            if mmd_paths:
                margin = self._timeline_content_margin()
                start_ms = max(0, int(
                    (drop_x - margin) / max(1.0, self._px_per_sec) * 1000
                ))
                self._add_mmd_asset_to_timeline(mmd_paths, start_ms=start_ms)
                event.acceptProposedAction()
                return True
            perf_paths = self._performance_source_paths_from_mime(mime)
            if perf_paths:
                margin = self._timeline_content_margin()
                start_ms = max(0, int(
                    (drop_x - margin) / max(1.0, self._px_per_sec) * 1000
                ))
                self._add_performance_source_clip(perf_paths[0], start_ms)
                event.acceptProposedAction()
                return True
            ar_paths = self._ar_pbr_paths_from_mime(mime)
            if ar_paths:
                margin = self._timeline_content_margin()
                start_ms = max(0, int(
                    (drop_x - margin) / max(1.0, self._px_per_sec) * 1000
                ))
                self._add_ar_pbr_asset_to_preview(
                    ar_paths[0],
                    image_point=(0.5, 0.62),
                    start_ms=start_ms,
                )
                event.acceptProposedAction()
                return True
            if self._add_timeline_media_from_mime(mime):
                event.acceptProposedAction()
                return True
            if mime.hasFormat(SPINE_MIME_TYPE):
                self._tracks_host_drop_spine("", drop_x)
                event.acceptProposedAction()
                return True
            if mime.hasFormat("application/x-live2d-actor-new"):
                self._tracks_host_drop_model("", drop_x)
                event.acceptProposedAction()
                return True
            path = SpineActorLaneRow._model_path_from_mime(mime)
            if path:
                self._tracks_host_drop_spine(path, drop_x)
                event.acceptProposedAction()
                return True
            path = Live2DActorLaneRow._model_path_from_mime(mime)
            if path:
                self._tracks_host_drop_model(path, drop_x)
                event.acceptProposedAction()
                return True

    if obj in (
        getattr(self, "_preview_host", None),
        getattr(self, "_preview_label", None),
        getattr(self, "_preview_gl", None),
    ):
        if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if self._vrm_avatar_paths_from_mime(event.mimeData()):
                event.acceptProposedAction()
                return True
            if self._mmd_paths_from_mime(event.mimeData()):
                event.acceptProposedAction()
                return True
            if self._ar_pbr_paths_from_mime(event.mimeData()):
                event.acceptProposedAction()
                return True
        elif event.type() == QEvent.Type.Drop:
            vrm_paths = self._vrm_avatar_paths_from_mime(event.mimeData())
            if vrm_paths:
                avatar = vrm_paths[0]
                if hasattr(self, "_media_pool"):
                    try:
                        self._media_pool.add_path(avatar)
                    except Exception:
                        pass
                self._open_vrm_media_in_vtuber_studio(str(avatar))
                event.acceptProposedAction()
                return True
            mmd_paths = self._mmd_paths_from_mime(event.mimeData())
            if mmd_paths:
                self._add_mmd_asset_to_timeline(mmd_paths)
                event.acceptProposedAction()
                return True
            paths = self._ar_pbr_paths_from_mime(event.mimeData())
            if paths:
                point = self._preview_drop_frame_point(obj, event)
                self._add_ar_pbr_asset_to_preview(paths[0], image_point=point)
                event.acceptProposedAction()
                return True

    if obj is getattr(self, "_preview_label", None) or \
            obj is getattr(self, "_preview_gl", None):
        if event.type() == event.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                if not self._ensure_preview_pixmap_for_paint():
                    if self._preview_has_renderable_content():
                        try:
                            if self._preview_has_visual_content():
                                self._clear_preview_placeholder()
                        except Exception:
                            pass
                        try:
                            self._player.refresh_current_frame()
                        except Exception:
                            pass
                        return True
                    self._import_media_from_empty_preview()
                    return True
                self._open_paint_dialog()
                return True
            if event.button() == Qt.MouseButton.RightButton:
                self._show_preview_context_menu(event.globalPosition().toPoint())
                return True
    # Wheel over the tracks area zooms the timeline (clip length).
    # Guard: eventFilter may fire during UI build before the scroll area
    # has been constructed.
    scroll = getattr(self, "_tracks_scroll", None)
    if (
        scroll is not None
        and obj is scroll.viewport()
        and event.type() == event.Type.Wheel
    ):
        delta = event.angleDelta().y()
        if delta > 0:
            self._change_zoom(1.2)
        elif delta < 0:
            self._change_zoom(1 / 1.2)
        return True
    return super(type(self), self).eventFilter(obj, event)


def _show_preview_context_menu(self, global_pos) -> None:
    menu = QMenu(self)
    clear_action = menu.addAction(tr("paint.btn.clear_all"))
    clear_action.setEnabled(bool(self._strokes))
    chosen = menu.exec(global_pos)
    if chosen is clear_action:
        self._strokes.clear()
        self._drawing_canvas.update()


def _preview_has_renderable_content(self) -> bool:
    visual_check = getattr(self, "_preview_has_visual_content", None)
    if callable(visual_check):
        has_visual = bool(visual_check())
    else:
        try:
            from app.video_editor_window import VideoEditorWindow

            has_visual = bool(VideoEditorWindow._active_renderable_clip_at_current_position(self))
        except Exception:
            has_visual = False
    return has_visual or any(
        bool(getattr(t, "is_loaded", False))
        for t in getattr(self, "_audio_tracks", []) or []
    )


def _ensure_preview_pixmap_for_paint(self) -> bool:
    """Ensure PaintDialog has a real frame even when GL preview is active."""
    pix = getattr(self, "_preview_pixmap", None)
    if pix is not None and not pix.isNull():
        return True
    qimg = self._latest_preview_qimage()
    if qimg is not None and not qimg.isNull():
        self._preview_pixmap = QPixmap.fromImage(qimg)
        self._remember_good_preview_pixmap()
        return self._preview_pixmap is not None and not self._preview_pixmap.isNull()
    if self._preview_has_renderable_content() and hasattr(self, "_player"):
        try:
            self._player.refresh_current_frame()
            qimg = self._latest_preview_qimage()
            if qimg is not None and not qimg.isNull():
                self._preview_pixmap = QPixmap.fromImage(qimg)
                self._remember_good_preview_pixmap()
                return True
        except Exception:
            pass
    return False


def _escape_timeline_context(self) -> bool:
    is_text_focus = getattr(self, "_is_text_focus", None)
    if callable(is_text_focus) and is_text_focus():
        return False

    mode = str(getattr(self, "_timeline_tool_mode", "select") or "select")
    if mode != "select":
        set_mode = getattr(self, "_set_timeline_tool_mode", None)
        if callable(set_mode):
            set_mode("select")
        else:
            self._timeline_tool_mode = "select"
        return True

    if _timeline_operations._clear_timeline_clip_selection(self):
        flash = getattr(self, "_flash_status", None)
        if callable(flash):
            flash("Selection cleared")
        return True
    return False


def keyPressEvent(self, event: QKeyEvent) -> None:
    key = event.key()
    mods = event.modifiers()
    if key == Qt.Key.Key_Escape and not mods:
        if self._escape_timeline_context():
            return
    if key in (Qt.Key.Key_J, Qt.Key.Key_K, Qt.Key.Key_L) and not mods:
        key_map = {
            Qt.Key.Key_J: "j",
            Qt.Key.Key_K: "k",
            Qt.Key.Key_L: "l",
        }
        if self._apply_jkl_transport(key_map[key]):
            return
    if key in (Qt.Key.Key_Comma, Qt.Key.Key_Period) and not (
        mods & Qt.KeyboardModifier.AltModifier
        or mods & Qt.KeyboardModifier.ControlModifier
    ):
        direction = -1 if key == Qt.Key.Key_Comma else 1
        amount = 10 if mods & Qt.KeyboardModifier.ShiftModifier else 1
        if self._step_timeline_frames(direction * amount):
            return
    if (
        key == Qt.Key.Key_A
        and mods & Qt.KeyboardModifier.ControlModifier
        and not (
            mods & Qt.KeyboardModifier.AltModifier
            or mods & Qt.KeyboardModifier.ShiftModifier
        )
    ):
        if not self._is_text_focus():
            self._select_all_timeline_clips()
            return
    if (
        key == Qt.Key.Key_D
        and mods & Qt.KeyboardModifier.ControlModifier
        and not (
            mods & Qt.KeyboardModifier.AltModifier
            or mods & Qt.KeyboardModifier.ShiftModifier
        )
    ):
        if not self._is_text_focus():
            self._duplicate_selected_timeline_clips()
            return
    if (
        key in (Qt.Key.Key_C, Qt.Key.Key_X, Qt.Key.Key_V)
        and mods & Qt.KeyboardModifier.ControlModifier
        and not (
            mods & Qt.KeyboardModifier.AltModifier
            or mods & Qt.KeyboardModifier.ShiftModifier
        )
    ):
        if not self._is_text_focus():
            if key == Qt.Key.Key_C:
                self._copy_selected_timeline_clips()
            elif key == Qt.Key.Key_X:
                self._cut_selected_timeline_clips()
            else:
                self._paste_timeline_clipboard()
            return
    if key == Qt.Key.Key_Space:
        self._toggle_play()
        return
    # Ctrl+T: apply Cross Dissolve (500ms) to the selected clip's right edge
    if (
        key == Qt.Key.Key_T
        and mods & Qt.KeyboardModifier.ControlModifier
        and not (mods & Qt.KeyboardModifier.ShiftModifier)
    ):
        self._apply_transition_to_selected("dissolve", 500)
        return
    if key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and (
        mods & Qt.KeyboardModifier.AltModifier
    ):
        settings = getattr(self, "_project_settings", {}) or {}
        step = type(self)._timeline_nudge_step_ms(
            settings,
            shift=bool(mods & Qt.KeyboardModifier.ShiftModifier),
            ctrl=bool(mods & Qt.KeyboardModifier.ControlModifier),
        )
        self._nudge_selected_clips(-step if key == Qt.Key.Key_Left else step)
        return
    if key in (Qt.Key.Key_Up, Qt.Key.Key_Down) and not (
        mods & Qt.KeyboardModifier.AltModifier
        or mods & Qt.KeyboardModifier.ControlModifier
        or mods & Qt.KeyboardModifier.ShiftModifier
    ):
        if not self._is_text_focus():
            self._jump_to_timeline_edit_point(-1 if key == Qt.Key.Key_Up else 1)
            return
    step = 5000 if mods & Qt.KeyboardModifier.ShiftModifier else 1000
    project_end = max(0, int(self._player.duration()))
    if key == Qt.Key.Key_Left:
        self._player.set_position(
            _bounded_seek_position(
                self._player.position(), -step, project_end,
            )
        )
        self._ensure_playhead_visible()
        return
    if key == Qt.Key.Key_Right:
        self._player.set_position(
            _bounded_seek_position(
                self._player.position(), step, project_end,
            )
        )
        self._ensure_playhead_visible()
        return
    if key == Qt.Key.Key_Home:
        self._player.set_position(0)
        self._ensure_playhead_visible()
        return
    if key == Qt.Key.Key_End:
        self._player.set_position(project_end)
        self._ensure_playhead_visible()
        return
    super(type(self), self).keyPressEvent(event)

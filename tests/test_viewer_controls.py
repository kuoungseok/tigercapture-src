from __future__ import annotations

from types import SimpleNamespace


def test_viewer_fit_button_routes_through_feedback_handler():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

    from app.video_editor_ui_preview_transport import build_preview_transport_area

    QApplication.instance() or QApplication([])

    class _Player:
        def position(self) -> int:
            return 0

    class _Owner(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[str] = []
            self.popout_btn = QPushButton(self)
            self._player = _Player()
            self._strokes = []

        def _refresh_top_project_breadcrumb(self) -> None:
            pass

        def _yield_startup_ui(self, _label: str) -> None:
            pass

        def _paint_preview_canvas_overlay(self, *_args) -> None:
            pass

        def _install_icon_pulse(self, *_args, **_kwargs) -> None:
            pass

        def _toggle_play(self) -> None:
            pass

        def _step_timeline_frames(self, _frames: int) -> bool:
            return True

        def _stop_transport(self) -> None:
            pass

        def _show_viewer_speed_menu(self) -> None:
            pass

        def _show_viewer_compare_menu(self) -> None:
            pass

        def _scale_preview_to_fit(self) -> None:
            self.calls.append("raw_fit")

        def _fit_viewer_preview_from_button(self) -> None:
            self.calls.append("fit_button")

        def _toggle_ar_pbr_depth_view(self, _checked: bool = False) -> None:
            pass

        def _mark_in_at_playhead(self) -> None:
            pass

        def _mark_out_at_playhead(self) -> None:
            pass

        def _clear_active_selection(self) -> None:
            pass

        def _add_marker_at_playhead(self) -> None:
            pass

        def _on_jog_delta(self, _frames: int) -> None:
            pass

        def _on_shuttle_speed_changed(self, _speed: float) -> None:
            pass

        def _on_undo(self) -> None:
            pass

        def _on_redo(self) -> None:
            pass

        def _on_new_project(self) -> None:
            pass

        def _on_save_project(self) -> None:
            pass

        def _on_open_project(self) -> None:
            pass

        def _open_command_palette(self) -> None:
            pass

        def _set_timeline_tool_mode(self, _mode: str) -> None:
            pass

        def _blade_at_playhead(self) -> None:
            pass

        def _ripple_delete_selected(self) -> None:
            pass

        def _open_precision_trim_dialog(self) -> None:
            pass

        def _shortcut_zoom_in(self) -> None:
            pass

        def _shortcut_zoom_out(self) -> None:
            pass

        def _shortcut_zoom_fit(self) -> None:
            pass

    owner = _Owner()
    layout = QVBoxLayout(owner)
    build_preview_transport_area(owner, owner, layout)

    owner.viewer_fit_btn.click()

    assert owner.calls == ["fit_button"]


def test_viewer_depth_toggle_refreshes_current_frame_and_syncs_button():
    from app.video_editor_window import VideoEditorWindow

    class _Style:
        def __init__(self) -> None:
            self.polished = 0

        def unpolish(self, _widget) -> None:
            pass

        def polish(self, _widget) -> None:
            self.polished += 1

    class _Button:
        def __init__(self) -> None:
            self.checked = False
            self.tooltip = ""
            self.props: dict[str, object] = {}
            self.blocked: list[bool] = []
            self._style = _Style()

        def blockSignals(self, value: bool) -> None:
            self.blocked.append(bool(value))

        def setChecked(self, value: bool) -> None:
            self.checked = bool(value)

        def setToolTip(self, value: str) -> None:
            self.tooltip = str(value)

        def setText(self, value: str) -> None:
            self.text = str(value)

        def setProperty(self, key: str, value: object) -> None:
            self.props[str(key)] = value

        def style(self):
            return self._style

    class _Player:
        def __init__(self) -> None:
            self.mode = "off"
            self.cleared = 0
            self.refreshed = 0

        def set_ar_pbr_depth_view_mode(self, mode: str) -> str:
            self.mode = str(mode)
            return self.mode

        def ar_pbr_depth_view_mode(self) -> str:
            return self.mode

        def clear_preview_prerender_cache(self) -> None:
            self.cleared += 1

        def refresh_current_frame(self) -> None:
            self.refreshed += 1

    canvas = SimpleNamespace(update_count=0)
    canvas.update = lambda: setattr(canvas, "update_count", canvas.update_count + 1)
    owner = SimpleNamespace(
        _player=_Player(),
        viewer_depth_btn=_Button(),
        _drawing_canvas=canvas,
        flashes=[],
    )
    owner._sync_ar_pbr_depth_view_button = (
        lambda: VideoEditorWindow._sync_ar_pbr_depth_view_button(owner)
    )
    owner._flash_status = lambda text: owner.flashes.append(str(text))

    VideoEditorWindow._toggle_ar_pbr_depth_view(owner, True)

    assert owner._player.mode == "matte"
    assert owner._player.cleared == 1
    assert owner._player.refreshed == 1
    assert owner.viewer_depth_btn.checked is True
    assert owner.viewer_depth_btn.props["active"] is True
    assert owner._drawing_canvas.update_count == 1
    assert owner.flashes == ["Depth view: Matte"]

    VideoEditorWindow._toggle_ar_pbr_depth_view(owner, True)

    assert owner._player.mode == "distance"
    assert owner.flashes[-1] == "Depth view: Distance"

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


class _FakePixmap:
    def __init__(self, payload: bytes = b"fake-popout-capture") -> None:
        self.payload = payload

    def save(self, path: str) -> bool:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(self.payload)
        return True


class _FakeWindow:
    def __init__(self) -> None:
        self.visible = False
        self.closed = 0
        self.raised = 0
        self.activated = 0
        self.geometry: tuple[int, int, int, int] = (0, 0, 0, 0)

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def close(self) -> None:
        self.closed += 1
        self.visible = False

    def isVisible(self) -> bool:
        return self.visible

    def raise_(self) -> None:
        self.raised += 1

    def activateWindow(self) -> None:
        self.activated += 1

    def setGeometry(self, x: int, y: int, width: int, height: int) -> None:
        self.geometry = (x, y, width, height)

    def grab(self) -> _FakePixmap:
        return _FakePixmap()


class _FakeSectionButton:
    def __init__(self, host: "_FakeSectionHost") -> None:
        self._host = host

    def isChecked(self) -> bool:
        return bool(self._host.opened)


class _FakeSectionHost:
    def __init__(self, opened: bool = False) -> None:
        self.opened = bool(opened)
        self.visible = True

    def findChildren(self, *_args):
        return [_FakeSectionButton(self)]

    def isVisible(self) -> bool:
        return bool(self.visible)

    def setVisible(self, value: bool) -> None:
        self.visible = bool(value)

    def geometry(self) -> tuple[int, int, int, int]:
        return (1, 2, 320, 180)


class _FakeScrollArea:
    def __init__(self) -> None:
        self.visible_targets: list[object] = []

    def ensureWidgetVisible(self, widget, *_args) -> None:
        self.visible_targets.append(widget)


class _FakeWorkbenchPanel:
    def __init__(self) -> None:
        self._node_graph_popout = None
        self._voice_lab_window = None
        self.toggle_count = 0
        self.voice_lab_open_count = 0

    def _toggle_node_graph_popout(self) -> None:
        self.toggle_count += 1
        self._node_graph_popout = _FakeWindow()

    def _open_voice_lab(self):
        self.voice_lab_open_count += 1
        self._voice_lab_window = _FakeWindow()
        self._voice_lab_window.show()
        return self._voice_lab_window


class _FakeAudioMixerPanel:
    def __init__(self) -> None:
        self._popout_win = None

    def _toggle_popout(self) -> None:
        self._popout_win = _FakeWindow()


class _FakePlayer:
    def __init__(self) -> None:
        self.cleared = 0
        self.refreshed = 0

    def clear_preview_prerender_cache(self) -> None:
        self.cleared += 1

    def refresh_current_frame(self) -> None:
        self.refreshed += 1


class _FakeCanvas:
    def __init__(self) -> None:
        self.updated = 0

    def update(self) -> None:
        self.updated += 1


class _FakeOwner:
    def __init__(self) -> None:
        self._preview_popout = None
        self._timeline_popout = None
        self._media_pool_popout = None
        self._workbench_popout = None
        self._color_popout = None
        self._subtitle_popout = None
        self._ai_command_popout = None
        self._vtuber_studio_window = None
        self._actor_library_popout = None
        self._effects_library_popout = None
        self._title_presets_popout = None
        self._transitions_popout = None
        self._workflow_presets_popout = None
        self._creator_assist_popout = None
        self._script_edit_popout = None
        self._render_queue_popout = None
        self._audio_workspace_popout = None
        self._pip_popout = None
        self._workbench_panel = _FakeWorkbenchPanel()
        self._audio_mixer_panel = _FakeAudioMixerPanel()
        self._right_dock_scroll = _FakeScrollArea()
        self._left_dock_scroll = _FakeScrollArea()
        self._creator_assist_section_host = _FakeSectionHost(False)
        self._audio_workspace_section_host = _FakeSectionHost(False)
        self._effects_library_section_host = _FakeSectionHost(False)
        self._tracks = [SimpleNamespace(id=1)]
        self._active_track_id = 1
        self._player = _FakePlayer()
        self._drawing_canvas = _FakeCanvas()
        self.preview_toggle_count = 0
        self.compare_sync_count = 0
        self.viewer_compare_sync_count = 0
        self.fit_count = 0

    def _active_track(self):
        for track in self._tracks:
            if track.id == self._active_track_id:
                return track
        return None

    def _find_track(self, track_id: int):
        for track in self._tracks:
            if track.id == track_id:
                return track
        return None

    def _sync_color_compare_buttons(self) -> None:
        self.compare_sync_count += 1

    def _sync_viewer_compare_button(self) -> None:
        self.viewer_compare_sync_count += 1

    def _scale_preview_to_fit(self) -> None:
        self.fit_count += 1

    def _toggle_preview_popout(self) -> None:
        self.preview_toggle_count += 1
        self._preview_popout = _FakeWindow()

    def _toggle_timeline_popout(self) -> None:
        self._timeline_popout = _FakeWindow()

    def _toggle_media_pool_popout(self) -> None:
        self._media_pool_popout = _FakeWindow()

    def _toggle_workbench_popout(self) -> None:
        self._workbench_popout = _FakeWindow()

    def _toggle_color_popout(self) -> None:
        self._color_popout = _FakeWindow()

    def _toggle_subtitle_popout(self) -> None:
        self._subtitle_popout = _FakeWindow()

    def _toggle_ai_command_popout(self) -> None:
        self._ai_command_popout = _FakeWindow()

    def _open_vtuber_broadcast_studio(self) -> None:
        self._vtuber_studio_window = _FakeWindow()

    def _toggle_actor_library_popout(self) -> None:
        self._actor_library_popout = _FakeWindow()

    def _toggle_effects_library_popout(self) -> None:
        self._effects_library_popout = _FakeWindow()

    def _toggle_title_presets_popout(self) -> None:
        self._title_presets_popout = _FakeWindow()

    def _toggle_transitions_popout(self) -> None:
        self._transitions_popout = _FakeWindow()

    def _toggle_workflow_presets_popout(self) -> None:
        self._workflow_presets_popout = _FakeWindow()

    def _toggle_creator_assist_popout(self) -> None:
        self._creator_assist_popout = _FakeWindow()

    def _toggle_script_edit_popout(self) -> None:
        self._script_edit_popout = _FakeWindow()

    def _toggle_render_queue_popout(self) -> None:
        self._render_queue_popout = _FakeWindow()

    def _toggle_audio_workspace_popout(self) -> None:
        self._audio_workspace_popout = _FakeWindow()

    def _toggle_pip_popout(self) -> None:
        self._pip_popout = _FakeWindow()

    def _set_collapsible_host_open(self, host, opened: bool) -> None:
        host.opened = bool(opened)
        host.visible = True


def test_ui_popout_actions_are_registered_without_review_window_actions():
    from app.actions import build_default_action_registry

    registry = build_default_action_registry(None)
    action_ids = {row["id"] for row in registry.list_actions()}

    assert {
        "ui.popout.list",
        "ui.popout.open",
        "ui.popout.set_geometry",
        "ui.popout.capture",
        "ui.popout.close",
    }.issubset(action_ids)
    assert "ui.section.list" in action_ids
    assert "ui.section.set_open" in action_ids
    assert "tts.voice_lab.open" in action_ids
    assert "review.ui.popout.open" not in action_ids
    assert "review.capture.window" not in action_ids
    assert "ui.viewer.compare.set" in action_ids
    assert "ui.viewer.fit" in action_ids


def test_viewer_compare_and_fit_actions_update_editor_state():
    from app.actions import build_default_action_registry

    owner = _FakeOwner()
    registry = build_default_action_registry(owner)

    compared = registry.execute(
        "ui.viewer.compare.set",
        {"mode": "wipe", "labels_enabled": False},
    ).to_dict()
    fitted = registry.execute("ui.viewer.fit").to_dict()

    assert compared["ok"] is True
    assert compared["changed"] is True
    assert compared["result"]["mode"] == "split"
    assert compared["result"]["labels_enabled"] is False
    assert owner._tracks[0].preview_color_compare_mode == "split"
    assert owner._tracks[0].preview_compare_labels_enabled is False
    assert owner.compare_sync_count == 1
    assert owner.viewer_compare_sync_count == 1
    assert owner._player.cleared == 1
    assert owner._player.refreshed == 1
    assert owner._drawing_canvas.updated == 1
    assert fitted["ok"] is True
    assert fitted["changed"] is False
    assert owner.fit_count == 1


def test_ui_popout_open_geometry_capture_and_close(tmp_path):
    from app.actions import build_default_action_registry

    owner = _FakeOwner()
    registry = build_default_action_registry(owner)

    opened = registry.execute("ui.popout.open", {"target": "preview"}).to_dict()
    assert opened["ok"] is True
    assert opened["result"]["target"] == "preview"
    assert owner.preview_toggle_count == 1
    assert owner._preview_popout is not None
    assert owner._preview_popout.isVisible() is True
    assert owner._preview_popout.activated >= 1

    resized = registry.execute(
        "ui.popout.set_geometry",
        {"surface": "viewer", "x": 10, "y": 20, "width": 640, "height": 360},
    ).to_dict()
    assert resized["ok"] is True
    assert resized["result"]["geometry"] == {"x": 10, "y": 20, "width": 640, "height": 360}
    assert owner._preview_popout.geometry == (10, 20, 640, 360)

    listing = registry.execute("ui.popout.list").to_dict()
    assert listing["ok"] is True
    preview_row = next(row for row in listing["result"]["targets"] if row["target"] == "preview")
    assert preview_row["open"] is True
    assert preview_row["geometry"] == {"x": 10, "y": 20, "width": 640, "height": 360}

    capture_path = tmp_path / "preview.bin"
    captured = registry.execute(
        "ui.popout.capture",
        {"target": "preview", "path": str(capture_path), "settle_ms": 0},
    ).to_dict()
    assert captured["ok"] is True
    assert Path(captured["result"]["path"]).exists()
    assert capture_path.read_bytes() == b"fake-popout-capture"

    closed = registry.execute("ui.popout.close", {"target": "preview"}).to_dict()
    assert closed["ok"] is True
    assert closed["result"]["was_open"] is True
    assert owner._preview_popout.isVisible() is False


def test_ui_popout_node_graph_routes_to_workbench_panel():
    from app.actions import build_default_action_registry

    owner = _FakeOwner()
    registry = build_default_action_registry(owner)

    opened = registry.execute("ui.popout.open", {"target": "node"}).to_dict()
    assert opened["ok"] is True
    assert opened["result"]["target"] == "node_graph"
    assert owner._workbench_panel.toggle_count == 1
    assert owner._workbench_panel._node_graph_popout is not None
    assert owner._workbench_panel._node_graph_popout.isVisible() is True


def test_ui_popout_supports_vtuber_studio_and_ai_command_targets():
    from app.actions import build_default_action_registry

    owner = _FakeOwner()
    registry = build_default_action_registry(owner)

    ai_open = registry.execute("ui.popout.open", {"target": "ai_command"}).to_dict()
    studio_open = registry.execute("ui.popout.open", {"target": "vtuber_studio"}).to_dict()

    assert ai_open["ok"] is True
    assert studio_open["ok"] is True
    assert owner._ai_command_popout is not None
    assert owner._vtuber_studio_window is not None


def test_ui_popout_supports_secondary_editor_sections():
    from app.actions import build_default_action_registry

    owner = _FakeOwner()
    registry = build_default_action_registry(owner)
    targets = {
        "actor_library",
        "effects",
        "title_presets",
        "transitions",
        "workflow_presets",
        "creator_assist",
        "script_edit",
        "render_queue",
        "audio_workspace",
        "pip",
        "audio_mixer",
    }

    listing = registry.execute("ui.popout.list").to_dict()
    listed = {row["target"] for row in listing["result"]["targets"]}
    assert {
        "actor_library",
        "effects_library",
        "title_presets",
        "transitions",
        "workflow_presets",
        "creator_assist",
        "script_edit",
        "render_queue",
        "audio_workspace",
        "pip",
        "audio_mixer",
    }.issubset(listed)

    for target in targets:
        opened = registry.execute("ui.popout.open", {"target": target}).to_dict()
        assert opened["ok"] is True

    assert owner._actor_library_popout is not None
    assert owner._effects_library_popout is not None
    assert owner._title_presets_popout is not None
    assert owner._transitions_popout is not None
    assert owner._workflow_presets_popout is not None
    assert owner._creator_assist_popout is not None
    assert owner._script_edit_popout is not None
    assert owner._render_queue_popout is not None
    assert owner._audio_workspace_popout is not None
    assert owner._pip_popout is not None
    assert owner._audio_mixer_panel._popout_win is not None


def test_ui_section_actions_open_collapsible_sections():
    from app.actions import build_default_action_registry

    owner = _FakeOwner()
    registry = build_default_action_registry(owner)

    listing = registry.execute("ui.section.list").to_dict()
    assert listing["ok"] is True
    sections = {row["target"]: row for row in listing["result"]["sections"]}
    assert sections["creator_assist"]["available"] is True
    assert sections["creator_assist"]["open"] is False

    opened = registry.execute("ui.section.set_open", {"target": "creator", "open": True}).to_dict()
    assert opened["ok"] is True
    assert opened["result"]["target"] == "creator_assist"
    assert opened["result"]["after"]["open"] is True
    assert owner._creator_assist_section_host.opened is True
    assert owner._right_dock_scroll.visible_targets[-1] is owner._creator_assist_section_host

    audio = registry.execute("ui.section.set_open", {"section": "voice", "open": True}).to_dict()
    assert audio["ok"] is True
    assert audio["result"]["target"] == "audio_workspace"
    assert owner._audio_workspace_section_host.opened is True


def test_tts_voice_lab_open_action_routes_to_workbench():
    from app.actions import build_default_action_registry

    owner = _FakeOwner()
    registry = build_default_action_registry(owner)

    result = registry.execute("tts.voice_lab.open", {"activate": True}).to_dict()
    assert result["ok"] is True
    assert result["result"]["opened"] is True
    assert result["result"]["visible"] is True
    assert owner._workbench_panel.voice_lab_open_count == 1
    assert owner._workbench_panel._voice_lab_window is not None

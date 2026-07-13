from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_recent_project_memory_filters_recovery_noise(monkeypatch, tmp_path):
    class FakeSettings:
        store: dict[str, object] = {}

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def value(self, key, default=None):
            return self.store.get(key, default)

        def setValue(self, key, value) -> None:
            self.store[key] = value

        def remove(self, key) -> None:
            self.store.pop(key, None)

        def sync(self) -> None:
            pass

    import PySide6.QtCore as qtcore

    FakeSettings.store.clear()
    monkeypatch.setattr(qtcore, "QSettings", FakeSettings)

    from app.project_io import load_last_project_path, load_recent_project_paths, remember_last_project

    project_a = tmp_path / "alpha.tgp"
    project_b = tmp_path / "beta.tgp"
    autosave = tmp_path / "alpha~autosave.tgp"
    recovery = tmp_path / ".tigercapture_recovery" / "alpha_recovery.tgp"
    recovery.parent.mkdir()
    for path in (project_a, project_b, autosave, recovery):
        path.write_text("{}", encoding="utf-8")

    remember_last_project(project_a)
    remember_last_project(project_b)
    remember_last_project(project_a)
    remember_last_project(autosave)
    remember_last_project(recovery)

    assert load_last_project_path() == recovery
    assert load_recent_project_paths(limit=5) == [project_a, project_b]


def test_video_editor_payload_parser_and_crash_note(monkeypatch, tmp_path):
    from app.controller import AppController

    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake")

    source, mode = AppController._parse_video_editor_payload(
        {"source_path": media, "workspace_mode": "simple"}
    )
    assert source == media
    assert mode == "simple"

    source, mode = AppController._parse_video_editor_payload(media)
    assert source == media
    assert mode == "standard"

    events: list[str] = []
    seen: list[bool] = []
    monkeypatch.setattr("app.crash_reporter.has_unseen_crash_report", lambda: True)
    monkeypatch.setattr("app.crash_reporter.mark_crash_report_seen", lambda: seen.append(True))
    editor = SimpleNamespace(_flash_status=lambda msg: events.append(msg))

    assert AppController._note_startup_crash_report(editor)
    assert seen == [True]
    assert events and "크래시 리포트" in events[-1]


def test_launcher_video_editor_open_does_not_auto_resume(monkeypatch):
    from app.controller import AppController

    monkeypatch.setenv("TIGERCAPTURE_CAPTURE_TO_STUDIO", "1")
    events: list[tuple] = []

    class FakeEditor:
        def __init__(self, source_path=None):
            self.source_path = source_path

        def setAttribute(self, *_args, **_kwargs):
            events.append(("set_attr",))

        def show(self):
            events.append(("show",))

        def raise_(self):
            events.append(("raise",))

        def activateWindow(self):
            events.append(("activate",))

    controller = AppController.__new__(AppController)
    controller._track_result_window = lambda editor: events.append(("track", editor))
    controller._clear_launcher_busy_later = lambda: events.append(("clear_busy",))

    monkeypatch.setattr("app.controller.VideoEditorWindow", FakeEditor)
    monkeypatch.setattr(
        AppController,
        "_apply_video_editor_workspace_mode",
        staticmethod(lambda editor, mode: events.append(("mode", mode))),
    )
    monkeypatch.setattr(
        AppController,
        "_note_startup_crash_report",
        staticmethod(lambda editor: events.append(("crash_note",)) or False),
    )
    monkeypatch.setattr(
        AppController,
        "_maybe_offer_resume_last_project",
        lambda self, editor: events.append(("resume",)),
    )

    AppController._open_video_editor(controller, None)

    assert ("show",) in events
    assert ("mode", "standard") in events
    assert ("crash_note",) in events
    assert ("resume",) not in events


def test_capture_launcher_blocks_studio_entry_by_default(monkeypatch):
    from app.controller import AppController

    monkeypatch.delenv("TIGERCAPTURE_CAPTURE_TO_STUDIO", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_ALLOW_STUDIO_ENTRY", raising=False)
    monkeypatch.delenv("TIGERSTUDIO_BUNDLED_STUDIO_ENTRY", raising=False)
    events: list[tuple] = []

    controller = AppController.__new__(AppController)
    controller._clear_launcher_busy_later = lambda: events.append(("clear_busy",))
    monkeypatch.setattr("app.controller.open_in_explorer", lambda path: events.append(("reveal", path)))

    AppController._open_video_editor(controller, None)

    assert events == [("clear_busy",)]


def test_project_load_video_track_skips_hdr_probe_by_default(monkeypatch, tmp_path):
    from app.project_io import _load_video_track

    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake")
    calls: list[str] = []

    def _blocked_hdr_probe(*_args, **_kwargs):
        calls.append("hdr")
        raise AssertionError("Project load should not run HDR ffmpeg probe by default")

    monkeypatch.delenv("TIGERCAPTURE_PROJECT_LOAD_HDR_PROBE", raising=False)
    monkeypatch.setattr("app.hdr_probe.probe_hdr", _blocked_hdr_probe)

    editor = SimpleNamespace(
        _next_track_id=1,
        _tracks=[],
        _insert_track_widget=lambda track: calls.append("insert"),
        _start_thumbnail_extraction=lambda track: calls.append("thumbs"),
        _set_active_track=lambda tid: calls.append(f"active:{tid}"),
    )
    _load_video_track(
        editor,
        {
            "id": 7,
            "clips": [{
                "id": 11,
                "source_path": str(media),
                "source_duration_ms": 1000,
                "timeline_in_ms": 0,
                "source_in_ms": 0,
                "source_out_ms": 1000,
            }],
        },
        media,
    )

    assert "hdr" not in calls
    assert calls[:3] == ["insert", "thumbs", "active:7"]
    assert editor._tracks[0].hdr_info is None


def test_video_track_import_skips_hdr_probe_by_default(monkeypatch, tmp_path):
    calls: list[str] = []

    def _blocked_hdr_probe(*_args, **_kwargs):
        calls.append("hdr")
        raise AssertionError("Video track import should not run HDR ffmpeg probe by default")

    monkeypatch.delenv("TIGERCAPTURE_VIDEO_TRACK_HDR_PROBE", raising=False)
    monkeypatch.setattr("app.hdr_probe.probe_hdr", _blocked_hdr_probe)

    from app.video_editor_window import _probe_track_hdr_info

    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake")

    assert _probe_track_hdr_info(media) is None
    assert calls == []


def test_live2d_startup_warmup_is_opt_in(monkeypatch):
    from app.video_editor_window import _live2d_startup_warmup_enabled

    monkeypatch.delenv("TIGERCAPTURE_LIVE2D_STARTUP_WARMUP", raising=False)
    assert _live2d_startup_warmup_enabled() is False

    monkeypatch.setenv("TIGERCAPTURE_LIVE2D_STARTUP_WARMUP", "1")
    assert _live2d_startup_warmup_enabled() is True


def test_media_pool_ingest_does_not_spawn_external_probes_by_default(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    _ = app

    calls: list[str] = []

    def _blocked_native_probe(*_args, **_kwargs):
        calls.append("native")
        raise AssertionError("Media Pool startup ingest should not call native probe")

    def _blocked_hdr_probe(*_args, **_kwargs):
        calls.append("hdr")
        raise AssertionError("Media Pool startup ingest should not call HDR ffmpeg probe")

    monkeypatch.delenv("TIGERCAPTURE_MEDIA_POOL_HDR_PROBE", raising=False)
    monkeypatch.setattr("app.native_worker.native_media_probe", _blocked_native_probe)
    monkeypatch.setattr("app.hdr_probe.probe_hdr", _blocked_hdr_probe)

    from app.media_pool import MediaPool

    media = tmp_path / "empty.mp4"
    media.write_bytes(b"not a real video")
    pool = MediaPool()
    try:
        assert pool.add_path(media)
        assert calls == []
    finally:
        pool.close()


def test_startup_launcher_cards_and_busy_state(monkeypatch, tmp_path):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QPushButton

    app = QApplication.instance() or QApplication([])
    _ = app

    import app.main_window as main_window_mod
    import app.project_io as project_io
    import app.preset_library as preset_library
    from app.preset_library import EditorPreset
    from app.recent_captures import RecentCapture
    from app.main_window import MainWindow

    project = tmp_path / "demo_project.tgp"
    project.write_text("{}", encoding="utf-8")
    media = tmp_path / "recent_clip.mp4"
    media.write_bytes(b"fake")

    monkeypatch.setattr(project_io, "load_recent_project_paths", lambda limit=2: [project])
    monkeypatch.setattr(main_window_mod, "default_save_dir", lambda: tmp_path)
    monkeypatch.setattr(
        main_window_mod,
        "list_recent",
        lambda _folder, limit=2: [RecentCapture(media, media.stat().st_size, media.stat().st_mtime)],
    )
    monkeypatch.setattr(
        preset_library,
        "presets_by_kind",
        lambda kind: [
            EditorPreset(
                id="template-screenstudio-test",
                kind="template",
                name="Screen Studio Test",
                description="Launcher card smoke test",
                tags=("screen-studio", "template"),
            )
        ] if kind == "template" else [],
    )
    monkeypatch.setenv("TIGERCAPTURE_CAPTURE_TO_STUDIO", "0")

    window = MainWindow()
    try:
        cards = window.findChildren(QPushButton, "LauncherMiniCard")
        texts = "\n".join(card.text() for card in cards)
        assert cards == []
        assert "demo_project.tgp" not in texts
        assert "recent_clip.mp4" not in texts
        start_cards = window.findChildren(QPushButton, "LauncherStartCard")
        start_texts = "\n".join(card.text() for card in start_cards)
        start_tooltips = "\n".join(card.toolTip() for card in start_cards)
        assert len(start_cards) == 2
        assert len([card for card in start_cards if not card.isHidden()]) == 1
        assert "Screen Studio Test" not in start_texts
        assert "Screen Studio Test" not in start_tooltips
        assert "템플릿" not in start_texts
        assert "Template" not in start_texts
        assert window.minimumHeight() <= 620
        assert window.height() <= 700
        assert window.templates_btn.text() in {"스튜디오 열기", "Open Studio"}
        assert window.templates_btn.isHidden()
        assert window.pro_editor_btn.isHidden()
        assert not hasattr(window, "_template_row_layout")
        assert window.launcher_workspace_mode() == "standard"
        assert window.launcher_workspace_standard_btn.isChecked()
        assert not window.launcher_workspace_simple_btn.isChecked()
        assert hasattr(window, "launcher_workspace_switch")
        assert not window.launcher_workspace_switch.isChecked()
        window.retranslate()
        assert window.templates_btn.text() in {"스튜디오 열기", "Open Studio"}
        assert window._pro_editor_label.text() in {"가벼운 캡처", "Light Capture"}
        opened_editors: list[object] = []
        window.open_video_editor_requested.connect(lambda payload: opened_editors.append(payload))
        window.pro_editor_btn.click()
        assert opened_editors == []

        window.show_startup_busy("Opening...")
        assert not window._startup_busy.isHidden()
        window.clear_startup_busy()
        assert window._startup_busy.isHidden()
    finally:
        window.close()


def test_startup_launcher_can_enable_bundled_studio_entry(monkeypatch, tmp_path):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    _ = app
    monkeypatch.setenv("TIGERCAPTURE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TIGERCAPTURE_CAPTURE_TO_STUDIO", "1")

    from app.main_window import MainWindow

    window = MainWindow()
    try:
        assert not window.templates_btn.isHidden()
        assert not window.pro_editor_btn.isHidden()
        assert window._pro_editor_label.text() in {"스튜디오 진입", "Open Studio"}
        opened_editors: list[object] = []
        window.open_video_editor_requested.connect(lambda payload: opened_editors.append(payload))

        window.pro_editor_btn.click()
        QTimer.singleShot(80, app.quit)
        app.exec()
        assert isinstance(opened_editors[-1], dict)
        assert opened_editors[-1]["source_path"] is None
        assert opened_editors[-1]["workspace_mode"] == "standard"

        window.launcher_workspace_simple_btn.click()
        assert window.launcher_workspace_switch.isChecked()
        window.pro_editor_btn.click()
        QTimer.singleShot(80, app.quit)
        app.exec()
        assert isinstance(opened_editors[-1], dict)
        assert opened_editors[-1]["source_path"] is None
        assert opened_editors[-1]["workspace_mode"] == "simple"
    finally:
        window.close()


def test_launcher_ignores_internal_media_pool_file_drag(monkeypatch, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtWidgets import QApplication

    from app.media_asset_routing import MEDIA_POOL_ITEM_MIME_TYPE
    from app.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    _ = app
    monkeypatch.setenv("TIGERCAPTURE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TIGERCAPTURE_CAPTURE_TO_STUDIO", "1")
    video = tmp_path / "pool_clip.mp4"
    video.write_bytes(b"fake")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(video))])
    mime.setData(MEDIA_POOL_ITEM_MIME_TYPE, str(video).encode("utf-8"))

    class _FakeDropEvent:
        def __init__(self, mime_data):
            self._mime_data = mime_data
            self.accepted = False
            self.ignored = False

        def mimeData(self):
            return self._mime_data

        def acceptProposedAction(self):
            self.accepted = True
            self.ignored = False

        def ignore(self):
            self.ignored = True

    window = MainWindow()
    opened_editors: list[object] = []
    window.open_video_editor_requested.connect(lambda payload: opened_editors.append(payload))
    try:
        drag = _FakeDropEvent(mime)
        MainWindow.dragEnterEvent(window, drag)
        drop = _FakeDropEvent(mime)
        MainWindow.dropEvent(window, drop)

        assert drag.ignored is True
        assert drop.ignored is True
        assert opened_editors == []
    finally:
        window.close()


def test_launcher_workspace_toggle_can_restore_env_mode(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    _ = app
    monkeypatch.setenv("TIGERCAPTURE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TIGERCAPTURE_CAPTURE_TO_STUDIO", "1")
    monkeypatch.setenv("TIGERCAPTURE_LAUNCHER_WORKSPACE_MODE", "simple")
    from app.main_window import MainWindow

    window = MainWindow()
    try:
        assert window.launcher_workspace_mode() == "simple"
        assert window.launcher_workspace_switch.isChecked()
        assert window.launcher_workspace_simple_btn.isChecked()
        assert not window.launcher_workspace_standard_btn.isChecked()
    finally:
        window.close()


def test_launcher_workspace_state_repairs_invalid_json(monkeypatch, tmp_path):
    import json
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    _ = app
    monkeypatch.setenv("TIGERCAPTURE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TIGERCAPTURE_CAPTURE_TO_STUDIO", "1")
    monkeypatch.setenv("TIGERCAPTURE_LAUNCHER_STATE_FORCE", "1")
    state = tmp_path / "launcher_state.json"
    state.write_text("{broken", encoding="utf-8")

    from app.main_window import MainWindow

    window = MainWindow()
    try:
        assert window.launcher_workspace_mode() == "standard"
        repaired = json.loads(state.read_text(encoding="utf-8"))
        assert repaired["workspace_mode"] == "standard"
        assert repaired["repaired_reason"] == "state_json_unreadable"
        assert list(tmp_path.glob("launcher_state.broken-*.json"))
    finally:
        window.close()


def test_startup_template_auto_applies_after_first_media(monkeypatch):
    import app.preset_library as preset_library
    from app.preset_library import EditorPreset
    from app.video_editor_window import VideoEditorWindow

    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_TEMPLATE_AUTO_APPLY_ENABLED", "1")

    template = EditorPreset(
        id="template-auto-apply",
        kind="template",
        name="Auto Apply Template",
        payload={"sequence": []},
    )
    monkeypatch.setattr(
        preset_library,
        "preset_by_id",
        lambda preset_id: template if preset_id == template.id else None,
    )

    events: list[tuple] = []
    dummy = SimpleNamespace(
        _startup_template_id=template.id,
        _startup_template_name=template.name,
        _startup_template_pending=True,
        _startup_template_applied=False,
        _startup_template_last_failure="",
        _tracks=[SimpleNamespace(source_path=None, clips=[object()])],
        _audio_tracks=[],
        _live2d_actor_tracks=[],
        _spine_actor_tracks=[],
        _preset_apply_failure_reason=lambda preset: "",
        _apply_editor_preset_object=lambda preset, depth=0: events.append(("apply", preset.id, depth)) or True,
        _workflow_apply_summary_rows=lambda preset: [
            {"kind": "effect", "status": "will_apply"},
            {"kind": "title", "status": "will_apply"},
        ],
        _preset_undo_label=lambda preset, context: f"{context}:{preset.id}",
        _register_change=lambda label: events.append(("undo", label)),
        _refresh_player_tracks=lambda: events.append(("refresh_player",)),
        _refresh_workbench=lambda: events.append(("refresh_workbench",)),
        _player=SimpleNamespace(refresh_current_frame=lambda: events.append(("frame",))),
        _show_workflow_apply_summary_toast=lambda preset, rows: events.append(("toast", preset.id, len(rows))),
        _flash_status=lambda msg: events.append(("flash", msg)),
    )
    dummy._startup_template_has_media_target = (
        lambda: VideoEditorWindow._startup_template_has_media_target(dummy)
    )
    dummy._startup_template_target_state = (
        lambda: VideoEditorWindow._startup_template_target_state(dummy)
    )
    dummy._startup_template_required_target_gap = (
        lambda preset, **kwargs: VideoEditorWindow._startup_template_required_target_gap(
            dummy,
            preset,
            **kwargs,
        )
    )
    dummy._startup_template_preset = (
        lambda: VideoEditorWindow._startup_template_preset(dummy)
    )
    dummy._finish_workflow_preset_application = (
        lambda preset, **kwargs: VideoEditorWindow._finish_workflow_preset_application(
            dummy,
            preset,
            **kwargs,
        )
    )

    assert VideoEditorWindow._try_apply_startup_template_if_ready(dummy, "video import")
    assert dummy._startup_template_pending is False
    assert dummy._startup_template_applied is True
    assert ("apply", template.id, 0) in events
    assert ("undo", f"startup template:{template.id}") in events
    assert ("toast", template.id, 2) in events
    assert any("Template applied: Auto Apply Template" in item[1] for item in events if item[0] == "flash")

    events.clear()
    assert not VideoEditorWindow._try_apply_startup_template_if_ready(dummy, "video import")
    assert events == []


def test_startup_template_waits_for_compatible_media(monkeypatch):
    import app.preset_library as preset_library
    from app.preset_library import EditorPreset
    from app.video_editor_window import VideoEditorWindow

    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_TEMPLATE_AUTO_APPLY_ENABLED", "1")

    template = EditorPreset(
        id="template-waits",
        kind="template",
        name="Waiting Template",
        payload={"sequence": []},
    )
    monkeypatch.setattr(
        preset_library,
        "preset_by_id",
        lambda preset_id: template if preset_id == template.id else None,
    )

    events: list[tuple] = []
    dummy = SimpleNamespace(
        _startup_template_id=template.id,
        _startup_template_name=template.name,
        _startup_template_pending=True,
        _startup_template_applied=False,
        _startup_template_last_failure="",
        _tracks=[SimpleNamespace(source_path=None, clips=[object()])],
        _audio_tracks=[],
        _live2d_actor_tracks=[],
        _spine_actor_tracks=[],
        _preset_apply_failure_reason=lambda preset: "비디오 클립 선택 또는 활성 타임라인 위치가 필요합니다",
        _apply_editor_preset_object=lambda preset, depth=0: (_ for _ in ()).throw(AssertionError("should not apply")),
        _flash_status=lambda msg: events.append(("flash", msg)),
    )
    dummy._startup_template_has_media_target = (
        lambda: VideoEditorWindow._startup_template_has_media_target(dummy)
    )
    dummy._startup_template_target_state = (
        lambda: VideoEditorWindow._startup_template_target_state(dummy)
    )
    dummy._startup_template_required_target_gap = (
        lambda preset, **kwargs: VideoEditorWindow._startup_template_required_target_gap(
            dummy,
            preset,
            **kwargs,
        )
    )
    dummy._startup_template_preset = (
        lambda: VideoEditorWindow._startup_template_preset(dummy)
    )

    assert not VideoEditorWindow._try_apply_startup_template_if_ready(dummy, "video import")
    assert dummy._startup_template_pending is True
    assert dummy._startup_template_applied is False
    assert "비디오 클립 선택" in dummy._startup_template_last_failure
    assert any("Template waiting" in item[1] for item in events if item[0] == "flash")


def test_startup_template_does_not_partially_apply_video_template_to_audio(monkeypatch):
    import app.preset_library as preset_library
    from app.preset_library import EditorPreset
    from app.video_editor_window import VideoEditorWindow

    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_TEMPLATE_AUTO_APPLY_ENABLED", "1")

    template = EditorPreset(
        id="template-video-required",
        kind="template",
        name="Video Required Template",
        payload={"sequence": [{"preset_id": "effect-video-required", "kind": "effect"}]},
    )
    effect = EditorPreset(
        id="effect-video-required",
        kind="effect",
        name="Video Effect",
    )
    by_id = {template.id: template, effect.id: effect}
    monkeypatch.setattr(
        preset_library,
        "preset_by_id",
        lambda preset_id: by_id.get(str(preset_id)),
    )

    events: list[tuple] = []
    dummy = SimpleNamespace(
        _startup_template_id=template.id,
        _startup_template_name=template.name,
        _startup_template_pending=True,
        _startup_template_applied=False,
        _startup_template_last_failure="",
        _tracks=[],
        _audio_tracks=[SimpleNamespace(is_loaded=True, clips=[object()])],
        _live2d_actor_tracks=[],
        _spine_actor_tracks=[],
        _preset_apply_failure_reason=lambda preset: "",
        _apply_editor_preset_object=lambda preset, depth=0: (_ for _ in ()).throw(AssertionError("should not apply")),
        _flash_status=lambda msg: events.append(("flash", msg)),
    )
    dummy._startup_template_has_media_target = (
        lambda: VideoEditorWindow._startup_template_has_media_target(dummy)
    )
    dummy._startup_template_target_state = (
        lambda: VideoEditorWindow._startup_template_target_state(dummy)
    )
    dummy._startup_template_required_target_gap = (
        lambda preset, **kwargs: VideoEditorWindow._startup_template_required_target_gap(
            dummy,
            preset,
            **kwargs,
        )
    )
    dummy._startup_template_preset = (
        lambda: VideoEditorWindow._startup_template_preset(dummy)
    )

    assert not VideoEditorWindow._try_apply_startup_template_if_ready(dummy, "audio import")
    assert dummy._startup_template_pending is True
    assert dummy._startup_template_applied is False
    assert "비디오 미디어" in dummy._startup_template_last_failure
    assert any("Template waiting" in item[1] for item in events if item[0] == "flash")


def test_simple_mode_keeps_media_pool_and_workbench_visible():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    _ = app

    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow()
    try:
        editor._project_settings = {
            "screenstudio_simple_mode": True,
            "screenstudio_advanced_visible": False,
        }
        editor.show()
        app.processEvents()
        editor._apply_screenstudio_simple_mode_ui()
        app.processEvents()

        assert editor._left_dock_scroll.isVisible()
        assert editor._right_dock_host.isVisible()
        assert editor._media_pool_section_host.isVisible()
        assert editor._workbench_section_host.isVisible()
        assert not editor._effects_library_section_host.isVisible()
        assert not editor._render_queue_section_host.isVisible()
    finally:
        editor.close()


def test_workspace_mode_switch_toggles_simple_and_standard_panels():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    _ = app

    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow()
    try:
        assert not editor._screenstudio_simple_mode_enabled()
        assert editor.workspace_standard_btn.isChecked()
        assert not editor.workspace_simple_btn.isChecked()
        editor._project_settings = {
            "screenstudio_simple_mode": False,
            "screenstudio_simple_mode_ui": {"layout": "standard"},
            "screenstudio_advanced_visible": True,
        }
        editor.show()
        app.processEvents()
        editor._apply_screenstudio_simple_mode_ui()
        app.processEvents()

        assert editor.workspace_standard_btn.isChecked()
        assert not editor.workspace_simple_btn.isChecked()
        assert not editor.screenstudio_advanced_btn.isVisible()
        assert editor._effects_library_section_host.isVisible()
        assert editor._render_queue_section_host.isVisible()

        editor.workspace_simple_btn.click()
        app.processEvents()

        assert editor._screenstudio_simple_mode_enabled()
        assert editor.workspace_simple_btn.isChecked()
        assert editor.screenstudio_advanced_btn.isVisible()
        assert editor._media_pool_section_host.isVisible()
        assert editor._workbench_section_host.isVisible()
        assert not editor._effects_library_section_host.isVisible()
        assert not editor._render_queue_section_host.isVisible()

        editor.workspace_standard_btn.click()
        app.processEvents()

        assert not editor._screenstudio_simple_mode_enabled()
        assert editor.workspace_standard_btn.isChecked()
        assert editor._effects_library_section_host.isVisible()
        assert editor._render_queue_section_host.isVisible()
    finally:
        editor.close()

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_whisper_transcription_service_uses_injected_commands_without_running_ffmpeg(tmp_path):
    from app.video_editor_subtitle_workflow import WhisperTranscriptionService

    wav_path = tmp_path / "audio.wav"
    wav_path.write_bytes(b"placeholder")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if cmd[:4] == ["ffmpeg-test", "-nostdin", "-v", "info"]:
            return SimpleNamespace(returncode=0, stderr="Stream #0:1: Audio: aac")
        if cmd[0] == "ffmpeg-test":
            return SimpleNamespace(returncode=0, stderr=b"")
        if cmd[:2] == ["python-test", "-c"]:
            assert repr(str(wav_path)) in cmd[2]
            assert "WhisperModel('base'" in cmd[2]
            assert "language='ko'" in cmd[2]
            return SimpleNamespace(
                returncode=0,
                stdout='[{"text": "hello", "start": 0.5, "end": 1.25}]',
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    progress = []
    service = WhisperTranscriptionService(
        ffmpeg_resolver=lambda: "ffmpeg-test",
        command_runner=fake_run,
        temp_wav_factory=lambda: str(wav_path),
        hidden_kwargs_factory=lambda: {"startupinfo": "hidden"},
        python_executable="python-test",
    )

    segments = service.transcribe(
        tmp_path / "clip.mp4",
        language="ko",
        model_size="base",
        progress=progress.append,
    )

    assert segments == [{"text": "hello", "start": 0.5, "end": 1.25}]
    assert progress == [10, 30, 50, 100]
    assert not wav_path.exists()
    assert calls[0][0] == ["ffmpeg-test", "-nostdin", "-v", "info", "-i", str(tmp_path / "clip.mp4")]
    assert calls[1][0][-1] == str(wav_path)
    assert calls[2][0][:2] == ["python-test", "-c"]
    assert all(kwargs["startupinfo"] == "hidden" for _cmd, kwargs in calls)


def test_whisper_transcription_service_stops_when_probe_has_no_audio(tmp_path):
    from app.video_editor_subtitle_workflow import WhisperTranscriptionError, WhisperTranscriptionService

    wav_path = tmp_path / "audio.wav"
    wav_path.write_bytes(b"placeholder")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0, stderr="Stream #0:0: Video: h264")

    service = WhisperTranscriptionService(
        ffmpeg_resolver=lambda: "ffmpeg-test",
        command_runner=fake_run,
        temp_wav_factory=lambda: str(wav_path),
        hidden_kwargs_factory=dict,
        python_executable="python-test",
    )

    with pytest.raises(WhisperTranscriptionError, match="no audio"):
        service.transcribe(tmp_path / "clip.mp4")

    assert len(calls) == 1
    assert not wav_path.exists()


def test_subtitle_overlay_controller_updates_hides_and_repositions():
    _qapp()
    from PySide6.QtWidgets import QLabel, QWidget

    from app.subtitles import Subtitle, SubtitlePanel
    from app.video_editor_subtitle_workflow import SubtitleOverlayController

    panel = SubtitlePanel(position_provider=lambda: 0)
    panel.layer.add(Subtitle(start_ms=0, end_ms=1000, text="Boxed subtitle", show_box=True))
    host = QWidget()
    host.resize(640, 360)
    overlay = QLabel(host)

    controller = SubtitleOverlayController(panel=panel, overlay=overlay, preview_host=host)

    active = controller.update(500)

    assert active is not None
    assert overlay.text() == "Boxed subtitle"
    assert not overlay.isHidden()
    assert "rgba(0, 0, 0, 180)" in overlay.styleSheet()
    assert overlay.width() <= int(640 * 0.9)
    assert overlay.x() >= 0
    assert overlay.y() >= 0

    assert controller.update(1500) is None
    assert overlay.isHidden()

    panel.layer.replace_all([Subtitle(start_ms=0, end_ms=1000, text="Plain subtitle", show_box=False)])
    controller.update(500)

    assert "background-color: transparent" in overlay.styleSheet()


def test_subtitle_overlay_controller_change_hook_registers_editor_change():
    _qapp()
    from PySide6.QtWidgets import QLabel, QWidget

    from app.subtitles import Subtitle, SubtitlePanel
    from app.video_editor_subtitle_workflow import SubtitleOverlayController

    panel = SubtitlePanel(position_provider=lambda: 0)
    panel.layer.add(Subtitle(start_ms=100, end_ms=500, text="At playhead"))
    overlay = QLabel()
    host = QWidget()
    host.resize(400, 240)
    changes = []
    player = SimpleNamespace(position=lambda: 120)
    controller = SubtitleOverlayController(
        panel=panel,
        overlay=overlay,
        preview_host=host,
        player=player,
        register_change=changes.append,
    )

    controller.on_subtitles_changed()

    assert overlay.text() == "At playhead"
    assert changes == ["subtitle edit"]


def test_subtitle_lane_edit_controller_reuses_subtitle_edit_dialog_contract():
    _qapp()
    from app.subtitles import Subtitle, SubtitlePanel
    from app.video_editor_subtitle_workflow import SubtitleLaneEditController

    class AcceptingDialog:
        instances = []

        def __init__(self, parent, initial, max_ms):
            self.parent = parent
            self.initial = initial
            self.max_ms = max_ms
            self.instances.append(self)

        def exec(self):
            return 1

        def result_subtitle(self):
            return Subtitle(start_ms=100, end_ms=700, text="edited", show_box=False)

    panel = SubtitlePanel(position_provider=lambda: 0)
    panel.layer.add(Subtitle(start_ms=0, end_ms=500, text="old"))
    changed = []
    controller = SubtitleLaneEditController(
        panel=panel,
        player=SimpleNamespace(duration=lambda: 1234),
        changed_callback=lambda: changed.append("changed"),
        dialog_cls=AcceptingDialog,
    )

    assert controller.edit(0) is True
    edited = panel.layer.items()[0]
    assert edited.text == "edited"
    assert edited.start_ms == 100
    assert edited.show_box is False
    assert AcceptingDialog.instances[0].initial.text == "old"
    assert AcceptingDialog.instances[0].max_ms == 1234
    assert changed == ["changed"]
    assert controller.edit(99) is False


def test_ai_subtitle_workflow_applies_screenstudio_planned_rows():
    _qapp()
    from app.subtitles import SubtitlePanel
    from app.video_editor_subtitle_workflow import AISubtitleWorkflow

    panel = SubtitlePanel(position_provider=lambda: 0)
    changed = []
    seen = {}

    def plan_builder(settings, transcript_segments):
        seen["settings"] = settings
        seen["segments"] = transcript_segments
        return {
            "subtitle_rows": [
                {
                    "text": "planned",
                    "start_ms": 250,
                    "end_ms": 900,
                    "show_box": False,
                    "style": {"preset": "screenstudio"},
                }
            ]
        }

    editor = SimpleNamespace(
        _project_settings={"screenstudio_simple_mode": True},
        _subtitle_panel=panel,
        _on_subtitles_changed=lambda: changed.append("changed"),
    )
    workflow = AISubtitleWorkflow(subtitle_plan_builder=plan_builder)

    count = workflow.apply_segments(
        editor,
        [
            {"text": "raw", "start": 0.25, "end": 0.9},
            {"text": "bad", "start": object(), "end": 1.0},
        ],
    )

    assert count == 1
    assert seen["settings"] == {"screenstudio_simple_mode": True}
    assert seen["segments"] == [{"text": "raw", "start_ms": 250, "end_ms": 900}]
    sub = panel.layer.items()[0]
    assert sub.text == "planned"
    assert sub.show_box is False
    assert sub.style == {"preset": "screenstudio"}
    assert changed == ["changed"]


def test_subtitle_section_builder_wires_panel_lane_and_header_buttons():
    _qapp()
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    from app.subtitles import SubtitleLaneRow, SubtitlePanel
    from app.video_editor_subtitle_workflow import SubtitleSectionBuilder

    class FakeRuler(QWidget):
        def __init__(self):
            super().__init__()
            self.subtitle_layer = None

        def set_subtitle_layer(self, layer):
            self.subtitle_layer = layer

    parent = QWidget()
    root_layout = QVBoxLayout(parent)
    tracks_host = QWidget()
    tracks_layout = QVBoxLayout(tracks_host)
    ruler = FakeRuler()
    tracks_layout.addWidget(ruler)
    calls = []

    widgets = SubtitleSectionBuilder().build(
        parent=parent,
        root_layout=root_layout,
        tracks_layout=tracks_layout,
        timeline_ruler=ruler,
        player=SimpleNamespace(position=lambda: 321),
        px_per_sec=55.0,
        make_section_header=lambda title, key: QLabel(f"{key}:{title}"),
        on_generate_ai_subtitles=lambda: calls.append("ai"),
        on_import_srt_subtitles=lambda: calls.append("srt"),
        on_subtitles_changed=lambda: calls.append("changed"),
        on_subtitle_popout=lambda: calls.append("popout"),
        on_subtitle_lane_edit=lambda idx: calls.append(("edit", idx)),
    )

    assert isinstance(widgets.panel, SubtitlePanel)
    assert isinstance(widgets.lane, SubtitleLaneRow)
    assert ruler.subtitle_layer is widgets.panel.layer
    assert tracks_layout.indexOf(widgets.lane) == tracks_layout.indexOf(ruler) + 1
    assert widgets.panel.isHidden()

    widgets.toggle_button.setChecked(True)
    assert not widgets.panel.isHidden()
    widgets.ai_button.click()
    widgets.srt_button.click()
    widgets.panel.subtitles_changed.emit()
    widgets.panel.popout_requested.emit()
    widgets.lane.request_edit.emit(3)

    assert calls == ["ai", "srt", "changed", "popout", ("edit", 3)]

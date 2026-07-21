import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtWidgets import QApplication

from app.gif_editor_window import (
    TIMELINE_MAX_HINT_W,
    TIMELINE_MIN_VIEW_W,
    FrameTimeline,
    GifEditorWindow,
)
from app.modes import CaptureMode


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_frame_timeline_keeps_long_content_scrollable_without_layout_growth():
    _ = _app()
    timeline = FrameTimeline()

    timeline.set_thumbnails([None] * 160)

    assert timeline.width() > TIMELINE_MAX_HINT_W
    assert timeline.minimumWidth() == 1
    assert timeline.minimumSizeHint().width() == TIMELINE_MIN_VIEW_W
    assert timeline.sizeHint().width() == TIMELINE_MAX_HINT_W


def test_gif_editor_save_notice_does_not_expand_window(monkeypatch, tmp_path):
    app = _app()
    monkeypatch.setattr(GifEditorWindow, "_start_thumbnail_generation", lambda self: None)
    monkeypatch.setattr("app.gif_editor_window.QMessageBox.information", lambda *args, **kwargs: 0)

    frames = [Image.new("RGB", (320, 180), (i % 255, 20, 40)) for i in range(120)]
    window = GifEditorWindow(frames, 15, tmp_path, mode=CaptureMode.GIF)
    try:
        window.show()
        app.processEvents()
        window.resize(900, 620)
        app.processEvents()
        before_width = window.width()

        output = tmp_path / "capture.gif"
        output.write_bytes(b"gif")
        for _ in range(3):
            window.notify_saved(output)
            app.processEvents()

        assert window.width() <= before_width
    finally:
        window.close()

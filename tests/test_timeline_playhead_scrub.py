from __future__ import annotations

import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _mouse_event(event_type, x: int, y: int, *, button=None, buttons=None):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    if button is None:
        button = Qt.MouseButton.LeftButton
    if buttons is None:
        buttons = button
    pos = QPointF(float(x), float(y))
    return QMouseEvent(
        event_type,
        pos,
        pos,
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def test_video_track_playhead_drag_requests_project_position():
    _app()
    from PySide6.QtCore import QEvent, Qt

    from app.timeline_track_row import TrackRow
    from app.video_track_legacy import VideoTrack

    row = TrackRow(VideoTrack(id=7, duration_ms=10_000))
    row.resize(900, row.LABEL_H + row.TIMELINE_H + 4)
    row.set_px_per_sec(100.0)
    row.set_position(1000)
    emitted: list[tuple[int, int]] = []
    row.position_requested.connect(lambda tid, ms: emitted.append((int(tid), int(ms))))
    try:
        start_x = row._project_ms_to_x(1000)
        end_x = row._project_ms_to_x(3250)
        y = row.LABEL_H + row.TIMELINE_H // 2

        row.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, start_x, y))
        row.mouseMoveEvent(
            _mouse_event(
                QEvent.Type.MouseMove,
                end_x,
                y,
                button=Qt.MouseButton.NoButton,
                buttons=Qt.MouseButton.LeftButton,
            )
        )
        row.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, end_x, y))

        assert emitted[0] == (7, 1000)
        assert emitted[-1] == (7, 3250)
        assert row._dragging_playhead is False
    finally:
        row.deleteLater()


def test_audio_track_playhead_drag_requests_project_position():
    _app()
    from PySide6.QtCore import QEvent, Qt

    from app.audio_tracks import AudioClip, AudioTrack
    from app.video_editor_audio_track_row import AudioTrackRow

    clip = AudioClip(
        id=3,
        source_path=Path("voice.wav"),
        duration_ms=10_000,
        trim_end_ms=10_000,
    )
    row = AudioTrackRow(AudioTrack(id=11, clips=[clip]))
    row.resize(900, row.LABEL_H + row.BAR_H + row.SPECTRUM_H + 4)
    row.set_px_per_sec(100.0)
    row.set_position(1200)
    emitted: list[tuple[int, int]] = []
    row.position_requested.connect(lambda tid, ms: emitted.append((int(tid), int(ms))))
    try:
        start_x = row._project_ms_to_x(1200)
        end_x = row._project_ms_to_x(4100)
        y = row.LABEL_H + row.BAR_H // 2

        row.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, start_x, y))
        row.mouseMoveEvent(
            _mouse_event(
                QEvent.Type.MouseMove,
                end_x,
                y,
                button=Qt.MouseButton.NoButton,
                buttons=Qt.MouseButton.LeftButton,
            )
        )
        row.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, end_x, y))

        assert emitted[0] == (11, 1200)
        assert emitted[-1] == (11, 4100)
        assert row._dragging_playhead is False
    finally:
        row.deleteLater()

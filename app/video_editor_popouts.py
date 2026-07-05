"""Detached preview, dock popout, and VTuber Studio windows.

These widgets are imported by ``video_editor_window`` but kept out of the main
editor module so popout/broadcast work can evolve without touching the 50k-line
integration surface.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QSize, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.drawing import DrawingCanvas
from app.broadcast_evidence_ui import (
    broadcast_evidence_register_defaults,
    broadcast_evidence_status_lines,
    build_broadcast_evidence_registration_payload,
)
from app.i18n import tr
from app.icons import app_icon, icon_size
from app.style import COLOR_BG_L1, COLOR_BG_L3


class PreviewPopoutWindow(QWidget):
    """Top-level mirror of the preview area. Displays the latest frame
    coming from ``ProjectPlayer.frame_ready`` scaled to fit. Closing
    this window simply destroys it ??the in-editor preview was never
    disturbed, so editing keeps working the whole time.
    """

    closed = Signal()
    toggle_play_requested = Signal()
    dock_requested = Signal()
    stop_requested = Signal()
    prev_frame_requested = Signal()
    next_frame_requested = Signal()
    mark_in_requested = Signal()
    mark_out_requested = Signal()
    clear_range_requested = Signal()
    marker_requested = Signal()
    fit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.popout.title"))
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLOR_BG_L1};
                color: #DDE3F5;
            }}
            QWidget#PlayBar {{
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }}
            QLabel#TimeLabel {{
                color: #F7F8FF;
                background-color: transparent;
                border: none;
                font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0px;
            }}
            QLabel#SpeedLabel {{
                color: #AEB7C8;
                background-color: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #151B26,
                    stop:1 #090D14
                );
                border: 1px solid #2C364A;
                border-radius: 4px;
                padding: 0px 8px;
                font-size: 10px;
                font-weight: 650;
            }}
            QPushButton#PlayButton,
            QPushButton#ToolButton,
            QPushButton#PreviewPopoutDockButton {{
                background-color: rgba(255,255,255,8);
                border: 1px solid rgba(180,190,210,30);
                border-radius: 4px;
                min-width: 20px;
                min-height: 20px;
                max-width: 20px;
                max-height: 20px;
                padding: 0px;
            }}
            QPushButton#PlayButton:hover,
            QPushButton#ToolButton:hover,
            QPushButton#PreviewPopoutDockButton:hover {{
                background-color: rgba(255,255,255,18);
                border-color: #4A5260;
            }}
            QPushButton#PlayButton:pressed,
            QPushButton#ToolButton:pressed,
            QPushButton#PreviewPopoutDockButton:pressed {{
                background-color: rgba(98, 90, 226, 170);
            }}
            QPushButton#ViewerDropdownButton {{
                color: #AEB7C8;
                background-color: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #151B26,
                    stop:1 #090D14
                );
                border: 1px solid #2C364A;
                border-radius: 3px;
                font-size: 10px;
                font-weight: 650;
                padding: 0px 6px;
                min-height: 20px;
                max-height: 20px;
            }}
            QPushButton#ViewerDropdownButton:hover {{
                color: #F1F4FA;
                background-color: #111722;
                border-color: #3A465B;
            }}
            """
        )
        self.resize(1280, 720)
        self.setMinimumSize(640, 360)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._label, stretch=1)
        self._controls_host = QWidget(self)
        self._controls_host.setObjectName("PlayBar")
        self._controls_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._controls_host.setMinimumHeight(32)
        self._controls_host.setMaximumHeight(36)
        controls = QHBoxLayout(self._controls_host)
        controls.setContentsMargins(8, 2, 8, 2)
        controls.setSpacing(5)

        self._time_label = QLabel("0:00 / 0:00", self._controls_host)
        self._time_label.setObjectName("TimeLabel")
        self._time_label.setMinimumWidth(128)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._prev_btn = self._make_icon_button("previous", "Step back one frame")
        self._prev_btn.clicked.connect(self.prev_frame_requested.emit)
        self._play_btn = self._make_icon_button("play", "Play / Pause", play=True)
        self._play_btn.clicked.connect(self.toggle_play_requested.emit)
        self._stop_btn = self._make_icon_button("stop", "Stop playback")
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        self._next_btn = self._make_icon_button("next", "Step forward one frame")
        self._next_btn.clicked.connect(self.next_frame_requested.emit)
        self._mark_in_btn = self._make_icon_button("mark-in", tr("veditor.mark_in.tooltip"))
        self._mark_in_btn.clicked.connect(self.mark_in_requested.emit)
        self._mark_out_btn = self._make_icon_button("mark-out", tr("veditor.mark_out.tooltip"))
        self._mark_out_btn.clicked.connect(self.mark_out_requested.emit)
        self._clear_btn = self._make_icon_button("x", tr("veditor.clear_sel.tooltip"))
        self._clear_btn.clicked.connect(self.clear_range_requested.emit)
        self._marker_btn = self._make_icon_button("marker", "Add marker at playhead")
        self._marker_btn.clicked.connect(self.marker_requested.emit)
        self._fit_btn = QPushButton("Fit", self._controls_host)
        self._fit_btn.setObjectName("ViewerDropdownButton")
        self._fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fit_btn.setFixedSize(38, 20)
        self._fit_btn.setToolTip("Fit frame to viewer")
        self._fit_btn.clicked.connect(self.fit_requested.emit)
        self._speed_label = QLabel("1.0x", self._controls_host)
        self._speed_label.setObjectName("SpeedLabel")
        self._speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._speed_label.setFixedSize(38, 20)
        self._dock_btn = self._make_icon_button("popout", "Dock preview back into the editor", name="PreviewPopoutDockButton")
        self._dock_btn.clicked.connect(self.dock_requested.emit)

        controls.addWidget(self._time_label)
        controls.addStretch(1)
        for button in (
            self._prev_btn,
            self._play_btn,
            self._stop_btn,
            self._next_btn,
        ):
            controls.addWidget(button)
        controls.addStretch(1)
        # Keep mark/range controls wired for keyboard/action parity, but
        # mirror the main viewer: these advanced controls are hidden by
        # default and do not crowd the popout play bar.
        for button in (
            self._mark_in_btn,
            self._mark_out_btn,
            self._clear_btn,
            self._marker_btn,
        ):
            controls.addWidget(button)
            button.hide()
        controls.addWidget(self._fit_btn)
        controls.addWidget(self._speed_label)
        controls.addWidget(self._dock_btn)
        layout.addWidget(self._controls_host, stretch=0)
        self._overlay_canvas = DrawingCanvas(
            get_time_ms=lambda: 0,
            get_strokes=lambda: [],
            parent=self,
        )
        self._overlay_canvas.hide()
        self._last_image: QImage | None = None
        self._last_pixmap: QPixmap | None = None
        self._playing = False
        self.fit_requested.connect(self.fit_to_view)

    def _make_icon_button(
        self,
        icon_name: str,
        tooltip: str,
        *,
        play: bool = False,
        name: str = "PreviewPopoutTool",
    ) -> QPushButton:
        button = QPushButton("", self._controls_host)
        button.setObjectName("PreviewPopoutPlay" if play else name)
        if play:
            button.setObjectName("PlayButton")
        elif name == "PreviewPopoutTool":
            button.setObjectName("ToolButton")
        size = 20
        icon_px = 11 if play else 11
        button.setFixedSize(size, size)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(app_icon(icon_name, size=icon_px, color="#FFFFFF" if play else "#D7DAE7"))
        button.setIconSize(icon_size(icon_px))
        button.setToolTip(tooltip)
        return button

    def overlay_canvas(self) -> DrawingCanvas:
        return self._overlay_canvas

    def set_overlay_hooks(self, paint_hook=None, interaction_hook=None) -> None:
        self._overlay_canvas.set_extra_paint_hook(paint_hook)
        self._overlay_canvas.set_interaction_hook(interaction_hook)
        if paint_hook is None and interaction_hook is None:
            self._overlay_canvas.hide()
        else:
            self._layout_overlay()
            self._overlay_canvas.show()
            self._overlay_canvas.raise_()
        self._layout_controls()

    def set_playing(self, playing: bool) -> None:
        self._playing = bool(playing)
        self._play_btn.setIcon(app_icon("pause" if playing else "play", size=11, color="#D7DAE7"))
        self._play_btn.setIconSize(icon_size(11))

    def set_time_text(self, text: str) -> None:
        self._time_label.setText(str(text or "0:00 / 0:00"))
        self._layout_controls()

    def set_speed_label(self, speed) -> None:
        try:
            text = f"{float(speed):g}x"
        except Exception:
            text = str(speed or "1.0x")
        self._speed_label.setText(text)
        self._layout_controls()

    def fit_to_view(self) -> None:
        self._rescale()

    def update_frame(self, image: QImage) -> None:
        self._last_image = image
        self._rescale()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()
        self._layout_controls()

    def _rescale(self) -> None:
        if self._last_image is None:
            return
        target = self._label.size()
        if target.width() < 2 or target.height() < 2:
            return
        pm = QPixmap.fromImage(self._last_image).scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._last_pixmap = pm
        self._label.setPixmap(pm)
        self._layout_overlay()

    def _layout_overlay(self) -> None:
        if self._last_pixmap is None or self._last_pixmap.isNull():
            self._overlay_canvas.hide()
            return
        label_rect = self._label.geometry()
        x = label_rect.x() + max(0, (label_rect.width() - self._last_pixmap.width()) // 2)
        y = label_rect.y() + max(0, (label_rect.height() - self._last_pixmap.height()) // 2)
        self._overlay_canvas.setGeometry(x, y, self._last_pixmap.width(), self._last_pixmap.height())
        self._overlay_canvas.show()
        self._overlay_canvas.raise_()

    def _layout_controls(self) -> None:
        self._controls_host.updateGeometry()
        self._controls_host.update()
        self._overlay_canvas.raise_()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            self.toggle_play_requested.emit()
            return
        # F11 toggles fullscreen on the popout monitor; Esc leaves it.
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class ColorPopoutWindow(QWidget):
    """Floating window that hosts the color-grading panel + scopes
    while the user has the section "popped out" of the editor.

    The widget tree is *moved* (reparented) into this window ??there's
    only one canonical color panel in the app, so sliders/wheels keep
    their values across pop-out / pop-in transitions and the rest of
    the editor's signals don't need to be re-wired.

    Closing the window emits ``closed``; the editor re-installs the
    panel into its own layout in response.
    """

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.color_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(960, 480)
        self.setMinimumSize(720, 400)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        """Reparent ``host`` into this window so the user can edit
        from the floating surface."""
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class TimelinePopoutWindow(QWidget):
    """Floating window that hosts the timeline (tracks + ruler + audio
    rows) when the user pops it out of the editor. Same reparent-the-
    widget-tree pattern as ``ColorPopoutWindow`` ??a single canonical
    timeline lives on the editor and just changes parent across pop-
    out / pop-in transitions, so all the existing track signals stay
    wired."""

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.timeline_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(1280, 360)
        self.setMinimumSize(640, 240)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class SubtitlePopoutWindow(QWidget):
    """Floating window that hosts the subtitle dock when the user pops
    it out of the editor's right column. Same reparent pattern as the
    timeline / colour popouts ??only one canonical subtitle panel
    exists in the app, so its list and slider state survive pop-out /
    pop-in cycles."""

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.subtitle_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(560, 480)
        self.setMinimumSize(320, 280)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class EffectsLibraryPopoutWindow(QWidget):
    """Floating window that hosts the Effects Library when the user
    pops it out. Same reparent pattern as the other popouts ??the
    cards keep their drag handlers since they're real QWidgets, the
    popout just owns the layout while the dock shows a placeholder."""

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.effects_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(320, 360)
        self.setMinimumSize(220, 280)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class MediaPoolPopoutWindow(QWidget):
    """Floating window that hosts the whole left dock column.

    The media pool button is the entry point, but the detached surface also
    carries effect, title, transition, and workflow preset sections so the
    left side of the editor moves as one workspace.
    """

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.media_pool_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(620, 760)
        self.setMinimumSize(340, 360)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class WorkbenchPopoutWindow(QWidget):
    """Floating window that hosts the main Workbench section."""

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.workbench_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(640, 780)
        self.setMinimumSize(360, 360)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class SectionPopoutWindow(QWidget):
    """Generic floating window for smaller dock sections.

    Large surfaces such as Preview, Timeline, Media Pool, and Workbench keep
    their dedicated classes. This small host covers secondary panels so adding
    a new dockable section does not require another one-off window class.
    """

    closed = Signal()

    def __init__(
        self,
        title: str,
        *,
        width: int = 520,
        height: int = 420,
        min_width: int = 260,
        min_height: int = 220,
        parent=None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(str(title or "Panel"))
        self.setStyleSheet(f"QWidget {{ background-color: {COLOR_BG_L3}; }}")
        self.resize(max(260, int(width)), max(220, int(height)))
        self.setMinimumSize(max(180, int(min_width)), max(160, int(min_height)))
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class _BroadcastProjectAudioBusMixdownThread(QThread):
    finished_with_diag = Signal(object)
    progress_changed = Signal(object)

    def __init__(
        self,
        *,
        tracks: list,
        output_path: Path,
        duration_ms: int,
        sample_rate: int = 48000,
        channels: int = 2,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._tracks = tracks
        self._output_path = Path(output_path)
        self._duration_ms = int(duration_ms)
        self._sample_rate = int(sample_rate)
        self._channels = int(channels)

    def run(self) -> None:  # pragma: no cover - exercised through integration/manual UI
        try:
            from app.broadcast_audio_mix import render_project_audio_bus_mixdown_progressive

            diag = render_project_audio_bus_mixdown_progressive(
                self._tracks,
                self._output_path,
                duration_ms=self._duration_ms,
                sample_rate=self._sample_rate,
                channels=self._channels,
                progress_callback=lambda event: self.progress_changed.emit(event),
                cancel_requested=self.isInterruptionRequested,
            )
        except Exception as exc:
            diag = {
                "schema": "tigerstudio.broadcast.project_audio_bus_mixdown.v1",
                "ok": False,
                "error": str(exc),
            }
        self.finished_with_diag.emit(diag)


class VTuberBroadcastStudioWindow(QWidget):
    """Operator-facing VTuber studio status surface.

    The actual compositing remains in ProjectPlayer/export. This window makes
    the three roles explicit so Performance Source clips are not mistaken for
    Program Output backgrounds. It is intentionally avatar-agnostic: VRM /
    VSeeFace, Live2D, and future avatar targets share this studio surface.
    """

    closed = Signal()
    apply_avatar_mapping_requested = Signal()
    apply_live2d_mapping_requested = Signal()
    start_live_target_requested = Signal(object)
    stop_live_target_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("VTuber Studio - Tiger Studio")
        self.resize(980, 680)
        self.setMinimumSize(620, 420)
        self.setStyleSheet(
            "QWidget{background:#0C0F18;color:#EEF0F8;}"
            "QLabel#StudioTitle{font-size:18px;font-weight:900;color:#FFFFFF;}"
            "QLabel#StudioSub{font-size:11px;color:#AEB6CC;}"
            "QFrame#StudioCard{background:#121725;border:1px solid #2E3757;border-radius:14px;}"
            "QLabel#StudioCardTitle{font-size:12px;font-weight:900;color:#FFFFFF;}"
            "QLabel#StudioCardBody{font-size:11px;color:#C6CCE0;}"
            "QLabel#StudioTargetLabel{font-size:11px;font-weight:900;color:#FFFFFF;}"
            "QLabel#StudioTargetStatus{font-size:11px;color:#AEB6CC;}"
            "QComboBox#StudioTargetCombo{background:#151B2B;color:#EEF0F8;border:1px solid #3C4770;border-radius:8px;padding:6px 10px;}"
            "QLineEdit#StudioTargetField{background:#151B2B;color:#EEF0F8;border:1px solid #3C4770;border-radius:8px;padding:6px 10px;}"
            "QSpinBox#StudioTargetSpin{background:#151B2B;color:#EEF0F8;border:1px solid #3C4770;border-radius:8px;padding:6px 10px;}"
            "QPushButton#StudioAction{background:#7658FF;color:#FFFFFF;border:1px solid #9C8CFF;border-radius:10px;padding:8px 12px;font-weight:800;}"
            "QPushButton#StudioAction:hover{background:#8A73FF;}"
        )
        self._editor_ref = None
        self._target_options: list[dict[str, object]] = []
        self._updating_target_combo = False
        self._updating_live_target = False
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        title = QLabel("VTuber Studio", self)
        title.setObjectName("StudioTitle")
        subtitle = QLabel(
            "Program Output is the recorded/broadcast picture. Performance Source is tracking input only.",
            self,
        )
        subtitle.setObjectName("StudioSub")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)
        subtitle.setText(
            "Program Output is the recorded/broadcast picture. Performance Source is tracking input only. "
            "Avatar targets can be VRM/VSeeFace, Live2D, or future studio actors."
        )

        target_row = QHBoxLayout()
        target_row.setContentsMargins(0, 0, 0, 0)
        target_row.setSpacing(8)
        target_label = QLabel("Avatar Target", self)
        target_label.setObjectName("StudioTargetLabel")
        self._target_combo = QComboBox(self)
        self._target_combo.setObjectName("StudioTargetCombo")
        self._target_combo.currentIndexChanged.connect(self._on_target_combo_changed)
        self._target_status = QLabel("", self)
        self._target_status.setObjectName("StudioTargetStatus")
        self._target_status.setWordWrap(True)
        target_row.addWidget(target_label)
        target_row.addWidget(self._target_combo, stretch=1)
        target_row.addWidget(self._target_status, stretch=2)
        root.addLayout(target_row)

        self._live_card = QFrame(self)
        self._live_card.setObjectName("StudioCard")
        live_lay = QGridLayout(self._live_card)
        live_lay.setContentsMargins(14, 12, 14, 12)
        live_lay.setSpacing(8)
        live_title = QLabel("Live Target", self._live_card)
        live_title.setObjectName("StudioCardTitle")
        live_body = QLabel("Select where Program Output will be recorded or streamed.", self._live_card)
        live_body.setObjectName("StudioCardBody")
        live_body.setWordWrap(True)
        self._live_target_combo = QComboBox(self._live_card)
        self._live_target_combo.setObjectName("StudioTargetCombo")
        self._live_target_combo.currentIndexChanged.connect(self._on_live_target_combo_changed)
        self._live_bitrate_spin = QSpinBox(self._live_card)
        self._live_bitrate_spin.setObjectName("StudioTargetSpin")
        self._live_bitrate_spin.setRange(500, 60000)
        self._live_bitrate_spin.setSingleStep(500)
        self._live_bitrate_spin.setSuffix(" kbps")
        self._live_bitrate_spin.editingFinished.connect(self._persist_live_target_settings)
        self._live_preflight_btn = QPushButton("Check", self._live_card)
        self._live_preflight_btn.setObjectName("StudioAction")
        self._live_preflight_btn.clicked.connect(self._on_live_target_preflight)
        self._live_start_btn = QPushButton("Go Live", self._live_card)
        self._live_start_btn.setObjectName("StudioAction")
        self._live_start_btn.clicked.connect(self._on_live_target_start)
        self._live_stop_btn = QPushButton("Stop", self._live_card)
        self._live_stop_btn.setObjectName("StudioAction")
        self._live_stop_btn.clicked.connect(self.stop_live_target_requested.emit)
        self._live_server_label = QLabel("Server", self._live_card)
        self._live_server_label.setObjectName("StudioTargetLabel")
        self._live_server_edit = QLineEdit(self._live_card)
        self._live_server_edit.setObjectName("StudioTargetField")
        self._live_server_edit.setPlaceholderText("rtmps://server/app")
        self._live_server_edit.editingFinished.connect(self._persist_live_target_settings)
        self._live_key_label = QLabel("Stream Key", self._live_card)
        self._live_key_label.setObjectName("StudioTargetLabel")
        self._live_key_edit = QLineEdit(self._live_card)
        self._live_key_edit.setObjectName("StudioTargetField")
        self._live_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._live_key_edit.setPlaceholderText("Session only")
        self._live_key_edit.editingFinished.connect(self._store_live_target_session_key)
        self._live_file_label = QLabel("File", self._live_card)
        self._live_file_label.setObjectName("StudioTargetLabel")
        self._live_file_edit = QLineEdit(self._live_card)
        self._live_file_edit.setObjectName("StudioTargetField")
        self._live_file_edit.setPlaceholderText("broadcast_output.mp4")
        self._live_file_edit.editingFinished.connect(self._persist_live_target_settings)
        self._live_audio_label = QLabel("Audio", self._live_card)
        self._live_audio_label.setObjectName("StudioTargetLabel")
        self._live_audio_combo = QComboBox(self._live_card)
        self._live_audio_combo.setObjectName("StudioTargetCombo")
        self._live_audio_combo.addItem("No audio", "none")
        self._live_audio_combo.addItem("Silent stereo", "silence")
        self._live_audio_combo.addItem("Project audio bus", "project_audio_bus")
        self._live_audio_combo.addItem("Microphone / device", "dshow_device")
        self._live_audio_combo.addItem("Audio file", "file")
        self._live_audio_combo.currentIndexChanged.connect(self._on_live_audio_combo_changed)
        self._live_audio_source_edit = QLineEdit(self._live_card)
        self._live_audio_source_edit.setObjectName("StudioTargetField")
        self._live_audio_source_edit.setPlaceholderText("Microphone device name or audio file path")
        self._live_audio_source_edit.editingFinished.connect(self._persist_live_target_settings)
        self._live_retry_label = QLabel("Retries", self._live_card)
        self._live_retry_label.setObjectName("StudioTargetLabel")
        self._live_retry_spin = QSpinBox(self._live_card)
        self._live_retry_spin.setObjectName("StudioTargetSpin")
        self._live_retry_spin.setRange(0, 20)
        self._live_retry_spin.setValue(3)
        self._live_retry_spin.setToolTip("RTMP reconnect attempts. Set 0 to disable auto reconnect.")
        self._live_retry_spin.editingFinished.connect(self._persist_live_target_settings)
        self._live_status = QLabel("", self._live_card)
        self._live_status.setObjectName("StudioTargetStatus")
        self._live_status.setWordWrap(True)
        live_lay.addWidget(live_title, 0, 0)
        live_lay.addWidget(live_body, 0, 1, 1, 3)
        live_lay.addWidget(self._live_target_combo, 1, 0, 1, 2)
        live_lay.addWidget(self._live_bitrate_spin, 1, 2)
        live_lay.addWidget(self._live_preflight_btn, 1, 3)
        live_lay.addWidget(self._live_server_label, 2, 0)
        live_lay.addWidget(self._live_server_edit, 2, 1, 1, 3)
        live_lay.addWidget(self._live_key_label, 3, 0)
        live_lay.addWidget(self._live_key_edit, 3, 1, 1, 3)
        live_lay.addWidget(self._live_file_label, 4, 0)
        live_lay.addWidget(self._live_file_edit, 4, 1, 1, 3)
        live_lay.addWidget(self._live_audio_label, 5, 0)
        live_lay.addWidget(self._live_audio_combo, 5, 1)
        live_lay.addWidget(self._live_audio_source_edit, 5, 2, 1, 2)
        live_lay.addWidget(self._live_retry_label, 6, 0)
        live_lay.addWidget(self._live_retry_spin, 6, 1)
        live_lay.addWidget(self._live_status, 7, 0, 1, 4)
        live_lay.addWidget(self._live_start_btn, 8, 2)
        live_lay.addWidget(self._live_stop_btn, 8, 3)
        root.addWidget(self._live_card)

        self._evidence_card, self._evidence_body = self._make_card(
            "Broadcast Evidence",
            "Local Program Output checks can run automatically. Private RTMP and Discord/window-share evidence must be registered after real checks.",
        )
        evidence_actions = QHBoxLayout()
        evidence_actions.setContentsMargins(0, 0, 0, 0)
        evidence_actions.setSpacing(8)
        self._evidence_refresh_btn = QPushButton("Refresh Evidence", self._evidence_card)
        self._evidence_refresh_btn.setObjectName("StudioAction")
        self._evidence_refresh_btn.clicked.connect(self._update_broadcast_evidence_status)
        self._evidence_register_rtmp_btn = QPushButton("Register RTMP", self._evidence_card)
        self._evidence_register_rtmp_btn.setObjectName("StudioAction")
        self._evidence_register_rtmp_btn.clicked.connect(lambda: self._open_broadcast_evidence_register_dialog("private_rtmp_ingest"))
        self._evidence_register_discord_btn = QPushButton("Register Discord", self._evidence_card)
        self._evidence_register_discord_btn.setObjectName("StudioAction")
        self._evidence_register_discord_btn.clicked.connect(lambda: self._open_broadcast_evidence_register_dialog("discord_window_share"))
        evidence_actions.addWidget(self._evidence_refresh_btn)
        evidence_actions.addWidget(self._evidence_register_rtmp_btn)
        evidence_actions.addWidget(self._evidence_register_discord_btn)
        evidence_actions.addStretch(1)
        evidence_layout = self._evidence_card.layout()
        if evidence_layout is not None:
            evidence_layout.addLayout(evidence_actions)
        root.addWidget(self._evidence_card)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        self._program_card, self._program_body = self._make_card(
            "Program Output",
            "Uses capture, normal media/image, or green chroma fallback. Performance Source video is never direct output.",
        )
        self._source_card, self._source_body = self._make_card(
            "Source Tracking",
            "Shows the active Performance Source frame for face/body tracking.",
        )
        self._mapping_card, self._mapping_body = self._make_card(
            "Avatar Mapping",
            "Shows how tracking drives the selected avatar: VRM/VSeeFace, Live2D, face, eyes, mouth, framing, and movement limits.",
        )
        self._controls_card, self._controls_body = self._make_card(
            "Studio Controls",
            "Choose an avatar target, add a Performance Source track at the same time, then map or monitor the result.",
        )
        grid.addWidget(self._program_card, 0, 0, 1, 2)
        grid.addWidget(self._source_card, 1, 0)
        grid.addWidget(self._mapping_card, 1, 1)
        grid.addWidget(self._controls_card, 2, 0, 1, 2)
        root.addLayout(grid, stretch=1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self._map_btn = QPushButton("Map Source to Selected Avatar", self)
        self._map_btn.setObjectName("StudioAction")
        self._map_btn.clicked.connect(self.apply_avatar_mapping_requested.emit)
        close_btn = QPushButton("Close", self)
        close_btn.setObjectName("StudioAction")
        close_btn.clicked.connect(self.close)
        actions.addWidget(self._map_btn)
        actions.addWidget(close_btn)
        root.addLayout(actions)

    def _make_card(self, title: str, body: str) -> tuple[QFrame, QLabel]:
        card = QFrame(self)
        card.setObjectName("StudioCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        title_label = QLabel(title, card)
        title_label.setObjectName("StudioCardTitle")
        body_label = QLabel(body, card)
        body_label.setObjectName("StudioCardBody")
        body_label.setWordWrap(True)
        lay.addWidget(title_label)
        lay.addWidget(body_label, stretch=1)
        return card, body_label

    def update_from_editor(self, editor) -> None:
        self._editor_ref = editor
        try:
            pos_ms = int(editor._player.position())
        except Exception:
            pos_ms = int(getattr(getattr(editor, "_player", None), "_position_ms", 0) or 0)
        try:
            from app.vtuber.performance_source import program_output_contract
            from app.vtuber.broadcast_studio_layout import build_vtuber_broadcast_studio_layout

            contract = program_output_contract(getattr(editor, "_tracks", []) or [], pos_ms)
            target_payload = self._avatar_target_summary_from_editor(editor)
            self._populate_avatar_targets(target_payload)
            self._populate_live_targets(editor)
            avatar = self._avatar_context_from_editor(editor, target_payload=target_payload)
            bridge_status = avatar.get("bridge_status") if avatar.get("kind") == "vrm" else None
            settings = getattr(editor, "_project_settings", {}) or {}
            broadcast = settings.get("broadcast_output") if isinstance(settings, dict) else {}
            live_target = broadcast.get("live_target") if isinstance(broadcast, dict) else {}
            layout = build_vtuber_broadcast_studio_layout(
                source_name="Performance Source",
                avatar_name=avatar["name"],
                avatar_target=target_payload.get("selected") if isinstance(target_payload.get("selected"), dict) else None,
                bridge_status=bridge_status if isinstance(bridge_status, dict) else None,
                timeline_tracks=getattr(editor, "_tracks", []) or [],
                time_ms=pos_ms,
                program_contract=contract,
                live_target=live_target if isinstance(live_target, dict) else None,
            )
        except Exception as exc:
            self._program_body.setText(f"Studio contract unavailable: {exc}")
            self._source_body.setText("Select media and Performance Source tracks in the timeline.")
            self._mapping_body.setText("Select or configure a VRM/VSeeFace, Live2D, or other avatar target to inspect mapping.")
            self._controls_body.setText("The studio window is a status surface; editing remains on the timeline.")
            self._populate_live_targets(editor)
            return

        background = dict(layout.get("program", {}).get("background") or {})
        performance = dict(layout.get("performance_source") or {})
        program = dict(layout.get("program") or {})
        fallback = dict(program.get("fallback") or {})
        self._program_body.setText(
            "Safe output: yes\n"
            f"Background: {background.get('kind', background.get('type', 'fallback'))}\n"
            "Direct Performance Source output: no\n"
            f"Avatar renderer: {program.get('renderer') or 'avatar_composite'}"
            + ("\nFallback: internal VRM renderer" if fallback.get("active") else "")
        )
        self._source_body.setText(
            f"Active: {'yes' if performance.get('active') else 'no'}\n"
            f"Name: {performance.get('name') or '-'}\n"
            f"Path: {performance.get('source_path') or '-'}"
        )
        if avatar["kind"] == "none":
            self._mapping_body.setText(
                "No avatar target selected.\n"
                "Add/select a VRM/VSeeFace avatar or a Live2D actor clip. "
                "Performance Source remains ready as tracking input."
            )
        elif avatar["kind"] == "vrm":
            bridge = avatar.get("bridge_status") if isinstance(avatar.get("bridge_status"), dict) else {}
            capture = dict(bridge.get("capture") or {})
            view = dict(bridge.get("view") or {})
            input_source = dict(view.get("input_source") or {})
            pose = avatar.get("pose_stream") if isinstance(avatar.get("pose_stream"), dict) else {}
            pose_stream = dict(pose.get("pose_stream") or {})
            self._mapping_body.setText(
                f"Avatar: {avatar['name']}\n"
                "Type: VRM / VSeeFace bridge\n"
                f"Bridge: {bridge.get('state', 'unknown')} / {view.get('badge', {}).get('text', capture.get('status', 'not probed'))}\n"
                f"Capture: {capture.get('method', '-')} / {capture.get('status', '-')}\n"
                f"Performance Source: {input_source.get('label') or performance.get('name') or '-'}\n"
                f"Pose stream: {'ready' if pose_stream.get('ready') else 'needs setup'}\n"
                "Path: Performance Source -> OpenSeeFace -> VMC/pose stream -> VRM / VSeeFace Bridge"
            )
        else:
            selected = avatar["clip"]
            subject = str(getattr(selected, "performance_source_subject_type", "") or getattr(selected, "mocap_subject_type", "") or "not mapped")
            source = str(getattr(selected, "performance_source_path", "") or "")
            self._mapping_body.setText(
                f"Avatar: {avatar['name']}\n"
                "Type: Live2D actor clip\n"
                f"Subject: {subject}\n"
                f"Mapped source: {Path(source).name if source else '-'}"
            )
        can_direct_map = avatar["kind"] == "live2d"
        self._map_btn.setEnabled(can_direct_map)
        self._map_btn.setToolTip(
            "Apply the active Performance Source to the selected Live2D actor clip"
            if can_direct_map
            else "VRM/VSeeFace targets are monitored here; direct baking is handled by the bridge/output workflow."
        )
        self._controls_body.setText(
            "1. Mark a video/webcam clip as Performance Source.\n"
            "2. Place it on the Performance Source track.\n"
            "3. Select a VRM/VSeeFace avatar or Live2D actor target.\n"
            "4. Live2D clips can bake mapping keys here; VRM/VSeeFace follows the bridge pose stream."
        )
        self._update_broadcast_evidence_status()

    def _avatar_target_summary_from_editor(self, editor) -> dict[str, object]:
        try:
            from app.actions.editor_adapter import EditorAdapter

            return EditorAdapter(editor).avatar_target_summary()
        except Exception:
            return {
                "selected_id": "none",
                "selected": {"id": "none", "kind": "none", "label": "No Avatar Target", "name": "Avatar"},
                "options": [],
            }

    def _populate_avatar_targets(self, payload: dict[str, object]) -> None:
        options = list(payload.get("options") if isinstance(payload.get("options"), list) else [])
        selected_id = str(payload.get("selected_id") or "")
        self._target_options = [dict(item) for item in options if isinstance(item, dict)]
        self._updating_target_combo = True
        try:
            self._target_combo.clear()
            for option in self._target_options:
                self._target_combo.addItem(str(option.get("label") or option.get("name") or option.get("id") or "Avatar Target"), str(option.get("id") or ""))
            if self._target_combo.count() <= 0:
                self._target_combo.addItem("No Avatar Target", "none")
            index = self._target_combo.findData(selected_id)
            self._target_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._updating_target_combo = False
        selected = payload.get("selected") if isinstance(payload.get("selected"), dict) else {}
        self._target_status.setText(
            f"{selected.get('kind', 'none')} | "
            f"{'pose stream' if selected.get('pose_stream') else 'direct mapping' if selected.get('direct_key_baking') else 'not configured'}"
        )

    def _on_target_combo_changed(self, _index: int) -> None:
        if self._updating_target_combo:
            return
        editor = self._editor_ref
        if editor is None:
            return
        target_id = str(self._target_combo.currentData() or "").strip()
        if not target_id or target_id == "none":
            return
        try:
            from app.actions.editor_adapter import EditorAdapter

            EditorAdapter(editor).select_vtuber_avatar_target(target_id=target_id)
        except Exception:
            return
        self.update_from_editor(editor)

    def _avatar_context_from_editor(self, editor, *, target_payload: dict[str, object] | None = None) -> dict[str, object]:
        payload = target_payload or self._avatar_target_summary_from_editor(editor)
        selected_target = payload.get("selected") if isinstance(payload.get("selected"), dict) else {}
        selected_kind = str(selected_target.get("kind") or "")
        selected_id = str(selected_target.get("id") or "")
        if selected_kind == "vrm_vseeface_bridge":
            bridge_status = self._bridge_status_from_editor(editor)
            pose_stream = self._pose_stream_preview_from_editor(editor)
            path = str(selected_target.get("path") or "")
            return {
                "kind": "vrm",
                "name": str(selected_target.get("name") or (Path(path).name if path else "VRM / VSeeFace Bridge")),
                "clip": None,
                "path": path,
                "bridge_status": bridge_status,
                "pose_stream": pose_stream,
            }
        if selected_kind == "live2d_actor_clip":
            clip = self._live2d_clip_for_target_id(editor, selected_id)
            if clip is not None:
                model_path = str(getattr(clip, "model_path", "") or "")
                return {
                    "kind": "live2d",
                    "name": Path(model_path).name if model_path else str(selected_target.get("name") or "Live2D Actor"),
                    "clip": clip,
                    "path": model_path,
                }
        selected = None
        getter = getattr(editor, "_selected_live2d_clip_for_mapping", None)
        if callable(getter):
            selected = getter()
        if selected is not None:
            model_path = str(getattr(selected, "model_path", "") or "")
            return {
                "kind": "live2d",
                "name": Path(model_path).name if model_path else "Live2D Actor",
                "clip": selected,
                "path": model_path,
            }
        settings = getattr(editor, "_project_settings", {}) or {}
        bridge = settings.get("vseeface_bridge") if isinstance(settings, dict) else {}
        if isinstance(bridge, dict):
            avatar_vrm = str(bridge.get("avatar_vrm") or bridge.get("vrm") or "").strip()
            if avatar_vrm:
                return {
                    "kind": "vrm",
                    "name": Path(avatar_vrm).name,
                    "clip": None,
                    "path": avatar_vrm,
                }
        return {"kind": "none", "name": "Avatar", "clip": None, "path": ""}

    def _live2d_clip_for_target_id(self, editor, target_id: str):
        parts = str(target_id or "").split(":")
        if len(parts) != 3 or parts[0] != "live2d":
            return None
        try:
            track_index = int(parts[1])
            clip_index = int(parts[2])
            track = list(getattr(editor, "_live2d_actor_tracks", []) or [])[track_index]
            return list(getattr(track, "clips", []) or [])[clip_index]
        except Exception:
            return None

    def _bridge_status_from_editor(self, editor) -> dict[str, object]:
        try:
            from app.actions.editor_adapter import EditorAdapter

            payload = EditorAdapter(editor).vrm_bridge_status()
            return dict(payload.get("bridge") or {})
        except Exception as exc:
            return {"state": "unavailable", "capture": {"status": str(exc)}, "view": {"badge": {"text": "Unavailable"}}}

    def _pose_stream_preview_from_editor(self, editor) -> dict[str, object]:
        try:
            from app.actions.editor_adapter import EditorAdapter

            return EditorAdapter(editor).vrm_pose_stream_preview()
        except Exception as exc:
            return {"pose_stream": {"ready": False}, "warnings": [str(exc)]}

    def _populate_live_targets(self, editor) -> None:
        try:
            from app.broadcast_output import LiveTargetProfile, live_target_preset, live_target_presets

            settings = getattr(editor, "_project_settings", {}) or {}
            broadcast = settings.get("broadcast_output") if isinstance(settings, dict) else {}
            live_settings = broadcast.get("live_target") if isinstance(broadcast, dict) else {}
            profile = LiveTargetProfile.from_mapping(live_settings if isinstance(live_settings, dict) else {})
            preset = live_target_preset(profile.target_id)
            session_key = self._live_target_session_key(editor, profile.target_id)
            self._updating_live_target = True
            try:
                self._live_target_combo.clear()
                for row in live_target_presets():
                    label = str(row.get("label") or row.get("id") or "Live Target")
                    if row.get("experimental"):
                        label = f"{label} (Experimental)"
                    self._live_target_combo.addItem(label, str(row.get("id") or ""))
                index = self._live_target_combo.findData(profile.target_id)
                self._live_target_combo.setCurrentIndex(index if index >= 0 else 0)
                self._live_server_edit.setText(profile.server_url or preset.default_server_url)
                self._live_key_edit.setText(session_key)
                self._live_file_edit.setText(profile.output_path or "broadcast_output.mp4")
                self._live_bitrate_spin.setValue(int(profile.video_bitrate_kbps or preset.default_video_bitrate_kbps))
                self._live_retry_spin.setValue(int(getattr(profile, "max_retries", 3 if preset.output_kind == "rtmp" else 0) or 0))
                audio_index = self._live_audio_combo.findData(profile.audio_input.kind)
                self._live_audio_combo.setCurrentIndex(audio_index if audio_index >= 0 else 0)
                if profile.audio_input.kind in {"file", "project_audio_bus"}:
                    self._live_audio_source_edit.setText(profile.audio_input.file_path)
                else:
                    self._live_audio_source_edit.setText(profile.audio_input.device_name)
            finally:
                self._updating_live_target = False
            self._sync_live_target_fields()
            self._sync_live_audio_fields()
            self._update_live_target_status()
            self.update_live_session_status(self._live_session_status_from_editor(editor))
        except Exception as exc:
            self._live_status.setText(f"Live Target unavailable: {exc}")
            self._update_broadcast_evidence_status()

    def _on_live_target_combo_changed(self, _index: int) -> None:
        if self._updating_live_target:
            return
        try:
            from app.broadcast_output import live_target_preset

            target_id = str(self._live_target_combo.currentData() or "")
            preset = live_target_preset(target_id)
            self._updating_live_target = True
            try:
                self._live_server_edit.setText(preset.default_server_url)
                self._live_bitrate_spin.setValue(int(preset.default_video_bitrate_kbps))
                self._live_retry_spin.setValue(3 if preset.output_kind == "rtmp" else 0)
                if not self._live_file_edit.text().strip():
                    self._live_file_edit.setText("broadcast_output.mp4")
                editor = self._editor_ref
                self._live_key_edit.setText(self._live_target_session_key(editor, target_id) if editor is not None else "")
            finally:
                self._updating_live_target = False
        except Exception:
            pass
        self._sync_live_target_fields()
        self._persist_live_target_settings()
        self._update_live_target_status()

    def _on_live_audio_combo_changed(self, _index: int) -> None:
        if self._updating_live_target:
            return
        self._sync_live_audio_fields()
        self._persist_live_target_settings()
        self._update_live_target_status()

    def _sync_live_target_fields(self) -> None:
        try:
            from app.broadcast_output import OUTPUT_RECORDING, OUTPUT_RTMP, OUTPUT_WINDOW_SHARE, OUTPUT_VIRTUAL_CAMERA, live_target_preset

            preset = live_target_preset(str(self._live_target_combo.currentData() or ""))
            is_rtmp = preset.output_kind == OUTPUT_RTMP
            is_record = preset.output_kind == OUTPUT_RECORDING
            if is_record:
                self._live_start_btn.setText("Record MP4")
            elif preset.output_kind in {OUTPUT_WINDOW_SHARE, OUTPUT_VIRTUAL_CAMERA}:
                self._live_start_btn.setText("Prepare")
            else:
                self._live_start_btn.setText("Go Live")
        except Exception:
            is_rtmp = False
            is_record = False
            self._live_start_btn.setText("Go Live")
        for widget in (self._live_server_label, self._live_server_edit, self._live_key_label, self._live_key_edit):
            widget.setVisible(is_rtmp)
        for widget in (self._live_file_label, self._live_file_edit):
            widget.setVisible(is_record)
        for widget in (self._live_retry_label, self._live_retry_spin):
            widget.setVisible(is_rtmp)
        self._sync_live_audio_fields()

    def _sync_live_audio_fields(self) -> None:
        kind = str(self._live_audio_combo.currentData() or "none")
        needs_source = kind in {"dshow_device", "file"}
        self._live_audio_source_edit.setVisible(needs_source)
        if kind == "dshow_device":
            self._live_audio_source_edit.setPlaceholderText("DirectShow microphone device name")
        elif kind == "file":
            self._live_audio_source_edit.setPlaceholderText("Audio file path")
        elif kind == "project_audio_bus":
            self._live_audio_source_edit.setPlaceholderText("Project timeline audio will be rendered before start")

    def _live_target_payload_from_widgets(self, *, include_stream_key: bool = True) -> dict[str, object]:
        audio_kind = str(self._live_audio_combo.currentData() or "none")
        audio_source = self._live_audio_source_edit.text().strip()
        payload: dict[str, object] = {
            "target_id": str(self._live_target_combo.currentData() or ""),
            "server_url": self._live_server_edit.text().strip(),
            "output_path": self._live_file_edit.text().strip(),
            "video_bitrate_kbps": int(self._live_bitrate_spin.value()),
            "include_audio": audio_kind != "none",
            "audio_source_kind": audio_kind,
            "auto_reconnect": int(self._live_retry_spin.value()) > 0,
            "max_retries": int(self._live_retry_spin.value()),
        }
        if audio_kind == "dshow_device":
            payload["audio_device_name"] = audio_source
        elif audio_kind == "file":
            payload["audio_file"] = audio_source
        elif audio_kind == "project_audio_bus":
            payload["audio_file"] = ""
        if include_stream_key:
            payload["stream_key"] = self._live_key_edit.text().strip()
        return payload

    def _persist_live_target_settings(self) -> None:
        if self._updating_live_target:
            return
        editor = self._editor_ref
        if editor is None:
            return
        self._store_live_target_session_key()
        payload = self._live_target_payload_from_widgets(include_stream_key=False)
        try:
            from app.actions.editor_adapter import EditorAdapter

            EditorAdapter(editor).select_broadcast_live_target(**payload)
        except Exception:
            try:
                from app.broadcast_output import LiveTargetProfile

                settings = dict(getattr(editor, "_project_settings", {}) or {})
                broadcast = dict(settings.get("broadcast_output") if isinstance(settings.get("broadcast_output"), dict) else {})
                broadcast["live_target"] = LiveTargetProfile.from_mapping(payload).to_project_settings()
                settings["broadcast_output"] = broadcast
                editor._project_settings = settings
                player = getattr(editor, "_player", None)
                if player is not None and hasattr(player, "set_project_settings"):
                    player.set_project_settings(settings)
            except Exception:
                return

    def _store_live_target_session_key(self) -> None:
        editor = self._editor_ref
        if editor is None or self._updating_live_target:
            return
        target_id = str(self._live_target_combo.currentData() or "")
        if not target_id:
            return
        keys = getattr(editor, "_broadcast_live_target_session_keys", None)
        if not isinstance(keys, dict):
            keys = {}
            setattr(editor, "_broadcast_live_target_session_keys", keys)
        keys[target_id] = self._live_key_edit.text().strip()
        self._update_live_target_status()

    def _live_target_session_key(self, editor, target_id: str) -> str:
        keys = getattr(editor, "_broadcast_live_target_session_keys", None) if editor is not None else None
        if isinstance(keys, dict):
            return str(keys.get(str(target_id or "")) or "")
        return ""

    def _on_live_target_preflight(self) -> None:
        self._persist_live_target_settings()
        editor = self._editor_ref
        if editor is None:
            return
        payload = self._live_target_payload_from_widgets(include_stream_key=True)
        try:
            from app.actions.editor_adapter import EditorAdapter

            diag = EditorAdapter(editor).broadcast_live_target_summary(
                **payload,
                width=self._program_canvas_width(editor),
                height=self._program_canvas_height(editor),
                fps=self._program_canvas_fps(editor),
            ).get("preflight", {})
        except Exception as exc:
            self._live_status.setText(f"Check failed: {exc}")
            return
        self._set_live_target_preflight_status(diag if isinstance(diag, dict) else {})

    def _on_live_target_start(self) -> None:
        self._persist_live_target_settings()
        self.start_live_target_requested.emit(self._live_target_payload_from_widgets(include_stream_key=True))

    def _update_live_target_status(self) -> None:
        try:
            from app.broadcast_output import OUTPUT_RECORDING, OUTPUT_RTMP, live_target_preset

            preset = live_target_preset(str(self._live_target_combo.currentData() or ""))
            if preset.output_kind == OUTPUT_RECORDING:
                self._live_status.setText(f"Ready to write Local MP4 from Program Output to {self._live_file_edit.text().strip() or 'broadcast_output.mp4'}.")
            elif preset.output_kind == OUTPUT_RTMP:
                key_state = "key entered for this session" if self._live_key_edit.text().strip() else "stream key needed"
                audio_kind = str(self._live_audio_combo.currentData() or "none")
                audio_names = {
                    "none": "audio off",
                    "silence": "silent stereo",
                    "project_audio_bus": "project audio bus",
                    "dshow_device": "microphone/device",
                    "file": "audio file",
                }
                audio_state = audio_names.get(audio_kind, f"audio {audio_kind}")
                suffix = " Vertical preset recommended." if int(preset.default_height) > int(preset.default_width) else ""
                retry_state = f"retries {int(self._live_retry_spin.value())}"
                self._live_status.setText(f"{preset.label}: {key_state}, {audio_state}, {retry_state}. Program Output only; Performance Source stays hidden.{suffix}")
            else:
                self._live_status.setText(f"{preset.label}: share the Program Output window or use an installed virtual-camera backend. No stream key is saved.")
        except Exception:
            self._live_status.setText("Select a Live Target and run Check before going live.")

    def _set_live_target_preflight_status(self, diag: dict[str, object]) -> None:
        target = diag.get("target") if isinstance(diag.get("target"), dict) else {}
        label = str(target.get("label") or "Live Target")
        ok = bool(diag.get("ok"))
        errors = [str(item) for item in (diag.get("errors") or []) if str(item)]
        warnings = [str(item) for item in (diag.get("warnings") or []) if str(item)]
        if ok:
            command_state = "FFmpeg command ready" if diag.get("command") else "No FFmpeg command needed"
            text = f"{label}: ready. {command_state}."
            if warnings:
                text += f"\nWarning: {warnings[0]}"
        else:
            text = f"{label}: not ready."
            if errors:
                text += f"\n{errors[0]}"
        self._live_status.setText(text)

    def update_live_session_status(self, status: dict[str, object] | None) -> None:
        data = dict(status or {})
        state = str(data.get("state") or "idle")
        active = bool(data.get("active"))
        self._live_start_btn.setEnabled(not active)
        self._live_stop_btn.setEnabled(active)
        if state == "running":
            health = str(data.get("health") or "ok")
            retry_count = int(data.get("retry_count") or 0)
            retry_text = f"  Retries: {retry_count}" if retry_count > 0 else ""
            self._live_status.setText(
                f"Live Target running ({health}). "
                f"Frames: {int(data.get('frames_written') or 0)}  "
                f"FPS: {float(data.get('estimated_fps') or 0.0):.1f}  "
                f"Backpressure: {int(data.get('backpressure_count') or 0)}"
                f"{retry_text}"
            )
        elif state == "reconnecting":
            self._live_status.setText(
                "Live Target reconnecting. "
                f"Retries: {int(data.get('retry_count') or 0)}/{int(data.get('max_retries') or 0)}"
            )
        elif state == "preparing_audio":
            self._live_start_btn.setEnabled(False)
            self._live_stop_btn.setEnabled(True)
            if "audio_mixdown_progress" in data:
                self._live_status.setText(
                    f"Preparing project audio bus for Live Target... {float(data.get('audio_mixdown_progress') or 0.0):.0f}%"
                )
            else:
                self._live_status.setText("Preparing project audio bus for Live Target...")
        elif state == "manual_output":
            self._live_status.setText("Manual output ready. Share the Program Output window or virtual camera.")
        elif state == "error":
            action = str(data.get("recovery_action") or "")
            kind = str(data.get("platform_error_kind") or "")
            suffix_parts = [part for part in (kind, action) if part]
            suffix = f" ({' / '.join(suffix_parts)})" if suffix_parts else ""
            troubleshooting = data.get("troubleshooting") if isinstance(data.get("troubleshooting"), dict) else {}
            checks = troubleshooting.get("checks") if isinstance(troubleshooting.get("checks"), list) else []
            next_step = f"\nNext: {checks[0]}" if checks else ""
            self._live_status.setText(f"Live Target error: {data.get('last_error') or 'unknown error'}{suffix}{next_step}")

    def _update_broadcast_evidence_status(self) -> None:
        try:
            from app.broadcast_platform_e2e import build_broadcast_platform_evidence_checklist

            checklist = build_broadcast_platform_evidence_checklist(".")
            self._evidence_body.setText("\n".join(broadcast_evidence_status_lines(checklist)))
        except Exception as exc:
            self._evidence_body.setText(f"Broadcast evidence checklist unavailable: {exc}")

    def _open_broadcast_evidence_register_dialog(self, check_id: str) -> None:
        check_id = str(check_id or "").strip()
        defaults = broadcast_evidence_register_defaults(check_id)
        dialog = QDialog(self)
        dialog.setWindowTitle(str(defaults.get("title") or "Register Broadcast Evidence"))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        label = QLabel(str(defaults.get("description") or ""), dialog)
        label.setWordWrap(True)
        layout.addWidget(label)

        platform_label = QLabel("Platform", dialog)
        platform_label.setObjectName("StudioTargetLabel")
        platform_edit = QLineEdit(dialog)
        platform_edit.setObjectName("StudioTargetField")
        platform_edit.setText(str(defaults.get("platform") or ""))
        layout.addWidget(platform_label)
        layout.addWidget(platform_edit)

        evidence_label = QLabel("Evidence path", dialog)
        evidence_label.setObjectName("StudioTargetLabel")
        evidence_edit = QLineEdit(dialog)
        evidence_edit.setObjectName("StudioTargetField")
        evidence_edit.setPlaceholderText(str(defaults.get("evidence_placeholder") or ""))
        layout.addWidget(evidence_label)
        layout.addWidget(evidence_edit)

        notes_label = QLabel("Redacted notes", dialog)
        notes_label.setObjectName("StudioTargetLabel")
        notes_edit = QPlainTextEdit(dialog)
        notes_edit.setPlaceholderText(str(defaults.get("notes_placeholder") or ""))
        notes_edit.setMinimumHeight(88)
        layout.addWidget(notes_label)
        layout.addWidget(notes_edit)

        from PySide6.QtWidgets import QCheckBox

        confirm = QCheckBox(str(defaults.get("confirm_label") or ""), dialog)
        layout.addWidget(confirm)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText("Register")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = build_broadcast_evidence_registration_payload(
            check_id=check_id,
            platform=platform_edit.text(),
            evidence_path=evidence_edit.text(),
            notes=notes_edit.toPlainText(),
            confirm_redacted=bool(confirm.isChecked()),
        )
        try:
            result = self._register_broadcast_evidence_payload(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Broadcast evidence", str(exc))
            self._evidence_body.setText(f"Evidence registration failed: {exc}")
            return
        QMessageBox.information(self, "Broadcast evidence", f"Evidence registered: {result.get('check_id') or check_id}")

    def _register_broadcast_evidence_payload(self, payload: dict[str, object]) -> dict[str, object]:
        data = dict(payload or {})
        editor = self._editor_ref
        if editor is not None:
            from app.actions.editor_adapter import EditorAdapter

            result = EditorAdapter(editor).register_broadcast_platform_evidence(**data)
        else:
            from app.broadcast_platform_e2e import register_manual_platform_evidence

            root = str(data.pop("root", ".") or ".")
            result = register_manual_platform_evidence(root, **data)
        self._update_broadcast_evidence_status()
        return dict(result)

    def _live_session_status_from_editor(self, editor) -> dict[str, object]:
        getter = getattr(editor, "_broadcast_output_session_status", None)
        if callable(getter):
            try:
                return dict(getter())
            except Exception:
                return {}
        return {}

    def _program_canvas_width(self, editor) -> int:
        value = getattr(editor, "_export_resolution", None)
        if isinstance(value, tuple) and value:
            return int(value[0])
        return 1920

    def _program_canvas_height(self, editor) -> int:
        value = getattr(editor, "_export_resolution", None)
        if isinstance(value, tuple) and len(value) > 1:
            return int(value[1])
        return 1080

    def _program_canvas_fps(self, editor) -> float:
        try:
            return float(getattr(editor, "_export_fps", 30.0) or 30.0)
        except Exception:
            return 30.0

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)

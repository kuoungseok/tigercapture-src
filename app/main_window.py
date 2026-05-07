from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.modes import MODE_ICONS, CaptureMode, mode_label
from app.paths import default_save_dir, open_in_explorer
from app.shortcuts import DEFAULT_SHORTCUTS
from app.style import APP_QSS

DELAY_SECONDS = [0, 3, 5, 10]


class MainWindow(QMainWindow):
    new_capture_requested = Signal(CaptureMode, int, bool)
    open_folder_requested = Signal()
    open_settings_requested = Signal()
    # Each "open editor" signal carries a Path (the dropped file)
    # when the editor should preload one, or None when the entry
    # point was the button / shortcut and the controller picks the
    # file itself.
    open_video_editor_requested = Signal(object)
    open_gif_file_requested = Signal(object)
    open_sound_editor_requested = Signal(object)
    open_donation_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(tr("app.name"))
        # Compact capture-tool look (ShareX / ScreenToGif vibe). The
        # Pro Editor section + drop-area features mean we still need
        # decent width, but height stays tight since everything not
        # capture-related is collapsed by default.
        self.resize(380, 300)
        self.setStyleSheet(APP_QSS)
        # Drop audio files anywhere on the main window → open Sound Editor.
        self.setAcceptDrops(True)

        self._current_mode: CaptureMode = CaptureMode.SCREENSHOT

        self.open_folder_requested.connect(self._default_open_folder)

        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(10)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_new_capture_button())
        root.addWidget(self._build_mode_section())
        root.addWidget(self._build_options_section())
        root.addWidget(self._build_pro_editor_section())
        root.addStretch(1)
        root.addWidget(self._build_credit_footer())

        self._install_shortcuts()

    def _install_shortcuts(self) -> None:
        handlers = {
            "new_capture": self._on_new_capture_clicked,
            "mode_screenshot": lambda: self._select_mode(CaptureMode.SCREENSHOT),
            "mode_gif": lambda: self._select_mode(CaptureMode.GIF),
            "mode_video": lambda: self._select_mode(CaptureMode.VIDEO),
            "open_folder": self.open_folder_requested.emit,
            "settings": self.open_settings_requested.emit,
        }
        for sc in DEFAULT_SHORTCUTS:
            handler = handlers.get(sc.id)
            if handler is None:
                continue
            shortcut = QShortcut(QKeySequence(sc.key), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(handler)

    def _select_mode(self, mode: CaptureMode) -> None:
        self._current_mode = mode
        for m, btn in self._mode_buttons:
            btn.setChecked(m is mode)

    def _build_top_bar(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._title_label = QLabel(tr("app.name"))
        self._title_label.setObjectName("AppTitle")
        layout.addWidget(self._title_label)
        layout.addStretch(1)

        self.donate_btn = QPushButton(tr("main.donate.button"))
        self.donate_btn.setObjectName("DonateButton")
        self.donate_btn.setToolTip(tr("main.tooltip.donate"))
        self.donate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.donate_btn.clicked.connect(self.open_donation_requested.emit)
        layout.addWidget(self.donate_btn)

        self.open_folder_btn = QPushButton("📁")
        self.open_folder_btn.setObjectName("IconButton")
        self.open_folder_btn.setToolTip(tr("main.tooltip.open_folder"))
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self.open_folder_requested.emit)
        layout.addWidget(self.open_folder_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("IconButton")
        self.settings_btn.setToolTip(tr("main.tooltip.settings"))
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings_requested.emit)
        layout.addWidget(self.settings_btn)

        return container

    def _default_open_folder(self) -> None:
        open_in_explorer(default_save_dir())

    def _build_credit_footer(self) -> QWidget:
        self._credit_label = QLabel(tr("app.credit"))
        self._credit_label.setObjectName("CreditFooter")
        self._credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return self._credit_label

    def _build_new_capture_button(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.new_capture_btn = QPushButton(tr("main.new_capture"))
        self.new_capture_btn.setObjectName("NewCaptureButton")
        self.new_capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_capture_btn.setMinimumHeight(38)
        self.new_capture_btn.clicked.connect(self._on_new_capture_clicked)

        layout.addWidget(self.new_capture_btn, stretch=1)
        return container

    def _build_mode_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._mode_section_label = QLabel(tr("main.section.mode"))
        self._mode_section_label.setObjectName("SectionLabel")
        layout.addWidget(self._mode_section_label)

        buttons_row = QWidget()
        row_layout = QHBoxLayout(buttons_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons: list[tuple[CaptureMode, QPushButton]] = []

        for mode in (CaptureMode.SCREENSHOT, CaptureMode.GIF, CaptureMode.VIDEO):
            btn = QPushButton(f"{MODE_ICONS[mode]}  {mode_label(mode)}")
            btn.setCheckable(True)
            btn.setProperty("modeButton", True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(32)
            if mode is self._current_mode:
                btn.setChecked(True)
            btn.clicked.connect(lambda _checked, m=mode: self._on_mode_selected(m))
            if mode is CaptureMode.GIF:
                # Double-click the GIF mode button to open an existing GIF
                # directly in the editor (no new recording).
                btn.setToolTip(
                    f"{mode_label(mode)}  —  {tr('main.mode.gif.dblclick_hint')}"
                )
                btn.installEventFilter(self)
                self._gif_mode_btn = btn
            self._mode_group.addButton(btn)
            row_layout.addWidget(btn, stretch=1)
            self._mode_buttons.append((mode, btn))

        layout.addWidget(buttons_row)
        return container

    def _build_options_section(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.delay_combo = QComboBox()
        for seconds in DELAY_SECONDS:
            label = (
                tr("main.delay.none")
                if seconds == 0
                else tr("main.delay.seconds", seconds=seconds)
            )
            self.delay_combo.addItem(label, userData=seconds)

        self.cursor_check = QCheckBox(tr("main.option.include_cursor"))
        self.cursor_check.setChecked(True)

        self._timer_label = QLabel(tr("main.option.timer"))
        layout.addWidget(self._timer_label)
        layout.addWidget(self.delay_combo)
        layout.addSpacing(8)
        layout.addWidget(self.cursor_check)
        layout.addStretch(1)

        return container

    def _build_pro_editor_section(self) -> QWidget:
        """Collapsible Pro Editor section. Starts collapsed so the
        first dialog stays focused on capture-related controls.
        Click the toggle header to expand the Media Editor + Sound
        Editor buttons. Power users still have one click to the
        editors after the first expansion (the toggle state isn't
        persisted yet — that's a settings follow-up)."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._pro_editor_section_label = tr("main.section.pro_editor")
        self._pro_editor_toggle = QPushButton(
            f"▶  {self._pro_editor_section_label}"
        )
        self._pro_editor_toggle.setObjectName("CollapsibleHeader")
        self._pro_editor_toggle.setCheckable(True)
        self._pro_editor_toggle.setChecked(False)
        self._pro_editor_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pro_editor_toggle.setStyleSheet(
            "QPushButton#CollapsibleHeader { "
            "  text-align: left; padding: 6px 8px; "
            "  background: transparent; border: none; "
            "  color: #b0b0b0; font-size: 12px; font-weight: 600; "
            "  letter-spacing: 0.5px; }"
            "QPushButton#CollapsibleHeader:hover { color: #ffffff; }"
        )
        self._pro_editor_toggle.toggled.connect(self._on_pro_editor_toggled)
        layout.addWidget(self._pro_editor_toggle)

        self._pro_editor_content = QWidget()
        pe_layout = QVBoxLayout(self._pro_editor_content)
        pe_layout.setContentsMargins(0, 0, 0, 0)
        pe_layout.setSpacing(6)

        self.pro_editor_btn = QPushButton(tr("main.pro_editor.button"))
        self.pro_editor_btn.setObjectName("ProEditorButton")
        self.pro_editor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pro_editor_btn.setMinimumHeight(34)
        self.pro_editor_btn.clicked.connect(
            lambda: self.open_video_editor_requested.emit(None)
        )
        pe_layout.addWidget(self.pro_editor_btn)

        # Sound Editor: standalone entry point to the per-clip sound
        # editor (EQ / Dynamics / AI Master / Export to FLAC-ALAC-MP3-
        # WAV). Lives next to the video editor so users discover it.
        self.sound_editor_btn = QPushButton(tr("main.sound_editor.button"))
        self.sound_editor_btn.setObjectName("SoundEditorButton")
        self.sound_editor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sound_editor_btn.setMinimumHeight(34)
        self.sound_editor_btn.setToolTip(tr("main.sound_editor.tooltip"))
        self.sound_editor_btn.clicked.connect(
            lambda: self.open_sound_editor_requested.emit(None)
        )
        pe_layout.addWidget(self.sound_editor_btn)

        self._pro_editor_content.hide()  # start collapsed
        layout.addWidget(self._pro_editor_content)
        return container

    def _on_pro_editor_toggled(self, checked: bool) -> None:
        self._pro_editor_content.setVisible(checked)
        arrow = "▼" if checked else "▶"
        self._pro_editor_toggle.setText(
            f"{arrow}  {self._pro_editor_section_label}"
        )

    def retranslate(self) -> None:
        """Reapply all translated strings without recreating the window."""
        self.setWindowTitle(tr("app.name"))
        self._title_label.setText(tr("app.name"))
        self._credit_label.setText(tr("app.credit"))
        self.open_folder_btn.setToolTip(tr("main.tooltip.open_folder"))
        self.settings_btn.setToolTip(tr("main.tooltip.settings"))
        self.donate_btn.setToolTip(tr("main.tooltip.donate"))
        self.donate_btn.setText(tr("main.donate.button"))
        self._pro_editor_section_label = tr("main.section.pro_editor")
        arrow = "▼" if self._pro_editor_toggle.isChecked() else "▶"
        self._pro_editor_toggle.setText(
            f"{arrow}  {self._pro_editor_section_label}"
        )
        self.pro_editor_btn.setText(tr("main.pro_editor.button"))
        self.sound_editor_btn.setText(tr("main.sound_editor.button"))
        self.sound_editor_btn.setToolTip(tr("main.sound_editor.tooltip"))
        self.new_capture_btn.setText(tr("main.new_capture"))
        self._mode_section_label.setText(tr("main.section.mode"))
        self._timer_label.setText(tr("main.option.timer"))
        self.cursor_check.setText(tr("main.option.include_cursor"))

        for mode, btn in self._mode_buttons:
            btn.setText(f"{MODE_ICONS[mode]}  {mode_label(mode)}")

        for i, seconds in enumerate(DELAY_SECONDS):
            label = (
                tr("main.delay.none")
                if seconds == 0
                else tr("main.delay.seconds", seconds=seconds)
            )
            self.delay_combo.setItemText(i, label)

    def refresh_recent(self) -> None:
        # Recent Captures strip was removed — kept as a no-op so any
        # external caller (controller) doesn't break.
        return

    def _on_mode_selected(self, mode: CaptureMode) -> None:
        self._current_mode = mode

    def eventFilter(self, obj, event):
        # Double-click the GIF mode button → shortcut to open an existing GIF
        # in the editor, skipping the record flow.
        if getattr(self, "_gif_mode_btn", None) is obj and event.type() == event.Type.MouseButtonDblClick:
            self.open_gif_file_requested.emit(None)
            return True
        return super().eventFilter(obj, event)

    # ---- drag-and-drop: route by file type ----
    _AUDIO_DROP_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp2", ".wma"}
    _VIDEO_DROP_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv"}
    _GIF_DROP_EXTS = {".gif"}

    def _classify_drop(self, urls) -> "tuple[str, Path] | None":
        """Return ``(kind, path)`` for the first routable file among the
        dropped URLs. ``kind`` is one of ``"audio" / "video" / "gif"``.
        Returns ``None`` when nothing matches a supported extension."""
        from pathlib import Path
        for u in urls:
            if not u.isLocalFile():
                continue
            p = Path(u.toLocalFile())
            ext = p.suffix.lower()
            if ext in self._GIF_DROP_EXTS:
                return ("gif", p)
            if ext in self._VIDEO_DROP_EXTS:
                return ("video", p)
            if ext in self._AUDIO_DROP_EXTS:
                return ("audio", p)
        return None

    def dragEnterEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasUrls() and self._classify_drop(md.urls()) is not None:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasUrls() and self._classify_drop(md.urls()) is not None:
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasUrls():
            routed = self._classify_drop(md.urls())
            if routed is not None:
                kind, path = routed
                if kind == "audio":
                    self.open_sound_editor_requested.emit(path)
                elif kind == "video":
                    self.open_video_editor_requested.emit(path)
                elif kind == "gif":
                    self.open_gif_file_requested.emit(path)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def _on_new_capture_clicked(self) -> None:
        delay_seconds = int(self.delay_combo.currentData() or 0)
        include_cursor = self.cursor_check.isChecked()
        self.new_capture_requested.emit(self._current_mode, delay_seconds, include_cursor)

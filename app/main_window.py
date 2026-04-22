from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
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
from app.widgets.recent_strip import RecentStrip


DELAY_SECONDS = [0, 3, 5, 10]


class MainWindow(QMainWindow):
    new_capture_requested = Signal(CaptureMode, int, bool)
    open_folder_requested = Signal()
    open_settings_requested = Signal()
    open_video_editor_requested = Signal()
    open_donation_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(tr("app.name"))
        self.resize(520, 520)
        self.setStyleSheet(APP_QSS)

        self._current_mode: CaptureMode = CaptureMode.SCREENSHOT

        self.open_folder_requested.connect(self._default_open_folder)

        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(16)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_new_capture_button())
        root.addWidget(self._build_mode_section())
        root.addWidget(self._build_options_section())
        root.addWidget(self._build_pro_editor_section())
        root.addWidget(self._build_divider())
        root.addWidget(self._build_recent_section(), stretch=1)
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
        self.new_capture_btn.setMinimumHeight(48)
        self.new_capture_btn.clicked.connect(self._on_new_capture_clicked)

        layout.addWidget(self.new_capture_btn, stretch=1)
        return container

    def _build_mode_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._mode_section_label = QLabel(tr("main.section.mode"))
        self._mode_section_label.setObjectName("SectionLabel")
        layout.addWidget(self._mode_section_label)

        buttons_row = QWidget()
        row_layout = QHBoxLayout(buttons_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons: list[tuple[CaptureMode, QPushButton]] = []

        for mode in (CaptureMode.SCREENSHOT, CaptureMode.GIF, CaptureMode.VIDEO):
            btn = QPushButton(f"{MODE_ICONS[mode]}  {mode_label(mode)}")
            btn.setCheckable(True)
            btn.setProperty("modeButton", True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(40)
            if mode is self._current_mode:
                btn.setChecked(True)
            btn.clicked.connect(lambda _checked, m=mode: self._on_mode_selected(m))
            self._mode_group.addButton(btn)
            row_layout.addWidget(btn, stretch=1)
            self._mode_buttons.append((mode, btn))

        layout.addWidget(buttons_row)
        return container

    def _build_options_section(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

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
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._pro_editor_section_label = QLabel(tr("main.section.pro_editor"))
        self._pro_editor_section_label.setObjectName("SectionLabel")
        layout.addWidget(self._pro_editor_section_label)

        self.pro_editor_btn = QPushButton(tr("main.pro_editor.button"))
        self.pro_editor_btn.setObjectName("ToolButton")
        self.pro_editor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pro_editor_btn.setMinimumHeight(40)
        self.pro_editor_btn.clicked.connect(self.open_video_editor_requested.emit)
        layout.addWidget(self.pro_editor_btn)

        return container

    def _build_divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("Divider")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _build_recent_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._recent_section_label = QLabel(tr("main.section.recent"))
        self._recent_section_label.setObjectName("SectionLabel")
        layout.addWidget(self._recent_section_label)

        self.recent_strip = RecentStrip()
        self.recent_strip.item_activated.connect(self._on_recent_activated)
        layout.addWidget(self.recent_strip)

        return container

    def retranslate(self) -> None:
        """Reapply all translated strings without recreating the window."""
        self.setWindowTitle(tr("app.name"))
        self._title_label.setText(tr("app.name"))
        self._credit_label.setText(tr("app.credit"))
        self.open_folder_btn.setToolTip(tr("main.tooltip.open_folder"))
        self.settings_btn.setToolTip(tr("main.tooltip.settings"))
        self.donate_btn.setToolTip(tr("main.tooltip.donate"))
        self.donate_btn.setText(tr("main.donate.button"))
        self._pro_editor_section_label.setText(tr("main.section.pro_editor"))
        self.pro_editor_btn.setText(tr("main.pro_editor.button"))
        self.new_capture_btn.setText(tr("main.new_capture"))
        self._mode_section_label.setText(tr("main.section.mode"))
        self._recent_section_label.setText(tr("main.section.recent"))
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

        self.refresh_recent()

    def _on_recent_activated(self, path) -> None:
        open_in_explorer(path)

    def refresh_recent(self) -> None:
        self.recent_strip.refresh(default_save_dir())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_recent()

    def _on_mode_selected(self, mode: CaptureMode) -> None:
        self._current_mode = mode

    def _on_new_capture_clicked(self) -> None:
        delay_seconds = int(self.delay_combo.currentData() or 0)
        include_cursor = self.cursor_check.isChecked()
        self.new_capture_requested.emit(self._current_mode, delay_seconds, include_cursor)

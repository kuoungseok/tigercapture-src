import json
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, Signal, Property
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.i18n import current_language, tr
from app.icons import app_icon, icon_size
from app.launcher_studio_policy import capture_to_studio_enabled
from app.modes import CaptureMode, mode_label
from app.paths import default_save_dir, open_in_explorer, runtime_data_dir
from app.recent_captures import format_size, list_recent
from app.shortcuts import DEFAULT_SHORTCUTS
from app.style import APP_QSS

DELAY_SECONDS = [0, 3, 5, 10]


class LauncherWorkspaceToggle(QPushButton):
    """Compact iOS-style Normal/Simple workspace switch for the launcher."""

    def __init__(self, standard_label: str, simple_label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._standard_label = standard_label
        self._simple_label = simple_label
        self._knob_progress = 0.0
        self._press_x = 0.0
        self._dragging = False
        self._drag_start_progress = 0.0
        self._animation = QPropertyAnimation(self, b"knobProgress", self)
        self._animation.setDuration(165)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setObjectName("LauncherWorkspaceToggle")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(136, 34)
        self.setText("")

    def set_labels(self, standard_label: str, simple_label: str) -> None:
        self._standard_label = str(standard_label or "Normal")
        self._simple_label = str(simple_label or "Simple")
        self.update()

    def _get_knob_progress(self) -> float:
        return float(self._knob_progress)

    def _set_knob_progress(self, value: float) -> None:
        self._knob_progress = max(0.0, min(1.0, float(value)))
        self.update()

    knobProgress = Property(float, _get_knob_progress, _set_knob_progress)

    @staticmethod
    def _event_x(event) -> float:
        try:
            return float(event.position().x())
        except Exception:
            try:
                return float(event.pos().x())
            except Exception:
                return 0.0

    @staticmethod
    def _mix(a: QColor, b: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, float(t)))
        return QColor(
            int(round(a.red() * (1.0 - t) + b.red() * t)),
            int(round(a.green() * (1.0 - t) + b.green() * t)),
            int(round(a.blue() * (1.0 - t) + b.blue() * t)),
            int(round(a.alpha() * (1.0 - t) + b.alpha() * t)),
        )

    def _animate_knob(self, checked: bool) -> None:
        target = 1.0 if checked else 0.0
        if self._dragging:
            self._set_knob_progress(target)
            return
        self._animation.stop()
        self._animation.setStartValue(float(self._knob_progress))
        self._animation.setEndValue(target)
        self._animation.start()

    def setChecked(self, checked: bool) -> None:  # type: ignore[override]
        super().setChecked(bool(checked))
        self._animate_knob(bool(checked))

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._animation.stop()
        self._press_x = self._event_x(event)
        self._drag_start_progress = float(self._knob_progress)
        self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if not bool(event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        x = self._event_x(event)
        delta = x - self._press_x
        if abs(delta) >= 3.0:
            self._dragging = True
        if self._dragging:
            travel = max(1.0, (self.width() - 8.0) / 2.0)
            self._set_knob_progress(self._drag_start_progress + delta / travel)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging:
            self._dragging = False
            self.setChecked(float(self._knob_progress) >= 0.5)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        checked = self.isChecked()
        progress = float(self._knob_progress)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        track_color = self._mix(QColor("#171D2F"), QColor("#31D66E"), progress)
        border_color = self._mix(QColor("#3B4563"), QColor("#9AF4B7"), progress)
        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(track_color)
        painter.drawRoundedRect(rect, rect.height() / 2.0, rect.height() / 2.0)

        knob_w = (rect.width() - 8.0) / 2.0
        knob_h = rect.height() - 8.0
        knob_left = rect.left() + 4.0
        knob_right = rect.right() - 4.0 - knob_w
        knob_x = knob_left * (1.0 - progress) + knob_right * progress
        knob = QRectF(knob_x, rect.top() + 4.0, knob_w, knob_h)
        painter.setPen(QPen(QColor(0, 0, 0, 42), 1.0))
        painter.setBrush(QColor("#F7FAFF"))
        painter.drawRoundedRect(knob, knob_h / 2.0, knob_h / 2.0)

        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        left_rect = QRectF(rect.left() + 4.0, rect.top() + 4.0, knob_w, knob_h)
        right_rect = QRectF(rect.right() - 4.0 - knob_w, rect.top() + 4.0, knob_w, knob_h)
        painter.setPen(QColor("#1D2536") if not checked else QColor("#FFFFFF"))
        painter.drawText(left_rect, Qt.AlignmentFlag.AlignCenter, self._standard_label)
        painter.setPen(QColor("#FFFFFF") if not checked else QColor("#123821"))
        painter.drawText(right_rect, Qt.AlignmentFlag.AlignCenter, self._simple_label)


class MainWindow(QMainWindow):
    new_capture_requested = Signal(CaptureMode, int, bool)
    open_folder_requested = Signal()
    open_settings_requested = Signal()
    # Each "open editor" signal may carry a Path/None for legacy call
    # sites, or a dict with source_path + workspace_mode from the launcher.
    open_video_editor_requested = Signal(object)
    open_project_requested = Signal(object)
    open_template_requested = Signal(object)
    open_gif_file_requested = Signal(object)
    open_sound_editor_requested = Signal(object)
    open_donation_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        try:
            from app.font_fallback import apply_ui_font
            apply_ui_font()
        except Exception:
            pass
        self.setWindowTitle(tr("app.name"))
        # Keep the launcher as an action picker.  The full editing
        # personality belongs in the editor; startup should stay calm.
        self.resize(760, 620)
        self.setMinimumSize(620, 560)
        self.setStyleSheet(APP_QSS)
        # Drop audio files anywhere on the main window → open Sound Editor.
        self.setAcceptDrops(True)

        self._current_mode: CaptureMode = CaptureMode.SCREENSHOT
        self._delay_seconds = 0
        self._launcher_workspace_state_ready = False

        self.open_folder_requested.connect(self._default_open_folder)

        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 10)
        root.setSpacing(8)

        root.addWidget(self._build_top_bar())
        self._launcher_scroll = QScrollArea()
        self._launcher_scroll.setObjectName("LauncherScroll")
        self._launcher_scroll.setWidgetResizable(True)
        self._launcher_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._launcher_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._launcher_body = QWidget()
        self._launcher_body.setObjectName("LauncherScrollContent")
        self._launcher_scroll.setWidget(self._launcher_body)
        body = QVBoxLayout(self._launcher_body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)
        body.addWidget(self._build_hero_panel())
        body.addWidget(self._build_startup_busy())
        body.addWidget(self._build_pro_editor_section())
        body.addWidget(self._build_capture_settings_section())
        body.addWidget(self._build_drop_zone())
        body.addStretch(1)
        body.addWidget(self._build_credit_footer())
        root.addWidget(self._launcher_scroll, stretch=1)

        self._install_shortcuts()
        self._apply_launcher_microcopy()

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
        layout.setSpacing(8)

        self._brand_label = QLabel("TigerCapture")
        self._brand_label.setObjectName("LauncherBrand")
        layout.addWidget(self._brand_label)
        layout.addStretch(1)

        self.donate_btn = QPushButton(tr("main.donate.button"))
        self.donate_btn.setObjectName("DonateButton")
        self.donate_btn.setToolTip(tr("main.tooltip.donate"))
        self.donate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.donate_btn.clicked.connect(self.open_donation_requested.emit)
        layout.addWidget(self.donate_btn)

        self.open_folder_btn = QPushButton("")
        self.open_folder_btn.setObjectName("IconButton")
        self.open_folder_btn.setIcon(app_icon("project", size=16))
        self.open_folder_btn.setIconSize(icon_size(16))
        self.open_folder_btn.setToolTip(tr("main.tooltip.open_folder"))
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self.open_folder_requested.emit)
        layout.addWidget(self.open_folder_btn)

        self.settings_btn = QPushButton("")
        self.settings_btn.setObjectName("IconButton")
        self.settings_btn.setIcon(app_icon("settings", size=16))
        self.settings_btn.setIconSize(icon_size(16))
        self.settings_btn.setToolTip(tr("main.tooltip.settings"))
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings_requested.emit)
        layout.addWidget(self.settings_btn)

        return container

    @staticmethod
    def _copy(ko: str, en: str) -> str:
        return ko if current_language() == "ko" else en

    @staticmethod
    def _studio_entry_enabled() -> bool:
        return capture_to_studio_enabled()

    def _new_capture_text(self) -> str:
        return self._copy("녹화 시작", "Start recording")

    def _timer_text(self) -> str:
        return self._copy("타이머", "Timer")

    def _video_editor_text(self) -> str:
        return self._copy("타이거 스튜디오", "Tiger Studio")

    def _sound_editor_text(self) -> str:
        return self._copy("오디오 정리", "Clean audio")

    def _continue_title_text(self) -> str:
        return self._copy("최근 작업", "Continue")

    def _template_title_text(self) -> str:
        return self._copy("추천 시작", "Suggested start")

    def _quick_start_title_text(self) -> str:
        if not self._studio_entry_enabled():
            return self._copy("가벼운 캡처", "Light Capture")
        return self._copy("스튜디오 진입", "Open Studio")

    def _record_card_text(self) -> str:
        return self._copy("녹화\n커서 + 자동 줌", "Record\nCursor + Zoom")

    def _edit_card_text(self) -> str:
        return self._copy("타이거 스튜디오\n미디어풀 열기", "Tiger Studio\nMedia Pool")

    def _apply_launcher_microcopy(self) -> None:
        if hasattr(self, "_hero_subtitle"):
            if self._studio_entry_enabled():
                self._hero_subtitle.setText(
                    self._copy(
                        "한 번 녹화하면 커서, 클릭, 자동 줌까지 보기 좋게 정리합니다.",
                        "Record once; cursor, clicks, and auto zoom are polished by default.",
                    )
                )
            else:
                self._hero_subtitle.setText(
                    self._copy(
                        "빠르게 캡처하고 저장 폴더에 남깁니다. Studio 편집은 별도 앱에서 시작합니다.",
                        "Capture quickly and save locally. Studio editing starts in the separate app.",
                    )
                )
        if hasattr(self, "_startup_busy_label"):
            self._startup_busy_label.setText(self._copy("여는 중...", "Opening..."))
        if hasattr(self, "_drop_title"):
            if self._studio_entry_enabled():
                self._drop_title.setText(
                    self._copy(
                        "화면 녹화 파일을 드롭하면 편집을 시작합니다",
                        "Drop a screen recording to open the editor",
                    )
                )
            else:
                self._drop_title.setText(
                    self._copy(
                        "캡처 파일은 저장 폴더에서 관리합니다",
                        "Captured files stay in the save folder",
                    )
                )
        if hasattr(self, "_drop_body"):
            if self._studio_entry_enabled():
                self._drop_body.setText(
                    self._copy(
                        "커서 메타데이터가 있으면 배경, 클릭, 자동 줌을 자동 적용합니다",
                        "Cursor metadata enables wallpaper, click, and auto-zoom defaults",
                    )
                )
            else:
                self._drop_body.setText(
                    self._copy(
                        "Studio 이동은 기본 차단되어 있습니다. 편집은 Tiger Studio 앱에서 여세요.",
                        "Studio handoff is blocked by default. Open Tiger Studio for editing.",
                    )
                )
        if hasattr(self, "templates_btn"):
            self.templates_btn.setText(self._copy("스튜디오 열기", "Open Studio"))
            self.templates_btn.setToolTip(
                self._copy("빈 타이거 스튜디오 작업공간을 엽니다", "Open a blank Tiger Studio workspace")
            )
        if hasattr(self, "launcher_workspace_label"):
            self.launcher_workspace_label.setText(self._copy("작업공간", "Workspace"))
        standard_label = self._copy("보통", "Normal")
        simple_label = self._copy("심플", "Simple")
        if hasattr(self, "launcher_workspace_switch"):
            self.launcher_workspace_switch.set_labels(standard_label, simple_label)
            self.launcher_workspace_switch.setToolTip(
                self._copy("보통/심플 작업공간을 밀어서 전환합니다", "Slide to switch Normal/Simple workspace")
            )
        if hasattr(self, "launcher_workspace_standard_btn"):
            self.launcher_workspace_standard_btn.setText(standard_label)
            self.launcher_workspace_standard_btn.setToolTip(
                self._copy("미디어풀, 워크벤치, 속성 패널을 모두 여는 보통 모드", "Open the normal editor workspace")
            )
        if hasattr(self, "launcher_workspace_simple_btn"):
            self.launcher_workspace_simple_btn.setText(simple_label)
            self.launcher_workspace_simple_btn.setToolTip(
                self._copy("미디어풀과 워크벤치는 유지하고 보조 패널을 줄이는 모드", "Keep Media Pool and Workbench while hiding secondary panels")
            )

    def _default_open_folder(self) -> None:
        open_in_explorer(default_save_dir())

    def _build_credit_footer(self) -> QWidget:
        self._credit_label = QLabel(tr("app.credit"))
        self._credit_label.setObjectName("CreditFooter")
        self._credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return self._credit_label

    def _build_hero_panel(self) -> QWidget:
        container = QFrame()
        container.setObjectName("LauncherHero")
        container.setMinimumHeight(118)
        container.setMaximumHeight(136)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 12, 14, 12)
        layout.setSpacing(12)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(6)

        self._hero_eyebrow = QLabel(
            self._copy("CAPTURE  /  EDIT  /  PUBLISH", "CAPTURE  /  EDIT  /  PUBLISH")
            if self._studio_entry_enabled()
            else self._copy("CAPTURE", "CAPTURE")
        )
        self._hero_eyebrow.setObjectName("LauncherEyebrow")
        self._hero_eyebrow.setMinimumHeight(15)
        copy.addWidget(self._hero_eyebrow)

        self._title_label = QLabel(tr("app.name"))
        self._title_label.setObjectName("AppTitle")
        self._title_label.setMinimumHeight(30)
        copy.addWidget(self._title_label)

        self._hero_subtitle = QLabel(
            self._copy(
                "녹화하면 커서, 클릭, 자동 줌까지 보기 좋게 준비되는 작은 스튜디오.",
                "Record once; cursor, clicks, and auto zoom are polished by default.",
            )
            if self._studio_entry_enabled()
            else self._copy(
                "빠르게 캡처하고 저장합니다. 편집은 Tiger Studio 앱에서 시작합니다.",
                "Capture quickly and save locally. Editing starts in Tiger Studio.",
            )
        )
        self._hero_subtitle.setObjectName("LauncherSubtitle")
        self._hero_subtitle.setWordWrap(True)
        self._hero_subtitle.setMinimumHeight(30)
        copy.addWidget(self._hero_subtitle)
        copy.addStretch(1)

        layout.addLayout(copy, stretch=1)

        self.new_capture_btn = QPushButton(self._new_capture_text())
        self.new_capture_btn.setObjectName("NewCaptureButton")
        self.new_capture_btn.setIcon(app_icon("plus", size=17, color="#FFFFFF"))
        self.new_capture_btn.setIconSize(icon_size(17))
        self.new_capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_capture_btn.setMinimumHeight(42)
        self.new_capture_btn.setMinimumWidth(144)
        self.new_capture_btn.clicked.connect(self._on_new_capture_clicked)
        layout.addWidget(self.new_capture_btn)

        return container

    def _build_startup_busy(self) -> QWidget:
        self._startup_busy = QFrame()
        self._startup_busy.setObjectName("LauncherBusy")
        layout = QHBoxLayout(self._startup_busy)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        self._startup_busy_label = QLabel(self._copy("준비 중...", "Opening..."))
        self._startup_busy_label.setObjectName("LauncherBusyLabel")
        self._startup_progress = QProgressBar()
        self._startup_progress.setObjectName("LauncherProgress")
        self._startup_progress.setRange(0, 0)
        self._startup_progress.setTextVisible(False)
        self._startup_progress.setFixedHeight(8)
        layout.addWidget(self._startup_busy_label)
        layout.addWidget(self._startup_progress, stretch=1)
        self._startup_busy.hide()
        return self._startup_busy

    def show_startup_busy(self, message: str | None = None) -> None:
        if message:
            self._startup_busy_label.setText(message)
        self._startup_busy.show()
        QTimer.singleShot(4500, self.clear_startup_busy)

    def show_editor_opening_state(self) -> None:
        """Inline launcher feedback that does not create a progress/popup surface."""
        if hasattr(self, "pro_editor_btn"):
            self.pro_editor_btn.setText(self._copy("여는 중...\n잠시만요", "Opening...\nPlease wait"))
        if hasattr(self, "templates_btn"):
            self.templates_btn.setText(self._copy("여는 중", "Opening"))
        if hasattr(self, "quick_record_btn"):
            self.quick_record_btn.setText(self._copy("녹화\n대기", "Record\nReady"))

    def clear_startup_busy(self) -> None:
        if hasattr(self, "_startup_busy"):
            self._startup_busy.hide()
        if hasattr(self, "pro_editor_btn"):
            self.pro_editor_btn.setText(
                self._copy("타이거 스튜디오\n미디어풀 열기", "Tiger Studio\nMedia Pool")
            )
        if hasattr(self, "templates_btn"):
            self.templates_btn.setText(self._copy("스튜디오 열기", "Open Studio"))
        if hasattr(self, "quick_record_btn"):
            self.quick_record_btn.setText(self._copy("녹화\n커서 + 자동 줌", "Record\nCursor + Zoom"))

    def _build_continue_section(self) -> QWidget:
        container = QFrame()
        container.setObjectName("LauncherPanel")
        container.setProperty("density", "quiet")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 9, 12, 10)
        layout.setSpacing(7)

        self._continue_label = QLabel(self._continue_title_text())
        self._continue_label.setObjectName("SectionLabel")
        layout.addWidget(self._continue_label)

        self._continue_row = QWidget()
        self._continue_row_layout = QHBoxLayout(self._continue_row)
        self._continue_row_layout.setContentsMargins(0, 0, 0, 0)
        self._continue_row_layout.setSpacing(8)
        layout.addWidget(self._continue_row)
        self._rebuild_continue_cards()
        return container

    def _build_template_section(self) -> QWidget:
        container = QFrame()
        container.setObjectName("LauncherTemplatePanel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 9)
        layout.setSpacing(7)

        self._template_label = QLabel(self._template_title_text())
        self._template_label.setObjectName("SectionLabel")
        layout.addWidget(self._template_label)

        self._template_row = QWidget()
        self._template_row_layout = QHBoxLayout(self._template_row)
        self._template_row_layout.setContentsMargins(0, 0, 0, 0)
        self._template_row_layout.setSpacing(6)
        layout.addWidget(self._template_row)
        self._rebuild_template_cards()
        return container

    def _clear_button_row(self, layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _make_launcher_card(
        self,
        title: str,
        meta: str,
        *,
        icon_name: str,
        tone: str,
        tooltip: str = "",
        compact: bool = False,
    ) -> QPushButton:
        btn = QPushButton(f"{title}\n{meta}")
        btn.setObjectName("LauncherMiniCard")
        btn.setProperty("tone", tone)
        btn.setProperty("density", "compact" if compact else "normal")
        btn.setIcon(app_icon(icon_name, size=17, color="#FFFFFF"))
        btn.setIconSize(icon_size(17))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(42 if compact else 52)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if tooltip:
            btn.setToolTip(tooltip)
        return btn

    def _make_start_card(
        self,
        title: str,
        meta: str,
        *,
        icon_name: str,
        tone: str,
        tooltip: str = "",
    ) -> QPushButton:
        btn = QPushButton(f"{title}\n{meta}")
        btn.setObjectName("LauncherStartCard")
        btn.setProperty("tone", tone)
        btn.setIcon(app_icon(icon_name, size=18, color="#FFFFFF"))
        btn.setIconSize(icon_size(18))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(62)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if tooltip:
            btn.setToolTip(tooltip)
        return btn

    def _recommended_template_payload(self) -> dict:
        try:
            from app.preset_library import presets_by_kind
            templates = presets_by_kind("template")
        except Exception:
            templates = []
        templates = sorted(
            templates,
            key=lambda p: (
                0 if "screen-studio" in {str(t).lower() for t in getattr(p, "tags", ())} else 1,
                str(getattr(p, "name", "")),
            ),
        )
        if templates:
            preset = templates[0]
            return {
                "id": str(getattr(preset, "id", "")),
                "name": str(getattr(preset, "name", "Template")),
                "description": str(getattr(preset, "description", "") or ""),
            }
        return {
            "id": "template-screenstudio-cursor-demo",
            "name": "Screen Studio Cursor Demo",
            "description": "Cursor tutorial starter",
        }

    @staticmethod
    def _short_name(path: Path, limit: int = 26) -> str:
        name = path.name
        if len(name) <= limit:
            return name
        keep = max(8, (limit - 1) // 2)
        return f"{name[:keep]}...{name[-keep:]}"

    def _project_meta(self, path: Path) -> str:
        try:
            dt = datetime.fromtimestamp(path.stat().st_mtime)
            return self._copy(dt.strftime("%m/%d %H:%M"), dt.strftime("%b %d %H:%M"))
        except OSError:
            return self._copy("프로젝트", "Project")

    def _rebuild_continue_cards(self) -> None:
        self._clear_button_row(self._continue_row_layout)
        added = 0
        try:
            from app.project_io import load_recent_project_paths
            projects = load_recent_project_paths(limit=1)
        except Exception:
            projects = []
        for project_path in projects:
            card = self._make_launcher_card(
                self._short_name(project_path),
                self._project_meta(project_path),
                icon_name="project",
                tone="project",
                tooltip=str(project_path),
                compact=True,
            )
            card.clicked.connect(lambda _checked=False, p=project_path: self._open_recent_project(p))
            self._continue_row_layout.addWidget(card, stretch=1)
            added += 1

        try:
            captures = list_recent(default_save_dir(), limit=1)
        except Exception:
            captures = []
        for capture in captures:
            icon_name = "video" if capture.kind == "video" else ("media" if capture.kind == "gif" else "camera")
            card = self._make_launcher_card(
                self._short_name(capture.path),
                f"{capture.kind.upper()}  {format_size(capture.size_bytes)}",
                icon_name=icon_name,
                tone=capture.kind,
                tooltip=str(capture.path),
                compact=True,
            )
            card.clicked.connect(lambda _checked=False, p=capture.path: self._open_recent_media(p))
            self._continue_row_layout.addWidget(card, stretch=1)
            added += 1
            if added >= 2:
                break

        if added == 0:
            card = self._make_launcher_card(
                self._copy("최근 작업 없음", "No recent work"),
                self._copy("파일을 드롭하거나 새 캡처로 시작", "Drop media or start a new capture"),
                icon_name="spark",
                tone="empty",
                compact=True,
            )
            card.setEnabled(False)
            self._continue_row_layout.addWidget(card, stretch=1)
        self._continue_row_layout.addStretch(1)

    def _rebuild_template_cards(self) -> None:
        self._clear_button_row(self._template_row_layout)
        if not self._studio_entry_enabled():
            card = self._make_launcher_card(
                self._copy("Studio 별도 앱", "Studio is separate"),
                self._copy("캡처 앱에서는 편집으로 이동하지 않습니다", "The capture app does not open editing"),
                icon_name="video",
                tone="empty",
                compact=True,
            )
            card.setEnabled(False)
            self._template_row_layout.addWidget(card, stretch=1)
            return
        try:
            from app.preset_library import presets_by_kind
            templates = presets_by_kind("template")
        except Exception:
            templates = []
        templates = sorted(
            templates,
            key=lambda p: (
                0 if "screen-studio" in {str(t).lower() for t in getattr(p, "tags", ())} else 1,
                str(getattr(p, "name", "")),
            ),
        )[:1]
        for idx, preset in enumerate(templates):
            tags = " / ".join(str(t) for t in getattr(preset, "tags", ())[:2])
            card = self._make_launcher_card(
                str(getattr(preset, "name", "Template")),
                self._copy("클릭 후 미디어를 넣으면 자동 적용", "Auto-applies after media"),
                icon_name="spark",
                tone=f"template{idx}",
                tooltip=f"{tags}\n{getattr(preset, 'description', '') or getattr(preset, 'id', '')}".strip(),
                compact=True,
            )
            payload = {
                "id": str(getattr(preset, "id", "")),
                "name": str(getattr(preset, "name", "Template")),
            }
            card.clicked.connect(lambda _checked=False, p=payload: self._open_template(p))
            self._template_row_layout.addWidget(card, stretch=1)
        if templates:
            more = QPushButton(self._copy("더보기", "More"))
            more.setObjectName("LauncherGhostButton")
            more.setCursor(Qt.CursorShape.PointingHandCursor)
            more.setToolTip(self._copy("스튜디오에서 전체 템플릿 보기", "Browse all templates in Tiger Studio"))
            more.clicked.connect(lambda _checked=False: self.open_video_editor_requested.emit(self._video_editor_payload()))
            self._template_row_layout.addWidget(more)
        if not templates:
            card = self._make_launcher_card(
                self._copy("템플릿 준비 중", "Templates unavailable"),
                self._copy("스튜디오에서 프리셋 확인", "Open Studio presets"),
                icon_name="spark",
                tone="empty",
                compact=True,
            )
            card.clicked.connect(lambda _checked=False: self.open_video_editor_requested.emit(self._video_editor_payload()))
            self._template_row_layout.addWidget(card, stretch=1)

    def _open_recent_project(self, path: Path) -> None:
        if not self._studio_entry_enabled():
            return
        self.show_startup_busy(self._copy("프로젝트 여는 중...", "Opening project..."))
        self.open_project_requested.emit(path)

    def _open_template(self, payload: dict) -> None:
        if not self._studio_entry_enabled():
            return
        self.show_startup_busy(self._copy("템플릿 워크벤치 여는 중...", "Opening template workspace..."))
        self.open_template_requested.emit(payload)

    def _open_recent_media(self, path: Path) -> None:
        self.show_startup_busy(self._copy("미디어 여는 중...", "Opening media..."))
        ext = path.suffix.lower()
        if ext in self._AUDIO_DROP_EXTS:
            self.open_sound_editor_requested.emit(path)
        elif ext in self._VIDEO_DROP_EXTS:
            if self._studio_entry_enabled():
                self.open_video_editor_requested.emit(self._video_editor_payload(path))
            else:
                open_in_explorer(path)
        else:
            self.open_gif_file_requested.emit(path)

    def launcher_workspace_mode(self) -> str:
        switch = getattr(self, "launcher_workspace_switch", None)
        if switch is not None:
            return "simple" if switch.isChecked() else "standard"
        simple_btn = getattr(self, "launcher_workspace_simple_btn", None)
        return "simple" if simple_btn is not None and simple_btn.isChecked() else "standard"

    @staticmethod
    def _workspace_mode_from_value(value: object) -> str | None:
        mode = str(value or "").strip().casefold()
        if mode in {"simple", "screenstudio", "screen_studio", "simp"}:
            return "simple"
        if mode in {"standard", "normal", "full", "default"}:
            return "standard"
        return None

    @staticmethod
    def _launcher_state_disabled() -> bool:
        if str(os.environ.get("TIGERCAPTURE_LAUNCHER_STATE_FORCE", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return False
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return True
        return str(os.environ.get("TIGERCAPTURE_LAUNCHER_STATE_DISABLED", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
            "disabled",
        }

    @staticmethod
    def _launcher_state_path() -> Path:
        return runtime_data_dir() / "launcher_state.json"

    def _repair_launcher_state(self, path: Path, reason: str) -> str:
        repaired_from = ""
        try:
            if path.exists():
                stamp = datetime.now().strftime("%Y%m%d%H%M%S")
                backup = path.with_name(f"{path.stem}.broken-{stamp}{path.suffix}")
                path.rename(backup)
                repaired_from = str(backup)
        except Exception:
            repaired_from = ""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "workspace_mode": "standard",
                        "repaired_at": datetime.now().isoformat(timespec="seconds"),
                        "repaired_reason": str(reason or "invalid_state"),
                        "repaired_from": repaired_from,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass
        try:
            from app.crash_reporter import record_action

            record_action("launcher.state_repaired", path=str(path), reason=str(reason), backup=repaired_from)
        except Exception:
            pass
        return "standard"

    def _load_launcher_workspace_mode(self) -> str:
        env_mode = self._workspace_mode_from_value(os.environ.get("TIGERCAPTURE_LAUNCHER_WORKSPACE_MODE"))
        if env_mode is not None:
            return env_mode
        if self._launcher_state_disabled():
            return "standard"
        path = self._launcher_state_path()
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    return self._repair_launcher_state(path, "state_payload_not_object")
                mode = self._workspace_mode_from_value(data.get("workspace_mode"))
                if mode is not None:
                    return mode
                return self._repair_launcher_state(path, "workspace_mode_missing_or_invalid")
        except Exception:
            return self._repair_launcher_state(path, "state_json_unreadable")
        return "standard"

    def _save_launcher_workspace_mode(self, mode: str) -> None:
        mode = self._workspace_mode_from_value(mode) or "standard"
        if self._launcher_state_disabled():
            return
        try:
            path = self._launcher_state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "workspace_mode": mode,
                        "updated_at": datetime.now().isoformat(timespec="seconds"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _set_launcher_workspace_simple(self, simple: bool, *, persist: bool = True) -> None:
        switch = getattr(self, "launcher_workspace_switch", None)
        if switch is not None and switch.isChecked() != bool(simple):
            switch.blockSignals(True)
            switch.setChecked(bool(simple))
            switch.blockSignals(False)
            switch.update()
        for attr, checked in (
            ("launcher_workspace_standard_btn", not bool(simple)),
            ("launcher_workspace_simple_btn", bool(simple)),
        ):
            btn = getattr(self, attr, None)
            if btn is not None and btn.isChecked() != checked:
                btn.blockSignals(True)
                btn.setChecked(checked)
                btn.blockSignals(False)
        if persist and getattr(self, "_launcher_workspace_state_ready", False):
            self._save_launcher_workspace_mode("simple" if simple else "standard")

    def _video_editor_payload(self, source_path: Path | None = None) -> dict[str, object]:
        return {
            "source_path": source_path,
            "workspace_mode": self.launcher_workspace_mode(),
        }

    def _build_mode_section(self) -> QWidget:
        container = QFrame()
        container.setObjectName("LauncherPanel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        self._mode_section_label = QLabel(tr("main.section.mode"))
        self._mode_section_label.setObjectName("SectionLabel")
        self._mode_section_label.setMinimumHeight(18)
        layout.addWidget(self._mode_section_label)

        buttons_row = QWidget()
        row_layout = QHBoxLayout(buttons_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons: list[tuple[CaptureMode, QPushButton]] = []

        for mode in (CaptureMode.SCREENSHOT, CaptureMode.GIF, CaptureMode.VIDEO):
            btn = QPushButton(mode_label(mode))
            btn.setIcon(self._mode_icon(mode))
            btn.setIconSize(icon_size(16))
            btn.setCheckable(True)
            btn.setProperty("modeButton", True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(44)
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
        container = QFrame()
        container.setObjectName("LauncherOptions")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.cursor_check = QCheckBox(self._copy("커서", "Cursor"))
        self.cursor_check.setToolTip(tr("main.option.include_cursor"))
        self.cursor_check.setChecked(True)

        self._timer_label = QLabel(self._timer_text())
        self._timer_label.setObjectName("LauncherOptionLabel")
        layout.addWidget(self._timer_label)
        layout.addWidget(self._build_delay_selector(min_height=32))
        layout.addSpacing(8)
        layout.addWidget(self.cursor_check)
        layout.addStretch(1)

        return container

    def _build_capture_settings_section(self) -> QWidget:
        container = QFrame()
        container.setObjectName("LauncherSettingsPanel")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(7)

        self._mode_section_label = QLabel(self._copy("캡처", "Capture"))
        self._mode_section_label.setObjectName("LauncherOptionLabel")
        layout.addWidget(self._mode_section_label)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons: list[tuple[CaptureMode, QPushButton]] = []
        for mode in (CaptureMode.SCREENSHOT, CaptureMode.GIF, CaptureMode.VIDEO):
            btn = QPushButton(mode_label(mode))
            btn.setIcon(self._mode_icon(mode))
            btn.setIconSize(icon_size(14))
            btn.setCheckable(True)
            btn.setProperty("modeButton", True)
            btn.setProperty("compact", "true")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(32)
            if mode is self._current_mode:
                btn.setChecked(True)
            btn.clicked.connect(lambda _checked, m=mode: self._on_mode_selected(m))
            if mode is CaptureMode.GIF:
                btn.setToolTip(
                    f"{mode_label(mode)}  —  {tr('main.mode.gif.dblclick_hint')}"
                )
                btn.installEventFilter(self)
                self._gif_mode_btn = btn
            self._mode_group.addButton(btn)
            self._mode_buttons.append((mode, btn))
            layout.addWidget(btn, stretch=1)

        self._timer_label = QLabel(self._timer_text())
        self._timer_label.setObjectName("LauncherOptionLabel")
        layout.addSpacing(4)
        layout.addWidget(self._timer_label)

        layout.addWidget(self._build_delay_selector(min_height=32))

        self.cursor_check = QCheckBox(self._copy("커서", "Cursor"))
        self.cursor_check.setToolTip(tr("main.option.include_cursor"))
        self.cursor_check.setChecked(True)
        layout.addWidget(self.cursor_check)
        return container

    def _delay_button_text(self, seconds: int) -> str:
        return "0s" if seconds == 0 else f"{seconds}s"

    def _delay_tooltip(self, seconds: int) -> str:
        return (
            tr("main.delay.none")
            if seconds == 0
            else tr("main.delay.seconds", seconds=seconds)
        )

    def _build_delay_selector(self, *, min_height: int) -> QWidget:
        strip = QFrame()
        strip.setObjectName("LauncherDelayStrip")
        row = QHBoxLayout(strip)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(3)

        self._delay_group = QButtonGroup(self)
        self._delay_group.setExclusive(True)
        self._delay_buttons: list[tuple[int, QPushButton]] = []
        for seconds in DELAY_SECONDS:
            btn = QPushButton(self._delay_button_text(seconds))
            btn.setCheckable(True)
            btn.setProperty("delayButton", True)
            btn.setProperty("compact", "true")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(min_height - 4)
            btn.setMinimumWidth(34)
            btn.setToolTip(self._delay_tooltip(seconds))
            if seconds == self._delay_seconds:
                btn.setChecked(True)
            btn.clicked.connect(lambda _checked=False, s=seconds: self._set_delay_seconds(s))
            self._delay_group.addButton(btn)
            self._delay_buttons.append((seconds, btn))
            row.addWidget(btn)
        return strip

    def _set_delay_seconds(self, seconds: int) -> None:
        self._delay_seconds = int(seconds)

    def _build_pro_editor_section(self) -> QWidget:
        """Action-first launcher deck for the common Screen Studio workflow."""
        container = QFrame()
        container.setObjectName("LauncherQuickPanel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(7)
        studio_enabled = self._studio_entry_enabled()

        self._pro_editor_section_label = self._quick_start_title_text()
        self._pro_editor_label = QLabel(self._pro_editor_section_label)
        self._pro_editor_label.setObjectName("SectionLabel")
        self._pro_editor_label.setMinimumHeight(18)
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        header_layout.addWidget(self._pro_editor_label)
        header_layout.addStretch(1)
        self.templates_btn = QPushButton(self._copy("스튜디오 열기", "Open Studio"))
        self.templates_btn.setObjectName("LauncherGhostButton")
        self.templates_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.templates_btn.setToolTip(self._copy("빈 타이거 스튜디오 작업공간을 엽니다", "Open a blank Tiger Studio workspace"))
        self.templates_btn.clicked.connect(self._open_video_editor_clicked)
        header_layout.addWidget(self.templates_btn)
        if not studio_enabled:
            self.templates_btn.hide()
        layout.addWidget(header)

        workspace_row = QFrame()
        workspace_row.setObjectName("LauncherWorkspaceSwitch")
        workspace_layout = QHBoxLayout(workspace_row)
        workspace_layout.setContentsMargins(8, 4, 8, 4)
        workspace_layout.setSpacing(8)
        self.launcher_workspace_label = QLabel(self._copy("작업공간", "Workspace"))
        self.launcher_workspace_label.setObjectName("LauncherHint")
        workspace_layout.addWidget(self.launcher_workspace_label)
        workspace_layout.addStretch(1)

        self.launcher_workspace_group = QButtonGroup(self)
        self.launcher_workspace_group.setExclusive(True)
        self.launcher_workspace_switch = LauncherWorkspaceToggle(
            self._copy("보통", "Normal"),
            self._copy("심플", "Simple"),
            workspace_row,
        )
        self.launcher_workspace_switch.setToolTip(
            self._copy("보통/심플 작업공간을 밀어서 전환합니다", "Slide to switch Normal/Simple workspace")
        )
        self.launcher_workspace_switch.toggled.connect(self._set_launcher_workspace_simple)
        workspace_layout.addWidget(self.launcher_workspace_switch)

        self.launcher_workspace_standard_btn = QPushButton(self._copy("보통", "Normal"), workspace_row)
        self.launcher_workspace_standard_btn.setObjectName("LauncherWorkspaceButton")
        self.launcher_workspace_standard_btn.setCheckable(True)
        self.launcher_workspace_standard_btn.setChecked(True)
        self.launcher_workspace_standard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launcher_workspace_standard_btn.setToolTip(
            self._copy("미디어풀, 워크벤치, 속성 패널을 모두 여는 보통 모드", "Open the normal editor workspace")
        )
        self.launcher_workspace_simple_btn = QPushButton(self._copy("심플", "Simple"), workspace_row)
        self.launcher_workspace_simple_btn.setObjectName("LauncherWorkspaceButton")
        self.launcher_workspace_simple_btn.setCheckable(True)
        self.launcher_workspace_simple_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launcher_workspace_simple_btn.setToolTip(
            self._copy("미디어풀과 워크벤치는 유지하고 보조 패널을 줄이는 모드", "Keep Media Pool and Workbench while hiding secondary panels")
        )
        for btn in (self.launcher_workspace_standard_btn, self.launcher_workspace_simple_btn):
            self.launcher_workspace_group.addButton(btn)
            btn.hide()
        self.launcher_workspace_standard_btn.clicked.connect(lambda _checked=False: self._set_launcher_workspace_simple(False))
        self.launcher_workspace_simple_btn.clicked.connect(lambda _checked=False: self._set_launcher_workspace_simple(True))
        saved_mode = self._load_launcher_workspace_mode()
        self._set_launcher_workspace_simple(saved_mode == "simple", persist=False)
        self._launcher_workspace_state_ready = True
        layout.addWidget(workspace_row)
        if not studio_enabled:
            workspace_row.hide()

        pe_row = QWidget()
        pe_layout = QHBoxLayout(pe_row)
        pe_layout.setContentsMargins(0, 0, 0, 0)
        pe_layout.setSpacing(8)

        self.quick_record_btn = self._make_start_card(
            self._copy("녹화", "Record"),
            self._copy("커서 + 자동 줌", "Cursor + Zoom"),
            icon_name="video",
            tone="record",
            tooltip=self._copy("선택한 모드와 타이머로 새 캡처를 시작합니다", "Start a new capture with the selected mode and timer"),
        )
        self.quick_record_btn.clicked.connect(self._on_new_capture_clicked)
        pe_layout.addWidget(self.quick_record_btn, stretch=1)

        self.pro_editor_btn = self._make_start_card(
            self._copy("타이거 스튜디오", "Tiger Studio"),
            self._copy("미디어풀 열기", "Media Pool"),
            icon_name="video",
            tone="edit",
            tooltip=self._copy(
                "빈 타이거 스튜디오 작업공간을 엽니다. 미디어풀에서 파일을 가져오면 됩니다.",
                "Open a blank Tiger Studio workspace. Import files from the Media Pool.",
            ),
        )
        self.pro_editor_btn.clicked.connect(self._open_video_editor_clicked)
        pe_layout.addWidget(self.pro_editor_btn, stretch=1)
        if not studio_enabled:
            self.pro_editor_btn.hide()

        layout.addWidget(pe_row)

        utility_row = QWidget()
        utility_layout = QHBoxLayout(utility_row)
        utility_layout.setContentsMargins(0, 0, 0, 0)
        utility_layout.setSpacing(8)
        self.sound_editor_btn = QPushButton(self._sound_editor_text())
        self.sound_editor_btn.setObjectName("LauncherGhostButton")
        self.sound_editor_btn.setIcon(app_icon("audio", size=14))
        self.sound_editor_btn.setIconSize(icon_size(14))
        self.sound_editor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sound_editor_btn.setMinimumHeight(32)
        self.sound_editor_btn.setToolTip(tr("main.sound_editor.tooltip"))
        self.sound_editor_btn.clicked.connect(self._open_sound_editor_clicked)
        utility_layout.addWidget(self.sound_editor_btn)

        utility_layout.addStretch(1)
        layout.addWidget(utility_row)
        return container

    def _on_pro_editor_toggled(self, checked: bool) -> None:
        return

    def _open_video_editor_clicked(self) -> None:
        if not self._studio_entry_enabled():
            return
        try:
            from app.startup_trace import (
                log_startup_trace,
                start_startup_flicker_trace,
                startup_trace_enabled,
            )

            trace_enabled = startup_trace_enabled()
            if trace_enabled:
                start_startup_flicker_trace(
                    "launcher.open_video_editor_clicked",
                    duration_ms=7000,
                    poll_ms=40,
                    reset_log=True,
                )
                log_startup_trace(
                    "launcher.open_video_editor.clicked",
                    workspace_mode=self.launcher_workspace_mode(),
                    env_enabled=trace_enabled,
                )
        except Exception:
            pass
        # Do not show the indeterminate QProgressBar on this path. On Windows,
        # the hidden->shown busy panel can allocate a transient native
        # QWindow that looks like a separate blinking TigerCapture window.
        self.show_editor_opening_state()
        payload = self._video_editor_payload()
        QTimer.singleShot(50, lambda payload=payload: self.open_video_editor_requested.emit(payload))

    def _open_sound_editor_clicked(self) -> None:
        self.show_startup_busy(self._copy("사운드 에디터 여는 중...", "Opening Sound Editor..."))
        self.open_sound_editor_requested.emit(None)

    def _build_drop_zone(self) -> QWidget:
        container = QFrame()
        container.setObjectName("LauncherDropZone")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(1)
        self._drop_title = QLabel(
            self._copy("화면 녹화 파일을 드롭하면 편집을 시작합니다", "Drop a screen recording to open the editor")
            if self._studio_entry_enabled()
            else self._copy("캡처 파일은 저장 폴더에서 관리합니다", "Captured files stay in the save folder")
        )
        self._drop_title.setObjectName("LauncherDropTitle")
        self._drop_body = QLabel(
            self._copy(
                "커서 메타데이터가 있으면 배경, 클릭, 자동 줌을 자동 적용",
                "Cursor metadata enables wallpaper, click, and auto-zoom",
            )
            if self._studio_entry_enabled()
            else self._copy(
                "Studio 이동은 기본 차단되어 있습니다. 편집은 Tiger Studio 앱에서 여세요.",
                "Studio handoff is blocked by default. Open Tiger Studio for editing.",
            )
        )
        self._drop_body.setObjectName("LauncherDropBody")
        layout.addWidget(self._drop_title)
        layout.addWidget(self._drop_body)
        return container

    def retranslate(self) -> None:
        """Reapply all translated strings without recreating the window."""
        self.setWindowTitle(tr("app.name"))
        self._brand_label.setText("TigerCapture")
        self._title_label.setText(tr("app.name"))
        self._hero_eyebrow.setText(
            self._copy("CAPTURE  /  EDIT  /  PUBLISH", "CAPTURE  /  EDIT  /  PUBLISH")
            if self._studio_entry_enabled()
            else self._copy("CAPTURE", "CAPTURE")
        )
        self._hero_subtitle.setText(
            self._copy(
                "녹화하면 커서, 클릭, 자동 줌까지 보기 좋게 준비되는 작은 스튜디오.",
                "Record once; cursor, clicks, and auto zoom are polished by default.",
            )
            if self._studio_entry_enabled()
            else self._copy(
                "빠르게 캡처하고 저장합니다. 편집은 Tiger Studio 앱에서 시작합니다.",
                "Capture quickly and save locally. Editing starts in Tiger Studio.",
            )
        )
        self._credit_label.setText(tr("app.credit"))
        self.open_folder_btn.setToolTip(tr("main.tooltip.open_folder"))
        self.settings_btn.setToolTip(tr("main.tooltip.settings"))
        self.donate_btn.setToolTip(tr("main.tooltip.donate"))
        self.donate_btn.setText(tr("main.donate.button"))
        self._startup_busy_label.setText(self._copy("준비 중...", "Opening..."))
        if hasattr(self, "_continue_label"):
            self._continue_label.setText(self._continue_title_text())
        if hasattr(self, "_template_label"):
            self._template_label.setText(self._template_title_text())
        self._pro_editor_section_label = self._quick_start_title_text()
        self._pro_editor_label.setText(self._pro_editor_section_label)
        if hasattr(self, "templates_btn"):
            self.templates_btn.setText(self._copy("스튜디오 열기", "Open Studio"))
            self.templates_btn.setToolTip(self._copy("빈 타이거 스튜디오 작업공간을 엽니다", "Open a blank Tiger Studio workspace"))
        if hasattr(self, "quick_record_btn"):
            self.quick_record_btn.setText(self._record_card_text())
        if hasattr(self, "pro_editor_btn"):
            self.pro_editor_btn.setText(self._edit_card_text())
        self.sound_editor_btn.setText(self._sound_editor_text())
        self.sound_editor_btn.setToolTip(tr("main.sound_editor.tooltip"))
        self.new_capture_btn.setText(self._new_capture_text())
        self._mode_section_label.setText(self._copy("캡처", "Capture"))
        self._timer_label.setText(self._timer_text())
        self.cursor_check.setText(self._copy("커서", "Cursor"))
        self.cursor_check.setToolTip(tr("main.option.include_cursor"))
        self._drop_title.setText(
            self._copy("화면 녹화 파일을 드롭하면 편집을 시작합니다", "Drop a screen recording to open the editor")
            if self._studio_entry_enabled()
            else self._copy("캡처 파일은 저장 폴더에서 관리합니다", "Captured files stay in the save folder")
        )
        self._drop_body.setText(
            self._copy(
                "커서 메타데이터가 있으면 배경, 클릭, 자동 줌을 자동 적용",
                "Cursor metadata enables wallpaper, click, and auto-zoom defaults",
            )
            if self._studio_entry_enabled()
            else self._copy(
                "Studio 이동은 기본 차단되어 있습니다. 편집은 Tiger Studio 앱에서 여세요.",
                "Studio handoff is blocked by default. Open Tiger Studio for editing.",
            )
        )

        for mode, btn in self._mode_buttons:
            btn.setText(mode_label(mode))
            btn.setIcon(self._mode_icon(mode))
            btn.setIconSize(icon_size(16))

        for seconds, btn in getattr(self, "_delay_buttons", []):
            btn.setText(self._delay_button_text(seconds))
            btn.setToolTip(self._delay_tooltip(seconds))
        self._apply_launcher_microcopy()

    def refresh_recent(self) -> None:
        if hasattr(self, "_continue_row_layout"):
            self._rebuild_continue_cards()
        if hasattr(self, "_template_row_layout"):
            self._rebuild_template_cards()

    def _on_mode_selected(self, mode: CaptureMode) -> None:
        self._current_mode = mode

    @staticmethod
    def _mode_icon(mode: CaptureMode):
        return app_icon(
            {
                CaptureMode.SCREENSHOT: "camera",
                CaptureMode.GIF: "media",
                CaptureMode.VIDEO: "video",
            }[mode],
            size=16,
        )

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
                    if self._studio_entry_enabled():
                        self.open_video_editor_requested.emit(self._video_editor_payload(path))
                    else:
                        open_in_explorer(path)
                elif kind == "gif":
                    self.open_gif_file_requested.emit(path)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def _on_new_capture_clicked(self) -> None:
        delay_seconds = int(getattr(self, "_delay_seconds", 0))
        include_cursor = self.cursor_check.isChecked()
        self.new_capture_requested.emit(self._current_mode, delay_seconds, include_cursor)

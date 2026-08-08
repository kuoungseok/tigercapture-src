"""Persistent top-left island for Painter UI Design focus mode."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QActionGroup, QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QWidgetAction,
)

from app.icons import app_icon, icon_size
from app.painter_i18n import painter_text


def _apply_island_shadow(widget: QFrame) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(24.0)
    shadow.setOffset(0.0, 5.0)
    shadow.setColor(QColor(0, 0, 0, 48))
    widget.setGraphicsEffect(shadow)


class PainterUIFocusIsland(QFrame):
    main_menu_requested = Signal()
    focus_exit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIFocusIsland")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        _apply_island_shadow(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 5, 7, 5)
        layout.setSpacing(6)

        self.logo_button = QToolButton(self)
        self.logo_button.setObjectName("PainterUIFocusIslandLogo")
        self.logo_button.setIcon(
            app_icon("tiger-painter-logo", size=20, color="#168BFF")
        )
        self.logo_button.setIconSize(icon_size(20))
        self.logo_button.setFixedSize(34, 32)
        self.logo_button.setToolTip(painter_text("Main menu"))
        self.logo_button.clicked.connect(self.main_menu_requested)
        layout.addWidget(self.logo_button)

        self.title_label = QLabel(painter_text("Untitled"), self)
        self.title_label.setObjectName("PainterUIFocusIslandTitle")
        self.title_label.setMinimumWidth(80)
        layout.addWidget(self.title_label)

        self.exit_button = QToolButton(self)
        self.exit_button.setObjectName("PainterUIFocusIslandExit")
        self.exit_button.setIcon(
            app_icon("figma-full-mode", size=16, color="#303236")
        )
        self.exit_button.setIconSize(icon_size(16))
        self.exit_button.setFixedSize(32, 30)
        self.exit_button.setToolTip(painter_text("Exit focus canvas"))
        self.exit_button.clicked.connect(self.focus_exit_requested)
        layout.addWidget(self.exit_button)
        self.adjustSize()
        self.hide()

    def set_document_title(self, title: str) -> None:
        self.title_label.setText(
            str(title or "").strip() or painter_text("Untitled")
        )
        self.adjustSize()

    def place_in_parent(self) -> None:
        if self.parentWidget() is None:
            return
        self.adjustSize()
        self.move(12, 12)
        self.raise_()


class PainterUIFocusControlsIsland(QFrame):
    """Top-right focus controls matching Figma's zoom/preview island."""

    zoom_requested = Signal(float)
    fit_requested = Signal(str)
    presentation_requested = Signal()
    preview_requested = Signal()
    export_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIFocusControlsIsland")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        _apply_island_shadow(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(4)

        self.zoom_button = QToolButton(self)
        self.zoom_button.setObjectName("PainterUIFocusZoomButton")
        self.zoom_button.setText("100%")
        self.zoom_button.setFixedSize(78, 34)
        self.zoom_button.setToolTip(painter_text("Zoom and fit"))
        self.zoom_button.clicked.connect(self._toggle_zoom_popover)
        layout.addWidget(self.zoom_button)

        self.preview_button = QToolButton(self)
        self.preview_button.setObjectName("PainterUIFocusPreviewButton")
        preview_menu = QMenu(self.preview_button)
        preview_menu.setObjectName("PainterUIFocusPreviewMenu")
        self.presentation_action = preview_menu.addAction(
            app_icon("play", size=16, color="#f4f4f4"),
            painter_text("Presentation"),
        )
        self.presentation_action.setCheckable(True)
        self.presentation_action.setChecked(True)
        self.presentation_action.triggered.connect(
            lambda _checked=False: self.presentation_requested.emit()
        )
        self.preview_action = preview_menu.addAction(
            app_icon("ui-frame", size=16, color="#f4f4f4"),
            painter_text("Preview"),
        )
        self.preview_action.triggered.connect(
            lambda _checked=False: self.preview_requested.emit()
        )
        self.preview_button.setDefaultAction(self.presentation_action)
        self.preview_button.setMenu(preview_menu)
        self.preview_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self.preview_button.setFixedSize(52, 34)
        self.preview_button.setToolTip(painter_text("Presentation"))
        layout.addWidget(self.preview_button)

        self.export_button = QPushButton(painter_text("Export"), self)
        self.export_button.setObjectName("PainterUIFocusExportButton")
        self.export_button.setFixedHeight(34)
        self.export_button.clicked.connect(self.export_requested)
        layout.addWidget(self.export_button)

        self.zoom_popover = self._build_zoom_menu()
        self._zoom_percent = 100
        self.adjustSize()
        self.hide()

    def _build_zoom_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setObjectName("PainterUIFocusZoomMenu")
        editor = QLineEdit("100%", menu)
        editor.setObjectName("PainterUIFocusZoomEditor")
        editor.setFixedWidth(236)
        editor.returnPressed.connect(
            lambda: self._apply_zoom_editor(editor)
        )
        editor_action = QWidgetAction(menu)
        editor_action.setDefaultWidget(editor)
        menu.addAction(editor_action)
        menu.addSeparator()
        self.zoom_editor = editor

        def command(label: str, handler, shortcut: str = ""):
            action = menu.addAction(painter_text(label))
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(handler)
            return action

        command("Zoom in", lambda: self._step_zoom(25), "Ctrl++")
        command("Zoom out", lambda: self._step_zoom(-25), "Ctrl+-")
        command(
            "Fit all artboards",
            lambda: self.fit_requested.emit("all"),
            "Shift+1",
        )
        menu.addSeparator()
        zoom_group = QActionGroup(menu)
        zoom_group.setExclusive(True)
        self.zoom_actions = {}
        for percent in (50, 100, 200):
            action = menu.addAction(f"{percent}%")
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, value=percent: (
                    self.zoom_requested.emit(float(value))
                )
            )
            zoom_group.addAction(action)
            self.zoom_actions[percent] = action
        self.zoom_actions[100].setChecked(True)
        menu.addSeparator()
        pixel_preview = menu.addMenu(painter_text("Pixel preview"))
        pixel_preview.addAction("1x")
        pixel_preview.addAction("2x")
        for label in (
            "Pixel grid",
            "Snap to pixel grid",
            "Layout guides",
            "Rulers",
            "Outlines",
            "Multiplayer cursors",
            "Additional labels",
            "Comments",
        ):
            action = menu.addAction(painter_text(label))
            action.setCheckable(True)
            action.setChecked(
                label in {"Pixel grid", "Snap to pixel grid"}
            )
        return menu

    def set_zoom_percent(self, percent: float) -> None:
        value = max(3, min(800, int(round(float(percent)))))
        self._zoom_percent = value
        self.zoom_button.setText(f"{value}%")
        self.zoom_editor.setText(f"{value}%")
        for percent, action in self.zoom_actions.items():
            action.setChecked(percent == value)

    def _step_zoom(self, delta: int) -> None:
        self.zoom_requested.emit(
            float(max(3, min(800, self._zoom_percent + int(delta))))
        )

    def _apply_zoom_editor(self, editor: QLineEdit) -> None:
        raw = editor.text().strip().removesuffix("%")
        try:
            value = float(raw)
        except ValueError:
            editor.setText(f"{self._zoom_percent}%")
            return
        self.zoom_requested.emit(max(3.0, min(800.0, value)))
        self.zoom_popover.hide()

    def _toggle_zoom_popover(self) -> None:
        if self.zoom_popover.isVisible():
            self.zoom_popover.hide()
            return
        self.zoom_popover.popup(
            self.zoom_button.mapToGlobal(
                QPoint(
                    self.zoom_button.width() - self.zoom_popover.sizeHint().width(),
                    self.zoom_button.height() + 5,
                )
            )
        )

    def place_in_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        self.move(max(12, parent.width() - self.width() - 12), 12)
        self.raise_()
        if self.zoom_popover.isVisible():
            self.zoom_popover.raise_()


__all__ = ["PainterUIFocusControlsIsland", "PainterUIFocusIsland"]

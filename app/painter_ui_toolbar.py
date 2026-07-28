"""Compact floating toolbar for Painter's UI Design canvas."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
)

from app.icons import app_icon, icon_size
from app.painter_i18n import painter_text


class PainterUIFloatingToolbar(QFrame):
    """Figma-style, canvas-local command surface.

    The toolbar emits intent only. Document mutations remain owned by the
    Painter dialog and its existing action-backed handlers.
    """

    tool_requested = Signal(str)
    snap_changed = Signal(bool)
    guide_visibility_changed = Signal(bool)
    guide_lock_changed = Signal(bool)
    guide_clear_requested = Signal()
    ruler_origin_reset_requested = Signal()
    fit_requested = Signal(str)
    zoom_requested = Signal(float)
    motion_actor_requested = Signal()
    animate_requested = Signal()
    motion_preview_changed = Signal(bool)
    quick_actions_requested = Signal()
    navigator_requested = Signal()
    inspector_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PaintUIDesignToolHost")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(self)
        layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)
        layout.setContentsMargins(6, 5, 6, 5)
        layout.setSpacing(2)

        self.tool_buttons: dict[str, QPushButton | QToolButton] = {}
        self._tool_actions: dict[str, QAction] = {}
        self._tool_group_for_kind: dict[str, QPushButton | QToolButton] = {}

        select_button = self._tool_button(
            "Select",
            "cursor",
            checked=True,
        )
        select_button.clicked.connect(
            lambda _checked=False: self.tool_requested.emit("select")
        )
        layout.addWidget(select_button)
        self.tool_buttons["select"] = select_button
        self._tool_group_for_kind["select"] = select_button

        frame_button = self._tool_button("Frame", "ui-frame")
        frame_button.clicked.connect(
            lambda _checked=False: self.tool_requested.emit("frame")
        )
        layout.addWidget(frame_button)
        self.tool_buttons["frame"] = frame_button
        self._tool_group_for_kind["frame"] = frame_button

        shape_button = self._tool_group_button(
            (
                ("Rectangle", "rectangle", "rectangle"),
                ("Ellipse", "ellipse", "ellipse"),
                ("Line", "line", "line"),
            )
        )
        layout.addWidget(shape_button)
        for kind in ("rectangle", "ellipse", "line"):
            self.tool_buttons[kind] = shape_button
            self._tool_group_for_kind[kind] = shape_button

        content_button = self._tool_group_button(
            (
                ("Text", "text", "caption"),
                ("Image", "image", "image"),
                ("Button", "button", "button"),
                ("Progress", "progress", "progress"),
            )
        )
        layout.addWidget(content_button)
        for kind in ("text", "image", "button", "progress"):
            self.tool_buttons[kind] = content_button
            self._tool_group_for_kind[kind] = content_button

        layout.addWidget(self._separator())
        self.snap_button = self._icon_button(
            "Snap to grid",
            "grid",
            checkable=True,
        )
        self.snap_button.setToolTip(
            "Snap position and size to an 8 px grid; rotate to 15 degrees"
        )
        self.snap_button.toggled.connect(self.snap_changed)
        layout.addWidget(self.snap_button)

        self.guide_button = QToolButton()
        self.guide_button.setObjectName("PainterUIFloatingToolButton")
        self.guide_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.guide_button.setFixedSize(32, 30)
        self.guide_button.setIcon(
            app_icon("ruler", size=15, color="#E4E8EE")
        )
        self.guide_button.setIconSize(icon_size(15))
        self.guide_button.setToolTip("Rulers and guides")
        self.guide_button.setAccessibleName("Rulers and guides")
        guide_menu = QMenu(self.guide_button)
        guide_menu.setObjectName("PainterUIGuideMenu")
        self.guide_visibility_action = guide_menu.addAction("Show guides")
        self.guide_visibility_action.setCheckable(True)
        self.guide_visibility_action.setChecked(True)
        self.guide_visibility_action.toggled.connect(
            self.guide_visibility_changed
        )
        self.guide_lock_action = guide_menu.addAction("Lock guides")
        self.guide_lock_action.setCheckable(True)
        self.guide_lock_action.toggled.connect(self.guide_lock_changed)
        guide_menu.addSeparator()
        self.guide_clear_action = guide_menu.addAction("Clear guides")
        self.guide_clear_action.triggered.connect(self.guide_clear_requested)
        self.ruler_origin_reset_action = guide_menu.addAction(
            "Reset ruler origin"
        )
        self.ruler_origin_reset_action.triggered.connect(
            self.ruler_origin_reset_requested
        )
        self.guide_button.setMenu(guide_menu)
        layout.addWidget(self.guide_button)

        self.zoom_button = self._icon_button("Zoom and fit", "zoom")
        self.zoom_button.clicked.connect(self._toggle_zoom_popover)
        layout.addWidget(self.zoom_button)

        from app.painter_ui_zoom_popover import PainterUIZoomPopover

        self.zoom_popover = PainterUIZoomPopover(self.parentWidget())
        self.zoom_popover.zoom_requested.connect(self._request_zoom)
        self.zoom_popover.fit_requested.connect(self._request_fit)
        self.view_buttons = self.zoom_popover.fit_buttons
        self._zoom_percent = 100.0

        self.zoom_indicator = QLabel("100%", self.parentWidget())
        self.zoom_indicator.setObjectName("PainterUIZoomIndicator")
        self.zoom_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_indicator.setFixedSize(54, 24)
        self.zoom_indicator.hide()
        self._zoom_indicator_timer = QTimer(self)
        self._zoom_indicator_timer.setSingleShot(True)
        self._zoom_indicator_timer.setInterval(900)
        self._zoom_indicator_timer.timeout.connect(self.zoom_indicator.hide)

        self.quick_actions_button = self._icon_button(
            "Quick Actions (Ctrl+/)",
            "search",
        )
        self.quick_actions_button.clicked.connect(
            self.quick_actions_requested
        )
        layout.addWidget(self.quick_actions_button)

        layout.addWidget(self._separator())
        self.navigator_button = self._icon_button(
            painter_text("Layers and assets"),
            "layers",
        )
        self.navigator_button.clicked.connect(self.navigator_requested)
        layout.addWidget(self.navigator_button)
        self.inspector_button = self._icon_button(
            painter_text("Properties"),
            "sliders",
        )
        self.inspector_button.clicked.connect(self.inspector_requested)
        layout.addWidget(self.inspector_button)

        layout.addWidget(self._separator())
        self.motion_actor_button = self._icon_button(
            "Motion Actor",
            "import",
        )
        self.motion_actor_button.setToolTip(
            "Import and place a .tgmotion animation actor"
        )
        self.motion_actor_button.clicked.connect(self.motion_actor_requested)
        layout.addWidget(self.motion_actor_button)

        self.animate_button = self._icon_button("Animate", "motion")
        self.animate_button.setToolTip(
            "Open the selected UI object in Motion Designer"
        )
        self.animate_button.clicked.connect(self.animate_requested)
        layout.addWidget(self.animate_button)

        self.motion_preview_button = self._icon_button(
            "Play UI motion preview",
            "play",
            checkable=True,
        )
        self.motion_preview_button.setToolTip(
            "Play or stop the selected UI motion"
        )
        self.motion_preview_button.toggled.connect(
            self.motion_preview_changed
        )
        layout.addWidget(self.motion_preview_button)

    def set_active_tool(self, tool: str) -> None:
        active = str(tool or "select")
        active_button = self._tool_group_for_kind.get(
            active,
            self.tool_buttons["select"],
        )
        for button in set(self._tool_group_for_kind.values()):
            button.blockSignals(True)
            button.setChecked(button is active_button)
            button.blockSignals(False)
        action = self._tool_actions.get(active)
        if action is not None and isinstance(active_button, QToolButton):
            active_button.setDefaultAction(action)
            active_button.setCheckable(True)
            active_button.setChecked(True)
            active_button.setObjectName("PainterUIFloatingToolButton")

    def sync_density(self, available_width: int) -> None:
        width = max(0, int(available_width))
        compact = width < 620
        self.motion_actor_button.setVisible(not compact)
        self.inspector_button.setVisible(not compact)
        self.adjustSize()

    def set_zoom_percent(
        self,
        percent: float,
        *,
        transient: bool = True,
    ) -> None:
        self._zoom_percent = max(3.0, min(800.0, float(percent)))
        rounded = int(round(self._zoom_percent))
        self.zoom_button.setToolTip(
            f"{painter_text('Zoom and fit')} · {rounded}%"
        )
        self.zoom_button.setAccessibleName(self.zoom_button.toolTip())
        self.zoom_popover.set_zoom_percent(self._zoom_percent)
        self.zoom_indicator.setText(f"{rounded}%")
        if transient and not self.zoom_popover.isVisible() and self.isVisible():
            self._place_zoom_indicator()
            self.zoom_indicator.show()
            self.zoom_indicator.raise_()
            self._zoom_indicator_timer.start()

    def set_guide_state(self, *, visible: bool, locked: bool) -> None:
        for action, checked in (
            (self.guide_visibility_action, visible),
            (self.guide_lock_action, locked),
        ):
            action.blockSignals(True)
            action.setChecked(bool(checked))
            action.blockSignals(False)

    def place_in_parent(self, *, bottom_margin: int = 16) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        x = max(8, (parent.width() - self.width()) // 2)
        y = max(8, parent.height() - self.height() - int(bottom_margin))
        self.move(x, y)
        self.raise_()
        if self.zoom_popover.isVisible():
            self.zoom_popover.open_above(self.zoom_button)
        if self.zoom_indicator.isVisible():
            self._place_zoom_indicator()

    def _toggle_zoom_popover(self) -> None:
        if self.zoom_popover.isVisible():
            self.zoom_popover.hide()
            return
        self.zoom_indicator.hide()
        self._zoom_indicator_timer.stop()
        self.zoom_popover.set_zoom_percent(self._zoom_percent)
        self.zoom_popover.open_above(self.zoom_button)

    def _request_zoom(self, percent: float) -> None:
        self.zoom_requested.emit(float(percent))

    def _request_fit(self, mode: str) -> None:
        self.fit_requested.emit(str(mode))
        self.zoom_popover.hide()

    def _place_zoom_indicator(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        point = self.zoom_button.mapTo(parent, self.zoom_button.rect().topLeft())
        x = point.x() + (self.zoom_button.width() - self.zoom_indicator.width()) // 2
        x = max(8, min(x, parent.width() - self.zoom_indicator.width() - 8))
        y = max(8, point.y() - self.zoom_indicator.height() - 6)
        self.zoom_indicator.move(x, y)

    def hideEvent(self, event) -> None:
        self.zoom_popover.hide()
        self.zoom_indicator.hide()
        super().hideEvent(event)

    @staticmethod
    def _separator() -> QFrame:
        separator = QFrame()
        separator.setObjectName("PainterUIToolbarSeparator")
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFixedSize(7, 22)
        return separator

    @staticmethod
    def _icon_button(
        label: str,
        icon_name: str,
        *,
        checkable: bool = False,
        checked: bool = False,
    ) -> QPushButton:
        button = QPushButton("")
        button.setObjectName("PainterUIFloatingToolButton")
        button.setCheckable(checkable)
        button.setChecked(checked)
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.setIcon(app_icon(icon_name, size=15, color="#E4E8EE"))
        button.setIconSize(icon_size(15))
        button.setFixedSize(30, 30)
        return button

    @staticmethod
    def _tool_button(
        label: str,
        icon_name: str,
        *,
        checked: bool = False,
    ) -> QPushButton:
        return PainterUIFloatingToolbar._icon_button(
            label,
            icon_name,
            checkable=True,
            checked=checked,
        )

    def _tool_group_button(
        self,
        rows: tuple[tuple[str, str, str], ...],
    ) -> QToolButton:
        button = QToolButton()
        button.setObjectName("PainterUIFloatingToolButton")
        button.setCheckable(True)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        button.setFixedSize(38, 30)
        button.setIconSize(icon_size(15))
        menu = QMenu(button)
        menu.setObjectName("PainterUIToolFlyout")
        for label, kind, icon_name in rows:
            action = QAction(
                app_icon(icon_name, size=15, color="#E4E8EE"),
                label,
                menu,
            )
            action.setData(kind)
            action.triggered.connect(
                lambda _checked=False, value=kind: self._select_group_tool(
                    value
                )
            )
            menu.addAction(action)
            self._tool_actions[kind] = action
        button.setMenu(menu)
        button.setDefaultAction(self._tool_actions[rows[0][1]])
        button.setCheckable(True)
        button.setObjectName("PainterUIFloatingToolButton")
        return button

    def _select_group_tool(self, kind: str) -> None:
        self.set_active_tool(kind)
        self.tool_requested.emit(str(kind))


__all__ = ["PainterUIFloatingToolbar"]

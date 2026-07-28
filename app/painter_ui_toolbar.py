"""Compact floating toolbar for Painter's UI Design canvas."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
)

from app.icons import app_icon, icon_size


class PainterUIFloatingToolbar(QFrame):
    """Figma-style, canvas-local command surface.

    The toolbar emits intent only. Document mutations remain owned by the
    Painter dialog and its existing action-backed handlers.
    """

    tool_requested = Signal(str)
    snap_changed = Signal(bool)
    fit_requested = Signal(str)
    motion_actor_requested = Signal()
    animate_requested = Signal()
    motion_preview_changed = Signal(bool)

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

        self.tool_buttons: dict[str, QPushButton] = {}
        for label, kind, icon_name in (
            ("Select", "select", "cursor"),
            ("Frame", "frame", "ui-frame"),
            ("Rectangle", "rectangle", "rectangle"),
            ("Ellipse", "ellipse", "ellipse"),
            ("Line", "line", "line"),
            ("Text", "text", "caption"),
            ("Image", "image", "image"),
            ("Button", "button", "button"),
            ("Progress", "progress", "progress"),
        ):
            button = self._icon_button(
                label,
                icon_name,
                checkable=True,
                checked=kind == "select",
            )
            button.clicked.connect(
                lambda _checked=False, value=kind: self.tool_requested.emit(
                    value
                )
            )
            layout.addWidget(button)
            self.tool_buttons[kind] = button

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

        self.view_buttons: dict[str, QPushButton] = {}
        for label, mode, icon_name in (
            ("Fit all artboards", "all", "zoom-fit"),
            ("Fit active artboard", "artboard", "fit"),
            ("Fit selection", "selection", "ui-frame"),
        ):
            button = self._icon_button(label, icon_name)
            button.clicked.connect(
                lambda _checked=False, value=mode: self.fit_requested.emit(
                    value
                )
            )
            layout.addWidget(button)
            self.view_buttons[mode] = button

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
        for name, button in self.tool_buttons.items():
            button.blockSignals(True)
            button.setChecked(name == active)
            button.blockSignals(False)

    def sync_density(self, available_width: int) -> None:
        width = max(0, int(available_width))
        compact = width < 620
        very_compact = width < 430
        for name in ("ellipse", "line", "button", "progress"):
            self.tool_buttons[name].setVisible(not compact)
        self.tool_buttons["image"].setVisible(not very_compact)
        for mode in ("artboard", "selection"):
            self.view_buttons[mode].setVisible(not compact)
        self.motion_actor_button.setVisible(not compact)
        self.adjustSize()

    def place_in_parent(self, *, bottom_margin: int = 16) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        x = max(8, (parent.width() - self.width()) // 2)
        y = max(8, parent.height() - self.height() - int(bottom_margin))
        self.move(x, y)
        self.raise_()

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


__all__ = ["PainterUIFloatingToolbar"]

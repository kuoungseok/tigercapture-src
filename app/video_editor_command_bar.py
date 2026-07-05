from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QToolButton, QWidget

from app.icons import app_icon, icon_size


COMMAND_MENU_ICONS = {
    "Project": "project",
    "Create": "spark",
    "Actors": "actors",
    "View": "grid",
    "Export": "export",
    "Tracks": "slide",
    "More": "more",
}


@dataclass(frozen=True)
class CommandBarBreakpoints:
    tight: bool
    narrow: bool
    tiny: bool


def command_bar_breakpoints(width: int) -> CommandBarBreakpoints:
    width = int(width or 0)
    return CommandBarBreakpoints(
        tight=width < 2100,
        narrow=width < 1600,
        tiny=width < 1200,
    )


def configure_command_menu_button(
    button: QToolButton,
    text: str,
    tooltip: str = "",
    *,
    edge: int = 32,
) -> None:
    button.setObjectName("CommandMenuButton")
    button.setText("")
    button.setAccessibleName(str(text))
    button.setIcon(app_icon(COMMAND_MENU_ICONS.get(str(text), "more"), size=16))
    button.setIconSize(icon_size(16))
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    button.setFixedSize(edge, edge)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    if tooltip:
        button.setToolTip(f"{text}\n{tooltip}")


def apply_catalog_command_button_size(
    button: QWidget | None,
    *,
    left_rail: bool,
) -> None:
    if button is None:
        return
    edge = 26 if left_rail else 32
    try:
        button.setVisible(True)
        button.setFixedSize(edge, edge)
    except Exception:
        return
    if hasattr(button, "setIconSize"):
        try:
            button.setIconSize(icon_size(14 if left_rail else 16))
        except Exception:
            pass


def install_lazy_action_menu(
    owner: QWidget,
    button: QToolButton,
    entries: Iterable[tuple[str, Callable] | None],
    *,
    object_name: str = "",
) -> None:
    cached_entries = tuple(entries)

    def _ensure_menu() -> None:
        try:
            if button.menu() is not None:
                return
            menu = QMenu(button)
            if object_name:
                menu.setObjectName(object_name)
            for entry in cached_entries:
                if entry is None:
                    menu.addSeparator()
                    continue
                label, slot = entry
                action = QAction(str(label), owner)
                action.triggered.connect(lambda _checked=False, s=slot: s())
                menu.addAction(action)
            button.setMenu(menu)
        except Exception:
            pass

    try:
        button.pressed.connect(_ensure_menu)
    except Exception:
        pass


def show_existing_button_menu(
    owner: QWidget,
    button: QToolButton | None,
    *,
    builder: Callable | None = None,
    anchor: QWidget | None = None,
    fallback_anchor: QWidget | None = None,
) -> None:
    if button is None:
        return
    try:
        if button.menu() is None and builder is not None:
            builder()
        menu = button.menu()
    except Exception:
        menu = None
    if menu is None:
        return
    if anchor is None:
        anchor = button if button.isVisible() else fallback_anchor
    if anchor is None:
        anchor = owner
    try:
        menu.exec(anchor.mapToGlobal(QPoint(0, max(1, anchor.height()))))
    except Exception:
        pass

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QWidget

from app.icons import app_icon, icon_size


TIMELINE_CURSOR_ROLE_MAP = {
    "blade": "blade_tool",
    "split": "blade_tool",
    "select": "select_tool",
    "zoom": "zoom_tool",
    "color": "color_picker",
    "ripple": "trim_tool",
    "roll": "trim_tool",
    "slip": "trim_tool",
    "slide": "trim_tool",
    "trim": "trim_tool",
    "tracks": "button",
    "nest": "button",
    "scopes": "button",
    "mixer": "button",
}


def timeline_cursor_role(role_or_icon: str) -> str:
    key = str(role_or_icon or "")
    return TIMELINE_CURSOR_ROLE_MAP.get(key, key)


def configure_timeline_tile(
    button: QWidget,
    label: str,
    icon_name: str,
    *,
    cursor_factory: Callable[[str], object],
    install_pulse: Callable[..., None] | None = None,
    color: str = "#B8C1CF",
    size: int = 30,
    role: str | None = None,
    animated_button_type: type | None = None,
) -> None:
    role_value = role or icon_name
    cursor_role = timeline_cursor_role(str(role_value))
    button.setObjectName("ToolTile")
    button.setProperty("paletteRole", role_value)
    button.setProperty("cursor_fx_role", cursor_role)
    if hasattr(button, "setText"):
        button.setText("")
    if hasattr(button, "setAccessibleName"):
        button.setAccessibleName(label)
    if hasattr(button, "setCursor"):
        button.setCursor(cursor_factory(cursor_role))
    if hasattr(button, "setFixedSize"):
        button.setFixedSize(size, size)
    if hasattr(button, "set_timeline_icon"):
        button.set_timeline_icon(icon_name, color)
    elif hasattr(button, "setIcon"):
        button.setIcon(app_icon(icon_name, size=16, color=color))
        button.setIconSize(icon_size(16))
    if isinstance(button, QToolButton):
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    is_animated = animated_button_type is not None and isinstance(button, animated_button_type)
    if install_pulse is not None and not is_animated:
        install_pulse(button, base=16, peak=20)


def set_timeline_palette_collapsed_widgets(
    widgets: tuple[QWidget, ...],
    *,
    collapsed: bool,
) -> None:
    for widget in widgets or ():
        try:
            widget.setVisible(not collapsed)
        except Exception:
            pass

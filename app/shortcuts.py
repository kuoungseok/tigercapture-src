from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Shortcut:
    id: str
    key: str  # Qt key sequence string
    label_key: str  # translation key


DEFAULT_SHORTCUTS: list[Shortcut] = [
    Shortcut("new_capture", "Ctrl+Shift+N", "shortcuts.new_capture"),
    Shortcut("mode_screenshot", "Ctrl+1", "shortcuts.mode_screenshot"),
    Shortcut("mode_gif", "Ctrl+2", "shortcuts.mode_gif"),
    Shortcut("mode_video", "Ctrl+3", "shortcuts.mode_video"),
    Shortcut("open_folder", "Ctrl+O", "shortcuts.open_folder"),
    Shortcut("settings", "Ctrl+,", "shortcuts.settings"),
]

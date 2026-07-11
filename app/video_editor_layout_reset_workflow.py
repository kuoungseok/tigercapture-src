from __future__ import annotations

from PySide6.QtCore import QSettings

from app.video_editor_layout_specs import (
    COLOR_TIMELINE_SPLITTER_SETTINGS_KEY,
    EDITOR_VERTICAL_SPLITTER_SETTINGS_KEY,
    LEFT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY,
    MAIN_DOCK_MAX_HEIGHT,
    MAIN_DOCK_SPLITTER_SETTINGS_KEY,
    RIGHT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY,
    TOP_WORKBENCH_SPLITTER_SETTINGS_KEY,
    VIEWER_TOP_STRETCH,
    WORKBENCH_TOP_STRETCH,
)


LAYOUT_SPLITTER_SETTINGS_KEYS = (
    MAIN_DOCK_SPLITTER_SETTINGS_KEY,
    EDITOR_VERTICAL_SPLITTER_SETTINGS_KEY,
    TOP_WORKBENCH_SPLITTER_SETTINGS_KEY,
    LEFT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY,
    RIGHT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY,
    COLOR_TIMELINE_SPLITTER_SETTINGS_KEY,
)


def _editor_settings() -> QSettings:
    return QSettings("TigerCapture", "TigerCapture")


def _remove_persisted_splitter_state() -> list[str]:
    removed: list[str] = []
    try:
        settings = _editor_settings()
    except Exception:
        return removed
    for key in LAYOUT_SPLITTER_SETTINGS_KEYS:
        try:
            settings.remove(key)
            removed.append(key)
        except Exception:
            continue
    try:
        settings.sync()
    except Exception:
        pass
    return removed


def _set_splitter_sizes(owner, attr: str, sizes: list[int]) -> bool:
    splitter = getattr(owner, attr, None)
    if splitter is None:
        return False
    try:
        splitter.setSizes(sizes)
        splitter.updateGeometry()
        return True
    except Exception:
        return False


def _reset_color_timeline_splitter(owner) -> bool:
    splitter = getattr(owner, "_color_timeline_splitter", None)
    if splitter is None:
        return False
    color_container = getattr(owner, "_color_container", None)
    timeline_height = int(getattr(owner, "_timeline_compact_default_height", 320))
    try:
        if color_container is not None and not color_container.isVisible():
            splitter.setSizes([0, timeline_height])
        else:
            splitter.setSizes([230, max(timeline_height, 300)])
        splitter.updateGeometry()
        return True
    except Exception:
        return False


def reset_editor_layout_to_default(self) -> dict[str, object]:
    """Reset editor splitters to the default resizable workspace proportions."""
    removed_keys = _remove_persisted_splitter_state()
    timeline_height = int(getattr(self, "_timeline_compact_default_height", 320))
    reset_splitters: list[str] = []

    if _set_splitter_sizes(self, "_main_dock_splitter", [188, 1240]):
        reset_splitters.append("main_dock")
    if _set_splitter_sizes(
        self,
        "_editor_vertical_splitter",
        [MAIN_DOCK_MAX_HEIGHT, timeline_height],
    ):
        reset_splitters.append("editor_vertical")
    if _set_splitter_sizes(
        self,
        "_top_work_splitter",
        [VIEWER_TOP_STRETCH * 120, WORKBENCH_TOP_STRETCH * 120],
    ):
        reset_splitters.append("top_workbench")
    if _set_splitter_sizes(self, "_left_dock_sections_splitter", [520, 260]):
        reset_splitters.append("left_dock_sections")
    if _set_splitter_sizes(self, "_right_dock_sections_splitter", [540, 260]):
        reset_splitters.append("right_dock_sections")
    if _reset_color_timeline_splitter(self):
        reset_splitters.append("color_timeline")

    for attr in (
        "_main_dock_splitter",
        "_editor_vertical_splitter",
        "_top_work_splitter",
        "_left_dock_sections_splitter",
        "_right_dock_sections_splitter",
        "_color_timeline_splitter",
    ):
        widget = getattr(self, attr, None)
        if widget is None:
            continue
        try:
            widget.update()
        except Exception:
            pass

    refresh = getattr(self, "_refresh_command_bar_responsive", None)
    if callable(refresh):
        try:
            refresh()
        except Exception:
            pass
    flash = getattr(self, "_flash_status", None)
    if callable(flash):
        try:
            flash("Editor layout reset")
        except Exception:
            pass

    return {
        "ok": bool(reset_splitters),
        "reset_splitters": reset_splitters,
        "removed_settings": removed_keys,
    }


__all__ = [
    "LAYOUT_SPLITTER_SETTINGS_KEYS",
    "reset_editor_layout_to_default",
]

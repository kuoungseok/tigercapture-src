"""Persistent presentation state for Painter UI Design side panels."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings


SETTINGS_ORG = "TigerCapture"
SETTINGS_APP = "TigerCapture"
SETTINGS_GROUP = "painter/ui_design/panels"

DEFAULT_PANEL_STATE = {
    "navigator_width": 168,
    "navigator_collapsed": False,
    "navigator_auto_hide": False,
    "navigator_user_override": False,
    "inspector_width": 268,
    "inspector_collapsed": True,
    "inspector_auto_hide": True,
}

NAVIGATOR_MIN_WIDTH = 112
INSPECTOR_MIN_WIDTH = 180
PERSISTED_PANEL_MAX_WIDTH = 16777215


def _bool_value(value: Any, fallback: bool) -> bool:
    if value is None:
        return bool(fallback)
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def load_painter_ui_panel_state(
    settings: QSettings | None = None,
) -> dict[str, int | bool]:
    store = settings or QSettings(SETTINGS_ORG, SETTINGS_APP)
    store.beginGroup(SETTINGS_GROUP)
    try:
        navigator_width = max(
            NAVIGATOR_MIN_WIDTH,
            min(
                PERSISTED_PANEL_MAX_WIDTH,
                int(
                    store.value(
                        "navigator_width",
                        DEFAULT_PANEL_STATE["navigator_width"],
                    )
                ),
            ),
        )
        inspector_width = max(
            INSPECTOR_MIN_WIDTH,
            min(
                PERSISTED_PANEL_MAX_WIDTH,
                int(
                    store.value(
                        "inspector_width",
                        DEFAULT_PANEL_STATE["inspector_width"],
                    )
                ),
            ),
        )
        navigator_user_override = _bool_value(
            store.value("navigator_user_override", None),
            bool(DEFAULT_PANEL_STATE["navigator_user_override"]),
        )
        navigator_collapsed = _bool_value(
            store.value("navigator_collapsed", None),
            bool(DEFAULT_PANEL_STATE["navigator_collapsed"]),
        )
        navigator_auto_hide = _bool_value(
            store.value("navigator_auto_hide", None),
            bool(DEFAULT_PANEL_STATE["navigator_auto_hide"]),
        )
        if not navigator_user_override:
            navigator_width = int(DEFAULT_PANEL_STATE["navigator_width"])
            navigator_collapsed = bool(
                DEFAULT_PANEL_STATE["navigator_collapsed"]
            )
            navigator_auto_hide = bool(
                DEFAULT_PANEL_STATE["navigator_auto_hide"]
            )
        return {
            "navigator_width": navigator_width,
            "navigator_collapsed": navigator_collapsed,
            "navigator_auto_hide": navigator_auto_hide,
            "navigator_user_override": navigator_user_override,
            "inspector_width": inspector_width,
            "inspector_collapsed": _bool_value(
                store.value("inspector_collapsed", None),
                bool(DEFAULT_PANEL_STATE["inspector_collapsed"]),
            ),
            "inspector_auto_hide": _bool_value(
                store.value("inspector_auto_hide", None),
                bool(DEFAULT_PANEL_STATE["inspector_auto_hide"]),
            ),
        }
    finally:
        store.endGroup()


def save_painter_ui_panel_state(
    changes: dict[str, int | bool],
    settings: QSettings | None = None,
) -> dict[str, int | bool]:
    store = settings or QSettings(SETTINGS_ORG, SETTINGS_APP)
    current = load_painter_ui_panel_state(store)
    for key, value in changes.items():
        if key in current:
            current[key] = value
    current["navigator_width"] = max(
        NAVIGATOR_MIN_WIDTH,
        min(PERSISTED_PANEL_MAX_WIDTH, int(current["navigator_width"])),
    )
    current["inspector_width"] = max(
        INSPECTOR_MIN_WIDTH,
        min(PERSISTED_PANEL_MAX_WIDTH, int(current["inspector_width"])),
    )
    current["navigator_collapsed"] = bool(
        current["navigator_collapsed"]
    )
    current["navigator_auto_hide"] = bool(
        current["navigator_auto_hide"]
    )
    current["navigator_user_override"] = bool(
        current["navigator_user_override"]
    )
    current["inspector_collapsed"] = bool(
        current["inspector_collapsed"]
    )
    current["inspector_auto_hide"] = bool(
        current["inspector_auto_hide"]
    )
    store.beginGroup(SETTINGS_GROUP)
    try:
        for key, value in current.items():
            store.setValue(key, value)
    finally:
        store.endGroup()
    store.sync()
    return dict(current)


__all__ = [
    "DEFAULT_PANEL_STATE",
    "INSPECTOR_MIN_WIDTH",
    "NAVIGATOR_MIN_WIDTH",
    "PERSISTED_PANEL_MAX_WIDTH",
    "SETTINGS_APP",
    "SETTINGS_GROUP",
    "SETTINGS_ORG",
    "load_painter_ui_panel_state",
    "save_painter_ui_panel_state",
]

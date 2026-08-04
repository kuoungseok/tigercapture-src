"""Official Figma-style Select layer submenu for Painter UI canvas."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from PySide6.QtWidgets import QMenu

from app.icons import app_icon
from app.painter_i18n import painter_text
from app.painter_ui_selection_navigation import ui_select_layer_rows


def _layer_icon_name(row: Mapping[str, Any]) -> str:
    if bool(row.get("locked")):
        return "lock"
    return {
        "frame": "ui-frame",
        "group": "group",
        "text": "caption",
        "image": "image",
        "ellipse": "ellipse",
        "line": "line",
        "button": "button",
        "progress": "progress",
    }.get(str(row.get("kind") or ""), "rectangle")


def add_ui_select_layer_menu(
    menu: QMenu,
    document: Mapping[str, Any] | None,
    hit_object_ids: Sequence[str],
    on_select: Callable[[str], None],
) -> QMenu | None:
    rows = ui_select_layer_rows(document, tuple(hit_object_ids))
    if not rows:
        return None
    submenu = menu.addMenu(painter_text("Select layer"))
    submenu.setObjectName("PainterUISelectLayerMenu")
    for row in rows:
        object_id = str(row["id"])
        action = submenu.addAction(
            app_icon(_layer_icon_name(row), size=14, color="#E4E8EE"),
            str(row.get("name") or object_id),
        )
        action.setData(object_id)
        action.setProperty("painter_ui_locked_layer", bool(row.get("locked")))
        action.setProperty("painter_ui_kind", str(row.get("kind") or ""))
        action.triggered.connect(
            lambda _checked=False, target=object_id: on_select(target)
        )
        if bool(row.get("locked")):
            action.setToolTip(painter_text("Locked layer"))
        action.setIconVisibleInMenu(True)
        action.setProperty("painter_ui_layer_order", len(submenu.actions()) - 1)
    submenu.menuAction().setData("select_layer")
    submenu.menuAction().setProperty(
        "painter_ui_hit_count",
        len(rows),
    )
    return submenu


__all__ = ["add_ui_select_layer_menu"]

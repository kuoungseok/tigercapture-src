"""Canonical command/state adapter for the Painter UI logo menu.

The logo menu must operate on the UI document directly.  Reusing the paint
workspace menus made commands appear disabled in UI Design mode and also
mixed raster-layer semantics with UI-object semantics.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QSettings


def _document(owner: Any) -> dict:
    return getattr(owner, "_painter_ui_document", None) or {}


def _selection(owner: Any) -> tuple[list[str], list[dict]]:
    document = _document(owner)
    ids = [str(value) for value in (document.get("selection") or {}).get("object_ids", [])]
    selected = set(ids)
    rows = [row for row in document.get("objects", []) if str(row.get("id")) in selected]
    return ids, rows


def _primary(owner: Any) -> dict | None:
    document = _document(owner)
    object_id = str((document.get("selection") or {}).get("object_id") or "")
    return next((row for row in document.get("objects", []) if row.get("id") == object_id), None)


def _active_artboard(owner: Any) -> dict | None:
    document = _document(owner)
    target = str(document.get("active_artboard_id") or "")
    return next((row for row in document.get("artboards", []) if row.get("id") == target), None)


def _preference(key: str, default: bool = False) -> bool:
    return bool(QSettings().value(f"painter/ui_menu/{key}", default, type=bool))


def _toggle_preference(owner: Any, key: str, default: bool = False) -> None:
    settings = QSettings()
    value = not bool(settings.value(f"painter/ui_menu/{key}", default, type=bool))
    settings.setValue(f"painter/ui_menu/{key}", value)
    setattr(owner, f"_painter_ui_pref_{key}", value)


def _select_all(owner: Any) -> None:
    document = _document(owner)
    artboard_id = str(document.get("active_artboard_id") or "")
    ids = [str(row["id"]) for row in document.get("objects", []) if row.get("artboard_id") == artboard_id]
    owner._set_painter_ui_selection(ids, ids[-1] if ids else "")


def _select_inverse(owner: Any) -> None:
    document = _document(owner)
    selected, _rows = _selection(owner)
    selected_set = set(selected)
    artboard_id = str(document.get("active_artboard_id") or "")
    ids = [
        str(row["id"])
        for row in document.get("objects", [])
        if row.get("artboard_id") == artboard_id and str(row["id"]) not in selected_set
    ]
    owner._set_painter_ui_selection(ids, ids[-1] if ids else "")


def _group(owner: Any) -> None:
    ids, _rows = _selection(owner)
    owner._group_painter_ui_objects(ids)


def _ungroup(owner: Any) -> None:
    row = _primary(owner)
    if row is None:
        return
    from app.painter_ui_boolean import is_ui_boolean_group, release_ui_boolean

    if is_ui_boolean_group(row):
        document = release_ui_boolean(_document(owner), str(row["id"]))
        owner._commit_painter_ui_service_document(document, "Release UI Boolean")
        return
    owner._ungroup_painter_ui_object(str(row["id"]))


def _reorder(owner: Any, command: str) -> None:
    ids, _rows = _selection(owner)
    owner._reorder_painter_ui_objects(ids, command)


def _align(owner: Any, command: str) -> None:
    owner._align_painter_ui_object("", command)


def _text_style(owner: Any, key: str, value: object | None = None) -> None:
    ids, rows = _selection(owner)
    changes: dict[str, dict] = {}
    for row in rows:
        if row.get("kind") != "text":
            continue
        style = dict(row.get("style") or {})
        if value is None:
            style[key] = not bool(style.get(key, False))
        elif key == "font_weight" and value == "toggle":
            style[key] = 400 if int(style.get(key) or 400) >= 600 else 700
        else:
            style[key] = value
        changes[str(row["id"])] = {"style": style}
    owner._update_painter_ui_objects_batch(changes, label="Format UI text")


def _text_case(owner: Any, mode: str) -> None:
    _ids, rows = _selection(owner)
    changes: dict[str, dict] = {}
    for row in rows:
        if row.get("kind") != "text":
            continue
        content = dict(row.get("content") or {})
        text = str(content.get("text") or "")
        content["text"] = text.upper() if mode == "upper" else text.lower() if mode == "lower" else text
        changes[str(row["id"])] = {"content": content}
    owner._update_painter_ui_objects_batch(changes, label="Change UI text case")


def _flip(owner: Any, horizontal: bool) -> None:
    _ids, rows = _selection(owner)
    if not rows:
        return
    min_x = min(float(row["x"]) for row in rows)
    min_y = min(float(row["y"]) for row in rows)
    max_x = max(float(row["x"]) + float(row["width"]) for row in rows)
    max_y = max(float(row["y"]) + float(row["height"]) for row in rows)
    changes: dict[str, dict] = {}
    for row in rows:
        if horizontal:
            changes[str(row["id"])] = {
                "x": min_x + max_x - float(row["x"]) - float(row["width"]),
                "rotation": -float(row.get("rotation") or 0.0),
            }
        else:
            changes[str(row["id"])] = {
                "y": min_y + max_y - float(row["y"]) - float(row["height"]),
                "rotation": 180.0 - float(row.get("rotation") or 0.0),
            }
    owner._update_painter_ui_objects_batch(changes, label="Flip UI selection")


def _create_component(owner: Any) -> None:
    row = _primary(owner)
    if row is not None:
        owner._create_painter_ui_component(str(row["id"]), str(row.get("name") or "Component"))


def _detach_instance(owner: Any) -> None:
    row = _primary(owner)
    if row is not None and row.get("component_role") == "instance":
        owner._detach_painter_ui_component(str(row["id"]), False, "")


def _reset_instance(owner: Any) -> None:
    row = _primary(owner)
    if row is not None and row.get("component_role") == "instance":
        owner._reset_all_painter_ui_component_overrides(str(row["id"]))


def _wrap_section(owner: Any) -> None:
    ids, rows = _selection(owner)
    if not ids:
        return
    min_x = min(float(row["x"]) for row in rows)
    min_y = min(float(row["y"]) for row in rows)
    max_x = max(float(row["x"]) + float(row["width"]) for row in rows)
    max_y = max(float(row["y"]) + float(row["height"]) for row in rows)
    owner._update_painter_ui_section(
        "create",
        "",
        {
            "name": "Section",
            "artboard_id": str(_document(owner).get("active_artboard_id") or ""),
            "object_ids": ids,
            "x": min_x - 24.0,
            "y": min_y - 48.0,
            "width": max_x - min_x + 48.0,
            "height": max_y - min_y + 72.0,
        },
    )


def _toggle_guides(owner: Any) -> None:
    from app.painter_ui_artboard_layout import normalize_ui_artboard_layout

    artboard = _active_artboard(owner)
    if artboard is None:
        return
    guides = normalize_ui_artboard_layout(
        artboard,
        width=float(artboard["width"]),
        height=float(artboard["height"]),
    )["guides"]
    owner._set_painter_ui_guides_visible(not bool(guides.get("visible", True)))


def _toggle_view_option(owner: Any, key: str, default: bool) -> None:
    attribute = f"_painter_ui_{key}"
    value = not bool(getattr(owner, attribute, default))
    setattr(owner, attribute, value)
    overlay = getattr(owner, "_painter_ui_overlay", None)
    if overlay is not None and hasattr(overlay, "set_view_options"):
        overlay.set_view_options(**{key: value})


def _boolean(owner: Any, operation: str) -> None:
    from app.painter_ui_boolean import compose_ui_boolean

    ids, _rows = _selection(owner)
    if len(ids) < 2:
        return
    document, _row = compose_ui_boolean(_document(owner), operation, ids)
    owner._commit_painter_ui_service_document(document, "Create UI Boolean group")


def _flatten_boolean(owner: Any) -> None:
    from app.painter_ui_boolean import flatten_ui_boolean, is_ui_boolean_group

    row = _primary(owner)
    if row is None or not is_ui_boolean_group(row):
        return
    document, _flattened = flatten_ui_boolean(
        _document(owner),
        str(row["id"]),
    )
    owner._commit_painter_ui_service_document(document, "Flatten UI Boolean")


def build_painter_ui_menu_callbacks(owner: Any) -> dict[str, Callable[[], None]]:
    """Return UI-design commands bound to the owning Painter dialog."""
    return {
        "undo": owner._undo,
        "redo": owner._redo,
        "copy_properties": owner._copy_painter_ui_object_payload,
        "paste_properties": owner._paste_painter_ui_object_properties,
        "paste_in_place": owner._paste_painter_ui_object_in_place,
        "paste_replace": owner._paste_replace_painter_ui_objects,
        "duplicate": owner._duplicate_painter_ui_object,
        "delete": owner._delete_painter_ui_selection,
        "find": owner._show_painter_ui_find_replace,
        "find_next": owner._show_painter_ui_find_replace,
        "find_previous": owner._show_painter_ui_find_replace,
        "select_all": lambda: _select_all(owner),
        "select_none": lambda: owner._set_painter_ui_selection([], ""),
        "select_inverse": lambda: _select_inverse(owner),
        "select_same_kind": lambda: owner._select_similar_painter_ui_objects(criterion="kind"),
        "select_parent": owner._select_parent_painter_ui_object,
        "group": lambda: _group(owner),
        "ungroup": lambda: _ungroup(owner),
        "wrap_section": lambda: _wrap_section(owner),
        "component": lambda: _create_component(owner),
        "reset_instance": lambda: _reset_instance(owner),
        "detach_instance": lambda: _detach_instance(owner),
        "front": lambda: _reorder(owner, "front"),
        "forward": lambda: _reorder(owner, "forward"),
        "backward": lambda: _reorder(owner, "backward"),
        "back": lambda: _reorder(owner, "back"),
        "flip_h": lambda: _flip(owner, True),
        "flip_v": lambda: _flip(owner, False),
        "align_left": lambda: _align(owner, "left"),
        "align_hcenter": lambda: _align(owner, "hcenter"),
        "align_right": lambda: _align(owner, "right"),
        "align_top": lambda: _align(owner, "top"),
        "align_vcenter": lambda: _align(owner, "vcenter"),
        "align_bottom": lambda: _align(owner, "bottom"),
        "distribute_h": lambda: _align(owner, "distribute_h"),
        "distribute_v": lambda: _align(owner, "distribute_v"),
        "tidy": owner._tidy_painter_ui_selection,
        "bold": lambda: _text_style(owner, "font_weight", "toggle"),
        "italic": lambda: _text_style(owner, "italic"),
        "underline": lambda: _text_style(owner, "underline"),
        "strike": lambda: _text_style(owner, "strikethrough"),
        "text_left": lambda: _text_style(owner, "text_align", "left"),
        "text_center": lambda: _text_style(owner, "text_align", "center"),
        "text_right": lambda: _text_style(owner, "text_align", "right"),
        "uppercase": lambda: _text_case(owner, "upper"),
        "lowercase": lambda: _text_case(owner, "lower"),
        "toggle_guides": lambda: _toggle_guides(owner),
        "toggle_pixel_grid": lambda: _toggle_view_option(owner, "pixel_grid", False),
        "toggle_layout_guides": lambda: _toggle_view_option(owner, "layout_guides", True),
        "toggle_pixel_preview": lambda: _toggle_view_option(owner, "pixel_preview", False),
        "toggle_layer_outlines": lambda: _toggle_view_option(owner, "layer_outlines", False),
        "toggle_outline_hidden": lambda: _toggle_view_option(owner, "outline_include_hidden", False),
        "toggle_outline_bounds": lambda: _toggle_view_option(owner, "outline_include_bounds", False),
        "toggle_umg_widget_view": (
            lambda checked=False: owner._set_painter_umg_widget_view_enabled(
                bool(checked)
            )
        ),
        "toggle_snap": lambda: owner._set_painter_ui_snap(not bool(getattr(owner, "_painter_ui_snap_enabled", True))),
        "zoom_in": owner._view_zoom_in,
        "zoom_out": owner._view_zoom_out,
        "zoom_100": owner._view_zoom_100,
        "fit_all": lambda: owner._fit_painter_ui_view("all"),
        "fit_selection": lambda: owner._fit_painter_ui_view("selection"),
        "toggle_navigator": owner._toggle_painter_ui_navigator,
        "toggle_inspector": owner._toggle_painter_ui_inspector,
        "boolean_union": lambda: _boolean(owner, "union"),
        "boolean_subtract": lambda: _boolean(owner, "subtract"),
        "boolean_intersect": lambda: _boolean(owner, "intersect"),
        "boolean_exclude": lambda: _boolean(owner, "exclude"),
        "boolean_flatten": lambda: _flatten_boolean(owner),
        "convert_vector": owner._convert_painter_ui_selection_to_vector,
        "pref_highlight_layers": lambda: _toggle_preference(owner, "highlight_layers", True),
        "pref_rename_duplicates": lambda: _toggle_preference(owner, "rename_duplicates", True),
        "pref_show_dimensions": lambda: _toggle_preference(owner, "show_dimensions", True),
        "pref_smart_quotes": lambda: _toggle_preference(owner, "smart_quotes", True),
        "pref_scroll_zoom": lambda: _toggle_preference(owner, "scroll_zoom", False),
        "pref_right_drag_pan": lambda: _toggle_preference(owner, "right_drag_pan", False),
    }


def painter_ui_menu_state(owner: Any) -> dict[str, bool]:
    ids, rows = _selection(owner)
    primary = _primary(owner)
    from app.painter_ui_artboard_layout import normalize_ui_artboard_layout

    artboard = _active_artboard(owner)
    guides_visible = True
    if artboard is not None:
        guides_visible = bool(
            normalize_ui_artboard_layout(
                artboard,
                width=float(artboard["width"]),
                height=float(artboard["height"]),
            )["guides"].get("visible", True)
        )
    from app.painter_ui_boolean import is_ui_boolean_group

    return {
        "has_selection": bool(ids),
        "multi_selection": len(ids) >= 2,
        "three_selection": len(ids) >= 3,
        "text_selection": any(row.get("kind") == "text" for row in rows),
        "group_selection": bool(
            primary
            and (
                primary.get("kind") == "group"
                or is_ui_boolean_group(primary)
            )
        ),
        "boolean_group_selection": bool(
            primary and is_ui_boolean_group(primary)
        ),
        "instance_selection": bool(primary and primary.get("component_role") == "instance"),
        "can_undo": bool(getattr(owner, "_undo_stack", [])),
        "can_redo": bool(getattr(owner, "_redo_stack", [])),
        "has_clipboard": isinstance(getattr(owner, "_painter_ui_property_clipboard", None), dict),
        "guides_visible": guides_visible,
        "pixel_grid": bool(getattr(owner, "_painter_ui_pixel_grid", False)),
        "layout_guides": bool(getattr(owner, "_painter_ui_layout_guides", True)),
        "pixel_preview": bool(getattr(owner, "_painter_ui_pixel_preview", False)),
        "layer_outlines": bool(getattr(owner, "_painter_ui_layer_outlines", False)),
        "outline_include_hidden": bool(getattr(owner, "_painter_ui_outline_include_hidden", False)),
        "outline_include_bounds": bool(getattr(owner, "_painter_ui_outline_include_bounds", False)),
        "umg_widget_view": bool(
            getattr(owner, "_painter_umg_widget_view", None)
            and getattr(owner, "_painter_umg_widget_view").isVisible()
        ),
        "snap_enabled": bool(getattr(owner, "_painter_ui_snap_enabled", True)),
        "navigator_visible": bool(
            getattr(owner, "_painter_ui_navigator", None)
            and not getattr(owner, "_painter_ui_navigator").is_collapsed()
        ),
        "inspector_visible": bool(
            getattr(owner, "_paint_ui_inspector", None)
            and not getattr(owner, "_paint_ui_inspector").is_collapsed()
        ),
        "pref_highlight_layers": _preference("highlight_layers", True),
        "pref_rename_duplicates": _preference("rename_duplicates", True),
        "pref_show_dimensions": _preference("show_dimensions", True),
        "pref_smart_quotes": _preference("smart_quotes", True),
        "pref_scroll_zoom": _preference("scroll_zoom", False),
        "pref_right_drag_pan": _preference("right_drag_pan", False),
    }


__all__ = ["build_painter_ui_menu_callbacks", "painter_ui_menu_state"]

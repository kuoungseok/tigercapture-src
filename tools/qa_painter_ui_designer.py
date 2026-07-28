"""Create a reproducible Painter UI Designer M1 workspace proof."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "debugCapture" / "painter_ui_designer_m1"),
    )
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if not args.show:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1360, 900)
    registry = ActionRegistry(owner=dialog)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    last_add = None
    phone_object_ids: dict[str, str] = {}
    for payload in (
        {
            "kind": "frame",
            "name": "Product Card",
            "x": 28,
            "y": 110,
            "width": 334,
            "height": 590,
            "style": {"fill": "#202B38", "stroke": "#53657C"},
        },
        {
            "kind": "image",
            "name": "Product Image",
            "x": 50,
            "y": 138,
            "width": 290,
            "height": 210,
            "style": {"fill": "#17202B", "stroke": "#63748A"},
        },
        {
            "kind": "ellipse",
            "name": "New Badge",
            "x": 292,
            "y": 126,
            "width": 54,
            "height": 54,
            "style": {"fill": "#C98E4F", "text_color": "#15191F"},
            "content": {"text": "NEW"},
        },
        {
            "kind": "text",
            "name": "Product Title",
            "x": 52,
            "y": 378,
            "width": 286,
            "height": 54,
            "style": {"text_color": "#F2F5F9", "font_size": 17},
            "content": {"text": "Studio Headphones"},
        },
        {
            "kind": "line",
            "name": "Title Divider",
            "x": 52,
            "y": 445,
            "width": 286,
            "height": 10,
            "style": {"fill": "#63748A", "stroke_width": 2},
        },
        {
            "kind": "rectangle",
            "name": "Availability",
            "x": 52,
            "y": 474,
            "width": 132,
            "height": 42,
            "style": {"fill": "#304458", "stroke": "#526B82", "radius": 4},
            "content": {"text": "Ready to ship"},
        },
        {
            "kind": "progress",
            "name": "Stock Level",
            "x": 52,
            "y": 542,
            "width": 286,
            "height": 20,
            "style": {"fill": "#263344", "accent": "#75A7DD"},
            "content": {"value": 0.72},
        },
        {
            "kind": "button",
            "name": "Add to Cart",
            "x": 52,
            "y": 596,
            "width": 286,
            "height": 58,
            "style": {"fill": "#4C74DB", "stroke": "#7091E7", "radius": 6},
            "content": {"text": "Add to Cart"},
        },
    ):
        last_add = registry.execute("paint.ui.object.add", payload).to_dict()
        phone_object_ids[str(payload["kind"])] = str(
            last_add["result"]["ui_design"]["selected_object_id"]
        )
    desktop_added = registry.execute(
        "paint.ui.artboard.add",
        {"name": "Desktop", "width": 1440, "height": 900, "breakpoint": "desktop"},
    ).to_dict()
    desktop_id = str(
        desktop_added["result"]["ui_design"]["active_artboard_id"]
    )
    desktop_object_ids = []
    for payload in (
        {
            "kind": "frame",
            "name": "Dashboard Panel",
            "artboard_id": desktop_id,
            "x": 120,
            "y": 130,
            "width": 1200,
            "height": 640,
            "style": {"fill": "#202B38", "stroke": "#53657C"},
        },
        {
            "kind": "rectangle",
            "name": "Metric A",
            "artboard_id": desktop_id,
            "x": 190,
            "y": 230,
            "width": 260,
            "height": 150,
            "style": {"fill": "#304458", "stroke": "#65809A"},
        },
        {
            "kind": "rectangle",
            "name": "Metric B",
            "artboard_id": desktop_id,
            "x": 590,
            "y": 280,
            "width": 260,
            "height": 150,
            "style": {"fill": "#385568", "stroke": "#6D91A7"},
        },
        {
            "kind": "rectangle",
            "name": "Metric C",
            "artboard_id": desktop_id,
            "x": 990,
            "y": 330,
            "width": 260,
            "height": 150,
            "style": {"fill": "#455A70", "stroke": "#7B8FA8"},
        },
    ):
        added = registry.execute("paint.ui.object.add", payload).to_dict()
        desktop_object_ids.append(
            str(added["result"]["ui_design"]["selected_object_id"])
        )
    registry.execute(
        "paint.ui.selection.set",
        {
            "object_ids": desktop_object_ids[1:],
            "primary_object_id": desktop_object_ids[-1],
        },
    )
    registry.execute("paint.ui.object.arrange", {"command": "top"})
    registry.execute("paint.ui.object.arrange", {"command": "distribute_h"})
    registry.execute("paint.ui.artboard.activate", {"artboard_id": "artboard-1"})
    button_id = str(
        (((last_add or {}).get("result") or {}).get("ui_design") or {}).get(
            "selected_object_id"
        )
        or ""
    )
    if button_id:
        registry.execute(
            "paint.ui.object.update",
            {"object_id": button_id, "changes": {"rotation": -4.0}},
        )
    dialog.show()
    app.processEvents()

    def select_inspector_tab(label: str) -> None:
        tabs = dialog._paint_ui_inspector._tabs
        for index in range(tabs.count()):
            if tabs.tabWhatsThis(index) == label:
                tabs.setCurrentIndex(index)
                return

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_dir / "painter_ui_designer_m1.png"
    dialog.grab().save(str(screenshot_path), "PNG")
    select_inspector_tab("Design")
    app.processEvents()
    inspect_screenshot_path = output_dir / "painter_ui_designer_m1_inspect.png"
    dialog.grab().save(str(inspect_screenshot_path), "PNG")
    registry.execute("paint.ui.artboard.activate", {"artboard_id": desktop_id})
    registry.execute(
        "paint.ui.guide.create",
        {
            "artboard_id": desktop_id,
            "orientation": "vertical",
            "position": 720,
        },
    )
    registry.execute(
        "paint.ui.guide.create",
        {
            "artboard_id": desktop_id,
            "orientation": "horizontal",
            "position": 450,
        },
    )
    registry.execute(
        "paint.ui.ruler.origin.set",
        {"artboard_id": desktop_id, "x": 120, "y": 130},
    )
    registry.execute(
        "paint.ui.selection.set",
        {
            "object_ids": desktop_object_ids[1:],
            "primary_object_id": desktop_object_ids[-1],
        },
    )
    select_inspector_tab("Design")
    app.processEvents()
    desktop_screenshot_path = output_dir / "painter_ui_designer_m1_desktop.png"
    dialog.grab().save(str(desktop_screenshot_path), "PNG")
    grouped = registry.execute(
        "paint.ui.object.group",
        {
            "object_ids": desktop_object_ids[1:],
            "name": "Metrics Group",
        },
    ).to_dict()
    group_id = str(grouped["result"]["ui_design"]["selected_object_id"])
    registry.execute(
        "paint.ui.object.reparent",
        {
            "object_ids": [desktop_object_ids[1]],
            "placement": "root",
        },
    )
    dialog._paint_ui_inspector.hierarchy_drop_requested.emit(
        [desktop_object_ids[1]],
        group_id,
        "inside",
    )
    app.processEvents()
    hierarchy_screenshot_path = (
        output_dir / "painter_ui_designer_m1_hierarchy.png"
    )
    dialog.grab().save(str(hierarchy_screenshot_path), "PNG")
    dialog._paint_ui_inspector.set_auto_hide(False)
    registry.execute(
        "paint.ui.selection.set",
        {
            "object_ids": [desktop_object_ids[1]],
            "primary_object_id": desktop_object_ids[1],
        },
    )
    app.processEvents()
    breadcrumb = dialog._painter_ui_selection_breadcrumb
    breadcrumb_ok = (
        breadcrumb.isVisible()
        and breadcrumb.layout().count() >= 3
    )
    breadcrumb_screenshot_path = (
        output_dir / "painter_ui_designer_m1_breadcrumb.png"
    )
    dialog.grab().save(str(breadcrumb_screenshot_path), "PNG")
    parent_selected = registry.execute(
        "paint.ui.selection.parent",
        {"object_id": desktop_object_ids[1]},
    ).to_dict()
    deep_selected = registry.execute(
        "paint.ui.selection.deep_select",
        {"object_id": group_id},
    ).to_dict()
    hierarchy_navigation_ok = (
        parent_selected.get("ok") is True
        and parent_selected["result"]["selection_navigation"][
            "selected_object_id"
        ] == group_id
        and deep_selected.get("ok") is True
        and bool(
            deep_selected["result"]["selection_navigation"][
                "selected_object_id"
            ]
        )
    )
    scope_entered = registry.execute(
        "paint.ui.selection.scope.enter",
        {"object_id": group_id},
    ).to_dict()
    app.processEvents()
    scope_ok = (
        scope_entered.get("ok") is True
        and scope_entered["result"]["selection_scope"]["scope_id"]
        == group_id
        and dialog._painter_ui_overlay.edit_scope_id() == group_id
    )
    scope_screenshot_path = (
        output_dir / "painter_ui_designer_m1_group_scope.png"
    )
    dialog.grab().save(str(scope_screenshot_path), "PNG")
    scope_exited = registry.execute(
        "paint.ui.selection.scope.exit",
        {},
    ).to_dict()
    scope_ok = (
        scope_ok
        and scope_exited.get("ok") is True
        and not scope_exited["result"]["selection_scope"]["scope_id"]
        and not dialog._painter_ui_overlay.edit_scope_id()
    )
    navigator = dialog._painter_ui_navigator
    navigator.set_collapsed(False, user_initiated=True)
    navigator.set_expanded_width(
        navigator.DEFAULT_EXPANDED_WIDTH,
        user_initiated=True,
    )
    app.processEvents()
    navigator_screenshot_path = (
        output_dir / "painter_ui_designer_m1_navigator.png"
    )
    dialog.grab().save(str(navigator_screenshot_path), "PNG")
    dialog._set_painter_ui_inspector_width(340, user_initiated=True)
    app.processEvents()
    inspector_resized_screenshot_path = (
        output_dir / "painter_ui_designer_m1_inspector_resized.png"
    )
    dialog.grab().save(str(inspector_resized_screenshot_path), "PNG")
    dialog._detach_painter_ui_inspector()
    app.processEvents()
    inspector_detached_screenshot_path = (
        output_dir / "painter_ui_designer_m1_inspector_detached.png"
    )
    dialog._painter_ui_inspector_dock_window.grab().save(
        str(inspector_detached_screenshot_path),
        "PNG",
    )
    detached_round_trip = bool(dialog._painter_ui_inspector_detached)
    dialog._dock_painter_ui_inspector()
    app.processEvents()
    detached_round_trip = (
        detached_round_trip
        and not dialog._painter_ui_inspector_detached
        and dialog._paint_inspector_frame.isVisible()
    )
    registry.execute(
        "paint.ui.artboard.activate",
        {"artboard_id": "artboard-1"},
    )
    registry.execute(
        "paint.ui.selection.set",
        {
            "object_ids": [phone_object_ids["text"]],
            "primary_object_id": phone_object_ids["text"],
        },
    )
    app.processEvents()
    text_context_ok = (
        dialog._paint_ui_inspector.design_context() == "text"
        and dialog._paint_ui_inspector.design_group_visible("text")
        and not dialog._paint_ui_inspector.design_group_visible("image")
        and dialog._paint_ui_inspector.visible_context_tabs()
        == ("design", "prototype", "inspect")
        and dialog._paint_ui_inspector.artboard_bar.isHidden()
    )
    text_inspector_screenshot_path = (
        output_dir / "painter_ui_designer_m1_text_inspector.png"
    )
    dialog.grab().save(str(text_inspector_screenshot_path), "PNG")
    dialog._painter_ui_overlay.fit_object(phone_object_ids["text"])
    app.processEvents()
    inline_text_ok = dialog._painter_ui_overlay.begin_text_edit(
        phone_object_ids["text"]
    )
    app.processEvents()
    inline_text_editor = dialog._painter_ui_overlay._text_editor
    inline_text_ok = bool(
        inline_text_ok
        and inline_text_editor is not None
        and inline_text_editor.isVisible()
        and inline_text_editor.geometry().width() >= 80
        and inline_text_editor.geometry().height() >= 32
    )
    inline_text_screenshot_path = (
        output_dir / "painter_ui_designer_m1_inline_text.png"
    )
    dialog.grab().save(str(inline_text_screenshot_path), "PNG")
    dialog._painter_ui_overlay._finish_text_edit(commit=False)
    dialog._painter_ui_overlay.fit_all()
    app.processEvents()
    registry.execute(
        "paint.ui.selection.set",
        {
            "object_ids": [phone_object_ids["image"]],
            "primary_object_id": phone_object_ids["image"],
        },
    )
    app.processEvents()
    image_context_ok = (
        dialog._paint_ui_inspector.design_context() == "image"
        and dialog._paint_ui_inspector.design_group_visible("image")
        and not dialog._paint_ui_inspector.design_group_visible("text")
    )
    image_inspector_screenshot_path = (
        output_dir / "painter_ui_designer_m1_image_inspector.png"
    )
    dialog.grab().save(str(image_inspector_screenshot_path), "PNG")
    registry.execute(
        "paint.ui.selection.set",
        {
            "object_ids": [
                phone_object_ids["text"],
                phone_object_ids["image"],
            ],
            "primary_object_id": phone_object_ids["text"],
        },
    )
    app.processEvents()
    multi_context_ok = (
        dialog._paint_ui_inspector.design_context() == "multi"
        and dialog._paint_ui_inspector.design_group_visible(
            "multi_properties"
        )
        and dialog._paint_ui_inspector.design_group_visible("arrange")
        and not dialog._paint_ui_inspector.design_group_visible("geometry")
        and dialog._paint_ui_inspector.visible_context_tabs()
        == ("design", "inspect")
        and dialog._paint_ui_inspector.artboard_bar.isHidden()
    )
    multi_properties_ok = (
        dialog._paint_ui_inspector.multi_opacity_spin.value() == 100
        and dialog._paint_ui_inspector.multi_fill_edit.text() == ""
        and dialog._paint_ui_inspector.multi_fill_edit.placeholderText()
        == "—"
    )
    multi_rows = dialog._painter_ui_overlay._multi_transform_rows()
    multi_bounds = dialog._painter_ui_overlay._selection_bounds(
        multi_rows
    )
    multi_resize_ok = bool(
        len(multi_rows) == 2
        and not multi_bounds.isNull()
        and len(
            dialog._painter_ui_overlay._handle_rects(multi_bounds)
        )
        == 4
    )
    multi_inspector_screenshot_path = (
        output_dir / "painter_ui_designer_m1_multi_inspector.png"
    )
    dialog.grab().save(str(multi_inspector_screenshot_path), "PNG")
    registry.execute(
        "paint.ui.selection.set",
        {"object_ids": [], "primary_object_id": ""},
    )
    app.processEvents()
    adaptive_context_ok = (
        dialog._paint_ui_inspector.design_context() == "artboard"
        and dialog._paint_ui_inspector.visible_context_tabs()
        == ("design", "inspect")
        and not dialog._paint_ui_inspector.artboard_bar.isHidden()
    )
    dialog._paint_ui_inspector.set_collapsed(True)
    registry.execute(
        "paint.ui.selection.set",
        {
            "object_ids": [phone_object_ids["text"]],
            "primary_object_id": phone_object_ids["text"],
        },
    )
    app.processEvents()
    quick_properties = dialog._painter_ui_quick_properties
    quick_properties_ok = (
        quick_properties.isVisible()
        and quick_properties.contains(dialog._paint_ui_inspector)
        and dialog._paint_ui_inspector.is_temporary_expanded()
        and dialog._paint_inspector_frame.maximumWidth() == 36
    )
    quick_properties_screenshot_path = (
        output_dir / "painter_ui_designer_m1_quick_properties.png"
    )
    dialog.grab().save(str(quick_properties_screenshot_path), "PNG")
    dialog._paint_ui_inspector.set_collapsed(False)
    app.processEvents()
    toolbar = dialog._ui_design_tool_host
    toolbar.zoom_button.click()
    app.processEvents()
    zoom_popover_ok = (
        toolbar.zoom_popover.isVisible()
        and len(toolbar.view_buttons) == 3
        and all(
            button.parentWidget() is toolbar.zoom_popover
            for button in toolbar.view_buttons.values()
        )
        and toolbar.zoom_popover.geometry().bottom()
        < toolbar.geometry().top()
    )
    zoom_popover_screenshot_path = (
        output_dir / "painter_ui_designer_m1_zoom_popover.png"
    )
    dialog.grab().save(str(zoom_popover_screenshot_path), "PNG")
    toolbar.zoom_popover.hide()

    dialog.resize(1100, 720)
    app.processEvents()
    dialog._sync_ui_design_toolbar_density()
    toolbar.zoom_button.click()
    app.processEvents()
    compact_zoom_ok = (
        toolbar.zoom_popover.isVisible()
        and toolbar.zoom_popover.geometry().left() >= 0
        and toolbar.zoom_popover.geometry().right()
        <= dialog._canvas_host.width()
        and toolbar.zoom_popover.geometry().bottom()
        < toolbar.geometry().top()
    )
    compact_screenshot_path = (
        output_dir / "painter_ui_designer_m1_compact_zoom.png"
    )
    dialog.grab().save(str(compact_screenshot_path), "PNG")
    toolbar.zoom_popover.hide()
    dialog.resize(1360, 900)
    app.processEvents()
    state = dialog.painter_action_state()
    group_row = next(
        (
            row
            for row in state["ui_design"]["document"]["objects"]
            if row["id"] == group_id
        ),
        {},
    )
    hierarchy_child = next(
        (
            row
            for row in state["ui_design"]["document"]["objects"]
            if row["id"] == desktop_object_ids[1]
        ),
        {},
    )
    active_artboard = next(
        (
            row
            for row in state["ui_design"]["document"]["artboards"]
            if row["id"] == desktop_id
        ),
        {},
    )
    guide_state = dict(active_artboard.get("guides") or {})
    report = {
        "schema": "tigerstudio.painter.ui.qa.v1",
        "ok": (
            state["workspace"]["mode"] == "ui_design"
            and state["ui_design"]["validation"]["ok"]
            and state["ui_design"]["validation"]["object_count"] == 13
            and state["ui_design"]["validation"]["artboard_count"] == 2
            and group_row.get("kind") == "group"
            and grouped.get("ok") is True
            and hierarchy_child.get("parent_id") == group_id
            and guide_state.get("vertical") == [720.0]
            and guide_state.get("horizontal") == [450.0]
            and guide_state.get("origin") == {"x": 120.0, "y": 130.0}
            and screenshot_path.is_file()
            and inspect_screenshot_path.is_file()
            and desktop_screenshot_path.is_file()
            and hierarchy_screenshot_path.is_file()
            and breadcrumb_screenshot_path.is_file()
            and scope_screenshot_path.is_file()
            and navigator_screenshot_path.is_file()
            and inspector_resized_screenshot_path.is_file()
            and inspector_detached_screenshot_path.is_file()
            and text_inspector_screenshot_path.is_file()
            and inline_text_screenshot_path.is_file()
            and image_inspector_screenshot_path.is_file()
            and multi_inspector_screenshot_path.is_file()
            and quick_properties_screenshot_path.is_file()
            and zoom_popover_screenshot_path.is_file()
            and compact_screenshot_path.is_file()
            and detached_round_trip
            and text_context_ok
            and inline_text_ok
            and image_context_ok
            and multi_context_ok
            and multi_properties_ok
            and multi_resize_ok
            and adaptive_context_ok
            and quick_properties_ok
            and zoom_popover_ok
            and compact_zoom_ok
            and breadcrumb_ok
            and hierarchy_navigation_ok
            and scope_ok
            and navigator.expanded_width()
            == navigator.DEFAULT_EXPANDED_WIDTH
        ),
        "screenshot": str(screenshot_path),
        "inspect_screenshot": str(inspect_screenshot_path),
        "desktop_screenshot": str(desktop_screenshot_path),
        "hierarchy_screenshot": str(hierarchy_screenshot_path),
        "breadcrumb_screenshot": str(breadcrumb_screenshot_path),
        "group_scope_screenshot": str(scope_screenshot_path),
        "navigator_screenshot": str(navigator_screenshot_path),
        "inspector_resized_screenshot": str(
            inspector_resized_screenshot_path
        ),
        "inspector_detached_screenshot": str(
            inspector_detached_screenshot_path
        ),
        "text_inspector_screenshot": str(text_inspector_screenshot_path),
        "inline_text_screenshot": str(inline_text_screenshot_path),
        "image_inspector_screenshot": str(image_inspector_screenshot_path),
        "multi_inspector_screenshot": str(multi_inspector_screenshot_path),
        "quick_properties_screenshot": str(
            quick_properties_screenshot_path
        ),
        "zoom_popover_screenshot": str(zoom_popover_screenshot_path),
        "compact_zoom_screenshot": str(compact_screenshot_path),
        "navigator_width": navigator.expanded_width(),
        "inspector_width": dialog._paint_inspector_expanded_width,
        "inspector_detached_round_trip": detached_round_trip,
        "quick_properties_ok": quick_properties_ok,
        "zoom_popover_ok": zoom_popover_ok,
        "compact_zoom_ok": compact_zoom_ok,
        "breadcrumb_ok": breadcrumb_ok,
        "hierarchy_navigation_ok": hierarchy_navigation_ok,
        "group_scope_ok": scope_ok,
        "context_visibility": {
            "text": text_context_ok,
            "image": image_context_ok,
            "multi": multi_context_ok,
            "adaptive": adaptive_context_ok,
        },
        "inline_text_ok": inline_text_ok,
        "multi_properties_ok": multi_properties_ok,
        "multi_resize_ok": multi_resize_ok,
        "guide_state": guide_state,
        "workspace": state["workspace"],
        "ui_design": state["ui_design"],
    }
    report_path = output_dir / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}, indent=2))
    if args.show:
        dialog.raise_()
        dialog.activateWindow()
        return app.exec()
    QTimer.singleShot(0, dialog.close)
    app.processEvents()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

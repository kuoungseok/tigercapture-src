from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document() -> dict:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(640, 360, name="UMG Widget View")
    document, button = add_ui_object(
        document,
        kind="button",
        name="Continue",
        x=48,
        y=248,
        width=220,
        height=56,
        style={"fill": "#2F6FED"},
        content={"text": "Continue"},
    )
    document, _blocked = add_ui_object(
        document,
        kind="rectangle",
        name="Gradient card",
        x=320,
        y=48,
        width=240,
        height=160,
        style={
            # Keep this fixture as an explicit blocker while simple gradients
            # are now generated through the Custom-HLSL material path.
            "effects": [{"type": "blur", "radius": 8.0}],
            "fills": [
                {
                    "type": "linear",
                    "visible": True,
                    "stops": [
                        {"position": 0.0, "color": "#111827FF"},
                        {"position": 1.0, "color": "#2563EBFF"},
                    ],
                }
            ]
        },
    )
    document["selection"] = {
        "object_id": button["id"],
        "object_ids": [button["id"]],
    }
    return document


def _material_document() -> tuple[dict, str, str]:
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(640, 360, name="UMG Material Graph")
    document, button = add_ui_object(
        document,
        kind="button",
        name="Continue",
        x=48,
        y=248,
        width=220,
        height=56,
        style={"fill": "#2F6FED"},
        content={"text": "Continue"},
    )
    document, gradient = add_ui_object(
        document,
        kind="rectangle",
        name="Gradient card",
        x=320,
        y=48,
        width=240,
        height=160,
        style={
            "fills": [
                {
                    "type": "linear",
                    "visible": True,
                    "start": {"x": 0.0, "y": 0.5},
                    "end": {"x": 1.0, "y": 0.5},
                    "stops": [
                        {"position": 0.0, "color": "#111827FF"},
                        {"position": 1.0, "color": "#2563EBFF"},
                    ],
                }
            ]
        },
    )
    document["selection"] = {
        "object_id": gradient["id"],
        "object_ids": [gradient["id"]],
    }
    return document, button["id"], gradient["id"]


def _rounded_card_document() -> tuple[dict, str]:
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(640, 360, name="Rounded Card Graph")
    document, card = add_ui_object(
        document,
        kind="rectangle",
        name="Inventory Card",
        x=112,
        y=72,
        width=360,
        height=216,
        style={
            "fill": "#245DA8FF",
            "corner_radii": {
                "top_left": 30.0,
                "top_right": 8.0,
                "bottom_right": 24.0,
                "bottom_left": 12.0,
            },
            "corner_smoothing": 0.58,
            "strokes": [
                {
                    "type": "solid",
                    "visible": True,
                    "color": "#DCEBFFFF",
                    "width": 4.0,
                    "align": "inside",
                }
            ],
            "effects": [
                {
                    "type": "drop_shadow",
                    "color": "#00000088",
                    "x": 7.0,
                    "y": 9.0,
                    "blur": 12.0,
                    "spread": 2.0,
                },
                {
                    "type": "inner_shadow",
                    "color": "#07162966",
                    "x": 1.0,
                    "y": 2.0,
                    "blur": 5.0,
                    "spread": 1.0,
                },
            ],
        },
    )
    document["selection"] = {
        "object_id": card["id"],
        "object_ids": [card["id"]],
    }
    return document, card["id"]


def _nested_canvas_document() -> tuple[dict, str, str]:
    from app.painter_ui_constraints import (
        capture_ui_constraints,
        constraint_parent_geometry,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(640, 360, name="Nested UMG Widget View")
    document, panel = add_ui_object(
        document,
        kind="frame",
        name="HUD Panel",
        x=56,
        y=32,
        width=528,
        height=296,
        style={"fill": "#172033"},
    )
    document, panel = update_ui_object(
        document,
        panel["id"],
        {
            "layout": {
                **panel["layout"],
                "umg_panel_mode": "canvas",
            }
        },
    )
    document, button = add_ui_object(
        document,
        kind="button",
        name="Continue",
        parent_id=panel["id"],
        x=48,
        y=208,
        width=220,
        height=56,
        style={"fill": "#2F6FED"},
        content={"text": "Continue"},
    )
    row = next(
        item for item in document["objects"] if item["id"] == button["id"]
    )
    row["constraints"] = capture_ui_constraints(
        row,
        constraint_parent_geometry(document, row),
        {"horizontal": "right", "vertical": "bottom"},
    )
    document["selection"] = {
        "object_id": panel["id"],
        "object_ids": [panel["id"]],
    }
    return document, panel["id"], button["id"]


def _button_state_projection_document(
    *,
    enabled: bool = True,
) -> tuple[dict, str]:
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(640, 360, name="UMG Button States")
    states = {
        "normal": {
            "fill": "#1D4ED8FF",
            "stroke": "#60A5FAFF",
            "stroke_width": 1.0,
            "radius": 8.0,
            "text_color": "#FFFFFFFF",
            "font_size": 18.0,
        },
        "hovered": {
            "fill": "#2563EBFF",
            "stroke": "#93C5FDFF",
            "stroke_width": 2.0,
            "radius": 8.0,
            "text_color": "#FFFFFFFF",
            "font_size": 18.0,
        },
        "pressed": {
            "fill": "#1E40AFFF",
            "stroke": "#BFDBFEFF",
            "stroke_width": 2.0,
            "radius": 8.0,
            "text_color": "#FFFFFFFF",
            "font_size": 18.0,
        },
        "disabled": {
            "fill": "#475569FF",
            "stroke": "#64748BFF",
            "stroke_width": 1.0,
            "radius": 8.0,
            "opacity": 0.5,
            "text_color": "#CBD5E1FF",
            "font_size": 18.0,
        },
    }
    document, button = add_ui_object(
        document,
        kind="button",
        name="Continue",
        x=180,
        y=140,
        width=240,
        height=64,
        style=copy.deepcopy(states["normal"]),
        content={
            "text": "Continue",
            "umg_button_style": {
                "enabled": bool(enabled),
                "states": copy.deepcopy(states),
            },
        },
    )
    for row in document["objects"]:
        if row["id"] == button["id"]:
            row["locked"] = True
            row["opacity"] = 0.8
    return document, button["id"]


def _find_menu_action(menu, label: str):
    for action in menu.actions():
        if action.text() == label:
            return action
        submenu = action.menu()
        if submenu is not None:
            found = _find_menu_action(submenu, label)
            if found is not None:
                return found
    return None


def test_umg_widget_view_has_standard_desktop_chrome_and_can_grow() -> None:
    app = _app()
    from PySide6.QtCore import Qt

    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    view = PainterUMGWidgetView()
    view.show()
    app.processEvents()

    flags = view.windowFlags()
    assert flags & Qt.WindowType.Window
    assert flags & Qt.WindowType.WindowSystemMenuHint
    assert flags & Qt.WindowType.WindowMinimizeButtonHint
    assert flags & Qt.WindowType.WindowMaximizeButtonHint
    assert flags & Qt.WindowType.WindowCloseButtonHint

    before = view.size()
    view.resize(before.width() + 120, before.height() + 80)
    app.processEvents()
    assert view.width() >= before.width() + 120
    assert view.height() >= before.height() + 80
    view.close()


def test_umg_widget_view_projects_without_mutating_the_source() -> None:
    app = _app()
    from PySide6.QtWidgets import QFrame

    from app.painter_ui_umg_simulator import PAINTER_UMG_SIMULATOR_SCHEMA
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document = _document()
    original = copy.deepcopy(document)
    view = PainterUMGWidgetView()
    view.resize(980, 620)
    view.set_document(document)
    view.show()
    app.processEvents()

    report = view.report()
    assert report["schema"] == PAINTER_UMG_SIMULATOR_SCHEMA
    assert report["source"]["revision"] == document["revision"]
    assert len(report["widgets"]) == 3
    assert report["widgets"][0]["id"] == "__tiger_artboard_background"
    assert report["counts"]["Native"] == 2
    assert report["counts"]["Blocked"] == 1
    assert report["blockers"][0]["name"] == "Gradient card"
    from app.painter_i18n import painter_text

    assert (
        f"{painter_text('Background preserved')} #FFFFFFFF"
        in view.summary_label.text()
    )
    assert document == original
    assert view.objectName() == "PainterUMGWidgetView"
    assert view.findChild(QFrame, "PainterUMGSourcePreview") is not None
    assert view.findChild(QFrame, "PainterUMGTargetPreview") is not None
    selected_id = document["selection"]["object_id"]
    assert (
        view.source_pane.preview._document["selection"]["object_id"]
        == selected_id
    )
    assert (
        view.target_pane.preview._document["selection"]["object_id"]
        == selected_id
    )
    assert view.source_pane.preview.isEnabled()
    assert view.target_pane.preview.isEnabled()
    assert view.target_pane.preview._umg_selection_enabled is False
    assert view.target_pane.preview._umg_button_testing_enabled is True
    decorations = view.anchor_decoration()
    assert decorations["source"]["visible"] is True
    assert decorations["target"]["visible"] is True
    assert decorations["source"]["read_only"] is False
    assert decorations["target"]["read_only"] is True
    assert decorations["target"]["object_id"] == selected_id
    assert decorations["target"]["rendered"] is True
    assert (
        decorations["target"]["render_transform_pivot"]
        == report["widgets_by_id"][selected_id]["render_transform_pivot"]
    )
    controls = view.control_state()
    assert controls == {
        "object_id": selected_id,
        "enabled": True,
        "horizontal": "left",
        "vertical": "top",
        "pivot_x": 0.5,
        "pivot_y": 0.5,
        "x": 48.0,
        "y": 248.0,
        "width": 220.0,
        "height": 56.0,
    }

    view.set_view_state({"zoom_percent": 125.0})
    state = view.view_state()
    assert state["source"]["zoom_percent"] == 125.0
    assert state["target"]["zoom_percent"] == 125.0

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_maps_later_artboard_scene_origin_to_umg_origin() -> None:
    app = _app()
    import pytest

    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document, _report = instantiate_ui_template("mobile_onboarding")
    view = PainterUMGWidgetView()
    view.resize(1120, 720)
    view.set_document(document, artboard_id="artboard-2")
    view.show()
    app.processEvents()
    view.fit_views()
    app.processEvents()

    state = view.view_state()
    assert state["source"]["center_x"] == pytest.approx(665.0)
    assert state["target"]["center_x"] == pytest.approx(195.0)
    assert state["target"]["center_x"] == pytest.approx(
        state["source"]["center_x"] - 470.0
    )
    assert state["target"]["center_y"] == pytest.approx(
        state["source"]["center_y"]
    )
    assert state["target"]["zoom_percent"] == pytest.approx(
        state["source"]["zoom_percent"],
        abs=0.01,
    )

    source_artboard = next(
        row
        for row in view.source_pane.preview._document["artboards"]
        if row["id"] == "artboard-2"
    )
    target_artboard = next(
        row
        for row in view.target_pane.preview._document["artboards"]
        if row["id"] == "artboard-2"
    )
    source_rect, _scale = view.source_pane.preview._artboard_viewport(
        source_artboard
    )
    target_rect, _scale = view.target_pane.preview._artboard_viewport(
        target_artboard
    )
    assert target_rect.center().x() == pytest.approx(
        source_rect.center().x(),
        abs=1.0,
    )
    assert target_rect.center().y() == pytest.approx(
        source_rect.center().y(),
        abs=1.0,
    )

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_paints_component_definition_button_pixels() -> None:
    app = _app()

    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document, _report = instantiate_ui_template("mobile_onboarding")
    view = PainterUMGWidgetView()
    view.resize(1120, 720)
    view.set_document(document, artboard_id="artboard-1")
    view.show()
    app.processEvents()
    view.fit_views()
    app.processEvents()

    preview = view.target_pane.preview
    visual = next(
        row
        for row in preview._document["objects"]
        if row["id"] == "ui-object-1-button::ui-object-1-button"
    )
    rect = preview._object_rect(visual)
    image = preview.grab().toImage()
    sample = image.pixelColor(
        round(rect.x() + rect.width() * 0.8),
        round(rect.y() + rect.height() * 0.8),
    )
    assert sample.name().casefold() == "#5b6cff"
    assert sample.alpha() == 255

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_summarizes_reusable_component_instances() -> None:
    app = _app()
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView
    from tools.qa_painter_ui_unreal_umg_component import (
        build_component_contract_evidence,
    )

    evidence = build_component_contract_evidence()
    document = evidence["fixture"]["document"]
    before = copy.deepcopy(document)
    view = PainterUMGWidgetView()
    view.resize(1120, 720)

    view.set_document(document)
    view.show()
    app.processEvents()

    report = view.report()
    assert document == before
    assert report["component_count"] == 2
    assert report["component_instance_count"] == 2
    assert "Components 2" in view.summary_label.text()
    assert "Instances 2" in view.summary_label.text()
    assert "2 reusable component Widget Blueprint(s)" in (
        view.summary_label.toolTip()
    )
    for instance_id in evidence["fixture"]["primary_instance_root_ids"]:
        widget = report["widgets_by_id"][instance_id]
        assert widget["generated_widget_type"] == "UUserWidget"
        assert widget["widget_class"].startswith("WBP_TS_C_")

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_target_button_states_are_pointer_testable_but_read_only() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    projection, button_id = _button_state_projection_document()
    original = copy.deepcopy(projection)
    view = PainterUMGWidgetView()
    view.resize(1120, 720)
    target = view.target_pane.preview
    selected: list[tuple[str, str]] = []
    geometry_changes: list[tuple] = []
    clicked: list[str] = []
    target.object_selection_requested.connect(
        lambda object_id, mode: selected.append((object_id, mode))
    )
    target.object_geometry_requested.connect(
        lambda *payload: geometry_changes.append(tuple(payload))
    )
    target.button_test_clicked.connect(clicked.append)
    view.target_pane.set_document(projection)
    view.show()
    app.processEvents()
    view.target_pane.fit()
    app.processEvents()

    row = next(
        item for item in target._document["objects"] if item["id"] == button_id
    )
    point = target._object_rect(row).center().toPoint()
    assert target.isEnabled()
    assert target.button_test_state()["testable_count"] == 1
    assert row["style"]["fill"] == "#1D4ED8FF"

    QTest.mouseMove(target, point)
    app.processEvents()
    hover = target.button_test_state()
    hover_row = next(
        item for item in target._document["objects"] if item["id"] == button_id
    )
    assert hover["hovered_object_id"] == button_id
    assert hover["visual_state"] == "hovered"
    assert hover["last_event"] == "hovered"
    assert hover_row["style"]["fill"] == "#2563EBFF"
    assert target.cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert "Hovered" in view.target_pane.subtitle_label.text()

    QTest.mousePress(target, Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()
    pressed = target.button_test_state()
    pressed_row = next(
        item for item in target._document["objects"] if item["id"] == button_id
    )
    assert pressed["pressed_object_id"] == button_id
    assert pressed["visual_state"] == "pressed"
    assert pressed["last_event"] == "pressed"
    assert pressed_row["style"]["fill"] == "#1E40AFFF"
    assert "Pressed" in view.target_pane.subtitle_label.text()

    QTest.mouseRelease(target, Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()
    released = target.button_test_state()
    released_row = next(
        item for item in target._document["objects"] if item["id"] == button_id
    )
    assert released["pressed_object_id"] == ""
    assert released["clicked_object_id"] == button_id
    assert released["visual_state"] == "hovered"
    assert released["last_event"] == "clicked"
    assert released_row["style"]["fill"] == "#2563EBFF"
    assert clicked == [button_id]
    assert "Clicked" in view.target_pane.subtitle_label.text()

    QTest.mousePress(target, Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseRelease(
        target,
        Qt.MouseButton.LeftButton,
        pos=target.rect().topLeft() + QPoint(4, 4),
    )
    app.processEvents()
    canceled_release = target.button_test_state()
    normal_row = next(
        item for item in target._document["objects"] if item["id"] == button_id
    )
    assert canceled_release["last_event"] == "released"
    assert canceled_release["visual_state"] == "normal"
    assert normal_row["style"]["fill"] == "#1D4ED8FF"
    assert clicked == [button_id]
    assert "Released" in view.target_pane.subtitle_label.text()

    assert selected == []
    assert geometry_changes == []
    assert projection == original

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_target_disabled_button_uses_disabled_state_without_click() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    projection, button_id = _button_state_projection_document(enabled=False)
    original = copy.deepcopy(projection)
    view = PainterUMGWidgetView()
    view.resize(1120, 720)
    target = view.target_pane.preview
    clicked: list[str] = []
    target.button_test_clicked.connect(clicked.append)
    view.target_pane.set_document(projection)
    view.show()
    app.processEvents()
    view.target_pane.fit()
    app.processEvents()

    row = next(
        item for item in target._document["objects"] if item["id"] == button_id
    )
    point = target._object_rect(row).center().toPoint()
    assert row["style"]["fill"] == "#475569FF"
    assert row["opacity"] == 0.4

    QTest.mouseMove(target, point)
    QTest.mouseClick(target, Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()

    state = target.button_test_state()
    assert state["hovered_object_id"] == button_id
    assert state["pressed_object_id"] == ""
    assert state["clicked_object_id"] == ""
    assert state["visual_state"] == "disabled"
    assert state["last_event"] == "disabled"
    assert target.cursor().shape() == Qt.CursorShape.ForbiddenCursor
    assert "Disabled" in view.target_pane.subtitle_label.text()
    assert clicked == []
    original_row = next(
        item for item in projection["objects"] if item["id"] == button_id
    )
    assert original_row["opacity"] == 0.8
    assert projection == original

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_opens_graph_for_selected_material_layer() -> None:
    app = _app()
    import pytest
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog, QDockWidget, QMainWindow, QStyle

    from app.painter_i18n import painter_text
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_material_editor import (
        PainterUMGMaterialEditorPanel,
    )
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document, native_id, material_id = _material_document()
    view = PainterUMGWidgetView()
    view.resize(1120, 720)
    view.set_document(document)
    view.show()
    app.processEvents()

    widget = view.report()["widgets_by_id"][material_id]
    assert widget["disposition"] == "Material"
    assert widget["rendered"] is True
    assert widget["material"]["Generator"] == (
        "tiger_ui_gradient_custom_hlsl_v1"
    )
    assert view.material_button.text() == painter_text("Material Graph")
    assert view.material_button.isEnabled()
    assert view.material_button.isCheckable()
    assert not view.material_button.isChecked()
    assert not view.material_graph_visible()
    assert isinstance(view.workspace, QMainWindow)
    assert view.workspace.centralWidget() is view.comparison_panel
    assert view.material_dock() is None
    assert view.minimumWidth() >= (
        view.layout_controls.minimumSizeHint().width() + 18
    )
    assert view.minimumHeight() >= 640

    QTest.mouseClick(view.material_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    panel = view.material_graph_panel()
    dock = view.material_dock()
    assert isinstance(panel, PainterUMGMaterialEditorPanel)
    assert isinstance(dock, QDockWidget)
    assert dock.widget() is panel
    assert not isinstance(panel, QDialog)
    assert panel.isVisible()
    assert panel.window() is view
    assert not dock.isFloating()
    assert (
        view.workspace.dockWidgetArea(dock)
        == Qt.DockWidgetArea.BottomDockWidgetArea
    )
    assert dock.allowedAreas() == (
        Qt.DockWidgetArea.BottomDockWidgetArea
        | Qt.DockWidgetArea.RightDockWidgetArea
    )
    assert dock.features() & QDockWidget.DockWidgetFeature.DockWidgetMovable
    assert dock.features() & QDockWidget.DockWidgetFeature.DockWidgetFloatable
    assert dock.features() & QDockWidget.DockWidgetFeature.DockWidgetClosable
    assert view.material_button.isChecked()
    assert view.material_graph_visible()
    assert panel.material_spec() == widget["material"]
    assert panel.hlsl_edit.isReadOnly()
    assert "return Result;" in panel.hlsl_edit.toPlainText()
    assert panel.close_button.text() == "Hide graph"
    assert all(
        top_level.objectName() != "PainterUMGMaterialEditorDialog"
        for top_level in app.topLevelWidgets()
    )

    assert dock.geometry().width() > 0
    assert dock.geometry().height() > 0

    # The native QMainWindow dock separator is the direct manipulation handle
    # between the upper comparison canvas and the lower material graph.  Keep
    # it wide enough to discover and verify that both regions can be resized.
    separator_extent = view.workspace.style().pixelMetric(
        QStyle.PixelMetric.PM_DockWidgetSeparatorExtent,
        None,
        view.workspace,
    )
    assert separator_extent >= 8
    view.workspace.resizeDocks(
        [dock],
        [210],
        Qt.Orientation.Vertical,
    )
    app.processEvents()
    compact_dock_height = dock.height()
    compact_comparison_height = view.comparison_panel.height()
    view.workspace.resizeDocks(
        [dock],
        [360],
        Qt.Orientation.Vertical,
    )
    app.processEvents()
    assert dock.height() > compact_dock_height
    assert view.comparison_panel.height() < compact_comparison_height

    # Native dock controls and the UMG header toggle share one final visible
    # state without feeding visibility signals back into each other.
    dock.toggleViewAction().trigger()
    QTest.qWait(10)
    app.processEvents()
    assert not dock.isVisible()
    assert not view.material_button.isChecked()
    dock.toggleViewAction().trigger()
    QTest.qWait(10)
    app.processEvents()
    assert dock.isVisible()
    assert view.material_button.isChecked()

    def assert_compact_geometry() -> None:
        assert panel.graph_view.geometry().width() > 0
        assert panel.graph_view.geometry().height() > 0
        assert panel.inspector_tabs.geometry().width() > 0
        assert panel.inspector_tabs.geometry().height() > 0
        panel.inspector_tabs.setCurrentIndex(0)
        app.processEvents()
        assert panel.preview.isVisible()
        assert panel.preview.geometry().width() > 0
        assert panel.preview.geometry().height() > 0
        assert panel.inspector_tabs.tabBar().tabRect(0).width() > 0
        panel.inspector_tabs.setCurrentIndex(1)
        app.processEvents()
        assert panel.hlsl_edit.isVisible()
        assert panel.hlsl_edit.geometry().width() > 0
        assert panel.hlsl_edit.geometry().height() > 0
        assert panel.inspector_tabs.tabBar().tabRect(1).width() > 0

    assert_compact_geometry()
    view.resize(view.minimumSize())
    app.processEvents()
    assert view.width() >= view.minimumWidth()
    assert view.height() >= view.minimumHeight()
    assert_compact_geometry()

    view.workspace.addDockWidget(
        Qt.DockWidgetArea.RightDockWidgetArea,
        dock,
    )
    view.workspace.resizeDocks(
        [dock],
        [320],
        Qt.Orientation.Horizontal,
    )
    app.processEvents()
    assert (
        view.workspace.dockWidgetArea(dock)
        == Qt.DockWidgetArea.RightDockWidgetArea
    )
    docked_width = dock.width()
    assert docked_width > 0

    panel.inspector_tabs.setCurrentIndex(1)
    panel.splitter.setSizes([420, 260])
    panel.graph_view.set_view_state(
        {"zoom": 0.73, "center": [310.0, 130.0]}
    )
    app.processEvents()
    saved_panel_state = panel.view_state()

    material_row = next(
        row for row in document["objects"] if row["id"] == material_id
    )
    changed_style = copy.deepcopy(material_row["style"])
    changed_style["fills"][0]["gradient"]["stops"][0][
        "color"
    ] = "#16A34AFF"
    document, _updated = update_ui_object(
        document,
        material_id,
        {"style": changed_style},
    )
    view.set_document(document, force=True)
    QTest.qWait(10)
    app.processEvents()
    replaced_panel = view.material_graph_panel()
    assert isinstance(replaced_panel, PainterUMGMaterialEditorPanel)
    assert replaced_panel is not panel
    assert replaced_panel.isVisible()
    assert view.material_dock() is dock
    assert (
        view.workspace.dockWidgetArea(dock)
        == Qt.DockWidgetArea.RightDockWidgetArea
    )
    assert dock.width() == pytest.approx(docked_width, abs=4)
    assert view.material_button.isChecked()
    assert replaced_panel.inspector_tabs.currentIndex() == 1
    restored_state = replaced_panel.view_state()
    assert restored_state["splitter_sizes"] == saved_panel_state[
        "splitter_sizes"
    ]
    assert restored_state["graph"]["zoom"] == pytest.approx(
        saved_panel_state["graph"]["zoom"]
    )
    panel = replaced_panel

    dock.setFloating(True)
    dock.resize(720, 340)
    QTest.qWait(10)
    app.processEvents()
    assert dock.isFloating()
    floating_size = dock.size()

    view.set_document(document, force=True)
    app.processEvents()
    assert view.material_dock() is dock
    assert dock.isFloating()
    assert dock.size() == floating_size

    QTest.mouseClick(panel.close_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert not view.material_button.isChecked()
    assert not view.material_graph_visible()
    assert view.comparison_panel.isVisible()

    QTest.mouseClick(view.material_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert view.material_graph_visible()
    assert dock.isFloating()
    assert dock.size() == floating_size

    # A floating dock must follow the outer UMG tool window.  Qt otherwise
    # leaves QDockWidget top-level windows visible when only the parent tool is
    # hidden, which would create an orphan graph window in UI mode.
    view.hide()
    QTest.qWait(10)
    app.processEvents()
    assert not view.isVisible()
    assert not dock.isVisible()
    assert view.material_button.isChecked()
    assert not any(
        top_level is dock and top_level.isVisible()
        for top_level in app.topLevelWidgets()
    )

    view.show()
    QTest.qWait(10)
    app.processEvents()
    assert view.isVisible()
    assert dock.isVisible()
    assert dock.isFloating()
    assert view.material_button.isChecked()
    assert dock.size() == floating_size

    document["selection"] = {
        "object_id": native_id,
        "object_ids": [native_id],
    }
    view.set_document(document, force=True)
    app.processEvents()
    assert not view.material_button.isEnabled()
    assert not view.material_button.isChecked()
    assert view.material_dock() is None
    assert view.material_graph_panel() is None
    assert view.comparison_panel.isVisible()

    document["selection"] = {
        "object_id": material_id,
        "object_ids": [material_id],
    }
    view.set_document(document, force=True)
    app.processEvents()
    assert view.material_button.isEnabled()
    assert not view.material_button.isChecked()
    QTest.mouseClick(view.material_button, Qt.MouseButton.LeftButton)
    QTest.qWait(10)
    app.processEvents()
    restored_dock = view.material_dock()
    assert isinstance(restored_dock, QDockWidget)
    assert restored_dock is not dock
    assert restored_dock.isFloating()
    assert restored_dock.size().width() == pytest.approx(
        floating_size.width(),
        abs=8,
    )
    assert restored_dock.size().height() == pytest.approx(
        floating_size.height(),
        abs=8,
    )

    view.close()
    QTest.qWait(10)
    app.processEvents()
    assert not restored_dock.isVisible()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_opens_rounded_card_material_graph() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document, card_id = _rounded_card_document()
    view = PainterUMGWidgetView()
    view.resize(1120, 720)
    view.set_document(document)
    view.show()
    app.processEvents()
    try:
        widget = view.report()["widgets_by_id"][card_id]
        assert widget["disposition"] == "Material"
        assert widget["rendered"] is True
        assert widget["material"]["Kind"] == "RoundedCard"
        assert widget["material"]["Schema"] == "tigerstudio.umg.ui_material.v2"
        assert widget["widget_class"] == "UCanvasPanel"
        assert widget["visual_widget_id"] == f"{card_id}_Visual"
        visual = view.report()["widgets_by_id"][f"{card_id}_Visual"]
        assert visual["widget_class"] == "UImage"
        assert visual["effective_parent_id"] == card_id
        target_objects = {
            row["id"]: row for row in view.report()["document"]["objects"]
        }
        assert target_objects[card_id]["kind"] == "frame"
        assert target_objects[f"{card_id}_Visual"]["parent_id"] == card_id
        assert view.material_button.isEnabled()

        QTest.mouseClick(view.material_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        panel = view.material_graph_panel()
        assert panel is not None
        assert panel.material_spec()["Kind"] == "RoundedCard"
        assert set(panel.scene.node_items) == {
            "geometry_uv",
            "fill",
            "corners_border",
            "shadows",
            "custom_hlsl",
            "output",
        }
        assert panel.preview_style()["corner_radii"] == {
            "top_left": 30.0,
            "top_right": 8.0,
            "bottom_right": 24.0,
            "bottom_left": 12.0,
        }
        assert "Rounded Card SDF" in panel.hlsl_edit.toPlainText()
        assert panel.hlsl_edit.isReadOnly()
    finally:
        view.close()
        view.deleteLater()
        app.processEvents()


def test_umg_widget_view_document_sync_does_not_emit_layout_edits() -> None:
    app = _app()
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    requested: list[tuple[str, dict]] = []
    view = PainterUMGWidgetView()
    view.object_changes_requested.connect(
        lambda object_id, changes: requested.append(
            (str(object_id), dict(changes))
        )
    )
    document = _document()
    view.set_document(document)
    view.set_document(document, force=True)
    app.processEvents()

    assert requested == []
    assert view.control_state()["object_id"] == document["selection"][
        "object_id"
    ]

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_source_click_selects_without_undo() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _document()
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    dialog._set_painter_umg_widget_view_enabled(True)
    app.processEvents()
    view = dialog._painter_umg_widget_view
    view.fit_views()
    app.processEvents()

    blocked = next(
        row
        for row in view.source_pane.preview._document["objects"]
        if row["name"] == "Gradient card"
    )
    undo_count = len(dialog._undo_stack)
    QTest.mouseClick(
        view.source_pane.preview,
        Qt.MouseButton.LeftButton,
        pos=view.source_pane.preview._object_rect(blocked).center().toPoint(),
    )
    app.processEvents()

    assert dialog._painter_ui_document["selection"]["object_id"] == blocked[
        "id"
    ]
    assert view.control_state()["object_id"] == blocked["id"]
    assert view.anchor_decoration()["source"]["object_id"] == blocked["id"]
    assert view.anchor_decoration()["target"]["object_id"] == blocked["id"]
    assert view.anchor_decoration()["target"]["reason"] == "blocked"
    assert len(dialog._undo_stack) == undo_count

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_umg_widget_view_normal_click_selects_nested_canvas_child_anchor() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, panel_id, button_id = _nested_canvas_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    dialog._set_painter_umg_widget_view_enabled(True)
    app.processEvents()
    view = dialog._painter_umg_widget_view
    view.fit_views()
    app.processEvents()

    source = view.source_pane.preview
    button = next(
        row for row in source._document["objects"] if row["id"] == button_id
    )
    assert dialog._painter_ui_document["selection"]["object_id"] == panel_id
    QTest.mouseClick(
        source,
        Qt.MouseButton.LeftButton,
        pos=source._object_rect(button).center().toPoint(),
    )
    app.processEvents()

    assert dialog._painter_ui_document["selection"]["object_id"] == button_id
    anchor = view.anchor_decoration()["source"]
    assert anchor["object_id"] == button_id
    assert anchor["parent_object_id"] == panel_id
    assert anchor["anchor_minimum"] == {"x": 1.0, "y": 1.0}
    assert anchor["anchor_maximum"] == {"x": 1.0, "y": 1.0}

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_umg_widget_view_anchor_controls_update_owner_target_and_undo() -> None:
    app = _app()
    import pytest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _document()
    selected_id = dialog._painter_ui_document["selection"]["object_id"]
    original_row = copy.deepcopy(
        next(
            row
            for row in dialog._painter_ui_document["objects"]
            if row["id"] == selected_id
        )
    )
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    dialog._set_painter_umg_widget_view_enabled(True)
    app.processEvents()
    view = dialog._painter_umg_widget_view
    controls = view.layout_controls
    undo_count = len(dialog._undo_stack)

    controls.horizontal_combo.setCurrentIndex(
        controls.horizontal_combo.findData("right")
    )
    controls.vertical_combo.setCurrentIndex(
        controls.vertical_combo.findData("bottom")
    )
    app.processEvents()

    row = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == selected_id
    )
    assert row["constraints"]["horizontal"] == "right"
    assert row["constraints"]["vertical"] == "bottom"
    assert (row["x"], row["y"], row["width"], row["height"]) == (
        original_row["x"],
        original_row["y"],
        original_row["width"],
        original_row["height"],
    )
    widget = view.report()["widgets_by_id"][selected_id]
    assert widget["slot"]["anchor_minimum"] == {"x": 1.0, "y": 1.0}
    assert widget["slot"]["anchor_maximum"] == {"x": 1.0, "y": 1.0}
    assert len(dialog._undo_stack) == undo_count + 2

    controls.pivot_x_spin.setValue(0.25)
    controls.pivot_y_spin.setValue(0.75)
    controls.flush_pending_changes()
    app.processEvents()

    row = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == selected_id
    )
    assert row["constraints"]["pivot_x"] == pytest.approx(0.25)
    assert row["constraints"]["pivot_y"] == pytest.approx(0.75)
    widget = view.report()["widgets_by_id"][selected_id]
    assert widget["slot"]["alignment"] == {"x": 0.25, "y": 0.75}
    assert widget["render_transform_pivot"] == {"x": 0.25, "y": 0.75}
    assert view.anchor_decoration()["target"][
        "render_transform_pivot"
    ] == {"x": 0.25, "y": 0.75}
    assert len(dialog._undo_stack) == undo_count + 3

    dialog._undo()
    app.processEvents()
    assert view.control_state()["pivot_x"] == pytest.approx(0.5)
    assert view.control_state()["pivot_y"] == pytest.approx(0.5)
    assert view.report()["widgets_by_id"][selected_id][
        "render_transform_pivot"
    ] == {"x": 0.5, "y": 0.5}

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_umg_panel_selector_updates_preview_selection_and_saved_document(
    tmp_path,
) -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, panel_id, child_id = _nested_canvas_document()
    panel = next(
        row for row in document["objects"] if row["id"] == panel_id
    )
    panel["layout"]["umg_panel_mode"] = "auto"
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    dialog._set_painter_umg_widget_view_enabled(True)
    app.processEvents()

    view = dialog._painter_umg_widget_view
    controls = view.layout_controls
    initial = view.control_state()
    assert initial["panel_mode"] == "auto"
    assert initial["panel_effective"] == "Overlay"
    assert initial["panel_policy"] == "auto"
    assert initial["panel_enabled"] is True
    assert "all_children_support_overlay_slots" in initial["panel_reasons"]
    assert view.report()["widgets_by_id"][panel_id]["widget_class"] == "UOverlay"

    undo_count = len(dialog._undo_stack)
    controls.panel_selector.mode_combo.setCurrentIndex(
        controls.panel_selector.mode_combo.findData("canvas")
    )
    app.processEvents()
    changed_panel = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == panel_id
    )
    assert changed_panel["layout"]["umg_panel_mode"] == "canvas"
    changed = view.control_state()
    assert changed["panel_effective"] == "Canvas"
    assert changed["panel_policy"] == "explicit"
    assert changed["panel_reasons"] == ["explicit_canvas_panel"]
    assert view.report()["widgets_by_id"][panel_id]["widget_class"] == "UCanvasPanel"
    assert len(dialog._undo_stack) == undo_count + 1

    dialog._select_painter_ui_object(child_id)
    app.processEvents()
    assert view.control_state()["object_id"] == child_id
    assert "panel_effective" not in view.control_state()
    assert controls.panel_selector.isHidden()
    dialog._select_painter_ui_object(panel_id)
    app.processEvents()
    assert view.control_state()["panel_effective"] == "Canvas"

    output = tmp_path / "umg-panel-mode.tspaint"
    dialog.save_document_to_path(output)
    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(output)
    restored_panel = next(
        row
        for row in restored._painter_ui_document["objects"]
        if row["id"] == panel_id
    )
    assert restored_panel["layout"]["umg_panel_mode"] == "canvas"

    dialog.close()
    restored.close()
    dialog.deleteLater()
    restored.deleteLater()
    app.processEvents()


def test_umg_layout_hint_follows_the_selected_child_parent_panel() -> None:
    app = _app()
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document, panel_id, child_id = _nested_canvas_document()
    panel = next(
        row for row in document["objects"] if row["id"] == panel_id
    )
    panel["layout"]["umg_panel_mode"] = "auto"
    document["selection"] = {
        "object_id": child_id,
        "object_ids": [child_id],
    }
    view = PainterUMGWidgetView()
    view.set_document(document)

    overlay = view.control_state()
    expected = (
        "Overlay 자식은 앵커 대신 정렬/Padding을 사용합니다. "
        "부모를 선택해 Canvas로 바꾸면 앵커가 활성화됩니다."
    )
    assert overlay["parent_panel_kind"] == "Overlay"
    assert overlay["slot_kind"] == "OverlaySlot"
    assert overlay["anchor_enabled"] is False
    assert overlay["constraint_controls_enabled"] is True
    assert overlay["anchor_hint"] == expected
    assert view.layout_controls.anchor_hint.text() == expected

    panel["layout"]["umg_panel_mode"] = "canvas"
    view.set_document(document, force=True)
    canvas = view.control_state()
    assert "parent_panel_kind" not in canvas
    assert view.layout_controls.horizontal_combo.isEnabled()
    assert view.layout_controls.anchor_hint.text() == (
        view.layout_controls._default_anchor_hint
    )

    panel["layout"]["umg_panel_mode"] = "auto"
    panel["layout"]["mode"] = "horizontal"
    view.set_document(document, force=True)
    flow = view.control_state()
    assert flow["parent_panel_kind"] == "Horizontal"
    assert flow["slot_kind"] == "HorizontalBoxSlot"
    assert flow["constraint_controls_enabled"] is False
    assert "Flow Slot" in flow["anchor_hint"]

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_geometry_controls_visibly_update_target_once() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _document()
    selected_id = dialog._painter_ui_document["selection"]["object_id"]
    original = copy.deepcopy(
        next(
            row
            for row in dialog._painter_ui_document["objects"]
            if row["id"] == selected_id
        )
    )
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    dialog._set_painter_umg_widget_view_enabled(True)
    app.processEvents()
    view = dialog._painter_umg_widget_view
    controls = view.layout_controls
    undo_count = len(dialog._undo_stack)

    for key, value in {
        "x": 84.0,
        "y": 212.0,
        "width": 260.0,
        "height": 72.0,
    }.items():
        controls.geometry_spins[key].setValue(value)
    controls.flush_pending_geometry_changes()
    app.processEvents()

    row = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == selected_id
    )
    assert (row["x"], row["y"], row["width"], row["height"]) == (
        84.0,
        212.0,
        260.0,
        72.0,
    )
    target = view.report()["widgets_by_id"][selected_id]["slot"][
        "resolved_geometry"
    ]
    assert target == {
        "x": 84.0,
        "y": 212.0,
        "width": 260.0,
        "height": 72.0,
    }
    assert len(dialog._undo_stack) == undo_count + 1

    dialog._undo()
    app.processEvents()
    restored = view.control_state()
    assert restored["x"] == original["x"]
    assert restored["y"] == original["y"]
    assert restored["width"] == original["width"]
    assert restored["height"] == original["height"]

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_umg_widget_view_direct_move_and_resize_preview_then_commit() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _document()
    selected_id = dialog._painter_ui_document["selection"]["object_id"]
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    dialog._set_painter_umg_widget_view_enabled(True)
    app.processEvents()
    view = dialog._painter_umg_widget_view
    view.fit_views()
    app.processEvents()
    source = view.source_pane.preview
    original = copy.deepcopy(
        next(row for row in source._document["objects"] if row["id"] == selected_id)
    )
    undo_count = len(dialog._undo_stack)

    start = source._object_rect(original).center().toPoint()
    end = start + QPoint(42, -24)
    QTest.mousePress(source, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(source, end, delay=5)
    app.processEvents()
    during_move = view.report()["widgets_by_id"][selected_id]["slot"][
        "resolved_geometry"
    ]
    assert (during_move["x"], during_move["y"]) != (
        original["x"],
        original["y"],
    )
    canonical_during = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == selected_id
    )
    assert canonical_during["x"] == original["x"]
    assert canonical_during["y"] == original["y"]
    QTest.mouseRelease(source, Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()

    moved = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == selected_id
    )
    assert (moved["x"], moved["y"]) != (original["x"], original["y"])
    assert len(dialog._undo_stack) == undo_count + 1

    selected_row = next(
        row for row in source._document["objects"] if row["id"] == selected_id
    )
    before_resize = copy.deepcopy(selected_row)
    handle = source._handle_rects(source._object_rect(selected_row))[
        "se"
    ].center().toPoint()
    resize_end = handle + QPoint(36, 24)
    QTest.mousePress(source, Qt.MouseButton.LeftButton, pos=handle)
    QTest.mouseMove(source, resize_end, delay=5)
    app.processEvents()
    during_resize = view.report()["widgets_by_id"][selected_id]["slot"][
        "resolved_geometry"
    ]
    assert during_resize["width"] > before_resize["width"]
    assert during_resize["height"] > before_resize["height"]
    QTest.mouseRelease(source, Qt.MouseButton.LeftButton, pos=resize_end)
    app.processEvents()

    resized = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == selected_id
    )
    assert resized["width"] > before_resize["width"]
    assert resized["height"] > before_resize["height"]
    assert len(dialog._undo_stack) == undo_count + 2

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_umg_widget_view_numeric_fields_drag_cleanly_without_arrow_buttons() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QAbstractSpinBox

    from app.painter_ui_inspector import PainterUIDragDoubleSpinBox
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    requested: list[tuple[str, dict]] = []
    view = PainterUMGWidgetView()
    view.resize(1180, 720)
    view.set_document(_document())
    view.object_changes_requested.connect(
        lambda object_id, changes: requested.append(
            (str(object_id), copy.deepcopy(dict(changes)))
        )
    )
    view.show()
    app.processEvents()

    x_spin = view.layout_controls.geometry_spins["x"]
    assert isinstance(x_spin, PainterUIDragDoubleSpinBox)
    assert x_spin.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    assert x_spin.width() >= 110
    assert x_spin.cursor().shape() == Qt.CursorShape.SizeHorCursor
    assert x_spin.suffix() == " px"
    assert view.layout_controls.pivot_x_spin.singleStep() == 0.01

    start_value = x_spin.value()
    start = x_spin.rect().center()
    end = start + QPoint(24, 0)
    QTest.mousePress(x_spin, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(x_spin, end, delay=5)
    QTest.mouseRelease(x_spin, Qt.MouseButton.LeftButton, pos=end)
    QTest.qWait(150)
    app.processEvents()

    assert x_spin.value() > start_value
    assert len(requested) == 1
    assert requested[0][1]["x"] == x_spin.value()

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_point_anchor_drag_beats_resize_and_commits_once() -> None:
    app = _app()
    import pytest
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document = _document()
    selected_id = document["selection"]["object_id"]
    selected = next(
        row for row in document["objects"] if row["id"] == selected_id
    )
    # Make the point anchor and north-west resize handle overlap exactly.
    selected["x"] = 0.0
    selected["y"] = 0.0

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    dialog._set_painter_umg_widget_view_enabled(True)
    app.processEvents()
    view = dialog._painter_umg_widget_view
    view.fit_views()
    app.processEvents()

    source = view.source_pane.preview
    plan = view.anchor_decoration()["source"]
    start = QPoint(
        round(plan["anchor_center_point"]["x"]),
        round(plan["anchor_center_point"]["y"]),
    )
    parent = plan["parent_bounds"]
    end = QPoint(
        round(parent["x"] + parent["width"] * 0.25),
        round(parent["y"] + parent["height"] * 0.30),
    )
    original = copy.deepcopy(selected)
    undo_count = len(dialog._undo_stack)

    QTest.mousePress(source, Qt.MouseButton.LeftButton, pos=start)
    assert source._interaction == "umg_anchor"
    QTest.mouseMove(source, end, delay=5)
    app.processEvents()

    canonical_during = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == selected_id
    )
    assert canonical_during.get("constraints", {}).get("horizontal") != "custom"
    assert len(dialog._undo_stack) == undo_count
    during = view.anchor_decoration()
    assert during["source"]["anchor_minimum"]["x"] == pytest.approx(
        0.25, abs=0.01
    )
    assert during["source"]["anchor_minimum"]["y"] == pytest.approx(
        0.30, abs=0.01
    )
    assert during["target"]["anchor_minimum"] == during["source"][
        "anchor_minimum"
    ]
    during_geometry = view.report()["widgets_by_id"][selected_id]["slot"][
        "resolved_geometry"
    ]
    assert during_geometry["x"] == pytest.approx(original["x"])
    assert during_geometry["y"] == pytest.approx(original["y"])
    assert during_geometry["width"] == pytest.approx(original["width"])
    assert during_geometry["height"] == pytest.approx(original["height"])

    QTest.mouseRelease(source, Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()

    committed = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == selected_id
    )
    assert committed["constraints"]["horizontal"] == "custom"
    assert committed["constraints"]["vertical"] == "custom"
    assert committed["constraints"]["anchor_min_x"] == pytest.approx(
        0.25, abs=0.01
    )
    assert committed["constraints"]["anchor_max_y"] == pytest.approx(
        0.30, abs=0.01
    )
    assert (
        committed["x"],
        committed["y"],
        committed["width"],
        committed["height"],
    ) == (
        original["x"],
        original["y"],
        original["width"],
        original["height"],
    )
    assert len(dialog._undo_stack) == undo_count + 1

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_umg_widget_view_anchor_plan_matches_ue58_medallion_shapes() -> None:
    app = _app()
    from app.painter_ui_constraints import (
        capture_ui_constraints,
        constraint_parent_geometry,
    )
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document = _document()
    selected_id = document["selection"]["object_id"]
    view = PainterUMGWidgetView()
    view.resize(980, 620)
    view.set_document(document)
    view.show()
    view.fit_views()
    app.processEvents()

    fixed = view.anchor_decoration()["source"]
    assert fixed["schema"].endswith("umg_anchor_decoration.v2")
    assert fixed["slot_kind"] == "CanvasPanelSlot"
    assert fixed["parent_panel_kind"] == "Canvas"
    assert fixed["gizmo_shape"] == "fixed"
    assert fixed["preset"] == "top_left"
    assert fixed["colors"] == {
        "normal": "#FFFFFFFF",
        "hovered": "#00FF00FF",
        "connector": "#D8D8D8CC",
        "stretch_outline": "#FFFFFFE6",
        "stretch_fill": "#FFFFFF0D",
    }
    assert len(fixed["connector_lines"]) == 1
    fixed_handles = {
        row["name"]: row for row in fixed["anchor_handles"]
    }
    assert set(fixed_handles) == {
        "center",
        "left",
        "right",
        "top",
        "bottom",
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
    }
    assert all(row["visible"] for row in fixed_handles.values())
    assert fixed_handles["center"]["size"] == {
        "width": 16.0,
        "height": 16.0,
    }
    assert fixed_handles["left"]["size"] == {
        "width": 32.0,
        "height": 16.0,
    }
    assert fixed_handles["top"]["size"] == {
        "width": 16.0,
        "height": 32.0,
    }
    assert fixed_handles["top_left"]["size"] == {
        "width": 24.0,
        "height": 24.0,
    }

    multi_document = copy.deepcopy(document)
    second_id = next(
        row["id"]
        for row in multi_document["objects"]
        if row["id"] != selected_id
    )
    multi_document["selection"] = {
        "object_id": selected_id,
        "object_ids": [selected_id, second_id],
    }
    view.set_document(multi_document, force=True)
    app.processEvents()
    assert view.anchor_decoration()["source"]["visible"] is False
    assert view.anchor_decoration()["source"]["reason"] == "multiple_selection"
    assert view.anchor_decoration()["target"]["visible"] is False
    assert view.anchor_decoration()["target"]["reason"] == "multiple_selection"

    stretched_document = copy.deepcopy(document)
    selected = next(
        row
        for row in stretched_document["objects"]
        if row["id"] == selected_id
    )
    selected["constraints"] = capture_ui_constraints(
        selected,
        constraint_parent_geometry(stretched_document, selected),
        {"horizontal": "stretch", "vertical": "stretch"},
    )
    view.set_document(stretched_document, force=True)
    app.processEvents()
    stretched = view.anchor_decoration()["source"]
    assert stretched["gizmo_shape"] == "stretch"
    assert stretched["preset"] == "fill"
    assert len(stretched["connector_lines"]) == 4
    assert {
        row["name"]
        for row in stretched["anchor_handles"]
        if row["visible"]
    } == {
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
    }

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_axis_handle_splits_point_anchor_like_ue58() -> None:
    app = _app()
    import pytest
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_constraints import (
        capture_ui_constraints,
        constraint_parent_geometry,
    )
    from app.painter_ui_umg_widget_view import (
        PainterUMGWidgetView,
        _UMGAnchorPreviewOverlay,
    )

    document = _document()
    selected_id = document["selection"]["object_id"]
    selected = next(
        row for row in document["objects"] if row["id"] == selected_id
    )
    selected["constraints"] = capture_ui_constraints(
        selected,
        constraint_parent_geometry(document, selected),
        {"horizontal": "center", "vertical": "center"},
    )
    committed: list[tuple[str, dict]] = []
    view = PainterUMGWidgetView()
    view.resize(980, 620)
    view.set_document(document)
    view.object_changes_requested.connect(
        lambda object_id, changes: committed.append(
            (str(object_id), copy.deepcopy(dict(changes)))
        )
    )
    view.show()
    view.fit_views()
    app.processEvents()

    source = view.source_pane.preview
    plan = view.anchor_decoration()["source"]
    anchor = plan["anchor_center_point"]
    start = QPoint(round(anchor["x"] - 18.0), round(anchor["y"]))
    end = QPoint(start.x() - 45, start.y())
    QTest.mousePress(source, Qt.MouseButton.LeftButton, pos=start)
    assert source._interaction == "umg_anchor"
    assert source._umg_anchor_drag["handle"] == "left"
    QTest.mouseMove(source, end, delay=5)
    app.processEvents()
    preview = view.anchor_decoration()["target"]
    assert preview["anchor_minimum"]["x"] == pytest.approx(0.4, abs=0.011)
    assert preview["anchor_maximum"]["x"] == pytest.approx(0.5)
    assert preview["anchor_minimum"]["y"] == pytest.approx(0.5)
    assert preview["anchor_maximum"]["y"] == pytest.approx(0.5)
    assert preview["gizmo_shape"] == "horizontal_stretch"
    QTest.mouseRelease(source, Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()
    assert len(committed) == 1

    no_modifiers = Qt.KeyboardModifier.NoModifier
    shift = Qt.KeyboardModifier.ShiftModifier
    assert _UMGAnchorPreviewOverlay._snap_anchor_value(
        0.209,
        screen_size=100.0,
        modifiers=no_modifiers,
    ) == pytest.approx(0.2)
    assert _UMGAnchorPreviewOverlay._snap_anchor_value(
        0.209,
        screen_size=100.0,
        modifiers=shift,
    ) == pytest.approx(0.209)

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_hides_anchor_for_auto_layout_flow_slot() -> None:
    app = _app()
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document = create_ui_document(640, 360, name="Flow slot")
    document, frame = add_ui_object(
        document,
        kind="frame",
        name="Horizontal box",
        x=40,
        y=40,
        width=520,
        height=180,
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {"layout": {"mode": "horizontal", "gap": 12}},
    )
    document, child = add_ui_object(
        document,
        kind="button",
        name="Flow button",
        parent_id=frame["id"],
        width=180,
        height=52,
        content={"text": "Flow"},
    )
    document["selection"] = {
        "object_id": child["id"],
        "object_ids": [child["id"]],
    }
    view = PainterUMGWidgetView()
    view.resize(980, 620)
    view.set_document(document)
    view.show()
    view.fit_views()
    app.processEvents()

    widget = view.report()["widgets_by_id"][child["id"]]
    assert widget["slot_kind"] == "HorizontalBoxSlot"
    assert widget["parent_panel_kind"] == "Horizontal"
    assert view.anchor_decoration()["source"]["visible"] is False
    assert (
        view.anchor_decoration()["source"]["reason"]
        == "not_canvas_panel_slot"
    )
    assert view.anchor_decoration()["target"]["visible"] is False

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_stretch_anchor_min_drag_preserves_geometry() -> None:
    app = _app()
    import pytest
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_constraints import (
        capture_ui_constraints,
        constraint_parent_geometry,
    )
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document = _document()
    selected_id = document["selection"]["object_id"]
    selected = next(
        row for row in document["objects"] if row["id"] == selected_id
    )
    selected["constraints"] = capture_ui_constraints(
        selected,
        constraint_parent_geometry(document, selected),
        {"horizontal": "stretch", "vertical": "stretch"},
    )
    committed: list[tuple[str, dict]] = []
    view = PainterUMGWidgetView()
    view.resize(980, 620)
    view.set_document(document)
    view.object_changes_requested.connect(
        lambda object_id, changes: committed.append(
            (str(object_id), copy.deepcopy(dict(changes)))
        )
    )
    view.show()
    view.fit_views()
    app.processEvents()

    source = view.source_pane.preview
    plan = view.anchor_decoration()["source"]
    assert plan["stretched"] is True
    start = QPoint(
        round(plan["anchor_minimum_point"]["x"]),
        round(plan["anchor_minimum_point"]["y"]),
    )
    parent = plan["parent_bounds"]
    end = QPoint(
        round(parent["x"] + parent["width"] * 0.15),
        round(parent["y"] + parent["height"] * 0.20),
    )
    original_geometry = copy.deepcopy(
        view.report()["widgets_by_id"][selected_id]["slot"][
            "resolved_geometry"
        ]
    )

    QTest.mousePress(source, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(source, end, delay=5)
    app.processEvents()
    preview = view.anchor_decoration()["target"]
    assert preview["anchor_minimum"]["x"] == pytest.approx(0.15, abs=0.01)
    assert preview["anchor_minimum"]["y"] == pytest.approx(0.20, abs=0.01)
    assert preview["anchor_maximum"] == {"x": 1.0, "y": 1.0}
    assert view.report()["widgets_by_id"][selected_id]["slot"][
        "resolved_geometry"
    ] == pytest.approx(original_geometry)

    QTest.mouseRelease(source, Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()
    assert len(committed) == 1
    constraints = committed[0][1]["constraints"]
    assert constraints["horizontal"] == "custom"
    assert constraints["vertical"] == "custom"
    assert constraints["anchor_min_x"] == pytest.approx(0.15, abs=0.01)
    assert constraints["anchor_max_x"] == 1.0

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_escape_cancels_anchor_preview_without_edit() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document = _document()
    selected_id = document["selection"]["object_id"]
    requested: list[tuple[str, dict]] = []
    view = PainterUMGWidgetView()
    view.resize(980, 620)
    view.set_document(document)
    view.object_changes_requested.connect(
        lambda object_id, changes: requested.append(
            (str(object_id), copy.deepcopy(dict(changes)))
        )
    )
    view.show()
    view.fit_views()
    app.processEvents()

    source = view.source_pane.preview
    original = copy.deepcopy(view.anchor_decoration()["source"])
    start = QPoint(
        round(original["anchor_center_point"]["x"]),
        round(original["anchor_center_point"]["y"]),
    )
    parent = original["parent_bounds"]
    end = QPoint(
        round(parent["x"] + parent["width"] * 0.4),
        round(parent["y"] + parent["height"] * 0.4),
    )
    QTest.mousePress(source, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(source, end, delay=5)
    app.processEvents()
    assert view.anchor_decoration()["source"]["anchor_minimum"] != original[
        "anchor_minimum"
    ]

    QTest.keyClick(source, Qt.Key.Key_Escape)
    app.processEvents()
    restored = view.anchor_decoration()["source"]
    assert restored["anchor_minimum"] == original["anchor_minimum"]
    assert restored["anchor_maximum"] == original["anchor_maximum"]
    assert source._document["selection"]["object_id"] == selected_id
    assert requested == []

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_draws_locked_target_anchor_and_pivot_from_report() -> None:
    app = _app()
    import pytest
    from PySide6.QtGui import QColor

    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document = _document()
    selected_id = document["selection"]["object_id"]
    document, _updated = update_ui_object(
        document,
        selected_id,
        {
            "constraints": {
                "horizontal": "right",
                "vertical": "bottom",
                "pivot_x": 0.25,
                "pivot_y": 0.75,
            }
        },
    )
    before = copy.deepcopy(document)
    view = PainterUMGWidgetView()
    view.resize(980, 620)
    view.set_document(document)
    view.show()
    app.processEvents()

    report_widget = view.report()["widgets_by_id"][selected_id]
    plan = view.anchor_decoration()["target"]
    assert plan["visible"] is True
    assert plan["read_only"] is True
    assert plan["object_id"] == selected_id
    assert plan["anchor_minimum"] == report_widget["slot"][
        "anchor_minimum"
    ]
    assert plan["anchor_maximum"] == report_widget["slot"][
        "anchor_maximum"
    ]
    assert plan["alignment"] == report_widget["slot"]["alignment"]
    assert (
        plan["render_transform_pivot"]
        == report_widget["render_transform_pivot"]
    )
    bounds = plan["widget_bounds"]
    pivot = plan["pivot_point"]
    assert pivot["x"] == pytest.approx(
        bounds["x"]
        + bounds["width"] * plan["render_transform_pivot"]["x"]
    )
    assert pivot["y"] == pytest.approx(
        bounds["y"]
        + bounds["height"] * plan["render_transform_pivot"]["y"]
    )
    parent = plan["parent_bounds"]
    minimum = plan["anchor_minimum_point"]
    assert minimum["x"] == pytest.approx(
        parent["x"] + parent["width"] * plan["anchor_minimum"]["x"]
    )
    assert minimum["y"] == pytest.approx(
        parent["y"] + parent["height"] * plan["anchor_minimum"]["y"]
    )
    assert view.target_pane.preview._document["objects"][0]["locked"] is True

    image = view.target_pane.preview.grab().toImage()
    pivot_color = image.pixelColor(round(pivot["x"]), round(pivot["y"]))
    assert pivot_color.red() > QColor("#D000A0").red()
    assert pivot_color.blue() > QColor("#A000A0").blue()
    assert document == before

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_keeps_blocked_selection_without_target_anchor() -> None:
    app = _app()
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document = _document()
    blocked_id = next(
        row["id"]
        for row in document["objects"]
        if row["name"] == "Gradient card"
    )
    document["selection"] = {
        "object_id": blocked_id,
        "object_ids": [blocked_id],
    }
    before = copy.deepcopy(document)
    view = PainterUMGWidgetView()
    view.resize(980, 620)
    view.set_document(document)
    view.show()
    app.processEvents()

    report_widget = view.report()["widgets_by_id"][blocked_id]
    target = view.anchor_decoration()["target"]
    assert report_widget["disposition"] == "Blocked"
    assert target["visible"] is False
    assert target["object_id"] == blocked_id
    assert target["disposition"] == "Blocked"
    assert target["reason"] == "blocked"
    assert view.target_pane.preview._document["selection"]["object_id"] == ""
    assert document == before

    view.close()
    view.deleteLater()
    app.processEvents()


def test_ui_menu_toggles_one_reused_umg_widget_view_non_destructively() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_i18n import painter_text
    from app.painter_ui_document import add_ui_object

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _document()
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.resize(1440, 820)
    dialog.show()
    app.processEvents()

    before = copy.deepcopy(dialog._painter_ui_document)
    undo_count = len(dialog._undo_stack)
    action = dialog._painter_umg_widget_view_action
    assert (
        _find_menu_action(
            dialog._painter_ui_menu,
            painter_text("UMG Widget View"),
        )
        is action
    )
    assert action.text() == painter_text("UMG Widget View")
    assert action.isCheckable()
    assert not action.isChecked()

    action.trigger()
    app.processEvents()
    view = dialog._painter_umg_widget_view
    assert dialog._canvas_workspace_mode == "ui_design"
    assert action.isChecked()
    assert view.isVisible()
    assert view.report()["source"]["revision"] == before["revision"]
    assert dialog._painter_ui_document == before
    assert len(dialog._undo_stack) == undo_count

    updated, _label = add_ui_object(
        dialog._painter_ui_document,
        kind="text",
        name="Live status",
        x=48,
        y=32,
        width=220,
        height=32,
        content={"text": "Connected"},
    )
    dialog._painter_ui_document = updated
    dialog._refresh_painter_ui_overlay()
    app.processEvents()
    assert view.report()["source"]["revision"] == updated["revision"]
    assert len(view.report()["widgets"]) == 4
    assert len(dialog._undo_stack) == undo_count

    action.trigger()
    app.processEvents()
    assert not action.isChecked()
    assert not view.isVisible()

    action.trigger()
    app.processEvents()
    assert action.isChecked()
    assert dialog._painter_umg_widget_view is view
    assert dialog._canvas_workspace_mode == "ui_design"
    assert dialog._painter_ui_document == updated
    assert len(dialog._undo_stack) == undo_count

    dialog._set_canvas_workspace_mode("paint")
    app.processEvents()
    assert dialog._canvas_workspace_mode == "paint"
    assert not action.isChecked()
    assert not view.isVisible()

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_logo_main_menu_view_uses_the_same_umg_widget_view_state() -> None:
    _app()
    from PySide6.QtWidgets import QWidget

    from app.painter_i18n import painter_text
    from app.painter_ui_main_menu import build_painter_ui_main_menu

    owner = QWidget()
    invoked: list[bool] = []
    menu = build_painter_ui_main_menu(
        owner,
        callbacks={
            "toggle_umg_widget_view": (
                lambda checked=False: invoked.append(bool(checked))
            )
        },
        source_menus={},
        state={"umg_widget_view": True},
    )

    action = _find_menu_action(menu, painter_text("UMG Widget View"))
    assert action is not None
    assert action.isCheckable()
    assert action.isChecked()
    action.trigger()
    assert invoked == [False]

    menu.deleteLater()
    owner.deleteLater()


def test_umg_widget_view_action_surface_shows_and_hides_the_same_view() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _document()
    registry = ActionRegistry(owner=dialog)
    action_id = "paint.ui.umg.widget_view.set"
    assert action_id in {row["id"] for row in registry.list_actions()}

    shown = registry.execute(action_id, {"visible": True}).to_dict()
    app.processEvents()
    view = dialog._painter_umg_widget_view
    assert shown["ok"] is True
    assert shown["changed"] is False
    assert dialog._canvas_workspace_mode == "ui_design"
    assert dialog._painter_umg_widget_view_action.isChecked()
    assert view.isVisible()

    hidden = registry.execute(action_id, {"visible": False}).to_dict()
    app.processEvents()
    assert hidden["ok"] is True
    assert hidden["changed"] is False
    assert dialog._painter_umg_widget_view is view
    assert not dialog._painter_umg_widget_view_action.isChecked()
    assert not view.isVisible()

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_umg_widget_view_renders_image_fill_and_explains_missing_files(
    tmp_path,
) -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage

    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    texture_path = tmp_path / "panel.png"
    image = QImage(8, 4, QImage.Format.Format_ARGB32)
    image.fill(QColor("#2F6FED"))
    assert image.save(str(texture_path))

    document = create_ui_document(320, 200, name="Image Fill UMG")
    document, panel = add_ui_object(
        document,
        kind="frame",
        name="Image Panel",
        x=24,
        y=20,
        width=272,
        height=160,
        style={"radius": 10.0},
        content={
            "source_path": str(texture_path),
            "image_fit": "fit",
            "focal_x": 0.5,
            "focal_y": 0.5,
        },
    )
    document, label = add_ui_object(
        document,
        kind="text",
        name="Panel Label",
        parent_id=panel["id"],
        x=16,
        y=16,
        width=140,
        height=32,
        content={"text": "Still above background"},
    )
    document["selection"] = {
        "object_id": panel["id"],
        "object_ids": [panel["id"]],
    }

    view = PainterUMGWidgetView()
    view.resize(960, 600)
    view.set_document(document)
    view.show()
    app.processEvents()

    report = view.report()
    assert report["ready"] is True
    assert report["resource_warnings"] == []
    widget = report["widgets_by_id"][panel["id"]]
    assert widget["image_fill"]["status"] == "ready"
    assert widget["image_fill"]["image_fit"] == "fit"
    objects = {
        row["id"]: row for row in report["document"]["objects"]
    }
    assert objects[panel["id"]]["content"]["source_path"] == str(
        texture_path
    )
    assert objects[label["id"]]["parent_id"] == panel["id"]
    assert not view.issue_label.isVisible()

    missing_path = tmp_path / "does-not-exist.png"
    document, _panel = update_ui_object(
        document,
        panel["id"],
        {
            "content": {
                **panel["content"],
                "source_path": str(missing_path),
            }
        },
    )
    view.set_document(document)
    app.processEvents()
    missing_report = view.report()
    assert missing_report["ready"] is False
    assert missing_report["resource_warnings"][0]["status"] == "missing_file"
    assert "Images:" in view.issue_label.text()
    assert "Image file not found" in view.issue_label.text()
    assert str(missing_path) in view.issue_label.text()

    view.close()
    view.deleteLater()
    app.processEvents()


def test_umg_widget_view_draws_blocked_layers_as_a_labelled_reference() -> None:
    app = _app()
    from app.painter_i18n import painter_text
    from app.painter_ui_umg_simulator import (
        UMG_REFERENCE_ID_PREFIX,
        UMG_REFERENCE_ONLY_KEY,
    )
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    document = _document()
    blocked_id = next(
        row["id"] for row in document["objects"] if row["name"] == "Gradient card"
    )
    view = PainterUMGWidgetView()
    view.resize(980, 620)
    view.set_document(document)
    view.show()
    app.processEvents()

    # Default on: a frame whose art is mostly blocked would otherwise render
    # almost empty and read as a broken import rather than an export limit.
    assert view.reference_visible() is True
    assert view.reference_button.isChecked() is True
    reference_id = f"{UMG_REFERENCE_ID_PREFIX}{blocked_id}"
    assert view.report()["reference_object_ids"] == [reference_id]
    target = view.target_pane.preview._document
    row = next(
        item for item in target["objects"] if item["id"] == reference_id
    )
    assert row["locked"] is True
    assert row["opacity"] < 1.0
    assert (
        row["content"][UMG_REFERENCE_ONLY_KEY]["source_object_id"] == blocked_id
    )
    assert f"{painter_text('Reference')} 1" in view.summary_label.text()

    view.reference_button.setChecked(False)
    app.processEvents()

    assert view.reference_visible() is False
    assert view.report()["reference_object_ids"] == []
    assert all(
        not str(item["id"]).startswith(UMG_REFERENCE_ID_PREFIX)
        for item in view.target_pane.preview._document["objects"]
    )
    assert painter_text("Reference") not in view.summary_label.text()
    # Readiness is a property of the export, never of the preview toggle.
    assert view.report()["counts"]["Blocked"] == 1

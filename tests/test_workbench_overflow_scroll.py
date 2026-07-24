from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _wheel_event(widget, *, delta: int = -120, modifiers=None):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QWheelEvent

    if modifiers is None:
        modifiers = Qt.KeyboardModifier.NoModifier
    point = QPoint(20, 20)
    return QWheelEvent(
        point,
        widget.mapToGlobal(point),
        QPoint(0, 0),
        QPoint(0, int(delta)),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def _header_disclosure_buttons(host):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton

    names = {"CollapsibleSectionHeader", "MediaPoolCollapsibleSectionHeader"}
    layout = host.layout()
    if layout is None:
        return []
    buttons = []
    for idx in range(layout.count()):
        item = layout.itemAt(idx)
        widget = item.widget() if item is not None else None
        if widget is None or widget.objectName() not in names:
            continue
        buttons.extend(
            widget.findChildren(
                QPushButton,
                "SectionDisclosure",
                Qt.FindChildOption.FindDirectChildrenOnly,
            )
        )
    return buttons


def _open_host_section(app, editor, host):
    buttons = _header_disclosure_buttons(host)
    assert len(buttons) == 1
    button = buttons[0]
    if not button.isChecked():
        button.click()
    for _ in range(4):
        app.processEvents()
    return button


def test_workbench_plain_wheel_scrolls_right_overflow_stack() -> None:
    app = _app()
    from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

    from app.workbench_panel import WorkbenchPanel

    root = QWidget()
    layout = QVBoxLayout(root)
    panel = WorkbenchPanel(root)
    layout.addWidget(panel)
    overflow = QScrollArea(root)
    overflow.setObjectName("RightDockScroll")
    overflow.setWidgetResizable(True)
    inner = QWidget()
    inner.setMinimumHeight(520)
    overflow.setWidget(inner)
    overflow.setFixedHeight(80)
    layout.addWidget(overflow)
    root.resize(520, 440)
    root.show()
    app.processEvents()

    bar = overflow.verticalScrollBar()
    old_value = bar.value()
    event = _wheel_event(panel)
    panel.wheelEvent(event)
    app.processEvents()

    assert event.isAccepted() is True
    assert bar.value() > old_value
    root.close()


def test_node_graph_plain_wheel_scrolls_overflow_and_ctrl_wheel_zooms() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

    from app.workbench.node_graph.widget import NodeGraphWidget

    root = QWidget()
    layout = QVBoxLayout(root)
    graph = NodeGraphWidget(root)
    layout.addWidget(graph)
    overflow = QScrollArea(root)
    overflow.setObjectName("RightDockScroll")
    overflow.setWidgetResizable(True)
    inner = QWidget()
    inner.setMinimumHeight(520)
    overflow.setWidget(inner)
    overflow.setFixedHeight(80)
    layout.addWidget(overflow)
    root.resize(520, 440)
    root.show()
    app.processEvents()

    bar = overflow.verticalScrollBar()
    start_zoom = graph.view.zoom_level()
    plain = _wheel_event(graph.view)
    graph.view.wheelEvent(plain)
    app.processEvents()

    assert plain.isAccepted() is True
    assert bar.value() > 0
    assert graph.view.zoom_level() == start_zoom

    ctrl = _wheel_event(
        graph.view,
        delta=120,
        modifiers=Qt.KeyboardModifier.ControlModifier,
    )
    graph.view.wheelEvent(ctrl)
    app.processEvents()

    assert ctrl.isAccepted() is True
    assert graph.view.zoom_level() > start_zoom
    root.close()


def test_video_editor_uses_one_scroll_area_for_workbench_and_tools() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSplitter

    from app.i18n import set_language
    from app.video_editor_window import VideoEditorWindow

    set_language("ko")
    editor = VideoEditorWindow()
    editor.resize(1650, 930)
    editor.show()
    app.processEvents()

    assert isinstance(editor._top_work_splitter, QSplitter)
    assert editor._top_work_splitter.orientation() == Qt.Orientation.Horizontal
    assert editor._top_work_splitter.indexOf(editor._viewer_column) == 0
    assert editor._top_work_splitter.indexOf(editor._top_workbench_slot) == 1
    assert editor._top_work_splitter.childrenCollapsible() is False
    assert editor._top_work_splitter.handleWidth() >= 5
    assert isinstance(editor._editor_vertical_splitter, QSplitter)
    assert editor._editor_vertical_splitter.orientation() == Qt.Orientation.Vertical
    assert editor._editor_vertical_splitter.indexOf(editor._main_dock_splitter) == 0
    assert editor._editor_vertical_splitter.indexOf(editor._color_timeline_splitter) == 1
    assert editor._editor_vertical_splitter.childrenCollapsible() is False
    assert editor._editor_vertical_splitter.handleWidth() >= 6
    assert editor._main_dock_splitter.maximumHeight() > 10000
    assert editor._top_work_area.maximumHeight() > 10000
    assert editor._preview_host.maximumHeight() > 10000
    assert editor._timeline_section_host.maximumHeight() > 10000
    assert isinstance(editor._left_dock_sections_splitter, QSplitter)
    assert editor._left_dock_sections_splitter.orientation() == Qt.Orientation.Vertical
    assert editor._left_dock_sections_splitter.indexOf(editor._media_pool_section_host) == 0
    assert editor._left_dock_sections_splitter.indexOf(editor._left_secondary_sections_host) == 1
    assert editor._left_dock_sections_splitter.childrenCollapsible() is False
    assert editor._left_dock_sections_splitter.handleWidth() >= 5
    assert editor._actor_library_section_host.parentWidget() is editor._left_secondary_sections_host
    assert editor._effects_library_section_host.parentWidget() is editor._left_secondary_sections_host
    assert isinstance(editor._right_dock_sections_splitter, QSplitter)
    assert editor._right_dock_sections_splitter.orientation() == Qt.Orientation.Vertical
    assert editor._right_dock_sections_splitter.indexOf(editor._right_workbench_pane) == 0
    assert editor._right_dock_sections_splitter.indexOf(editor._right_secondary_sections_host) == 1
    assert editor._right_dock_sections_splitter.childrenCollapsible() is False
    assert editor._right_dock_sections_splitter.handleWidth() >= 5
    assert editor._right_dock_scroll.parentWidget() is editor._top_workbench_slot
    assert editor._right_dock_scroll.maximumHeight() > 108
    assert editor._workbench_section_host.parentWidget() is editor._right_workbench_pane
    assert editor._workbench_section_host.minimumHeight() >= 500
    assert editor._workbench_section_host.height() >= 500

    assert editor._right_dock_layout.indexOf(editor._right_dock_sections_splitter) == 0
    workbench_idx = editor._right_workbench_pane_layout.indexOf(editor._workbench_section_host)
    creator_idx = editor._right_secondary_sections_layout.indexOf(editor._creator_assist_section_host)
    ai_idx = editor._right_secondary_sections_layout.indexOf(editor._ai_command_section_host)
    subtitle_idx = editor._right_secondary_sections_layout.indexOf(editor._subtitle_section_host)
    assert workbench_idx == 0
    assert creator_idx == 0
    assert ai_idx > creator_idx
    assert subtitle_idx > ai_idx
    assert editor._subtitle_section_host.objectName() == "WorkbenchSectionHost"
    assert editor._creator_ppt_maker_btn is None
    assert editor._creator_unreal_engine_link_btn is None
    assert editor._creator_tools_body.isVisible() is False

    initial_scroll = editor._right_dock_scroll.verticalScrollBar().value()
    editor._show_ai_command_dock()
    app.processEvents()
    app.processEvents()
    assert editor._ai_command_section_host.height() >= 120
    assert editor._ai_command_dock.height() >= 90
    assert editor._ai_command_input.isVisible() is True
    assert editor._ai_command_status.isVisible() is True
    assert editor._right_dock_scroll.verticalScrollBar().value() > initial_scroll

    bar = editor._right_dock_scroll.verticalScrollBar()
    bar.setValue(0)
    app.processEvents()
    old_value = bar.value()
    event = _wheel_event(editor._workbench_panel)
    editor._workbench_panel.wheelEvent(event)
    app.processEvents()

    assert event.isAccepted() is True
    assert bar.value() > old_value
    editor.close()


def test_workbench_lower_sections_stay_bounded_and_scroll_into_view() -> None:
    app = _app()
    from PySide6.QtWidgets import QPushButton, QScrollArea

    from app.i18n import set_language
    from app.video_editor_window import VideoEditorWindow

    set_language("ko")
    editor = VideoEditorWindow()
    editor.resize(1650, 930)
    editor.show()
    for _ in range(4):
        app.processEvents()

    sections = [
        (editor._creator_assist_section_host, 320),
        (editor._ai_command_section_host, 136),
        (editor._ai_script_edit_section_host, 320),
        (editor._render_queue_section_host, 320),
        (editor._audio_workspace_section_host, 154),
        (editor._subtitle_section_host, 320),
    ]
    scroll = editor._right_dock_scroll
    viewport = scroll.viewport()

    for host, expected_height in sections:
        button = _open_host_section(app, editor, host)

        assert host.minimumHeight() == expected_height
        assert host.maximumHeight() == expected_height
        assert host.height() <= expected_height
        assert button.isVisible() is True

        button_y = button.mapTo(viewport, button.rect().topLeft()).y()
        assert 0 <= button_y <= viewport.height() - min(button.height(), viewport.height())

    creator_scroll = editor._creator_assist_scroll_area
    assert isinstance(creator_scroll, QScrollArea)
    assert creator_scroll.widget() is editor._creator_assist_panel
    assert creator_scroll.verticalScrollBar().maximum() > 0
    assert editor._creator_assist_panel.minimumHeight() >= 440
    render_scroll = editor._render_queue_scroll_area
    assert isinstance(render_scroll, QScrollArea)
    assert render_scroll.widget().minimumHeight() >= 440
    assert render_scroll.verticalScrollBar().maximum() > 0
    assert editor._subtitle_panel_toggle_btn.objectName() == "ToolButton"
    assert len(editor._subtitle_section_host.findChildren(QPushButton, "SectionDisclosure")) == 1
    editor.close()

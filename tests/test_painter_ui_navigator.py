from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_ui_navigator_lists_pages_filters_layers_and_emits_selection() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget

    from app.painter_ui_navigator import PainterUINavigatorPanel

    layers_page = QWidget()
    layer_list = QListWidget(layers_page)
    layer_list.addItem(QListWidgetItem("Header"))
    layer_list.addItem(QListWidgetItem("Footer"))
    panel = PainterUINavigatorPanel(layers_page, layer_list)
    selected: list[str] = []
    added: list[bool] = []
    removed: list[str] = []
    renamed: list[tuple[str, str]] = []
    panel.page_selected.connect(selected.append)
    panel.page_add_requested.connect(lambda: added.append(True))
    panel.page_remove_requested.connect(removed.append)
    panel.page_rename_requested.connect(
        lambda page_id, name: renamed.append((page_id, name))
    )
    panel.set_document(
        {
            "active_page_id": "page-desktop",
            "pages": [
                {"id": "page-mobile", "name": "Mobile"},
                {"id": "page-desktop", "name": "Desktop"},
            ],
        }
    )

    assert panel.page_list.count() == 2
    assert panel.page_list.currentItem().text() == "Desktop"
    panel.page_list.setCurrentRow(0)
    app.processEvents()
    assert selected == ["page-mobile"]
    panel.page_add_button.click()
    assert added == [True]
    panel.page_list.currentItem().setText("Phone")
    app.processEvents()
    assert renamed == [("page-mobile", "Phone")]
    panel.page_remove_button.click()
    assert removed == ["page-mobile"]

    panel.search_edit.setText("head")
    assert not layer_list.item(0).isHidden()
    assert layer_list.item(1).isHidden()
    assert all(
        panel.page_list.item(index).isHidden()
        for index in range(panel.page_list.count())
    )
    assert panel.mode_tabs.count() == 2
    assert panel.mode_tabs.tabText(0) == "Layers"
    assert panel.mode_tabs.tabText(1) == "Assets"
    panel.set_collapsed(True)
    assert panel.is_collapsed()
    assert panel.maximumWidth() == 0
    panel.collapse_button.click()
    assert not panel.is_collapsed()
    assert panel.minimumWidth() == panel.DEFAULT_EXPANDED_WIDTH
    assert (
        panel.content_scroll.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    )
    panel.deleteLater()


def test_ui_navigator_resizes_and_restores_last_expanded_width() -> None:
    _app()
    from PySide6.QtWidgets import QListWidget, QWidget

    from app.painter_ui_navigator import PainterUINavigatorPanel

    panel = PainterUINavigatorPanel(QWidget(), QListWidget())
    changed: list[int] = []
    panel.width_changed.connect(changed.append)

    assert panel.set_expanded_width(300, user_initiated=True) == 300
    assert panel.minimumWidth() == 300
    assert panel.maximumWidth() == 300
    assert panel._collapse_user_override is True
    panel.set_collapsed(True)
    assert panel.width() == 0
    panel.set_collapsed(False)
    assert panel.minimumWidth() == 300
    assert panel.maximumWidth() == 300
    assert panel.expanded_width() == 300

    assert panel.set_expanded_width(20) == panel.MIN_EXPANDED_WIDTH
    assert panel.set_expanded_width(999) == 999
    assert changed == [300, panel.MIN_EXPANDED_WIDTH, 999]
    panel.restore_state(176, True, user_override=True)
    assert panel.expanded_width() == 176
    assert panel.is_collapsed()
    assert panel.has_user_collapse_override()
    panel.deleteLater()


def test_ui_navigator_auto_hide_temporarily_expands_without_pinning() -> None:
    _app()
    from PySide6.QtWidgets import QListWidget, QWidget

    from app.painter_ui_navigator import PainterUINavigatorPanel

    panel = PainterUINavigatorPanel(QWidget(), QListWidget())
    closed: list[bool] = []
    pinned: list[bool] = []
    panel.temporary_close_requested.connect(lambda: closed.append(True))
    panel.pin_requested.connect(lambda: pinned.append(True))

    panel.set_auto_hide(True)
    assert panel.is_auto_hide()
    assert panel.is_collapsed()
    assert panel.maximumWidth() == 0

    panel.set_temporary_expanded(True)
    assert panel.is_temporary_expanded()
    assert panel.is_collapsed()
    assert panel.minimumWidth() == panel.MIN_EXPANDED_WIDTH
    assert not panel.pin_button.isHidden()
    panel.pin_button.click()
    panel.collapse_button.click()
    assert pinned == [True]
    assert closed == [True]

    panel.set_temporary_expanded(False)
    assert panel.maximumWidth() == 0
    panel.deleteLater()


def test_inspector_can_move_layers_page_to_split_workspace() -> None:
    _app()
    from app.painter_ui_inspector import PainterUIInspector

    inspector = PainterUIInspector()
    assert inspector._tabs.count() == 9
    page = inspector.take_layers_page()
    assert page is inspector.layers_page
    assert inspector._tabs.count() == 8
    assert inspector._tabs.indexOf(page) == -1
    assert inspector._tabs.tabWhatsThis(inspector._tabs.currentIndex()) == "Design"
    assets = inspector.take_asset_pages()
    assert list(assets) == [
        "Sections",
        "Components",
        "Styles",
        "Libraries",
        "Tokens",
    ]
    assert inspector._tabs.count() == 3
    assert [
        inspector._tabs.tabText(index)
        for index in range(inspector._tabs.count())
    ] == ["Design", "Prototype", "Inspect"]
    inspector.set_collapsed(True)
    assert inspector.is_collapsed()
    assert inspector._tabs.isHidden()
    inspector.collapse_button.click()
    assert not inspector.is_collapsed()
    inspector.deleteLater()


def test_split_layers_use_icons_without_developer_type_suffixes() -> None:
    _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document(390, 844, name="Mobile")
    document, _row = add_ui_object(
        document,
        kind="rectangle",
        name="Primary Card",
        x=20,
        y=40,
        width=160,
        height=80,
    )
    inspector = PainterUIInspector()
    inspector.set_document(document)
    item = inspector.layer_list.item(0)
    assert item.text() == "Primary Card"
    assert not item.icon().isNull()
    assert item.toolTip().startswith("rectangle")
    inspector.deleteLater()

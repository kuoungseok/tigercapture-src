from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_ui_navigator_lists_pages_filters_layers_and_emits_selection() -> None:
    app = _app()
    from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget

    from app.painter_ui_navigator import PainterUINavigatorPanel

    layers_page = QWidget()
    layer_list = QListWidget(layers_page)
    layer_list.addItem(QListWidgetItem("Header"))
    layer_list.addItem(QListWidgetItem("Footer"))
    panel = PainterUINavigatorPanel(layers_page, layer_list)
    selected: list[str] = []
    panel.artboard_selected.connect(selected.append)
    panel.set_document(
        {
            "active_artboard_id": "desktop",
            "artboards": [
                {"id": "mobile", "name": "Mobile", "width": 390, "height": 844},
                {"id": "desktop", "name": "Desktop", "width": 1440, "height": 900},
            ],
        }
    )

    assert panel.page_list.count() == 2
    assert panel.page_list.currentItem().text() == "Desktop"
    panel.page_list.setCurrentRow(0)
    app.processEvents()
    assert selected == ["mobile"]

    panel.search_edit.setText("head")
    assert not layer_list.item(0).isHidden()
    assert layer_list.item(1).isHidden()
    assert all(
        panel.page_list.item(index).isHidden()
        for index in range(panel.page_list.count())
    )
    panel.deleteLater()


def test_inspector_can_move_layers_page_to_split_workspace() -> None:
    _app()
    from app.painter_ui_inspector import PainterUIInspector

    inspector = PainterUIInspector()
    assert inspector._tabs.count() == 7
    page = inspector.take_layers_page()
    assert page is inspector.layers_page
    assert inspector._tabs.count() == 6
    assert inspector._tabs.indexOf(page) == -1
    assert inspector._tabs.tabWhatsThis(inspector._tabs.currentIndex()) == "Inspect"
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

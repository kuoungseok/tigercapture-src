from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_preferred_instance_dialog_adds_removes_and_reorders_without_filtering() -> None:
    app = _app()
    from app.painter_ui_component_preferred_values_dialog import (
        PainterUIInstanceSwapPreferredDialog,
    )
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_property,
        set_ui_component_instance_swap_preferred_values,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    components = []
    for name in ("Card", "Icon A", "Icon B", "Icon C"):
        document, root = add_ui_object(
            document,
            kind="frame",
            name=name,
            width=80,
            height=40,
        )
        document, component = convert_ui_object_to_component(
            document,
            root_object_id=root["id"],
            name=name,
        )
        components.append(component)
    card, icon_a, icon_b, icon_c = components
    document, _definition = define_ui_component_property(
        document,
        component_id=card["id"],
        property_name="Icon",
        definition={"type": "instance_swap", "default": icon_a["id"]},
    )
    document, _definition = set_ui_component_instance_swap_preferred_values(
        document,
        component_id=card["id"],
        property_name="Icon",
        preferred_component_ids=[icon_b["id"], icon_a["id"]],
    )

    dialog = PainterUIInstanceSwapPreferredDialog(
        document,
        component_id=card["id"],
        property_name="Icon",
    )
    assert dialog.preferred_component_ids() == [icon_b["id"], icon_a["id"]]
    assert dialog.available_list.count() == 4

    candidates = {
        str(dialog.available_list.item(index).data(Qt.ItemDataRole.UserRole)):
        dialog.available_list.item(index)
        for index in range(dialog.available_list.count())
    }
    candidates[icon_b["id"]].setCheckState(Qt.CheckState.Unchecked)
    candidates[icon_c["id"]].setCheckState(Qt.CheckState.Checked)
    dialog.preferred_list.setCurrentRow(1)
    dialog.move_up_button.click()
    app.processEvents()

    assert dialog.preferred_component_ids() == [icon_c["id"], icon_a["id"]]
    dialog.search_edit.setText("Icon C")
    app.processEvents()
    assert candidates[icon_c["id"]].isHidden() is False
    assert candidates[icon_a["id"]].isHidden() is True
    dialog.deleteLater()
    app.processEvents()

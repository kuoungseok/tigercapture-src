"""Component library panel for Painter UI Design documents."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_document import normalize_ui_document


def inspect_ui_component_library(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    components = {row["id"]: row for row in document["components"]}
    instance_counts = {
        component_id: sum(
            1
            for row in document["objects"]
            if row["component_role"] == "instance"
            and row["component_id"] == component_id
            and row["component_source_object_id"]
            == components[component_id]["root_object_id"]
        )
        for component_id in components
    }
    families: list[dict[str, Any]] = []
    for component in document["components"]:
        if component["base_component_id"]:
            continue
        member_ids = [
            component["id"],
            *[
                variant_id
                for variant_id in component["variant_ids"]
                if variant_id in components
            ],
        ]
        members = [
            {
                "component_id": member_id,
                "name": components[member_id]["name"],
                "root_object_id": components[member_id]["root_object_id"],
                "variant_key": str(
                    components[member_id]["metadata"].get("variant_key") or ""
                ),
                "instance_count": instance_counts.get(member_id, 0),
                "is_base": member_id == component["id"],
            }
            for member_id in member_ids
        ]
        families.append(
            {
                "family_id": component["id"],
                "name": component["name"],
                "variant_count": max(0, len(members) - 1),
                "instance_count": sum(
                    int(member["instance_count"]) for member in members
                ),
                "members": members,
            }
        )
    return {
        "schema": "tigerstudio.painter.ui.component_library.inspect.v1",
        "family_count": len(families),
        "component_count": len(components),
        "instance_count": sum(instance_counts.values()),
        "families": families,
    }


class PainterUIComponentLibrary(QWidget):
    object_selected = Signal(str)
    instantiate_requested = Signal(str, str, float, float)
    variant_create_requested = Signal(str, str)
    component_update_requested = Signal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = normalize_ui_document(None)
        self._syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search components")
        self.search_edit.textChanged.connect(self._rebuild)
        layout.addWidget(self.search_edit)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(14)
        self.tree.currentItemChanged.connect(self._sync_selection)
        self.tree.itemDoubleClicked.connect(
            lambda _item, _column: self._emit_select_definition()
        )
        layout.addWidget(self.tree, 1)

        self.status_label = QLabel("No components")
        self.status_label.setObjectName("PaintMuted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Component name")
        self.name_edit.returnPressed.connect(self._emit_rename)
        layout.addWidget(self.name_edit)

        commands = QFrame()
        command_layout = QHBoxLayout(commands)
        command_layout.setContentsMargins(0, 0, 0, 0)
        command_layout.setSpacing(3)
        self.select_button = QPushButton("Select")
        self.select_button.clicked.connect(self._emit_select_definition)
        self.instance_button = QPushButton("Instance")
        self.instance_button.clicked.connect(self._emit_instance)
        self.variant_button = QPushButton("Variant")
        self.variant_button.clicked.connect(self._emit_variant)
        self.rename_button = QPushButton("Rename")
        self.rename_button.clicked.connect(self._emit_rename)
        for button in (
            self.select_button,
            self.instance_button,
            self.variant_button,
            self.rename_button,
        ):
            command_layout.addWidget(button)
        layout.addWidget(commands)

    def set_document(self, value: Mapping[str, Any]) -> None:
        selected_component_id = self._selected_component_id()
        self._document = normalize_ui_document(value)
        self._rebuild(selected_component_id)

    def select_component(self, component_id: str) -> bool:
        target = str(component_id or "")
        self._rebuild(target)
        return self._selected_component_id() == target

    def _selected_component_id(self) -> str:
        item = self.tree.currentItem()
        return (
            str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            if item is not None
            else ""
        )

    def _component(self, component_id: str) -> dict[str, Any] | None:
        return next(
            (
                row
                for row in self._document["components"]
                if row["id"] == component_id
            ),
            None,
        )

    def _rebuild(self, preferred_component_id: str = "") -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            preferred = str(preferred_component_id or self._selected_component_id())
            query = self.search_edit.text().strip().casefold()
            report = inspect_ui_component_library(self._document)
            self.tree.clear()
            selected_item: QTreeWidgetItem | None = None
            for family in report["families"]:
                member_names = " ".join(
                    str(member["name"]) for member in family["members"]
                ).casefold()
                if query and query not in str(family["name"]).casefold() and query not in member_names:
                    continue
                family_item = QTreeWidgetItem(
                    [
                        (
                            f"{family['name']}  "
                            f"({family['variant_count']} variants, "
                            f"{family['instance_count']} instances)"
                        )
                    ]
                )
                family_item.setData(
                    0, Qt.ItemDataRole.UserRole, str(family["family_id"])
                )
                family_item.setData(0, Qt.ItemDataRole.UserRole + 1, "base")
                self.tree.addTopLevelItem(family_item)
                if family["family_id"] == preferred:
                    selected_item = family_item
                for member in family["members"]:
                    if member["is_base"]:
                        continue
                    label = str(member["variant_key"] or member["name"])
                    variant_item = QTreeWidgetItem(
                        [f"{label}  ({member['instance_count']} instances)"]
                    )
                    variant_item.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        str(member["component_id"]),
                    )
                    variant_item.setData(
                        0, Qt.ItemDataRole.UserRole + 1, "variant"
                    )
                    family_item.addChild(variant_item)
                    if member["component_id"] == preferred:
                        selected_item = variant_item
                family_item.setExpanded(True)
            if selected_item is None and self.tree.topLevelItemCount():
                selected_item = self.tree.topLevelItem(0)
            if selected_item is not None:
                self.tree.setCurrentItem(selected_item)
            else:
                self._sync_selection(None)
        finally:
            self._syncing = False
        self._sync_selection(self.tree.currentItem())

    def _sync_selection(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None = None,
    ) -> None:
        component = self._component(
            str(current.data(0, Qt.ItemDataRole.UserRole) or "")
            if current is not None
            else ""
        )
        enabled = component is not None
        for widget in (
            self.name_edit,
            self.select_button,
            self.instance_button,
            self.variant_button,
            self.rename_button,
        ):
            widget.setEnabled(enabled)
        if component is None:
            self.name_edit.clear()
            self.status_label.setText("No components")
            return
        self.name_edit.setText(str(component["name"]))
        report = inspect_ui_component_library(self._document)
        family = next(
            (
                row
                for row in report["families"]
                if any(
                    member["component_id"] == component["id"]
                    for member in row["members"]
                )
            ),
            None,
        )
        self.status_label.setText(
            (
                f"{'Base' if not component['base_component_id'] else 'Variant'}"
                f"  |  {int((family or {}).get('variant_count', 0))} variants"
                f"  |  {int((family or {}).get('instance_count', 0))} instances"
            )
        )

    def _emit_select_definition(self) -> None:
        component = self._component(self._selected_component_id())
        if component is not None:
            self.object_selected.emit(str(component["root_object_id"]))

    def _emit_instance(self) -> None:
        component = self._component(self._selected_component_id())
        if component is None:
            return
        root = next(
            (
                row
                for row in self._document["objects"]
                if row["id"] == component["root_object_id"]
            ),
            None,
        )
        if root is None:
            return
        self.instantiate_requested.emit(
            str(component["id"]),
            str(self._document["active_artboard_id"]),
            float(root["x"]) + 32.0,
            float(root["y"]) + 32.0,
        )

    def _emit_variant(self) -> None:
        component = self._component(self._selected_component_id())
        if component is not None:
            self.variant_create_requested.emit(
                str(component["id"]),
                f"{component['name']} Variant",
            )

    def _emit_rename(self) -> None:
        component_id = self._selected_component_id()
        name = self.name_edit.text().strip()
        if component_id and name:
            self.component_update_requested.emit(component_id, {"name": name})


__all__ = ["PainterUIComponentLibrary", "inspect_ui_component_library"]

"""Design-token library panel for Painter UI Design documents."""
from __future__ import annotations

import json
from typing import Any, Mapping

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_document import UI_TOKEN_KINDS, normalize_ui_document
from app.icons import app_icon
from app.painter_ui_themes import UI_THEME_MODES
from app.painter_ui_variables import (
    LEGACY_THEME_COLLECTION_ID,
    LEGACY_THEME_MODE_IDS,
    UI_VARIABLE_SCOPES,
    UI_VARIABLE_TYPES,
    inspect_ui_variable_collections,
)


TOKEN_BINDING_PATHS = UI_VARIABLE_SCOPES


def inspect_ui_token_library(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    bindings: dict[str, list[dict[str, str]]] = {
        row["id"]: [] for row in document["tokens"]
    }
    for obj in document["objects"]:
        for path, token_id in obj["token_bindings"].items():
            if token_id in bindings:
                bindings[token_id].append(
                    {
                        "object_id": str(obj["id"]),
                        "object_name": str(obj["name"]),
                        "path": str(path),
                    }
                )
    alias_references: dict[str, list[str]] = {
        row["id"]: [] for row in document["tokens"]
    }
    for token in document["tokens"]:
        alias_id = str(token["alias_token_id"])
        if alias_id in alias_references:
            alias_references[alias_id].append(str(token["id"]))
    token_by_id = {row["id"]: row for row in document["tokens"]}

    def alias_chain(token_id: str) -> list[str]:
        chain: list[str] = []
        current_id = str(token_id)
        while current_id and current_id not in chain:
            chain.append(current_id)
            current = token_by_id.get(current_id)
            current_id = str((current or {}).get("alias_token_id") or "")
        return chain

    tokens = [
        {
            **token,
            "usage_count": len(bindings[token["id"]]),
            "bindings": bindings[token["id"]],
            "alias_reference_ids": alias_references[token["id"]],
            "unused": not bindings[token["id"]]
            and not alias_references[token["id"]],
            "alias_chain": alias_chain(token["id"]),
        }
        for token in document["tokens"]
    ]
    return {
        "schema": "tigerstudio.painter.ui.token_library.inspect.v2",
        "token_count": len(tokens),
        "used_count": sum(not row["unused"] for row in tokens),
        "unused_count": sum(row["unused"] for row in tokens),
        "collections": inspect_ui_variable_collections(document)["collections"],
        "kinds": {
            kind: [row for row in tokens if row["kind"] == kind]
            for kind in sorted(UI_TOKEN_KINDS)
        },
        "tokens": tokens,
    }


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _parse_value(text: str) -> Any:
    value = str(text or "").strip()
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


class PainterUITokenLibrary(QWidget):
    token_add_requested = Signal(object)
    token_update_requested = Signal(str, object)
    token_remove_requested = Signal(str, bool)
    token_binding_requested = Signal(str, str, str)
    token_import_requested = Signal(str)
    token_export_requested = Signal()
    collection_add_requested = Signal(object)
    collection_update_requested = Signal(str, object)
    collection_remove_requested = Signal(str, bool)
    mode_add_requested = Signal(str, str)
    mode_update_requested = Signal(str, str, str)
    mode_remove_requested = Signal(str, str, bool)
    mode_set_requested = Signal(str, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUITokenLibrary")
        self.setStyleSheet(
            """
            QWidget#PainterUITokenLibrary {
                background: #111720;
                color: #DDE5EF;
            }
            QWidget#PainterUITokenLibrary QLabel {
                color: #AEB9C8;
                background: transparent;
                border: none;
            }
            QWidget#PainterUITokenLibrary QLineEdit,
            QWidget#PainterUITokenLibrary QComboBox,
            QWidget#PainterUITokenLibrary QTreeWidget {
                background: #0C1118;
                color: #E7EDF5;
                border: 1px solid #2B3543;
                border-radius: 4px;
                selection-background-color: #284B72;
                selection-color: #FFFFFF;
            }
            QWidget#PainterUITokenLibrary QTreeWidget {
                alternate-background-color: #101722;
            }
            QWidget#PainterUITokenLibrary QHeaderView::section {
                background: #161E29;
                color: #97A7BA;
                border: none;
                border-bottom: 1px solid #2B3543;
                padding: 3px 5px;
            }
            QWidget#PainterUITokenLibrary QPushButton {
                min-height: 24px;
                background: #192230;
                color: #DDE5EF;
                border: 1px solid #303C4C;
                border-radius: 4px;
                padding: 1px 7px;
            }
            QWidget#PainterUITokenLibrary QPushButton:hover {
                background: #233044;
                border-color: #4A6585;
            }
            QWidget#PainterUITokenLibrary QPushButton:disabled {
                color: #5F6B79;
                background: #111720;
            }
            """
        )
        self._document = normalize_ui_document(None)
        self._syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        collection_row = QHBoxLayout()
        self.collection_combo = QComboBox()
        self.collection_combo.setToolTip("Variable collection")
        self.collection_combo.currentIndexChanged.connect(
            self._collection_changed
        )
        self.collection_add_button = QPushButton("+")
        self.collection_add_button.setIcon(app_icon("plus", size=11))
        self.collection_add_button.setText("")
        self.collection_add_button.setFixedWidth(28)
        self.collection_add_button.setToolTip("New collection")
        self.collection_add_button.clicked.connect(self._emit_collection_add)
        self.collection_rename_button = QPushButton("Rename")
        self.collection_rename_button.clicked.connect(
            self._emit_collection_rename
        )
        self.collection_delete_button = QPushButton("Delete")
        self.collection_delete_button.setIcon(app_icon("trash", size=11))
        self.collection_delete_button.setText("")
        self.collection_delete_button.setFixedWidth(28)
        self.collection_delete_button.clicked.connect(
            self._emit_collection_remove
        )
        collection_row.addWidget(self.collection_combo, 1)
        collection_row.addWidget(self.collection_add_button)
        collection_row.addWidget(self.collection_rename_button)
        collection_row.addWidget(self.collection_delete_button)
        layout.addLayout(collection_row)

        mode_row = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.setToolTip("Active mode for this artboard")
        self.mode_combo.currentIndexChanged.connect(self._emit_mode_set)
        self.mode_add_button = QPushButton("+")
        self.mode_add_button.setIcon(app_icon("plus", size=11))
        self.mode_add_button.setText("")
        self.mode_add_button.setFixedWidth(28)
        self.mode_add_button.setToolTip("New mode")
        self.mode_add_button.clicked.connect(self._emit_mode_add)
        self.mode_rename_button = QPushButton("Rename")
        self.mode_rename_button.clicked.connect(self._emit_mode_rename)
        self.mode_delete_button = QPushButton("Delete")
        self.mode_delete_button.setIcon(app_icon("trash", size=11))
        self.mode_delete_button.setText("")
        self.mode_delete_button.setFixedWidth(28)
        self.mode_delete_button.clicked.connect(self._emit_mode_remove)
        mode_row.addWidget(QLabel("Mode"))
        mode_row.addWidget(self.mode_combo, 1)
        mode_row.addWidget(self.mode_add_button)
        mode_row.addWidget(self.mode_rename_button)
        mode_row.addWidget(self.mode_delete_button)
        layout.addLayout(mode_row)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search tokens")
        self.search_edit.textChanged.connect(self._rebuild)
        self.kind_filter = QComboBox()
        self.kind_filter.addItem("All kinds", "")
        for kind in sorted(UI_TOKEN_KINDS):
            self.kind_filter.addItem(kind.title(), kind)
        self.kind_filter.currentIndexChanged.connect(self._rebuild)
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.kind_filter)
        layout.addLayout(search_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Token", "Usage"])
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(14)
        self.tree.currentItemChanged.connect(self._sync_selection)
        layout.addWidget(self.tree, 1)

        self.status_label = QLabel("No tokens")
        self.status_label.setObjectName("PaintMuted")
        layout.addWidget(self.status_label)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(3)
        self.name_edit = QLineEdit()
        form.addRow("Name", self.name_edit)
        self.kind_combo = QComboBox()
        self.kind_combo.addItems(sorted(UI_TOKEN_KINDS))
        form.addRow("Kind", self.kind_combo)
        self.variable_type_combo = QComboBox()
        self.variable_type_combo.addItems(UI_VARIABLE_TYPES)
        form.addRow("Type", self.variable_type_combo)
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("Value or JSON")
        form.addRow("Default", self.value_edit)
        self.mode_value_edit = QLineEdit()
        self.mode_value_edit.setPlaceholderText("Inherit default")
        form.addRow("Mode value", self.mode_value_edit)
        # Kept as hidden compatibility inputs for older callers and documents.
        self.theme_edits: dict[str, QLineEdit] = {}
        for theme in UI_THEME_MODES:
            edit = QLineEdit()
            edit.setPlaceholderText("Inherit default")
            edit.hide()
            self.theme_edits[theme] = edit
        self.alias_combo = QComboBox()
        form.addRow("Alias", self.alias_combo)
        self.scope_edit = QLineEdit()
        self.scope_edit.setPlaceholderText("All properties")
        self.scope_edit.setToolTip(
            "Optional comma-separated property paths allowed for this variable"
        )
        form.addRow("Scope", self.scope_edit)
        self.description_edit = QLineEdit()
        form.addRow("Description", self.description_edit)
        layout.addLayout(form)

        commands = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self._emit_add)
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self._emit_update)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._emit_remove)
        commands.addWidget(self.new_button)
        commands.addWidget(self.apply_button)
        commands.addWidget(self.delete_button)
        layout.addLayout(commands)

        transfer_row = QHBoxLayout()
        self.conflict_policy_combo = QComboBox()
        self.conflict_policy_combo.addItem("Update conflicts", "update")
        self.conflict_policy_combo.addItem("Skip conflicts", "skip")
        self.conflict_policy_combo.addItem("Create new IDs", "regenerate")
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(
            lambda: self.token_import_requested.emit(
                str(self.conflict_policy_combo.currentData() or "update")
            )
        )
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.token_export_requested)
        transfer_row.addWidget(self.conflict_policy_combo, 1)
        transfer_row.addWidget(self.import_button)
        transfer_row.addWidget(self.export_button)
        layout.addLayout(transfer_row)

        binding_row = QHBoxLayout()
        self.binding_path_combo = QComboBox()
        self.binding_path_combo.addItems(TOKEN_BINDING_PATHS)
        self.bind_button = QPushButton("Bind")
        self.bind_button.clicked.connect(self._emit_bind)
        self.unbind_button = QPushButton("Unbind")
        self.unbind_button.clicked.connect(self._emit_unbind)
        binding_row.addWidget(self.binding_path_combo, 1)
        binding_row.addWidget(self.bind_button)
        binding_row.addWidget(self.unbind_button)
        layout.addLayout(binding_row)

    def set_document(self, value: Mapping[str, Any]) -> None:
        selected_token_id = self._selected_token_id()
        selected_collection_id = str(self.collection_combo.currentData() or "")
        self._document = normalize_ui_document(value)
        self._sync_collections(selected_collection_id)
        self._rebuild(selected_token_id)

    def select_token(self, token_id: str) -> bool:
        target = str(token_id or "")
        self._rebuild(target)
        return self._selected_token_id() == target

    def _selected_token_id(self) -> str:
        item = self.tree.currentItem()
        return (
            str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            if item is not None
            else ""
        )

    def _selected_object_id(self) -> str:
        return str(self._document["selection"]["object_id"] or "")

    def _token(self, token_id: str) -> dict[str, Any] | None:
        return next(
            (row for row in self._document["tokens"] if row["id"] == token_id),
            None,
        )

    def _selected_collection_id(self) -> str:
        return str(self.collection_combo.currentData() or "")

    def _selected_mode_id(self) -> str:
        return str(self.mode_combo.currentData() or "")

    def _selected_collection(self) -> dict[str, Any] | None:
        collection_id = self._selected_collection_id()
        return next(
            (
                row
                for row in self._document["variable_collections"]
                if row["id"] == collection_id
            ),
            None,
        )

    def _sync_collections(self, preferred_id: str = "") -> None:
        self._syncing = True
        try:
            active_artboard = next(
                row
                for row in self._document["artboards"]
                if row["id"] == self._document["active_artboard_id"]
            )
            self.collection_combo.clear()
            for collection in self._document["variable_collections"]:
                self.collection_combo.addItem(
                    str(collection["name"]),
                    str(collection["id"]),
                )
            target = preferred_id or (
                self._document["tokens"][0]["collection_id"]
                if self._document["tokens"]
                else self._document["variable_collections"][0]["id"]
            )
            index = self.collection_combo.findData(target)
            self.collection_combo.setCurrentIndex(max(0, index))
            self._sync_modes(active_artboard)
        finally:
            self._syncing = False

    def _sync_modes(self, artboard: Mapping[str, Any] | None = None) -> None:
        collection = self._selected_collection()
        self.mode_combo.clear()
        if collection is None:
            return
        for mode in collection["modes"]:
            self.mode_combo.addItem(str(mode["name"]), str(mode["id"]))
        if artboard is None:
            artboard = next(
                row
                for row in self._document["artboards"]
                if row["id"] == self._document["active_artboard_id"]
            )
        active_mode_id = str(
            artboard["variable_modes"].get(
                collection["id"],
                collection["default_mode_id"],
            )
        )
        index = self.mode_combo.findData(active_mode_id)
        self.mode_combo.setCurrentIndex(max(0, index))

    def _collection_changed(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            self._sync_modes()
        finally:
            self._syncing = False
        self._rebuild()

    def _rebuild(self, preferred_token_id: str = "") -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            preferred = str(preferred_token_id or self._selected_token_id())
            query = self.search_edit.text().strip().casefold()
            kind_filter = str(self.kind_filter.currentData() or "")
            collection_id = self._selected_collection_id()
            report = inspect_ui_token_library(self._document)
            self.tree.clear()
            selected_item: QTreeWidgetItem | None = None
            for kind, tokens in report["kinds"].items():
                if kind_filter and kind != kind_filter:
                    continue
                visible = [
                    row
                    for row in tokens
                    if row["collection_id"] == collection_id
                    and (
                        not query
                        or query in str(row["name"]).casefold()
                        or query in str(row["description"]).casefold()
                    )
                ]
                if not visible:
                    continue
                kind_item = QTreeWidgetItem([kind.title(), str(len(visible))])
                self.tree.addTopLevelItem(kind_item)
                for token in visible:
                    usage = int(token["usage_count"]) + len(
                        token["alias_reference_ids"]
                    )
                    token_item = QTreeWidgetItem(
                        [str(token["name"]), "Unused" if not usage else str(usage)]
                    )
                    token_item.setData(
                        0, Qt.ItemDataRole.UserRole, str(token["id"])
                    )
                    kind_item.addChild(token_item)
                    if token["id"] == preferred:
                        selected_item = token_item
                kind_item.setExpanded(True)
            if selected_item is None:
                for index in range(self.tree.topLevelItemCount()):
                    root = self.tree.topLevelItem(index)
                    if root.childCount():
                        selected_item = root.child(0)
                        break
            if selected_item is not None:
                self.tree.setCurrentItem(selected_item)
        finally:
            self._syncing = False
        self._sync_selection(self.tree.currentItem())

    def _sync_selection(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None = None,
    ) -> None:
        token = self._token(
            str(current.data(0, Qt.ItemDataRole.UserRole) or "")
            if current is not None
            else ""
        )
        enabled = token is not None
        for widget in (
            self.name_edit,
            self.kind_combo,
            self.variable_type_combo,
            self.value_edit,
            self.mode_value_edit,
            self.alias_combo,
            self.scope_edit,
            self.description_edit,
            self.apply_button,
            self.delete_button,
            self.bind_button,
            self.unbind_button,
        ):
            widget.setEnabled(enabled)
        self.alias_combo.clear()
        self.alias_combo.addItem("None", "")
        for row in self._document["tokens"]:
            if (
                token is None
                or (
                    row["id"] != token["id"]
                    and row["variable_type"] == token["variable_type"]
                )
            ):
                self.alias_combo.addItem(str(row["name"]), str(row["id"]))
        if token is None:
            self.name_edit.clear()
            self.value_edit.clear()
            self.mode_value_edit.clear()
            self.description_edit.clear()
            self.scope_edit.clear()
            for edit in self.theme_edits.values():
                edit.clear()
            self.status_label.setText("No tokens")
            return
        self.name_edit.setText(str(token["name"]))
        self.kind_combo.setCurrentText(str(token["kind"]))
        self.variable_type_combo.setCurrentText(str(token["variable_type"]))
        self.value_edit.setText(_format_value(token["value"]))
        self.mode_value_edit.setText(
            _format_value(token["mode_values"].get(self._selected_mode_id()))
        )
        for theme, edit in self.theme_edits.items():
            edit.setText(_format_value(token["theme_values"].get(theme)))
            edit.setEnabled(True)
        alias_index = self.alias_combo.findData(str(token["alias_token_id"]))
        self.alias_combo.setCurrentIndex(max(0, alias_index))
        self.description_edit.setText(str(token["description"]))
        self.scope_edit.setText(", ".join(token["scope"]))
        report = inspect_ui_token_library(self._document)
        row = next(item for item in report["tokens"] if item["id"] == token["id"])
        alias_names = [
            str((self._token(alias_id) or {}).get("name") or alias_id)
            for alias_id in row["alias_chain"]
        ]
        chain_text = (
            "  |  " + " -> ".join(alias_names)
            if len(alias_names) > 1
            else ""
        )
        self.status_label.setText(
            f"{row['usage_count']} bindings  |  "
            f"{len(row['alias_reference_ids'])} aliases  |  {token['id']}"
            f"{chain_text}"
        )
        has_object = bool(self._selected_object_id())
        self.bind_button.setEnabled(has_object)
        self.unbind_button.setEnabled(has_object)

    def _emit_add(self) -> None:
        self.token_add_requested.emit(
            {
                "name": "New Token",
                "kind": str(self.kind_combo.currentText() or "color"),
                "collection_id": self._selected_collection_id(),
                "variable_type": str(
                    self.variable_type_combo.currentText() or "string"
                ),
                "value": None,
            }
        )

    def _token_changes(self) -> dict[str, Any]:
        token = self._token(self._selected_token_id()) or {}
        mode_values = dict(token.get("mode_values") or {})
        mode_id = self._selected_mode_id()
        mode_text = self.mode_value_edit.text().strip()
        if mode_id:
            if mode_text:
                mode_values[mode_id] = _parse_value(mode_text)
            else:
                mode_values.pop(mode_id, None)
        theme_values = {
            theme: _parse_value(edit.text())
            for theme, edit in self.theme_edits.items()
            if edit.text().strip()
        }
        if self._selected_collection_id() == LEGACY_THEME_COLLECTION_ID:
            reverse_theme_ids = {
                mode_id: theme
                for theme, mode_id in LEGACY_THEME_MODE_IDS.items()
            }
            theme = reverse_theme_ids.get(mode_id)
            if theme:
                if mode_text:
                    theme_values[theme] = _parse_value(mode_text)
                else:
                    theme_values.pop(theme, None)
        return {
            "name": self.name_edit.text().strip() or "Token",
            "kind": str(self.kind_combo.currentText()),
            "collection_id": self._selected_collection_id(),
            "variable_type": str(self.variable_type_combo.currentText()),
            "variable_type_explicit": True,
            "value": _parse_value(self.value_edit.text()),
            "theme_values": theme_values,
            "mode_values": mode_values,
            "scope": [
                value.strip()
                for value in self.scope_edit.text().split(",")
                if value.strip()
            ],
            "alias_token_id": str(self.alias_combo.currentData() or ""),
            "description": self.description_edit.text().strip(),
        }

    def _emit_collection_add(self) -> None:
        name, ok = QInputDialog.getText(self, "New collection", "Name")
        if ok and name.strip():
            kind, kind_ok = QInputDialog.getItem(
                self,
                "Collection type",
                "Type",
                ("Theme", "Density", "Locale", "Platform", "Brand", "Custom"),
                5,
                False,
            )
            if not kind_ok:
                return
            self.collection_add_requested.emit(
                {
                    "name": name.strip(),
                    "kind": str(kind).strip().casefold(),
                }
            )

    def _emit_collection_rename(self) -> None:
        collection = self._selected_collection()
        if collection is None:
            return
        name, ok = QInputDialog.getText(
            self,
            "Rename collection",
            "Name",
            text=str(collection["name"]),
        )
        if ok and name.strip():
            self.collection_update_requested.emit(
                collection["id"],
                {"name": name.strip()},
            )

    def _emit_collection_remove(self) -> None:
        collection_id = self._selected_collection_id()
        if collection_id:
            self.collection_remove_requested.emit(collection_id, False)

    def _emit_mode_add(self) -> None:
        collection_id = self._selected_collection_id()
        if not collection_id:
            return
        name, ok = QInputDialog.getText(self, "New mode", "Name")
        if ok and name.strip():
            self.mode_add_requested.emit(collection_id, name.strip())

    def _emit_mode_rename(self) -> None:
        collection_id = self._selected_collection_id()
        mode_id = self._selected_mode_id()
        if not collection_id or not mode_id:
            return
        name, ok = QInputDialog.getText(
            self,
            "Rename mode",
            "Name",
            text=self.mode_combo.currentText(),
        )
        if ok and name.strip():
            self.mode_update_requested.emit(
                collection_id,
                mode_id,
                name.strip(),
            )

    def _emit_mode_remove(self) -> None:
        collection_id = self._selected_collection_id()
        mode_id = self._selected_mode_id()
        if collection_id and mode_id:
            self.mode_remove_requested.emit(collection_id, mode_id, False)

    def _emit_mode_set(self) -> None:
        if self._syncing:
            return
        collection_id = self._selected_collection_id()
        mode_id = self._selected_mode_id()
        if collection_id and mode_id:
            self.mode_set_requested.emit(
                self._document["active_artboard_id"],
                collection_id,
                mode_id,
            )
        self._sync_selection(self.tree.currentItem())

    def _emit_update(self) -> None:
        token_id = self._selected_token_id()
        if token_id:
            self.token_update_requested.emit(token_id, self._token_changes())

    def _emit_remove(self) -> None:
        token_id = self._selected_token_id()
        if token_id:
            self.token_remove_requested.emit(token_id, False)

    def _emit_bind(self) -> None:
        object_id = self._selected_object_id()
        token_id = self._selected_token_id()
        if object_id and token_id:
            self.token_binding_requested.emit(
                object_id,
                str(self.binding_path_combo.currentText()),
                token_id,
            )

    def _emit_unbind(self) -> None:
        object_id = self._selected_object_id()
        if object_id:
            self.token_binding_requested.emit(
                object_id,
                str(self.binding_path_combo.currentText()),
                "",
            )


__all__ = [
    "PainterUITokenLibrary",
    "TOKEN_BINDING_PATHS",
    "inspect_ui_token_library",
]

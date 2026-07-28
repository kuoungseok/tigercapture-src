"""Design-token library panel for Painter UI Design documents."""
from __future__ import annotations

import json
from typing import Any, Mapping

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_document import UI_TOKEN_KINDS, normalize_ui_document
from app.painter_ui_themes import UI_THEME_MODES


TOKEN_BINDING_PATHS = (
    "style.fill",
    "style.stroke",
    "style.text_color",
    "style.stroke_width",
    "style.radius",
    "style.shadow",
    "style.font_size",
    "layout.gap",
    "layout.cross_gap",
    "layout.padding.left",
    "layout.padding.top",
    "layout.padding.right",
    "layout.padding.bottom",
    "opacity",
    "content.source",
)


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
    tokens = [
        {
            **token,
            "usage_count": len(bindings[token["id"]]),
            "bindings": bindings[token["id"]],
            "alias_reference_ids": alias_references[token["id"]],
            "unused": not bindings[token["id"]]
            and not alias_references[token["id"]],
        }
        for token in document["tokens"]
    ]
    return {
        "schema": "tigerstudio.painter.ui.token_library.inspect.v1",
        "token_count": len(tokens),
        "used_count": sum(not row["unused"] for row in tokens),
        "unused_count": sum(row["unused"] for row in tokens),
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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = normalize_ui_document(None)
        self._syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

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
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("Value or JSON")
        form.addRow("Default", self.value_edit)
        self.theme_edits: dict[str, QLineEdit] = {}
        for theme in UI_THEME_MODES:
            edit = QLineEdit()
            edit.setPlaceholderText("Inherit default")
            self.theme_edits[theme] = edit
            form.addRow(theme.replace("_", " ").title(), edit)
        self.alias_combo = QComboBox()
        form.addRow("Alias", self.alias_combo)
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
        self._document = normalize_ui_document(value)
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

    def _rebuild(self, preferred_token_id: str = "") -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            preferred = str(preferred_token_id or self._selected_token_id())
            query = self.search_edit.text().strip().casefold()
            kind_filter = str(self.kind_filter.currentData() or "")
            report = inspect_ui_token_library(self._document)
            self.tree.clear()
            selected_item: QTreeWidgetItem | None = None
            for kind, tokens in report["kinds"].items():
                if kind_filter and kind != kind_filter:
                    continue
                visible = [
                    row
                    for row in tokens
                    if not query
                    or query in str(row["name"]).casefold()
                    or query in str(row["description"]).casefold()
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
            self.value_edit,
            self.alias_combo,
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
            if token is None or row["id"] != token["id"]:
                self.alias_combo.addItem(str(row["name"]), str(row["id"]))
        if token is None:
            self.name_edit.clear()
            self.value_edit.clear()
            self.description_edit.clear()
            for edit in self.theme_edits.values():
                edit.clear()
            self.status_label.setText("No tokens")
            return
        self.name_edit.setText(str(token["name"]))
        self.kind_combo.setCurrentText(str(token["kind"]))
        self.value_edit.setText(_format_value(token["value"]))
        for theme, edit in self.theme_edits.items():
            edit.setText(_format_value(token["theme_values"].get(theme)))
            edit.setEnabled(True)
        alias_index = self.alias_combo.findData(str(token["alias_token_id"]))
        self.alias_combo.setCurrentIndex(max(0, alias_index))
        self.description_edit.setText(str(token["description"]))
        report = inspect_ui_token_library(self._document)
        row = next(item for item in report["tokens"] if item["id"] == token["id"])
        self.status_label.setText(
            f"{row['usage_count']} bindings  |  "
            f"{len(row['alias_reference_ids'])} aliases  |  {token['id']}"
        )
        has_object = bool(self._selected_object_id())
        self.bind_button.setEnabled(has_object)
        self.unbind_button.setEnabled(has_object)

    def _emit_add(self) -> None:
        self.token_add_requested.emit(
            {
                "name": "New Token",
                "kind": str(self.kind_combo.currentText() or "color"),
                "value": None,
            }
        )

    def _token_changes(self) -> dict[str, Any]:
        return {
            "name": self.name_edit.text().strip() or "Token",
            "kind": str(self.kind_combo.currentText()),
            "value": _parse_value(self.value_edit.text()),
            "theme_values": {
                theme: _parse_value(edit.text())
                for theme, edit in self.theme_edits.items()
                if edit.text().strip()
            },
            "alias_token_id": str(self.alias_combo.currentData() or ""),
            "description": self.description_edit.text().strip(),
        }

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

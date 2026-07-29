"""Compact Assets panel for Painter UI named styles."""
from __future__ import annotations

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

from app.icons import app_icon
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_styles import (
    UI_NAMED_STYLE_KINDS,
    UI_STYLE_KINDS,
    extract_ui_named_style,
    inspect_ui_style_library,
)


class PainterUIStyleLibrary(QWidget):
    style_add_requested = Signal(object)
    style_update_requested = Signal(str, object)
    style_remove_requested = Signal(str, bool)
    style_apply_requested = Signal(str, str)
    style_unlink_requested = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIStyleLibrary")
        self._document = normalize_ui_document(None)
        self._syncing = False
        self.setStyleSheet(
            """
            QWidget#PainterUIStyleLibrary {
                background: #111720;
                color: #DDE5EF;
            }
            QWidget#PainterUIStyleLibrary QLabel {
                color: #AEB9C8;
                background: transparent;
                border: none;
            }
            QWidget#PainterUIStyleLibrary QLineEdit,
            QWidget#PainterUIStyleLibrary QComboBox,
            QWidget#PainterUIStyleLibrary QTreeWidget {
                background: #0C1118;
                color: #E7EDF5;
                border: 1px solid #2B3543;
                border-radius: 4px;
                selection-background-color: #284B72;
                selection-color: #FFFFFF;
            }
            QWidget#PainterUIStyleLibrary QHeaderView::section {
                background: #161E29;
                color: #97A7BA;
                border: none;
                border-bottom: 1px solid #2B3543;
                padding: 3px 5px;
            }
            QWidget#PainterUIStyleLibrary QPushButton {
                min-height: 24px;
                background: #192230;
                color: #DDE5EF;
                border: 1px solid #303C4C;
                border-radius: 4px;
                padding: 1px 7px;
            }
            QWidget#PainterUIStyleLibrary QPushButton:hover {
                background: #233044;
                border-color: #4A6585;
            }
            QWidget#PainterUIStyleLibrary QPushButton:disabled {
                color: #5F6B79;
                background: #111720;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search styles")
        self.search_edit.textChanged.connect(self._rebuild)
        self.kind_filter = QComboBox()
        self.kind_filter.addItem("All styles", "")
        for kind in UI_STYLE_KINDS:
            self.kind_filter.addItem(kind.replace("_", " ").title(), kind)
        self.kind_filter.currentIndexChanged.connect(self._rebuild)
        filter_row.addWidget(self.search_edit, 1)
        filter_row.addWidget(self.kind_filter)
        layout.addLayout(filter_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Style", "Usage"])
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(14)
        self.tree.currentItemChanged.connect(self._sync_selection)
        layout.addWidget(self.tree, 1)

        self.status_label = QLabel("No styles")
        layout.addWidget(self.status_label)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(3)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Style name")
        form.addRow("Name", self.name_edit)
        self.kind_combo = QComboBox()
        for kind in UI_STYLE_KINDS:
            self.kind_combo.addItem(kind.replace("_", " ").title(), kind)
        form.addRow("Kind", self.kind_combo)
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Optional description")
        form.addRow("Description", self.description_edit)
        layout.addLayout(form)

        capture_row = QHBoxLayout()
        self.new_button = QPushButton("Create from selection")
        self.new_button.setIcon(app_icon("plus", size=11))
        self.new_button.clicked.connect(self._emit_add)
        self.update_button = QPushButton("Update")
        self.update_button.clicked.connect(self._emit_update)
        self.delete_button = QPushButton()
        self.delete_button.setIcon(app_icon("trash", size=11))
        self.delete_button.setToolTip("Delete style")
        self.delete_button.setFixedWidth(28)
        self.delete_button.clicked.connect(self._emit_remove)
        capture_row.addWidget(self.new_button, 1)
        capture_row.addWidget(self.update_button)
        capture_row.addWidget(self.delete_button)
        layout.addLayout(capture_row)

        apply_row = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self._emit_apply)
        self.unlink_button = QPushButton("Detach")
        self.unlink_button.clicked.connect(self._emit_unlink)
        apply_row.addWidget(self.apply_button)
        apply_row.addWidget(self.unlink_button)
        layout.addLayout(apply_row)

    def set_document(self, value: Mapping[str, Any]) -> None:
        selected_style_id = self._selected_style_id()
        self._document = normalize_ui_document(value)
        self._rebuild(selected_style_id)

    def _selected_style_id(self) -> str:
        item = self.tree.currentItem()
        return (
            str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            if item is not None
            else ""
        )

    def _selected_style(self) -> dict[str, Any] | None:
        style_id = self._selected_style_id()
        report = inspect_ui_style_library(self._document)
        return next(
            (row for row in report["styles"] if row["id"] == style_id),
            None,
        )

    def _selected_object(self) -> dict[str, Any] | None:
        object_id = str(self._document["selection"]["object_id"] or "")
        return next(
            (
                row
                for row in self._document["objects"]
                if row["id"] == object_id
            ),
            None,
        )

    def _active_artboard(self) -> dict[str, Any]:
        return next(
            row
            for row in self._document["artboards"]
            if row["id"] == self._document["active_artboard_id"]
        )

    def _rebuild(self, preferred_style_id: str = "") -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            preferred = str(preferred_style_id or self._selected_style_id())
            query = self.search_edit.text().strip().casefold()
            kind_filter = str(self.kind_filter.currentData() or "")
            report = inspect_ui_style_library(self._document)
            self.tree.clear()
            selected_item = None
            for kind in UI_STYLE_KINDS:
                if kind_filter and kind != kind_filter:
                    continue
                rows = [
                    row
                    for row in report["kinds"][kind]
                    if not query
                    or query in row["name"].casefold()
                    or query in row["description"].casefold()
                ]
                if not rows:
                    continue
                root = QTreeWidgetItem(
                    [kind.replace("_", " ").title(), str(len(rows))]
                )
                self.tree.addTopLevelItem(root)
                for row in rows:
                    item = QTreeWidgetItem(
                        [
                            row["name"],
                            str(row["usage_count"])
                            if row["usage_count"]
                            else "Unused",
                        ]
                    )
                    item.setData(0, Qt.ItemDataRole.UserRole, row["id"])
                    root.addChild(item)
                    if row["id"] == preferred:
                        selected_item = item
                root.setExpanded(True)
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
        style = self._selected_style()
        enabled = style is not None
        self.update_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)
        self.unlink_button.setEnabled(enabled)
        if style is None:
            self.name_edit.clear()
            self.description_edit.clear()
            self.kind_combo.setEnabled(True)
            self.status_label.setText("No styles")
            return
        self.name_edit.setText(str(style["name"]))
        index = self.kind_combo.findData(style["kind"])
        self.kind_combo.setCurrentIndex(max(0, index))
        self.kind_combo.setEnabled(False)
        self.description_edit.setText(str(style["description"]))
        self.status_label.setText(
            f"{style['usage_count']} linked  |  {style['id']}"
        )
        can_apply = (
            bool(self._selected_object())
            if style["kind"] in UI_NAMED_STYLE_KINDS
            else bool(self._active_artboard())
        )
        self.apply_button.setEnabled(can_apply)
        self.unlink_button.setEnabled(can_apply)

    def _capture(self, kind: str) -> dict[str, Any] | None:
        if kind == "layout_grid":
            return {
                "kind": kind,
                "properties": {
                    "layout_grids": self._active_artboard()["layout_grids"]
                },
                "token_bindings": {},
            }
        obj = self._selected_object()
        return extract_ui_named_style(obj, kind=kind) if obj is not None else None

    def _emit_add(self) -> None:
        kind = str(self.kind_combo.currentData() or "color")
        captured = self._capture(kind)
        if captured is None:
            return
        self.style_add_requested.emit(
            {
                "name": self.name_edit.text().strip()
                or f"New {kind.replace('_', ' ').title()} Style",
                "kind": kind,
                "properties": captured["properties"],
                "token_bindings": captured["token_bindings"],
                "description": self.description_edit.text().strip(),
            }
        )

    def _emit_update(self) -> None:
        style = self._selected_style()
        if style is None:
            return
        captured = self._capture(style["kind"])
        if captured is None:
            return
        self.style_update_requested.emit(
            style["id"],
            {
                "name": self.name_edit.text().strip() or style["name"],
                "properties": captured["properties"],
                "token_bindings": captured["token_bindings"],
                "description": self.description_edit.text().strip(),
            },
        )

    def _emit_remove(self) -> None:
        style_id = self._selected_style_id()
        if style_id:
            self.style_remove_requested.emit(style_id, False)

    def _emit_apply(self) -> None:
        style = self._selected_style()
        if style is None:
            return
        target_id = (
            self._active_artboard()["id"]
            if style["kind"] == "layout_grid"
            else str((self._selected_object() or {}).get("id") or "")
        )
        if target_id:
            self.style_apply_requested.emit(style["id"], target_id)

    def _emit_unlink(self) -> None:
        style = self._selected_style()
        if style is None:
            return
        target_id = (
            self._active_artboard()["id"]
            if style["kind"] == "layout_grid"
            else str((self._selected_object() or {}).get("id") or "")
        )
        if target_id:
            self.style_unlink_requested.emit(style["kind"], target_id)


__all__ = ["PainterUIStyleLibrary"]

"""Compact Assets panel for versioned local Painter UI libraries."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFileDialog,
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
from app.painter_ui_library_store import (
    compare_ui_library_update,
    default_ui_library_store_root,
    inspect_ui_library_store,
)


class PainterUILibraryPanel(QWidget):
    package_export_requested = Signal(object)
    package_install_requested = Signal(str)
    update_apply_requested = Signal(str)
    update_defer_requested = Signal(str, int)
    rollback_requested = Signal(str)

    def __init__(self, parent=None, *, store_root: str | Path | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUILibraryPanel")
        self._store_root = Path(
            store_root or default_ui_library_store_root()
        ).expanduser().resolve()
        self._document: dict[str, Any] = {}
        self._candidate_path = ""
        self._candidate_report: dict[str, Any] = {}
        self.setStyleSheet(
            """
            QWidget#PainterUILibraryPanel { background: #111720; color: #DDE5EF; }
            QWidget#PainterUILibraryPanel QLabel {
                color: #AEB9C8; background: transparent; border: none;
            }
            QWidget#PainterUILibraryPanel QLineEdit,
            QWidget#PainterUILibraryPanel QTreeWidget {
                background: #0C1118; color: #E7EDF5;
                border: 1px solid #2B3543; border-radius: 4px;
                selection-background-color: #284B72;
            }
            QWidget#PainterUILibraryPanel QHeaderView::section {
                background: #161E29; color: #97A7BA; border: none;
                border-bottom: 1px solid #2B3543; padding: 3px 5px;
            }
            QWidget#PainterUILibraryPanel QPushButton {
                min-height: 24px; background: #192230; color: #DDE5EF;
                border: 1px solid #303C4C; border-radius: 4px;
                padding: 1px 7px;
            }
            QWidget#PainterUILibraryPanel QPushButton:hover {
                background: #233044; border-color: #4A6585;
            }
            QWidget#PainterUILibraryPanel QPushButton:disabled {
                color: #5F6B79; background: #111720;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search libraries")
        self.search_edit.textChanged.connect(self.refresh_store)
        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(app_icon("refresh", size=11))
        self.refresh_button.setToolTip("Refresh local libraries")
        self.refresh_button.setFixedWidth(28)
        self.refresh_button.clicked.connect(self.refresh_store)
        toolbar.addWidget(self.search_edit, 1)
        toolbar.addWidget(self.refresh_button)
        layout.addLayout(toolbar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Library", "Version", "State"])
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(14)
        self.tree.currentItemChanged.connect(self._sync_selection)
        layout.addWidget(self.tree, 1)

        self.summary_label = QLabel("No local libraries installed")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        package_row = QHBoxLayout()
        self.export_button = QPushButton("Export")
        self.export_button.setIcon(app_icon("export", size=11))
        self.export_button.clicked.connect(self._choose_export)
        self.install_button = QPushButton("Install")
        self.install_button.setIcon(app_icon("plus", size=11))
        self.install_button.clicked.connect(self._choose_install)
        self.review_button = QPushButton("Review update")
        self.review_button.clicked.connect(self._choose_review)
        package_row.addWidget(self.export_button)
        package_row.addWidget(self.install_button)
        package_row.addWidget(self.review_button)
        layout.addLayout(package_row)

        update_row = QHBoxLayout()
        self.accept_button = QPushButton("Accept")
        self.accept_button.clicked.connect(self._emit_accept)
        self.defer_button = QPushButton("Defer")
        self.defer_button.clicked.connect(self._emit_defer)
        self.rollback_button = QPushButton("Rollback")
        self.rollback_button.clicked.connect(self._emit_rollback)
        update_row.addWidget(self.accept_button)
        update_row.addWidget(self.defer_button)
        update_row.addWidget(self.rollback_button)
        layout.addLayout(update_row)
        self.refresh_store()

    def set_document(self, document: dict[str, Any]) -> None:
        self._document = dict(document or {})
        self.export_button.setEnabled(bool(self._document))

    def set_store_root(self, value: str | Path) -> None:
        self._store_root = Path(value).expanduser().resolve()
        self.refresh_store()

    def refresh_store(self, *_args) -> None:
        selected = self._selected_library_id()
        report = inspect_ui_library_store(store_root=self._store_root)
        query = self.search_edit.text().strip().casefold()
        self.tree.clear()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in report["packages"]:
            if query and query not in str(row["name"]).casefold():
                continue
            grouped.setdefault(str(row["id"]), []).append(row)
        selected_item = None
        for library_id, rows in sorted(grouped.items()):
            rows.sort(key=lambda row: int(row["version"]), reverse=True)
            root = QTreeWidgetItem([rows[0]["name"], "", ""])
            root.setData(0, Qt.ItemDataRole.UserRole, library_id)
            self.tree.addTopLevelItem(root)
            for row in rows:
                state = (
                    "Active"
                    if row["active"]
                    else "Deferred"
                    if row["deferred"]
                    else "Installed"
                )
                item = QTreeWidgetItem(
                    [row["name"], f"v{row['version']}", state]
                )
                item.setData(0, Qt.ItemDataRole.UserRole, library_id)
                item.setData(1, Qt.ItemDataRole.UserRole, int(row["version"]))
                item.setData(2, Qt.ItemDataRole.UserRole, dict(row))
                root.addChild(item)
                if library_id == selected and row["active"]:
                    selected_item = item
            root.setExpanded(True)
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)
        self.summary_label.setText(
            f"{report['library_count']} libraries  |  "
            f"{len(report['packages'])} installed versions"
            if report["packages"]
            else "No local libraries installed"
        )
        self._sync_selection(self.tree.currentItem())

    def _selected_library_id(self) -> str:
        item = self.tree.currentItem()
        return (
            str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            if item is not None
            else ""
        )

    def _sync_selection(self, current, _previous=None) -> None:
        library_id = self._selected_library_id()
        report = (
            current.data(2, Qt.ItemDataRole.UserRole)
            if current is not None
            else None
        )
        report = report if isinstance(report, dict) else {}
        self.rollback_button.setEnabled(bool(library_id))
        if report:
            counts = report.get("counts") or {}
            self.summary_label.setText(
                f"{report['name']} v{report['version']}  |  "
                f"{counts.get('components', 0)} components, "
                f"{counts.get('styles', 0)} styles, "
                f"{counts.get('tokens', 0)} tokens"
            )
        has_candidate = bool(self._candidate_report)
        self.accept_button.setEnabled(has_candidate)
        self.defer_button.setEnabled(has_candidate)

    def _choose_export(self) -> None:
        name = str(self._document.get("name") or "Painter UI Library")
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export UI Library",
            f"{name}.tsuilib",
            "Tiger Studio UI Library (*.tsuilib)",
        )
        if not path:
            return
        library_id = Path(path).stem
        self.package_export_requested.emit(
            {
                "path": path,
                "library_id": library_id,
                "name": name,
                "version": 1,
            }
        )

    def _choose_install(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Install UI Library",
            "",
            "Tiger Studio UI Library (*.tsuilib)",
        )
        if path:
            self.package_install_requested.emit(path)

    def _choose_review(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Review UI Library Update",
            "",
            "Tiger Studio UI Library (*.tsuilib)",
        )
        if not path:
            return
        self.set_update_candidate(path)

    def set_update_candidate(self, path: str) -> dict[str, Any]:
        report = compare_ui_library_update(path, store_root=self._store_root)
        self._candidate_path = str(path)
        self._candidate_report = report
        self.summary_label.setText(
            f"{report['library_id']}  v{report['current_version']} -> "
            f"v{report['candidate_version']}  |  "
            f"{'Update available' if report['update_available'] else 'Review'}"
        )
        self.accept_button.setEnabled(True)
        self.defer_button.setEnabled(True)
        return report

    def _emit_accept(self) -> None:
        if self._candidate_path:
            self.update_apply_requested.emit(self._candidate_path)

    def _emit_defer(self) -> None:
        if self._candidate_report:
            self.update_defer_requested.emit(
                str(self._candidate_report["library_id"]),
                int(self._candidate_report["candidate_version"]),
            )

    def _emit_rollback(self) -> None:
        library_id = self._selected_library_id()
        if library_id:
            self.rollback_requested.emit(library_id)


__all__ = ["PainterUILibraryPanel"]

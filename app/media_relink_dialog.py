"""Missing-media relink browser dialog."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.media_relink import (
    build_media_health_report,
    build_relink_plan,
    missing_relinkable_paths,
)


class MissingMediaRelinkDialog(QDialog):
    """Browse missing media and choose replacement candidates per file."""

    def __init__(
        self,
        *,
        project_path: Path,
        project_doc: dict[str, Any],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Relink Missing Media")
        self.setMinimumSize(860, 560)
        self._project_path = Path(project_path)
        self._project_doc = project_doc
        self._roots: list[Path] = []
        self._plan: dict[str, Any] = {}
        self._health: dict[str, Any] = {}
        self._combo_by_old_path: dict[str, QComboBox] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        root_row = QHBoxLayout()
        self._root_list = QListWidget()
        self._root_list.setMaximumHeight(82)
        root_row.addWidget(self._root_list, 1)

        root_buttons = QVBoxLayout()
        self._add_root_btn = QPushButton("Add Folder")
        self._remove_root_btn = QPushButton("Remove")
        self._scan_btn = QPushButton("Scan")
        self._add_root_btn.clicked.connect(self._add_root)
        self._remove_root_btn.clicked.connect(self._remove_selected_root)
        self._scan_btn.clicked.connect(self._scan)
        root_buttons.addWidget(self._add_root_btn)
        root_buttons.addWidget(self._remove_root_btn)
        root_buttons.addWidget(self._scan_btn)
        root_buttons.addStretch(1)
        root_row.addLayout(root_buttons)
        root.addLayout(root_row)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels([
            "Missing file",
            "Replacement candidate",
            "Status",
            "Original path",
        ])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self._table, 1)

        self._warning = QLabel("")
        self._warning.setWordWrap(True)
        self._warning.setStyleSheet("color:#d8a030;")
        root.addWidget(self._warning)

        buttons = QDialogButtonBox()
        self._apply_btn = QPushButton("Write Relinked Copy")
        self._apply_btn.clicked.connect(self._accept_if_ready)
        buttons.addButton(self._apply_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        close_btn = QPushButton("Cancel")
        close_btn.clicked.connect(self.reject)
        buttons.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)
        root.addWidget(buttons)

        self.add_search_root(self._project_path.parent)
        self._scan()

    def add_search_root(self, root: Path | str) -> None:
        path = Path(root)
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if any(existing == resolved for existing in self._roots):
            return
        self._roots.append(resolved)
        self._root_list.addItem(str(resolved))

    def search_roots(self) -> list[Path]:
        return list(self._roots)

    def selected_choices(self) -> dict[str, str]:
        choices: dict[str, str] = {}
        for old_path, combo in self._combo_by_old_path.items():
            value = str(combo.currentData() or "")
            if value:
                choices[old_path] = value
        return choices

    def plan(self) -> dict[str, Any]:
        return dict(self._plan)

    def _add_root(self) -> None:
        start = str(self._roots[-1] if self._roots else self._project_path.parent)
        folder = QFileDialog.getExistingDirectory(
            self,
            "Add media search folder",
            start,
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return
        self.add_search_root(folder)
        self._scan()

    def _remove_selected_root(self) -> None:
        row = self._root_list.currentRow()
        if row < 0:
            return
        self._root_list.takeItem(row)
        if 0 <= row < len(self._roots):
            self._roots.pop(row)
        self._scan()

    def _scan(self) -> None:
        missing = missing_relinkable_paths(self._project_doc)
        if not self._roots:
            self._plan = {
                "missing_count": len(missing),
                "resolved_count": 0,
                "conflict_count": 0,
                "unresolved_count": len(missing),
                "search_roots": [],
                "rows": [
                    {
                        "old_path": path,
                        "filename": Path(path).name,
                        "candidates": [],
                        "selected": "",
                        "status": "missing",
                        "conflict": False,
                    }
                    for path in missing
                ],
            }
        else:
            self._plan = build_relink_plan(self._project_doc, self._roots)
        self._health = build_media_health_report(self._project_doc, self._roots)
        self._populate_table()

    def _populate_table(self) -> None:
        self._combo_by_old_path.clear()
        rows = list(self._plan.get("rows", []) or [])
        self._table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            old_path = str(row.get("old_path", ""))
            filename = str(row.get("filename") or Path(old_path).name)
            candidates = list(row.get("candidates", []) or [])
            status = str(row.get("status") or "missing")

            self._table.setItem(row_idx, 0, QTableWidgetItem(filename))
            self._table.setItem(row_idx, 3, QTableWidgetItem(old_path))

            combo = QComboBox()
            if candidates:
                for candidate in candidates:
                    combo.addItem(str(candidate), str(candidate))
                selected = str(row.get("selected") or candidates[0])
                idx = combo.findData(selected)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            else:
                combo.addItem("No candidate found", "")
                combo.setEnabled(False)
            combo.currentIndexChanged.connect(self._refresh_warnings)
            self._combo_by_old_path[old_path] = combo
            self._table.setCellWidget(row_idx, 1, combo)

            label = {
                "resolved": "Ready",
                "conflict": "Choose candidate",
                "missing": "Missing",
            }.get(status, status)
            item = QTableWidgetItem(label)
            if status == "conflict":
                item.setForeground(QColor("#d8a030"))
            elif status == "missing":
                item.setForeground(QColor("#d35f5f"))
            self._table.setItem(row_idx, 2, item)

        self._table.resizeRowsToContents()
        self._refresh_warnings()

    def _refresh_warnings(self) -> None:
        missing_count = int(self._plan.get("missing_count", 0) or 0)
        resolved = int(self._plan.get("resolved_count", 0) or 0)
        conflicts = int(self._plan.get("conflict_count", 0) or 0)
        unresolved = int(self._plan.get("unresolved_count", 0) or 0)
        choices = self.selected_choices()
        proxy_counts = self._health.get("proxy_counts", {}) or {}
        stale_proxy = int(proxy_counts.get("stale", 0) or 0)
        missing_proxy = int(proxy_counts.get("missing", 0) or 0)

        selected_to_old: dict[str, list[str]] = {}
        for old_path, new_path in choices.items():
            selected_to_old.setdefault(new_path, []).append(old_path)
        duplicate_replacements = {
            new_path: old_paths
            for new_path, old_paths in selected_to_old.items()
            if len(old_paths) > 1
        }

        self._summary.setText(
            f"{self._project_path.name} | missing {missing_count} | "
            f"ready {resolved} | conflicts {conflicts} | unresolved {unresolved} | "
            f"stale proxy {stale_proxy} | roots {len(self._roots)}"
        )

        warnings: list[str] = []
        if conflicts:
            warnings.append(
                f"{conflicts} file(s) have multiple candidates. Review the replacement column."
            )
        if unresolved:
            warnings.append(f"{unresolved} file(s) still have no candidate.")
        if duplicate_replacements:
            warnings.append(
                f"{len(duplicate_replacements)} replacement path(s) are selected by multiple missing entries."
            )
        if stale_proxy:
            warnings.append(
                f"{stale_proxy} video proxy file(s) are stale and should be regenerated."
            )
        if missing_proxy:
            warnings.append(
                f"{missing_proxy} video source(s) have no proxy yet; long projects may preview slower."
            )
        self._warning.setText("\n".join(warnings))

        self._apply_btn.setEnabled(bool(choices))

    def _accept_if_ready(self) -> None:
        if not self.selected_choices():
            QMessageBox.information(
                self,
                "Relink Missing Media",
                "No replacement candidates are selected.",
            )
            return
        self.accept()

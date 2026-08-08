"""On-demand searchable shortcut map for Painter UI Design."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from app.painter_i18n import painter_text
from app.painter_ui_shortcut_map import inspect_painter_shortcuts


_SHORTCUT_QSS = """
QDialog#painterUiShortcutMapDialog {
    background: #15161B;
    color: #E9ECF4;
}
QDialog#painterUiShortcutMapDialog QLabel,
QDialog#painterUiShortcutMapDialog QCheckBox {
    color: #D8DCE7;
}
QDialog#painterUiShortcutMapDialog QLabel#painterUiDialogTitle {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 600;
}
QDialog#painterUiShortcutMapDialog QLabel#painterUiShortcutStatus {
    color: #9299A8;
}
QDialog#painterUiShortcutMapDialog QLineEdit {
    min-height: 28px;
    padding: 0 8px;
    color: #F4F6FA;
    background: #0F1116;
    border: 1px solid #343946;
    border-radius: 4px;
}
QDialog#painterUiShortcutMapDialog QTreeWidget {
    color: #DDE1EA;
    background: #101217;
    alternate-background-color: #14171D;
    border: 1px solid #303542;
    border-radius: 4px;
    outline: none;
}
QDialog#painterUiShortcutMapDialog QHeaderView::section {
    min-height: 25px;
    padding: 0 6px;
    color: #9FA6B5;
    background: #1D2027;
    border: 0;
    border-right: 1px solid #303542;
}
QDialog#painterUiShortcutMapDialog QPushButton {
    min-height: 28px;
    padding: 0 10px;
    color: #DDE1EA;
    background: #242832;
    border: 1px solid #383E4C;
    border-radius: 4px;
}
"""


class PainterUIShortcutMapDialog(QDialog):
    """Display active and mode-specific shortcuts without editing the document."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterUiShortcutMapDialog")
        self.setWindowTitle(painter_text("Keyboard shortcuts"))
        self.setModal(False)
        self.resize(620, 560)
        self.setStyleSheet(_SHORTCUT_QSS)
        self._report: dict[str, Any] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        title = QLabel(painter_text("Keyboard shortcuts"))
        title.setObjectName("painterUiDialogTitle")
        root.addWidget(title)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            painter_text("Search commands or keys")
        )
        self.search_edit.setClearButtonEnabled(True)
        search_row.addWidget(self.search_edit, 1)
        self.conflicts_check = QCheckBox(painter_text("Conflicts only"))
        search_row.addWidget(self.conflicts_check)
        root.addLayout(search_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("painterUiShortcutStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setHeaderLabels(
            [
                painter_text("Command"),
                painter_text("Shortcut"),
                painter_text("Mode"),
            ]
        )
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tree.header().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        root.addWidget(self.tree, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton(painter_text("Close"))
        close_button.clicked.connect(self.close)
        footer.addWidget(close_button)
        root.addLayout(footer)

        self.search_edit.textChanged.connect(self.refresh)
        self.conflicts_check.toggled.connect(self.refresh)
        self.refresh()

    def report(self) -> dict[str, Any]:
        return dict(self._report)

    def refresh(self, *_args) -> dict[str, Any]:
        self._report = inspect_painter_shortcuts(
            query=self.search_edit.text(),
            conflicts_only=self.conflicts_check.isChecked(),
        )
        self.tree.clear()
        for row in self._report["rows"]:
            mode = {
                "ui_design": painter_text("UI Design"),
                "paint": painter_text("Paint"),
                "3d_place": painter_text("3D Place"),
                "global": painter_text("Global"),
            }.get(row["scope"], row["scope"])
            label = painter_text(row["label"])
            if row["conflict"]:
                label = f"! {label}"
            item = QTreeWidgetItem([label, row["shortcut"], mode])
            item.setData(0, Qt.ItemDataRole.UserRole, row["id"])
            if not row["active"]:
                muted = QColor("#747B89")
                for column in range(3):
                    item.setForeground(column, muted)
            if row["conflict"]:
                warning = QColor("#E7A06A")
                for column in range(3):
                    item.setForeground(column, warning)
                item.setToolTip(
                    0,
                    painter_text("Conflicts with: {items}").format(
                        items=", ".join(row["conflicts_with"])
                    ),
                )
            self.tree.addTopLevelItem(item)
        if self._report["visible_count"]:
            self.status_label.setText(
                painter_text(
                    "{visible} commands · {active} active · {conflicts} conflicts"
                ).format(
                    visible=self._report["visible_count"],
                    active=self._report["active_count"],
                    conflicts=self._report["conflict_count"],
                )
            )
        else:
            self.status_label.setText(
                painter_text("No shortcuts match this search.")
            )
        return self.report()


__all__ = ["PainterUIShortcutMapDialog"]

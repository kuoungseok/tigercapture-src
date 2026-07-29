"""On-demand Find/Replace dialog for Painter UI Design documents."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app.painter_i18n import painter_text
from app.painter_ui_find_replace import (
    FIND_REPLACE_CATEGORIES,
    inspect_ui_find_replace,
)


_CATEGORY_LABELS = {
    "text": "Text",
    "component": "Component",
    "style": "Style",
    "variable": "Variable",
    "font": "Font",
    "asset": "Asset",
}

_FIND_REPLACE_QSS = """
QDialog#painterUiFindReplaceDialog {
    background: #15161B;
    color: #E9ECF4;
}
QDialog#painterUiFindReplaceDialog QLabel,
QDialog#painterUiFindReplaceDialog QCheckBox {
    color: #D8DCE7;
}
QDialog#painterUiFindReplaceDialog QLabel#painterUiDialogTitle {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 600;
}
QDialog#painterUiFindReplaceDialog QLabel#painterUiDialogSubtitle,
QDialog#painterUiFindReplaceDialog QLabel#painterUiFindReplaceStatus {
    color: #9299A8;
}
QDialog#painterUiFindReplaceDialog QLineEdit {
    min-height: 28px;
    padding: 0 8px;
    color: #F4F6FA;
    background: #0F1116;
    border: 1px solid #343946;
    border-radius: 4px;
}
QDialog#painterUiFindReplaceDialog QLineEdit:focus {
    border-color: #6C91BC;
}
QDialog#painterUiFindReplaceDialog QListWidget {
    color: #DDE1EA;
    background: #101217;
    alternate-background-color: #14171D;
    border: 1px solid #303542;
    border-radius: 4px;
    outline: none;
}
QDialog#painterUiFindReplaceDialog QListWidget::item {
    padding: 6px 5px;
    border-bottom: 1px solid #232731;
}
QDialog#painterUiFindReplaceDialog QPushButton {
    min-height: 28px;
    padding: 0 10px;
    color: #DDE1EA;
    background: #242832;
    border: 1px solid #383E4C;
    border-radius: 4px;
}
QDialog#painterUiFindReplaceDialog QPushButton:hover {
    background: #303643;
}
QDialog#painterUiFindReplaceDialog QPushButton:disabled {
    color: #626978;
    background: #1B1E25;
}
QDialog#painterUiFindReplaceDialog QPushButton#painterUiPrimaryButton {
    color: #FFFFFF;
    background: #3E6388;
    border-color: #527BA2;
}
"""


class PainterUIFindReplaceDialog(QDialog):
    """Preview changes and request one selective document mutation."""

    apply_requested = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterUiFindReplaceDialog")
        self.setWindowTitle(painter_text("Find / Replace"))
        self.setModal(False)
        self.resize(540, 520)
        self.setStyleSheet(_FIND_REPLACE_QSS)
        self._document: dict[str, Any] = {}
        self._report: dict[str, Any] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel(painter_text("Find / Replace"))
        title.setObjectName("painterUiDialogTitle")
        root.addWidget(title)
        subtitle = QLabel(
            painter_text(
                "Preview text and linked references before changing the document."
            )
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("painterUiDialogSubtitle")
        root.addWidget(subtitle)

        fields = QFrame()
        fields_layout = QVBoxLayout(fields)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(6)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText(painter_text("Find"))
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText(painter_text("Replace with"))
        fields_layout.addWidget(self.find_edit)
        fields_layout.addWidget(self.replace_edit)
        root.addWidget(fields)

        category_row = QGridLayout()
        category_row.setHorizontalSpacing(8)
        category_row.setVerticalSpacing(3)
        self.category_checks: dict[str, QCheckBox] = {}
        for index, category in enumerate(FIND_REPLACE_CATEGORIES):
            check = QCheckBox(painter_text(_CATEGORY_LABELS[category]))
            check.setChecked(True)
            self.category_checks[category] = check
            category_row.addWidget(check, index // 3, index % 3)
        category_row.setColumnStretch(3, 1)
        root.addLayout(category_row)

        option_row = QHBoxLayout()
        self.case_check = QCheckBox(painter_text("Case sensitive"))
        self.whole_check = QCheckBox(painter_text("Whole value"))
        option_row.addWidget(self.case_check)
        option_row.addWidget(self.whole_check)
        option_row.addStretch(1)
        self.preview_button = QPushButton(painter_text("Preview"))
        self.preview_button.clicked.connect(self.preview)
        option_row.addWidget(self.preview_button)
        root.addLayout(option_row)

        self.status_label = QLabel(
            painter_text("Enter a value, then preview matching UI properties.")
        )
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("painterUiFindReplaceStatus")
        root.addWidget(self.status_label)

        self.results = QListWidget()
        self.results.setObjectName("painterUiFindReplaceResults")
        self.results.setAlternatingRowColors(True)
        self.results.itemChanged.connect(self._refresh_apply_state)
        root.addWidget(self.results, 1)

        footer = QHBoxLayout()
        self.select_all_button = QPushButton(painter_text("Select valid"))
        self.select_all_button.clicked.connect(self._select_valid)
        footer.addWidget(self.select_all_button)
        footer.addStretch(1)
        close_button = QPushButton(painter_text("Close"))
        close_button.clicked.connect(self.close)
        footer.addWidget(close_button)
        self.apply_button = QPushButton(painter_text("Apply selected"))
        self.apply_button.setObjectName("painterUiPrimaryButton")
        self.apply_button.clicked.connect(self._request_apply)
        footer.addWidget(self.apply_button)
        root.addLayout(footer)

        self.find_edit.returnPressed.connect(self.preview)
        self.replace_edit.returnPressed.connect(self.preview)
        self._refresh_apply_state()

    def set_document(self, document: Mapping[str, Any] | None) -> None:
        self._document = copy.deepcopy(dict(document or {}))
        self._report = None
        self.results.clear()
        self.status_label.setText(
            painter_text("Enter a value, then preview matching UI properties.")
        )
        self._refresh_apply_state()

    def parameters(self) -> dict[str, Any]:
        return {
            "find": self.find_edit.text(),
            "replacement": self.replace_edit.text(),
            "categories": [
                category
                for category, check in self.category_checks.items()
                if check.isChecked()
            ],
            "case_sensitive": self.case_check.isChecked(),
            "whole_value": self.whole_check.isChecked(),
        }

    def preview(self) -> dict[str, Any] | None:
        self.results.clear()
        self._report = None
        if not self._document:
            self.status_label.setText(
                painter_text("No UI document is available.")
            )
            self._refresh_apply_state()
            return None
        parameters = self.parameters()
        if not str(parameters["find"]).strip():
            self.status_label.setText(
                painter_text("Enter a value to find.")
            )
            self._refresh_apply_state()
            return None
        if not parameters["categories"]:
            self.status_label.setText(
                painter_text("Select at least one category.")
            )
            self._refresh_apply_state()
            return None
        try:
            report = inspect_ui_find_replace(self._document, **parameters)
        except (TypeError, ValueError) as exc:
            self.status_label.setText(str(exc))
            self._refresh_apply_state()
            return None
        self._report = report
        self.results.blockSignals(True)
        for match in report["matches"]:
            item = QListWidgetItem(
                f"{match['target_name']}  /  {match['path']}\n"
                f"{match['current']}  ->  {match['proposed']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, match["match_id"])
            flags = item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            if match["valid"]:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                flags &= ~Qt.ItemFlag.ItemIsEnabled
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setToolTip(match["reason"])
                item.setText(
                    item.text() + f"\n{painter_text('Blocked')}: {match['reason']}"
                )
            item.setFlags(flags)
            self.results.addItem(item)
        self.results.blockSignals(False)
        if report["match_count"]:
            self.status_label.setText(
                painter_text("{count} matches · {valid} can be applied").format(
                    count=report["match_count"],
                    valid=report["valid_match_count"],
                )
            )
        else:
            self.status_label.setText(painter_text("No matches found."))
        self._refresh_apply_state()
        return copy.deepcopy(report)

    def selected_match_ids(self) -> list[str]:
        return [
            str(item.data(Qt.ItemDataRole.UserRole) or "")
            for index in range(self.results.count())
            if (item := self.results.item(index)).checkState()
            == Qt.CheckState.Checked
        ]

    def _select_valid(self) -> None:
        self.results.blockSignals(True)
        for index in range(self.results.count()):
            item = self.results.item(index)
            if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                item.setCheckState(Qt.CheckState.Checked)
        self.results.blockSignals(False)
        self._refresh_apply_state()

    def _refresh_apply_state(self, *_args) -> None:
        self.apply_button.setEnabled(bool(self.selected_match_ids()))
        self.select_all_button.setEnabled(self.results.count() > 0)

    def _request_apply(self) -> None:
        match_ids = self.selected_match_ids()
        if not match_ids:
            return
        self.apply_requested.emit(
            {
                **self.parameters(),
                "selected_match_ids": match_ids,
            }
        )

    def show_applied(self, document: Mapping[str, Any], count: int) -> None:
        self.set_document(document)
        self.status_label.setText(
            painter_text("{count} matches applied.").format(count=int(count))
        )


__all__ = ["PainterUIFindReplaceDialog"]

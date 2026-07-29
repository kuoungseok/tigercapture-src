"""On-demand Batch Rename dialog for selected Painter UI objects."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.painter_i18n import painter_text
from app.painter_ui_batch_rename import inspect_ui_batch_rename


_BATCH_RENAME_QSS = """
QDialog#painterUiBatchRenameDialog {
    background: #15161B;
    color: #E9ECF4;
}
QDialog#painterUiBatchRenameDialog QLabel,
QDialog#painterUiBatchRenameDialog QCheckBox {
    color: #D8DCE7;
}
QDialog#painterUiBatchRenameDialog QLabel#painterUiDialogTitle {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 600;
}
QDialog#painterUiBatchRenameDialog QLabel#painterUiDialogSubtitle,
QDialog#painterUiBatchRenameDialog QLabel#painterUiBatchRenameStatus {
    color: #9299A8;
}
QDialog#painterUiBatchRenameDialog QLineEdit,
QDialog#painterUiBatchRenameDialog QSpinBox {
    min-height: 27px;
    padding: 0 7px;
    color: #F4F6FA;
    background: #0F1116;
    border: 1px solid #343946;
    border-radius: 4px;
}
QDialog#painterUiBatchRenameDialog QListWidget {
    color: #DDE1EA;
    background: #101217;
    alternate-background-color: #14171D;
    border: 1px solid #303542;
    border-radius: 4px;
    outline: none;
}
QDialog#painterUiBatchRenameDialog QListWidget::item {
    padding: 6px 5px;
    border-bottom: 1px solid #232731;
}
QDialog#painterUiBatchRenameDialog QPushButton {
    min-height: 28px;
    padding: 0 10px;
    color: #DDE1EA;
    background: #242832;
    border: 1px solid #383E4C;
    border-radius: 4px;
}
QDialog#painterUiBatchRenameDialog QPushButton:disabled {
    color: #626978;
    background: #1B1E25;
}
QDialog#painterUiBatchRenameDialog QPushButton#painterUiPrimaryButton {
    color: #FFFFFF;
    background: #3E6388;
    border-color: #527BA2;
}
"""


class PainterUIBatchRenameDialog(QDialog):
    """Preview and request one selective batch-name mutation."""

    apply_requested = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterUiBatchRenameDialog")
        self.setWindowTitle(painter_text("Batch Rename"))
        self.setModal(False)
        self.resize(500, 560)
        self.setStyleSheet(_BATCH_RENAME_QSS)
        self._document: dict[str, Any] = {}
        self._object_ids: list[str] = []
        self._report: dict[str, Any] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        title = QLabel(painter_text("Batch Rename"))
        title.setObjectName("painterUiDialogTitle")
        root.addWidget(title)
        subtitle = QLabel(
            painter_text(
                "Preview names for the selected UI objects before applying."
            )
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("painterUiDialogSubtitle")
        root.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        self.find_edit = QLineEdit()
        self.replace_edit = QLineEdit()
        self.prefix_edit = QLineEdit()
        self.suffix_edit = QLineEdit()
        form.addRow(painter_text("Find"), self.find_edit)
        form.addRow(painter_text("Replace with"), self.replace_edit)
        form.addRow(painter_text("Prefix"), self.prefix_edit)
        form.addRow(painter_text("Suffix"), self.suffix_edit)
        root.addLayout(form)

        number_row = QHBoxLayout()
        self.numbering_check = QCheckBox(painter_text("Add numbering"))
        self.number_start = QSpinBox()
        self.number_start.setRange(-999999, 999999)
        self.number_start.setValue(1)
        self.number_padding = QSpinBox()
        self.number_padding.setRange(0, 8)
        self.number_padding.setValue(2)
        number_row.addWidget(self.numbering_check)
        number_row.addWidget(QLabel(painter_text("Start")))
        number_row.addWidget(self.number_start)
        number_row.addWidget(QLabel(painter_text("Digits")))
        number_row.addWidget(self.number_padding)
        number_row.addStretch(1)
        root.addLayout(number_row)
        self.case_check = QCheckBox(painter_text("Case sensitive"))
        root.addWidget(self.case_check)

        preview_row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setObjectName("painterUiBatchRenameStatus")
        self.status_label.setWordWrap(True)
        preview_row.addWidget(self.status_label, 1)
        self.preview_button = QPushButton(painter_text("Preview"))
        self.preview_button.clicked.connect(self.preview)
        preview_row.addWidget(self.preview_button)
        root.addLayout(preview_row)

        self.results = QListWidget()
        self.results.setAlternatingRowColors(True)
        self.results.itemChanged.connect(self._refresh_apply_state)
        root.addWidget(self.results, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton(painter_text("Close"))
        close_button.clicked.connect(self.close)
        footer.addWidget(close_button)
        self.apply_button = QPushButton(painter_text("Apply selected"))
        self.apply_button.setObjectName("painterUiPrimaryButton")
        self.apply_button.clicked.connect(self._request_apply)
        footer.addWidget(self.apply_button)
        root.addLayout(footer)

        for editor in (
            self.find_edit,
            self.replace_edit,
            self.prefix_edit,
            self.suffix_edit,
        ):
            editor.returnPressed.connect(self.preview)
        self._refresh_apply_state()

    def set_document(
        self,
        document: Mapping[str, Any] | None,
        object_ids: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self._document = copy.deepcopy(dict(document or {}))
        self._object_ids = [str(value) for value in (object_ids or [])]
        self._report = None
        self.results.clear()
        if self._object_ids:
            self.status_label.setText(
                painter_text("{count} selected objects").format(
                    count=len(self._object_ids)
                )
            )
        else:
            self.status_label.setText(
                painter_text("Select UI objects to rename.")
            )
        self._refresh_apply_state()

    def parameters(self) -> dict[str, Any]:
        return {
            "object_ids": list(self._object_ids),
            "find": self.find_edit.text(),
            "replacement": self.replace_edit.text(),
            "prefix": self.prefix_edit.text(),
            "suffix": self.suffix_edit.text(),
            "numbering": self.numbering_check.isChecked(),
            "number_start": self.number_start.value(),
            "number_padding": self.number_padding.value(),
            "number_separator": " ",
            "case_sensitive": self.case_check.isChecked(),
        }

    def preview(self) -> dict[str, Any] | None:
        self.results.clear()
        self._report = None
        if not self._document or not self._object_ids:
            self.status_label.setText(
                painter_text("Select UI objects to rename.")
            )
            self._refresh_apply_state()
            return None
        try:
            report = inspect_ui_batch_rename(
                self._document, **self.parameters()
            )
        except (TypeError, ValueError) as exc:
            self.status_label.setText(str(exc))
            self._refresh_apply_state()
            return None
        self._report = report
        self.results.blockSignals(True)
        for match in report["matches"]:
            item = QListWidgetItem(
                f"{match['current']}  ->  {match['proposed']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, match["match_id"])
            item.setFlags(
                item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(Qt.CheckState.Checked)
            self.results.addItem(item)
        self.results.blockSignals(False)
        self.status_label.setText(
            painter_text("{count} names can be changed").format(
                count=report["valid_match_count"]
            )
            if report["match_count"]
            else painter_text("No name changes to apply.")
        )
        self._refresh_apply_state()
        return copy.deepcopy(report)

    def selected_match_ids(self) -> list[str]:
        return [
            str(item.data(Qt.ItemDataRole.UserRole) or "")
            for index in range(self.results.count())
            if (item := self.results.item(index)).checkState()
            == Qt.CheckState.Checked
        ]

    def _refresh_apply_state(self, *_args) -> None:
        self.apply_button.setEnabled(bool(self.selected_match_ids()))
        self.preview_button.setEnabled(bool(self._object_ids))

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
        object_ids = list(self._object_ids)
        self.set_document(document, object_ids)
        self.status_label.setText(
            painter_text("{count} names changed.").format(count=int(count))
        )


__all__ = ["PainterUIBatchRenameDialog"]

"""Data editor dialogs for PPT table and chart elements."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.pptgen.formula import evaluate_numeric_formula, format_formula_value
from app.pptgen.schema import SlideElement
from app.pptgen.ui.style import PPT_DIALOG_QSS


def _table_cells(element: SlideElement) -> tuple[int, int, list[list[str]]]:
    rows = max(1, int(element.metadata.get("rows", 3) or 3))
    cols = max(1, int(element.metadata.get("cols", 3) or 3))
    raw_cells = element.metadata.get("cells")
    cells: list[list[str]] = []
    if isinstance(raw_cells, list):
        for row in raw_cells[:rows]:
            cells.append([str(cell) for cell in row[:cols]] if isinstance(row, list) else [])
    while len(cells) < rows:
        cells.append([])
    for row_index, row in enumerate(cells):
        while len(row) < cols:
            row.append(f"Cell {row_index + 1}-{len(row) + 1}")
    return rows, cols, cells


def _chart_rows(element: SlideElement) -> list[tuple[str, str]]:
    raw_labels = element.metadata.get("labels") or ["A", "B", "C", "D"]
    raw_values = element.metadata.get("values") or [32, 58, 44, 72]
    labels = [str(label) for label in raw_labels] if isinstance(raw_labels, list) else ["A", "B", "C", "D"]
    values = [str(value) for value in raw_values] if isinstance(raw_values, list) else ["32", "58", "44", "72"]
    count = max(1, min(max(len(labels), len(values)), 12))
    rows: list[tuple[str, str]] = []
    for index in range(count):
        rows.append((labels[index] if index < len(labels) else f"Item {index + 1}", values[index] if index < len(values) else "0"))
    return rows


def _column_name(index: int) -> str:
    value = int(index) + 1
    chars: list[str] = []
    while value:
        value, rem = divmod(value - 1, 26)
        chars.append(chr(ord("A") + rem))
    return "".join(reversed(chars)) or "A"


class TableDataDialog(QDialog):
    def __init__(self, element: SlideElement, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.element = element
        self.setWindowTitle("Edit Table Data")
        self.resize(620, 460)
        self.setStyleSheet(PPT_DIALOG_QSS)
        rows, cols, cells = _table_cells(element)
        layout = QVBoxLayout(self)
        hint = QLabel("Cells can contain text, numbers, or formulas such as =A2+B2, =SUM(1,2,3), =AVG(A2,B2).", self)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        controls = QHBoxLayout()
        self.rows_spin = QSpinBox(self)
        self.rows_spin.setRange(1, 12)
        self.rows_spin.setValue(rows)
        self.cols_spin = QSpinBox(self)
        self.cols_spin.setRange(1, 8)
        self.cols_spin.setValue(cols)
        form = QFormLayout()
        form.addRow("Rows", self.rows_spin)
        form.addRow("Columns", self.cols_spin)
        controls.addLayout(form)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.table = QTableWidget(rows, cols, self)
        self.table.setAlternatingRowColors(True)
        self._refresh_headers()
        self._set_cells(cells)
        layout.addWidget(self.table, 1)

        self.rows_spin.valueChanged.connect(self._resize_table)
        self.cols_spin.valueChanged.connect(self._resize_table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_cells(self, cells: list[list[str]]) -> None:
        self._refresh_headers()
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                text = cells[row][col] if row < len(cells) and col < len(cells[row]) else ""
                self.table.setItem(row, col, QTableWidgetItem(text))

    def _refresh_headers(self) -> None:
        self.table.setHorizontalHeaderLabels([_column_name(col) for col in range(self.table.columnCount())])
        self.table.setVerticalHeaderLabels([str(row + 1) for row in range(self.table.rowCount())])

    def _snapshot(self) -> list[list[str]]:
        cells: list[list[str]] = []
        for row in range(self.table.rowCount()):
            values: list[str] = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append(item.text() if item else "")
            cells.append(values)
        return cells

    def _resize_table(self) -> None:
        cells = self._snapshot()
        self.table.setRowCount(int(self.rows_spin.value()))
        self.table.setColumnCount(int(self.cols_spin.value()))
        self._set_cells(cells)

    def apply_to_element(self) -> None:
        cells = self._snapshot()
        self.element.metadata["rows"] = len(cells)
        self.element.metadata["cols"] = len(cells[0]) if cells else 1
        self.element.metadata["cells"] = cells


class ChartDataDialog(QDialog):
    def __init__(self, element: SlideElement, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.element = element
        self.setWindowTitle("Edit Chart Data")
        self.resize(560, 420)
        self.setStyleSheet(PPT_DIALOG_QSS)
        rows = _chart_rows(element)
        layout = QVBoxLayout(self)
        hint = QLabel("The value column accepts numbers or formulas such as =SUM(12,8), =AVG(20,40), or =A1+B1.", self)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top = QHBoxLayout()
        self.count_spin = QSpinBox(self)
        self.count_spin.setRange(1, 12)
        self.count_spin.setValue(len(rows))
        top.addWidget(QLabel("Items", self))
        top.addWidget(self.count_spin)
        top.addStretch(1)
        layout.addLayout(top)

        self.table = QTableWidget(len(rows), 3, self)
        self.table.setHorizontalHeaderLabels(["Label", "Value / Formula", "Preview"])
        self._set_rows(rows)
        self.table.itemChanged.connect(self._refresh_preview)
        layout.addWidget(self.table, 1)

        self.count_spin.valueChanged.connect(self._resize_table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_preview()

    def _set_rows(self, rows: list[tuple[str, str]]) -> None:
        blocked = self.table.blockSignals(True)
        try:
            for row in range(self.table.rowCount()):
                label, value = rows[row] if row < len(rows) else (f"Item {row + 1}", "0")
                self.table.setItem(row, 0, QTableWidgetItem(label))
                self.table.setItem(row, 1, QTableWidgetItem(value))
                preview = QTableWidgetItem("")
                preview.setFlags(preview.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 2, preview)
        finally:
            self.table.blockSignals(blocked)

    def _snapshot(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for row in range(self.table.rowCount()):
            label_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            rows.append((label_item.text() if label_item else "", value_item.text() if value_item else "0"))
        return rows

    def _resize_table(self) -> None:
        rows = self._snapshot()
        self.table.setRowCount(int(self.count_spin.value()))
        self._set_rows(rows)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        rows = self._snapshot()
        cells = [[label, value] for label, value in rows]
        for row, (_label, value) in enumerate(rows):
            preview = self.table.item(row, 2)
            if preview is None:
                preview = QTableWidgetItem("")
                preview.setFlags(preview.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 2, preview)
            try:
                number = evaluate_numeric_formula(value, cells=cells)
                preview.setText(str(int(number)) if abs(number - round(number)) < 1e-7 else f"{number:.2f}")
            except Exception:
                preview.setText(format_formula_value(value, cells=cells))

    def apply_to_element(self) -> None:
        rows = self._snapshot()
        self.element.metadata["labels"] = [label or f"Item {index + 1}" for index, (label, _value) in enumerate(rows)]
        self.element.metadata["values"] = [value or "0" for _label, value in rows]


def edit_table_data(parent: QWidget, element: SlideElement) -> bool:
    dialog = TableDataDialog(element, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    dialog.apply_to_element()
    return True


def edit_chart_data(parent: QWidget, element: SlideElement) -> bool:
    dialog = ChartDataDialog(element, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    dialog.apply_to_element()
    return True


__all__ = ["ChartDataDialog", "TableDataDialog", "edit_chart_data", "edit_table_data"]

"""Transient report for measured Painter UI runtime performance."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from app.painter_i18n import painter_text


_QSS = """
QDialog#painterUiRuntimePerformanceDialog {
    background: #15161B; color: #E9ECF4;
}
QDialog#painterUiRuntimePerformanceDialog QLabel { color: #D8DCE7; }
QDialog#painterUiRuntimePerformanceDialog QLabel#title {
    color: #FFFFFF; font-size: 15px; font-weight: 600;
}
QDialog#painterUiRuntimePerformanceDialog QLabel#status { color: #9299A8; }
QDialog#painterUiRuntimePerformanceDialog QTreeWidget {
    color: #DDE1EA; background: #101217;
    alternate-background-color: #14171D;
    border: 1px solid #303542; border-radius: 4px; outline: none;
}
QDialog#painterUiRuntimePerformanceDialog QHeaderView::section {
    min-height: 25px; padding: 0 6px; color: #9FA6B5;
    background: #1D2027; border: 0; border-right: 1px solid #303542;
}
QDialog#painterUiRuntimePerformanceDialog QPushButton {
    min-height: 28px; padding: 0 10px; color: #DDE1EA;
    background: #242832; border: 1px solid #383E4C; border-radius: 4px;
}
QDialog#painterUiRuntimePerformanceDialog QPushButton#primary {
    color: #FFFFFF; background: #315F8D; border-color: #5383B0;
}
QDialog#painterUiRuntimePerformanceDialog QPushButton:focus {
    border: 2px solid #8FC7FF;
}
"""


class PainterUIRuntimePerformanceDialog(QDialog):
    run_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterUiRuntimePerformanceDialog")
        self.setWindowTitle(painter_text("Runtime performance"))
        self.setModal(False)
        self.resize(650, 480)
        self.setStyleSheet(_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        title = QLabel(painter_text("Runtime performance"))
        title.setObjectName("title")
        root.addWidget(title)
        self.status_label = QLabel(
            painter_text("Run the local runtime benchmark.")
        )
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels(
            [
                painter_text("Path"),
                painter_text("Median"),
                painter_text("Warning"),
                painter_text("Block"),
                painter_text("Status"),
            ]
        )
        root.addWidget(self.tree, 1)
        self.scope_label = QLabel(
            painter_text(
                "Results describe this machine only and are not a universal performance claim."
            )
        )
        self.scope_label.setObjectName("status")
        self.scope_label.setWordWrap(True)
        root.addWidget(self.scope_label)
        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton(painter_text("Close"))
        close.clicked.connect(self.close)
        footer.addWidget(close)
        self.run_button = QPushButton(painter_text("Run benchmark"))
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(self.run_requested)
        footer.addWidget(self.run_button)
        root.addLayout(footer)
        self._apply_density()

    def set_running(self) -> None:
        self.run_button.setEnabled(False)
        self.status_label.setText(
            painter_text("Running local benchmark...")
        )

    def set_report(self, report: Mapping[str, Any] | None) -> None:
        payload = dict(report or {})
        self.tree.clear()
        self.run_button.setEnabled(True)
        if not payload:
            self.status_label.setText(
                painter_text("Run the local runtime benchmark.")
            )
            return
        for row in payload.get("cases", []):
            status = str(row.get("status") or "")
            item = QTreeWidgetItem(
                [
                    painter_text(str(row.get("label") or "")),
                    f"{float(row.get('median_ms') or 0):.1f} ms",
                    f"{float(row.get('warning_ms') or 0):.0f} ms",
                    f"{float(row.get('block_ms') or 0):.0f} ms",
                    painter_text(
                        "Within budget"
                        if status == "covered"
                        else status.title()
                    ),
                ]
            )
            color = (
                QColor("#76C39B")
                if status == "covered"
                else QColor("#E2B969")
                if status == "warning"
                else QColor("#E77C72")
            )
            item.setForeground(4, color)
            item.setToolTip(
                0,
                ", ".join(
                    f"{float(sample):.1f} ms"
                    for sample in row.get("samples_ms", [])
                ),
            )
            self.tree.addTopLevelItem(item)
        self.status_label.setText(
            painter_text(
                "{objects} objects · {covered}/{total} paths covered · "
                "{warning} warning · {blocked} blocked"
            ).format(
                objects=int(payload.get("object_count") or 0),
                covered=int(payload.get("covered_count") or 0),
                total=int(payload.get("case_count") or 0),
                warning=int(payload.get("warning_count") or 0),
                blocked=int(payload.get("blocked_count") or 0),
            )
        )
        self._apply_density()

    def _apply_density(self) -> None:
        compact = self.width() < 520
        self.tree.setColumnHidden(2, compact)
        self.tree.setColumnHidden(3, compact)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_density()


__all__ = ["PainterUIRuntimePerformanceDialog"]

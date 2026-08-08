"""On-demand Painter UI document performance budget report."""
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
QDialog#painterUiPerformanceBudgetDialog {
    background: #15161B; color: #E9ECF4;
}
QDialog#painterUiPerformanceBudgetDialog QLabel { color: #D8DCE7; }
QDialog#painterUiPerformanceBudgetDialog QLabel#title {
    color: #FFFFFF; font-size: 15px; font-weight: 600;
}
QDialog#painterUiPerformanceBudgetDialog QLabel#status { color: #9299A8; }
QDialog#painterUiPerformanceBudgetDialog QTreeWidget {
    color: #DDE1EA; background: #101217;
    alternate-background-color: #14171D;
    border: 1px solid #303542; border-radius: 4px; outline: none;
}
QDialog#painterUiPerformanceBudgetDialog QHeaderView::section {
    min-height: 25px; padding: 0 6px; color: #9FA6B5;
    background: #1D2027; border: 0; border-right: 1px solid #303542;
}
QDialog#painterUiPerformanceBudgetDialog QPushButton {
    min-height: 28px; padding: 0 10px; color: #DDE1EA;
    background: #242832; border: 1px solid #383E4C; border-radius: 4px;
}
QDialog#painterUiPerformanceBudgetDialog QPushButton:focus {
    border: 2px solid #8FC7FF;
}
"""


class PainterUIPerformanceBudgetDialog(QDialog):
    refresh_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterUiPerformanceBudgetDialog")
        self.setWindowTitle(painter_text("Performance budget"))
        self.setModal(False)
        self.resize(620, 470)
        self.setStyleSheet(_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        title = QLabel(painter_text("Performance budget"))
        title.setObjectName("title")
        root.addWidget(title)
        self.status_label = QLabel(
            painter_text("No performance budget report available.")
        )
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels(
            [
                painter_text("Metric"),
                painter_text("Current"),
                painter_text("Warning"),
                painter_text("Block"),
                painter_text("Status"),
            ]
        )
        root.addWidget(self.tree, 1)
        self.policy_label = QLabel("")
        self.policy_label.setObjectName("status")
        self.policy_label.setWordWrap(True)
        root.addWidget(self.policy_label)
        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton(painter_text("Close"))
        close.clicked.connect(self.close)
        footer.addWidget(close)
        refresh = QPushButton(painter_text("Refresh"))
        refresh.clicked.connect(self.refresh_requested)
        footer.addWidget(refresh)
        root.addLayout(footer)
        self._apply_density()

    def set_report(self, report: Mapping[str, Any] | None) -> None:
        payload = dict(report or {})
        self.tree.clear()
        if not payload:
            self.status_label.setText(
                painter_text("No performance budget report available.")
            )
            self.policy_label.clear()
            return
        for row in payload.get("budgets", []):
            status = str(row.get("status") or "")
            item = QTreeWidgetItem(
                [
                    painter_text(str(row.get("label") or "")),
                    str(int(row.get("value") or 0)),
                    str(int(row.get("warning_limit") or 0)),
                    str(int(row.get("block_limit") or 0)),
                    painter_text(
                        "Within budget"
                        if status == "covered"
                        else status.title()
                    ),
                ]
            )
            if status == "warning":
                color = QColor("#E2B969")
            elif status == "blocked":
                color = QColor("#E77C72")
            else:
                color = QColor("#76C39B")
            item.setForeground(4, color)
            item.setToolTip(
                0,
                painter_text(str(row.get("reason") or status)),
            )
            self.tree.addTopLevelItem(item)
        self.status_label.setText(
            painter_text(
                "{covered}/{total} budgets covered · {warning} warning · "
                "{blocked} blocked"
            ).format(
                covered=int(payload.get("covered_count") or 0),
                total=int(payload.get("budget_count") or 0),
                warning=int(payload.get("warning_count") or 0),
                blocked=int(payload.get("blocked_count") or 0),
            )
        )
        self.policy_label.setText(
            painter_text(
                "This report checks document scale. Wall-clock rendering "
                "performance is measured by separate runtime QA."
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


__all__ = ["PainterUIPerformanceBudgetDialog"]

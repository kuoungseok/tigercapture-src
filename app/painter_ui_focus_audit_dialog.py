"""On-demand keyboard focus audit for Painter UI Design."""
from __future__ import annotations

from typing import Any, Mapping

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
QDialog#painterUiFocusAuditDialog { background: #15161B; color: #E9ECF4; }
QDialog#painterUiFocusAuditDialog QLabel { color: #D8DCE7; }
QDialog#painterUiFocusAuditDialog QLabel#title {
    color: #FFFFFF; font-size: 15px; font-weight: 600;
}
QDialog#painterUiFocusAuditDialog QLabel#status { color: #9299A8; }
QDialog#painterUiFocusAuditDialog QTreeWidget {
    color: #DDE1EA; background: #101217;
    alternate-background-color: #14171D;
    border: 1px solid #303542; border-radius: 4px; outline: none;
}
QDialog#painterUiFocusAuditDialog QHeaderView::section {
    min-height: 25px; padding: 0 6px; color: #9FA6B5;
    background: #1D2027; border: 0; border-right: 1px solid #303542;
}
QDialog#painterUiFocusAuditDialog QPushButton {
    min-height: 28px; padding: 0 10px; color: #DDE1EA;
    background: #242832; border: 1px solid #383E4C; border-radius: 4px;
}
QDialog#painterUiFocusAuditDialog QPushButton:focus {
    border: 2px solid #8FC7FF;
}
"""


class PainterUIFocusAuditDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterUiFocusAuditDialog")
        self.setWindowTitle(painter_text("Keyboard focus audit"))
        self.setModal(False)
        self.resize(620, 480)
        self.setStyleSheet(_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        title = QLabel(painter_text("Keyboard focus audit"))
        title.setObjectName("title")
        root.addWidget(title)
        self.status_label = QLabel(
            painter_text("No keyboard focus report available.")
        )
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels(
            [
                painter_text("Control"),
                painter_text("Type"),
                painter_text("Tab"),
                painter_text("Focus ring"),
                painter_text("Status"),
            ]
        )
        root.addWidget(self.tree, 1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_button = QPushButton(painter_text("Close"))
        self.close_button.clicked.connect(self.close)
        footer.addWidget(self.close_button)
        root.addLayout(footer)
        self._apply_density()

    def set_report(self, report: Mapping[str, Any] | None) -> None:
        payload = dict(report or {})
        self.tree.clear()
        if not payload:
            self.status_label.setText(
                painter_text("No keyboard focus report available.")
            )
            return
        rows = list(payload.get("issues") or payload.get("controls") or [])
        for row in rows:
            status = str(row.get("status") or "")
            item = QTreeWidgetItem(
                [
                    str(row.get("label") or row.get("id") or ""),
                    str(row.get("kind") or ""),
                    painter_text("Yes" if row.get("tab_focus") else "No"),
                    painter_text("Yes" if row.get("focus_ring") else "No"),
                    painter_text(
                        "Covered" if status == "covered" else "Blocked"
                    ),
                ]
            )
            item.setToolTip(
                0,
                ", ".join(str(value) for value in row.get("issue_codes") or [])
                or str(row.get("id") or ""),
            )
            if status != "covered":
                for column in range(5):
                    item.setForeground(column, QColor("#E7A06A"))
            self.tree.addTopLevelItem(item)
        self.status_label.setText(
            painter_text(
                "{controls} controls · {tab} keyboard · "
                "{rings} focus rings · {issues} issues"
            ).format(
                controls=int(payload.get("control_count") or 0),
                tab=int(payload.get("tab_focus_count") or 0),
                rings=int(payload.get("focus_ring_count") or 0),
                issues=int(payload.get("issue_count") or 0),
            )
        )
        self._apply_density()

    def _apply_density(self) -> None:
        compact = self.width() < 520
        self.tree.setColumnHidden(1, compact)
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


__all__ = ["PainterUIFocusAuditDialog"]

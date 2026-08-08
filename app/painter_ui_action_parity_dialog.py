"""On-demand Painter UI/Action parity report."""
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
QDialog#painterUiActionParityDialog { background: #15161B; color: #E9ECF4; }
QDialog#painterUiActionParityDialog QLabel { color: #D8DCE7; }
QDialog#painterUiActionParityDialog QLabel#title {
    color: #FFFFFF; font-size: 15px; font-weight: 600;
}
QDialog#painterUiActionParityDialog QLabel#status { color: #9299A8; }
QDialog#painterUiActionParityDialog QTreeWidget {
    color: #DDE1EA; background: #101217;
    alternate-background-color: #14171D;
    border: 1px solid #303542; border-radius: 4px; outline: none;
}
QDialog#painterUiActionParityDialog QHeaderView::section {
    min-height: 25px; padding: 0 6px; color: #9FA6B5;
    background: #1D2027; border: 0; border-right: 1px solid #303542;
}
QDialog#painterUiActionParityDialog QPushButton {
    min-height: 28px; padding: 0 10px; color: #DDE1EA;
    background: #242832; border: 1px solid #383E4C; border-radius: 4px;
}
"""


class PainterUIActionParityDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterUiActionParityDialog")
        self.setWindowTitle(painter_text("UI / Action parity"))
        self.setModal(False)
        self.resize(660, 560)
        self.setStyleSheet(_QSS)
        self._report: dict[str, Any] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        title = QLabel(painter_text("UI / Action parity"))
        title.setObjectName("title")
        root.addWidget(title)
        self.status_label = QLabel(painter_text("No parity report available."))
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels(
            [
                painter_text("Feature"),
                painter_text("UI surface"),
                painter_text("Actions"),
                painter_text("Status"),
            ]
        )
        self.tree.header().setStretchLastSection(False)
        root.addWidget(self.tree, 1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton(painter_text("Close"))
        close.clicked.connect(self.close)
        footer.addWidget(close)
        root.addLayout(footer)
        self._apply_density()

    def set_report(self, report: Mapping[str, Any] | None) -> None:
        self._report = dict(report or {})
        self.tree.clear()
        if not self._report:
            self.status_label.setText(
                painter_text("No parity report available.")
            )
            return
        for row in self._report.get("families", []):
            status = str(row.get("status") or "")
            item = QTreeWidgetItem(
                [
                    painter_text(str(row.get("label") or "")),
                    painter_text(str(row.get("surface") or "")),
                    str(int(row.get("action_count") or 0)),
                    painter_text(
                        "Covered" if status == "covered" else "Missing"
                    ),
                ]
            )
            item.setToolTip(0, painter_text(str(row.get("surface") or "")))
            if status != "covered":
                for column in range(4):
                    item.setForeground(column, QColor("#E7A06A"))
                item.setToolTip(
                    0,
                    "\n".join(row.get("missing_action_ids") or []),
                )
            self.tree.addTopLevelItem(item)
        self.status_label.setText(
            painter_text(
                "{actions} Actions · {covered}/{families} surfaces covered · "
                "{orphans} orphan candidates"
            ).format(
                actions=int(self._report.get("action_count") or 0),
                covered=int(
                    self._report.get("covered_family_count") or 0
                ),
                families=int(self._report.get("family_count") or 0),
                orphans=len(
                    self._report.get("orphan_candidate_ids") or []
                ),
            )
        )
        self._apply_density()

    def _apply_density(self) -> None:
        compact = self.width() < 560
        self.tree.setColumnHidden(1, compact)
        header = self.tree.header()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch
            if compact
            else QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_density()


__all__ = ["PainterUIActionParityDialog"]

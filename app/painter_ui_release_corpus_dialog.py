"""On-demand Painter UI release round-trip corpus report."""
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
QDialog#painterUiReleaseCorpusDialog { background: #15161B; color: #E9ECF4; }
QDialog#painterUiReleaseCorpusDialog QLabel { color: #D8DCE7; }
QDialog#painterUiReleaseCorpusDialog QLabel#title {
    color: #FFFFFF; font-size: 15px; font-weight: 600;
}
QDialog#painterUiReleaseCorpusDialog QLabel#status { color: #9299A8; }
QDialog#painterUiReleaseCorpusDialog QTreeWidget {
    color: #DDE1EA; background: #101217;
    alternate-background-color: #14171D;
    border: 1px solid #303542; border-radius: 4px; outline: none;
}
QDialog#painterUiReleaseCorpusDialog QHeaderView::section {
    min-height: 25px; padding: 0 6px; color: #9FA6B5;
    background: #1D2027; border: 0; border-right: 1px solid #303542;
}
QDialog#painterUiReleaseCorpusDialog QPushButton {
    min-height: 28px; padding: 0 10px; color: #DDE1EA;
    background: #242832; border: 1px solid #383E4C; border-radius: 4px;
}
QDialog#painterUiReleaseCorpusDialog QPushButton#primary {
    color: #FFFFFF; background: #315F8D; border-color: #5383B0;
}
QDialog#painterUiReleaseCorpusDialog QPushButton:focus {
    border: 2px solid #8FC7FF;
}
"""


class PainterUIReleaseCorpusDialog(QDialog):
    run_requested = Signal()
    open_output_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterUiReleaseCorpusDialog")
        self.setWindowTitle(painter_text("UI release corpus"))
        self.setModal(False)
        self.resize(650, 500)
        self.setStyleSheet(_QSS)
        self._output_dir = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        title = QLabel(painter_text("UI release corpus"))
        title.setObjectName("title")
        root.addWidget(title)
        self.status_label = QLabel(
            painter_text("Run the release corpus to verify exchange packages.")
        )
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels(
            [
                painter_text("Package"),
                painter_text("Status"),
                painter_text("Time"),
                painter_text("Scope"),
            ]
        )
        root.addWidget(self.tree, 1)
        self.honesty_label = QLabel("")
        self.honesty_label.setObjectName("status")
        self.honesty_label.setWordWrap(True)
        root.addWidget(self.honesty_label)
        footer = QHBoxLayout()
        self.open_button = QPushButton(painter_text("Open output folder"))
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(
            lambda: self.open_output_requested.emit(self._output_dir)
        )
        footer.addWidget(self.open_button)
        footer.addStretch(1)
        close = QPushButton(painter_text("Close"))
        close.clicked.connect(self.close)
        footer.addWidget(close)
        self.run_button = QPushButton(painter_text("Run corpus"))
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(self.run_requested)
        footer.addWidget(self.run_button)
        root.addLayout(footer)
        self._apply_density()

    def set_running(self) -> None:
        self.run_button.setEnabled(False)
        self.status_label.setText(painter_text("Running release corpus..."))

    def set_report(self, report: Mapping[str, Any] | None) -> None:
        payload = dict(report or {})
        self.tree.clear()
        self.run_button.setEnabled(True)
        self._output_dir = str(payload.get("output_dir") or "")
        self.open_button.setEnabled(bool(self._output_dir))
        if not payload:
            self.status_label.setText(
                painter_text("Run the release corpus to verify exchange packages.")
            )
            self.honesty_label.clear()
            return
        for row in payload.get("cases", []):
            status = str(row.get("status") or "")
            detail = dict(row.get("detail") or {})
            item = QTreeWidgetItem(
                [
                    painter_text(
                        str(row.get("label") or row.get("id") or "")
                    ),
                    painter_text(
                        "Passed" if status == "passed" else "Blocked"
                    ),
                    f"{float(row.get('duration_ms') or 0):.1f} ms",
                    painter_text(
                        str(detail.get("scope") or "semantic round trip")
                    ),
                ]
            )
            item.setToolTip(
                0,
                str(row.get("reason") or detail.get("artifact") or ""),
            )
            if status != "passed":
                for column in range(4):
                    item.setForeground(column, QColor("#E7A06A"))
            self.tree.addTopLevelItem(item)
        self.status_label.setText(
            painter_text(
                "{passed}/{total} release packages passed · {blocked} blocked"
            ).format(
                passed=int(payload.get("passed_count") or 0),
                total=int(payload.get("case_count") or 0),
                blocked=int(payload.get("blocked_count") or 0),
            )
        )
        claims = dict(payload.get("runtime_claims") or {})
        self.honesty_label.setText(
            painter_text(
                "Figma native file is not claimed. Unreal compile and real "
                "capture remain separate release gates."
            )
            if claims
            else ""
        )
        self._apply_density()

    def _apply_density(self) -> None:
        compact = self.width() < 520
        self.tree.setColumnHidden(2, compact)
        self.tree.setColumnHidden(3, compact)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_density()


__all__ = ["PainterUIReleaseCorpusDialog"]

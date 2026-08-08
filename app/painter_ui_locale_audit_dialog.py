"""On-demand locale overflow and font-fallback audit dialog."""
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
QDialog#painterUiLocaleAuditDialog { background: #15161B; color: #E9ECF4; }
QDialog#painterUiLocaleAuditDialog QLabel { color: #D8DCE7; }
QDialog#painterUiLocaleAuditDialog QLabel#title {
    color: #FFFFFF; font-size: 15px; font-weight: 600;
}
QDialog#painterUiLocaleAuditDialog QLabel#status { color: #9299A8; }
QDialog#painterUiLocaleAuditDialog QTreeWidget {
    color: #DDE1EA; background: #101217;
    alternate-background-color: #14171D;
    border: 1px solid #303542; border-radius: 4px; outline: none;
}
QDialog#painterUiLocaleAuditDialog QHeaderView::section {
    min-height: 25px; padding: 0 6px; color: #9FA6B5;
    background: #1D2027; border: 0; border-right: 1px solid #303542;
}
QDialog#painterUiLocaleAuditDialog QPushButton {
    min-height: 28px; padding: 0 10px; color: #DDE1EA;
    background: #242832; border: 1px solid #383E4C; border-radius: 4px;
}
"""


class PainterUILocaleAuditDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterUiLocaleAuditDialog")
        self.setWindowTitle(painter_text("Locale and font audit"))
        self.setModal(False)
        self.resize(580, 470)
        self.setStyleSheet(_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        title = QLabel(painter_text("Locale and font audit"))
        title.setObjectName("title")
        root.addWidget(title)
        self.status_label = QLabel(painter_text("No locale report available."))
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels(
            [
                painter_text("Language"),
                painter_text("Overflow"),
                painter_text("Elided"),
                painter_text("Glyphs"),
                painter_text("Status"),
            ]
        )
        root.addWidget(self.tree, 1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton(painter_text("Close"))
        close.clicked.connect(self.close)
        footer.addWidget(close)
        root.addLayout(footer)
        self._apply_density()

    def set_report(self, report: Mapping[str, Any] | None) -> None:
        payload = dict(report or {})
        self.tree.clear()
        if not payload:
            self.status_label.setText(
                painter_text("No locale report available.")
            )
            return
        for row in payload.get("locales", []):
            status = str(row.get("status") or "")
            item = QTreeWidgetItem(
                [
                    str(row.get("label") or row.get("language") or ""),
                    str(int(row.get("overflow_count") or 0)),
                    str(int(row.get("elided_count") or 0)),
                    str(int(row.get("missing_glyph_count") or 0)),
                    painter_text(
                        "Covered" if status == "covered" else "Blocked"
                    ),
                ]
            )
            if status != "covered":
                for column in range(5):
                    item.setForeground(column, QColor("#E7A06A"))
            self.tree.addTopLevelItem(item)
        self.status_label.setText(
            painter_text(
                "{languages} languages · {entries} critical strings · "
                "{issues} issues · {font}"
            ).format(
                languages=int(payload.get("language_count") or 0),
                entries=int(payload.get("entry_count") or 0),
                issues=int(payload.get("issue_count") or 0),
                font=str(payload.get("font_family") or ""),
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


__all__ = ["PainterUILocaleAuditDialog"]

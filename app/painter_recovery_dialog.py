"""On-demand Painter recovery snapshot chooser."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app.painter_i18n import painter_text


_QSS = """
QDialog#painterRecoveryDialog { background: #15161B; color: #E9ECF4; }
QDialog#painterRecoveryDialog QLabel { color: #D8DCE7; }
QDialog#painterRecoveryDialog QLabel#title {
    color: #FFFFFF; font-size: 15px; font-weight: 600;
}
QDialog#painterRecoveryDialog QLabel#status { color: #9299A8; }
QDialog#painterRecoveryDialog QListWidget {
    color: #DDE1EA; background: #101217;
    alternate-background-color: #14171D;
    border: 1px solid #303542; border-radius: 4px; outline: none;
}
QDialog#painterRecoveryDialog QListWidget::item {
    min-height: 42px; padding: 5px 7px; border-bottom: 1px solid #232731;
}
QDialog#painterRecoveryDialog QPushButton {
    min-height: 28px; padding: 0 10px; color: #DDE1EA;
    background: #242832; border: 1px solid #383E4C; border-radius: 4px;
}
QDialog#painterRecoveryDialog QPushButton#primary {
    color: #FFFFFF; background: #3E6388; border-color: #527BA2;
}
QDialog#painterRecoveryDialog QPushButton#danger {
    color: #F0B7AE; background: #38201F; border-color: #6D3733;
}
"""


class PainterRecoveryDialog(QDialog):
    restore_requested = Signal(dict)
    discard_requested = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterRecoveryDialog")
        self.setWindowTitle(painter_text("Recover autosave"))
        self.setModal(False)
        self.resize(560, 460)
        self.setStyleSheet(_QSS)
        self._rows: list[dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        title = QLabel(painter_text("Recover autosave"))
        title.setObjectName("title")
        root.addWidget(title)
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.currentRowChanged.connect(self._sync_buttons)
        self.list_widget.itemDoubleClicked.connect(
            lambda _item: self._restore()
        )
        root.addWidget(self.list_widget, 1)
        footer = QHBoxLayout()
        self.discard_button = QPushButton(painter_text("Discard snapshot"))
        self.discard_button.setObjectName("danger")
        self.discard_button.clicked.connect(self._discard)
        footer.addWidget(self.discard_button)
        footer.addStretch(1)
        close = QPushButton(painter_text("Close"))
        close.clicked.connect(self.close)
        footer.addWidget(close)
        self.restore_button = QPushButton(painter_text("Restore"))
        self.restore_button.setObjectName("primary")
        self.restore_button.clicked.connect(self._restore)
        footer.addWidget(self.restore_button)
        root.addLayout(footer)
        self.set_snapshots([])

    def set_snapshots(self, rows: list[Mapping[str, Any]]) -> None:
        self._rows = [dict(row) for row in rows]
        self.list_widget.clear()
        for row in self._rows:
            source = str(row.get("source_path") or "").strip()
            name = source.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            if not name:
                name = painter_text("Untitled Painter document")
            saved = datetime.fromtimestamp(
                float(row.get("saved_at") or 0)
            ).strftime("%Y-%m-%d  %H:%M:%S")
            size_kb = int(row.get("bytes") or 0) / 1024.0
            item = QListWidgetItem(
                f"{name}\n{saved}  ·  {size_kb:.1f} KB"
            )
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.list_widget.addItem(item)
        if self._rows:
            self.list_widget.setCurrentRow(0)
            self.status_label.setText(
                painter_text("{count} recovery snapshots").format(
                    count=len(self._rows)
                )
            )
        else:
            self.status_label.setText(
                painter_text("No recovery snapshots are available.")
            )
        self._sync_buttons()

    def selected_snapshot(self) -> dict[str, Any] | None:
        item = self.list_widget.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return dict(value) if isinstance(value, dict) else None

    def _sync_buttons(self, *_args) -> None:
        enabled = self.selected_snapshot() is not None
        self.restore_button.setEnabled(enabled)
        self.discard_button.setEnabled(enabled)

    def _restore(self) -> None:
        row = self.selected_snapshot()
        if row:
            self.restore_requested.emit(row)

    def _discard(self) -> None:
        row = self.selected_snapshot()
        if row:
            self.discard_requested.emit(row)

    def show_error(self, message: str) -> None:
        self.status_label.setText(str(message))
        self.status_label.setStyleSheet("color: #E7A06A;")


__all__ = ["PainterRecoveryDialog"]

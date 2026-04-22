from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.donation_config import DonationOption, enabled_donations
from app.i18n import tr


class DonationDialog(QDialog):
    """Small modal listing ways to support the project."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("donation.title"))
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        header = QLabel(tr("donation.header"))
        header.setStyleSheet("font-size: 15px; font-weight: 700; color: #1a1a1a;")
        header.setWordWrap(True)
        root.addWidget(header)

        body = QLabel(tr("donation.body"))
        body.setStyleSheet("color: #5a5a5a; font-size: 12px;")
        body.setWordWrap(True)
        root.addWidget(body)

        items = enabled_donations()
        if not items:
            empty = QLabel(tr("donation.none"))
            empty.setStyleSheet("color: #9a9a9a; font-size: 12px; padding: 10px 0;")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(empty)
        else:
            for opt in items:
                root.addWidget(self._build_row(opt))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            tr("donation.close")
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addSpacing(4)
        root.addWidget(buttons)

    def _build_row(self, opt: DonationOption) -> QWidget:
        container = QWidget()
        container.setObjectName("DonationRow")
        container.setStyleSheet(
            "QWidget#DonationRow { background: #f6f6f6; "
            "border: 1px solid #e1e1e1; border-radius: 6px; }"
        )
        row = QHBoxLayout(container)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(10)

        name = QLabel(f"{opt.icon}  {tr('donation.' + opt.key)}")
        name.setStyleSheet("font-size: 13px; color: #1a1a1a; border: none;")

        if opt.copy_text and not opt.url:
            text_label = QLabel(opt.copy_text)
            text_label.setStyleSheet(
                "color: #3a3a3a; font-family: Consolas; font-size: 12px; border: none;"
            )
            copy_btn = QPushButton(tr("donation.copy"))
            copy_btn.setObjectName("ToolButton")
            copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            copy_btn.clicked.connect(lambda _=False, t=opt.copy_text: self._copy(t))
            row.addWidget(name)
            row.addStretch(1)
            row.addWidget(text_label)
            row.addWidget(copy_btn)
        else:
            open_btn = QPushButton(tr("donation.open"))
            open_btn.setObjectName("PrimaryToolButton")
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(lambda _=False, u=opt.url: self._open(u))
            row.addWidget(name)
            row.addStretch(1)
            row.addWidget(open_btn)

        return container

    @staticmethod
    def _open(url: str) -> None:
        if url:
            webbrowser.open(url)

    def _copy(self, text: str) -> None:
        if text:
            QGuiApplication.clipboard().setText(text)
            self.setWindowTitle(tr("donation.copied"))

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from app.i18n import (
    SUPPORTED_LANGUAGES,
    current_language,
    save_language,
    set_language,
    tr,
)
from app.shortcuts import DEFAULT_SHORTCUTS


class SettingsDialog(QDialog):
    """Minimal settings dialog with a language selector. Persists the choice
    via QSettings; restart is required for the change to fully apply.
    """

    language_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setModal(True)
        self.resize(400, 360)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(10)
        lang_label = QLabel(tr("settings.language"))
        self.lang_combo = QComboBox()
        for code, display in SUPPORTED_LANGUAGES.items():
            self.lang_combo.addItem(display, userData=code)
        current = current_language()
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == current:
                self.lang_combo.setCurrentIndex(i)
                break
        lang_row.addWidget(lang_label)
        lang_row.addWidget(self.lang_combo, stretch=1)
        root.addLayout(lang_row)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #e1e1e1; max-height: 1px;")
        root.addWidget(divider)

        shortcuts_label = QLabel(tr("settings.shortcuts"))
        shortcuts_label.setStyleSheet("font-weight: 600; color: #3a3a3a;")
        root.addWidget(shortcuts_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)
        for row, sc in enumerate(DEFAULT_SHORTCUTS):
            name = QLabel(tr(sc.label_key))
            name.setStyleSheet("color: #3a3a3a;")
            key = QLabel(sc.key)
            key.setStyleSheet(
                "color: #1a1a1a; background-color: #f0f0f0; "
                "border: 1px solid #d0d0d0; border-radius: 4px; "
                "padding: 2px 8px; font-family: Consolas, monospace;"
            )
            key.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(name, row, 0)
            grid.addWidget(key, row, 1)
        grid.setColumnStretch(0, 1)
        root.addLayout(grid)

        root.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("settings.btn.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            tr("settings.btn.cancel")
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_accept(self) -> None:
        code = str(self.lang_combo.currentData())
        if code != current_language():
            save_language(code)
            set_language(code)
            self.language_changed.emit(code)
        self.accept()

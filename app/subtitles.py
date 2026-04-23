from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr


@dataclass
class Subtitle:
    start_ms: int
    end_ms: int
    text: str
    show_box: bool = True

    def contains(self, pos_ms: int) -> bool:
        return self.start_ms <= pos_ms < self.end_ms


def _format_ms(ms: int) -> str:
    ms = max(0, int(ms))
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}.{(ms % 1000) // 100}"


class SubtitleEditDialog(QDialog):
    """Modal editor for a single Subtitle. Time is entered in seconds with
    one decimal place for sub-second precision; text is multi-line."""

    def __init__(
        self,
        parent: QWidget | None = None,
        initial: Subtitle | None = None,
        max_ms: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("subtitle.edit.title"))
        self.setModal(True)
        self.resize(440, 280)

        max_s = max(1, max_ms // 1000)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        time_row = QHBoxLayout()
        time_row.setSpacing(8)
        time_row.addWidget(QLabel(tr("subtitle.edit.start")))
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, max_s * 10)
        self.start_spin.setSuffix(" · 0.1s")
        time_row.addWidget(self.start_spin)
        time_row.addSpacing(12)
        time_row.addWidget(QLabel(tr("subtitle.edit.end")))
        self.end_spin = QSpinBox()
        self.end_spin.setRange(0, max_s * 10)
        self.end_spin.setSuffix(" · 0.1s")
        time_row.addWidget(self.end_spin)
        time_row.addStretch(1)
        root.addLayout(time_row)

        root.addWidget(QLabel(tr("subtitle.edit.text")))
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(tr("subtitle.edit.placeholder"))
        root.addWidget(self.text_edit, stretch=1)

        self.box_check = QCheckBox(tr("subtitle.edit.show_box"))
        self.box_check.setChecked(True)
        root.addWidget(self.box_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if initial is not None:
            self.start_spin.setValue(initial.start_ms // 100)
            self.end_spin.setValue(max(initial.end_ms // 100, initial.start_ms // 100 + 1))
            self.text_edit.setPlainText(initial.text)
            self.box_check.setChecked(initial.show_box)
        else:
            self.start_spin.setValue(0)
            self.end_spin.setValue(30)

    def result_subtitle(self) -> Subtitle:
        s = self.start_spin.value() * 100
        e = max(s + 100, self.end_spin.value() * 100)
        return Subtitle(
            start_ms=s,
            end_ms=e,
            text=self.text_edit.toPlainText(),
            show_box=self.box_check.isChecked(),
        )


class SubtitlePanel(QWidget):
    """Compact list of subtitles with add/edit/delete buttons.

    ``position_provider`` is an optional callable returning the current
    playhead position in ms, used to pre-fill the start time when adding
    a new subtitle ("add at current playhead" UX).
    """

    subtitles_changed = Signal()
    DEFAULT_DURATION_MS = 4000

    def __init__(self, position_provider=None) -> None:
        super().__init__()
        self._subtitles: list[Subtitle] = []
        self._max_ms: int = 0
        self._position_provider = position_provider or (lambda: 0)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        self._title_label = QLabel(tr("subtitle.section.title"))
        self._title_label.setStyleSheet("font-weight: 600; color: palette(text);")
        header.addWidget(self._title_label)
        header.addStretch(1)

        from PySide6.QtWidgets import QPushButton

        self.add_btn = QPushButton(tr("subtitle.btn.add"))
        self.add_btn.setObjectName("ToolButton")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._on_add)

        self.edit_btn = QPushButton(tr("subtitle.btn.edit"))
        self.edit_btn.setObjectName("ToolButton")
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(self._on_edit)

        self.del_btn = QPushButton(tr("subtitle.btn.delete"))
        self.del_btn.setObjectName("ToolButton")
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.clicked.connect(self._on_delete)

        header.addWidget(self.add_btn)
        header.addWidget(self.edit_btn)
        header.addWidget(self.del_btn)
        root.addLayout(header)

        self._list = QListWidget()
        self._list.setMaximumHeight(110)
        self._list.setAlternatingRowColors(True)
        self._list.itemDoubleClicked.connect(lambda _: self._on_edit())
        root.addWidget(self._list)

    def subtitles(self) -> list[Subtitle]:
        return list(self._subtitles)

    def set_project_duration(self, ms: int) -> None:
        self._max_ms = max(0, int(ms))

    def active_subtitle(self, pos_ms: int) -> Subtitle | None:
        for s in self._subtitles:
            if s.contains(pos_ms):
                return s
        return None

    def _on_add(self) -> None:
        try:
            current_ms = max(0, int(self._position_provider()))
        except Exception:
            current_ms = 0
        seed = Subtitle(
            start_ms=current_ms,
            end_ms=current_ms + self.DEFAULT_DURATION_MS,
            text="",
        )
        dlg = SubtitleEditDialog(self, seed, self._max_ms)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._subtitles.append(dlg.result_subtitle())
            self._subtitles.sort(key=lambda s: s.start_ms)
            self._refresh_list()
            self.subtitles_changed.emit()

    def _on_edit(self) -> None:
        idx = self._list.currentRow()
        if idx < 0 or idx >= len(self._subtitles):
            return
        dlg = SubtitleEditDialog(self, self._subtitles[idx], self._max_ms)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._subtitles[idx] = dlg.result_subtitle()
            self._subtitles.sort(key=lambda s: s.start_ms)
            self._refresh_list()
            self.subtitles_changed.emit()

    def _on_delete(self) -> None:
        idx = self._list.currentRow()
        if idx < 0 or idx >= len(self._subtitles):
            return
        del self._subtitles[idx]
        self._refresh_list()
        self.subtitles_changed.emit()

    def _refresh_list(self) -> None:
        self._list.clear()
        for s in self._subtitles:
            preview = s.text.strip().splitlines()[0] if s.text.strip() else "(empty)"
            if len(preview) > 50:
                preview = preview[:47] + "…"
            item = QListWidgetItem(
                f"{_format_ms(s.start_ms)} → {_format_ms(s.end_ms)}   {preview}"
            )
            self._list.addItem(item)

    def retranslate(self) -> None:
        self._title_label.setText(tr("subtitle.section.title"))
        self.add_btn.setText(tr("subtitle.btn.add"))
        self.edit_btn.setText(tr("subtitle.btn.edit"))
        self.del_btn.setText(tr("subtitle.btn.delete"))

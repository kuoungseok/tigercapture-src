"""Canvas-native plain-text editor for Painter UI text objects."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QPlainTextEdit


class PainterUIInlineTextEditor(QPlainTextEdit):
    commit_requested = Signal(str)
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._finishing = False
        self.setObjectName("PainterUIInlineTextEditor")
        self.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.setTabChangesFocus(False)

    def request_commit(self) -> None:
        if self._finishing:
            return
        self._finishing = True
        self.commit_requested.emit(self.toPlainText())

    def request_cancel(self) -> None:
        if self._finishing:
            return
        self._finishing = True
        self.cancel_requested.emit()

    def reset_finish_state(self) -> None:
        self._finishing = False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.request_cancel()
            event.accept()
            return
        if (
            event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
            and event.modifiers()
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        ):
            self.request_commit()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        if event.reason() != Qt.FocusReason.PopupFocusReason:
            self.request_commit()


__all__ = ["PainterUIInlineTextEditor"]

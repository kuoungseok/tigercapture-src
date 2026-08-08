"""Figma-style canvas comment composer and threaded comments panel."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_review import inspect_ui_review


class PainterUICommentComposer(QFrame):
    submitted = Signal(str)
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUICommentComposer")
        self.setFixedSize(292, 154)
        self.setStyleSheet(
            "#PainterUICommentComposer { background:#FFFFFF; border:1px solid #D9D9D9;"
            " border-radius:12px; }"
            "#PainterUICommentComposer QTextEdit { border:0; background:#FFFFFF; color:#1E1E1E;"
            " font-size:14px; padding:6px; }"
            "#PainterUICommentComposer QPushButton { min-height:30px; padding:0 12px;"
            " border-radius:6px; border:1px solid #D9D9D9; background:#FFFFFF; color:#1E1E1E; }"
            "#PainterUICommentComposer QPushButton#PrimaryCommentButton { background:#0D99FF;"
            " color:#FFFFFF; border-color:#0D99FF; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("댓글을 입력하세요…")
        layout.addWidget(self.editor, 1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton("취소")
        cancel.clicked.connect(self._cancel)
        submit = QPushButton("댓글")
        submit.setObjectName("PrimaryCommentButton")
        submit.clicked.connect(self._submit)
        actions.addWidget(cancel)
        actions.addWidget(submit)
        layout.addLayout(actions)
        self.hide()

    def open_at(self, x: float, y: float) -> None:
        parent = self.parentWidget()
        if parent is not None:
            px = max(8, min(int(x + 14), parent.width() - self.width() - 8))
            py = max(8, min(int(y + 14), parent.height() - self.height() - 8))
            self.move(px, py)
        self.editor.clear()
        self.show()
        self.raise_()
        self.editor.setFocus(Qt.FocusReason.PopupFocusReason)

    def _submit(self) -> None:
        text = self.editor.toPlainText().strip()
        if text:
            self.submitted.emit(text)
            self.hide()

    def _cancel(self) -> None:
        self.hide()
        self.cancelled.emit()


class PainterUICommentsPanel(QWidget):
    comment_selected = Signal(str)
    comment_update_requested = Signal(str, object)
    comment_remove_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUICommentsPanel")
        self._document: Mapping[str, Any] = {}
        self._comments: list[dict[str, Any]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        title = QLabel("댓글")
        title.setStyleSheet("font-size:16px; font-weight:600;")
        layout.addWidget(title)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("댓글 검색")
        self.search.textChanged.connect(self._rebuild)
        self.filter = QComboBox()
        self.filter.addItem("열린 댓글", "open")
        self.filter.addItem("모든 댓글", "all")
        self.filter.addItem("해결됨", "resolved")
        self.filter.currentIndexChanged.connect(self._rebuild)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.filter)
        layout.addLayout(filters)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._select_item)
        layout.addWidget(self.list, 1)
        self.thread = QLabel("캔버스를 클릭해 댓글을 추가하세요.")
        self.thread.setWordWrap(True)
        self.thread.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.thread)
        self.reply = QLineEdit()
        self.reply.setPlaceholderText("답글 추가…")
        self.reply.returnPressed.connect(self._send_reply)
        layout.addWidget(self.reply)
        actions = QHBoxLayout()
        self.resolve = QPushButton("해결")
        self.resolve.clicked.connect(self._toggle_resolved)
        reply_button = QPushButton("답글")
        reply_button.clicked.connect(self._send_reply)
        self.delete = QPushButton("삭제")
        self.delete.clicked.connect(self._delete)
        actions.addWidget(self.resolve)
        actions.addWidget(reply_button)
        actions.addStretch(1)
        actions.addWidget(self.delete)
        layout.addLayout(actions)
        self._sync_actions()

    def set_document(self, document: Mapping[str, Any]) -> None:
        self._document = document
        self._comments = [
            dict(row)
            for row in inspect_ui_review(document, normalize=False)["comments"]
        ]
        selected = self.current_comment_id()
        self._rebuild()
        self.select_comment(selected)

    def current_comment_id(self) -> str:
        item = self.list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def select_comment(self, comment_id: str) -> None:
        for index in range(self.list.count()):
            item = self.list.item(index)
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == str(comment_id or ""):
                self.list.setCurrentItem(item)
                return

    def _visible_comments(self) -> list[dict[str, Any]]:
        query = self.search.text().strip().casefold()
        mode = str(self.filter.currentData() or "open")
        rows = []
        for row in self._comments:
            resolved = bool(row.get("resolved"))
            if mode == "open" and resolved:
                continue
            if mode == "resolved" and not resolved:
                continue
            haystack = " ".join(
                [str(row.get("author") or ""), str(row.get("text") or "")]
                + [str(reply.get("text") or "") for reply in row.get("replies", [])]
            ).casefold()
            if query and query not in haystack:
                continue
            rows.append(row)
        return rows

    def _rebuild(self, *_args) -> None:
        selected = self.current_comment_id()
        self.list.clear()
        for number, row in enumerate(self._visible_comments(), 1):
            replies = len(row.get("replies") or [])
            suffix = f"  ·  답글 {replies}" if replies else ""
            item = QListWidgetItem(
                f"{number}  {row.get('author') or 'Reviewer'}{suffix}\n{row.get('text') or ''}"
            )
            item.setData(Qt.ItemDataRole.UserRole, str(row.get("id") or ""))
            self.list.addItem(item)
        self.select_comment(selected)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._sync_actions()

    def _current_row(self) -> dict[str, Any] | None:
        comment_id = self.current_comment_id()
        return next((row for row in self._comments if row.get("id") == comment_id), None)

    def _select_item(self, *_args) -> None:
        row = self._current_row()
        if row is None:
            self.thread.setText("캔버스를 클릭해 댓글을 추가하세요.")
        else:
            lines = [f"{row.get('author') or 'Reviewer'}: {row.get('text') or ''}"]
            lines.extend(
                f"{reply.get('author') or 'Reviewer'}: {reply.get('text') or ''}"
                for reply in row.get("replies") or []
            )
            self.thread.setText("\n\n".join(lines))
            self.comment_selected.emit(str(row.get("id") or ""))
        self._sync_actions()

    def _sync_actions(self) -> None:
        row = self._current_row()
        enabled = row is not None
        self.reply.setEnabled(enabled)
        self.resolve.setEnabled(enabled)
        self.delete.setEnabled(enabled)
        self.resolve.setText("다시 열기" if row and row.get("resolved") else "해결")

    def _send_reply(self) -> None:
        row = self._current_row()
        text = self.reply.text().strip()
        if row and text:
            self.comment_update_requested.emit(
                str(row["id"]), {"reply": text, "author": "Reviewer"}
            )
            self.reply.clear()

    def _toggle_resolved(self) -> None:
        row = self._current_row()
        if row:
            self.comment_update_requested.emit(
                str(row["id"]), {"resolved": not bool(row.get("resolved"))}
            )

    def _delete(self) -> None:
        row = self._current_row()
        if row:
            self.comment_remove_requested.emit(str(row["id"]))

"""Batch export: queue multiple clips/ranges for export."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class BatchExportItem:
    def __init__(self, label: str, out_path: str, in_ms: int, out_ms: int):
        self.label = label
        self.out_path = out_path
        self.in_ms = in_ms
        self.out_ms = out_ms
        self.status = "pending"  # pending / running / done / error


class BatchExportDialog(QDialog):
    """Shows a queue of export jobs and runs them sequentially."""

    def __init__(self, items: list[BatchExportItem], export_fn, parent=None):
        super().__init__(parent)
        self.setWindowTitle("일괄 내보내기")
        self.setMinimumWidth(520)
        self._items = items
        self._export_fn = export_fn
        self._current = 0

        layout = QVBoxLayout(self)

        # Job list
        self._list = QListWidget()
        for item in items:
            self._list.addItem(f"⏳ {item.label}  →  {Path(item.out_path).name}")
        layout.addWidget(self._list)

        # Overall progress
        self._overall = QProgressBar()
        self._overall.setRange(0, max(len(items), 1))
        self._overall.setValue(0)
        layout.addWidget(QLabel("전체 진행:"))
        layout.addWidget(self._overall)

        # Current job progress
        self._current_bar = QProgressBar()
        self._current_bar.setRange(0, 100)
        layout.addWidget(QLabel("현재 작업:"))
        layout.addWidget(self._current_bar)

        # Buttons
        btns = QDialogButtonBox()
        self._start_btn = QPushButton("시작")
        self._start_btn.clicked.connect(self._start)
        btns.addButton(self._start_btn, QDialogButtonBox.ButtonRole.ActionRole)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.reject)
        btns.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(btns)

    def _start(self):
        self._start_btn.setEnabled(False)
        self._run_next()

    def _run_next(self):
        if self._current >= len(self._items):
            self._start_btn.setText("완료")
            return
        item = self._items[self._current]
        item.status = "running"
        self._list.item(self._current).setText(
            f"▶ {item.label}  →  {Path(item.out_path).name}"
        )

        self._thread = self._export_fn(
            item.in_ms, item.out_ms, item.out_path,
            progress_cb=self._on_progress,
        )
        if hasattr(self._thread, "finished"):
            self._thread.finished.connect(self._on_done)
        if hasattr(self._thread, "start"):
            self._thread.start()

    def _on_progress(self, pct: int):
        self._current_bar.setValue(pct)

    def _on_done(self):
        item = self._items[self._current]
        item.status = "done"
        self._list.item(self._current).setText(
            f"✅ {item.label}  →  {Path(item.out_path).name}"
        )
        self._current += 1
        self._overall.setValue(self._current)
        self._current_bar.setValue(0)
        self._run_next()

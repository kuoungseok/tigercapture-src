"""Batch export dialog backed by the persistent render queue store."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from app.render_queue import RenderQueueStore, jobs_from_batch_items


class BatchExportItem:
    def __init__(self, label: str, out_path: str, in_ms: int, out_ms: int):
        self.label = label
        self.out_path = out_path
        self.in_ms = in_ms
        self.out_ms = out_ms
        self.status = "pending"  # pending / running / done / error
        self.error = ""


class BatchExportDialog(QDialog):
    """Shows a queue of export jobs and runs them sequentially."""

    def __init__(self, items: list[BatchExportItem], export_fn, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Render Queue")
        self.setMinimumWidth(560)
        self._items = items
        self._export_fn = export_fn
        self._current = 0
        self._thread = None
        self._queue_store = RenderQueueStore()
        self._queue_job_ids = self._queue_store.replace(
            jobs_from_batch_items(items)
        )

        layout = QVBoxLayout(self)

        self._list = QListWidget()
        for item in items:
            self._list.addItem(self._row_text(item))
        layout.addWidget(self._list)

        self._overall = QProgressBar()
        self._overall.setRange(0, max(len(items), 1))
        self._overall.setValue(0)
        layout.addWidget(QLabel("Overall progress:"))
        layout.addWidget(self._overall)

        self._current_bar = QProgressBar()
        self._current_bar.setRange(0, 100)
        layout.addWidget(QLabel("Current job:"))
        layout.addWidget(self._current_bar)

        self._summary = QLabel("")
        layout.addWidget(self._summary)

        btns = QDialogButtonBox()
        self._start_btn = QPushButton("Start")
        self._start_btn.clicked.connect(self._start)
        btns.addButton(self._start_btn, QDialogButtonBox.ButtonRole.ActionRole)
        retry_btn = QPushButton("Retry Failed")
        retry_btn.clicked.connect(self._retry_failed)
        btns.addButton(retry_btn, QDialogButtonBox.ButtonRole.ActionRole)
        clear_btn = QPushButton("Clear Done")
        clear_btn.clicked.connect(self._clear_done)
        btns.addButton(clear_btn, QDialogButtonBox.ButtonRole.ActionRole)
        reveal_btn = QPushButton("Reveal Output")
        reveal_btn.clicked.connect(self._reveal_selected)
        btns.addButton(reveal_btn, QDialogButtonBox.ButtonRole.ActionRole)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btns.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(btns)
        self._refresh_summary()

    @staticmethod
    def _row_text(item: BatchExportItem) -> str:
        text = f"[{item.status}] {item.label}  ->  {Path(item.out_path).name}"
        if item.status == "error" and item.error:
            text += f"  ({item.error[:80]})"
        return text

    def _refresh_list(self) -> None:
        self._list.clear()
        for item in self._items:
            self._list.addItem(self._row_text(item))
        self._refresh_summary()

    def _update_queue_status(
        self,
        index: int,
        status: str,
        *,
        error: str = "",
        diagnostics: str = "",
    ) -> None:
        if 0 <= index < len(self._queue_job_ids):
            self._queue_store.update_status(
                self._queue_job_ids[index],
                status,
                error=error,
                diagnostics=diagnostics,
            )

    def _refresh_summary(self) -> None:
        counts: dict[str, int] = {}
        for item in self._items:
            counts[item.status] = counts.get(item.status, 0) + 1
        total = len(self._items)
        done = counts.get("done", 0)
        failed = counts.get("error", 0)
        pending = counts.get("pending", 0)
        running = counts.get("running", 0)
        self._summary.setText(
            f"{total} jobs | {done} done | {failed} failed | "
            f"{running} running | {pending} pending"
        )

    def _start(self):
        self._start_btn.setEnabled(False)
        self._current = 0
        self._run_next()

    def _run_next(self):
        while self._current < len(self._items) and self._items[self._current].status != "pending":
            self._current += 1
        if self._current >= len(self._items):
            self._start_btn.setText("Done")
            self._refresh_summary()
            return
        item = self._items[self._current]
        item.status = "running"
        self._list.item(self._current).setText(self._row_text(item))
        self._update_queue_status(self._current, "running")
        self._refresh_summary()

        self._thread = self._export_fn(
            item.in_ms,
            item.out_ms,
            item.out_path,
            progress_cb=self._on_progress,
        )
        if hasattr(self._thread, "finished_error"):
            self._thread.finished_error.connect(self._on_error)
        if hasattr(self._thread, "finished"):
            self._thread.finished.connect(self._on_done)
        if hasattr(self._thread, "start"):
            self._thread.start()

    def _on_progress(self, pct: int):
        self._current_bar.setValue(max(0, min(100, int(pct))))

    def _on_error(self, reason: str):
        item = self._items[self._current]
        item.status = "error"
        item.error = str(reason)
        self._list.item(self._current).setText(self._row_text(item))
        diagnostics = ""
        try:
            from app.render_diagnostics import format_render_failure_diagnostics

            job_id = self._queue_job_ids[self._current]
            job = next((j for j in self._queue_store.jobs if j.id == job_id), None)
            diagnostics = format_render_failure_diagnostics(reason, job)
        except Exception:
            diagnostics = str(reason)
        self._update_queue_status(
            self._current,
            "error",
            error=str(reason),
            diagnostics=diagnostics,
        )
        self._refresh_summary()

    def _on_done(self):
        item = self._items[self._current]
        if item.status != "error":
            item.status = "done"
            self._list.item(self._current).setText(self._row_text(item))
            self._update_queue_status(self._current, "done")
        self._current += 1
        self._overall.setValue(self._current)
        self._current_bar.setValue(0)
        self._refresh_summary()
        self._run_next()

    def _retry_failed(self) -> None:
        if self._thread is not None and hasattr(self._thread, "isRunning"):
            try:
                if self._thread.isRunning():
                    return
            except Exception:
                pass
        changed = False
        for item in self._items:
            if item.status != "error":
                continue
            item.status = "pending"
            item.error = ""
            changed = True
        if changed:
            self._queue_store.retry_failed()
            self._current = 0
            self._start_btn.setText("Start")
            self._start_btn.setEnabled(True)
            self._refresh_list()

    def _clear_done(self) -> None:
        if self._thread is not None and hasattr(self._thread, "isRunning"):
            try:
                if self._thread.isRunning():
                    return
            except Exception:
                pass
        kept: list[BatchExportItem] = []
        kept_ids: list[str] = []
        done_ids: list[str] = []
        for item, job_id in zip(self._items, self._queue_job_ids):
            if item.status == "done":
                done_ids.append(job_id)
                continue
            kept.append(item)
            kept_ids.append(job_id)
        self._items = kept
        self._queue_job_ids = kept_ids
        self._queue_store.remove_jobs(done_ids)
        self._current = 0
        self._overall.setRange(0, max(len(self._items), 1))
        self._overall.setValue(0)
        self._refresh_list()

    def _reveal_selected(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._items):
            return
        out_path = Path(self._items[row].out_path)
        target = out_path.parent if out_path.parent.exists() else out_path
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except Exception:
            pass

"""In-app actor loading/cache/probe status browser."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class ActorLoadingManagerDialog(QDialog):
    """Browse Live2D/Spine loading cache, isolated probe, and prerender state."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Actor Loading Manager")
        self.resize(820, 520)
        self._entries: list[dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        body = QHBoxLayout()
        self._list = QListWidget()
        body.addWidget(self._list, 1)
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        body.addWidget(self._detail, 2)
        root.addLayout(body, 1)

        buttons = QDialogButtonBox()
        self._refresh_btn = QPushButton("Refresh")
        self._clear_btn = QPushButton("Clear Cache")
        self._qa_btn = QPushButton("Run Loading QA")
        self._probe_btn = QPushButton("Probe Selected")
        self._prerender_btn = QPushButton("Prerender Selected")
        self._quarantine_btn = QPushButton("Quarantine")
        self._overnight_plan_btn = QPushButton("Overnight Plan")
        self._overnight_render_btn = QPushButton("Render Smoke")
        self._open_btn = QPushButton("Open Cache Folder")
        self._open_actor_btn = QPushButton("Open Actor Folder")
        close_btn = QPushButton("Close")
        self._refresh_btn.clicked.connect(self.refresh)
        self._clear_btn.clicked.connect(self._clear_cache)
        self._qa_btn.clicked.connect(self._run_loading_qa)
        self._probe_btn.clicked.connect(self._probe_selected)
        self._prerender_btn.clicked.connect(self._prerender_selected)
        self._quarantine_btn.clicked.connect(self._quarantine_selected)
        self._overnight_plan_btn.clicked.connect(lambda: self._run_overnight(render=False))
        self._overnight_render_btn.clicked.connect(lambda: self._run_overnight(render=True))
        self._open_btn.clicked.connect(self._open_cache_folder)
        self._open_actor_btn.clicked.connect(self._open_actor_folder)
        close_btn.clicked.connect(self.accept)
        for btn in (
            self._refresh_btn,
            self._clear_btn,
            self._qa_btn,
            self._probe_btn,
            self._prerender_btn,
            self._quarantine_btn,
            self._overnight_plan_btn,
            self._overnight_render_btn,
            self._open_btn,
            self._open_actor_btn,
        ):
            buttons.addButton(btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(close_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(buttons)

        self._list.itemSelectionChanged.connect(self._refresh_detail)
        self.refresh()

    def refresh(self) -> None:
        from app.actor_loading_cache import actor_loading_cache_report
        from app.actor_prerender_cache import actor_prerender_cache_report

        loading = actor_loading_cache_report()
        prerender = actor_prerender_cache_report()
        entries = list(loading.get("entries", []) or [])
        self._entries = entries
        self._list.clear()
        counts = (loading.get("summary", {}) or {}).get("status_counts", {})
        self._summary.setText(
            f"Actor loads: {len(entries)} | "
            f"statuses={counts} | prerender={prerender.get('summary', {}).get('entries', 0)} cache(s)"
        )
        for idx, row in enumerate(entries):
            label = (
                f"[{str(row.get('status', 'unknown')).upper()}] "
                f"{row.get('kind', '-')}: {Path(str(row.get('path', ''))).name} "
                f"{row.get('progress', 0)}%"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setToolTip(str(row.get("path", "")))
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        else:
            self._detail.setPlainText("No actor loading cache entries yet.")
        self._sync_selection_buttons()

    def _selected(self) -> dict[str, Any] | None:
        item = self._list.currentItem()
        if item is None:
            return None
        try:
            return self._entries[int(item.data(Qt.ItemDataRole.UserRole))]
        except Exception:
            return None

    def _refresh_detail(self) -> None:
        row = self._selected()
        if not row:
            self._detail.setPlainText("")
            self._sync_selection_buttons()
            return
        try:
            from app.actor_loading_status import actor_loading_diagnostic_card, format_actor_loading_diagnostic_card

            card = row.get("diagnostic_card") if isinstance(row.get("diagnostic_card"), dict) else None
            if card is None:
                card = actor_loading_diagnostic_card(
                    str(row.get("kind") or ""),
                    str(row.get("path") or ""),
                    status=str(row.get("status") or ""),
                    stage=str(row.get("stage") or ""),
                    message=str(row.get("message") or ""),
                    metadata=dict(row.get("metadata") or {}),
                )
            body = format_actor_loading_diagnostic_card(card)
            body += "\n\nTechnical details\n"
            body += json.dumps(row, ensure_ascii=False, indent=2, default=str)
            self._detail.setPlainText(body)
        except Exception:
            self._detail.setPlainText(json.dumps(row, ensure_ascii=False, indent=2, default=str))
        self._sync_selection_buttons()

    def _sync_selection_buttons(self) -> None:
        row = self._selected()
        enabled = bool(row and row.get("kind") and row.get("path"))
        for btn in (self._probe_btn, self._prerender_btn, self._quarantine_btn, self._open_actor_btn):
            try:
                btn.setEnabled(enabled)
            except Exception:
                pass

    def _clear_cache(self) -> None:
        from app.actor_loading_cache import clear_actor_loading_cache

        clear_actor_loading_cache()
        self.refresh()

    def _run_loading_qa(self) -> None:
        try:
            from tools.qa_actor_loading_ux import run_actor_loading_ux_qa

            report = run_actor_loading_ux_qa()
        except Exception as exc:
            QMessageBox.warning(self, "Actor Loading Manager", f"QA failed: {exc}")
            return
        QMessageBox.information(
            self,
            "Actor Loading Manager",
            f"Loading QA {'passed' if report.get('ok') else 'needs attention'}.\nIssues: {len(report.get('issues', []) or [])}",
        )
        self.refresh()

    def _probe_selected(self) -> None:
        row = self._selected()
        if not row:
            return
        try:
            from app.actor_preview_frame_server import default_actor_preview_frame_server, write_actor_probe_report

            payload = default_actor_preview_frame_server().probe_frame(
                str(row.get("kind") or ""),
                str(row.get("path") or ""),
                width=320,
                height=320,
                timeout_ms=30_000,
            )
            out = write_actor_probe_report(Path("debugCapture") / "actor_probe_selected.json", payload)
        except Exception as exc:
            QMessageBox.warning(self, "Actor Loading Manager", f"Probe failed: {exc}")
            return
        self._detail.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        QMessageBox.information(
            self,
            "Actor Loading Manager",
            f"Probe {payload.get('status', 'unknown')}.\nReport: {out}",
        )
        self.refresh()

    def _prerender_selected(self) -> None:
        row = self._selected()
        if not row:
            return
        try:
            from app.actor_preview_frame_server import default_actor_preview_frame_server

            payload = default_actor_preview_frame_server().prerender_preview(
                str(row.get("kind") or ""),
                str(row.get("path") or ""),
                width=360,
                height=360,
                fps=12,
                duration_ms=1200,
                limit_frames=12,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Actor Loading Manager", f"Prerender failed: {exc}")
            return
        self._detail.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        QMessageBox.information(
            self,
            "Actor Loading Manager",
            f"Prerender {payload.get('status', 'unknown')}.\nFrames: {payload.get('frame_count', 0)}\nFolder: {payload.get('folder', '')}",
        )
        self.refresh()

    def _quarantine_selected(self) -> None:
        row = self._selected()
        if not row:
            return
        try:
            from app.actor_known_failures import add_actor_known_failure

            entry = add_actor_known_failure(
                kind=str(row.get("kind") or ""),
                path=str(row.get("path") or ""),
                area="loading",
                reason=f"Quarantined from Actor Loading Manager after status={row.get('status', 'unknown')}.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Actor Loading Manager", f"Quarantine failed: {exc}")
            return
        QMessageBox.information(
            self,
            "Actor Loading Manager",
            f"Known-failure quarantine updated:\n{entry.get('id')}",
        )

    def _run_overnight(self, *, render: bool) -> None:
        try:
            from tools.qa_actor_overnight import run_actor_overnight_qa

            report = run_actor_overnight_qa(render=render, limit=8 if render else 24, timeout_ms=30_000)
            out = Path("debugCapture") / "actor_overnight_qa.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except Exception as exc:
            QMessageBox.warning(self, "Actor Loading Manager", f"Overnight QA failed: {exc}")
            return
        self._detail.setPlainText(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        QMessageBox.information(
            self,
            "Actor Loading Manager",
            f"Overnight {'render smoke' if render else 'plan'} {'passed' if report.get('ok') else 'needs attention'}.\nReport: {out}",
        )

    def _open_cache_folder(self) -> None:
        try:
            from app.actor_loading_cache import default_actor_cache_path

            os.startfile(str(default_actor_cache_path().parent))
        except Exception:
            pass

    def _open_actor_folder(self) -> None:
        row = self._selected()
        if not row:
            return
        try:
            path = Path(str(row.get("path") or ""))
            folder = path.parent if path.suffix else path
            os.startfile(str(folder))
        except Exception:
            pass

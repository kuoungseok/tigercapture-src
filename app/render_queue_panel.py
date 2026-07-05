"""Dockable render queue panel for background batch exports."""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.render_queue import (
    RenderQueueJob,
    RenderQueueStore,
    create_diagnostic_retry_job,
    jobs_from_batch_items,
    render_queue_product_diagnostics,
)
from app.style import editor_scrollbar_qss


ExportFactory = Callable[[int, int, str, Any], Any]


def _format_range(in_ms: int, out_ms: int) -> str:
    def _one(ms: int) -> str:
        seconds = max(0, int(ms)) // 1000
        return f"{seconds // 60}:{seconds % 60:02d}"

    return f"{_one(in_ms)} - {_one(out_ms)}"


def audio_delivery_preflight_text_for_tracks(
    audio_tracks: list[Any] | None = None,
    *,
    measured: dict[str, Any] | None = None,
    target: str = "shortform",
) -> str:
    """Return compact audio delivery QA text for export diagnostics."""
    from app.audio_workflow import audio_delivery_qa_gate, build_default_routing_matrix

    rows: list[dict[str, Any]] = []
    for idx, track in enumerate(list(audio_tracks or [])):
        if isinstance(track, dict):
            rows.append({
                "id": track.get("id", idx),
                "label": track.get("label") or track.get("name") or f"A{idx + 1}",
                "role": track.get("role") or track.get("bus_role") or track.get("bus_id") or "",
                "bus_id": track.get("bus_id") or "",
            })
        else:
            rows.append({
                "id": getattr(track, "id", idx),
                "label": getattr(track, "label", "") or getattr(track, "name", "") or f"A{idx + 1}",
                "role": getattr(track, "role", "") or getattr(track, "bus_role", "") or getattr(track, "bus_id", ""),
                "bus_id": getattr(track, "bus_id", ""),
            })
    if measured is None:
        measured = {"integrated_lufs": -14.0, "true_peak_db": -1.0, "lra": 8.0}
    gate = audio_delivery_qa_gate(
        measured,
        target=target,
        routing=build_default_routing_matrix(rows).to_dict(),
    )
    loudness = gate.get("loudness", {}) if isinstance(gate, dict) else {}
    lines = [
        (
            f"Audio Delivery QA: {'OK' if gate.get('ok') else 'Review'} | "
            f"target={loudness.get('target_id', target)} | "
            f"LUFS={float(loudness.get('integrated_lufs', 0.0) or 0.0):.1f}/"
            f"{float(loudness.get('target_lufs', 0.0) or 0.0):.1f} | "
            f"peak={float(loudness.get('true_peak_db', 0.0) or 0.0):.1f} dB | "
            f"routes={int(gate.get('route_count', 0) or 0)} buses={int(gate.get('bus_count', 0) or 0)}"
        )
    ]
    warnings = [str(v) for v in list(gate.get("warnings", []) or []) if str(v)]
    if warnings:
        lines.append("Audio Delivery Warnings: " + "; ".join(warnings[:4]))
    return "\n".join(lines)


def render_preflight_cards_from_text(text: str) -> list[dict[str, str]]:
    """Parse export/preflight diagnostics into compact UI card rows."""
    raw_lines = [line.strip() for line in str(text or "").splitlines()]
    lines = [line for line in raw_lines if line]
    prefixes = [
        ("readiness", "Professional Readiness", "Professional Readiness"),
        ("color_scope", "Color Scope QA", "Color Scope QA"),
        ("audio_delivery", "Audio Delivery QA", "Audio Delivery QA"),
        ("audio_warning", "Audio Delivery Warnings", "Audio Warnings"),
        ("vfx_graph", "VFX Graph QA", "VFX Graph QA"),
        ("export_parity", "Preset/Template Export Parity", "Export Parity"),
    ]
    cards: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        lower = line.lower()
        matched = None
        for card_id, prefix, label in prefixes:
            if lower.startswith(prefix.lower()):
                matched = (card_id, prefix, label)
                break
        if matched is None:
            continue
        card_id, prefix, label = matched
        if card_id in seen:
            continue
        seen.add(card_id)
        _, _, after = line.partition(":")
        summary = after.strip() or line[len(prefix):].strip(" :-") or line
        state = "info"
        state_label = "Info"
        status_tokens = {
            token.strip(" .,;:|[]()").lower()
            for token in lower.replace("/", " ").replace("-", " ").split()
        }
        if {
            "review",
            "warning",
            "warnings",
            "fail",
            "failed",
            "missing",
            "unresolved",
            "error",
            "errors",
        } & status_tokens:
            state = "review"
            state_label = "Review"
        elif " ok" in f" {lower}" or lower.endswith(": ok") or ": ok" in lower:
            state = "ok"
            state_label = "OK"
        elif card_id == "audio_warning":
            state = "review"
            state_label = "Review"
        cards.append({
            "id": card_id,
            "label": label,
            "state": state,
            "state_label": state_label,
            "summary": summary[:220],
            "detail": line,
        })
    return cards


def render_preflight_card_summary_text(text: str) -> str:
    cards = render_preflight_cards_from_text(text)
    if not cards:
        return ""
    return " | ".join(
        f"{card['label']}: {card['state_label']}"
        for card in cards[:4]
    )


def render_preflight_card_detail_text(card: dict[str, str], diagnostics: str = "") -> str:
    """Return a readable per-card diagnostics detail block."""
    label = str(card.get("label") or "Preflight")
    state = str(card.get("state_label") or card.get("state") or "Info")
    summary = str(card.get("summary") or "").strip()
    detail = str(card.get("detail") or "").strip()
    lines = [
        label,
        "",
        f"Status: {state}",
    ]
    if summary:
        lines.append(f"Summary: {summary}")
    if detail:
        lines.extend(["", "Source:", detail])
    related: list[str] = []
    label_prefix = label.lower()
    card_id = str(card.get("id") or "").lower()
    for raw in str(diagnostics or "").splitlines():
        line = raw.strip()
        lower = line.lower()
        if not line or line == detail:
            continue
        if lower.startswith(label_prefix) or (
            card_id == "readiness" and lower.startswith(("readiness actions", "- "))
        ):
            related.append(line)
    if related:
        lines.extend(["", "Related:", *related[:8]])
    return "\n".join(lines)


def render_preflight_card_action_specs(card: dict[str, str]) -> list[dict[str, str]]:
    """Return user-facing actions that make sense for a preflight card."""
    card_id = str(card.get("id") or "").lower()
    if card_id == "readiness":
        return [
            {"id": "health", "label": "Open Health"},
            {"id": "qa_dashboard", "label": "QA Dashboard"},
        ]
    if card_id == "color_scope":
        return [
            {"id": "color_page", "label": "Open Color"},
            {"id": "qa_dashboard", "label": "Color QA"},
        ]
    if card_id in {"audio_delivery", "audio_warning"}:
        return [
            {"id": "audio_mixer", "label": "Open Mixer"},
            {"id": "qa_dashboard", "label": "Audio QA"},
        ]
    if card_id == "vfx_graph":
        return [
            {"id": "health", "label": "Open Health"},
            {"id": "qa_dashboard", "label": "QA Dashboard"},
        ]
    if card_id == "export_parity":
        return [
            {"id": "preset_qa", "label": "Run Preset QA"},
            {"id": "deliver_presets", "label": "Deliver Presets"},
        ]
    return [{"id": "qa_dashboard", "label": "QA Dashboard"}]


class RenderQueuePanel(QWidget):
    """Persistent, non-modal render queue runner.

    The panel stores all jobs as history in ``RenderQueueStore``. Jobs from the
    current editor session also carry an in-memory export factory, so they can
    run in the background while the editor remains usable.
    """

    status_changed = Signal(dict)

    def __init__(self, parent=None, *, store: RenderQueueStore | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RenderQueuePanel")
        self._store = store or RenderQueueStore()
        self._runtime_items: dict[str, Any] = {}
        self._runtime_exports: dict[str, Callable] = {}
        self._thread = None
        self._current_job_id = ""
        self._paused = False
        self._last_success_note = ""
        self._last_maintenance_note = ""
        self._runtime_project_settings: dict[str, dict] = {}
        self._runtime_preflight_diagnostics: dict[str, str] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(4)

        self._summary = QLabel("")
        self._summary.setObjectName("RenderQueueSummary")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        filters = QHBoxLayout()
        filters.setSpacing(6)
        self._status_filter = QComboBox()
        self._status_filter.setObjectName("RenderQueueFilter")
        for label, status in [
            ("All", ""),
            ("Pending", "pending"),
            ("Running", "running"),
            ("Paused", "paused"),
            ("Done", "done"),
            ("Failed", "error"),
            ("Canceled", "canceled"),
        ]:
            self._status_filter.addItem(label, status)
        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("RenderQueueSearch")
        self._search_edit.setPlaceholderText("Search job, output, source, diagnostics")
        self._clear_old_btn = QPushButton("Clear Old")
        self._clear_old_btn.setObjectName("ToolButton")
        filters.addWidget(QLabel("Status"))
        filters.addWidget(self._status_filter)
        filters.addWidget(self._search_edit, 1)
        filters.addWidget(self._clear_old_btn)
        root.addLayout(filters)

        self._table = QTableWidget(0, 5)
        self._table.setObjectName("RenderQueueTable")
        self._table.setHorizontalHeaderLabels([
            "Status",
            "Job",
            "Range",
            "Output",
            "Diagnostics",
        ])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(42)
        root.addWidget(self._table, 1)
        self._table.itemSelectionChanged.connect(self._update_detail_panel)

        self._detail = QPlainTextEdit()
        self._detail.setObjectName("RenderQueueDetail")
        self._detail.setReadOnly(True)
        self._detail.setPlaceholderText("Select a render job to inspect diagnostics.")
        self._detail.setMinimumHeight(92)
        self._detail.setMaximumHeight(150)
        self._preflight_cards_host = QWidget(self)
        self._preflight_cards_host.setObjectName("RenderPreflightCards")
        self._preflight_cards_host.setStyleSheet(
            "QWidget#RenderPreflightCards { background:transparent; border:none; }"
            "QPushButton[preflightCard='true'] {"
            "border:1px solid #30363D; border-radius:7px; padding:4px 7px;"
            "font-size:9px; font-weight:600; color:#DCE2EA; text-align:left;"
            "background:#15181D;"
            "}"
            "QPushButton[preflightCard='true']:hover {"
            "border-color:#68717E; background:#20252B;"
            "}"
            "QPushButton[preflightState='ok'] {"
            "border-color:#4D6E61; background:rgba(143,168,148,22);"
            "}"
            "QPushButton[preflightState='review'] {"
            "border-color:#76574F; background:rgba(182,90,82,22);"
            "}"
            "QPushButton[preflightState='info'] {"
            "border-color:#596474; background:rgba(168,183,202,20);"
            "}"
        )
        self._preflight_cards_layout = QHBoxLayout(self._preflight_cards_host)
        self._preflight_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._preflight_cards_layout.setSpacing(6)
        self._preflight_cards_host.hide()
        self._preflight_card_buttons: list[QPushButton] = []
        root.addWidget(self._preflight_cards_host)
        root.addWidget(self._detail)

        self._overall = QProgressBar()
        self._overall.setObjectName("RenderQueueProgress")
        self._overall.setRange(0, 100)
        self._overall.setValue(0)
        root.addWidget(self._overall)

        buttons = QHBoxLayout()
        buttons.setSpacing(3)
        self._run_btn = QPushButton("Run")
        self._pause_btn = QPushButton("Pause")
        self._resume_btn = QPushButton("Resume")
        self._cancel_btn = QPushButton("Cancel")
        self._retry_btn = QPushButton("Retry")
        self._retry_range_btn = QPushButton("Queue Retry Range")
        self._clear_btn = QPushButton("Clear Done")
        self._reveal_btn = QPushButton("Reveal")
        self._copy_diag_btn = QPushButton("Copy Diagnostics")
        self._view_log_btn = QPushButton("View Log")
        self._deliver_presets_btn = QPushButton("Deliver Presets")
        self._resolve_btn = QPushButton("Resolve")
        self._refresh_btn = QPushButton("Refresh")
        for btn in [
            self._run_btn,
            self._pause_btn,
            self._resume_btn,
            self._cancel_btn,
            self._retry_btn,
            self._retry_range_btn,
            self._clear_btn,
            self._reveal_btn,
            self._copy_diag_btn,
            self._view_log_btn,
            self._deliver_presets_btn,
            self._resolve_btn,
            self._refresh_btn,
        ]:
            btn.setObjectName("ToolButton")
            btn.setMinimumHeight(24)
            btn.setToolTip(btn.text())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            buttons.addWidget(btn)
        root.addLayout(buttons)

        self._run_btn.clicked.connect(self.start_pending)
        self._pause_btn.clicked.connect(self.pause_after_current)
        self._resume_btn.clicked.connect(self.resume_pending)
        self._cancel_btn.clicked.connect(self.cancel_current_or_pending)
        self._retry_btn.clicked.connect(self.retry_failed)
        self._retry_range_btn.clicked.connect(self.queue_selected_retry_range)
        self._clear_btn.clicked.connect(self.clear_completed)
        self._clear_old_btn.clicked.connect(self.clear_old_history)
        self._reveal_btn.clicked.connect(self.reveal_selected_output)
        self._copy_diag_btn.clicked.connect(self.copy_selected_diagnostics)
        self._view_log_btn.clicked.connect(self.show_selected_log)
        self._deliver_presets_btn.clicked.connect(self.show_deliver_presets)
        self._resolve_btn.clicked.connect(self.show_failure_wizard)
        self._refresh_btn.clicked.connect(self.refresh_from_store)
        self._status_filter.currentIndexChanged.connect(self._refresh_table)
        self._search_edit.textChanged.connect(self._refresh_table)

        self._apply_studio_style()
        self.refresh_from_store()

    def _apply_studio_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#RenderQueuePanel {
                background: #111214;
                color: #E6EAF2;
                font-family: "Pretendard", "Noto Sans KR", "Malgun Gothic", "Segoe UI", sans-serif;
                font-size: 10px;
            }
            QWidget#RenderQueuePanel QLabel {
                color: #B8C0CA;
                font-size: 10px;
            }
            QLabel#RenderQueueSummary {
                color: #AEB5BF;
                padding: 0px 1px 2px 1px;
            }
            QComboBox#RenderQueueFilter,
            QLineEdit#RenderQueueSearch,
            QPlainTextEdit#RenderQueueDetail {
                color: #DCE2EA;
                background: #14161A;
                border: 1px solid #282D34;
                border-radius: 7px;
                padding: 5px 8px;
                selection-background-color: #4A5568;
                selection-color: #FFFFFF;
            }
            QComboBox#RenderQueueFilter:focus,
            QLineEdit#RenderQueueSearch:focus,
            QPlainTextEdit#RenderQueueDetail:focus {
                background: #15181D;
                border-color: #566171;
            }
            QTableWidget#RenderQueueTable {
                color: #DCE2EA;
                background: #101215;
                alternate-background-color: #14171B;
                gridline-color: transparent;
                border: 1px solid #242A31;
                border-radius: 8px;
                selection-background-color: rgba(94, 107, 126, 54);
                selection-color: #F2F5FA;
                outline: none;
            }
            QTableWidget#RenderQueueTable::item {
                border-bottom: 1px solid rgba(52, 59, 68, 118);
                padding: 5px 6px;
            }
            QTableWidget#RenderQueueTable::item:selected {
                color: #F3F5F8;
                background: rgba(76, 86, 101, 72);
                border-bottom: 1px solid rgba(116, 126, 140, 126);
            }
            QHeaderView::section {
                color: #AEB5BF;
                background: #171A1F;
                border: none;
                border-right: 1px solid rgba(58, 64, 73, 120);
                border-bottom: 1px solid rgba(58, 64, 73, 120);
                padding: 5px 6px;
                font-size: 9px;
                font-weight: 600;
            }
            QProgressBar#RenderQueueProgress {
                color: #AEB5BF;
                background: #121419;
                border: 1px solid #29303A;
                border-radius: 5px;
                height: 9px;
                text-align: center;
                font-size: 8px;
            }
            QProgressBar#RenderQueueProgress::chunk {
                background: #778290;
                border-radius: 4px;
            }
            QPushButton#ToolButton {
                color: #DCE2EA;
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #23272E, stop:1 #171A1F);
                border: 1px solid #363D46;
                border-radius: 7px;
                padding: 4px 7px;
                font-size: 9px;
                font-weight: 600;
            }
            QPushButton#ToolButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2B3038, stop:1 #1B1F25);
                border-color: #66717D;
            }
            QPushButton#ToolButton:pressed {
                background: #15181D;
                border-color: #515A66;
            }
            QPushButton#ToolButton:disabled {
                color: #5E6670;
                background: #111316;
                border-color: #22262C;
            }
            """
            + editor_scrollbar_qss("QWidget#RenderQueuePanel")
        )

    def queue_items(
        self,
        items: list[Any],
        export_fn: Callable,
        *,
        project_path: str = "",
        source_path: str = "",
        format_id: str = "",
        quality_id: str = "",
        project_settings: dict | None = None,
        preflight_diagnostics: str = "",
        auto_start: bool = False,
    ) -> list[str]:
        jobs = jobs_from_batch_items(
            items,
            project_path=project_path,
            source_path=source_path,
            format_id=format_id,
            quality_id=quality_id,
        )
        job_ids: list[str] = []
        for item, job in zip(items, jobs):
            item.status = "pending"
            item.error = ""
            preflight = str(preflight_diagnostics or "")
            if preflight:
                job.diagnostics = preflight
            job_id = self._store.add(job)
            job_ids.append(job_id)
            self._runtime_items[job_id] = item
            self._runtime_exports[job_id] = export_fn
            self._runtime_project_settings[job_id] = dict(project_settings or {})
            if preflight:
                self._runtime_preflight_diagnostics[job_id] = preflight
        self._paused = False
        self.refresh_from_store()
        if auto_start:
            self.start_pending()
        return job_ids

    def is_running(self) -> bool:
        if self._thread is None:
            return False
        try:
            return bool(self._thread.isRunning())
        except Exception:
            return bool(self._current_job_id)

    def refresh_from_store(self) -> None:
        if not self.is_running():
            self._store.load()
        self._refresh_table()

    def start_pending(self) -> None:
        if self.is_running():
            return
        self._paused = False
        self._run_next()

    def pause_after_current(self) -> None:
        self._paused = True
        changed = 0
        for job_id, item in self._runtime_items.items():
            if getattr(item, "status", "") == "pending":
                item.status = "paused"
                self._store.update_status(job_id, "paused")
                changed += 1
        if changed:
            self.refresh_from_store()
        else:
            self._refresh_table()

    def resume_pending(self) -> None:
        self._paused = False
        for job_id, item in self._runtime_items.items():
            if getattr(item, "status", "") == "paused":
                item.status = "pending"
                self._store.update_status(job_id, "pending")
        self.refresh_from_store()
        self.start_pending()

    def cancel_current_or_pending(self) -> None:
        self._paused = True
        if self.is_running() and self._current_job_id:
            thread = self._thread
            if hasattr(thread, "cancel"):
                try:
                    thread.cancel()
                except Exception:
                    pass
            job = self._job_by_id(self._current_job_id)
            self._store.update_status(
                self._current_job_id,
                "canceled",
                error="Canceled by user.",
                diagnostics=self._diagnostics_for_job(job, "Canceled by user"),
            )
            item = self._runtime_items.get(self._current_job_id)
            if item is not None:
                item.status = "canceled"
                item.error = "Canceled by user."
        for job_id, item in self._runtime_items.items():
            if getattr(item, "status", "") in {"pending", "paused"}:
                item.status = "canceled"
                item.error = "Canceled before render started."
                self._store.update_status(
                    job_id,
                    "canceled",
                    error="Canceled before render started.",
                )
        self.refresh_from_store()

    def retry_failed(self) -> None:
        if self.is_running():
            return
        for job_id, item in self._runtime_items.items():
            if getattr(item, "status", "") == "error":
                item.status = "pending"
                item.error = ""
                self._store.update_status(job_id, "pending")
        self.refresh_from_store()

    def queue_selected_retry_range(self) -> str:
        if self.is_running():
            return ""
        job = self._selected_job()
        if job is None or job.status != "error":
            return ""
        export_fn = self._runtime_exports.get(job.id)
        if export_fn is None:
            QMessageBox.information(
                self,
                "Render Queue",
                "This historical job has no live export session. Re-open the project and queue it again.",
            )
            return ""
        retry = create_diagnostic_retry_job(job)
        job_id = self._store.add(retry)
        self._runtime_exports[job_id] = export_fn
        self._runtime_project_settings[job_id] = dict(
            self._runtime_project_settings.get(job.id, {})
        )
        self._runtime_items[job_id] = SimpleNamespace(
            label=retry.label,
            out_path=retry.out_path,
            in_ms=retry.in_ms,
            out_ms=retry.out_ms,
            status="pending",
            error="",
        )
        self.refresh_from_store()
        self._select_job_id(job_id)
        return job_id

    def clear_completed(self) -> None:
        if self.is_running():
            return
        done_ids = {job.id for job in self._store.jobs if job.status == "done"}
        removed = self._store.clear_completed()
        if removed:
            for job_id in done_ids:
                self._runtime_items.pop(job_id, None)
                self._runtime_exports.pop(job_id, None)
                self._runtime_project_settings.pop(job_id, None)
                self._runtime_preflight_diagnostics.pop(job_id, None)
        self.refresh_from_store()

    def clear_old_history(self) -> None:
        if self.is_running():
            return
        before_ids = {job.id for job in self._store.jobs}
        removed = self._store.prune_terminal_history(
            older_than_days=30,
            keep_latest=200,
        )
        if removed:
            live_ids = {job.id for job in self._store.jobs}
            for job_id in before_ids - live_ids:
                self._runtime_items.pop(job_id, None)
                self._runtime_exports.pop(job_id, None)
                self._runtime_project_settings.pop(job_id, None)
                self._runtime_preflight_diagnostics.pop(job_id, None)
            self._last_maintenance_note = f"Removed {removed} old history job(s)."
        else:
            self._last_maintenance_note = "No old render history to remove."
        self.refresh_from_store()

    def reveal_selected_output(self) -> None:
        job = self._selected_job()
        if job is None:
            return
        out_path = Path(job.out_path)
        target = out_path.parent if out_path.parent.exists() else out_path
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except Exception as exc:
            QMessageBox.information(self, "Render Queue", f"Could not open output folder:\n{exc}")

    def _run_next(self) -> None:
        if self._paused:
            self._refresh_table()
            return
        job = self._next_runnable_job()
        if job is None:
            self._current_job_id = ""
            self._thread = None
            self._refresh_table()
            return

        export_fn = self._runtime_exports.get(job.id)
        item = self._runtime_items.get(job.id)
        if export_fn is None or item is None:
            self._store.update_status(
                job.id,
                "error",
                error="Job was loaded from history and has no live export session.",
            )
            self._refresh_table()
            self._run_next()
            return

        self._current_job_id = job.id
        self._last_success_note = ""
        item.status = "running"
        item.error = ""
        self._store.update_status(
            job.id,
            "running",
            diagnostics=self._diagnostics_for_job(job, "Encoder started"),
        )
        self._refresh_table()

        self._thread = export_fn(
            int(job.in_ms),
            int(job.out_ms),
            str(job.out_path),
            progress_cb=self._on_progress,
        )
        if hasattr(self._thread, "finished_error"):
            self._thread.finished_error.connect(self._on_error)
        if hasattr(self._thread, "finished_success"):
            self._thread.finished_success.connect(self._on_success)
        if hasattr(self._thread, "stage"):
            self._thread.stage.connect(self._on_stage)
        if hasattr(self._thread, "finished"):
            self._thread.finished.connect(self._on_done)
        if hasattr(self._thread, "start"):
            self._thread.start()

    def _next_runnable_job(self) -> RenderQueueJob | None:
        self._store.load()
        for job in self._store.jobs:
            if job.status == "pending" and job.id in self._runtime_exports:
                return job
        return None

    def _on_progress(self, pct: int) -> None:
        if not self._current_job_id:
            return
        progress = max(0, min(100, int(pct)))
        self._store.update_progress(self._current_job_id, progress)
        self._refresh_table()

    def _on_stage(self, stage: str) -> None:
        if not self._current_job_id:
            return
        job = self._job_by_id(self._current_job_id)
        self._store.update_progress(
            self._current_job_id,
            int(getattr(job, "progress", 0) if job is not None else 0),
            diagnostics=self._diagnostics_for_job(job, str(stage)),
        )
        self._refresh_table()

    def _on_success(self, out_path, size_bytes: int) -> None:
        try:
            size_mb = float(size_bytes) / (1024.0 * 1024.0)
            self._last_success_note = f"Encoder completed: {Path(out_path).name} ({size_mb:.2f} MB)"
        except Exception:
            self._last_success_note = "Encoder completed"
        try:
            from app.screenstudio_polish import (
                screenstudio_default_export_settings,
                screenstudio_export_completion_summary,
                screenstudio_write_local_share_manifest,
            )

            job_id = self._current_job_id
            settings = self._runtime_project_settings.get(job_id, {})
            defaults = screenstudio_default_export_settings(settings)
            if defaults.get("share_package_ready"):
                screenstudio_write_local_share_manifest(out_path, defaults)
            completion = screenstudio_export_completion_summary(out_path, defaults)
            if completion.get("summary_line"):
                self._last_success_note = (
                    f"{self._last_success_note} | "
                    f"Screen Studio completion: {completion.get('summary_line')}"
                )
            if completion.get("share_manifest_exists"):
                self._last_success_note = (
                    f"{self._last_success_note} | "
                    f"Share manifest: {completion.get('share_manifest_path')}"
                )
        except Exception:
            pass
        try:
            from app.color_management import probe_export_color_metadata

            job_id = self._current_job_id
            settings = self._runtime_project_settings.get(job_id, {})
            report = probe_export_color_metadata(out_path, settings)
            diag = str(report.get("diagnostics") or "")
            if diag:
                self._last_success_note = f"{self._last_success_note} | {diag}"
        except Exception:
            pass

    def _on_error(self, reason: str) -> None:
        job_id = self._current_job_id
        if not job_id:
            return
        canceled = "canceled" in str(reason).lower()
        job = self._job_by_id(job_id)
        try:
            from app.render_diagnostics import format_render_failure_diagnostics

            diagnostics = format_render_failure_diagnostics(reason, job)
        except Exception:
            diagnostics = self._diagnostics_for_job(
                job,
                f"Encoder {'canceled' if canceled else 'failed'}: {reason}",
            )
        item = self._runtime_items.get(job_id)
        if item is not None:
            item.status = "canceled" if canceled else "error"
            item.error = str(reason)
        self._store.update_status(
            job_id,
            "canceled" if canceled else "error",
            error=str(reason),
            diagnostics=diagnostics,
        )
        self._refresh_table()

    def _on_done(self) -> None:
        job_id = self._current_job_id
        if not job_id:
            return
        item = self._runtime_items.get(job_id)
        if item is not None and getattr(item, "status", "") not in {"error", "canceled"}:
            item.status = "done"
            job = self._job_by_id(job_id)
            self._store.update_status(
                job_id,
                "done",
                diagnostics=self._diagnostics_for_job(
                    job,
                    self._last_success_note or "Encoder completed",
                ),
            )
        self._last_success_note = ""
        self._current_job_id = ""
        self._thread = None
        self._refresh_table()
        if not self._paused:
            self._run_next()

    def _refresh_table(self) -> None:
        selected_id = ""
        selected = self._selected_job()
        if selected is not None:
            selected_id = selected.id
        all_jobs = list(self._store.jobs)
        jobs = [job for job in all_jobs if self._job_matches_filter(job)]
        self._table.setRowCount(len(jobs))
        total_progress = 0
        active_jobs = 0
        runnable_jobs = 0
        paused_runtime_jobs = 0
        failed_runtime_jobs = 0
        selected_row = -1
        for job in all_jobs:
            total_progress += int(job.progress)
            is_runtime = job.id in self._runtime_exports
            if is_runtime and job.status in {"pending", "running", "paused"}:
                active_jobs += 1
            if is_runtime and job.status == "pending":
                runnable_jobs += 1
            if is_runtime and job.status == "paused":
                paused_runtime_jobs += 1
            if is_runtime and job.status == "error":
                failed_runtime_jobs += 1
        for row_idx, job in enumerate(jobs):
            status = job.status
            progress_suffix = f" {job.progress}%" if status == "running" else ""
            if job.id == selected_id:
                selected_row = row_idx
            product_diag = render_queue_product_diagnostics(job)
            preflight_summary = render_preflight_card_summary_text(job.diagnostics)
            cells = [
                f"{status}{progress_suffix}",
                job.label,
                _format_range(job.in_ms, job.out_ms),
                Path(job.out_path).name or job.out_path,
                preflight_summary or product_diag.get("summary") or job.diagnostics or job.error,
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, job.id)
                if status == "error":
                    item.setToolTip(job.diagnostics or job.error)
                elif job.diagnostics:
                    item.setToolTip(job.diagnostics)
                self._table.setItem(row_idx, col, item)
        for row_idx in range(self._table.rowCount()):
            self._table.setRowHeight(row_idx, 42)
        if jobs:
            if selected_row < 0:
                selected_row = 0
            self._table.selectRow(selected_row)
        else:
            self._table.clearSelection()
        self._overall.setValue(int(total_progress / max(len(all_jobs), 1)))
        summary = self._store.summary()
        visible_note = (
            f" | showing {len(jobs)}/{len(all_jobs)}"
            if len(jobs) != len(all_jobs)
            else ""
        )
        maintenance_note = (
            f" | {self._last_maintenance_note}"
            if self._last_maintenance_note
            else ""
        )
        self._summary.setText(
            f"{summary.get('total', 0)} jobs | "
            f"{summary.get('running', 0)} running | "
            f"{summary.get('pending', 0)} pending | "
            f"{summary.get('paused', 0)} paused | "
            f"{summary.get('done', 0)} done | "
            f"{summary.get('error', 0)} failed"
            f"{visible_note}"
            f"{maintenance_note}"
        )
        self._run_btn.setEnabled(not self.is_running() and runnable_jobs > 0)
        self._pause_btn.setEnabled(active_jobs > 0 and not self._paused)
        self._resume_btn.setEnabled(paused_runtime_jobs > 0)
        self._cancel_btn.setEnabled(self.is_running() or active_jobs > 0)
        self._retry_btn.setEnabled(not self.is_running() and failed_runtime_jobs > 0)
        selected = self._selected_job()
        self._retry_range_btn.setEnabled(
            not self.is_running()
            and selected is not None
            and selected.status == "error"
            and selected.id in self._runtime_exports
        )
        self._clear_btn.setEnabled(not self.is_running() and summary.get("done", 0) > 0)
        terminal_count = sum(
            1 for job in all_jobs if job.status in {"done", "error", "canceled"}
        )
        self._clear_old_btn.setEnabled(not self.is_running() and terminal_count > 0)
        self._update_detail_panel()
        self.status_changed.emit(summary)

    def _job_matches_filter(self, job: RenderQueueJob) -> bool:
        status_filter = str(self._status_filter.currentData() or "")
        if status_filter and job.status != status_filter:
            return False
        query = self._search_edit.text().strip().lower()
        if not query:
            return True
        haystack = "\n".join([
            job.status,
            job.label,
            job.out_path,
            Path(job.out_path).name,
            job.source_path,
            Path(job.source_path).name if job.source_path else "",
            job.format_id,
            job.quality_id,
            job.error,
            job.diagnostics,
        ]).lower()
        return all(term in haystack for term in query.split())

    def _selected_job(self) -> RenderQueueJob | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        return self._job_by_id(str(item.data(Qt.ItemDataRole.UserRole) or ""))

    def _job_by_id(self, job_id: str) -> RenderQueueJob | None:
        for job in self._store.jobs:
            if job.id == job_id:
                return job
        return None

    def _select_job_id(self, job_id: str) -> None:
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole) or "") == job_id:
                self._table.selectRow(row)
                self._update_detail_panel()
                return

    def _update_detail_panel(self) -> None:
        job = self._selected_job()
        text = self._diagnostics_text_for_job(job)
        self._detail.setPlainText(text)
        self._update_preflight_cards(job)
        self._copy_diag_btn.setText("Copy Diagnostics")
        self._copy_diag_btn.setEnabled(bool(text.strip()))
        self._view_log_btn.setEnabled(bool(text.strip()))
        self._resolve_btn.setEnabled(job is not None and job.status in {"error", "canceled"})
        self._retry_range_btn.setEnabled(
            not self.is_running()
            and job is not None
            and job.status == "error"
            and job.id in self._runtime_exports
        )

    def _update_preflight_cards(self, job: RenderQueueJob | None) -> None:
        self._preflight_card_buttons = []
        while self._preflight_cards_layout.count():
            item = self._preflight_cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        cards = render_preflight_cards_from_text(job.diagnostics if job is not None else "")
        if not cards:
            self._preflight_cards_host.hide()
            return
        compact_labels = {
            "readiness": "Readiness",
            "color_scope": "Color QA",
            "audio_delivery": "Audio QA",
            "audio_warning": "Audio Warn",
            "vfx_graph": "VFX QA",
            "export_parity": "Parity",
        }
        for card in cards[:6]:
            label = compact_labels.get(str(card.get("id") or ""), str(card.get("label") or "Preflight"))
            state = str(card.get("state_label") or "Info")
            button = QPushButton(
                f"{label}  {state}",
                self._preflight_cards_host,
            )
            button.setProperty("preflightCard", "true")
            button.setProperty("preflightState", card.get("state", "info"))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(32)
            button.setMinimumWidth(116)
            button.setToolTip(card.get("detail", "") or card.get("summary", ""))
            captured_card = dict(card)
            button.clicked.connect(lambda _checked=False, c=captured_card, j=job: self._show_preflight_card_detail(c, j))
            self._preflight_card_buttons.append(button)
            self._preflight_cards_layout.addWidget(button, 1)
        self._preflight_cards_layout.addStretch(1)
        self._preflight_cards_host.show()

    def _show_preflight_card_detail(self, card: dict[str, str], job: RenderQueueJob | None) -> None:
        diagnostics = job.diagnostics if job is not None else ""
        text = render_preflight_card_detail_text(card, diagnostics)
        dlg = QDialog(self)
        dlg.setWindowTitle(str(card.get("label") or "Preflight"))
        dlg.resize(560, 420)
        root = QVBoxLayout(dlg)
        root.setContentsMargins(12, 12, 12, 12)
        title = QLabel(str(card.get("label") or "Preflight"), dlg)
        title.setWordWrap(True)
        title.setStyleSheet("font-weight:900;color:#FFFFFF;")
        root.addWidget(title)
        detail = QPlainTextEdit(dlg)
        detail.setReadOnly(True)
        detail.setPlainText(text)
        root.addWidget(detail, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dlg)
        for spec in render_preflight_card_action_specs(card):
            action_btn = QPushButton(str(spec.get("label") or "Action"), dlg)
            action_id = str(spec.get("id") or "")
            buttons.addButton(action_btn, QDialogButtonBox.ButtonRole.ActionRole)
            action_btn.clicked.connect(
                lambda _checked=False, aid=action_id, d=dlg: (
                    self._run_preflight_card_action(aid, job),
                    d.accept(),
                )
            )
        copy_btn = QPushButton("Copy", dlg)
        buttons.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(detail.toPlainText()))
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)
        dlg.exec()

    def _parent_slot(self, name: str):
        parent = self.window()
        slot = getattr(parent, name, None)
        return slot if callable(slot) else None

    def _run_preflight_card_action(self, action_id: str, job: RenderQueueJob | None = None) -> bool:
        action_id = str(action_id or "")
        if action_id == "health":
            slot = self._parent_slot("_show_media_health") or self._parent_slot("_open_health_center")
            if slot:
                slot()
                return True
        elif action_id == "qa_dashboard":
            slot = self._parent_slot("_open_qa_dashboard")
            if slot:
                slot()
                return True
        elif action_id == "color_page":
            slot = self._parent_slot("_open_color_page")
            if slot:
                slot()
                return True
        elif action_id == "audio_mixer":
            slot = self._parent_slot("_on_audio_mixer_toggled")
            if slot:
                slot(True)
                return True
        elif action_id == "preset_qa":
            slot = self._parent_slot("_show_preset_application_corpus_report")
            if slot:
                slot()
                return True
        elif action_id == "deliver_presets":
            self.show_deliver_presets()
            return True
        elif action_id == "relink":
            slot = self._parent_slot("_on_relink_project_media")
            if slot:
                slot()
                return True
        QMessageBox.information(
            self,
            "Render Queue",
            "This action is available from the main editor for the current project.",
        )
        return False

    def copy_selected_diagnostics(self) -> None:
        text = self._diagnostics_text_for_job(self._selected_job())
        if not text.strip():
            return
        QApplication.clipboard().setText(text)
        self._copy_diag_btn.setText("Copied")

    def show_selected_log(self) -> None:
        job = self._selected_job()
        text = self._diagnostics_text_for_job(job)
        if not text.strip():
            return
        dlg = QDialog(self)
        title = f"Render Log - {job.label if job is not None else 'Job'}"
        dlg.setWindowTitle(title)
        dlg.resize(760, 520)
        root = QVBoxLayout(dlg)
        root.setContentsMargins(10, 10, 10, 10)
        edit = QPlainTextEdit()
        edit.setReadOnly(True)
        edit.setPlainText(text)
        root.addWidget(edit, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_btn = QPushButton("Copy")
        save_btn = QPushButton("Save Log")
        buttons.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(save_btn, QDialogButtonBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(edit.toPlainText()))
        save_btn.clicked.connect(lambda: self._save_log_text(edit.toPlainText(), job))
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)
        dlg.exec()

    def _save_log_text(self, text: str, job: RenderQueueJob | None) -> Path | None:
        if not text.strip():
            return None
        default_name = f"render_{getattr(job, 'id', 'job')}.log"
        try:
            base = Path.home() / "Videos" / "TigerCapture" / ".cache" / "render_logs"
            base.mkdir(parents=True, exist_ok=True)
        except Exception:
            base = Path.cwd()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Render Log",
            str(base / default_name),
            "Log files (*.log);;Text files (*.txt);;All files (*.*)",
        )
        if not path:
            return None
        out = Path(path)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            return out
        except Exception as exc:
            QMessageBox.warning(self, "Render Queue", f"Could not save log: {exc}")
            return None

    def show_failure_wizard(self) -> None:
        job = self._selected_job()
        if job is None:
            return
        diag = render_queue_product_diagnostics(job)
        dlg = QDialog(self)
        dlg.setWindowTitle("Render Failure Assistant")
        dlg.resize(680, 420)
        root = QVBoxLayout(dlg)
        root.setContentsMargins(12, 12, 12, 12)
        summary = QLabel(str(diag.get("summary") or "Render job needs attention."))
        summary.setWordWrap(True)
        summary.setStyleSheet("font-weight:900;color:#FFFFFF;")
        root.addWidget(summary)
        detail = QPlainTextEdit()
        detail.setReadOnly(True)
        detail.setPlainText(self._diagnostics_text_for_job(job))
        root.addWidget(detail, 1)
        buttons = QDialogButtonBox()
        relink_btn = QPushButton("Open Relink")
        preset_qa_btn = QPushButton("Run Preset QA")
        retry_range_btn = QPushButton("Retry 5s Range")
        copy_btn = QPushButton("Copy")
        save_btn = QPushButton("Save Log")
        close_btn = QPushButton("Close")
        for btn in (relink_btn, preset_qa_btn, retry_range_btn, copy_btn, save_btn):
            buttons.addButton(btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)
        root.addWidget(buttons)

        relink_btn.clicked.connect(lambda: (self._parent_slot("_on_relink_project_media") or (lambda: QMessageBox.information(self, "Relink", "Relink is available from Project > Relink Media.")))())
        preset_qa_btn.clicked.connect(lambda: (self._parent_slot("_show_preset_application_corpus_report") or (lambda: QMessageBox.information(self, "Preset QA", "Open QA Dashboard or run preset application corpus QA.")))())
        retry_range_btn.clicked.connect(lambda: (self.queue_selected_retry_range(), dlg.accept()))
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(detail.toPlainText()))
        save_btn.clicked.connect(lambda: self._save_log_text(detail.toPlainText(), job))
        close_btn.clicked.connect(dlg.reject)
        dlg.exec()

    def deliver_jobs_payload(self, profile_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """Return Deliver-page preset jobs available to this queue panel."""
        from app.professional_workflow_payloads import build_deliver_jobs_payload

        return build_deliver_jobs_payload(profile_ids)

    def deliver_preset_summary_text(self, profile_ids: list[str] | None = None) -> str:
        """Compact Deliver-page preset summary for QA/status surfaces."""
        jobs = self.deliver_jobs_payload(profile_ids)
        if not jobs:
            return "Deliver presets: none"
        formats = sorted({str(job.get("format_id") or "") for job in jobs if job.get("format_id")})
        colors = sorted({str(job.get("color_space") or "") for job in jobs if job.get("color_space")})
        hdr = sum(1 for job in jobs if "PQ" in str(job.get("color_space") or "").upper() or "HLG" in str(job.get("color_space") or "").upper())
        return (
            f"Deliver presets: {len(jobs)} job(s) | "
            f"{'/'.join(formats) or 'format n/a'} | "
            f"HDR {hdr} | {', '.join(colors[:3])}"
        )

    def audio_delivery_preflight_text(
        self,
        audio_tracks: list[Any] | None = None,
        *,
        measured: dict[str, Any] | None = None,
        target: str = "shortform",
    ) -> str:
        return audio_delivery_preflight_text_for_tracks(
            audio_tracks,
            measured=measured,
            target=target,
        )

    def show_deliver_presets(self) -> None:
        """Show the current Deliver-page preset matrix for batch export planning."""
        jobs = self.deliver_jobs_payload()
        dlg = QDialog(self)
        dlg.setWindowTitle("Deliver Presets")
        dlg.resize(720, 420)
        root = QVBoxLayout(dlg)
        root.setContentsMargins(12, 12, 12, 12)
        title = QLabel("Deliver Page Preset Matrix")
        title.setStyleSheet("font-weight:900;color:#FFFFFF;")
        root.addWidget(title)
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(["ID", "Format", "Resolution", "FPS", "Color", "Audio", "Bitrate"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for job in jobs:
            row = table.rowCount()
            table.insertRow(row)
            resolution = job.get("resolution", [])
            if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
                res_text = f"{resolution[0]}x{resolution[1]}"
            else:
                res_text = "-"
            values = [
                job.get("id", ""),
                job.get("format_id", ""),
                res_text,
                job.get("fps", ""),
                job.get("color_space", ""),
                job.get("audio_layout", ""),
                job.get("bitrate_mbps", ""),
            ]
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(str(value)))
        root.addWidget(table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_btn = QPushButton("Copy JSON")
        buttons.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(json.dumps(jobs, ensure_ascii=False, indent=2, default=str)))
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)
        dlg.exec()

    @staticmethod
    def _diagnostics_text_for_job(job: RenderQueueJob | None) -> str:
        if job is None:
            return ""
        lines = [
            "Render Queue Diagnostics",
            "",
            f"Status: {job.status}",
            f"Job: {job.label}",
            f"Range: {_format_range(job.in_ms, job.out_ms)}",
        ]
        if job.out_path:
            lines.append(f"Output: {job.out_path}")
        if job.source_path:
            lines.append(f"Source: {job.source_path}")
        if job.format_id:
            lines.append(f"Format: {job.format_id}")
        if job.quality_id:
            lines.append(f"Quality: {job.quality_id}")
        if job.progress:
            lines.append(f"Progress: {job.progress}%")
        product_diag = render_queue_product_diagnostics(job)
        if product_diag.get("summary"):
            lines.extend(["", "Product Diagnosis:", str(product_diag.get("summary"))])
        completion = product_diag.get("completion")
        if isinstance(completion, dict) and completion:
            lines.extend(["", "Export Completion:"])
            lines.append(f"Status: {completion.get('status')}")
            if completion.get("summary_line"):
                lines.append(f"Summary: {completion.get('summary_line')}")
            if completion.get("share_manifest_path"):
                lines.append(f"Share Manifest: {completion.get('share_manifest_path')}")
            action_labels = [str(v) for v in completion.get("action_labels", []) or []]
            if action_labels:
                lines.append(f"Actions: {', '.join(action_labels)}")
        actions = [str(action) for action in product_diag.get("actions", []) or []]
        if actions:
            lines.extend(["", "Suggested Actions:"])
            lines.extend(f"- {action}" for action in actions)
        if product_diag.get("parity"):
            lines.append(f"Preset/Template Export Parity: {product_diag.get('parity')}")
        if job.error:
            lines.extend(["", "Error:", job.error])
        if job.diagnostics and job.diagnostics != job.error:
            lines.extend(["", "Diagnostics:", job.diagnostics])
        if job.started_at:
            lines.append(f"Started: {job.started_at}")
        if job.finished_at:
            lines.append(f"Finished: {job.finished_at}")
        return "\n".join(lines)

    def _diagnostics_for_job(self, job: RenderQueueJob | None, state: str) -> str:
        if job is None:
            return state
        pieces = [state]
        if job.format_id:
            pieces.append(f"format={job.format_id}")
        if job.quality_id:
            pieces.append(f"quality={job.quality_id}")
        if job.source_path:
            pieces.append(f"source={Path(job.source_path).name}")
        base = " | ".join(pieces)
        preflight = ""
        try:
            preflight = str(self._runtime_preflight_diagnostics.get(job.id, "") or "")
        except Exception:
            preflight = ""
        if preflight:
            return f"{base}\n\n{preflight}"
        return base

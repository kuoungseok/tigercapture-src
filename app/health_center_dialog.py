"""Unified diagnostic center for long editing sessions."""
from __future__ import annotations

import json
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
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _status(ok: bool, title: str, summary: str, details: list[str] | None = None) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "title": title,
        "summary": summary,
        "details": details or [],
    }


def build_health_center_report(editor: Any | None = None) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []

    try:
        from app.crash_reporter import load_crash_report, latest_crash_report_path

        crash = load_crash_report()
        exc = crash.get("exception", {}) if isinstance(crash, dict) else {}
        autosave = crash.get("emergency_autosave", {}) if isinstance(crash, dict) else {}
        sections.append(_status(
            not bool(exc),
            "Crash Report",
            f"{exc.get('type', 'No crash')}: {exc.get('message', '')}" if exc else "No recent crash report.",
            [
                f"Report: {latest_crash_report_path()}",
                f"Emergency autosave: {autosave.get('path', '') if isinstance(autosave, dict) else ''}",
                f"Recent actions: {len(crash.get('recent_actions', []) or []) if isinstance(crash, dict) else 0}",
            ],
        ))
    except Exception as exc:
        sections.append(_status(False, "Crash Report", f"Unavailable: {exc!r}"))

    try:
        from app.qa_dashboard import build_qa_dashboard_rows

        qa_rows = build_qa_dashboard_rows()
        existing = sum(1 for row in qa_rows if row.get("exists"))
        failing = [row for row in qa_rows if row.get("exists") and not row.get("ok")]
        sections.append(_status(
            not failing,
            "QA Dashboard",
            f"{existing}/{len(qa_rows)} reports available, {len(failing)} need attention.",
            [f"- {row.get('label')}: {row.get('summary')}" for row in failing[:8]],
        ))
    except Exception as exc:
        sections.append(_status(False, "QA Dashboard", f"Unavailable: {exc!r}"))

    try:
        from app.render_queue import RenderQueueStore

        store = RenderQueueStore()
        summary = store.summary()
        failed = int(summary.get("error", 0) or 0)
        sections.append(_status(
            failed == 0,
            "Render Queue",
            ", ".join(f"{key}={value}" for key, value in sorted(summary.items())),
            [
                f"- {job.label}: {job.status} {job.error or job.diagnostics}"
                for job in store.jobs
                if job.status in {"error", "canceled"}
            ][:8],
        ))
    except Exception as exc:
        sections.append(_status(False, "Render Queue", f"Unavailable: {exc!r}"))

    if editor is not None:
        try:
            from app.media_health_dialog import (
                build_editor_media_health_doc,
                professional_readiness_detail_lines,
                professional_readiness_summary_text,
                suggest_media_health_roots,
            )
            from app.media_relink import build_media_health_report

            doc = build_editor_media_health_doc(editor)
            roots = suggest_media_health_roots(doc, getattr(editor, "_project_path", None))
            media_report = build_media_health_report(doc, roots)
            counts = media_report.get("status_counts", {}) or {}
            missing = int(counts.get("missing", 0) or 0)
            stale = int(counts.get("proxy_stale", 0) or 0)
            sections.append(_status(
                missing == 0 and stale == 0,
                "Media / Proxy",
                " | ".join(f"{key}:{value}" for key, value in sorted(counts.items())) or "No media references.",
                [
                    f"- {row.get('filename', Path(str(row.get('path', ''))).name)}: {row.get('status')}"
                    for row in media_report.get("rows", [])[:8]
                    if row.get("status") != "ok"
                ],
            ))
            try:
                from app.professional_readiness import build_professional_readiness_report

                readiness = build_professional_readiness_report(doc)
                readiness_report = {"professional_readiness": readiness}
                sections.append(_status(
                    bool(readiness.get("ok", False)),
                    "Professional Readiness",
                    professional_readiness_summary_text(readiness_report) or f"score {int(readiness.get('score', 0) or 0)}",
                    professional_readiness_detail_lines(readiness_report),
                ))
            except Exception as exc:
                sections.append(_status(False, "Professional Readiness", f"Unavailable: {exc!r}"))
        except Exception as exc:
            sections.append(_status(False, "Media / Proxy", f"Unavailable: {exc!r}"))
    else:
        sections.append(_status(True, "Media / Proxy", "Open from the editor to inspect current project media."))

    try:
        from app.actor_qa_status import load_actor_qa_status

        actor_status = load_actor_qa_status()
        models = list(actor_status.get("models", []) or []) if isinstance(actor_status, dict) else []
        risky = [
            row for row in models
            if isinstance(row, dict) and str(row.get("status", "")).lower() not in {"", "pass"}
        ]
        sections.append(_status(
            not risky,
            "Live2D / Spine QA",
            f"{len(models)} models indexed, {len(risky)} risk/fail/quarantine rows.",
            [f"- {row.get('model_name', row.get('path', 'model'))}: {row.get('status')}" for row in risky[:8]],
        ))
    except Exception as exc:
        sections.append(_status(False, "Live2D / Spine QA", f"Unavailable: {exc!r}"))

    ok_count = sum(1 for section in sections if section.get("ok"))
    return {
        "ok": ok_count == len(sections),
        "summary": {
            "sections": len(sections),
            "ok": ok_count,
            "attention": len(sections) - ok_count,
        },
        "sections": sections,
    }


class HealthCenterDialog(QDialog):
    def __init__(self, editor=None) -> None:
        super().__init__(editor)
        self.setWindowTitle("Health Center")
        self.resize(920, 600)
        self._editor = editor
        self._report: dict[str, Any] = {}

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
        self._qa_btn = QPushButton("Open QA Dashboard")
        self._crash_btn = QPushButton("Open Crash Report")
        close_btn = QPushButton("Close")
        buttons.addButton(self._refresh_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._qa_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._crash_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(close_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(buttons)

        self._refresh_btn.clicked.connect(self.refresh)
        self._qa_btn.clicked.connect(lambda: getattr(self._editor, "_open_qa_dashboard", lambda: None)())
        self._crash_btn.clicked.connect(lambda: getattr(self._editor, "_open_crash_report", lambda: None)())
        close_btn.clicked.connect(self.accept)
        self._list.itemSelectionChanged.connect(self._refresh_detail)
        self.refresh()

    def refresh(self) -> None:
        self._report = build_health_center_report(self._editor)
        sections = list(self._report.get("sections", []) or [])
        summary = self._report.get("summary", {}) or {}
        self._summary.setText(
            f"Health Center: {summary.get('ok', 0)}/{summary.get('sections', 0)} OK, "
            f"{summary.get('attention', 0)} need attention."
        )
        self._list.clear()
        for idx, section in enumerate(sections):
            prefix = "OK" if section.get("ok") else "ATTN"
            item = QListWidgetItem(f"[{prefix}] {section.get('title')}  {section.get('summary')}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        item = self._list.currentItem()
        sections = list(self._report.get("sections", []) or [])
        if item is None:
            self._detail.setPlainText("")
            return
        try:
            section = sections[int(item.data(Qt.ItemDataRole.UserRole))]
        except Exception:
            self._detail.setPlainText("")
            return
        lines = [
            str(section.get("title", "")),
            f"Status: {'OK' if section.get('ok') else 'Needs attention'}",
            str(section.get("summary", "")),
            "",
        ]
        lines.extend(str(line) for line in section.get("details", []) or [])
        self._detail.setPlainText("\n".join(lines))

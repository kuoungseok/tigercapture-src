"""Crash report viewer shown inside the editor after a failed session."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.crash_reporter import (
    export_repro_bundle,
    has_unseen_crash_report,
    latest_crash_report_path,
    load_crash_report,
    mark_crash_report_seen,
    repro_steps_from_report,
)


def crash_report_user_summary(report: dict, report_path: str | Path | None = None) -> dict[str, object]:
    """Return a friendly, UI-ready summary for crash/recovery dialogs."""
    data = report if isinstance(report, dict) else {}
    exc = data.get("exception", {}) if isinstance(data, dict) else {}
    exc = exc if isinstance(exc, dict) else {}
    autosave = data.get("emergency_autosave", {}) if isinstance(data, dict) else {}
    autosave = autosave if isinstance(autosave, dict) else {}
    autosave_path = Path(str(autosave.get("path") or "")) if autosave.get("path") else None
    actor_context = data.get("actor_context", {}) if isinstance(data, dict) else {}
    actor_related = bool(isinstance(actor_context, dict) and actor_context.get("actor_related"))
    recent_actions = list(data.get("recent_actions", []) or []) if isinstance(data, dict) else []
    headline = "이전 세션이 비정상 종료되었습니다" if exc else "크래시 리포트가 없습니다"
    exception_text = f"{exc.get('type', 'Exception')}: {exc.get('message', '')}" if exc else "No crash report"
    actions: list[str] = []
    if autosave_path is not None and autosave_path.exists():
        actions.append("Open Emergency Autosave")
    actions.append("Export Repro")
    actions.append("Copy Summary")
    if actor_related:
        actions.append("Review Live2D/Spine loading context")
    return {
        "headline": headline,
        "exception": exception_text,
        "report_path": str(report_path or ""),
        "autosave_path": str(autosave_path or ""),
        "autosave_ready": bool(autosave_path is not None and autosave_path.exists()),
        "actor_related": actor_related,
        "recent_action_count": len(recent_actions),
        "recommended_actions": actions,
        "plain_text": (
            f"{headline}\n"
            f"Reason: {exception_text}\n"
            f"Autosave: {autosave_path or 'not available'}\n"
            f"Next: {', '.join(actions)}"
        ),
    }


class CrashReportDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        report_path: str | Path | None = None,
        open_project_callback: Callable[[Path], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Crash Report")
        self.resize(860, 620)
        self._report_path = Path(report_path) if report_path is not None else latest_crash_report_path()
        self._report = load_crash_report(self._report_path)
        self._user_summary = crash_report_user_summary(self._report, self._report_path)
        self._open_project_callback = open_project_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self._summary = QLabel(self._summary_text())
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        action_row = QHBoxLayout()
        self._open_autosave_btn = QPushButton("Open Emergency Autosave")
        self._export_repro_btn = QPushButton("Export Repro")
        self._copy_btn = QPushButton("Copy Summary")
        self._open_logs_btn = QPushButton("Open Logs")
        action_row.addWidget(self._open_autosave_btn)
        action_row.addWidget(self._export_repro_btn)
        action_row.addWidget(self._copy_btn)
        action_row.addWidget(self._open_logs_btn)
        action_row.addStretch(1)
        root.addLayout(action_row)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setPlainText(self._detail_text())
        root.addWidget(self._detail, 1)

        buttons = QDialogButtonBox()
        close_btn = QPushButton("Dismiss")
        buttons.addButton(close_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(buttons)

        self._open_autosave_btn.clicked.connect(self._open_autosave)
        self._export_repro_btn.clicked.connect(self._export_repro)
        self._copy_btn.clicked.connect(self._copy_summary)
        self._open_logs_btn.clicked.connect(self._open_logs)
        close_btn.clicked.connect(self.accept)

        autosave = self._autosave_path()
        self._open_autosave_btn.setEnabled(autosave is not None and autosave.exists())

    def _exception_text(self) -> str:
        exc = self._report.get("exception", {}) if isinstance(self._report, dict) else {}
        if not isinstance(exc, dict) or not exc:
            return "No crash report found."
        return f"{exc.get('type', 'Exception')}: {exc.get('message', '')}"

    def _autosave_path(self) -> Path | None:
        autosave = self._report.get("emergency_autosave", {}) if isinstance(self._report, dict) else {}
        if not isinstance(autosave, dict):
            return None
        text = str(autosave.get("path") or "")
        return Path(text) if text else None

    def _summary_text(self) -> str:
        friendly = dict(getattr(self, "_user_summary", {}) or {})
        autosave = self._autosave_path()
        autosave_text = str(autosave) if autosave is not None else "No emergency autosave"
        actor_text = ""
        actor_context = self._report.get("actor_context", {}) if isinstance(self._report, dict) else {}
        if isinstance(actor_context, dict) and actor_context.get("actor_related"):
            latest = actor_context.get("latest_load") or actor_context.get("latest_open") or actor_context.get("latest_drop") or {}
            data = latest.get("data", {}) if isinstance(latest, dict) else {}
            if isinstance(data, dict):
                actor_text = (
                    f"\nActor context: {latest.get('event', '-') if isinstance(latest, dict) else '-'} "
                    f"{data.get('stage', '')} {data.get('path') or data.get('model_path') or data.get('skel_path') or ''}"
                )
        return (
            f"{friendly.get('headline', 'Latest crash')}\n"
            f"Latest crash: {self._exception_text()}\n"
            f"Report: {self._report_path}\n"
            f"Emergency autosave: {autosave_text}\n"
            f"Recommended: {', '.join(str(item) for item in friendly.get('recommended_actions', []) or [])}"
            f"{actor_text}"
        )

    def _detail_text(self) -> str:
        if not self._report:
            return f"No crash report file was found at {self._report_path}"
        lines = [self._summary_text(), "", "Repro steps:"]
        steps = repro_steps_from_report(self._report)
        lines.extend(f"{idx + 1}. {step}" for idx, step in enumerate(steps or ["No recent action breadcrumbs."]))
        actor_context = self._report.get("actor_context", {}) if isinstance(self._report, dict) else {}
        if isinstance(actor_context, dict) and actor_context.get("actor_related"):
            lines.extend(["", "Actor context:", json.dumps(actor_context, ensure_ascii=False, indent=2, default=str)])
        lines.extend(["", "Recent actions:"])
        for row in list(self._report.get("recent_actions", []) or [])[-40:]:
            lines.append(json.dumps(row, ensure_ascii=False, default=str))
        lines.extend(["", "Traceback:", str(self._report.get("traceback", ""))])
        return "\n".join(lines)

    def _open_autosave(self) -> None:
        autosave = self._autosave_path()
        if autosave is None or not autosave.exists():
            QMessageBox.information(self, "Crash Report", "No readable emergency autosave is available.")
            return
        if self._open_project_callback is not None:
            self._open_project_callback(autosave)
            mark_crash_report_seen(self._report_path)
            self.accept()

    def _export_repro(self) -> None:
        out = export_repro_bundle(self._report_path)
        if out is None:
            QMessageBox.warning(self, "Crash Report", "Could not export a repro bundle.")
            return
        QMessageBox.information(self, "Crash Report", f"Repro bundle written:\n{out}")

    def _copy_summary(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._detail.toPlainText())

    def _open_logs(self) -> None:
        folder = self._report_path.parent
        try:
            os.startfile(str(folder))
        except Exception:
            pass

    def accept(self) -> None:  # type: ignore[override]
        mark_crash_report_seen(self._report_path)
        super().accept()


def show_startup_crash_report_if_needed(parent, open_project_callback=None) -> bool:
    if not has_unseen_crash_report():
        return False
    dlg = CrashReportDialog(parent, open_project_callback=open_project_callback)
    dlg.exec()
    return True

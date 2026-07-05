"""Recovery candidate browser for autosave and crash-recovery projects."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)


def _format_mtime(value: Any) -> str:
    try:
        stamp = float(value or 0.0)
        if stamp <= 0:
            return ""
        return datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _format_size(value: Any) -> str:
    try:
        size = float(value or 0)
    except Exception:
        return ""
    units = ("B", "KB", "MB", "GB")
    unit = units[0]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            break
        size /= 1024.0
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.1f} {unit}"


def _status_label(row: dict[str, Any], health: dict[str, Any]) -> str:
    if not row.get("readable"):
        return "Broken"
    level = str(health.get("level") or "")
    return {
        "open_safe": "Ready",
        "needs_relink": "Needs Relink",
        "actor_assets_need_review": "Actor Check",
        "repair_recommended": "Repair",
        "unreadable": "Broken",
        "none": "Missing",
    }.get(level, "Readable" if row.get("readable") else "Broken")


def _user_action_label(row: dict[str, Any], health: dict[str, Any]) -> str:
    if not row.get("readable"):
        return "Skip broken file"
    level = str(health.get("level") or "")
    return {
        "open_safe": "Open this recovery",
        "needs_relink": "Open and relink missing media",
        "actor_assets_need_review": "Open and review actor assets",
        "repair_recommended": "Open repaired copy",
        "unreadable": "Skip broken file",
        "none": "Find another autosave",
    }.get(level, str(health.get("recommended_action") or "Open candidate"))


def recovery_candidate_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize repair-tool output into rows for UI and tests."""
    product = report.get("product_summary", {}) or {}
    source_rows = list(product.get("candidates", []) or report.get("candidates", []) or [])
    rows: list[dict[str, Any]] = []
    for index, source in enumerate(source_rows):
        row = dict(source)
        health = dict(row.get("health", {}) or {})
        path = str(row.get("path", "") or "")
        rows.append({
            "index": index,
            "path": path,
            "filename": Path(path).name if path else "",
            "readable": bool(row.get("readable")),
            "ok": bool(row.get("ok")),
            "status_label": _status_label(row, health),
            "health_level": str(health.get("level", "") or ""),
            "score": int(health.get("score", 0) or 0),
            "missing_count": int(row.get("missing_count", 0) or 0),
            "missing_by_kind": dict(row.get("missing_by_kind", {}) or {}),
            "missing_preview": list(row.get("missing_preview", []) or []),
            "changes_count": int(row.get("changes_count", 0) or 0),
            "changes_preview": [str(item) for item in row.get("changes_preview", []) or []],
            "actor_assets_ok": bool(row.get("actor_assets_ok", True)),
            "actor_failed_count": int(row.get("actor_failed_count", 0) or 0),
            "actor_failures_preview": list(row.get("actor_failures_preview", []) or []),
            "guidance_actions": [str(item) for item in row.get("guidance_actions", []) or []],
            "mtime_text": _format_mtime(row.get("mtime")),
            "size_text": _format_size(row.get("size")),
            "recommended_action": str(health.get("recommended_action", "") or ""),
            "user_action_label": _user_action_label(row, health),
            "reason": str(health.get("reason", "") or row.get("error", "") or ""),
            "error": str(row.get("error", "") or ""),
            "raw": row,
        })
    return rows


class RecoveryCandidatesDialog(QDialog):
    """Table-based recovery picker with health details."""

    def __init__(self, report: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recovery")
        self.setMinimumSize(980, 560)
        self._report = report
        self._rows = recovery_candidate_rows(report)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        product = report.get("product_summary", {}) or {}
        message = str(product.get("message") or "Choose a recovery candidate to open.")
        self._summary = QLabel(f"{message}  |  candidates {len(self._rows)}")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "Status",
            "Score",
            "Missing",
            "Changes",
            "Modified",
            "Size",
            "Path",
        ])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.itemDoubleClicked.connect(lambda _item: self._accept_if_readable())
        self._table.itemSelectionChanged.connect(self._refresh_detail)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self._table, 1)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMinimumHeight(118)
        root.addWidget(self._detail)

        buttons = QDialogButtonBox()
        self._open_btn = QPushButton("Open Selected")
        self._open_btn.clicked.connect(self._accept_if_readable)
        buttons.addButton(self._open_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        close_btn = QPushButton("Cancel")
        close_btn.clicked.connect(self.reject)
        buttons.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)
        root.addWidget(buttons)

        self._populate()

    def selected_candidate(self) -> dict[str, Any] | None:
        row_idx = self._selected_row_index()
        if row_idx is None or not (0 <= row_idx < len(self._rows)):
            return None
        return dict(self._rows[row_idx]["raw"])

    def _selected_row_index(self) -> int | None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return None
        return int(selected[0].row())

    def _populate(self) -> None:
        self._table.setRowCount(len(self._rows))
        for row_idx, row in enumerate(self._rows):
            values = [
                row["status_label"],
                str(row["score"]),
                str(row["missing_count"]),
                str(row["changes_count"]),
                row["mtime_text"],
                row["size_text"],
                row["path"],
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, row_idx)
                if col in (1, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._apply_item_color(item, row)
                self._table.setItem(row_idx, col, item)
        if self._rows:
            self._table.selectRow(0)
        self._table.resizeRowsToContents()
        self._refresh_detail()

    def _apply_item_color(self, item: QTableWidgetItem, row: dict[str, Any]) -> None:
        status = row.get("health_level") or row.get("status_label")
        color = {
            "open_safe": "#6ecf80",
            "needs_relink": "#d8a030",
            "actor_assets_need_review": "#d8a030",
            "repair_recommended": "#7ab8ff",
            "unreadable": "#d35f5f",
            "Broken": "#d35f5f",
        }.get(str(status), "")
        if color:
            item.setForeground(QColor(color))

    def _refresh_detail(self) -> None:
        row_idx = self._selected_row_index()
        if row_idx is None or not (0 <= row_idx < len(self._rows)):
            self._detail.setPlainText("No recovery candidate selected.")
            self._open_btn.setEnabled(False)
            return
        row = self._rows[row_idx]
        self._open_btn.setEnabled(bool(row.get("readable")))
        actor_state = "OK" if row.get("actor_assets_ok") else "Needs review"
        lines = [
            f"Status: {row['status_label']}  |  Score: {row['score']}",
            f"Missing media/model paths: {row['missing_count']}  |  Schema changes: {row['changes_count']}  |  Actor assets: {actor_state}",
            f"User action: {row.get('user_action_label') or '-'}",
            f"Recommended action: {row['recommended_action'] or '-'}",
            f"Reason: {row['reason'] or '-'}",
            f"Path: {row['path']}",
        ]
        if row.get("error"):
            lines.append(f"Error: {row['error']}")
        guidance_actions = row.get("guidance_actions") or []
        if guidance_actions:
            lines.append("")
            lines.append("Suggested steps:")
            lines.extend(f"- {action}" for action in guidance_actions)
        missing_by_kind = row.get("missing_by_kind") or {}
        if missing_by_kind:
            parts = [
                f"{kind} {count}"
                for kind, count in sorted(missing_by_kind.items())
                if int(count or 0) > 0
            ]
            if parts:
                lines.append("")
                lines.append(f"Missing by kind: {', '.join(parts)}")
        missing_preview = row.get("missing_preview") or []
        if missing_preview:
            lines.append("")
            lines.append("Missing path preview:")
            for item in missing_preview:
                if not isinstance(item, dict):
                    continue
                kind = str(item.get("kind") or "path")
                path = str(item.get("path") or "")
                lines.append(f"- [{kind}] {path}")
        changes_preview = row.get("changes_preview") or []
        if changes_preview:
            lines.append("")
            lines.append("Schema repair preview:")
            lines.extend(f"- {change}" for change in changes_preview)
        actor_failures = row.get("actor_failures_preview") or []
        if actor_failures:
            lines.append("")
            lines.append("Actor asset preview:")
            for item in actor_failures:
                if not isinstance(item, dict):
                    continue
                kind = str(item.get("kind") or "actor")
                track = item.get("track_id")
                clip = item.get("clip_index")
                path = str(item.get("path") or "")
                issues = ", ".join(str(issue) for issue in item.get("issues", []) or [])
                scope = f"track {track} clip {clip}"
                if issues and path:
                    lines.append(f"- {kind} {scope}: {issues} ({path})")
                elif issues:
                    lines.append(f"- {kind} {scope}: {issues}")
                elif path:
                    lines.append(f"- {kind} {scope}: {path}")
        self._detail.setPlainText("\n".join(lines))

    def _accept_if_readable(self) -> None:
        row_idx = self._selected_row_index()
        if row_idx is None or not (0 <= row_idx < len(self._rows)):
            return
        if not self._rows[row_idx].get("readable"):
            self._refresh_detail()
            return
        self.accept()

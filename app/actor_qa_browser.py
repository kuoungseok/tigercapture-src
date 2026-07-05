"""Small browser for Live2D/Spine compatibility status artifacts."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
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

from app.actor_qa_status import actor_status_detail_lines, load_actor_qa_status


def _image_candidates(row: dict[str, Any]) -> tuple[Path | None, Path | None]:
    """Best-effort baseline/actual image discovery from actor QA rows."""
    baseline: Path | None = None
    actual: Path | None = None

    def _consider(value: Any, target: str) -> None:
        nonlocal baseline, actual
        if isinstance(value, dict):
            for key, child in value.items():
                key_l = str(key).casefold()
                next_target = target
                if any(word in key_l for word in ("baseline", "golden", "expected")):
                    next_target = "baseline"
                elif any(word in key_l for word in ("actual", "render", "preview")):
                    next_target = "actual"
                _consider(child, next_target)
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                _consider(child, target)
            return
        if not isinstance(value, str):
            return
        path = Path(value)
        if path.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".webp"}:
            return
        if not path.exists():
            return
        if target == "baseline" and baseline is None:
            baseline = path
        elif target == "actual" and actual is None:
            actual = path

    _consider(row, "")
    return baseline, actual


class ActorQABrowserDialog(QDialog):
    """Model-level pass/fail browser for actor corpus QA."""

    def __init__(self, parent=None, *, status_path: Path | str | None = None) -> None:
        super().__init__(parent)
        self._status_path = Path(status_path or "debugCapture/actor_corpus_status.json")
        self._rows: list[dict[str, Any]] = []
        self.setWindowTitle("Live2D / Spine Compatibility")
        self.resize(860, 560)

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

        preview_row = QHBoxLayout()
        self._baseline_preview = QLabel("Baseline")
        self._actual_preview = QLabel("Actual")
        for label in (self._baseline_preview, self._actual_preview):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(148)
            label.setStyleSheet("background:#0B0D16;border:1px solid #30384F;border-radius:12px;color:#A7ADC2;")
            preview_row.addWidget(label)
        root.addLayout(preview_row)

        buttons = QDialogButtonBox()
        refresh_btn = QPushButton("Refresh")
        open_btn = QPushButton("Open Report Folder")
        close_btn = QPushButton("Close")
        refresh_btn.clicked.connect(self.refresh)
        open_btn.clicked.connect(self._open_folder)
        close_btn.clicked.connect(self.accept)
        buttons.addButton(refresh_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(open_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(close_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(buttons)

        self._list.itemSelectionChanged.connect(self._refresh_detail)
        self.refresh()

    def refresh(self) -> None:
        payload = load_actor_qa_status(self._status_path)
        rows = [row for row in payload.get("models", []) or [] if isinstance(row, dict)]
        self._rows = rows
        self._list.clear()
        counts: dict[str, int] = {}
        for idx, row in enumerate(rows):
            status = str(row.get("status") or "unknown")
            kind = str(row.get("kind") or "actor")
            name = Path(str(row.get("path") or row.get("model_name") or "model")).name
            counts[status] = counts.get(status, 0) + 1
            item = QListWidgetItem(f"[{status.upper()}] {kind}  {name}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setToolTip(str(row.get("path") or ""))
            self._list.addItem(item)
        if not rows:
            self._list.addItem("No actor corpus status found")
        summary_bits = ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "no models"
        self._summary.setText(f"Status file: {self._status_path} | {summary_bits}")
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._refresh_detail()

    def _selected_row(self) -> dict[str, Any] | None:
        item = self._list.currentItem()
        if item is None:
            return None
        try:
            return self._rows[int(item.data(Qt.ItemDataRole.UserRole))]
        except Exception:
            return None

    def _refresh_detail(self) -> None:
        row = self._selected_row()
        if not row:
            self._detail.setPlainText("No actor QA row selected.")
            return
        lines = actor_status_detail_lines(row)
        path = str(row.get("path") or "")
        if path:
            lines.extend(["", f"path: {path}"])
        self._detail.setPlainText("\n".join(lines))
        self._refresh_previews(row)

    def _set_preview(self, label: QLabel, title: str, path: Path | None) -> None:
        label.setPixmap(QPixmap())
        if path is None:
            label.setText(f"{title}\nNo image")
            return
        pix = QPixmap(str(path))
        if pix.isNull():
            label.setText(f"{title}\nUnreadable")
            return
        label.setPixmap(pix.scaled(
            label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        label.setToolTip(str(path))

    def _refresh_previews(self, row: dict[str, Any]) -> None:
        baseline, actual = _image_candidates(row)
        self._set_preview(self._baseline_preview, "Baseline", baseline)
        self._set_preview(self._actual_preview, "Actual", actual)

    def _open_folder(self) -> None:
        folder = self._status_path.parent if self._status_path.parent.exists() else Path("debugCapture")
        try:
            os.startfile(str(folder))
        except Exception:
            pass

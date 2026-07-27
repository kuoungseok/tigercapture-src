"""Painter UI tab for editable Figma import and plugin-package export."""
from __future__ import annotations

import os
from typing import Any, Mapping

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_figma import (
    import_figma_file,
    import_figma_json,
    inspect_figma_compatibility,
)


class _FigmaImportThread(QThread):
    completed = Signal(object, object)
    failed = Signal(str)

    def __init__(self, source: str, token: str, *, json_snapshot: bool) -> None:
        super().__init__()
        self._source = str(source)
        self._token = str(token)
        self._json_snapshot = bool(json_snapshot)

    def run(self) -> None:
        try:
            if self._json_snapshot:
                document, report = import_figma_json(self._source)
            else:
                document, report = import_figma_file(
                    self._source,
                    token=self._token,
                )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(document, report)


class PainterUIFigmaPanel(QWidget):
    document_imported = Signal(object, str, object)
    export_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document: dict[str, Any] = {}
        self._worker: _FigmaImportThread | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        title = QLabel("Figma Exchange")
        title.setObjectName("painterPanelSectionTitle")
        root.addWidget(title)

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Figma file URL or file key")
        root.addWidget(self.source_edit)

        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText(
            "Personal/OAuth token"
            + (" (FIGMA_ACCESS_TOKEN detected)" if os.environ.get("FIGMA_ACCESS_TOKEN") else "")
        )
        root.addWidget(self.token_edit)

        token_note = QLabel(
            "Requires file_content:read. The token is used once and is never saved."
        )
        token_note.setWordWrap(True)
        token_note.setObjectName("painterMutedLabel")
        root.addWidget(token_note)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Import"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Replace current UI document", "replace")
        self.mode_combo.addItem("Append as new artboards", "append")
        mode_row.addWidget(self.mode_combo, 1)
        root.addLayout(mode_row)

        self.import_button = QPushButton("Import Editable Figma File")
        self.import_button.clicked.connect(self._import_remote)
        root.addWidget(self.import_button)

        self.snapshot_button = QPushButton("Import Figma REST JSON...")
        self.snapshot_button.clicked.connect(self._choose_snapshot)
        root.addWidget(self.snapshot_button)

        divider = QLabel("EXPORT TO FIGMA")
        divider.setObjectName("painterPanelSectionTitle")
        root.addWidget(divider)

        export_note = QLabel(
            "Creates a local Figma development-plugin bundle with editable nodes, "
            "components, variables, images, Auto Layout, and prototype links. "
            "It does not forge a native .fig file."
        )
        export_note.setWordWrap(True)
        export_note.setObjectName("painterMutedLabel")
        root.addWidget(export_note)

        self.export_button = QPushButton("Export Figma Plugin Bundle...")
        self.export_button.clicked.connect(self._choose_export_directory)
        root.addWidget(self.export_button)

        self.compatibility_label = QLabel("No UI document")
        self.compatibility_label.setWordWrap(True)
        root.addWidget(self.compatibility_label)
        root.addStretch(1)

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        self._document = dict(value or {})
        report = inspect_figma_compatibility(self._document)
        counts = report["counts"]
        self.compatibility_label.setText(
            f"{report['artboard_count']} artboards | "
            f"{counts['native']} editable | "
            f"{counts['baked']} baked | {counts['blocked']} blocked"
        )
        self.export_button.setEnabled(counts["blocked"] == 0)

    def set_busy(self, busy: bool) -> None:
        self.import_button.setEnabled(not busy)
        self.snapshot_button.setEnabled(not busy)
        self.source_edit.setEnabled(not busy)
        self.token_edit.setEnabled(not busy)
        if busy:
            self.compatibility_label.setText("Importing Figma document...")

    def _start_import(self, source: str, *, json_snapshot: bool) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        source = str(source or "").strip()
        if not source:
            self.compatibility_label.setText("Enter a Figma URL or choose JSON.")
            return
        self.set_busy(True)
        worker = _FigmaImportThread(
            source,
            self.token_edit.text().strip(),
            json_snapshot=json_snapshot,
        )
        self._worker = worker
        worker.completed.connect(self._import_completed)
        worker.failed.connect(self._import_failed)
        worker.finished.connect(self._worker_finished)
        worker.start()

    def _import_remote(self) -> None:
        self._start_import(self.source_edit.text(), json_snapshot=False)

    def _choose_snapshot(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Figma REST JSON",
            "",
            "Figma REST JSON (*.json);;JSON files (*.json)",
        )
        if path:
            self._start_import(path, json_snapshot=True)

    def _import_completed(self, document: object, report: object) -> None:
        mode = str(self.mode_combo.currentData() or "replace")
        self.document_imported.emit(document, mode, report)
        row = dict(report or {})
        self.compatibility_label.setText(
            f"Imported {row.get('artboard_count', 0)} artboards and "
            f"{row.get('object_count', 0)} editable objects."
        )

    def _import_failed(self, message: str) -> None:
        self.compatibility_label.setText(f"Figma import failed: {message}")

    def _worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        self.set_busy(False)
        if worker is not None:
            worker.deleteLater()

    def _choose_export_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Export Figma Plugin Bundle",
        )
        if path:
            self.export_requested.emit(path)


__all__ = ["PainterUIFigmaPanel"]

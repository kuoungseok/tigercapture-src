"""File/version/PDF commands for Painter UI Design."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
)

from app.painter_i18n import painter_text


class PainterUIVersionHistoryDialog(QDialog):
    """Named, restorable UI-document checkpoints."""

    def __init__(self, document: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(painter_text("Version history"))
        self.resize(480, 420)
        self.selected_checkpoint_id = ""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(painter_text("Named versions of this design")))
        self.list_widget = QListWidget(self)
        target = ((document.get("linked_targets") or {}).get("review") or {})
        checkpoints = list(target.get("checkpoints") or [])
        for row in reversed(checkpoints):
            name = str(row.get("name") or row.get("id") or "Version")
            created = str(row.get("created_at") or "").replace("T", " ")[:19]
            revision = int(row.get("source_revision") or 0)
            item = QListWidgetItem(f"{name}\n{created}  ·  revision {revision}")
            item.setData(Qt.ItemDataRole.UserRole, str(row.get("id") or ""))
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)
        if not checkpoints:
            layout.addWidget(QLabel(painter_text("No saved versions are available.")))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok,
            parent=self,
        )
        self.restore_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.restore_button.setText(painter_text("Restore version"))
        self.restore_button.setEnabled(bool(checkpoints))
        buttons.accepted.connect(self._accept_selected)
        buttons.rejected.connect(self.reject)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._accept_selected())
        layout.addWidget(buttons)
        if checkpoints:
            self.list_widget.setCurrentRow(0)

    def _accept_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.selected_checkpoint_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if self.selected_checkpoint_id:
            self.accept()


def save_named_version(owner: Any) -> bool:
    default_name = f"Version {int((owner._painter_ui_document or {}).get('revision') or 0)}"
    name, accepted = QInputDialog.getText(
        owner,
        painter_text("Save to version history"),
        painter_text("Version name"),
        text=default_name,
    )
    if not accepted or not str(name).strip():
        return False
    owner._create_painter_ui_review_checkpoint(str(name).strip())
    owner._schedule_painter_recovery_snapshot(force=True)
    return True


def save_local_copy(owner: Any) -> dict | None:
    """Write a portable copy without changing the active document identity."""
    current = str(getattr(owner, "_painter_document_path", "") or "")
    initial = (
        Path(current).with_name(f"{Path(current).stem} copy.tspaint")
        if current
        else Path.home() / "Untitled copy.tspaint"
    )
    path, _selected = QFileDialog.getSaveFileName(
        owner,
        painter_text("Save Local Copy..."),
        str(initial),
        "Tiger Studio Painter (*.tspaint)",
    )
    if not path:
        return None
    from app.painter_document_io import save_painter_document

    active_path = str(getattr(owner, "_painter_document_path", "") or "")
    active_dirty = bool(getattr(owner, "_painter_document_dirty", False))
    report = save_painter_document(
        path,
        owner._painter_document_payload(),
        background_png=owner._painter_background_png_bytes(),
    )
    owner._painter_document_path = active_path
    owner._painter_document_dirty = active_dirty
    report["copy_only"] = True
    return report


def show_version_history(owner: Any) -> bool:
    document = getattr(owner, "_painter_ui_document", None) or {}
    dialog = PainterUIVersionHistoryDialog(document, owner)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    checkpoint_id = dialog.selected_checkpoint_id
    review = ((document.get("linked_targets") or {}).get("review") or {})
    checkpoint = next(
        (row for row in review.get("checkpoints", []) if row.get("id") == checkpoint_id),
        None,
    )
    snapshot = (checkpoint or {}).get("document")
    if not isinstance(snapshot, dict):
        return False
    answer = QMessageBox.question(
        owner,
        painter_text("Restore version"),
        painter_text("Restore this version? The current state remains undoable."),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return False
    from app.painter_ui_document import normalize_ui_document

    restored = normalize_ui_document(copy.deepcopy(snapshot))
    linked = copy.deepcopy(restored.get("linked_targets") or {})
    linked["review"] = copy.deepcopy(review)
    restored["linked_targets"] = linked
    restored["revision"] = int(document.get("revision") or 0) + 1
    owner._push_undo_state("Restore UI version")
    owner._painter_ui_document = restored
    owner._painter_document_dirty = True
    owner._refresh_painter_ui_overlay()
    return True


def export_artboards_pdf(document: dict, path: str | Path) -> dict:
    from app.painter_ui_asset_export import render_ui_artboard
    from app.painter_ui_document import normalize_ui_document

    normalized = normalize_ui_document(document)
    target = Path(path)
    if target.suffix.lower() != ".pdf":
        target = target.with_suffix(".pdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(target))
    writer.setTitle("Tiger Studio Painter UI")
    writer.setCreator("Tiger Studio Painter")
    writer.setResolution(144)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
    painter = QPainter(writer)
    try:
        for index, artboard in enumerate(normalized["artboards"]):
            if index:
                writer.newPage()
            image = render_ui_artboard(normalized, artboard["id"], density=1.0)
            viewport = QRectF(painter.viewport())
            size = image.size()
            size.scale(viewport.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
            rect = QRectF(0, 0, size.width(), size.height())
            rect.moveCenter(viewport.center())
            painter.drawImage(rect, image)
    finally:
        painter.end()
    return {
        "schema": "tigerstudio.painter.ui.pdf_export.v1",
        "path": str(target.resolve()),
        "page_count": len(normalized["artboards"]),
        "ok": target.exists() and target.stat().st_size > 0,
    }


def prompt_export_artboards_pdf(owner: Any) -> dict | None:
    current = str(getattr(owner, "_painter_document_path", "") or "")
    initial = Path(current).with_suffix(".pdf") if current else Path.home() / "Painter UI.pdf"
    path, _selected = QFileDialog.getSaveFileName(
        owner,
        painter_text("Export frames to PDF"),
        str(initial),
        "PDF (*.pdf)",
    )
    if not path:
        return None
    try:
        return export_artboards_pdf(owner._painter_ui_document, path)
    except Exception as exc:
        QMessageBox.warning(owner, painter_text("PDF export failed"), str(exc))
        return None


def create_document_branch(owner: Any) -> dict | None:
    name, accepted = QInputDialog.getText(
        owner,
        painter_text("Create branch"),
        painter_text("Branch name"),
    )
    if not accepted or not str(name).strip():
        return None
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(name).strip()).strip("-.") or "branch"
    current = Path(str(getattr(owner, "_painter_document_path", "") or "Untitled.tspaint"))
    if not current.is_absolute():
        current = Path.home() / current
    target = current.with_name(f"{current.stem}.branch-{slug}{current.suffix or '.tspaint'}")
    if target.exists():
        answer = QMessageBox.question(
            owner,
            painter_text("Create branch"),
            painter_text("That branch already exists. Replace it?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return None
    report = owner.save_document_to_path(target)
    report["branch_name"] = str(name).strip()
    return report


__all__ = [
    "PainterUIVersionHistoryDialog",
    "create_document_branch",
    "export_artboards_pdf",
    "prompt_export_artboards_pdf",
    "save_local_copy",
    "save_named_version",
    "show_version_history",
]

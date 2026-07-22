from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QSize, QStandardPaths, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.ai_workspace import (
    MotionAIReference,
    MotionAIRequest,
    references_from_paths,
)


class MotionAIPromptEdit(QPlainTextEdit):
    references_dropped = Signal(object)
    submit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionAIPrompt")
        self.setAcceptDrops(True)
        self.setPlaceholderText("Describe the motion, then drop text or images here...")
        self.setMinimumHeight(92)

    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802 - Qt override
        return bool(source.hasUrls() or source.hasImage() or source.hasText())

    def insertFromMimeData(self, source) -> None:  # noqa: N802 - Qt override
        if source.hasUrls():
            paths = [url.toLocalFile() for url in source.urls() if url.isLocalFile()]
            remote = [url.toString() for url in source.urls() if not url.isLocalFile()]
            if paths:
                self.references_dropped.emit({"paths": paths})
            if remote:
                self.insertPlainText("\n".join(remote))
            return
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QPixmap):
                image = image.toImage()
            if isinstance(image, QImage) and not image.isNull():
                self.references_dropped.emit({"image": image})
                return
        if source.hasText():
            self.insertPlainText(source.text())
            return
        super().insertFromMimeData(source)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.key() in {Qt.Key_Return, Qt.Key_Enter} and event.modifiers() & Qt.ControlModifier:
            self.submit_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class MotionAIReferenceList(QListWidget):
    delete_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.key() in {Qt.Key_Delete, Qt.Key_Backspace}:
            self.delete_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class MotionAIPanel(QWidget):
    plan_requested = Signal(object)
    apply_requested = Signal(object)

    def __init__(self, parent=None, *, attachment_root: str | Path | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionAIPanel")
        self.setAcceptDrops(True)
        self.setMinimumWidth(300)
        self.setMaximumWidth(430)
        self._references: list[MotionAIReference] = []
        self._proposal: dict | None = None
        if attachment_root is None:
            app_data = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
            attachment_root = Path(app_data or Path.home() / ".tigercapture") / "motion_ai" / "imports"
        self._attachment_root = Path(attachment_root)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("AI WORKSPACE", self)
        title.setObjectName("MotionAIHeading")
        header.addWidget(title)
        header.addStretch(1)
        self.status = QLabel("Local Draft", self)
        self.status.setObjectName("MotionAIStatus")
        header.addWidget(self.status)
        root.addLayout(header)

        self.references = MotionAIReferenceList(self)
        self.references.setObjectName("MotionAIReferences")
        self.references.setViewMode(QListWidget.IconMode)
        self.references.setFlow(QListWidget.LeftToRight)
        self.references.setWrapping(False)
        self.references.setResizeMode(QListWidget.Adjust)
        self.references.setMovement(QListWidget.Static)
        self.references.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.references.setIconSize(QSize(72, 46))
        self.references.setGridSize(QSize(92, 70))
        self.references.setMaximumHeight(76)
        self.references.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.references.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.references.setToolTip("Image and text references. Delete removes selected items.")
        self.references.delete_requested.connect(self.remove_selected_references)
        root.addWidget(self.references)

        self.prompt = MotionAIPromptEdit(self)
        self.prompt.references_dropped.connect(self._accept_drop_payload)
        self.prompt.submit_requested.connect(self.request_plan)
        root.addWidget(self.prompt)

        tools = QHBoxLayout()
        self.attach_button = QToolButton(self)
        self.attach_button.setObjectName("MotionAIIconButton")
        self.attach_button.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.attach_button.setToolTip("Attach image or text file")
        self.attach_button.clicked.connect(self.choose_references)
        tools.addWidget(self.attach_button)
        self.clear_button = QToolButton(self)
        self.clear_button.setObjectName("MotionAIIconButton")
        self.clear_button.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.clear_button.setToolTip("Clear prompt and references")
        self.clear_button.clicked.connect(self.clear_request)
        tools.addWidget(self.clear_button)
        tools.addStretch(1)
        self.plan_button = QPushButton("Plan", self)
        self.plan_button.clicked.connect(self.request_plan)
        tools.addWidget(self.plan_button)
        self.apply_button = QPushButton("Apply", self)
        self.apply_button.setObjectName("MotionPrimaryButton")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_proposal)
        tools.addWidget(self.apply_button)
        root.addLayout(tools)

        result_label = QLabel("PROPOSAL", self)
        result_label.setObjectName("MotionAIHeading")
        root.addWidget(result_label)
        self.result = QPlainTextEdit(self)
        self.result.setObjectName("MotionAIResult")
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("Plan results appear here. Review before applying.")
        root.addWidget(self.result, 1)

        hint = QLabel("Ctrl+Enter plans. Dropped images remain references until Apply.", self)
        hint.setObjectName("MotionAIHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

    def reference_dicts(self) -> list[dict]:
        return [item.to_dict() for item in self._references]

    def build_request(self, composition_id: str) -> dict:
        return MotionAIRequest(
            composition_id=composition_id,
            prompt=self.prompt.toPlainText().strip(),
            references=list(self._references),
        ).to_dict()

    def add_reference(self, reference: MotionAIReference) -> None:
        identity = (reference.kind, reference.uri.casefold(), reference.text)
        if any((item.kind, item.uri.casefold(), item.text) == identity for item in self._references):
            return
        self._references.append(reference)
        item = QListWidgetItem(reference.name or ("Image" if reference.kind == "image" else "Text"))
        item.setData(Qt.UserRole, reference.id)
        item.setToolTip(reference.uri or reference.text[:240])
        if reference.kind == "image" and reference.uri:
            pixmap = QPixmap(reference.uri)
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap.scaled(
                    self.references.iconSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )))
        if item.icon().isNull():
            item.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        self.references.addItem(item)
        self._invalidate_proposal()

    def add_paths(self, paths: list[str]) -> list[str]:
        references, warnings = references_from_paths(paths)
        for reference in references:
            self.add_reference(reference)
        if warnings:
            self.status.setText(f"Skipped {len(warnings)}")
            self.result.setPlainText("\n".join(warnings))
        return warnings

    def choose_references(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach references",
            "",
            "Images and text (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff *.txt *.md *.csv *.json *.srt *.vtt)",
        )
        if paths:
            self.add_paths(paths)

    def remove_selected_references(self) -> None:
        ids = {str(item.data(Qt.UserRole) or "") for item in self.references.selectedItems()}
        if not ids:
            return
        self._references = [item for item in self._references if item.id not in ids]
        for index in reversed(range(self.references.count())):
            if str(self.references.item(index).data(Qt.UserRole) or "") in ids:
                self.references.takeItem(index)
        self._invalidate_proposal()

    def clear_request(self) -> None:
        self.prompt.clear()
        self.references.clear()
        self._references.clear()
        self.result.clear()
        self.status.setText("Local Draft")
        self._invalidate_proposal()

    def request_plan(self) -> None:
        self.plan_requested.emit({
            "prompt": self.prompt.toPlainText().strip(),
            "references": self.reference_dicts(),
            "provider": "local_layout",
        })

    def set_proposal(self, proposal: dict) -> None:
        self._proposal = dict(proposal)
        summary = str(proposal.get("summary") or "")
        layers = list(proposal.get("layers") or [])
        warnings = [str(item) for item in proposal.get("warnings") or []]
        lines = [summary, "", *[f"+ {item.get('name', 'Layer')}" for item in layers]]
        if warnings:
            lines.extend(["", "Review:", *[f"- {item}" for item in warnings]])
        self.result.setPlainText("\n".join(lines).strip())
        self.apply_button.setEnabled(bool(layers))
        self.status.setText(f"{len(layers)} layer draft")

    def apply_proposal(self) -> None:
        if self._proposal:
            self.apply_requested.emit(dict(self._proposal))

    def set_applied(self, layer_count: int) -> None:
        self.status.setText(f"Applied {int(layer_count)}")
        self.apply_button.setEnabled(False)

    def _accept_drop_payload(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        paths = [str(item) for item in payload.get("paths", [])]
        if paths:
            self.add_paths(paths)
        image = payload.get("image")
        if isinstance(image, QImage) and not image.isNull():
            self._attachment_root.mkdir(parents=True, exist_ok=True)
            path = self._attachment_root / f"clipboard_{uuid4().hex}.png"
            if image.save(str(path), "PNG"):
                self.add_paths([str(path)])

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasImage() or mime.hasText():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override
        mime = event.mimeData()
        if mime.hasUrls():
            paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
            if paths:
                self._accept_drop_payload({"paths": paths})
            remote = [url.toString() for url in mime.urls() if not url.isLocalFile()]
            if remote:
                self.prompt.insertPlainText("\n".join(remote))
            event.acceptProposedAction()
            return
        if mime.hasImage():
            image = mime.imageData()
            if isinstance(image, QPixmap):
                image = image.toImage()
            self._accept_drop_payload({"image": image})
            event.acceptProposedAction()
            return
        if mime.hasText():
            self.prompt.insertPlainText(mime.text())
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _invalidate_proposal(self) -> None:
        self._proposal = None
        self.apply_button.setEnabled(False)


__all__ = ["MotionAIPanel", "MotionAIPromptEdit"]

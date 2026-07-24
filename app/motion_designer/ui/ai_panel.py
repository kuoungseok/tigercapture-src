from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QSize, QStandardPaths, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
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
from .layer_extraction_panel import LayerExtractionPanel
from .ai_patch_diff import MotionAIPatchDiffWidget


class MotionAIPromptEdit(QPlainTextEdit):
    references_dropped = Signal(object)
    submit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionAIPrompt")
        self.setAcceptDrops(True)
        self.setPlaceholderText(
            "Describe the motion, then drop text, images, audio, or video here..."
        )
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
    patch_requested = Signal(object)
    patch_apply_requested = Signal(object)
    decomposition_repaired = Signal(object)

    def __init__(self, parent=None, *, attachment_root: str | Path | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionAIPanel")
        self.setAcceptDrops(True)
        self.setMinimumWidth(300)
        self.setMaximumWidth(430)
        self._references: list[MotionAIReference] = []
        self._proposal: dict | None = None
        self._candidates: list[dict] = []
        self._patch: dict | None = None
        self._applied_layer_ids: list[str] = []
        self._provider_status = self._read_provider_status()
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
        self.status = QLabel(self._provider_status, self)
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
        self.references.setToolTip(
            "Image, text, audio, and video references. Delete removes selected items."
        )
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
        self.attach_button.setToolTip("Attach image, text, audio, or video")
        self.attach_button.clicked.connect(self.choose_references)
        tools.addWidget(self.attach_button)
        self.clear_button = QToolButton(self)
        self.clear_button.setObjectName("MotionAIIconButton")
        self.clear_button.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.clear_button.setToolTip("Clear prompt and references")
        self.clear_button.clicked.connect(self.clear_request)
        tools.addWidget(self.clear_button)
        self.decompose_images = QCheckBox("Explode image layers", self)
        self.decompose_images.setChecked(True)
        self.decompose_images.setToolTip(
            "Separate local image references into editable background, subject, text, and depth layers."
        )
        self.decompose_images.toggled.connect(self._invalidate_proposal)
        tools.addWidget(self.decompose_images)
        self.advanced_button = QToolButton(self)
        self.advanced_button.setText("Advanced")
        self.advanced_button.setCheckable(True)
        self.advanced_button.setToolTip("Show layer extraction and motion controls")
        tools.addWidget(self.advanced_button)
        tools.addStretch(1)
        self.plan_button = QPushButton("Plan", self)
        self.plan_button.clicked.connect(self.request_plan)
        tools.addWidget(self.plan_button)
        self.revise_button = QPushButton("Revise", self)
        self.revise_button.setEnabled(False)
        self.revise_button.setToolTip(
            "Plan a scoped revision for the layers applied by Motion AI"
        )
        self.revise_button.clicked.connect(self.request_patch)
        tools.addWidget(self.revise_button)
        self.apply_button = QPushButton("Apply", self)
        self.apply_button.setObjectName("MotionPrimaryButton")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_proposal)
        tools.addWidget(self.apply_button)
        root.addLayout(tools)

        self.extraction = LayerExtractionPanel(self)
        self.extraction.setVisible(False)
        self.extraction.options_changed.connect(self._invalidate_proposal)
        self.advanced_button.toggled.connect(self.extraction.setVisible)
        root.addWidget(self.extraction)

        result_header = QHBoxLayout()
        result_label = QLabel("PROPOSAL", self)
        result_label.setObjectName("MotionAIHeading")
        result_header.addWidget(result_label)
        result_header.addStretch(1)
        self.candidate_selector = QComboBox(self)
        self.candidate_selector.setToolTip("Choose a generated motion treatment")
        self.candidate_selector.setVisible(False)
        self.candidate_selector.currentIndexChanged.connect(
            self._select_candidate
        )
        result_header.addWidget(self.candidate_selector)
        self.repair_button = QPushButton("Refine Layers", self)
        self.repair_button.setEnabled(False)
        self.repair_button.setToolTip(
            "Review original, reconstructed background, masks, locks, and groups"
        )
        self.repair_button.clicked.connect(self._open_layer_repair)
        result_header.addWidget(self.repair_button)
        root.addLayout(result_header)
        self.candidate_strip = QListWidget(self)
        self.candidate_strip.setObjectName("MotionAICandidateStrip")
        self.candidate_strip.setViewMode(QListWidget.IconMode)
        self.candidate_strip.setFlow(QListWidget.LeftToRight)
        self.candidate_strip.setWrapping(False)
        self.candidate_strip.setMovement(QListWidget.Static)
        self.candidate_strip.setSelectionMode(QAbstractItemView.SingleSelection)
        self.candidate_strip.setIconSize(QSize(124, 70))
        self.candidate_strip.setGridSize(QSize(144, 110))
        self.candidate_strip.setMinimumHeight(120)
        self.candidate_strip.setMaximumHeight(124)
        self.candidate_strip.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.candidate_strip.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.candidate_strip.setVisible(False)
        self.candidate_strip.currentRowChanged.connect(self._select_candidate)
        root.addWidget(self.candidate_strip)
        self.result = QPlainTextEdit(self)
        self.result.setObjectName("MotionAIResult")
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("Plan results appear here. Review before applying.")
        root.addWidget(self.result, 1)
        self.patch_diff = MotionAIPatchDiffWidget(self)
        self.patch_diff.apply_requested.connect(self.apply_patch)
        self.patch_diff.dismissed.connect(self.dismiss_patch)
        root.addWidget(self.patch_diff)

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
        item = QListWidgetItem(reference.name or reference.kind.title())
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
            (
                "Motion references (*.png *.jpg *.jpeg *.webp *.bmp *.gif "
                "*.tif *.tiff *.txt *.md *.csv *.json *.srt *.vtt *.wav "
                "*.mp3 *.m4a *.aac *.flac *.ogg *.opus *.mp4 *.mov *.mkv "
                "*.avi *.webm *.m4v)"
            ),
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
        self.status.setText(self._provider_status)
        self._invalidate_proposal()

    def request_plan(self) -> None:
        self.plan_requested.emit({
            "prompt": self.prompt.toPlainText().strip(),
            "references": self.reference_dicts(),
            "provider": "",
            "decompose_images": self.decompose_images.isChecked(),
            **self.extraction.options(),
        })

    def request_patch(self) -> None:
        prompt = self.prompt.toPlainText().strip()
        if not prompt or not self._applied_layer_ids:
            return
        self.patch_requested.emit({
            "prompt": prompt,
            "layer_ids": list(self._applied_layer_ids),
            "provider": "",
        })

    def set_patch_planning(self, active: bool) -> None:
        self.revise_button.setEnabled(
            not active and bool(self._applied_layer_ids)
        )
        if active:
            self.status.setText("Planning revision...")

    def set_patch(self, payload: dict) -> None:
        patch = payload.get("patch")
        report = payload.get("diff")
        if not isinstance(patch, dict) or not isinstance(report, dict):
            self.set_error("Motion AI returned an invalid revision.")
            return
        self._patch = dict(patch)
        self.patch_diff.set_diff(dict(report))
        self.status.setText(
            f"Revision ready / {int(report.get('operation_count', 0))} changes"
        )

    def apply_patch(self) -> None:
        if self._patch:
            self.patch_apply_requested.emit(dict(self._patch))

    def dismiss_patch(self) -> None:
        self._patch = None
        self.patch_diff.setVisible(False)
        self.status.setText(self._provider_status)

    def set_generating(self, active: bool) -> None:
        self.plan_button.setEnabled(not active)
        self.attach_button.setEnabled(not active)
        self.clear_button.setEnabled(not active)
        self.decompose_images.setEnabled(not active)
        self.advanced_button.setEnabled(not active)
        self.extraction.set_generating(active)
        self.repair_button.setEnabled(
            not active and self._proposal_has_decomposition()
        )
        if active:
            self.apply_button.setEnabled(False)
            self.status.setText("Planning...")
            self.result.setPlainText(
                "The selected Tiger Studio AI provider is preparing a reviewable storyboard."
            )
        elif self._proposal is None:
            self.status.setText(self._provider_status)

    def set_error(self, message: str) -> None:
        self._proposal = None
        self.set_generating(False)
        self.status.setText("Plan failed")
        self.result.setPlainText(str(message or "Motion AI generation failed."))

    def set_proposal(self, proposal: dict) -> None:
        self._candidates = [dict(proposal)]
        self.candidate_selector.setVisible(False)
        self.candidate_strip.clear()
        self.candidate_strip.setVisible(False)
        self._display_proposal(dict(proposal))

    def set_candidate_set(self, payload: dict) -> None:
        candidates = [
            dict(item)
            for item in payload.get("candidates", [])
            if isinstance(item, dict)
        ]
        if not candidates:
            self.set_error("Motion AI returned no candidates.")
            return
        self._candidates = candidates
        self.candidate_strip.blockSignals(True)
        self.candidate_strip.clear()
        self.candidate_selector.blockSignals(True)
        self.candidate_selector.clear()
        for index, item in enumerate(candidates, 1):
            analysis = item.get("analysis") if isinstance(item.get("analysis"), dict) else {}
            variant = str(analysis.get("motion_variant") or f"Candidate {index}")
            self.candidate_selector.addItem(variant.title(), index - 1)
            strip_item = QListWidgetItem(variant.title())
            strip_item.setData(Qt.UserRole, index - 1)
            strip_item.setTextAlignment(Qt.AlignHCenter)
            strip_item.setToolTip(
                f"{variant.title()} / {len(item.get('layers') or [])} layers"
            )
            strip_item.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
            self.candidate_strip.addItem(strip_item)
        selected = max(0, min(
            len(candidates) - 1,
            int(payload.get("selected_index", 0) or 0),
        ))
        self.candidate_selector.setCurrentIndex(selected)
        self.candidate_selector.blockSignals(False)
        self.candidate_selector.setVisible(False)
        self.candidate_strip.setCurrentRow(selected)
        self.candidate_strip.blockSignals(False)
        self.candidate_strip.setVisible(len(candidates) > 1)
        self._display_proposal(candidates[selected])

    def _select_candidate(self, index: int) -> None:
        if 0 <= int(index) < len(self._candidates):
            self.candidate_selector.blockSignals(True)
            self.candidate_selector.setCurrentIndex(int(index))
            self.candidate_selector.blockSignals(False)
            if self.candidate_strip.currentRow() != int(index):
                self.candidate_strip.blockSignals(True)
                self.candidate_strip.setCurrentRow(int(index))
                self.candidate_strip.blockSignals(False)
            self._display_proposal(self._candidates[int(index)])

    def set_candidate_previews(self, payload: dict) -> None:
        for row in payload.get("previews", []):
            if not isinstance(row, dict):
                continue
            index = int(row.get("index", -1) or 0)
            if not 0 <= index < self.candidate_strip.count():
                continue
            candidate_id = str(row.get("candidate_id") or "")
            if candidate_id and candidate_id != str(
                self._candidates[index].get("id") or ""
            ):
                continue
            thumbnail = str(row.get("thumbnail_path") or "")
            pixmap = QPixmap(thumbnail)
            if pixmap.isNull():
                continue
            item = self.candidate_strip.item(index)
            item.setIcon(QIcon(pixmap))
            item.setToolTip(
                f"{item.text()} / real render at {int(row.get('time_ms', 0)) / 1000:.2f}s"
            )

    def set_candidate_preview_error(self, message: str) -> None:
        self.status.setText("Candidate preview unavailable")
        self.status.setToolTip(str(message or "Candidate preview failed."))

    def _display_proposal(self, proposal: dict) -> None:
        self._proposal = dict(proposal)
        summary = str(proposal.get("summary") or "")
        layers = list(proposal.get("layers") or [])
        warnings = [str(item) for item in proposal.get("warnings") or []]
        lines = [summary, "", *[f"+ {item.get('name', 'Layer')}" for item in layers]]
        analysis = proposal.get("analysis") if isinstance(proposal.get("analysis"), dict) else {}
        cost = analysis.get("renderer_cost") if isinstance(analysis.get("renderer_cost"), dict) else {}
        if analysis:
            lines.extend([
                "",
                "Preflight:",
                f"- Render: {cost.get('grade', 'unknown')} / {float(cost.get('cost_units', 0.0)):.1f} units",
                f"- Assets: {len(analysis.get('missing_assets') or [])} missing",
                f"- Bake/cache: {len(analysis.get('bake_requirements') or [])} required",
            ])
        decompositions = [
            item for item in analysis.get("image_decompositions", [])
            if isinstance(item, dict)
        ]
        if decompositions:
            locked_count = sum(
                1
                for report in decompositions
                for element in report.get("elements", [])
                if isinstance(element, dict)
                and bool((element.get("metadata") or {}).get("motion_lock_to_background"))
            )
            providers = list(dict.fromkeys(
                str(
                    (report.get("diagnostics") or {}).get("segmentation", {}).get("provider")
                    or (report.get("diagnostics") or {}).get("segmentation_backend")
                    or "unknown"
                )
                for report in decompositions
            ))
            valid_count = sum(
                1
                for report in decompositions
                if bool((report.get("diagnostics") or {}).get("validation", {}).get("ok"))
            )
            lines.extend([
                "",
                "Layer extraction:",
                f"- Provider: {', '.join(providers)}",
                f"- Background locks: {locked_count}",
                f"- Integrity: {valid_count}/{len(decompositions)} passed",
                f"- Motion: {analysis.get('motion_variant', self.extraction.variant.currentText())}",
            ])
        self.repair_button.setEnabled(bool(decompositions))
        if warnings:
            lines.extend(["", "Review:", *[f"- {item}" for item in warnings]])
        self.result.setPlainText("\n".join(lines).strip())
        self.apply_button.setEnabled(bool(layers))
        provider = str(proposal.get("provider") or "AI")
        self.status.setText(f"{provider} / {len(layers)} layers")

    def apply_proposal(self) -> None:
        if self._proposal:
            self.apply_requested.emit(dict(self._proposal))

    def set_applied(
        self,
        layer_count: int,
        layer_ids: list[str] | None = None,
    ) -> None:
        self.status.setText(f"Applied {int(layer_count)}")
        self.apply_button.setEnabled(False)
        self._applied_layer_ids = [str(item) for item in (layer_ids or [])]
        self.revise_button.setEnabled(bool(self._applied_layer_ids))

    def set_patch_applied(self, operation_count: int) -> None:
        self.status.setText(f"Revision applied / {int(operation_count)} changes")
        self._patch = None
        self.patch_diff.setVisible(False)
        self.revise_button.setEnabled(bool(self._applied_layer_ids))

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
        self._patch = None
        self._candidates.clear()
        self.candidate_selector.clear()
        self.candidate_selector.setVisible(False)
        self.candidate_strip.clear()
        self.candidate_strip.setVisible(False)
        self.repair_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.patch_diff.setVisible(False)

    def update_current_proposal(self, proposal: dict) -> None:
        current = self.candidate_selector.currentIndex()
        if 0 <= current < len(self._candidates):
            self._candidates[current] = dict(proposal)
        else:
            self._candidates = [dict(proposal)]
        self._display_proposal(dict(proposal))

    def _proposal_has_decomposition(self) -> bool:
        if not isinstance(self._proposal, dict):
            return False
        analysis = (
            self._proposal.get("analysis")
            if isinstance(self._proposal.get("analysis"), dict)
            else {}
        )
        return any(
            isinstance(item, dict)
            for item in analysis.get("image_decompositions", [])
        )

    def _open_layer_repair(self) -> None:
        if not self._proposal_has_decomposition():
            return
        from .layer_extraction_dialog import LayerExtractionDialog

        analysis = self._proposal.get("analysis", {})
        decomposition = next(
            item
            for item in analysis.get("image_decompositions", [])
            if isinstance(item, dict)
        )
        dialog = LayerExtractionDialog(decomposition, self)
        if dialog.exec() == dialog.Accepted:
            self.decomposition_repaired.emit(dialog.result_dict())

    @staticmethod
    def _read_provider_status() -> str:
        try:
            from app.ai_providers import provider_user_state

            state = provider_user_state()
            labels = {
                "qwen_local": "Qwen Local",
                "codex_mcp": "Codex",
                "claude_mcp": "Claude",
                "local_llm": "Local LLM",
                "manual_json": "Manual JSON",
                "rule_based": "Rule-based",
            }
            selected_id = str(state.get("selected_provider") or "")
            effective_id = str(state.get("effective_generation_provider") or selected_id)
            selected = labels.get(selected_id, selected_id or "AI")
            effective = labels.get(effective_id, effective_id or selected)
            return selected if selected == effective else f"{selected} -> {effective}"
        except Exception:
            return "AI Ready"


__all__ = ["MotionAIPanel", "MotionAIPromptEdit"]

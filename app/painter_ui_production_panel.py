"""Compact user-facing production panel for Painter UI milestones M2A-M6."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_document import normalize_ui_document
from app.painter_i18n import painter_text
from app.painter_ui_review import inspect_ui_review


class PainterUIProductionPanel(QWidget):
    template_save_requested = Signal(str, str)
    template_install_requested = Signal(str)
    review_comment_add_requested = Signal(str)
    review_comment_update_requested = Signal(str, object)
    review_checkpoint_requested = Signal(str)
    review_export_requested = Signal(str)
    prototype_export_requested = Signal(str)
    web_preflight_requested = Signal()
    web_package_requested = Signal(str)
    ppt_preflight_requested = Signal(str)
    ppt_send_requested = Signal(str)
    assets_export_requested = Signal(str, object, object, bool)
    figma_document_imported = Signal(object, str, object)
    figma_export_requested = Signal(str)
    umg_preflight_requested = Signal()
    umg_package_requested = Signal(str)
    umg_generate_requested = Signal(str, str)
    ai_plan_requested = Signal(str)
    ai_apply_requested = Signal(object)
    ai_audit_requested = Signal()
    ai_prototype_plan_requested = Signal(str)
    ai_prototype_apply_requested = Signal(object)
    artifact_open_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = normalize_ui_document(None)
        self._ai_plan: dict[str, Any] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self.tabs = tabs
        root.addWidget(tabs)

        library = QWidget()
        library_layout = QVBoxLayout(library)
        library_layout.setContentsMargins(4, 4, 4, 4)
        self.template_id_edit = QLineEdit()
        self.template_id_edit.setPlaceholderText("Template ID")
        self.template_name_edit = QLineEdit()
        self.template_name_edit.setPlaceholderText("Template name")
        save_template = QPushButton("Save Current as Template")
        save_template.clicked.connect(
            lambda: self.template_save_requested.emit(
                self.template_id_edit.text().strip(),
                self.template_name_edit.text().strip(),
            )
        )
        install_template = QPushButton("Install Template Package")
        install_template.clicked.connect(self._choose_template_package)
        library_layout.addWidget(self.template_id_edit)
        library_layout.addWidget(self.template_name_edit)
        library_layout.addWidget(save_template)
        library_layout.addWidget(install_template)
        library_layout.addStretch(1)
        tabs.addTab(library, "Library")

        review = QWidget()
        review_layout = QVBoxLayout(review)
        review_layout.setContentsMargins(4, 4, 4, 4)
        self.review_list = QListWidget()
        self.review_comment_edit = QLineEdit()
        self.review_comment_edit.setPlaceholderText("Comment on selection")
        add_comment = QPushButton("Add Comment")
        add_comment.clicked.connect(
            lambda: self.review_comment_add_requested.emit(
                self.review_comment_edit.text().strip()
            )
        )
        resolve_comment = QPushButton("Resolve Selected")
        resolve_comment.clicked.connect(self._resolve_selected_comment)
        self.checkpoint_edit = QLineEdit()
        self.checkpoint_edit.setPlaceholderText("Checkpoint name")
        create_checkpoint = QPushButton("Create Checkpoint")
        create_checkpoint.clicked.connect(
            lambda: self.review_checkpoint_requested.emit(
                self.checkpoint_edit.text().strip()
            )
        )
        export_review = QPushButton("Export Offline Review")
        export_review.clicked.connect(
            lambda: self._choose_directory(self.review_export_requested)
        )
        review_layout.addWidget(self.review_list, 1)
        review_layout.addWidget(self.review_comment_edit)
        review_actions = QHBoxLayout()
        review_actions.addWidget(add_comment)
        review_actions.addWidget(resolve_comment)
        review_layout.addLayout(review_actions)
        review_layout.addWidget(self.checkpoint_edit)
        review_layout.addWidget(create_checkpoint)
        review_layout.addWidget(export_review)
        tabs.addTab(review, "Review")

        deliver = QWidget()
        deliver_layout = QVBoxLayout(deliver)
        deliver_layout.setContentsMargins(4, 4, 4, 4)
        export_prototype = QPushButton("Export Interactive Prototype")
        export_prototype.clicked.connect(
            lambda: self._choose_directory(self.prototype_export_requested)
        )
        self.web_preflight_button = QPushButton(painter_text("Web Preflight"))
        self.web_preflight_button.clicked.connect(self.web_preflight_requested)
        self.web_package_button = QPushButton(
            painter_text("Export Web Package")
        )
        self.web_package_button.clicked.connect(
            lambda: self._choose_directory(self.web_package_requested)
        )
        self.asset_png = QCheckBox("PNG")
        self.asset_png.setChecked(True)
        self.asset_webp = QCheckBox("WebP")
        self.asset_svg = QCheckBox("SVG")
        self.asset_atlas = QCheckBox("Texture Atlas")
        density_label = QLabel("Density: @1x @2x @3x")
        export_assets = QPushButton("Export Production Assets")
        export_assets.clicked.connect(self._choose_asset_directory)
        deliver_layout.addWidget(export_prototype)
        web_row = QHBoxLayout()
        web_row.addWidget(self.web_preflight_button)
        web_row.addWidget(self.web_package_button)
        deliver_layout.addLayout(web_row)
        self.ppt_scope_combo = QComboBox()
        self.ppt_scope_combo.addItem(
            painter_text("Active Artboard"),
            "active_artboard",
        )
        self.ppt_scope_combo.addItem(
            painter_text("All Artboards"),
            "all_artboards",
        )
        self.ppt_preflight_button = QPushButton(painter_text("PPT Preflight"))
        self.ppt_preflight_button.clicked.connect(
            lambda: self.ppt_preflight_requested.emit(
                str(self.ppt_scope_combo.currentData())
            )
        )
        self.ppt_send_button = QPushButton(painter_text("Send to PPT"))
        self.ppt_send_button.clicked.connect(
            lambda: self.ppt_send_requested.emit(
                str(self.ppt_scope_combo.currentData())
            )
        )
        ppt_row = QHBoxLayout()
        ppt_row.addWidget(self.ppt_scope_combo, 1)
        ppt_row.addWidget(self.ppt_preflight_button)
        ppt_row.addWidget(self.ppt_send_button)
        deliver_layout.addLayout(ppt_row)
        deliver_layout.addWidget(density_label)
        format_row = QHBoxLayout()
        for control in (self.asset_png, self.asset_webp, self.asset_svg):
            format_row.addWidget(control)
        deliver_layout.addLayout(format_row)
        deliver_layout.addWidget(self.asset_atlas)
        deliver_layout.addWidget(export_assets)
        deliver_layout.addStretch(1)
        tabs.addTab(deliver, "Deliver")

        from app.painter_ui_figma_panel import PainterUIFigmaPanel

        self.figma_panel = PainterUIFigmaPanel()
        self.figma_panel.document_imported.connect(self.figma_document_imported)
        self.figma_panel.export_requested.connect(self.figma_export_requested)
        tabs.addTab(self.figma_panel, "Figma")

        unreal = QWidget()
        unreal_layout = QVBoxLayout(unreal)
        unreal_layout.setContentsMargins(4, 4, 4, 4)
        self.unreal_project_edit = QLineEdit()
        self.unreal_project_edit.setPlaceholderText("Unreal .uproject path")
        preflight = QPushButton("UMG Preflight")
        preflight.clicked.connect(self.umg_preflight_requested)
        package = QPushButton("Package TigerStudioUMG")
        package.clicked.connect(
            lambda: self._choose_directory(self.umg_package_requested)
        )
        generate = QPushButton("Generate in Unreal 5.8")
        generate.clicked.connect(self._choose_umg_output)
        unreal_layout.addWidget(self.unreal_project_edit)
        unreal_layout.addWidget(preflight)
        unreal_layout.addWidget(package)
        unreal_layout.addWidget(generate)
        unreal_layout.addStretch(1)
        tabs.addTab(unreal, "Unreal")

        ai = QWidget()
        ai_layout = QVBoxLayout(ai)
        ai_layout.setContentsMargins(4, 4, 4, 4)
        self.ai_mode_combo = QComboBox()
        self.ai_mode_combo.addItem(painter_text("Screen Design"), "screen")
        self.ai_mode_combo.addItem(
            painter_text("Interactive Prototype"),
            "prototype",
        )
        self.ai_prompt_edit = QLineEdit()
        self.ai_prompt_edit.setPlaceholderText(
            painter_text("Describe a screen, component, or product UI")
        )
        plan = QPushButton(painter_text("Plan and Preview"))
        plan.clicked.connect(self._request_ai_plan)
        self.ai_summary = QLabel(painter_text("No AI plan"))
        self.ai_summary.setWordWrap(True)
        self.ai_delivery_label = QLabel("Web · App · UMG")
        self.ai_delivery_label.setWordWrap(True)
        apply_plan = QPushButton(painter_text("Apply Approved Plan"))
        apply_plan.clicked.connect(self._request_ai_apply)
        audit = QPushButton(painter_text("Run Product QA"))
        audit.clicked.connect(self.ai_audit_requested)
        ai_layout.addWidget(self.ai_mode_combo)
        ai_layout.addWidget(self.ai_prompt_edit)
        ai_layout.addWidget(plan)
        ai_layout.addWidget(self.ai_summary)
        ai_layout.addWidget(self.ai_delivery_label)
        ai_layout.addWidget(apply_plan)
        ai_layout.addWidget(audit)
        from app.painter_ui_accessibility_panel import (
            PainterUIAccessibilityPanel,
        )

        self.accessibility_panel = PainterUIAccessibilityPanel()
        ai_layout.addWidget(self.accessibility_panel)
        ai_layout.addStretch(1)
        tabs.addTab(ai, "AI")

        self.status_label = QLabel("Production tools ready")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self._artifact_path = ""
        self.open_artifact_button = QPushButton("Open Last Artifact")
        self.open_artifact_button.setEnabled(False)
        self.open_artifact_button.clicked.connect(
            lambda: self.artifact_open_requested.emit(self._artifact_path)
        )
        root.addWidget(self.open_artifact_button)

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        self._document = normalize_ui_document(value)
        self.figma_panel.set_document(self._document)
        review = inspect_ui_review(self._document)
        self.review_list.clear()
        for row in review["comments"]:
            prefix = "Resolved" if row.get("resolved") else "Open"
            item = QListWidgetItem(
                f"{prefix} | {row.get('author')}: {row.get('text')}"
            )
            item.setData(256, row["id"])
            self.review_list.addItem(item)
        self.status_label.setText(
            f"{len(self._document['artboards'])} artboards | "
            f"{len(self._document['objects'])} objects | "
            f"{review['unresolved_count']} open comments"
        )

    def set_ai_plan(self, plan: Mapping[str, Any]) -> None:
        self._ai_plan = dict(plan)
        self.ai_summary.setText(
            str(plan.get("summary") or "AI plan ready")
            + "\n"
            + painter_text("Explicit apply required")
            + f" · {len(plan.get('operations', []))}"
        )
        delivery = plan.get("delivery")
        delivery = delivery if isinstance(delivery, Mapping) else {}
        targets = delivery.get("targets")
        targets = targets if isinstance(targets, Mapping) else {}
        self.ai_delivery_label.setText(
            " · ".join(
                f"{target.upper()} "
                + (
                    painter_text("Ready")
                    if bool((targets.get(target) or {}).get("ok"))
                    else painter_text("Blocked")
                )
                for target in ("web", "app", "umg")
            )
        )

    def _request_ai_plan(self) -> None:
        prompt = self.ai_prompt_edit.text().strip()
        if self.ai_mode_combo.currentData() == "prototype":
            self.ai_prototype_plan_requested.emit(prompt)
        else:
            self.ai_plan_requested.emit(prompt)

    def _request_ai_apply(self) -> None:
        if self.ai_mode_combo.currentData() == "prototype":
            self.ai_prototype_apply_requested.emit(self._ai_plan)
        else:
            self.ai_apply_requested.emit(self._ai_plan)

    def set_status(self, text: str) -> None:
        self.status_label.setText(str(text))

    def set_audit_report(self, report: Mapping[str, Any] | None) -> None:
        payload = report if isinstance(report, Mapping) else {}
        accessibility = payload.get("accessibility")
        self.accessibility_panel.set_report(
            accessibility if isinstance(accessibility, Mapping) else None
        )

    def set_artifact(self, path: str) -> None:
        self._artifact_path = str(path or "")
        self.open_artifact_button.setEnabled(bool(self._artifact_path))

    def _choose_template_package(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Install Painter UI Template",
            "",
            "Tiger UI Template (*.tstemplate)",
        )
        if path:
            self.template_install_requested.emit(path)

    def _choose_directory(self, signal) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            signal.emit(path)

    def _choose_asset_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Export UI Assets")
        if not path:
            return
        formats = []
        if self.asset_png.isChecked():
            formats.append("png")
        if self.asset_webp.isChecked():
            formats.append("webp")
        if self.asset_svg.isChecked():
            formats.append("svg")
        self.assets_export_requested.emit(
            path,
            formats or ["png"],
            [1.0, 2.0, 3.0],
            self.asset_atlas.isChecked(),
        )

    def _choose_umg_output(self) -> None:
        project = self.unreal_project_edit.text().strip()
        if not project:
            self.set_status("Choose an Unreal .uproject before generation.")
            return
        output = QFileDialog.getExistingDirectory(self, "Package UMG Document")
        if output:
            self.umg_generate_requested.emit(project, output)

    def _resolve_selected_comment(self) -> None:
        item = self.review_list.currentItem()
        if item is not None:
            self.review_comment_update_requested.emit(
                str(item.data(256) or ""),
                {"resolved": True},
            )


__all__ = ["PainterUIProductionPanel"]

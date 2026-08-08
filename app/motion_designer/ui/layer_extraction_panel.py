"""Compact controls for AI image layer extraction and choreography."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)


class SegmentationInstallThread(QThread):
    finished_payload = Signal(dict)

    def __init__(self, command: list[str], parent=None) -> None:
        super().__init__(parent)
        self._command = [str(part) for part in command if str(part)]

    def run(self) -> None:  # pragma: no cover - exercised by user-confirmed install
        try:
            completed = subprocess.run(
                self._command,
                cwd=str(Path(__file__).resolve().parents[3]),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            self.finished_payload.emit({
                "ok": completed.returncode == 0,
                "returncode": int(completed.returncode),
                "stdout": str(completed.stdout or "")[-3000:],
                "stderr": str(completed.stderr or "")[-3000:],
            })
        except Exception as exc:
            self.finished_payload.emit({
                "ok": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(exc),
            })


class LayerExtractionPanel(QWidget):
    options_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionLayerExtractionPanel")
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(5)
        self._install_thread: SegmentationInstallThread | None = None

        self.segmentation = QComboBox(self)
        self._refresh_segmentation_choices()
        self.segmentation.setToolTip(
            "Auto uses BiRefNet Matting and SAM 2. Legacy Basic is never presented as an AI-quality result."
        )
        self.max_layers = QSpinBox(self)
        self.max_layers.setRange(1, 12)
        self.max_layers.setValue(5)
        self.max_layers.setToolTip("Maximum editable visual layers per image reference.")
        self.auto_detect = QCheckBox("Detect objects", self)
        self.auto_detect.setChecked(True)
        self.auto_detect.setToolTip(
            "Propose object boxes automatically before segmentation. Semantic labels require an optional local detector."
        )
        self.matting = QComboBox(self)
        self.matting.addItem("AI matte / preserve alpha", "edge_aware")
        self.matting.addItem("Binary", "binary")

        self.inpaint = QComboBox(self)
        self.inpaint.addItem("Auto", "auto")
        self.inpaint.addItem("Fast", "fast")
        self.inpaint.addItem(
            "Enhanced Local (fallback)",
            "enhanced_local",
        )
        self.inpaint.setToolTip(
            "Reconstructs pixels hidden behind extracted foreground layers."
        )
        self.variant = QComboBox(self)
        self.variant.addItem("Auto", "auto")
        self.variant.addItem("Clean", "clean")
        self.variant.addItem("Dynamic", "dynamic")
        self.variant.addItem("Collage", "collage")

        self.native_text = QCheckBox("Editable text", self)
        self.native_text.setChecked(True)
        self.native_text.setToolTip(
            "Only high-confidence OCR is rebuilt as native Motion typography."
        )
        self.ocr_threshold = QDoubleSpinBox(self)
        self.ocr_threshold.setRange(0.50, 0.98)
        self.ocr_threshold.setSingleStep(0.02)
        self.ocr_threshold.setDecimals(2)
        self.ocr_threshold.setValue(0.78)

        controls = (
            ("Segmentation", self.segmentation, 0, 0),
            ("Layers", self.max_layers, 0, 2),
            ("Background", self.inpaint, 1, 0),
            ("Motion", self.variant, 1, 2),
            ("OCR confidence", self.ocr_threshold, 2, 0),
            ("Matting", self.matting, 3, 0),
        )
        for label_text, control, row, column in controls:
            label = QLabel(label_text, self)
            label.setObjectName("MotionAIOptionLabel")
            layout.addWidget(label, row, column)
            layout.addWidget(control, row, column + 1)
        layout.addWidget(self.native_text, 2, 2, 1, 2)
        layout.addWidget(self.auto_detect, 3, 2, 1, 2)
        self.capability = QLabel(self)
        self.capability.setObjectName("MotionAIHint")
        self.capability.setWordWrap(True)
        layout.addWidget(self.capability, 4, 0, 1, 3)
        self.install_button = QPushButton("Install cutout AI", self)
        self.install_button.setObjectName("MotionAIInstallButton")
        self.install_button.clicked.connect(self.install_segmentation_ai)
        layout.addWidget(self.install_button, 4, 3)
        self.refresh_setup_status()
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        for control in (
            self.segmentation,
            self.max_layers,
            self.auto_detect,
            self.matting,
            self.inpaint,
            self.variant,
            self.native_text,
            self.ocr_threshold,
        ):
            signal = (
                control.currentIndexChanged
                if isinstance(control, QComboBox)
                else control.toggled
                if isinstance(control, QCheckBox)
                else control.valueChanged
            )
            signal.connect(lambda *_args: self.options_changed.emit())

    def options(self) -> dict:
        return {
            "max_decomposed_elements": int(self.max_layers.value()),
            "segmentation_mode": str(self.segmentation.currentData() or "auto"),
            "auto_detect_objects": bool(self.auto_detect.isChecked()),
            "matting_mode": str(self.matting.currentData() or "edge_aware"),
            "inpaint_mode": str(self.inpaint.currentData() or "auto"),
            "reconstruct_text": bool(self.native_text.isChecked()),
            "ocr_native_threshold": float(self.ocr_threshold.value()),
            "motion_variant": str(self.variant.currentData() or "auto"),
            "segmentation_setup_ready": self.segmentation_ready(),
        }

    def set_generating(self, active: bool) -> None:
        self.setEnabled(not active)

    def _refresh_segmentation_choices(self) -> None:
        previous = str(self.segmentation.currentData() or "auto")
        try:
            from app.motion_designer.segmentation_setup import segmentation_setup_status

            status = segmentation_setup_status()
        except Exception:
            status = {
                "automatic_cutout_ready": False,
                "assisted_segmentation_ready": False,
            }
        self.segmentation.blockSignals(True)
        self.segmentation.clear()
        auto_ready = bool(status.get("automatic_cutout_ready"))
        sam2_ready = bool(status.get("assisted_segmentation_ready"))
        self.segmentation.addItem(
            "Auto (BiRefNet + SAM 2)" if auto_ready else "Auto (AI not installed)",
            "auto",
        )
        self.segmentation.addItem(
            "BiRefNet Matting" if auto_ready else "BiRefNet Matting (not installed)",
            "birefnet",
        )
        self.segmentation.addItem(
            "SAM 2 Assisted" if sam2_ready else "SAM 2 Assisted (not installed)",
            "sam2",
        )
        self.segmentation.addItem("Legacy Basic (GrabCut)", "basic")
        index = self.segmentation.findData(previous)
        self.segmentation.setCurrentIndex(index if index >= 0 else 0)
        self.segmentation.blockSignals(False)

    def refresh_setup_status(self) -> dict[str, Any]:
        from app.motion_designer.segmentation_setup import segmentation_setup_status

        status = segmentation_setup_status()
        ready = bool(status.get("available"))
        if ready:
            self.capability.setText(
                "Cutout AI ready: BiRefNet soft-alpha matting and SAM 2 assisted masks."
            )
        else:
            missing = [
                str(row.get("label"))
                for row in status.get("providers", [])
                if not bool(row.get("available"))
            ]
            self.capability.setText(
                "Cutout AI is not installed. Missing: "
                + ", ".join(missing)
                + ". Legacy Basic remains available only as a compatibility tool."
            )
        self.install_button.setVisible(not ready)
        self.install_button.setEnabled(
            not ready
            and not (
                self._install_thread is not None
                and self._install_thread.isRunning()
            )
        )
        self._refresh_segmentation_choices()
        return status

    def segmentation_ready(self) -> bool:
        mode = str(self.segmentation.currentData() or "auto")
        if mode == "basic":
            return True
        status = self.refresh_setup_status()
        if mode == "sam2":
            return bool(status.get("assisted_segmentation_ready"))
        return bool(status.get("automatic_cutout_ready"))

    def ensure_segmentation_ready(self) -> bool:
        if self.segmentation_ready():
            return True
        answer = QMessageBox.question(
            self,
            "Motion AI cutout is not installed",
            (
                "BiRefNet Matting and SAM 2 are required for AI-quality layer extraction.\n\n"
                "Install them now? The download is about 1.3 GB and stays on this computer.\n\n"
                "You can explicitly choose Legacy Basic to use GrabCut instead."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.install_segmentation_ai()
        return False

    def install_segmentation_ai(self) -> None:
        if self._install_thread is not None and self._install_thread.isRunning():
            return
        from app.motion_designer.segmentation_setup import segmentation_install_plan

        plan = segmentation_install_plan()
        answer = QMessageBox.question(
            self,
            "Install Motion AI cutout models",
            (
                f"Target: {plan['target_root']}\n"
                f"Download: {plan['estimated_download']}\n\n"
                f"{plan['license_notice']}\n\n"
                "Continue with the local installation?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.capability.setText("Installing cutout AI. The editor remains usable...")
        self.install_button.setEnabled(False)
        thread = SegmentationInstallThread(plan["command"], self)
        thread.finished_payload.connect(self._finish_segmentation_install)
        thread.finished.connect(thread.deleteLater)
        self._install_thread = thread
        thread.start()

    def _finish_segmentation_install(self, payload: dict[str, Any]) -> None:
        self._install_thread = None
        status = self.refresh_setup_status()
        if bool(payload.get("ok")) and bool(status.get("available")):
            QMessageBox.information(
                self,
                "Motion AI",
                "BiRefNet Matting and SAM 2 are ready.",
            )
            self.options_changed.emit()
            return
        QMessageBox.warning(
            self,
            "Motion AI install failed",
            str(payload.get("stderr") or "The installed files did not pass readiness checks.")[-1600:],
        )


__all__ = ["LayerExtractionPanel"]

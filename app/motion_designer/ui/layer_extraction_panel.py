"""Compact controls for AI image layer extraction and choreography."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QSpinBox,
    QWidget,
)


class LayerExtractionPanel(QWidget):
    options_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionLayerExtractionPanel")
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(5)

        self.segmentation = QComboBox(self)
        self.segmentation.addItem("Auto", "auto")
        self.segmentation.addItem("Basic Local", "basic")
        try:
            from app.motion_designer.semantic_segmentation import (
                segmentation_capabilities,
            )

            sam_available = bool(
                segmentation_capabilities()["local_sam"]["available"]
            )
        except Exception:
            sam_available = False
        self.segmentation.addItem(
            "SAM" if sam_available else "SAM (not installed)",
            "sam",
        )
        self.segmentation.setToolTip(
            "Auto uses the strongest available local provider and records any fallback."
        )
        self.max_layers = QSpinBox(self)
        self.max_layers.setRange(1, 12)
        self.max_layers.setValue(5)
        self.max_layers.setToolTip("Maximum editable visual layers per image reference.")

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
        )
        for label_text, control, row, column in controls:
            label = QLabel(label_text, self)
            label.setObjectName("MotionAIOptionLabel")
            layout.addWidget(label, row, column)
            layout.addWidget(control, row, column + 1)
        layout.addWidget(self.native_text, 2, 2, 1, 2)
        capability = QLabel(
            (
                "SAM ready. Enhanced inpainting uses the local fallback."
                if sam_available
                else "SAM needs segment_anything + vit_b checkpoint; Basic Local remains available."
            ),
            self,
        )
        capability.setObjectName("MotionAIHint")
        capability.setWordWrap(True)
        layout.addWidget(capability, 3, 0, 1, 4)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        for control in (
            self.segmentation,
            self.max_layers,
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
            "inpaint_mode": str(self.inpaint.currentData() or "auto"),
            "reconstruct_text": bool(self.native_text.isChecked()),
            "ocr_native_threshold": float(self.ocr_threshold.value()),
            "motion_variant": str(self.variant.currentData() or "auto"),
        }

    def set_generating(self, active: bool) -> None:
        self.setEnabled(not active)


__all__ = ["LayerExtractionPanel"]

"""Inspector controls for tactile stop-motion timing and pose work."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.stop_motion import (
    MATERIAL_PRESETS,
    MOTION_STYLES,
    effective_stop_motion,
)


class StopMotionPanel(QWidget):
    timing_requested = Signal(object)
    material_requested = Signal(str, int)
    pose_capture_requested = Signal(str)
    pose_apply_requested = Signal(str)
    onion_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loading = False
        self._layer: MotionLayer | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        heading = QLabel("Stop Motion", self)
        heading.setObjectName("MotionInspectorSection")
        root.addWidget(heading)
        root.addWidget(QLabel(
            "Hold exposure, tactile pose variation, reusable poses, and audio-ready cadence.",
            self,
        ))

        form = QFormLayout()
        self.enabled = QCheckBox("Enable held exposure", self)
        form.addRow(self.enabled)
        self.exposure = QComboBox(self)
        self.exposure.addItem("Ones (every frame)", 1)
        self.exposure.addItem("Twos (two-frame hold)", 2)
        self.exposure.addItem("Threes (three-frame hold)", 3)
        form.addRow("Exposure", self.exposure)
        self.style = QComboBox(self)
        for style in MOTION_STYLES:
            self.style.addItem(style.replace("_", " ").title(), style)
        form.addRow("Motion Style", self.style)

        self.jitter = QDoubleSpinBox(self)
        self.jitter.setRange(0.0, 64.0)
        self.jitter.setSuffix(" px")
        form.addRow("Pose Jitter", self.jitter)
        self.rotation = QDoubleSpinBox(self)
        self.rotation.setRange(0.0, 12.0)
        self.rotation.setDecimals(2)
        self.rotation.setSuffix(" deg")
        form.addRow("Rotation Jitter", self.rotation)
        self.scale = QDoubleSpinBox(self)
        self.scale.setRange(0.0, 0.25)
        self.scale.setDecimals(3)
        self.scale.setSingleStep(0.005)
        form.addRow("Scale Jitter", self.scale)
        self.seed = QSpinBox(self)
        self.seed.setRange(0, 2_147_483_647)
        form.addRow("Locked Seed", self.seed)
        root.addLayout(form)

        timing = QPushButton("Apply Timing", self)
        timing.clicked.connect(self._emit_timing)
        root.addWidget(timing)

        material_row = QHBoxLayout()
        self.material = QComboBox(self)
        for preset in MATERIAL_PRESETS:
            self.material.addItem(preset.replace("_", " ").title(), preset)
        material = QPushButton("Apply Material", self)
        material.clicked.connect(
            lambda: self.material_requested.emit(
                str(self.material.currentData()),
                self.seed.value(),
            ),
        )
        material_row.addWidget(self.material, 1)
        material_row.addWidget(material)
        root.addLayout(material_row)

        self.pose_name = QLineEdit(self)
        self.pose_name.setPlaceholderText("Pose name")
        self.poses = QComboBox(self)
        pose_row = QHBoxLayout()
        capture = QPushButton("Capture", self)
        apply_pose = QPushButton("Apply", self)
        onion = QPushButton("Onion", self)
        capture.clicked.connect(self._emit_capture)
        apply_pose.clicked.connect(self._emit_pose_apply)
        onion.clicked.connect(self.onion_requested)
        pose_row.addWidget(capture)
        pose_row.addWidget(apply_pose)
        pose_row.addWidget(onion)
        root.addWidget(self.pose_name)
        root.addWidget(self.poses)
        root.addLayout(pose_row)
        self.status = QLabel("", self)
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        root.addStretch(1)
        self.set_context(None, None)

    def _emit_timing(self) -> None:
        self.timing_requested.emit({
            "enabled": self.enabled.isChecked(),
            "exposure_frames": int(self.exposure.currentData()),
            "pose_jitter_px": self.jitter.value(),
            "rotation_jitter_deg": self.rotation.value(),
            "scale_jitter": self.scale.value(),
            "motion_style": str(self.style.currentData()),
            "seed": self.seed.value(),
        })

    def _emit_capture(self) -> None:
        name = self.pose_name.text().strip() or "Pose"
        self.pose_capture_requested.emit(name)

    def _emit_pose_apply(self) -> None:
        pose_id = str(self.poses.currentData() or "")
        if pose_id:
            self.pose_apply_requested.emit(pose_id)

    def set_status(self, text: str) -> None:
        self.status.setText(str(text))

    def set_context(
        self,
        composition: MotionComposition | None,
        layer: MotionLayer | None,
    ) -> None:
        self._layer = layer
        self.setEnabled(composition is not None)
        if composition is None:
            return
        settings = effective_stop_motion(composition, layer)
        self._loading = True
        self.enabled.setChecked(bool(settings["enabled"]))
        self.exposure.setCurrentIndex(max(0, self.exposure.findData(settings["exposure_frames"])))
        self.style.setCurrentIndex(max(0, self.style.findData(settings["motion_style"])))
        self.jitter.setValue(float(settings["pose_jitter_px"]))
        self.rotation.setValue(float(settings["rotation_jitter_deg"]))
        self.scale.setValue(float(settings["scale_jitter"]))
        self.seed.setValue(int(settings["seed"]))
        current_pose = self.poses.currentData()
        self.poses.clear()
        for pose in composition.metadata.get("stop_motion_poses") or []:
            self.poses.addItem(str(pose.get("name") or "Pose"), str(pose.get("id") or ""))
        index = self.poses.findData(current_pose)
        if index >= 0:
            self.poses.setCurrentIndex(index)
        self._loading = False


__all__ = ["StopMotionPanel"]
